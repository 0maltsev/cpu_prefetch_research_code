#include "cpu_prefetch/workload/records.hpp"

#include <openssl/evp.h>

#include <algorithm>
#include <cstring>
#include <limits>
#include <memory>
#include <new>
#include <utility>

namespace cpu_prefetch::workload {
namespace {

constexpr std::string_view kContentDomain =
    "cpu-prefetch/event-record-content-sha256/v1";
constexpr std::string_view kOrderedIndexDomain = "cpu-prefetch/ordered-index-sha256/v1";
constexpr std::string_view kAddressDeltaDomain = "cpu-prefetch/address-delta-sha256/v1";

struct DigestContextDeleter final {
  void operator()(EVP_MD_CTX* context) const noexcept { EVP_MD_CTX_free(context); }
};

class CanonicalSha256 final {
public:
  CanonicalSha256() : context_(EVP_MD_CTX_new()) {
    if (context_ == nullptr ||
        EVP_DigestInit_ex(context_.get(), EVP_sha256(), nullptr) != 1) {
      throw WorkloadSetupError("OpenSSL SHA-256 initialization failed");
    }
  }

  void field(std::span<const std::byte> bytes) {
    std::array<std::byte, 8> length{};
    encode_u64(static_cast<std::uint64_t>(bytes.size()), length);
    update(length);
    update(bytes);
  }

  void field(std::string_view text) {
    field(std::span<const std::byte>(reinterpret_cast<const std::byte*>(text.data()),
                                     text.size()));
  }

  void field_u64(std::uint64_t value) {
    std::array<std::byte, 8> bytes{};
    encode_u64(value, bytes);
    field(bytes);
  }

  void field_i64(std::int64_t value) { field_u64(static_cast<std::uint64_t>(value)); }

  [[nodiscard]] Sha256Digest finish() {
    std::array<std::byte, 32> output{};
    unsigned int output_size = 0U;
    if (EVP_DigestFinal_ex(context_.get(),
                           reinterpret_cast<unsigned char*>(output.data()),
                           &output_size) != 1 ||
        output_size != output.size()) {
      throw WorkloadSetupError("OpenSSL SHA-256 finalization failed");
    }
    return Sha256Digest(output);
  }

private:
  static void encode_u64(std::uint64_t value, std::span<std::byte, 8> output) noexcept {
    for (std::size_t index = 0; index < output.size(); ++index) {
      const auto shift = static_cast<unsigned int>((7U - index) * 8U);
      output[index] = static_cast<std::byte>((value >> shift) & 0xffU);
    }
  }

  void update(std::span<const std::byte> bytes) {
    if (!bytes.empty() &&
        EVP_DigestUpdate(context_.get(), bytes.data(), bytes.size()) != 1) {
      throw WorkloadSetupError("OpenSSL SHA-256 update failed");
    }
  }

  std::unique_ptr<EVP_MD_CTX, DigestContextDeleter> context_;
};

[[nodiscard]] bool is_power_of_two(std::size_t value) noexcept {
  return value != 0U && (value & (value - 1U)) == 0U;
}

[[nodiscard]] std::size_t checked_multiply(std::size_t left, std::size_t right) {
  if (left != 0U && right > std::numeric_limits<std::size_t>::max() / left) {
    throw WorkloadSetupError("event arena size overflows size_t");
  }
  return left * right;
}

void validate_permutation(std::span<const std::size_t> order) {
  if (order.empty()) {
    throw WorkloadSetupError("ordered-index input must not be empty");
  }
  std::vector<bool> seen(order.size(), false);
  for (const auto index : order) {
    if (index >= order.size() || seen[index]) {
      throw WorkloadSetupError("ordered-index input must be a complete permutation");
    }
    seen[index] = true;
  }
}

[[nodiscard]] std::int64_t signed_delta(std::size_t from, std::size_t to,
                                        std::size_t stride) {
  const auto from_offset = checked_multiply(from, stride);
  const auto to_offset = checked_multiply(to, stride);
  if (to_offset >= from_offset) {
    const auto difference = to_offset - from_offset;
    if (difference >
        static_cast<std::size_t>(std::numeric_limits<std::int64_t>::max())) {
      throw WorkloadSetupError("positive address delta exceeds int64");
    }
    return static_cast<std::int64_t>(difference);
  }
  const auto magnitude = from_offset - to_offset;
  if (magnitude > static_cast<std::size_t>(std::numeric_limits<std::int64_t>::max())) {
    throw WorkloadSetupError("negative address delta exceeds int64");
  }
  return -static_cast<std::int64_t>(magnitude);
}

} // namespace

EventArena::EventArena(const EventArenaConfig& config)
    : capacity_(config.capacity), cache_line_bytes_(config.cache_line_bytes),
      base_page_bytes_(config.base_page_bytes) {
  if (!is_power_of_two(capacity_)) {
    throw WorkloadSetupError("event arena capacity must be a nonzero power of two");
  }
  if (!is_power_of_two(cache_line_bytes_) || cache_line_bytes_ < sizeof(EventRecord)) {
    throw WorkloadSetupError(
        "event cache-line bytes must be a power of two that fits the record");
  }
  if (!is_power_of_two(base_page_bytes_) || base_page_bytes_ < cache_line_bytes_) {
    throw WorkloadSetupError(
        "event base-page bytes must be a power of two at least one cache line");
  }
  if (config.seed_namespace.empty()) {
    throw WorkloadSetupError("event arena seed namespace must not be empty");
  }
  static_assert(sizeof(std::size_t) <= sizeof(std::uint64_t));

  const DeterministicStream order_stream(derive_stream_key(
      config.master_seed, config.seed_namespace, StreamPurpose::event_order));
  const DeterministicStream payload_stream(derive_stream_key(
      config.master_seed, config.seed_namespace, StreamPurpose::event_payload));
  record_order_ = make_permutation(capacity_, order_stream);
  allocated_bytes_ = checked_multiply(capacity_, cache_line_bytes_);
  storage_ = static_cast<std::byte*>(
      ::operator new(allocated_bytes_, std::align_val_t(base_page_bytes_)));
  std::memset(storage_, 0, allocated_bytes_);
  for (std::size_t index = 0; index < capacity_; ++index) {
    std::construct_at(
        reinterpret_cast<EventRecord*>(line_at(index)),
        EventRecord{static_cast<std::uint64_t>(index), payload_stream.draw(index)});
  }
  try {
    prepared_content_checksum_ = content_checksum();
  } catch (...) {
    for (std::size_t index = 0; index < capacity_; ++index) {
      std::destroy_at(reinterpret_cast<EventRecord*>(line_at(index)));
    }
    ::operator delete(storage_, std::align_val_t(base_page_bytes_));
    storage_ = nullptr;
    throw;
  }
}

EventArena::~EventArena() {
  if (storage_ != nullptr) {
    for (std::size_t index = 0; index < capacity_; ++index) {
      std::destroy_at(reinterpret_cast<EventRecord*>(line_at(index)));
    }
    ::operator delete(storage_, std::align_val_t(base_page_bytes_));
  }
}

const EventRecord& EventArena::physical_record(std::size_t index) const {
  if (index >= capacity_) {
    throw WorkloadSetupError("physical record index is outside the event arena");
  }
  return *reinterpret_cast<const EventRecord*>(line_at(index));
}

EventSelection EventArena::select(LogicalSequence sequence) const noexcept {
  const auto position = static_cast<std::size_t>(sequence.value % capacity_);
  const auto record_index = record_order_[position];
  return {RecordIndex{static_cast<std::uint64_t>(record_index)},
          reinterpret_cast<const EventRecord*>(line_at(record_index))};
}

RecordAccessResult EventArena::access_and_mix(const void* pointer,
                                              ConsumerState& state) const noexcept {
  const auto base = reinterpret_cast<std::uintptr_t>(storage_);
  const auto address = reinterpret_cast<std::uintptr_t>(pointer);
  if (address < base) {
    return {RecordAccessStatus::outside_arena, RecordIndex{0U}, 0U};
  }
  const auto offset = address - base;
  if (offset >= allocated_bytes_) {
    return {RecordAccessStatus::outside_arena, RecordIndex{0U}, 0U};
  }
  if (offset % cache_line_bytes_ != 0U) {
    return {RecordAccessStatus::not_record_start, RecordIndex{0U}, 0U};
  }
  const auto physical_index = offset / cache_line_bytes_;
  const auto* record = static_cast<const EventRecord*>(pointer);
  const auto observed_index = record->record_index;
  const auto payload = record->payload;
  if (observed_index != physical_index) {
    return {RecordAccessStatus::record_index_corrupt, RecordIndex{observed_index},
            payload};
  }
  state = mix_consumer_state(state, RecordIndex{observed_index}, payload);
  return {RecordAccessStatus::valid, RecordIndex{observed_index}, payload};
}

EventArenaLayout EventArena::layout() const noexcept {
  bool padding_initialized = true;
  bool lines_aligned = true;
  for (std::size_t index = 0; index < capacity_; ++index) {
    const auto* line = line_at(index);
    lines_aligned = lines_aligned &&
                    reinterpret_cast<std::uintptr_t>(line) % cache_line_bytes_ == 0U;
    padding_initialized =
        padding_initialized &&
        std::all_of(line + sizeof(EventRecord), line + cache_line_bytes_,
                    [](std::byte value) { return value == std::byte{0}; });
  }
  return {capacity_,
          cache_line_bytes_,
          base_page_bytes_,
          allocated_bytes_,
          capacity_,
          (allocated_bytes_ / base_page_bytes_) +
              (allocated_bytes_ % base_page_bytes_ == 0U ? 0U : 1U),
          reinterpret_cast<std::uintptr_t>(storage_) % base_page_bytes_ == 0U,
          lines_aligned,
          padding_initialized};
}

Sha256Digest EventArena::content_checksum() const {
  CanonicalSha256 digest;
  digest.field(kContentDomain);
  digest.field_u64(cache_line_bytes_);
  digest.field_u64(capacity_);
  const auto padding_size = cache_line_bytes_ - sizeof(EventRecord);
  for (std::size_t index = 0; index < capacity_; ++index) {
    const auto& record = physical_record(index);
    digest.field_u64(record.record_index);
    digest.field_u64(record.payload);
    digest.field_u64(padding_size);
    digest.field(
        std::span<const std::byte>(line_at(index) + sizeof(EventRecord), padding_size));
  }
  return digest.finish();
}

Sha256Digest EventArena::ordered_index_checksum() const {
  return ordered_index_sha256(record_order_);
}

Sha256Digest EventArena::address_delta_checksum() const {
  const auto deltas = address_deltas();
  return address_delta_sha256(deltas);
}

std::vector<std::int64_t> EventArena::address_deltas() const {
  return make_cyclic_address_deltas(record_order_, cache_line_bytes_);
}

const std::byte* EventArena::line_at(std::size_t index) const noexcept {
  return storage_ + (index * cache_line_bytes_);
}

std::byte* EventArena::line_at(std::size_t index) noexcept {
  return storage_ + (index * cache_line_bytes_);
}

ConsumerState initial_consumer_state(const MasterSeed& master_seed,
                                     std::string_view name_space) {
  const DeterministicStream stream(derive_stream_key(
      master_seed, name_space, StreamPurpose::initial_consumer_state));
  return ConsumerState{stream.draw(0U)};
}

std::vector<std::int64_t> make_cyclic_address_deltas(std::span<const std::size_t> order,
                                                     std::size_t stride_bytes) {
  validate_permutation(order);
  if (stride_bytes == 0U) {
    throw WorkloadSetupError("address-delta stride must be nonzero");
  }
  std::vector<std::int64_t> deltas;
  deltas.reserve(order.size());
  for (std::size_t index = 0; index < order.size(); ++index) {
    const auto next = (index + 1U) == order.size() ? 0U : index + 1U;
    deltas.push_back(signed_delta(order[index], order[next], stride_bytes));
  }
  return deltas;
}

Sha256Digest ordered_index_sha256(std::span<const std::size_t> order) {
  validate_permutation(order);
  CanonicalSha256 digest;
  digest.field(kOrderedIndexDomain);
  digest.field_u64(order.size());
  for (const auto index : order) {
    digest.field_u64(index);
  }
  return digest.finish();
}

Sha256Digest address_delta_sha256(std::span<const std::int64_t> deltas) {
  if (deltas.empty()) {
    throw WorkloadSetupError("address-delta input must not be empty");
  }
  CanonicalSha256 digest;
  digest.field(kAddressDeltaDomain);
  digest.field_u64(deltas.size());
  for (const auto delta : deltas) {
    digest.field_i64(delta);
  }
  return digest.finish();
}

} // namespace cpu_prefetch::workload
