#ifndef CPU_PREFETCH_WORKLOAD_RECORDS_HPP
#define CPU_PREFETCH_WORKLOAD_RECORDS_HPP

#include "cpu_prefetch/workload/deterministic.hpp"

#include <cstddef>
#include <cstdint>
#include <span>
#include <string>
#include <vector>

namespace cpu_prefetch::workload {

struct RecordIndex final {
  std::uint64_t value;
  auto operator==(const RecordIndex&) const -> bool = default;
};

struct LogicalSequence final {
  std::uint64_t value;
  auto operator==(const LogicalSequence&) const -> bool = default;
};

struct AcceptedOrdinal final {
  std::uint64_t value;
  auto operator==(const AcceptedOrdinal&) const -> bool = default;
};

struct EventRecord final {
  std::uint64_t record_index;
  alignas(std::uint64_t) std::uint64_t payload;
};

static_assert(offsetof(EventRecord, record_index) == 0U);
static_assert(offsetof(EventRecord, payload) == sizeof(std::uint64_t));
static_assert(sizeof(EventRecord) == 2U * sizeof(std::uint64_t));

struct ConsumerState final {
  std::uint64_t value;
  auto operator==(const ConsumerState&) const -> bool = default;
};

[[nodiscard]] constexpr ConsumerState
mix_consumer_state(ConsumerState state, RecordIndex record_index,
                   std::uint64_t payload) noexcept {
  auto value = state.value + 0x9e3779b97f4a7c15ULL;
  value ^= record_index.value;
  value = (value ^ (value >> 30U)) * 0xbf58476d1ce4e5b9ULL;
  value ^= payload;
  value = (value ^ (value >> 27U)) * 0x94d049bb133111ebULL;
  return ConsumerState{value ^ (value >> 31U)};
}

struct EventArenaConfig final {
  std::size_t capacity;
  std::size_t cache_line_bytes;
  std::size_t base_page_bytes;
  MasterSeed master_seed;
  std::string seed_namespace;
};

struct EventSelection final {
  RecordIndex record_index;
  const EventRecord* record;
};

enum class RecordAccessStatus : std::uint8_t {
  valid,
  outside_arena,
  not_record_start,
  record_index_corrupt,
};

struct RecordAccessResult final {
  RecordAccessStatus status;
  RecordIndex record_index;
  std::uint64_t payload;
};

struct EventArenaLayout final {
  std::size_t capacity;
  std::size_t cache_line_bytes;
  std::size_t base_page_bytes;
  std::size_t allocated_bytes;
  std::size_t distinct_cache_lines;
  std::size_t distinct_pages;
  bool base_page_aligned;
  bool every_record_line_aligned;
  bool padding_initialized;
};

class EventArena final {
public:
  explicit EventArena(const EventArenaConfig& config);
  ~EventArena();

  EventArena(const EventArena&) = delete;
  EventArena& operator=(const EventArena&) = delete;
  EventArena(EventArena&&) = delete;
  EventArena& operator=(EventArena&&) = delete;

  [[nodiscard]] std::size_t capacity() const noexcept { return capacity_; }
  [[nodiscard]] std::size_t cache_line_bytes() const noexcept {
    return cache_line_bytes_;
  }
  [[nodiscard]] std::span<const std::size_t> record_order() const noexcept {
    return record_order_;
  }
  [[nodiscard]] const EventRecord& physical_record(std::size_t index) const;
  [[nodiscard]] EventSelection select(LogicalSequence sequence) const noexcept;
  [[nodiscard]] RecordAccessResult access_and_mix(const void* pointer,
                                                  ConsumerState& state) const noexcept;
  [[nodiscard]] EventArenaLayout layout() const noexcept;
  [[nodiscard]] Sha256Digest content_checksum() const;
  [[nodiscard]] const Sha256Digest& prepared_content_checksum() const noexcept {
    return prepared_content_checksum_;
  }
  [[nodiscard]] Sha256Digest ordered_index_checksum() const;
  [[nodiscard]] Sha256Digest address_delta_checksum() const;
  [[nodiscard]] std::vector<std::int64_t> address_deltas() const;

private:
  [[nodiscard]] const std::byte* line_at(std::size_t index) const noexcept;
  [[nodiscard]] std::byte* line_at(std::size_t index) noexcept;

  std::size_t capacity_{0};
  std::size_t cache_line_bytes_{0};
  std::size_t base_page_bytes_{0};
  std::size_t allocated_bytes_{0};
  std::byte* storage_{nullptr};
  std::vector<std::size_t> record_order_;
  Sha256Digest prepared_content_checksum_{{}};
};

[[nodiscard]] ConsumerState initial_consumer_state(const MasterSeed& master_seed,
                                                   std::string_view name_space);
[[nodiscard]] std::vector<std::int64_t>
make_cyclic_address_deltas(std::span<const std::size_t> order,
                           std::size_t stride_bytes);
[[nodiscard]] Sha256Digest ordered_index_sha256(std::span<const std::size_t> order);
[[nodiscard]] Sha256Digest address_delta_sha256(std::span<const std::int64_t> deltas);

} // namespace cpu_prefetch::workload

#endif // CPU_PREFETCH_WORKLOAD_RECORDS_HPP
