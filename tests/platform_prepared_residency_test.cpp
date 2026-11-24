#include "cpu_prefetch/platform/prepared_residency.hpp"

#include <gtest/gtest.h>

#include <array>
#include <cerrno>
#include <limits>

namespace {
namespace platform = cpu_prefetch::platform;

struct InjectedQuery final {
  std::array<int, 2U> values{0, 0};
  std::size_t writes{2U};
  platform::PageResidencyQueryResult result{0, 0};
  std::size_t calls{0U};
  auto query_pages(std::span<void* const> pages, std::span<int> status) noexcept
      -> platform::PageResidencyQueryResult {
    ++calls;
    if (pages.size() != 2U || status.size() != 2U) {
      return {-1, EINVAL};
    }
    for (std::size_t index = 0U; index < writes; ++index) {
      status[index] = values[index];
    }
    return result;
  }
};

TEST(PreparedResidency, EnumeratesEveryPageAndRetainsActualCallerOwnedStatus) {
  alignas(4096) std::array<std::byte, 8192U> mapping{};
  std::array<void*, 2U> pages{};
  std::array<int, 2U> status{};
  platform::PreparedPageResidencyQuery prepared(mapping, 4096U, pages, status);
  EXPECT_EQ(pages[0U], mapping.data());
  EXPECT_EQ(pages[1U], mapping.data() + 4096U);
  EXPECT_EQ(status, (std::array<int, 2U>{-1, -1}));
  EXPECT_EQ(prepared.page_status().data(), status.data());
  InjectedQuery query;
  query.values = {3, 3};
  const auto result = prepared.sample(query);
  EXPECT_TRUE(result.succeeded());
  EXPECT_EQ(query.calls, 1U);
  EXPECT_TRUE(prepared.all_pages_on(result, 3U));
  EXPECT_FALSE(prepared.all_pages_on(result, 0U));
  EXPECT_EQ(status, query.values);
}

TEST(PreparedResidency, RejectsInvalidGeometryWithoutWritingScratch) {
  alignas(4096) std::array<std::byte, 8192U> mapping{};
  std::array<void*, 2U> pages{mapping.data(), mapping.data()};
  std::array<int, 2U> status{91, 97};
  const auto original_pages = pages;
  const auto original_status = status;
  const std::span<std::byte> bytes(mapping);
  const std::span<void*> addresses(pages);
  const std::span<int> statuses(status);
  for (const auto page_bytes : {0U, 3000U, 16384U}) {
    EXPECT_THROW(
        (platform::PreparedPageResidencyQuery(bytes, page_bytes, pages, status)),
        std::invalid_argument);
  }
  EXPECT_THROW(
      (platform::PreparedPageResidencyQuery(bytes.subspan(1U), 4096U, pages, status)),
      std::invalid_argument);
  EXPECT_THROW(
      (platform::PreparedPageResidencyQuery(bytes.first(8191U), 4096U, pages, status)),
      std::invalid_argument);
  EXPECT_THROW(
      (platform::PreparedPageResidencyQuery(bytes, 4096U, addresses.first(1U), status)),
      std::invalid_argument);
  EXPECT_THROW(
      (platform::PreparedPageResidencyQuery(bytes, 4096U, pages, statuses.first(1U))),
      std::invalid_argument);
  EXPECT_EQ(pages, original_pages);
  EXPECT_EQ(status, original_status);
}

TEST(PreparedResidency, RejectsScratchInsideObservedMappingBeforeWriting) {
  alignas(4096) std::array<void*, 512U> live_addresses{};
  std::array<int, 1U> status{103};
  const std::span<void*> addresses(live_addresses);
  const auto mapping = std::as_writable_bytes(addresses);
  static_assert(sizeof(live_addresses) == 4096U);
  EXPECT_THROW((platform::PreparedPageResidencyQuery(mapping, 4096U,
                                                     addresses.first(1U), status)),
               std::invalid_argument);
  EXPECT_TRUE(std::all_of(live_addresses.begin(), live_addresses.end(),
                          [](auto value) { return value == nullptr; }));
  EXPECT_EQ(status[0U], 103);
}

TEST(PreparedResidency, FailedOrPartialQueryCannotInheritAnEarlierSuccess) {
  alignas(4096) std::array<std::byte, 8192U> mapping{};
  std::array<void*, 2U> pages{};
  std::array<int, 2U> status{};
  platform::PreparedPageResidencyQuery prepared(mapping, 4096U, pages, status);
  InjectedQuery query;
  ASSERT_TRUE(prepared.all_pages_on(prepared.sample(query), 0U));
  query.writes = 0U;
  query.result = {-1, EPERM};
  const auto failed = prepared.sample(query);
  EXPECT_EQ(query.calls, 2U);
  EXPECT_EQ(failed.syscall_return, -1);
  EXPECT_EQ(failed.error_number, EPERM);
  EXPECT_EQ(status, (std::array<int, 2U>{-1, -1}));
  EXPECT_FALSE(prepared.all_pages_on(failed, 0U));
  query.result = {0, 0};
  query.writes = 1U;
  const auto partial = prepared.sample(query);
  EXPECT_TRUE(partial.succeeded());
  EXPECT_EQ(status, (std::array<int, 2U>{0, -1}));
  EXPECT_FALSE(prepared.all_pages_on(partial, 0U));
}

TEST(PreparedResidency, PreservesWrongNodesPageErrorsAndNonzeroSyscallResults) {
  alignas(4096) std::array<std::byte, 8192U> mapping{};
  std::array<void*, 2U> pages{};
  std::array<int, 2U> status{};
  platform::PreparedPageResidencyQuery prepared(mapping, 4096U, pages, status);
  InjectedQuery query;
  for (const auto values :
       {std::array<int, 2U>{0, 1}, std::array<int, 2U>{0, -EACCES}}) {
    query.values = values;
    const auto result = prepared.sample(query);
    EXPECT_EQ(status, values);
    EXPECT_FALSE(prepared.all_pages_on(result, 0U));
  }
  query.values = {0, 0};
  query.result = {1, 0};
  const auto incomplete = prepared.sample(query);
  EXPECT_EQ(incomplete.syscall_return, 1);
  EXPECT_FALSE(prepared.all_pages_on(incomplete, 0U));
  query.result = {0, 0};
  EXPECT_FALSE(prepared.all_pages_on(prepared.sample(query),
                                     std::numeric_limits<std::uint32_t>::max()));
}

TEST(PreparedResidency, LinuxAdapterRejectsBadLengthsWithoutInvokingSyscall) {
  platform::LinuxPageResidencyQuery query;
  std::array<void*, 1U> pages{};
  std::array<int, 2U> status{109, 113};
  const auto empty = query.query_pages({}, {});
  EXPECT_EQ(empty.syscall_return, -1);
  EXPECT_EQ(empty.error_number, EINVAL);
  const auto mismatched = query.query_pages(pages, status);
  EXPECT_EQ(mismatched.syscall_return, -1);
  EXPECT_EQ(mismatched.error_number, EINVAL);
  EXPECT_EQ(status, (std::array<int, 2U>{109, 113}));
}

} // namespace
