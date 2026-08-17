#include "cpu_prefetch/queue/linked_spsc.hpp"

#include <algorithm>
#include <cstdint>
#include <memory>

namespace cpu_prefetch::queue {

LinkedSpscQueue::LinkedSpscQueue(QueueCapacity capacity,
                                 CacheLineBytes cache_line_bytes,
                                 ArenaAlignmentBytes arena_alignment_bytes,
                                 std::span<const std::size_t> node_order) {
  detail::validate_cache_line_bytes(cache_line_bytes.value);
  detail::validate_cache_line_bytes(arena_alignment_bytes.value);
  if (arena_alignment_bytes.value < cache_line_bytes.value) {
    throw QueueSetupError(
        "linked node-arena alignment must be at least the cache-line size");
  }
  if (capacity.value == 0U) {
    throw QueueSetupError("linked capacity must be nonzero");
  }
  const auto node_count = detail::checked_add(capacity.value, 1U);
  if (node_order.size() != node_count) {
    throw QueueSetupError("linked node order must contain capacity plus one nodes");
  }

  std::vector<bool> seen(node_count, false);
  for (const auto index : node_order) {
    if (index >= node_count || seen[index]) {
      throw QueueSetupError("linked node order must be a permutation");
    }
    seen[index] = true;
  }

  capacity_ = capacity.value;
  cache_line_bytes_ = cache_line_bytes.value;
  node_arena_alignment_bytes_ = arena_alignment_bytes.value;
  node_stride_bytes_ = detail::round_up(sizeof(Node), cache_line_bytes_);
  node_storage_ =
      detail::AlignedBlock(detail::checked_multiply(node_count, node_stride_bytes_),
                           node_arena_alignment_bytes_);
  recycler_storage_ = detail::AlignedBlock(
      detail::checked_multiply(capacity_, sizeof(RecyclerSlot)), cache_line_bytes_);
  ownership_storage_ = detail::AlignedBlock(
      detail::checked_multiply(4U, cache_line_bytes_), cache_line_bytes_);

  for (std::size_t index = 0; index < node_count; ++index) {
    auto* node = std::construct_at(node_at(index));
    node->arena_index = index;
  }
  recycler_slots_ = reinterpret_cast<RecyclerSlot*>(recycler_storage_.data());
  for (std::size_t index = 0; index < capacity_; ++index) {
    auto* slot = std::construct_at(&recycler_slots_[index]);
    slot->value.store(node_at(node_order[index + 1U]), std::memory_order_relaxed);
  }

  auto* sentinel = node_at(node_order[0]);
  producer_ =
      std::construct_at(reinterpret_cast<ProducerState*>(ownership_storage_.data()));
  producer_->tail = sentinel;
  consumer_ = std::construct_at(
      reinterpret_cast<ConsumerState*>(ownership_storage_.data() + cache_line_bytes_));
  consumer_->head = sentinel;
  recycler_producer_ = std::construct_at(reinterpret_cast<RecyclerPosition*>(
      ownership_storage_.data() + (2U * cache_line_bytes_)));
  recycler_consumer_ = std::construct_at(reinterpret_cast<RecyclerPosition*>(
      ownership_storage_.data() + (3U * cache_line_bytes_)));
}

LinkedSpscQueue::~LinkedSpscQueue() {
  if (recycler_slots_ != nullptr) {
    for (std::size_t index = 0; index < capacity_; ++index) {
      std::destroy_at(&recycler_slots_[index]);
    }
  }
  if (node_storage_.data() != nullptr) {
    for (std::size_t index = 0; index < capacity_ + 1U; ++index) {
      std::destroy_at(node_at(index));
    }
  }
  if (producer_ != nullptr) {
    std::destroy_at(producer_);
  }
  if (consumer_ != nullptr) {
    std::destroy_at(consumer_);
  }
  if (recycler_producer_ != nullptr) {
    std::destroy_at(recycler_producer_);
  }
  if (recycler_consumer_ != nullptr) {
    std::destroy_at(recycler_consumer_);
  }
}

LinkedSpscQueue::Node* LinkedSpscQueue::node_at(std::size_t index) noexcept {
  return reinterpret_cast<Node*>(node_storage_.data() + (index * node_stride_bytes_));
}

const LinkedSpscQueue::Node*
LinkedSpscQueue::node_at(std::size_t index) const noexcept {
  return reinterpret_cast<const Node*>(node_storage_.data() +
                                       (index * node_stride_bytes_));
}

std::optional<std::size_t> LinkedSpscQueue::index_of(const Node* node) const noexcept {
  const auto base = reinterpret_cast<std::uintptr_t>(node_storage_.data());
  const auto address = reinterpret_cast<std::uintptr_t>(node);
  if (address < base) {
    return std::nullopt;
  }
  const auto offset = address - base;
  if (offset % node_stride_bytes_ != 0U) {
    return std::nullopt;
  }
  const auto index = offset / node_stride_bytes_;
  if (index > capacity_) {
    return std::nullopt;
  }
  return index;
}

AtomicLockFreeEvidence LinkedSpscQueue::atomic_lock_free_evidence() const noexcept {
  bool runtime_lock_free = true;
  for (std::size_t index = 0; index < capacity_; ++index) {
    runtime_lock_free =
        runtime_lock_free && recycler_slots_[index].value.is_lock_free();
  }
  for (std::size_t index = 0; index < capacity_ + 1U; ++index) {
    runtime_lock_free = runtime_lock_free && node_at(index)->next.is_lock_free();
  }
  return {sizeof(void*), sizeof(std::atomic<Node*>), alignof(std::atomic<Node*>),
          std::atomic<Node*>::is_always_lock_free, runtime_lock_free};
}

LayoutEvidence LinkedSpscQueue::layout_evidence() const noexcept {
  const auto producer_address = reinterpret_cast<std::uintptr_t>(producer_);
  const auto consumer_address = reinterpret_cast<std::uintptr_t>(consumer_);
  const auto recycler_producer_address =
      reinterpret_cast<std::uintptr_t>(recycler_producer_);
  const auto recycler_consumer_address =
      reinterpret_cast<std::uintptr_t>(recycler_consumer_);
  const bool separated =
      consumer_address - producer_address >= cache_line_bytes_ &&
      recycler_producer_address - consumer_address >= cache_line_bytes_ &&
      recycler_consumer_address - recycler_producer_address >= cache_line_bytes_;
  bool nodes_aligned = node_stride_bytes_ % cache_line_bytes_ == 0U;
  for (std::size_t index = 0; index < capacity_ + 1U; ++index) {
    nodes_aligned =
        nodes_aligned && detail::is_aligned(node_at(index), cache_line_bytes_);
  }
  return {cache_line_bytes_, 4U,
          node_storage_.size() + recycler_storage_.size() + ownership_storage_.size(),
          nodes_aligned && detail::is_aligned(recycler_slots_, cache_line_bytes_) &&
              detail::is_aligned(producer_, cache_line_bytes_) &&
              detail::is_aligned(consumer_, cache_line_bytes_) &&
              detail::is_aligned(recycler_producer_, cache_line_bytes_) &&
              detail::is_aligned(recycler_consumer_, cache_line_bytes_),
          separated};
}

LinkedQuiescentAudit LinkedSpscQueue::audit_quiescent() const {
  const auto node_count = capacity_ + 1U;
  std::vector<bool> owned(node_count, false);
  std::vector<std::size_t> reachable_order;
  std::vector<std::size_t> recycler_order;
  reachable_order.reserve(node_count);
  recycler_order.reserve(capacity_);

  bool chain_acyclic = true;
  bool every_node_owned_once = true;
  bool tail_reachable = false;
  const Node* current = consumer_->head;
  while (current != nullptr) {
    const auto index = index_of(current);
    if (!index.has_value() || owned[*index]) {
      chain_acyclic = false;
      every_node_owned_once = false;
      break;
    }
    owned[*index] = true;
    reachable_order.push_back(*index);
    if (current == producer_->tail) {
      tail_reachable = true;
    }
    current = current->next.load(std::memory_order_relaxed);
  }

  const auto recycler_start = recycler_consumer_->position;
  bool encountered_empty = false;
  bool recycler_fifo_shape = true;
  for (std::size_t offset = 0; offset < capacity_; ++offset) {
    const auto position = (recycler_start + offset) % capacity_;
    const auto* node = recycler_slots_[position].value.load(std::memory_order_relaxed);
    if (node == nullptr) {
      encountered_empty = true;
      continue;
    }
    if (encountered_empty) {
      recycler_fifo_shape = false;
    }
    const auto index = index_of(node);
    if (!index.has_value() || owned[*index]) {
      every_node_owned_once = false;
      continue;
    }
    owned[*index] = true;
    recycler_order.push_back(*index);
  }

  every_node_owned_once = every_node_owned_once &&
                          std::ranges::all_of(owned, [](bool value) { return value; });
  const bool positions_in_range = recycler_producer_->position < capacity_ &&
                                  recycler_consumer_->position < capacity_;
  const auto queued_events = reachable_order.empty() ? 0U : reachable_order.size() - 1U;
  return {reachable_order.size(),
          queued_events,
          recycler_order.size(),
          std::move(reachable_order),
          std::move(recycler_order),
          chain_acyclic,
          tail_reachable,
          every_node_owned_once,
          recycler_fifo_shape,
          positions_in_range};
}

} // namespace cpu_prefetch::queue
