#include "cpu_prefetch/platform/q15_msr.hpp"

#include <gtest/gtest.h>

#include <algorithm>
#include <array>
#include <cerrno>
#include <cstdint>
#include <cstring>
#include <fcntl.h>
#include <limits>
#include <map>
#include <string>
#include <utility>
#include <vector>

namespace {

using namespace cpu_prefetch::platform;

class FakePosixFiles final : public PosixFileOperations {
public:
  [[nodiscard]] auto open_file(const char* path, int flags) -> int override {
    opened_paths.emplace_back(path);
    open_flags.push_back(flags);
    if (fail_open) {
      errno = EACCES;
      return -1;
    }
    const auto cpu = cpu_from_path(path);
    if (cpu == std::numeric_limits<std::uint32_t>::max()) {
      errno = ENOENT;
      return -1;
    }
    descriptors.emplace(next_descriptor, cpu);
    return next_descriptor++;
  }

  [[nodiscard]] auto read_at(int descriptor, void* buffer, std::size_t size,
                             FileOffset offset) -> std::ptrdiff_t override {
    read_offsets.push_back(offset.value);
    const auto position = descriptors.find(descriptor);
    if (position == descriptors.end() || fail_read) {
      errno = EIO;
      return -1;
    }
    const auto value = values.at(position->second);
    std::memcpy(buffer, &value, size);
    return short_read ? static_cast<std::ptrdiff_t>(size - 1U)
                      : static_cast<std::ptrdiff_t>(size);
  }

  [[nodiscard]] auto write_at(int descriptor, const void* buffer, std::size_t size,
                              FileOffset offset) -> std::ptrdiff_t override {
    write_offsets.push_back(offset.value);
    const auto position = descriptors.find(descriptor);
    if (position == descriptors.end() || fail_write) {
      errno = EIO;
      return -1;
    }
    std::uint64_t value = 0U;
    std::memcpy(&value, buffer, size);
    values[position->second] = value;
    return short_write ? static_cast<std::ptrdiff_t>(size - 1U)
                       : static_cast<std::ptrdiff_t>(size);
  }

  [[nodiscard]] auto close_file(int descriptor) -> int override {
    closed.push_back(descriptor);
    descriptors.erase(descriptor);
    if (fail_close) {
      errno = EIO;
      return -1;
    }
    return 0;
  }

  std::map<std::uint32_t, std::uint64_t> values{
      {0U, 0x1234'5678'9abc'def0ULL},
      {1U, 0xfedc'ba98'7654'3210ULL},
      {26U, 0x0f0f'0f0f'0f0f'0f00ULL},
  };
  bool fail_open{false};
  bool fail_read{false};
  bool fail_write{false};
  bool fail_close{false};
  bool short_read{false};
  bool short_write{false};
  std::vector<std::string> opened_paths;
  std::vector<int> open_flags;
  std::vector<std::uint64_t> read_offsets;
  std::vector<std::uint64_t> write_offsets;
  std::vector<int> closed;

private:
  [[nodiscard]] static auto cpu_from_path(std::string_view path) -> std::uint32_t {
    if (path == "/dev/cpu/0/msr") {
      return 0U;
    }
    if (path == "/dev/cpu/1/msr") {
      return 1U;
    }
    if (path == "/dev/cpu/26/msr") {
      return 26U;
    }
    return std::numeric_limits<std::uint32_t>::max();
  }

  int next_descriptor{10};
  std::map<int, std::uint32_t> descriptors;
};

[[nodiscard]] auto prestate() -> std::vector<HardwarePrefetchMsrValue> {
  return {{0U, 0x1234'5678'9abc'def0ULL},
          {1U, 0xfedc'ba98'7654'3210ULL},
          {26U, 0x0f0f'0f0f'0f0f'0f00ULL}};
}

TEST(Q15FixedMsrAdapter, ReadsOnlyFixedPathsAndOffset) {
  FakePosixFiles files;
  LinuxHardwarePrefetchMsrBackend reader(files, FixedMsrAccess::read_only);
  EXPECT_EQ(reader.backend_id(), kQ15ReadBackendId);
  ASSERT_TRUE(reader.read(0U));
  ASSERT_TRUE(reader.read(1U));
  ASSERT_TRUE(reader.read(26U));
  EXPECT_FALSE(reader.read(2U));
  EXPECT_EQ(files.opened_paths,
            (std::vector<std::string>{"/dev/cpu/0/msr", "/dev/cpu/1/msr",
                                      "/dev/cpu/26/msr"}));
  EXPECT_EQ(files.read_offsets, (std::vector<std::uint64_t>{0x1a4U, 0x1a4U, 0x1a4U}));
  EXPECT_TRUE(std::all_of(files.open_flags.begin(), files.open_flags.end(),
                          [](int flags) { return (flags & O_ACCMODE) == O_RDONLY; }));
  const auto denied = reader.write(0U, 0U);
  EXPECT_FALSE(denied.succeeded);
  EXPECT_EQ(files.opened_paths.size(), 3U);
}

TEST(Q15FixedMsrAdapter, FailsClosedOnEveryIoBoundary) {
  FakePosixFiles files;
  LinuxHardwarePrefetchMsrBackend reader(files, FixedMsrAccess::read_only);
  files.fail_open = true;
  EXPECT_FALSE(reader.read(0U));
  files.fail_open = false;
  files.short_read = true;
  EXPECT_FALSE(reader.read(0U));
  files.short_read = false;
  files.fail_close = true;
  EXPECT_FALSE(reader.read(0U));

  FakePosixFiles write_files;
  LinuxHardwarePrefetchMsrBackend writer(write_files, FixedMsrAccess::read_write);
  write_files.short_write = true;
  EXPECT_FALSE(writer.write(0U, 0U).succeeded);
  write_files.short_write = false;
  write_files.fail_open = true;
  EXPECT_FALSE(writer.write(0U, 0U).succeeded);
  EXPECT_FALSE(writer.write(9U, 0U).succeeded);
}

TEST(Q15FixedMsrAdapter, DecodesSelectedFamilyAndModel) {
  const auto identity = decode_x86_family_model(0x0005'0657U);
  EXPECT_EQ(identity.family, 0x06U);
  EXPECT_EQ(identity.model, 0x55U);
  const auto extended_family = decode_x86_family_model(0x0010'0f10U);
  EXPECT_EQ(extended_family.family, 0x10U);
}

TEST(Q15FixedMsrAdapter, AppliesAndRestoresOneExactTransitionWithoutSelfReadback) {
  FakePosixFiles files;
  LinuxHardwarePrefetchMsrBackend writer(files, FixedMsrAccess::read_write);
  const auto plan = make_hardware_prefetch_plan(
      {kIntelFamily6, kIntelModel55},
      cpu_prefetch::protocol::RequestedHardwareState::h1, prestate());
  ASSERT_TRUE(plan);

  const auto applied = perform_hardware_prefetch_transition(
      plan.value(), 1U, HardwarePrefetchTransition::apply_h1, writer);
  ASSERT_TRUE(applied);
  EXPECT_EQ(applied.value().value, 0xfedc'ba98'7654'321fULL);
  EXPECT_EQ(files.values.at(1U), applied.value().value);
  EXPECT_EQ(files.read_offsets.size(), 1U);
  EXPECT_EQ(files.write_offsets.size(), 1U);

  const auto restored = perform_hardware_prefetch_transition(
      plan.value(), 1U, HardwarePrefetchTransition::restore_h0, writer);
  ASSERT_TRUE(restored);
  EXPECT_EQ(restored.value().value, 0xfedc'ba98'7654'3210ULL);
  EXPECT_EQ(files.values.at(1U), restored.value().value);
}

TEST(Q15FixedMsrAdapter, RejectsStaleOrUnregisteredTransition) {
  FakePosixFiles files;
  LinuxHardwarePrefetchMsrBackend writer(files, FixedMsrAccess::read_write);
  const auto plan = make_hardware_prefetch_plan(
      {kIntelFamily6, kIntelModel55},
      cpu_prefetch::protocol::RequestedHardwareState::h1, prestate());
  ASSERT_TRUE(plan);
  files.values[0U] ^= 0x100U;
  EXPECT_FALSE(perform_hardware_prefetch_transition(
      plan.value(), 0U, HardwarePrefetchTransition::apply_h1, writer));
  EXPECT_FALSE(perform_hardware_prefetch_transition(
      plan.value(), 2U, HardwarePrefetchTransition::apply_h1, writer));
  EXPECT_TRUE(files.write_offsets.empty());

  auto broad = plan.value();
  broad.requested[0].value ^= 0x100U;
  EXPECT_FALSE(perform_hardware_prefetch_transition(
      broad, 0U, HardwarePrefetchTransition::apply_h1, writer));
  EXPECT_TRUE(files.write_offsets.empty());
}

} // namespace
