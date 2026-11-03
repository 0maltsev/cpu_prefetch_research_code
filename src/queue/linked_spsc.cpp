#include "cpu_prefetch/queue/linked_spsc.hpp"

#include <algorithm>
#include <array>
#include <cstdint>
#include <limits>
#include <memory>

namespace cpu_prefetch::queue {

auto LinkedSpscQueue::storage_requirements(QueueCapacity capacity,
                                           CacheLineBytes cache_line_bytes,
                                           ArenaAlignmentBytes arena_alignment_bytes)
    -> LinkedStorageRequirements {
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
  const auto stride = detail::round_up(sizeof(Node), cache_line_bytes.value);
  const auto node_bytes = detail::checked_multiply(node_count, stride);
  const auto recycler_bytes =
      detail::checked_multiply(capacity.value, sizeof(RecyclerSlot));
  const auto ownership_bytes = detail::checked_multiply(4U, cache_line_bytes.value);
  const auto order_bytes = detail::checked_multiply(node_count, sizeof(std::size_t));
  auto total = detail::checked_add(node_bytes, recycler_bytes);
  total = detail::checked_add(total, ownership_bytes);
  total = detail::checked_add(total, order_bytes);
  total = detail::checked_add(total, node_count);
  if (total > static_cast<std::size_t>(std::numeric_limits<std::ptrdiff_t>::max())) {
    throw QueueSetupError("linked storage exceeds addressable object extent");
  }
  return {node_bytes, recycler_bytes, ownership_bytes, stride, node_count, node_count};
}

LinkedSpscQueue::LinkedSpscQueue(QueueCapacity capacity,
                                 CacheLineBytes cache_line_bytes,
                                 ArenaAlignmentBytes arena_alignment_bytes,
                                 std::span<const std::size_t> node_order)
    : capacity_(capacity.value), cache_line_bytes_(cache_line_bytes.value),
      node_arena_alignment_bytes_(arena_alignment_bytes.value) {
  const auto required =
      storage_requirements(capacity, cache_line_bytes, arena_alignment_bytes);
  if (node_order.size() != required.order_count) {
    throw QueueSetupError("linked node order must contain capacity plus one nodes");
  }
  owned_initial_node_order_.resize(required.order_count);
  std::vector<std::byte> scratch(required.validation_bytes);
  node_storage_ =
      detail::AlignedBlock(required.node_bytes, node_arena_alignment_bytes_);
  recycler_storage_ = detail::AlignedBlock(required.recycler_bytes, cache_line_bytes_);
  ownership_storage_ =
      detail::AlignedBlock(required.ownership_bytes, cache_line_bytes_);
  initialize_storage(node_order,
                     {{node_storage_.data(), node_storage_.size()},
                      {recycler_storage_.data(), recycler_storage_.size()},
                      {ownership_storage_.data(), ownership_storage_.size()},
                      owned_initial_node_order_,
                      scratch});
}

LinkedSpscQueue::LinkedSpscQueue(QueueCapacity capacity,
                                 CacheLineBytes cache_line_bytes,
                                 ArenaAlignmentBytes arena_alignment_bytes,
                                 std::span<const std::size_t> node_order,
                                 LinkedStorageView storage)
    : capacity_(capacity.value), cache_line_bytes_(cache_line_bytes.value),
      node_arena_alignment_bytes_(arena_alignment_bytes.value) {
  initialize_storage(node_order, storage);
}

void LinkedSpscQueue::initialize_storage(std::span<const std::size_t> node_order,
                                         LinkedStorageView storage) {
  const auto required = storage_requirements({capacity_}, {cache_line_bytes_},
                                             {node_arena_alignment_bytes_});
  if (node_order.size() != required.order_count ||
      storage.nodes.size() != required.node_bytes ||
      storage.recycler.size() != required.recycler_bytes ||
      storage.ownership.size() != required.ownership_bytes ||
      storage.initial_order.size() != required.order_count ||
      storage.permutation_scratch.size() != required.validation_bytes) {
    throw QueueSetupError("linked storage and order must have exact sizes");
  }
  struct Range final {
    const void* pointer;
    std::size_t bytes;
    std::size_t alignment;
  };
  const std::array ranges{
      Range{this, sizeof(*this), alignof(LinkedSpscQueue)},
      Range{node_order.data(), node_order.size_bytes(), alignof(std::size_t)},
      Range{storage.nodes.data(), storage.nodes.size(), node_arena_alignment_bytes_},
      Range{storage.recycler.data(), storage.recycler.size(), cache_line_bytes_},
      Range{storage.ownership.data(), storage.ownership.size(), cache_line_bytes_},
      Range{storage.initial_order.data(), storage.initial_order.size_bytes(),
            alignof(std::size_t)},
      Range{storage.permutation_scratch.data(), storage.permutation_scratch.size(),
            alignof(std::byte)}};
  for (std::size_t index = 0U; index < ranges.size(); ++index) {
    const auto current = ranges[index];
    const auto begin = reinterpret_cast<std::uintptr_t>(current.pointer);
    if (current.pointer == nullptr ||
        !detail::is_aligned(current.pointer, current.alignment) ||
        current.bytes > std::numeric_limits<std::uintptr_t>::max() - begin) {
      throw QueueSetupError("linked storage alignment/address extent is invalid");
    }
    for (std::size_t prior = 0U; prior < index; ++prior) {
      const auto other = reinterpret_cast<std::uintptr_t>(ranges[prior].pointer);
      if (begin < other + ranges[prior].bytes && other < begin + current.bytes) {
        throw QueueSetupError("linked storage ranges must not overlap");
      }
    }
  }
  std::fill(storage.permutation_scratch.begin(), storage.permutation_scratch.end(),
            std::byte{});
  for (const auto index : node_order) {
    if (index >= required.order_count ||
        storage.permutation_scratch[index] != std::byte{}) {
      throw QueueSetupError("linked node order must be a permutation");
    }
    storage.permutation_scratch[index] = std::byte{1U};
  }
  std::copy(node_order.begin(), node_order.end(), storage.initial_order.begin());
  initial_node_order_ = storage.initial_order;
  node_bytes_ = storage.nodes;
  node_stride_bytes_ = required.node_stride_bytes;
  const auto node_count = required.order_count;

  for (std::size_t index = 0; index < node_count; ++index) {
    auto* node = std::construct_at(node_at(index));
    node->arena_index = index;
  }
  recycler_slots_ = reinterpret_cast<RecyclerSlot*>(storage.recycler.data());
  for (std::size_t index = 0; index < capacity_; ++index) {
    auto* slot = std::construct_at(&recycler_slots_[index]);
    slot->value.store(node_at(node_order[index + 1U]), std::memory_order_relaxed);
  }

  auto* sentinel = node_at(node_order[0]);
  producer_ =
      std::construct_at(reinterpret_cast<ProducerState*>(storage.ownership.data()));
  producer_->tail = sentinel;
  consumer_ = std::construct_at(
      reinterpret_cast<ConsumerState*>(storage.ownership.data() + cache_line_bytes_));
  consumer_->head = sentinel;
  recycler_producer_ = std::construct_at(reinterpret_cast<RecyclerPosition*>(
      storage.ownership.data() + (2U * cache_line_bytes_)));
  recycler_consumer_ = std::construct_at(reinterpret_cast<RecyclerPosition*>(
      storage.ownership.data() + (3U * cache_line_bytes_)));
}

LinkedSpscQueue::~LinkedSpscQueue() {
  if (recycler_slots_ != nullptr) {
    for (std::size_t index = 0; index < capacity_; ++index) {
      std::destroy_at(&recycler_slots_[index]);
    }
  }
  if (node_bytes_.data() != nullptr) {
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
  return reinterpret_cast<Node*>(node_bytes_.data() + (index * node_stride_bytes_));
}

const LinkedSpscQueue::Node*
LinkedSpscQueue::node_at(std::size_t index) const noexcept {
  return reinterpret_cast<const Node*>(node_bytes_.data() +
                                       (index * node_stride_bytes_));
}

std::optional<std::size_t> LinkedSpscQueue::index_of(const Node* node) const noexcept {
  const auto base = reinterpret_cast<std::uintptr_t>(node_bytes_.data());
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
          node_bytes_.size() + capacity_ * sizeof(RecyclerSlot) +
              4U * cache_line_bytes_,
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

bool LinkedSpscQueue::reset_quiescent() noexcept {
  const auto node_count = capacity_ + 1U;
  const auto valid_empty_cycle = [this, node_count]() noexcept {
    if (initial_node_order_.size() != node_count ||
        producer_->tail != consumer_->head ||
        recycler_producer_->position >= capacity_ ||
        recycler_consumer_->position >= capacity_ ||
        recycler_producer_->position != recycler_consumer_->position) {
      return false;
    }
    const auto sentinel_index = index_of(consumer_->head);
    if (!sentinel_index.has_value() ||
        consumer_->head->next.load(std::memory_order_relaxed) != nullptr) {
      return false;
    }
    for (const auto index : initial_node_order_) {
      if (index >= node_count) {
        return false;
      }
    }
    const auto found = std::find(initial_node_order_.begin(), initial_node_order_.end(),
                                 *sentinel_index);
    if (found == initial_node_order_.end()) {
      return false;
    }
    auto order_position = static_cast<std::size_t>(found - initial_node_order_.begin());
    auto recycler_position = recycler_consumer_->position;
    for (std::size_t count = 0U; count < capacity_; ++count) {
      order_position = order_position + 1U == node_count ? 0U : order_position + 1U;
      const auto* expected = node_at(initial_node_order_[order_position]);
      if (expected == consumer_->head || recycler_slots_[recycler_position].value.load(
                                             std::memory_order_relaxed) != expected) {
        return false;
      }
      recycler_position = next_position(recycler_position);
    }
    return true;
  };
  if (!valid_empty_cycle()) {
    return false;
  }
  for (std::size_t index = 0U; index < node_count; ++index) {
    auto* node = node_at(index);
    node->next.store(nullptr, std::memory_order_relaxed);
    node->event = nullptr;
  }
  for (std::size_t index = 0U; index < capacity_; ++index) {
    recycler_slots_[index].value.store(node_at(initial_node_order_[index + 1U]),
                                       std::memory_order_relaxed);
  }
  auto* sentinel = node_at(initial_node_order_.front());
  producer_->tail = sentinel;
  consumer_->head = sentinel;
  recycler_producer_->position = 0U;
  recycler_consumer_->position = 0U;
  return valid_empty_cycle();
}

} // namespace cpu_prefetch::queue
