#ifndef CPU_PREFETCH_STORAGE_RAW_OBSERVATIONS_HPP
#define CPU_PREFETCH_STORAGE_RAW_OBSERVATIONS_HPP

#include "cpu_prefetch/protocol/model.hpp"
#include "cpu_prefetch/timing/capture.hpp"

#include <cstddef>
#include <cstdint>
#include <span>
#include <stdexcept>
#include <string>
#include <string_view>
#include <variant>
#include <vector>

namespace cpu_prefetch::storage {

inline constexpr std::string_view kRawFormatId = "RAW-OBS-U64LE-LP-RUNID-v1";
inline constexpr std::string_view kRawEncoding =
    "FIXED_U64_LE_LENGTH_PREFIXED_UTF8_RUN_ID";
inline constexpr std::string_view kRawTimeUnit = "PICOSECONDS";
inline constexpr std::string_view kRawEndianness = "LITTLE_ENDIAN";
inline constexpr std::string_view kRawCompression = "NONE";
inline constexpr std::string_view kDurabilityPolicyId = "RAW-OBS-NONE-TMP1-DUR2-v1";

inline constexpr std::uint64_t kProducerBodyBytes = 15U * sizeof(std::uint64_t);
inline constexpr std::uint64_t kConsumerBodyBytes = 10U * sizeof(std::uint64_t);
inline constexpr std::uint64_t kJoinedBodyBytes = 24U * sizeof(std::uint64_t);
inline constexpr std::size_t kRawBufferAlignment = 64U;

class StorageSetupError final : public std::invalid_argument {
public:
  using std::invalid_argument::invalid_argument;
};

struct RowLayout final {
  std::uint64_t run_id_bytes;
  std::uint64_t prefix_bytes;
  std::uint64_t producer_row_bytes;
  std::uint64_t consumer_row_bytes;
  std::uint64_t joined_row_bytes;
};

[[nodiscard]] auto make_row_layout(std::string_view run_id) -> RowLayout;

enum class AppendStatus : std::uint8_t {
  appended,
  buffer_overflow,
  invalid_observation,
  stream_unprepared,
  stream_sealed,
};

enum class StreamCompleteness : std::uint8_t {
  writing,
  sealed_complete,
  sealed_incomplete,
};

[[nodiscard]] auto to_string(StreamCompleteness state) noexcept -> std::string_view;

struct RawStreamSnapshot final {
  protocol::StreamKind stream_kind;
  std::string_view run_id;
  std::span<const std::byte> bytes;
  std::uint64_t row_count;
  std::uint64_t row_capacity;
  std::uint64_t row_bytes;
  StreamCompleteness completeness;
  bool overflowed;
};

class ProducerObservationStream final {
public:
  ProducerObservationStream(const protocol::RunId& run_id, std::uint64_t row_capacity);
  ~ProducerObservationStream();

  ProducerObservationStream(const ProducerObservationStream&) = delete;
  ProducerObservationStream& operator=(const ProducerObservationStream&) = delete;
  ProducerObservationStream(ProducerObservationStream&&) = delete;
  ProducerObservationStream& operator=(ProducerObservationStream&&) = delete;

  // Call once from the already-affined producer during preparation. This
  // initializes every reserved byte and every literal row prefix before the
  // measurement barrier, establishing producer-local first touch.
  [[nodiscard]] auto prepare_for_owner() noexcept -> bool;
  [[nodiscard]] auto append(const timing::ProducerObservation& observation) noexcept
      -> AppendStatus;
  [[nodiscard]] auto seal_complete() noexcept -> bool;
  void seal_incomplete() noexcept;
  [[nodiscard]] auto snapshot() const noexcept -> RawStreamSnapshot;
  [[nodiscard]] auto buffer_address() const noexcept -> const std::byte* {
    return storage_;
  }

private:
  struct alignas(kRawBufferAlignment) ControlBlock final {
    std::uint64_t row_count{0U};
    std::uint64_t row_capacity{0U};
    std::uint64_t row_bytes{0U};
    StreamCompleteness completeness{StreamCompleteness::writing};
    bool overflowed{false};
    bool prepared{false};
    std::byte padding[37]{};
  };

  static_assert(sizeof(ControlBlock) == kRawBufferAlignment);
  static_assert(alignof(ControlBlock) == kRawBufferAlignment);

  std::string run_id_;
  RowLayout layout_{};
  std::byte* storage_{nullptr};
  std::uint64_t allocated_bytes_{0U};
  ControlBlock control_{};
};

class ConsumerObservationStream final {
public:
  ConsumerObservationStream(const protocol::RunId& run_id, std::uint64_t row_capacity);
  ~ConsumerObservationStream();

  ConsumerObservationStream(const ConsumerObservationStream&) = delete;
  ConsumerObservationStream& operator=(const ConsumerObservationStream&) = delete;
  ConsumerObservationStream(ConsumerObservationStream&&) = delete;
  ConsumerObservationStream& operator=(ConsumerObservationStream&&) = delete;

  // Call once from the already-affined consumer during preparation. This
  // initializes every reserved byte and every literal row prefix before the
  // measurement barrier, establishing consumer-local first touch.
  [[nodiscard]] auto prepare_for_owner() noexcept -> bool;
  [[nodiscard]] auto append(const timing::ConsumerObservation& observation) noexcept
      -> AppendStatus;
  [[nodiscard]] auto seal_complete() noexcept -> bool;
  void seal_incomplete() noexcept;
  [[nodiscard]] auto snapshot() const noexcept -> RawStreamSnapshot;
  [[nodiscard]] auto buffer_address() const noexcept -> const std::byte* {
    return storage_;
  }

private:
  struct alignas(kRawBufferAlignment) ControlBlock final {
    std::uint64_t row_count{0U};
    std::uint64_t row_capacity{0U};
    std::uint64_t row_bytes{0U};
    StreamCompleteness completeness{StreamCompleteness::writing};
    bool overflowed{false};
    bool prepared{false};
    std::byte padding[37]{};
  };

  static_assert(sizeof(ControlBlock) == kRawBufferAlignment);
  static_assert(alignof(ControlBlock) == kRawBufferAlignment);

  std::string run_id_;
  RowLayout layout_{};
  std::byte* storage_{nullptr};
  std::uint64_t allocated_bytes_{0U};
  ControlBlock control_{};
};

struct DecodedProducerRow final {
  std::string run_id;
  timing::ProducerObservation observation;
};

struct DecodedConsumerRow final {
  std::string run_id;
  timing::ConsumerObservation observation;
};

using DecodedRows =
    std::variant<std::vector<DecodedProducerRow>, std::vector<DecodedConsumerRow>,
                 std::vector<protocol::JoinedRecord>>;

struct DecodedRawStream final {
  protocol::StreamKind stream_kind;
  DecodedRows rows;
};

// Decoding is post-run. It validates the imported envelope contract, exact
// physical grammar, SHA-256, row counts, row identity, key continuity, and the
// existing logical-row semantic validator. Cross-stream reconciliation is not
// performed here and remains Stage 12 work.
[[nodiscard]] auto decode_external_raw(const protocol::RawObservationEnvelope& envelope,
                                       std::span<const std::byte> bytes)
    -> protocol::Result<DecodedRawStream>;

// Stage 11 defines the accepted joined codec for compatibility testing only.
// It does not construct or reconcile joined rows.
[[nodiscard]] auto
encode_joined_rows_for_format_test(const protocol::RunId& run_id,
                                   std::span<const protocol::JoinedRecord> rows)
    -> std::vector<std::byte>;

} // namespace cpu_prefetch::storage

#endif // CPU_PREFETCH_STORAGE_RAW_OBSERVATIONS_HPP
