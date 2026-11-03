#include "cpu_prefetch/platform/prepared_prefetch_readback.hpp"

#include <gtest/gtest.h>

#include <algorithm>
#include <cerrno>
#include <cstring>
#include <fcntl.h>
#include <string_view>

namespace {

using namespace cpu_prefetch::platform;
using State = cpu_prefetch::protocol::RequestedHardwareState;

constexpr std::array<std::uint64_t, 3U> kPrestate{
    0x1234'5678'9abc'def0ULL, 0xfedc'ba98'7654'321aULL, 0x0f0f'0f0f'0f0f'0f05ULL};

auto prestate(std::uint32_t model) -> std::array<HardwarePrefetchMsrValue, 3U> {
  const auto& cpus = model == kIntelModel55 ? kHardwarePrefetchControlCpus
                                            : kHardwarePrefetchControlCpusV5;
  return {{{cpus[0], kPrestate[0]}, {cpus[1], kPrestate[1]}, {cpus[2], kPrestate[2]}}};
}

struct FakeFiles final : PrefetchReadbackOperations {
  CpuFamilyModel observed{kIntelFamily6, kIntelModel3E};
  bool identity_failure{false};
  std::size_t identity_calls{};
  std::size_t open_calls{};
  std::size_t read_calls{};
  std::size_t close_calls{};
  std::optional<std::size_t> fail_open_index;
  bool opened_without_identity{false};
  bool bad_descriptor{false};
  std::array<std::array<char, 64U>, kPreparedPrefetchMaxCpus> paths{};
  std::array<int, kPreparedPrefetchMaxCpus> flags{};
  std::array<bool, kPreparedPrefetchMaxCpus> closed{};
  std::array<std::size_t, kPreparedPrefetchMaxCpus> read_sizes{};
  std::array<std::uint64_t, kPreparedPrefetchMaxCpus> offsets{};
  std::array<std::uint64_t, kPreparedPrefetchMaxCpus> values{kPrestate};
  std::array<LinuxCallResult, kPreparedPrefetchMaxCpus> reads{};
  LinuxCallResult close_result{0, 0};

  FakeFiles() { reads.fill({sizeof(std::uint64_t), 0}); }
  auto identity() -> Result<CpuFamilyModel> override {
    ++identity_calls;
    if (identity_failure) {
      return Result<CpuFamilyModel>::failure(
          {ErrorCategory::missing_evidence, "$test", "FAKE-CPUID", "injected failure"});
    }
    return Result<CpuFamilyModel>::success(observed);
  }
  auto open_file(const char* path, int requested_flags) noexcept
      -> LinuxCallResult override {
    opened_without_identity = opened_without_identity || identity_calls == 0U;
    const auto index = open_calls++;
    if (index >= paths.size()) {
      return {-1, EMFILE};
    }
    const std::string_view text(path);
    std::copy_n(text.begin(), std::min(text.size(), paths[index].size() - 1U),
                paths[index].data());
    flags[index] = requested_flags;
    return fail_open_index == index
               ? LinuxCallResult{-1, EACCES}
               : LinuxCallResult{static_cast<std::int64_t>(100U + index), 0};
  }
  auto read_at(int descriptor, std::span<std::byte> bytes, FileOffset offset) noexcept
      -> LinuxCallResult override {
    ++read_calls;
    if (descriptor < 100 ||
        static_cast<std::size_t>(descriptor - 100) >= values.size()) {
      bad_descriptor = true;
      return {-1, EBADF};
    }
    const auto index = static_cast<std::size_t>(descriptor - 100);
    read_sizes[index] = bytes.size();
    offsets[index] = offset.value;
    const auto count = reads[index].return_value;
    if (count > 0) {
      const auto copied = std::min(
          {static_cast<std::size_t>(count), bytes.size(), sizeof(std::uint64_t)});
      std::memcpy(bytes.data(), &values[index], copied);
    }
    return reads[index];
  }
  auto close_file(int descriptor) noexcept -> LinuxCallResult override {
    ++close_calls;
    if (descriptor < 100 ||
        static_cast<std::size_t>(descriptor - 100) >= closed.size()) {
      bad_descriptor = true;
      return {-1, EBADF};
    }
    const auto index = static_cast<std::size_t>(descriptor - 100);
    bad_descriptor = bad_descriptor || closed[index];
    closed[index] = true;
    return close_result;
  }
};

TEST(PreparedPrefetchReadback,
     ResolvesBothModelsAndOpensExactReadOnlyPathsAfterIdentity) {
  for (const auto model : {kIntelModel55, kIntelModel3E}) {
    FakeFiles files;
    files.observed.model = model;
    PreparedPrefetchReadback reader(files);
    ASSERT_TRUE(reader.prepare({kIntelFamily6, model}, prestate(model)));
    EXPECT_EQ(files.identity_calls, 1U);
    EXPECT_FALSE(files.opened_without_identity);
    EXPECT_EQ(files.open_calls, 3U);
    EXPECT_EQ(files.read_calls, 0U);
    EXPECT_EQ(std::string_view(files.paths[0].data()), "/dev/cpu/0/msr");
    EXPECT_EQ(std::string_view(files.paths[1].data()), "/dev/cpu/1/msr");
    EXPECT_EQ(std::string_view(files.paths[2].data()),
              model == kIntelModel55 ? "/dev/cpu/26/msr" : "/dev/cpu/8/msr");
    for (const auto flags : files.flags) {
      EXPECT_EQ(flags, O_RDONLY | O_CLOEXEC);
    }
    EXPECT_EQ(reader.preparation().mapping_id, model == kIntelModel55
                                                   ? kHardwarePrefetchMappingId
                                                   : kHardwarePrefetchMappingId3E);
  }
}

TEST(PreparedPrefetchReadback, RejectsUnregisteredAndMismatchedModelsBeforeOpen) {
  for (const auto requested :
       {CpuFamilyModel{7U, kIntelModel3E}, CpuFamilyModel{kIntelFamily6, 0xffU},
        CpuFamilyModel{kIntelFamily6, kIntelModel55}}) {
    FakeFiles files;
    PreparedPrefetchReadback reader(files);
    EXPECT_FALSE(reader.prepare(requested, prestate(kIntelModel3E)));
    EXPECT_EQ(files.open_calls, 0U);
    EXPECT_EQ(files.read_calls, 0U);
    EXPECT_EQ(reader.preparation().stop,
              requested.model == kIntelModel55
                  ? PrefetchReadbackPreparationStop::identity_mismatch
                  : PrefetchReadbackPreparationStop::mapping_rejected);
  }
}

TEST(PreparedPrefetchReadback, RetainsCpuidFailureBeforeAnyDeviceAccess) {
  FakeFiles files;
  files.identity_failure = true;
  PreparedPrefetchReadback reader(files);
  EXPECT_FALSE(reader.prepare(files.observed, prestate(kIntelModel3E)));
  EXPECT_EQ(reader.preparation().stop,
            PrefetchReadbackPreparationStop::identity_failed);
  const auto& identity = reader.preparation().observed_identity;
  if (!identity.has_value()) {
    FAIL() << "missing CPUID failure";
    return;
  }
  EXPECT_FALSE(identity->has_value());
  ASSERT_EQ(identity->errors().size(), 1U);
  EXPECT_EQ(identity->errors()[0].rule_id, "FAKE-CPUID");
  EXPECT_EQ(files.open_calls, 0U);
}

TEST(PreparedPrefetchReadback,
     ResolverRejectsWrongMissingDuplicateAndCollapsedPrestate) {
  for (unsigned failure = 0U; failure < 4U; ++failure) {
    FakeFiles files;
    auto initial = prestate(kIntelModel3E);
    auto selected = std::span<const HardwarePrefetchMsrValue>(initial);
    if (failure == 0U) {
      initial[2].cpu = 26U;
    } else if (failure == 1U) {
      selected = selected.first(2U);
    } else if (failure == 2U) {
      initial[2].cpu = initial[0].cpu;
    } else {
      initial[1].value |= kHardwarePrefetchDisableMask;
    }
    PreparedPrefetchReadback reader(files);
    EXPECT_FALSE(reader.prepare(files.observed, selected));
    EXPECT_EQ(reader.preparation().stop,
              PrefetchReadbackPreparationStop::prestate_rejected);
    EXPECT_FALSE(reader.preparation().resolver_errors.empty());
    EXPECT_EQ(files.open_calls, 0U);
  }
}

TEST(PreparedPrefetchReadback, WholeRegisterH0H1ExpectationsAreFrozenInResolvedOrder) {
  FakeFiles files;
  auto initial = prestate(kIntelModel3E);
  std::reverse(initial.begin(), initial.end());
  PreparedPrefetchReadback reader(files);
  ASSERT_TRUE(reader.prepare(files.observed, initial));
  for (auto& value : initial) {
    value.value = 0U;
    value.cpu = 99U;
  }
  PrefetchReadbackSample h0;
  ASSERT_TRUE(reader.sample(State::h0, h0));
  for (auto& value : files.values) {
    value |= 0x0fULL;
  }
  PrefetchReadbackSample h1;
  ASSERT_TRUE(reader.sample(State::h1, h1));
  EXPECT_EQ(h0.cpu_count, 3U);
  EXPECT_EQ(h1.prepared_controller_identity, files.observed);
  for (std::size_t index = 0U; index < h1.cpu_count; ++index) {
    EXPECT_EQ(h0.cpus[index].cpu, kHardwarePrefetchControlCpusV5[index]);
    EXPECT_EQ(h0.cpus[index].observed_value, kPrestate[index]);
    EXPECT_EQ(h0.cpus[index].expected_value, kPrestate[index]);
    EXPECT_EQ(h1.cpus[index].observed_value, kPrestate[index] | 0x0fULL);
    EXPECT_EQ(h1.cpus[index].expected_value, kPrestate[index] | 0x0fULL);
    EXPECT_TRUE(h0.cpus[index].matches);
    EXPECT_TRUE(h1.cpus[index].matches);
    EXPECT_EQ(files.read_sizes[index], 8U);
    EXPECT_EQ(files.offsets[index], 0x1a4U);
  }
  EXPECT_EQ(files.open_calls, 3U);
  EXPECT_EQ(files.identity_calls, 1U);
  EXPECT_EQ(files.read_calls, 6U);
}

TEST(PreparedPrefetchReadback, RejectsWrongDisableBitsAndChangedSentinelBits) {
  for (const auto state : {State::h0, State::h1}) {
    for (const auto change : {std::uint64_t{1U}, std::uint64_t{1U} << 63U}) {
      FakeFiles files;
      PreparedPrefetchReadback reader(files);
      ASSERT_TRUE(reader.prepare(files.observed, prestate(kIntelModel3E)));
      if (state == State::h1) {
        for (auto& value : files.values) {
          value |= 0x0fULL;
        }
      }
      files.values[1] ^= change;
      PrefetchReadbackSample sample;
      EXPECT_FALSE(reader.sample(state, sample));
      EXPECT_EQ(sample.stop, PrefetchReadbackStop::value_mismatch);
      EXPECT_TRUE(sample.cpus[0].matches);
      EXPECT_FALSE(sample.cpus[1].matches);
      EXPECT_TRUE(sample.cpus[2].matches);
      EXPECT_EQ(files.read_calls, 3U);
    }
  }
}

TEST(PreparedPrefetchReadback, RetainsEveryShortReadAndReadsRemainingCpusWithoutRetry) {
  for (std::int64_t count = 0; count < 8; ++count) {
    FakeFiles files;
    files.reads[1] = {count, 0};
    PreparedPrefetchReadback reader(files);
    ASSERT_TRUE(reader.prepare(files.observed, prestate(kIntelModel3E)));
    PrefetchReadbackSample sample;
    EXPECT_FALSE(reader.sample(State::h0, sample));
    EXPECT_EQ(sample.stop, PrefetchReadbackStop::read_failed);
    const auto& read = sample.cpus[1].read;
    if (!read.has_value()) {
      FAIL() << "missing short read";
      return;
    }
    EXPECT_EQ(read->return_value, count);
    EXPECT_EQ(read->error_number, 0);
    EXPECT_FALSE(sample.cpus[1].observed_value.has_value());
    std::array<std::byte, 8U> expected{};
    std::memcpy(expected.data(), &kPrestate[1], static_cast<std::size_t>(count));
    EXPECT_EQ(sample.cpus[1].raw_bytes, expected);
    EXPECT_TRUE(sample.cpus[0].matches);
    EXPECT_TRUE(sample.cpus[2].matches);
    EXPECT_EQ(files.read_calls, 3U);
  }
}

TEST(PreparedPrefetchReadback,
     RetainsReadErrorsAndImpossibleCountsWithoutInventedValues) {
  for (const auto failed : {LinuxCallResult{-1, EINTR}, LinuxCallResult{-1, EIO},
                            LinuxCallResult{9, 0}, LinuxCallResult{8, EIO}}) {
    FakeFiles files;
    files.reads[0] = failed;
    PreparedPrefetchReadback reader(files);
    ASSERT_TRUE(reader.prepare(files.observed, prestate(kIntelModel3E)));
    PrefetchReadbackSample sample;
    EXPECT_FALSE(reader.sample(State::h0, sample));
    EXPECT_EQ(sample.stop, PrefetchReadbackStop::read_failed);
    const auto& read = sample.cpus[0].read;
    if (!read.has_value()) {
      FAIL() << "missing failed read";
      return;
    }
    EXPECT_EQ(read->return_value, failed.return_value);
    EXPECT_EQ(read->error_number, failed.error_number);
    EXPECT_FALSE(sample.cpus[0].observed_value.has_value());
    EXPECT_TRUE(sample.cpus[1].matches);
    EXPECT_TRUE(sample.cpus[2].matches);
    EXPECT_EQ(files.read_calls, 3U);
  }
}

TEST(PreparedPrefetchReadback, RejectsUnpreparedInvalidStateAndOutputReuseWithoutIo) {
  FakeFiles files;
  PreparedPrefetchReadback reader(files);
  PrefetchReadbackSample unprepared;
  EXPECT_FALSE(reader.sample(State::h0, unprepared));
  EXPECT_EQ(unprepared.stop, PrefetchReadbackStop::not_prepared);
  ASSERT_TRUE(reader.prepare(files.observed, prestate(kIntelModel3E)));
  PrefetchReadbackSample invalid;
  EXPECT_FALSE(reader.sample(State::not_applicable, invalid));
  EXPECT_EQ(invalid.stop, PrefetchReadbackStop::invalid_state);
  EXPECT_EQ(files.read_calls, 0U);
  PrefetchReadbackSample sample;
  ASSERT_TRUE(reader.sample(State::h0, sample));
  const auto prior = sample.cpus[0].raw_bytes;
  EXPECT_FALSE(reader.sample(State::h1, sample));
  EXPECT_TRUE(sample.succeeded());
  EXPECT_EQ(sample.requested_state, State::h0);
  EXPECT_EQ(sample.cpus[0].raw_bytes, prior);
  EXPECT_EQ(files.read_calls, 3U);
  EXPECT_FALSE(reader.sample(State::h0, unprepared));
  EXPECT_EQ(files.read_calls, 3U);
}

TEST(PreparedPrefetchReadback, OneShotPreparationAndPartialOpenCleanupRetainEveryFact) {
  for (std::size_t failed = 0U; failed < 3U; ++failed) {
    FakeFiles files;
    files.fail_open_index = failed;
    {
      PreparedPrefetchReadback reader(files);
      EXPECT_FALSE(reader.prepare(files.observed, prestate(kIntelModel3E)));
      EXPECT_EQ(reader.preparation().stop,
                PrefetchReadbackPreparationStop::open_failed);
      EXPECT_FALSE(reader.prepare(files.observed, prestate(kIntelModel3E)));
      EXPECT_EQ(files.open_calls, failed + 1U);
      const auto& opened = reader.preparation().cpus[failed].open;
      if (!opened.has_value()) {
        FAIL() << "missing open error";
        return;
      }
      EXPECT_EQ(opened->return_value, -1);
      EXPECT_EQ(opened->error_number, EACCES);
      PrefetchReadbackSample sample;
      EXPECT_FALSE(reader.sample(State::h0, sample));
      EXPECT_EQ(files.read_calls, 0U);
      EXPECT_TRUE(reader.release());
      EXPECT_TRUE(reader.release());
      EXPECT_EQ(files.close_calls, failed);
      for (std::size_t index = 0U; index < failed; ++index) {
        const auto& closed = reader.preparation().cpus[index].close;
        if (!closed.has_value()) {
          FAIL() << "missing successful close";
          return;
        }
        EXPECT_TRUE(closed->zero_return());
      }
    }
    EXPECT_EQ(files.close_calls, failed);
    EXPECT_FALSE(files.bad_descriptor);
  }
}

TEST(PreparedPrefetchReadback, CloseFailuresAreRetainedAndNeverRetried) {
  FakeFiles files;
  files.close_result = {-1, EINTR};
  {
    PreparedPrefetchReadback reader(files);
    ASSERT_TRUE(reader.prepare(files.observed, prestate(kIntelModel3E)));
    EXPECT_FALSE(reader.prepare(files.observed, prestate(kIntelModel3E)));
    EXPECT_FALSE(reader.release());
    EXPECT_FALSE(reader.release());
    EXPECT_EQ(files.close_calls, 3U);
    for (const auto& cpu : reader.preparation().cpus) {
      if (!cpu.close.has_value()) {
        FAIL() << "missing close error";
        return;
      }
      EXPECT_EQ(cpu.close->return_value, -1);
      EXPECT_EQ(cpu.close->error_number, EINTR);
    }
    PrefetchReadbackSample sample;
    EXPECT_FALSE(reader.sample(State::h0, sample));
    EXPECT_EQ(files.read_calls, 0U);
  }
  EXPECT_EQ(files.close_calls, 3U);
  EXPECT_FALSE(files.bad_descriptor);
}

TEST(PreparedPrefetchReadback, ReleaseBeforePreparationPreventsOpening) {
  FakeFiles files;
  PreparedPrefetchReadback reader(files);
  EXPECT_TRUE(reader.release());
  EXPECT_FALSE(reader.prepare(files.observed, prestate(kIntelModel3E)));
  EXPECT_EQ(files.open_calls, 0U);
  EXPECT_EQ(files.close_calls, 0U);
}

TEST(PreparedPrefetchReadback, DestructorClosesEverySuccessfullyOpenedHandle) {
  FakeFiles files;
  {
    PreparedPrefetchReadback reader(files);
    ASSERT_TRUE(reader.prepare(files.observed, prestate(kIntelModel3E)));
    EXPECT_EQ(files.close_calls, 0U);
  }
  EXPECT_EQ(files.close_calls, 3U);
  EXPECT_TRUE(std::all_of(files.closed.begin(), files.closed.end(),
                          [](bool closed) { return closed; }));
  EXPECT_FALSE(files.bad_descriptor);
}

} // namespace
