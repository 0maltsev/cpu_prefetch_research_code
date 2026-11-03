#include "cpu_prefetch/runner/stage17_schedule_source.hpp"

#include <gtest/gtest.h>

#include <array>
#include <fcntl.h>
#include <limits>
#include <linux/memfd.h>
#include <stdexcept>
#include <sys/syscall.h>
#include <unistd.h>

namespace {
using namespace cpu_prefetch::runner::stage17;
constexpr std::array<unsigned char, 24U> kBytes{0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0,
                                                0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1, 0};
constexpr std::string_view kHash =
    "eaed691da47d6566a045f77213f63042ecd60361a5dd33c279083bfad15955f1";
class Source final {
public:
  explicit Source(std::span<const unsigned char> bytes, bool seal = true) {
    writer_ = static_cast<int>(
        ::syscall(SYS_memfd_create, "schedule-test", MFD_CLOEXEC | MFD_ALLOW_SEALING));
    if (writer_ < 0 || ::write(writer_, bytes.data(), bytes.size()) !=
                           static_cast<ssize_t>(bytes.size()))
      throw std::runtime_error("test memfd preparation failed");
    if (seal && ::fcntl(writer_, F_ADD_SEALS,
                        F_SEAL_WRITE | F_SEAL_GROW | F_SEAL_SHRINK | F_SEAL_SEAL) != 0)
      throw std::runtime_error("test sealing failed");
    reader_ = ::open(("/proc/self/fd/" + std::to_string(writer_)).c_str(),
                     O_RDONLY | O_CLOEXEC);
    if (reader_ < 0)
      throw std::runtime_error("test read-only reopen failed");
  }
  ~Source() {
    static_cast<void>(::close(reader_));
    static_cast<void>(::close(writer_));
  }
  Source(const Source&) = delete;
  auto operator=(const Source&) -> Source& = delete;
  auto reader() const noexcept -> int { return reader_; }
  auto writer() const noexcept -> int { return writer_; }

private:
  int writer_{-1};
  int reader_{-1};
};
auto plan() -> SealedScheduleSourcePlan {
  return {"original-generator-schedule",
          std::string(kHash),
          3U,
          0U,
          257U,
          48U,
          std::numeric_limits<std::uint64_t>::max()};
}

TEST(Stage17ScheduleSource, LoadsExactBigEndianGoldenWithoutMutatingBorrowedOffset) {
  Source source(kBytes);
  ASSERT_EQ(::lseek(source.reader(), 7, SEEK_SET), 7);
  const auto loaded = load_sealed_schedule_source(source.reader(), plan());
  ASSERT_TRUE(loaded) << (loaded ? "" : loaded.errors().front().message);
  EXPECT_EQ(loaded.value(), (std::vector<std::uint64_t>{1U, 1U, 256U}));
  EXPECT_EQ(::lseek(source.reader(), 0, SEEK_CUR), 7);
  EXPECT_GE(::fcntl(source.reader(), F_GETFD), 0);
}

TEST(Stage17ScheduleSource, PreservesUnsignedHighBitValues) {
  constexpr std::array<unsigned char, 24U> bytes{
      0, 0, 0, 0, 0,   0,   0,   1,   1,   2,   3,   4,
      5, 6, 7, 8, 255, 255, 255, 255, 255, 255, 255, 254};
  Source source(bytes);
  auto input = plan();
  input.canonical_sha256 =
      "f2de8797331ae6661f6209b7ff8cead752118e55ee039b74a46c7bef4e1b4eb7";
  input.source_horizon_ticks = std::numeric_limits<std::uint64_t>::max();
  const auto loaded = load_sealed_schedule_source(source.reader(), input);
  ASSERT_TRUE(loaded);
  EXPECT_EQ(loaded.value(),
            (std::vector<std::uint64_t>{1U, 0x0102030405060708U, 0xfffffffffffffffeU}));
}

TEST(Stage17ScheduleSource, AllowsExactEmptyArtifactWithItsOriginalHash) {
  Source source({});
  auto input = plan();
  input.offered_count = 0U;
  input.maximum_vector_bytes = 0U;
  input.canonical_sha256 =
      "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855";
  const auto loaded = load_sealed_schedule_source(source.reader(), input);
  ASSERT_TRUE(loaded);
  EXPECT_TRUE(loaded.value().empty());
  input.canonical_sha256 = std::string(kHash);
  EXPECT_FALSE(load_sealed_schedule_source(source.reader(), input));
}

TEST(Stage17ScheduleSource, RejectsUnsealedWritableWrongSizeOrWrongHash) {
  Source source(kBytes);
  Source mutable_source(kBytes, false);
  EXPECT_FALSE(load_sealed_schedule_source(mutable_source.reader(), plan()));
  EXPECT_FALSE(load_sealed_schedule_source(source.writer(), plan()));
  EXPECT_FALSE(load_sealed_schedule_source(-1, plan()));
  auto input = plan();
  input.offered_count = 2U;
  EXPECT_FALSE(load_sealed_schedule_source(source.reader(), input));
  input = plan();
  input.canonical_sha256 = std::string(64U, '0');
  EXPECT_FALSE(load_sealed_schedule_source(source.reader(), input));
}

TEST(Stage17ScheduleSource, RejectsWindowOrderMemoryAndDeadlineFailures) {
  Source source(kBytes);
  auto input = plan();
  input.source_horizon_ticks = 256U;
  EXPECT_FALSE(load_sealed_schedule_source(source.reader(), input));
  input = plan();
  input.source_origin_ticks = 2U;
  EXPECT_FALSE(load_sealed_schedule_source(source.reader(), input));
  input = plan();
  input.maximum_vector_bytes = 47U;
  EXPECT_FALSE(load_sealed_schedule_source(source.reader(), input));
  input = plan();
  input.deadline_monotonic_ns = 1U;
  EXPECT_FALSE(load_sealed_schedule_source(source.reader(), input));
  auto unordered = kBytes;
  unordered[7U] = 2U;
  Source reordered(unordered);
  EXPECT_FALSE(load_sealed_schedule_source(reordered.reader(), plan()));
}
} // namespace
