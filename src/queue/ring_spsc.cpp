#include "cpu_prefetch/queue/ring_spsc.hpp"

#include <limits>
#include <memory>

namespace cpu_prefetch::queue {

auto RingSpscQueue::storage_requirements(QueueCapacity capacity,
                                         CacheLineBytes cache_line_bytes)
    -> RingStorageRequirements {
  detail::validate_cache_line_bytes(cache_line_bytes.value);
  if (capacity.value == 0U) {
    throw QueueSetupError("ring capacity must be nonzero");
  }

  const auto slot_bytes = detail::checked_multiply(capacity.value, sizeof(Slot));
  const auto cursor_bytes = detail::checked_multiply(2U, cache_line_bytes.value);
  static_cast<void>(detail::checked_add(slot_bytes, cursor_bytes));
  return {slot_bytes, cursor_bytes};
}

RingSpscQueue::RingSpscQueue(QueueCapacity capacity, CacheLineBytes cache_line_bytes)
    : capacity_(capacity.value), cache_line_bytes_(cache_line_bytes.value) {
  const auto required = storage_requirements(capacity, cache_line_bytes);
  slot_storage_ = detail::AlignedBlock(required.slot_bytes, cache_line_bytes_);
  cursor_storage_ = detail::AlignedBlock(required.cursor_bytes, cache_line_bytes_);

  initialize_storage({{slot_storage_.data(), slot_storage_.size()},
                      {cursor_storage_.data(), cursor_storage_.size()}});
}

RingSpscQueue::RingSpscQueue(QueueCapacity capacity, CacheLineBytes cache_line_bytes,
                             RingStorageView storage)
    : capacity_(capacity.value), cache_line_bytes_(cache_line_bytes.value) {
  initialize_storage(storage);
}

void RingSpscQueue::initialize_storage(RingStorageView storage) {
  const auto required = storage_requirements({capacity_}, {cache_line_bytes_});
  const auto slot_bytes = required.slot_bytes;
  const auto cursor_bytes = required.cursor_bytes;
  if (storage.slots.size() != slot_bytes || storage.cursors.size() != cursor_bytes ||
      storage.slots.data() == nullptr || storage.cursors.data() == nullptr ||
      !detail::is_aligned(storage.slots.data(), cache_line_bytes_) ||
      !detail::is_aligned(storage.cursors.data(), cache_line_bytes_)) {
    throw QueueSetupError(
        "ring storage must have exact sizes and cache-line alignment");
  }
  const auto slot_begin = reinterpret_cast<std::uintptr_t>(storage.slots.data());
  const auto cursor_begin = reinterpret_cast<std::uintptr_t>(storage.cursors.data());
  if (slot_bytes > std::numeric_limits<std::uintptr_t>::max() - slot_begin ||
      cursor_bytes > std::numeric_limits<std::uintptr_t>::max() - cursor_begin) {
    throw QueueSetupError("ring storage address range overflows uintptr_t");
  }
  if (slot_begin < cursor_begin + cursor_bytes &&
      cursor_begin < slot_begin + slot_bytes) {
    throw QueueSetupError("ring slot and cursor storage must not overlap");
  }

  slots_ = reinterpret_cast<Slot*>(storage.slots.data());
  for (std::size_t index = 0; index < capacity_; ++index) {
    std::construct_at(&slots_[index]);
  }
  producer_ = std::construct_at(reinterpret_cast<CursorState*>(storage.cursors.data()));
  consumer_ = std::construct_at(
      reinterpret_cast<CursorState*>(storage.cursors.data() + cache_line_bytes_));
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
  return {cache_line_bytes_, 2U, capacity_ * sizeof(Slot) + 2U * cache_line_bytes_,
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

bool RingSpscQueue::reset_quiescent() noexcept {
  const auto before = audit_quiescent();
  if (before.occupied_slots != 0U || !before.positions_in_range ||
      producer_->position != consumer_->position) {
    return false;
  }
  for (std::size_t index = 0U; index < capacity_; ++index) {
    if (slots_[index].value.load(std::memory_order_relaxed) != nullptr) {
      return false;
    }
  }
  producer_->position = 0U;
  consumer_->position = 0U;
  const auto after = audit_quiescent();
  return after.occupied_slots == 0U && after.producer_position == 0U &&
         after.consumer_position == 0U && after.positions_in_range;
}

} // namespace cpu_prefetch::queue
