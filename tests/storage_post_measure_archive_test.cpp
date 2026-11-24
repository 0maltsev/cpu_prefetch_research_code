#include "cpu_prefetch/storage/post_measure_archive.hpp"
#include "cpu_prefetch/workload/deterministic.hpp"

#include <algorithm>
#include <array>
#include <cerrno>
#include <fcntl.h>
#include <gtest/gtest.h>
#include <limits>
#include <stdexcept>
#include <unistd.h>
#include <vector>
#include <zstd.h>

namespace cpu_prefetch::storage {
namespace {
using Bytes = std::vector<std::byte>;
void put(std::span<std::byte> destination, std::uint64_t value) {
  for (std::size_t index = 0; index < 8U; ++index) {
    destination[index] = static_cast<std::byte>((value >> (index * 8U)) & 255U);
  }
}
auto get(std::span<const std::byte> source) -> std::uint64_t {
  std::uint64_t value = 0U;
  for (std::size_t index = 0; index < 8U; ++index) {
    value |= std::to_integer<std::uint64_t>(source[index]) << (index * 8U);
  }
  return value;
}
class File final {
public:
  explicit File(std::span<const std::byte> data = {}) {
    descriptor_ = ::mkstemp(name_.data());
    if (descriptor_ < 0) {
      throw std::runtime_error("mkstemp");
    }
    std::size_t offset = 0U;
    while (offset < data.size()) {
      const auto count =
          ::write(descriptor_, data.data() + offset, data.size() - offset);
      if (count <= 0) {
        throw std::runtime_error("fixture write");
      }
      offset += static_cast<std::size_t>(count);
    }
  }
  ~File() {
    static_cast<void>(::close(descriptor_));
    static_cast<void>(::unlink(name_.data()));
  }
  File(const File&) = delete;
  auto operator=(const File&) -> File& = delete;
  void readonly() {
    static_cast<void>(::close(descriptor_));
    descriptor_ = ::open(name_.data(), O_RDONLY | O_CLOEXEC);
    if (descriptor_ < 0) {
      throw std::runtime_error("fixture reopen");
    }
  }
  [[nodiscard]] auto fd() const -> int { return descriptor_; }
  [[nodiscard]] auto read_all() const -> Bytes {
    const auto size = ::lseek(descriptor_, 0, SEEK_END);
    if (size < 0) {
      throw std::runtime_error("fixture seek");
    }
    Bytes data(static_cast<std::size_t>(size));
    if (::pread(descriptor_, data.data(), data.size(), 0) != size) {
      throw std::runtime_error("fixture read");
    }
    return data;
  }

private:
  std::array<char, 25> name_{"/tmp/cpfa-test-XXXXXX"};
  int descriptor_{-1};
};
auto plan_for(std::span<const std::byte> data, ArchiveCodec codec,
              std::uint64_t width = 8U) -> ArchivePlan {
  const std::string hash(64U, 'a');
  return {{"TEST-ARTIFACT",
           codec == ArchiveCodec::rows ? "Q16B_NODE_ORDER" : "TEST_CONTROL",
           codec == ArchiveCodec::rows ? "NODEORDER-U64LE-v1" : "JSON", std::nullopt,
           std::nullopt, std::nullopt, data.size(), workload::sha256(data).hex(), codec,
           codec == ArchiveCodec::rows ? std::optional(width) : std::nullopt,
           std::nullopt, hash, hash, hash},
          {23, 16384U, 8388608U, 16777216U, 67108864U, 67108864U, 1048576U, 100000U,
           std::numeric_limits<std::uint64_t>::max()}};
}
struct Scratch final {
  Bytes canonical;
  Bytes transformed;
  Bytes encoded;
  explicit Scratch(const ArchivePlan& plan) {
    const auto sizes = archive_scratch_requirements(plan);
    canonical.resize(sizes.canonical_bytes);
    transformed.resize(sizes.transformed_bytes);
    encoded.resize(sizes.encoded_bytes);
  }
  auto view() -> ArchiveScratch { return {canonical, transformed, encoded}; }
};
class Operations final : public ArchiveFileOperations {
public:
  LinuxArchiveFileOperations native;
  std::size_t read_piece{std::numeric_limits<std::size_t>::max()};
  std::size_t write_piece{std::numeric_limits<std::size_t>::max()};
  int read_error{0};
  int write_error{0};
  int sync_error{0};
  bool zero_read{false};
  bool changed{false};
  std::uint64_t time_value{1U};
  bool regress{false};
  bool bad_clock{false};
  std::size_t reads{0};
  std::size_t writes{0};
  std::size_t inspections{0};
  std::size_t syncs{0};
  auto inspect(int descriptor) noexcept -> ArchiveStat override {
    auto result = native.inspect(descriptor);
    if (++inspections == 3U && changed) {
      ++result.changed_nanoseconds;
    }
    return result;
  }
  auto read(int descriptor, std::span<std::byte> data, std::uint64_t offset) noexcept
      -> ArchiveCall override {
    ++reads;
    if (read_error != 0) {
      return {-1, read_error};
    }
    if (zero_read) {
      return {0, 0};
    }
    return native.read(descriptor, data.first(std::min(data.size(), read_piece)),
                       offset);
  }
  auto write(int descriptor, std::span<const std::byte> data,
             std::uint64_t offset) noexcept -> ArchiveCall override {
    ++writes;
    if (write_error != 0) {
      return {-1, write_error};
    }
    return native.write(descriptor, data.first(std::min(data.size(), write_piece)),
                        offset);
  }
  auto synchronize(int descriptor) noexcept -> ArchiveCall override {
    ++syncs;
    return sync_error != 0 ? ArchiveCall{-1, sync_error}
                           : native.synchronize(descriptor);
  }
  auto clock() noexcept -> ArchiveClockRead override {
    if (bad_clock) {
      return {{-1, EIO}, 0U};
    }
    const auto now = time_value;
    time_value = regress ? 0U : time_value + 1U;
    return {{0, 0}, now};
  }
};
// Independent inverse of the published grammar; Python separately verifies
// profile, frame/window/header/hash/truncation rejection against actual files.
auto reconstruct(const Bytes& archive, const ArchivePlan& plan) -> Bytes {
  const auto input = std::span<const std::byte>(archive);
  if (input.size() < 16U) {
    throw std::runtime_error("truncated archive");
  }
  std::size_t cursor = 16U + static_cast<std::size_t>(get(input.subspan(8U, 8U)));
  const auto requirements = archive_scratch_requirements(plan);
  Bytes restored;
  for (std::uint64_t block = 0; block < requirements.block_count; ++block) {
    const auto header = input.subspan(cursor, 64U);
    cursor += 64U;
    EXPECT_EQ(get(header.first(8U)), block);
    EXPECT_EQ(get(header.subspan(8U, 8U)), restored.size());
    const auto decoded = static_cast<std::size_t>(get(header.subspan(16U, 8U)));
    const auto encoded = static_cast<std::size_t>(get(header.subspan(24U, 8U)));
    const auto frame = input.subspan(cursor, encoded);
    cursor += encoded;
    const auto digest = workload::sha256(frame);
    EXPECT_TRUE(std::ranges::equal(digest.bytes(), header.subspan(32U)));
    Bytes transformed(decoded);
    EXPECT_EQ(ZSTD_decompress(transformed.data(), transformed.size(), frame.data(),
                              frame.size()),
              decoded);
    if (plan.identity.codec == ArchiveCodec::bytes) {
      restored.insert(restored.end(), transformed.begin(), transformed.end());
    } else {
      Bytes canonical(decoded);
      if (!plan.identity.row_bytes) {
        throw std::runtime_error("missing test row geometry");
      }
      const auto width = static_cast<std::size_t>(*plan.identity.row_bytes);
      const auto rows = decoded / width;
      for (std::size_t column = 0; column < width / 8U; ++column) {
        std::uint64_t accumulator = 0U;
        for (std::size_t row = 0; row < rows; ++row) {
          accumulator +=
              get(std::span(transformed).subspan((column * rows + row) * 8U, 8U));
          put(std::span(canonical).subspan(row * width + column * 8U, 8U), accumulator);
        }
      }
      restored.insert(restored.end(), canonical.begin(), canonical.end());
    }
  }
  EXPECT_EQ(cursor + 56U, input.size());
  EXPECT_EQ(get(input.subspan(cursor + 8U, 8U)), requirements.block_count);
  EXPECT_EQ(get(input.subspan(cursor + 16U, 8U)), restored.size());
  const auto digest = workload::sha256(restored);
  EXPECT_TRUE(std::ranges::equal(digest.bytes(), input.subspan(cursor + 24U, 32U)));
  return restored;
}
TEST(PostMeasureArchive, RowBoundariesWrapAndIndependentFrames) {
  for (const std::size_t count : {0U, 1U, 8191U, 8192U, 8193U}) {
    Bytes data(count * 8U);
    for (std::size_t row = 0; row < count; ++row) {
      put(std::span(data).subspan(row * 8U, 8U),
          row % 2U == 0U ? ~std::uint64_t{row} : row);
    }
    const auto plan = plan_for(data, ArchiveCodec::rows);
    Scratch scratch(plan);
    File source(data);
    source.readonly();
    File target;
    const auto result =
        encode_post_measure_archive(source.fd(), target.fd(), plan, scratch.view());
    ASSERT_EQ(result.stop, ArchiveEncodeStop::complete_staging_synced);
    EXPECT_EQ(reconstruct(target.read_all(), plan), data);
    EXPECT_EQ(result.observed_archive_sha256,
              workload::sha256(target.read_all()).hex());
    EXPECT_EQ(source.read_all(), data);
  }
}
TEST(PostMeasureArchive, OpaqueByteBlockTailAndEmpty) {
  for (const std::size_t length : {0U, 1U, 4194305U}) {
    Bytes data(length);
    for (std::size_t i = 0; i < length; ++i) {
      data[i] = static_cast<std::byte>(i % 256U);
    }
    const auto plan = plan_for(data, ArchiveCodec::bytes);
    Scratch scratch(plan);
    File source(data);
    source.readonly();
    File target;
    ASSERT_EQ(
        encode_post_measure_archive(source.fd(), target.fd(), plan, scratch.view())
            .stop,
        ArchiveEncodeStop::complete_staging_synced);
    EXPECT_EQ(reconstruct(target.read_all(), plan), data);
  }
}
TEST(PostMeasureArchive, ActualPrimaryAndDemandPrefixesAllWorkers) {
  for (const auto* format :
       {"RAW-OBS-U64LE-LP-RUNID-v1", "Q16A-DEMAND-U64LE-LP-RUNID-v1"}) {
    for (const auto* worker : {"producer", "consumer"}) {
      const std::size_t body =
          std::string_view(format).starts_with("Q16A")
              ? 72U
              : (std::string_view(worker) == "producer" ? 120U : 80U);
      const auto width = 8U + body;
      Bytes data(width * 8193U);
      for (std::size_t row = 0; row < 8193U; ++row) {
        auto record = std::span(data).subspan(row * width, width);
        record[0] = std::byte{3};
        record[4] = std::byte{'R'};
        record[5] = std::byte{'0'};
        record[6] = std::byte{'1'};
        for (std::size_t word = 1U; word < width / 8U; ++word) {
          put(record.subspan(word * 8U, 8U), ~std::uint64_t{row + word});
        }
      }
      auto plan = plan_for(data, ArchiveCodec::rows);
      plan.identity.canonical_format = format;
      plan.identity.run_id = "R01";
      plan.identity.worker = worker;
      plan.identity.row_bytes = width;
      Scratch scratch(plan);
      File source(data);
      source.readonly();
      File target;
      ASSERT_EQ(
          encode_post_measure_archive(source.fd(), target.fd(), plan, scratch.view())
              .stop,
          ArchiveEncodeStop::complete_staging_synced);
      EXPECT_EQ(reconstruct(target.read_all(), plan), data);
    }
  }
}
TEST(PostMeasureArchive, MalformedRawRetainedAndExplicitWholeByteFallback) {
  Bytes data(128U, std::byte{255});
  auto plan = plan_for(data, ArchiveCodec::rows);
  plan.identity.canonical_format = "RAW-OBS-U64LE-LP-RUNID-v1";
  plan.identity.worker = "producer";
  plan.identity.run_id = "R01";
  plan.identity.row_bytes = 128U;
  Scratch scratch(plan);
  File source(data);
  source.readonly();
  File target;
  EXPECT_EQ(
      encode_post_measure_archive(source.fd(), target.fd(), plan, scratch.view()).stop,
      ArchiveEncodeStop::invalid_source_geometry);
  EXPECT_EQ(source.read_all(), data);
  EXPECT_FALSE(target.read_all().empty());
  plan.identity.codec = ArchiveCodec::bytes;
  plan.identity.row_bytes.reset();
  plan.identity.fallback_reason = "malformed canonical LP prefix retained";
  Scratch fallback(plan);
  File second;
  ASSERT_EQ(
      encode_post_measure_archive(source.fd(), second.fd(), plan, fallback.view()).stop,
      ArchiveEncodeStop::complete_staging_synced);
  EXPECT_EQ(reconstruct(second.read_all(), plan), data);
}
TEST(PostMeasureArchive, PositivePartialReadsAndWritesAdvanceExactly) {
  Bytes data(513U, std::byte{192});
  const auto plan = plan_for(data, ArchiveCodec::bytes);
  Scratch scratch(plan);
  File source(data);
  source.readonly();
  File target;
  Operations operations;
  operations.read_piece = 7U;
  operations.write_piece = 11U;
  const auto result = encode_post_measure_archive(source.fd(), target.fd(), plan,
                                                  scratch.view(), operations);
  ASSERT_EQ(result.stop, ArchiveEncodeStop::complete_staging_synced);
  EXPECT_GT(operations.reads, 1U);
  EXPECT_GT(operations.writes, 1U);
  EXPECT_EQ(reconstruct(target.read_all(), plan), data);
}
TEST(PostMeasureArchive, ReadFailureAndEintrNotRetried) {
  for (const int error : {EIO, EINTR, 0}) {
    Bytes data(8U);
    const auto plan = plan_for(data, ArchiveCodec::bytes);
    Scratch scratch(plan);
    File source(data);
    source.readonly();
    File target;
    Operations operations;
    operations.read_error = error;
    operations.zero_read = error == 0;
    const auto result = encode_post_measure_archive(source.fd(), target.fd(), plan,
                                                    scratch.view(), operations);
    EXPECT_EQ(result.stop, ArchiveEncodeStop::source_read);
    EXPECT_EQ(operations.reads, 1U);
    ASSERT_TRUE(result.failed_call);
    if (result.failed_call) {
      EXPECT_EQ(result.failed_call->error_number, error);
    }
    EXPECT_EQ(operations.syncs, 0U);
    EXPECT_EQ(source.read_all(), data);
  }
}
TEST(PostMeasureArchive, WriteAndSyncFailureRetainActualFacts) {
  for (const bool sync : {false, true}) {
    Bytes data(8U);
    const auto plan = plan_for(data, ArchiveCodec::bytes);
    Scratch scratch(plan);
    File source(data);
    source.readonly();
    File target;
    Operations operations;
    if (sync) {
      operations.sync_error = ENOSPC;
    } else {
      operations.write_error = EINTR;
    }
    const auto result = encode_post_measure_archive(source.fd(), target.fd(), plan,
                                                    scratch.view(), operations);
    EXPECT_EQ(result.stop,
              sync ? ArchiveEncodeStop::synchronize : ArchiveEncodeStop::output_write);
    ASSERT_TRUE(result.failed_call);
    if (result.failed_call) {
      EXPECT_EQ(result.failed_call->error_number, sync ? ENOSPC : EINTR);
    }
    EXPECT_EQ(operations.syncs, sync ? 1U : 0U);
    if (!sync) {
      EXPECT_EQ(operations.writes, 1U);
    }
  }
}
TEST(PostMeasureArchive, HashAndChangedSourceFailBeforeFooter) {
  for (const bool changed : {false, true}) {
    Bytes data(8U);
    auto plan = plan_for(data, ArchiveCodec::bytes);
    if (!changed) {
      plan.identity.canonical_sha256.assign(64U, '0');
    }
    Scratch scratch(plan);
    File source(data);
    source.readonly();
    File target;
    Operations operations;
    operations.changed = changed;
    const auto result = encode_post_measure_archive(source.fd(), target.fd(), plan,
                                                    scratch.view(), operations);
    EXPECT_EQ(result.stop, changed ? ArchiveEncodeStop::source_changed
                                   : ArchiveEncodeStop::source_hash_mismatch);
    EXPECT_EQ(operations.syncs, 0U);
    EXPECT_FALSE(result.observed_archive_sha256);
  }
}
TEST(PostMeasureArchive, ClockDeadlineRegressionFailureAndCallBudget) {
  for (const int mode : {0, 1, 2, 3}) {
    Bytes data(8U);
    auto plan = plan_for(data, ArchiveCodec::bytes);
    if (mode == 0) {
      plan.limits.deadline_monotonic_ns = 1U;
    }
    if (mode == 3) {
      plan.limits.maximum_io_calls = 1U;
    }
    Scratch scratch(plan);
    File source(data);
    source.readonly();
    File target;
    Operations operations;
    operations.regress = mode == 1;
    operations.bad_clock = mode == 2;
    const auto result = encode_post_measure_archive(source.fd(), target.fd(), plan,
                                                    scratch.view(), operations);
    EXPECT_EQ(result.stop, mode == 0 ? ArchiveEncodeStop::deadline
                                     : (mode == 3 ? ArchiveEncodeStop::io_budget
                                                  : ArchiveEncodeStop::clock_failure));
    EXPECT_EQ(operations.writes, 0U);
  }
}
TEST(PostMeasureArchive, ScratchAliasQuotaAndContextBounds) {
  Bytes data(8U);
  auto plan = plan_for(data, ArchiveCodec::rows);
  Scratch scratch(plan);
  File source(data);
  source.readonly();
  File alias_target;
  auto alias = scratch.view();
  alias.transformed = alias.canonical;
  EXPECT_EQ(
      encode_post_measure_archive(source.fd(), alias_target.fd(), plan, alias).stop,
      ArchiveEncodeStop::invalid_scratch);
  File quota_target;
  plan.limits.maximum_archive_bytes = 1U;
  EXPECT_EQ(
      encode_post_measure_archive(source.fd(), quota_target.fd(), plan, scratch.view())
          .stop,
      ArchiveEncodeStop::output_quota);
  EXPECT_TRUE(quota_target.read_all().empty());
  plan.limits.maximum_archive_bytes = 65536U;
  File context_target;
  plan.limits.maximum_observed_context_bytes = 1U;
  EXPECT_EQ(encode_post_measure_archive(source.fd(), context_target.fd(), plan,
                                        scratch.view())
                .stop,
            ArchiveEncodeStop::context_limit);
}
TEST(PostMeasureArchive, DescriptorIdentityWritableSourceAndExistingOutputRejected) {
  Bytes data(8U);
  const auto plan = plan_for(data, ArchiveCodec::bytes);
  Scratch scratch(plan);
  File source(data);
  File target;
  EXPECT_EQ(
      encode_post_measure_archive(source.fd(), target.fd(), plan, scratch.view()).stop,
      ArchiveEncodeStop::invalid_descriptors);
  source.readonly();
  EXPECT_EQ(
      encode_post_measure_archive(source.fd(), source.fd(), plan, scratch.view()).stop,
      ArchiveEncodeStop::invalid_descriptors);
  File occupied(data);
  EXPECT_EQ(
      encode_post_measure_archive(source.fd(), occupied.fd(), plan, scratch.view())
          .stop,
      ArchiveEncodeStop::invalid_descriptors);
  EXPECT_EQ(occupied.read_all(), data);
}
TEST(PostMeasureArchive, InvalidGeometryUnknownFormatsAndSizingOverflow) {
  Bytes data(8U);
  auto plan = plan_for(data, ArchiveCodec::rows);
  plan.identity.row_bytes = 16U;
  EXPECT_THROW(static_cast<void>(archive_scratch_requirements(plan)),
               std::invalid_argument);
  plan.identity.row_bytes = 8U;
  plan.identity.canonical_format = "unknown";
  EXPECT_THROW(static_cast<void>(archive_header_json(plan)), std::invalid_argument);
  plan.identity.canonical_format = "NODEORDER-U64LE-v1";
  plan.identity.canonical_size_bytes = 9U;
  EXPECT_THROW(static_cast<void>(archive_header_json(plan)), std::invalid_argument);
  plan.identity.canonical_size_bytes = 8U;
  plan.limits.maximum_header_bytes = std::numeric_limits<std::uint64_t>::max();
  EXPECT_THROW(static_cast<void>(archive_scratch_requirements(plan)),
               std::overflow_error);
}
} // namespace
} // namespace cpu_prefetch::storage
