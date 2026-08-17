#ifndef CPU_PREFETCH_QUEUE_COMMON_HPP
#define CPU_PREFETCH_QUEUE_COMMON_HPP

#include <atomic>
#include <cstddef>
#include <cstdint>
#include <optional>
#include <stdexcept>

namespace cpu_prefetch::queue {

namespace testing {
struct QueuePhaseTestAccess;
}

struct QueueCapacity final {
  std::size_t value;
};

struct CacheLineBytes final {
  std::size_t value;
};

class EventPointer final {
public:
  [[nodiscard]] static std::optional<EventPointer> from(const void* value) noexcept;

  [[nodiscard]] const void* get() const noexcept { return value_; }

private:
  explicit EventPointer(const void* value) noexcept : value_(value) {}

  const void* value_;
};

enum class EnqueueResult : std::uint8_t {
  accepted,
  full,
};

enum class DequeueStatus : std::uint8_t {
  item,
  empty,
  recycler_invariant_failure,
};

struct DequeueResult final {
  DequeueStatus status;
  const void* event;
};

struct AtomicLockFreeEvidence final {
  std::size_t abi_pointer_width_bytes;
  std::size_t atomic_pointer_width_bytes;
  std::size_t atomic_pointer_alignment_bytes;
  bool always_lock_free;
  bool runtime_lock_free;
};

struct LayoutEvidence final {
  std::size_t requested_cache_line_bytes;
  std::size_t mutable_line_count;
  std::size_t storage_bytes;
  bool bases_aligned;
  bool ownership_lines_separated;
};

class QueueSetupError final : public std::invalid_argument {
public:
  using std::invalid_argument::invalid_argument;
};

namespace detail {

class AlignedBlock final {
public:
  AlignedBlock() noexcept = default;
  AlignedBlock(std::size_t bytes, std::size_t alignment);
  ~AlignedBlock();

  AlignedBlock(const AlignedBlock&) = delete;
  AlignedBlock& operator=(const AlignedBlock&) = delete;
  AlignedBlock(AlignedBlock&& other) noexcept;
  AlignedBlock& operator=(AlignedBlock&& other) noexcept;

  [[nodiscard]] std::byte* data() noexcept { return data_; }
  [[nodiscard]] const std::byte* data() const noexcept { return data_; }
  [[nodiscard]] std::size_t size() const noexcept { return size_; }
  [[nodiscard]] std::size_t alignment() const noexcept { return alignment_; }

private:
  void release() noexcept;

  std::byte* data_{nullptr};
  std::size_t size_{0};
  std::size_t alignment_{0};
};

[[nodiscard]] bool is_power_of_two(std::size_t value) noexcept;
void validate_cache_line_bytes(std::size_t cache_line_bytes);
[[nodiscard]] std::size_t checked_add(std::size_t left, std::size_t right);
[[nodiscard]] std::size_t checked_multiply(std::size_t left, std::size_t right);
[[nodiscard]] std::size_t round_up(std::size_t value, std::size_t alignment);
[[nodiscard]] bool is_aligned(const void* pointer, std::size_t alignment) noexcept;

} // namespace detail

static_assert(sizeof(std::atomic<const void*>) == sizeof(const void*));
static_assert(std::atomic<const void*>::is_always_lock_free);

} // namespace cpu_prefetch::queue

#endif // CPU_PREFETCH_QUEUE_COMMON_HPP
