#include "cpu_prefetch/queue/common.hpp"

#include <limits>
#include <new>
#include <utility>

namespace cpu_prefetch::queue {

std::optional<EventPointer> EventPointer::from(const void* value) noexcept {
  if (value == nullptr) {
    return std::nullopt;
  }
  return EventPointer(value);
}

namespace detail {

AlignedBlock::AlignedBlock(std::size_t bytes, std::size_t alignment)
    : data_(
          static_cast<std::byte*>(::operator new(bytes, std::align_val_t(alignment)))),
      size_(bytes), alignment_(alignment) {}

AlignedBlock::~AlignedBlock() { release(); }

AlignedBlock::AlignedBlock(AlignedBlock&& other) noexcept
    : data_(std::exchange(other.data_, nullptr)), size_(std::exchange(other.size_, 0)),
      alignment_(std::exchange(other.alignment_, 0)) {}

AlignedBlock& AlignedBlock::operator=(AlignedBlock&& other) noexcept {
  if (this != &other) {
    release();
    data_ = std::exchange(other.data_, nullptr);
    size_ = std::exchange(other.size_, 0);
    alignment_ = std::exchange(other.alignment_, 0);
  }
  return *this;
}

void AlignedBlock::release() noexcept {
  if (data_ != nullptr) {
    ::operator delete(data_, std::align_val_t(alignment_));
  }
  data_ = nullptr;
  size_ = 0;
  alignment_ = 0;
}

bool is_power_of_two(std::size_t value) noexcept {
  return value != 0U && (value & (value - 1U)) == 0U;
}

void validate_cache_line_bytes(std::size_t cache_line_bytes) {
  if (!is_power_of_two(cache_line_bytes) ||
      cache_line_bytes < alignof(std::max_align_t)) {
    throw QueueSetupError(
        "cache-line bytes must be a power of two and satisfy max alignment");
  }
}

std::size_t checked_add(std::size_t left, std::size_t right) {
  if (right > std::numeric_limits<std::size_t>::max() - left) {
    throw QueueSetupError("queue storage size overflows size_t");
  }
  return left + right;
}

std::size_t checked_multiply(std::size_t left, std::size_t right) {
  if (left != 0U && right > std::numeric_limits<std::size_t>::max() / left) {
    throw QueueSetupError("queue storage size overflows size_t");
  }
  return left * right;
}

std::size_t round_up(std::size_t value, std::size_t alignment) {
  const auto remainder = value % alignment;
  if (remainder == 0U) {
    return value;
  }
  return checked_add(value, alignment - remainder);
}

bool is_aligned(const void* pointer, std::size_t alignment) noexcept {
  return reinterpret_cast<std::uintptr_t>(pointer) % alignment == 0U;
}

} // namespace detail
} // namespace cpu_prefetch::queue
