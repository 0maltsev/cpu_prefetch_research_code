#ifndef CPU_PREFETCH_PLATFORM_PREPARED_RESIDENCY_HPP
#define CPU_PREFETCH_PLATFORM_PREPARED_RESIDENCY_HPP

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <span>
#include <stdexcept>

namespace cpu_prefetch::platform {

struct PageResidencyQueryResult final {
  std::int64_t syscall_return;
  int error_number;
  [[nodiscard]] auto succeeded() const noexcept -> bool {
    return syscall_return == 0 && error_number == 0;
  }
};

class LinuxPageResidencyQuery final {
public:
  [[nodiscard]] auto query_pages(std::span<void* const> pages,
                                 std::span<int> status) const noexcept
      -> PageResidencyQueryResult;
};

// Prepare once before capture, using caller-owned typed scratch. Sampling
// replaces status in place: retain each required snapshot before sampling
// again, or supply separate status storage for every planned observation.
// One owner may sample/read this query at a time. Nothing owns these regions.
class PreparedPageResidencyQuery final {
public:
  PreparedPageResidencyQuery(std::span<std::byte> mapping, std::size_t page_bytes,
                             std::span<void*> pages, std::span<int> status)
      : pages_(pages), status_(status) {
    const auto begin = reinterpret_cast<std::uintptr_t>(mapping.data());
    if (mapping.empty() || page_bytes == 0U || (page_bytes & (page_bytes - 1U)) != 0U ||
        begin % page_bytes != 0U || mapping.size() % page_bytes != 0U ||
        pages.size() != mapping.size() / page_bytes || status.size() != pages.size() ||
        pages.size() > std::numeric_limits<std::size_t>::max() / sizeof(void*) ||
        status.size() > std::numeric_limits<std::size_t>::max() / sizeof(int)) {
      throw std::invalid_argument(
          "residency query requires whole aligned pages and exact scratch sizes");
    }
    struct Range final {
      std::uintptr_t begin;
      std::size_t bytes;
    };
    const std::array ranges{
        Range{begin, mapping.size()},
        Range{reinterpret_cast<std::uintptr_t>(pages.data()), pages.size_bytes()},
        Range{reinterpret_cast<std::uintptr_t>(status.data()), status.size_bytes()}};
    for (std::size_t index = 0U; index < ranges.size(); ++index) {
      const auto range = ranges[index];
      if (range.begin == 0U ||
          range.bytes > std::numeric_limits<std::uintptr_t>::max() - range.begin) {
        throw std::invalid_argument("residency query address range overflows");
      }
      for (std::size_t other = 0U; other < index; ++other) {
        const auto prior = ranges[other];
        if (range.begin < prior.begin + prior.bytes &&
            prior.begin < range.begin + range.bytes) {
          throw std::invalid_argument("residency query mapping and scratch overlap");
        }
      }
    }
    for (std::size_t index = 0U; index < pages.size(); ++index) {
      pages[index] = mapping.data() + index * page_bytes;
    }
    std::fill(status.begin(), status.end(), -1);
  }

  template <typename Query>
  [[nodiscard]] auto sample(Query& query) const noexcept -> PageResidencyQueryResult {
    static_assert(noexcept(query.query_pages(std::span<void* const>(pages_), status_)));
    // Missing/partially written status must never inherit an earlier success.
    std::fill(status_.begin(), status_.end(), -1);
    return query.query_pages(std::span<void* const>(pages_), status_);
  }
  [[nodiscard]] auto page_status() const noexcept -> std::span<const int> {
    return status_;
  }
  [[nodiscard]] auto page_addresses() const noexcept -> std::span<void* const> {
    return pages_;
  }
  [[nodiscard]] auto all_pages_on(PageResidencyQueryResult result,
                                  std::uint32_t expected_node) const noexcept -> bool {
    if (!result.succeeded() ||
        expected_node > static_cast<std::uint32_t>(std::numeric_limits<int>::max())) {
      return false;
    }
    return std::all_of(status_.begin(), status_.end(), [expected_node](int node) {
      return node >= 0 && static_cast<std::uint32_t>(node) == expected_node;
    });
  }

private:
  std::span<void*> pages_;
  std::span<int> status_;
};

} // namespace cpu_prefetch::platform

#endif
