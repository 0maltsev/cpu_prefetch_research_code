#include "cpu_prefetch/platform/prepared_file_snapshot.hpp"

#include <gtest/gtest.h>

#include <algorithm>
#include <cerrno>
#include <cstring>
#include <fcntl.h>
#include <string>
#include <vector>

namespace {
using namespace cpu_prefetch::platform;

struct FakeFiles final : FileSnapshotOperations {
  std::string content{"0123456789"};
  std::array<char, 64U> path{};
  int flags{};
  std::size_t opens{}, calls{}, closes{};
  std::size_t delivery{8U};
  std::optional<std::size_t> overridden_call;
  LinuxCallResult override_result{-1, EINTR};
  LinuxCallResult open_result{42, 0};
  LinuxCallResult close_result{0, 0};
  bool bad_descriptor{false};
  auto open_file(const char* source, int mode) noexcept -> LinuxCallResult override {
    ++opens;
    flags = mode;
    const std::string_view name(source);
    std::copy_n(name.begin(), std::min(name.size(), path.size() - 1U), path.begin());
    return open_result;
  }
  auto read_at(int descriptor, std::span<std::byte> bytes, std::size_t offset) noexcept
      -> LinuxCallResult override {
    bad_descriptor = bad_descriptor || descriptor != 42;
    const auto call = calls++;
    if (overridden_call == call) {
      return override_result;
    }
    const auto available = offset < content.size() ? content.size() - offset : 0U;
    const auto count = std::min({bytes.size(), available, delivery});
    if (count > 0U) {
      std::memcpy(bytes.data(), content.data() + offset, count);
    }
    return {static_cast<std::int64_t>(count), 0};
  }
  auto close_file(int descriptor) noexcept -> LinuxCallResult override {
    bad_descriptor = bad_descriptor || descriptor != 42;
    ++closes;
    return close_result;
  }
};

struct Storage final {
  std::array<char, 10U> path{};
  std::array<std::array<std::byte, 16U>, kFileSnapshotGroups> bytes{};
  std::array<std::array<FileSnapshotRead, 4U>, kFileSnapshotGroups> reads{};
  std::array<FileSnapshotSample, kFileSnapshotGroups> samples{};
  FileSnapshotPlan plan{"/raw/file", 16U, 8U, 4U, {true, true, true, true, true, true}};
  Storage() {
    for (std::size_t index = 0U; index < samples.size(); ++index) {
      samples[index] = {bytes[index], reads[index]};
    }
  }
};

TEST(PreparedFileSnapshot, FreezesExactReadOnlyPathAndSixDistinctOneShotOutputs) {
  Storage storage;
  std::string input(storage.plan.path);
  storage.plan.path = input;
  FakeFiles files;
  PreparedFileSnapshot reader(files);
  ASSERT_TRUE(reader.prepare(storage.plan, storage.path, storage.samples));
  input[1U] = 'X';
  EXPECT_EQ(reader.preparation().plan.path, "/raw/file");
  EXPECT_EQ(std::string_view(files.path.data()), "/raw/file");
  EXPECT_EQ(files.flags, O_RDONLY | O_CLOEXEC);
  for (std::size_t group = 0U; group < kFileSnapshotGroups; ++group) {
    files.content[0U] = static_cast<char>('a' + static_cast<int>(group));
    ASSERT_EQ(reader.sample(group), FileSnapshotStop::complete);
    EXPECT_EQ(storage.samples[group].captured_bytes, 10U);
    EXPECT_EQ(storage.bytes[group][0U], static_cast<std::byte>('a' + group));
    EXPECT_EQ(reader.sample(group), FileSnapshotStop::output_reused);
  }
  EXPECT_EQ(storage.bytes[0U][0U], std::byte{'a'});
  EXPECT_EQ(files.opens, 1U);
  EXPECT_FALSE(reader.prepare(storage.plan, storage.path, storage.samples));
  EXPECT_TRUE(reader.release());
  EXPECT_TRUE(reader.release());
  EXPECT_EQ(files.closes, 1U);
  EXPECT_FALSE(files.bad_descriptor);
}

TEST(PreparedFileSnapshot, AdvancesShortReadsByActualCountAndProbesAtActualEnd) {
  Storage storage;
  FakeFiles files;
  files.delivery = 3U;
  PreparedFileSnapshot reader(files);
  ASSERT_TRUE(reader.prepare(storage.plan, storage.path, storage.samples));
  ASSERT_EQ(reader.sample(0U), FileSnapshotStop::complete);
  const auto& sample = storage.samples[0U];
  EXPECT_EQ(sample.captured_bytes, 10U);
  EXPECT_EQ(sample.data_reads, 4U);
  for (std::size_t index = 0U; index < 4U; ++index) {
    EXPECT_EQ(sample.reads[index].offset, index * 3U);
    EXPECT_EQ(sample.reads[index].requested_bytes, index == 3U ? 7U : 8U);
    const auto observed = sample.reads[index].observed;
    if (!observed.has_value()) {
      FAIL() << "missing data read";
      return;
    }
    EXPECT_EQ(observed->return_value, index == 3U ? 1 : 3);
  }
  EXPECT_EQ(sample.eof_probe.offset, 10U);
  if (!sample.eof_probe.observed.has_value()) {
    FAIL() << "missing EOF probe";
    return;
  }
  EXPECT_EQ(sample.eof_probe.observed->return_value, 0);
  EXPECT_EQ(files.calls, 5U);
}

TEST(PreparedFileSnapshot, ExactCapacityRequiresEofAndRetainsOverflowProbeByte) {
  for (const auto length : {16U, 17U}) {
    Storage storage;
    FakeFiles files;
    files.content.assign(length, 'q');
    PreparedFileSnapshot reader(files);
    ASSERT_TRUE(reader.prepare(storage.plan, storage.path, storage.samples));
    EXPECT_EQ(reader.sample(0U), length == 16U
                                     ? FileSnapshotStop::complete
                                     : FileSnapshotStop::byte_capacity_exhausted);
    const auto& sample = storage.samples[0U];
    EXPECT_EQ(sample.captured_bytes, 16U);
    EXPECT_EQ(sample.data_reads, 2U);
    EXPECT_EQ(sample.eof_probe.offset, 16U);
    EXPECT_EQ(files.calls, 3U);
    if (length == 17U) {
      EXPECT_EQ(sample.probe_byte, std::byte{'q'});
    }
  }
}

TEST(PreparedFileSnapshot, RejectsReadBudgetExhaustionWithRetainedPrefix) {
  Storage storage;
  storage.plan.max_data_reads = 2U;
  for (auto& sample : storage.samples) {
    sample.reads = sample.reads.first(2U);
  }
  FakeFiles files;
  files.delivery = 3U;
  PreparedFileSnapshot reader(files);
  ASSERT_TRUE(reader.prepare(storage.plan, storage.path, storage.samples));
  EXPECT_EQ(reader.sample(0U), FileSnapshotStop::read_budget_exhausted);
  EXPECT_EQ(storage.samples[0U].captured_bytes, 6U);
  EXPECT_EQ(storage.samples[0U].eof_probe.offset, 6U);
  EXPECT_EQ(storage.samples[0U].probe_byte, std::byte{'6'});
  EXPECT_EQ(files.calls, 3U);
}

TEST(PreparedFileSnapshot, EmptyAndArbitraryBinaryDataAreRetainedWithoutParsing) {
  for (const std::string& content :
       {std::string{}, std::string("\0\xff\xc3\xa9", 4U)}) {
    Storage storage;
    FakeFiles files;
    files.content = content;
    PreparedFileSnapshot reader(files);
    ASSERT_TRUE(reader.prepare(storage.plan, storage.path, storage.samples));
    EXPECT_EQ(reader.sample(0U), FileSnapshotStop::complete);
    const auto& sample = storage.samples[0U];
    EXPECT_EQ(sample.captured_bytes, content.size());
    EXPECT_FALSE(sample.eof_probe.observed.has_value());
    if (!content.empty()) {
      EXPECT_EQ(std::memcmp(sample.bytes.data(), content.data(), content.size()), 0);
    }
  }
}

TEST(PreparedFileSnapshot, ReadFailuresIncludingEintrAreNeverRetried) {
  for (const auto failed_call : {0U, 1U}) {
    Storage storage;
    FakeFiles files;
    files.overridden_call = failed_call;
    PreparedFileSnapshot reader(files);
    ASSERT_TRUE(reader.prepare(storage.plan, storage.path, storage.samples));
    EXPECT_EQ(reader.sample(0U), FileSnapshotStop::read_failed);
    const auto& sample = storage.samples[0U];
    EXPECT_EQ(sample.captured_bytes, failed_call * 8U);
    const auto observed = sample.reads[failed_call].observed;
    if (!observed.has_value()) {
      FAIL() << "missing failed read";
      return;
    }
    EXPECT_EQ(observed->return_value, -1);
    EXPECT_EQ(observed->error_number, EINTR);
    EXPECT_FALSE(sample.eof_probe.observed.has_value());
    EXPECT_EQ(files.calls, failed_call + 1U);
  }
}

TEST(PreparedFileSnapshot, ProbeErrorAndImpossibleCountsRetainActualCalls) {
  for (unsigned variant = 0U; variant < 3U; ++variant) {
    Storage storage;
    FakeFiles files;
    files.content.assign(16U, 'x');
    files.overridden_call = variant == 0U ? 0U : 2U;
    files.override_result = variant == 0U   ? LinuxCallResult{9, 0}
                            : variant == 1U ? LinuxCallResult{2, 0}
                                            : LinuxCallResult{-1, EIO};
    PreparedFileSnapshot reader(files);
    ASSERT_TRUE(reader.prepare(storage.plan, storage.path, storage.samples));
    EXPECT_EQ(reader.sample(0U), variant == 2U ? FileSnapshotStop::probe_failed
                                               : FileSnapshotStop::invalid_read_count);
    EXPECT_EQ(storage.samples[0U].captured_bytes, variant == 0U ? 0U : 16U);
    EXPECT_EQ(files.calls, variant == 0U ? 1U : 3U);
  }
}

TEST(PreparedFileSnapshot, ExplicitUnrequestedSlotsDoNoIoAndAreOneShot) {
  Storage storage;
  storage.plan.requested[1U] = false;
  FakeFiles files;
  PreparedFileSnapshot reader(files);
  EXPECT_EQ(reader.sample(0U), FileSnapshotStop::not_prepared);
  EXPECT_EQ(reader.sample(6U), FileSnapshotStop::invalid_slot);
  ASSERT_TRUE(reader.prepare(storage.plan, storage.path, storage.samples));
  EXPECT_EQ(reader.sample(1U), FileSnapshotStop::not_requested);
  EXPECT_FALSE(storage.samples[1U].io_complete());
  EXPECT_EQ(reader.sample(1U), FileSnapshotStop::output_reused);
  EXPECT_EQ(files.calls, 0U);
  EXPECT_TRUE(reader.release());
  EXPECT_EQ(reader.sample(0U), FileSnapshotStop::not_prepared);
}

TEST(PreparedFileSnapshot, InvalidPlansRejectBeforeOpen) {
  for (unsigned variant = 0U; variant < 9U; ++variant) {
    Storage storage;
    switch (variant) {
    case 0U:
      storage.plan.path = "relative";
      break;
    case 1U:
      storage.plan.path = std::string_view("/x\0y", 4U);
      break;
    case 2U:
      storage.plan.byte_capacity = 0U;
      break;
    case 3U:
      storage.plan.chunk_bytes = 0U;
      break;
    case 4U:
      storage.plan.chunk_bytes = 17U;
      break;
    case 5U:
      storage.plan.max_data_reads = 0U;
      break;
    case 6U:
      storage.plan.requested.fill(false);
      break;
    case 7U:
      storage.plan.byte_capacity = std::numeric_limits<std::size_t>::max();
      break;
    default:
      storage.plan.max_data_reads = std::numeric_limits<std::size_t>::max();
      break;
    }
    FakeFiles files;
    PreparedFileSnapshot reader(files);
    EXPECT_FALSE(reader.prepare(storage.plan, storage.path, storage.samples));
    EXPECT_EQ(reader.preparation().stop, FileSnapshotPreparationStop::invalid_plan);
    EXPECT_EQ(files.opens, 0U);
  }
}

TEST(PreparedFileSnapshot, AliasedOrWrongLengthStorageRejectsBeforeOpen) {
  for (unsigned variant = 0U; variant < 5U; ++variant) {
    Storage storage;
    auto path = std::span<char>(storage.path);
    switch (variant) {
    case 0U:
      storage.samples[1U].bytes = storage.samples[0U].bytes;
      break;
    case 1U:
      storage.samples[1U].reads = storage.samples[0U].reads;
      break;
    case 2U:
      storage.samples[0U].bytes = storage.samples[0U].bytes.first(15U);
      break;
    case 3U:
      path = path.first(9U);
      break;
    default:
      storage.plan.path = std::string_view(storage.path.data(), 9U);
      std::copy_n("/raw/file", 9U, storage.path.begin());
      break;
    }
    FakeFiles files;
    PreparedFileSnapshot reader(files);
    EXPECT_FALSE(reader.prepare(storage.plan, path, storage.samples));
    EXPECT_EQ(reader.preparation().stop, FileSnapshotPreparationStop::invalid_storage);
    EXPECT_EQ(files.opens, 0U);
  }
}

TEST(PreparedFileSnapshot, FrozenDescriptorsAndPrivateOneShotStatePreventReuse) {
  Storage storage;
  FakeFiles files;
  PreparedFileSnapshot reader(files);
  ASSERT_TRUE(reader.prepare(storage.plan, storage.path, storage.samples));
  storage.samples[1U].bytes = storage.samples[0U].bytes;
  EXPECT_EQ(reader.sample(1U), FileSnapshotStop::invalid_storage);
  EXPECT_EQ(files.calls, 0U);
  ASSERT_EQ(reader.sample(0U), FileSnapshotStop::complete);
  const auto calls = files.calls;
  storage.samples[0U] = {storage.bytes[0U], storage.reads[0U]};
  EXPECT_EQ(reader.sample(0U), FileSnapshotStop::output_reused);
  EXPECT_EQ(files.calls, calls);
}

TEST(PreparedFileSnapshot, OpenAndCloseFailuresAreRetainedAndNeverRetried) {
  Storage storage;
  FakeFiles files;
  files.open_result = {-1, EACCES};
  {
    PreparedFileSnapshot reader(files);
    EXPECT_FALSE(reader.prepare(storage.plan, storage.path, storage.samples));
    EXPECT_EQ(reader.preparation().stop, FileSnapshotPreparationStop::open_failed);
    if (!reader.preparation().open.has_value()) {
      FAIL() << "missing open result";
      return;
    }
    EXPECT_EQ(reader.preparation().open->error_number, EACCES);
    EXPECT_FALSE(reader.prepare(storage.plan, storage.path, storage.samples));
  }
  EXPECT_EQ(files.closes, 0U);
  files.open_result = {42, 0};
  files.close_result = {-1, EINTR};
  {
    PreparedFileSnapshot reader(files);
    ASSERT_TRUE(reader.prepare(storage.plan, storage.path, storage.samples));
    EXPECT_FALSE(reader.release());
    EXPECT_FALSE(reader.release());
    if (!reader.preparation().close.has_value()) {
      FAIL() << "missing close result";
      return;
    }
    EXPECT_EQ(reader.preparation().close->error_number, EINTR);
  }
  EXPECT_EQ(files.closes, 1U);
}

TEST(PreparedFileSnapshot, ReleaseBeforePreparationPreventsOpening) {
  Storage storage;
  FakeFiles files;
  PreparedFileSnapshot reader(files);
  EXPECT_TRUE(reader.release());
  EXPECT_FALSE(reader.prepare(storage.plan, storage.path, storage.samples));
  EXPECT_EQ(files.opens, 0U);
}

TEST(PreparedFileSnapshot, NativeProcSmapsUsesBoundedAdvancingReads) {
  constexpr std::string_view path = "/proc/self/smaps";
  // Software-test budget only; this is not a stand qualification/default.
  constexpr std::size_t capacity = std::size_t{2U} * 1024U * 1024U;
  constexpr std::size_t max_reads = 2048U;
  std::array<char, path.size() + 1U> frozen{};
  std::array<std::vector<std::byte>, kFileSnapshotGroups> buffers;
  std::array<std::vector<FileSnapshotRead>, kFileSnapshotGroups> reads;
  std::array<FileSnapshotSample, kFileSnapshotGroups> samples{};
  for (std::size_t index = 0U; index < samples.size(); ++index) {
    buffers[index].resize(capacity);
    reads[index].resize(max_reads);
    samples[index] = {buffers[index], reads[index]};
  }
  LinuxFileSnapshotOperations files;
  PreparedFileSnapshot reader(files);
  ASSERT_TRUE(reader.prepare(
      {path, capacity, 32768U, max_reads, {true, false, false, false, false, false}},
      frozen, samples));
  ASSERT_EQ(reader.sample(0U), FileSnapshotStop::complete);
  const auto& sample = samples[0U];
  EXPECT_GT(sample.captured_bytes, 0U);
  EXPECT_LE(sample.data_reads, max_reads);
  const std::string_view raw(reinterpret_cast<const char*>(sample.bytes.data()),
                             sample.captured_bytes);
  EXPECT_NE(raw.find("KernelPageSize:"), std::string_view::npos);
  EXPECT_TRUE(reader.release());
}

} // namespace
