#include "cpu_prefetch/queue/ring_spsc.hpp"

#include <memory>

namespace cpu_prefetch::queue {

RingSpscQueue::RingSpscQueue(QueueCapacity capacity, CacheLineBytes cache_line_bytes) {
  detail::validate_cache_line_bytes(cache_line_bytes.value);
  if (capacity.value == 0U) {
    throw QueueSetupError("ring capacity must be nonzero");
  }

  capacity_ = capacity.value;
  cache_line_bytes_ = cache_line_bytes.value;
  slot_storage_ = detail::AlignedBlock(
      detail::checked_multiply(capacity_, sizeof(Slot)), cache_line_bytes_);
  cursor_storage_ = detail::AlignedBlock(
      detail::checked_multiply(2U, cache_line_bytes_), cache_line_bytes_);

  slots_ = reinterpret_cast<Slot*>(slot_storage_.data());
  for (std::size_t index = 0; index < capacity_; ++index) {
    std::construct_at(&slots_[index]);
  }
  producer_ = std::construct_at(reinterpret_cast<CursorState*>(cursor_storage_.data()));
  consumer_ = std::construct_at(
      reinterpret_cast<CursorState*>(cursor_storage_.data() + cache_line_bytes_));
}

RingSpscQueue::~RingSpscQueue() {
  if (slots_ != nullptr) {
    for (std::size_t index = 0; index < capacity_; ++index) {
      std::destroy_at(&slots_[index]);
    }
  }
  if (producer_ != nullptr) {
    std::destroy_at(producer_);
  }
  if (consumer_ != nullptr) {
    std::destroy_at(consumer_);
  }
}

AtomicLockFreeEvidence RingSpscQueue::atomic_lock_free_evidence() const noexcept {
  bool runtime_lock_free = true;
  for (std::size_t index = 0; index < capacity_; ++index) {
    runtime_lock_free = runtime_lock_free && slots_[index].value.is_lock_free();
  }
  return {sizeof(const void*), sizeof(std::atomic<const void*>),
          alignof(std::atomic<const void*>),
          std::atomic<const void*>::is_always_lock_free, runtime_lock_free};
}

LayoutEvidence RingSpscQueue::layout_evidence() const noexcept {
  const auto cursor_distance = reinterpret_cast<std::uintptr_t>(consumer_) -
                               reinterpret_cast<std::uintptr_t>(producer_);
  return {cache_line_bytes_, 2U, slot_storage_.size() + cursor_storage_.size(),
          detail::is_aligned(slots_, cache_line_bytes_) &&
              detail::is_aligned(producer_, cache_line_bytes_) &&
              detail::is_aligned(consumer_, cache_line_bytes_),
          cursor_distance >= cache_line_bytes_};
}

RingQuiescentAudit RingSpscQueue::audit_quiescent() const noexcept {
  std::size_t occupied = 0;
  for (std::size_t index = 0; index < capacity_; ++index) {
    if (slots_[index].value.load(std::memory_order_relaxed) != nullptr) {
      ++occupied;
    }
  }
  return {occupied, producer_->position, consumer_->position,
          producer_->position < capacity_ && consumer_->position < capacity_};
}

} // namespace cpu_prefetch::queue
