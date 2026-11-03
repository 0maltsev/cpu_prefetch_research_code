#include "cpu_prefetch/runner/stage17_schedule_source.hpp"

#include <openssl/evp.h>

#include <algorithm>
#include <array>
#include <cstddef>
#include <ctime>
#include <fcntl.h>
#include <limits>
#include <memory>
#include <stdexcept>
#include <sys/stat.h>
#include <unistd.h>

namespace cpu_prefetch::runner::stage17 {
namespace {
void require(bool condition, const char* message) {
  if (!condition)
    throw std::invalid_argument(message);
}
void before_deadline(std::uint64_t deadline) {
  timespec now{};
  require(::clock_gettime(CLOCK_MONOTONIC, &now) == 0 && now.tv_sec >= 0 &&
              now.tv_nsec >= 0 && now.tv_nsec < 1'000'000'000,
          "schedule source clock unavailable");
  const auto seconds = static_cast<std::uint64_t>(now.tv_sec);
  require(seconds <= (std::numeric_limits<std::uint64_t>::max() -
                      static_cast<std::uint64_t>(now.tv_nsec)) /
                         1'000'000'000U,
          "schedule source clock overflow");
  require(seconds * 1'000'000'000U + static_cast<std::uint64_t>(now.tv_nsec) < deadline,
          "schedule source deadline expired");
}
auto seal_check(int descriptor) -> struct stat {
  struct stat value{};
  require(descriptor >= 0 && ::fstat(descriptor, &value) == 0 &&
              S_ISREG(value.st_mode) && value.st_size >= 0,
          "schedule source must be a regular descriptor");
  const int flags = ::fcntl(descriptor, F_GETFL);
  const int seals = ::fcntl(descriptor, F_GET_SEALS);
  constexpr int required = F_SEAL_WRITE | F_SEAL_GROW | F_SEAL_SHRINK | F_SEAL_SEAL;
  require(flags >= 0 && (flags & O_ACCMODE) == O_RDONLY && seals >= 0 &&
              (seals & required) == required,
          "schedule source must be read-only and fully sealed");
  return value;
}
} // namespace

auto load_sealed_schedule_source(int descriptor, const SealedScheduleSourcePlan& plan)
    -> protocol::Result<std::vector<std::uint64_t>> {
  try {
    require(!plan.artifact_id.empty() && plan.artifact_id.size() <= 256U &&
                plan.canonical_sha256.size() == 64U &&
                std::all_of(plan.canonical_sha256.begin(), plan.canonical_sha256.end(),
                            [](char c) {
                              return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f');
                            }),
            "schedule source identity/hash is malformed");
    require(plan.source_origin_ticks < plan.source_horizon_ticks &&
                plan.deadline_monotonic_ns > 0U &&
                plan.offered_count <= plan.maximum_vector_bytes / 16U &&
                plan.offered_count <=
                    static_cast<std::uint64_t>(std::numeric_limits<off_t>::max()) /
                        8U &&
                plan.offered_count <= std::numeric_limits<std::size_t>::max() / 8U,
            "schedule source extent exceeds its bound");
    before_deadline(plan.deadline_monotonic_ns);
    const auto original = seal_check(descriptor);
    const auto total = plan.offered_count * 8U;
    require(static_cast<std::uint64_t>(original.st_size) == total,
            "schedule source size differs from exact offered count");
    std::vector<std::uint64_t> deadlines;
    require(plan.offered_count <= deadlines.max_size(),
            "schedule vector size overflow");
    deadlines.reserve(static_cast<std::size_t>(plan.offered_count));
    const std::unique_ptr<EVP_MD_CTX, decltype(&EVP_MD_CTX_free)> digest(
        EVP_MD_CTX_new(), &EVP_MD_CTX_free);
    require(digest && EVP_DigestInit_ex(digest.get(), EVP_sha256(), nullptr) == 1,
            "schedule source hash initialization failed");
    std::array<unsigned char, 8192U> block{};
    std::uint64_t offset = 0U;
    while (offset < total) {
      before_deadline(plan.deadline_monotonic_ns);
      const auto length = static_cast<std::size_t>(
          std::min<std::uint64_t>(block.size(), total - offset));
      std::size_t consumed = 0U;
      while (consumed < length) {
        before_deadline(plan.deadline_monotonic_ns);
        const auto amount =
            ::pread(descriptor, block.data() + consumed, length - consumed,
                    static_cast<off_t>(offset + consumed));
        require(amount > 0, "schedule source read failed or truncated");
        consumed += static_cast<std::size_t>(amount);
      }
      require(EVP_DigestUpdate(digest.get(), block.data(), length) == 1,
              "schedule source hashing failed");
      for (std::size_t index = 0U; index < length; index += 8U) {
        std::uint64_t value = 0U;
        for (std::size_t byte = 0U; byte < 8U; ++byte)
          value = (value << 8U) | block[index + byte];
        require(value >= plan.source_origin_ticks &&
                    value < plan.source_horizon_ticks &&
                    (deadlines.empty() || value >= deadlines.back()),
                "schedule source is outside its window or unordered");
        deadlines.push_back(value);
      }
      offset += length;
    }
    std::array<unsigned char, EVP_MAX_MD_SIZE> hash{};
    unsigned int length = 0U;
    require(EVP_DigestFinal_ex(digest.get(), hash.data(), &length) == 1 &&
                length == 32U,
            "schedule source final hash failed");
    constexpr std::string_view hex = "0123456789abcdef";
    std::string actual;
    actual.reserve(64U);
    for (std::size_t index = 0U; index < length; ++index) {
      actual.push_back(hex[hash[index] >> 4U]);
      actual.push_back(hex[hash[index] & 15U]);
    }
    require(actual == plan.canonical_sha256,
            "schedule source original byte hash differs");
    const auto final = seal_check(descriptor);
    require(final.st_dev == original.st_dev && final.st_ino == original.st_ino &&
                final.st_size == original.st_size &&
                final.st_mtim.tv_sec == original.st_mtim.tv_sec &&
                final.st_mtim.tv_nsec == original.st_mtim.tv_nsec,
            "schedule source descriptor identity changed");
    before_deadline(plan.deadline_monotonic_ns);
    return protocol::Result<std::vector<std::uint64_t>>::success(deadlines);
  } catch (const std::exception& exception) {
    return protocol::Result<std::vector<std::uint64_t>>::failure(
        {protocol::ErrorCategory::cross_field, "$/formal/schedule_source",
         "S17-SEALED-SCHEDULE-SOURCE", exception.what()});
  }
}
} // namespace cpu_prefetch::runner::stage17
