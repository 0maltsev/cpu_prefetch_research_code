#include "cpu_prefetch/storage/raw_observations.hpp"

#include "cpu_prefetch/workload/deterministic.hpp"

#include <array>
#include <cstring>
#include <limits>
#include <new>
#include <optional>
#include <utility>

namespace cpu_prefetch::storage {
namespace {

constexpr std::uint64_t kProducerAcceptedFlags = 15U;
constexpr std::uint64_t kProducerFullFlags = 1U;

[[nodiscard]] auto checked_add(std::uint64_t left, std::uint64_t right,
                               std::uint64_t& result) noexcept -> bool {
  if (right > std::numeric_limits<std::uint64_t>::max() - left) {
    return false;
  }
  result = left + right;
  return true;
}

[[nodiscard]] auto checked_multiply(std::uint64_t left, std::uint64_t right,
                                    std::uint64_t& result) noexcept -> bool {
  if (left != 0U && right > std::numeric_limits<std::uint64_t>::max() / left) {
    return false;
  }
  result = left * right;
  return true;
}

[[nodiscard]] auto valid_utf8(std::string_view text) noexcept -> bool {
  for (std::size_t index = 0U; index < text.size();) {
    const auto first = static_cast<unsigned char>(text[index]);
    std::uint32_t code_point = 0U;
    std::size_t length = 0U;
    if (first <= 0x7fU) {
      code_point = first;
      length = 1U;
    } else if ((first & 0xe0U) == 0xc0U) {
      code_point = first & 0x1fU;
      length = 2U;
    } else if ((first & 0xf0U) == 0xe0U) {
      code_point = first & 0x0fU;
      length = 3U;
    } else if ((first & 0xf8U) == 0xf0U) {
      code_point = first & 0x07U;
      length = 4U;
    } else {
      return false;
    }
    if (index + length > text.size()) {
      return false;
    }
    for (std::size_t offset = 1U; offset < length; ++offset) {
      const auto next = static_cast<unsigned char>(text[index + offset]);
      if ((next & 0xc0U) != 0x80U) {
        return false;
      }
      code_point = (code_point << 6U) | (next & 0x3fU);
    }
    const bool overlong = (length == 2U && code_point < 0x80U) ||
                          (length == 3U && code_point < 0x800U) ||
                          (length == 4U && code_point < 0x10000U);
    if (overlong || code_point > 0x10ffffU ||
        (code_point >= 0xd800U && code_point <= 0xdfffU)) {
      return false;
    }
    index += length;
  }
  return true;
}

void store_u32_le(std::byte* output, std::uint32_t value) noexcept {
  for (std::size_t index = 0U; index < sizeof(value); ++index) {
    output[index] = static_cast<std::byte>((value >> (index * 8U)) & 0xffU);
  }
}

void store_u64_le(std::byte* output, std::uint64_t value) noexcept {
  for (std::size_t index = 0U; index < sizeof(value); ++index) {
    output[index] = static_cast<std::byte>((value >> (index * 8U)) & 0xffU);
  }
}

[[nodiscard]] auto load_u32_le(const std::byte* input) noexcept -> std::uint32_t {
  std::uint32_t value = 0U;
  for (std::size_t index = 0U; index < sizeof(value); ++index) {
    value |= static_cast<std::uint32_t>(std::to_integer<unsigned int>(input[index]))
             << (index * 8U);
  }
  return value;
}

[[nodiscard]] auto load_u64_le(const std::byte* input) noexcept -> std::uint64_t {
  std::uint64_t value = 0U;
  for (std::size_t index = 0U; index < sizeof(value); ++index) {
    value |= static_cast<std::uint64_t>(std::to_integer<unsigned int>(input[index]))
             << (index * 8U);
  }
  return value;
}

template <std::size_t Count>
void store_words(std::byte* output,
                 const std::array<std::uint64_t, Count>& words) noexcept {
  for (std::size_t index = 0U; index < words.size(); ++index) {
    store_u64_le(output + index * sizeof(std::uint64_t), words[index]);
  }
}

struct PrefixInitialization final {
  std::uint64_t capacity;
  std::uint64_t row_bytes;
  std::uint64_t prefix_bytes;
  std::string_view run_id;
};

void initialize_prefixes(std::byte* storage,
                         const PrefixInitialization& initialization) noexcept {
  const auto length = static_cast<std::uint32_t>(initialization.run_id.size());
  for (std::uint64_t row = 0U; row < initialization.capacity; ++row) {
    auto* output = storage + static_cast<std::size_t>(row * initialization.row_bytes);
    store_u32_le(output, length);
    for (std::size_t index = 0U; index < initialization.run_id.size(); ++index) {
      output[sizeof(std::uint32_t) + index] = static_cast<std::byte>(
          static_cast<unsigned char>(initialization.run_id[index]));
    }
    for (std::uint64_t index = sizeof(std::uint32_t) + initialization.run_id.size();
         index < initialization.prefix_bytes; ++index) {
      output[static_cast<std::size_t>(index)] = std::byte{0};
    }
  }
}

[[nodiscard]] auto make_validation_error(protocol::ErrorCategory category,
                                         std::string path, std::string rule,
                                         std::string message)
    -> protocol::ValidationError {
  return {category, std::move(path), std::move(rule), std::move(message)};
}

template <typename T>
[[nodiscard]] auto decode_failure(protocol::ErrorCategory category, std::string path,
                                  std::string rule, std::string message)
    -> protocol::Result<T> {
  return protocol::Result<T>::failure(make_validation_error(
      category, std::move(path), std::move(rule), std::move(message)));
}

[[nodiscard]] auto expected_row_bytes(protocol::StreamKind kind,
                                      const RowLayout& layout) noexcept
    -> std::uint64_t {
  switch (kind) {
  case protocol::StreamKind::producer:
    return layout.producer_row_bytes;
  case protocol::StreamKind::consumer:
    return layout.consumer_row_bytes;
  case protocol::StreamKind::joined_derived:
    return layout.joined_row_bytes;
  }
  return 0U;
}

[[nodiscard]] auto verify_prefix(const std::byte* row, const RowLayout& layout,
                                 std::string_view expected_run_id) noexcept -> bool {
  if (load_u32_le(row) != layout.run_id_bytes) {
    return false;
  }
  for (std::size_t index = 0U; index < expected_run_id.size(); ++index) {
    if (row[sizeof(std::uint32_t) + index] !=
        static_cast<std::byte>(static_cast<unsigned char>(expected_run_id[index]))) {
      return false;
    }
  }
  for (std::uint64_t index = sizeof(std::uint32_t) + layout.run_id_bytes;
       index < layout.prefix_bytes; ++index) {
    if (row[static_cast<std::size_t>(index)] != std::byte{0}) {
      return false;
    }
  }
  return true;
}

[[nodiscard]] auto joined_words(const protocol::JoinedRecord& row)
    -> std::array<std::uint64_t, 24> {
  return {row.accepted_ordinal,
          row.logical_sequence,
          row.record_index,
          row.producer_row_ordinal,
          row.consumer_row_ordinal,
          row.scheduled_arrival,
          row.producer_handle_begin,
          row.record_lookup_completion,
          row.enqueue_invocation,
          row.enqueue_linearization,
          row.enqueue_attempt_completion,
          row.dequeue_invocation,
          row.dequeue_linearization,
          row.dequeue_completion,
          row.consumer_action_completion,
          row.producer_lateness,
          row.pointer_lookup_interval,
          row.enqueue_service_time,
          row.admission_delay,
          row.queue_residence,
          row.dequeue_service_time,
          row.post_dequeue_delivery_interval,
          row.consumer_action_interval,
          row.end_to_end_latency};
}

} // namespace

auto make_row_layout(std::string_view run_id) -> RowLayout {
  if (run_id.empty()) {
    throw StorageSetupError("raw-observation run_id must not be empty");
  }
  if (!valid_utf8(run_id)) {
    throw StorageSetupError("raw-observation run_id must be valid UTF-8");
  }
  if (run_id.size() > std::numeric_limits<std::uint32_t>::max()) {
    throw StorageSetupError("raw-observation run_id exceeds uint32 length");
  }
  const auto length = static_cast<std::uint64_t>(run_id.size());
  std::uint64_t with_length = 0U;
  if (!checked_add(sizeof(std::uint32_t), length, with_length) ||
      with_length > std::numeric_limits<std::uint64_t>::max() - 7U) {
    throw StorageSetupError("raw-observation row prefix size overflows uint64");
  }
  const auto prefix = (with_length + 7U) & ~std::uint64_t{7U};
  std::uint64_t producer = 0U;
  std::uint64_t consumer = 0U;
  std::uint64_t joined = 0U;
  if (!checked_add(prefix, kProducerBodyBytes, producer) ||
      !checked_add(prefix, kConsumerBodyBytes, consumer) ||
      !checked_add(prefix, kJoinedBodyBytes, joined) ||
      producer > std::numeric_limits<std::size_t>::max() ||
      consumer > std::numeric_limits<std::size_t>::max() ||
      joined > std::numeric_limits<std::size_t>::max()) {
    throw StorageSetupError("raw-observation row size exceeds host size_t");
  }
  return {length, prefix, producer, consumer, joined};
}

auto to_string(StreamCompleteness state) noexcept -> std::string_view {
  switch (state) {
  case StreamCompleteness::writing:
    return "WRITING";
  case StreamCompleteness::sealed_complete:
    return "SEALED_COMPLETE";
  case StreamCompleteness::sealed_incomplete:
    return "SEALED_INCOMPLETE";
  }
  return "UNKNOWN";
}

ProducerObservationStream::ProducerObservationStream(const protocol::RunId& run_id,
                                                     std::uint64_t row_capacity)
    : run_id_(run_id.value()), layout_(make_row_layout(run_id_)) {
  if (!checked_multiply(row_capacity, layout_.producer_row_bytes, allocated_bytes_) ||
      allocated_bytes_ > std::numeric_limits<std::size_t>::max()) {
    throw StorageSetupError("producer raw buffer size overflows host size_t");
  }
  control_.row_capacity = row_capacity;
  control_.row_bytes = layout_.producer_row_bytes;
  if (allocated_bytes_ != 0U) {
    storage_ = static_cast<std::byte*>(
        ::operator new(static_cast<std::size_t>(allocated_bytes_),
                       std::align_val_t{kRawBufferAlignment}));
  }
}

ProducerObservationStream::~ProducerObservationStream() {
  if (storage_ != nullptr) {
    ::operator delete(storage_, std::align_val_t{kRawBufferAlignment});
  }
}

auto ProducerObservationStream::prepare_for_owner() noexcept -> bool {
  if (control_.prepared || control_.completeness != StreamCompleteness::writing) {
    return false;
  }
  if (allocated_bytes_ != 0U) {
    std::memset(storage_, 0, static_cast<std::size_t>(allocated_bytes_));
    initialize_prefixes(storage_, {control_.row_capacity, layout_.producer_row_bytes,
                                   layout_.prefix_bytes, run_id_});
  }
  control_.prepared = true;
  return true;
}

auto ProducerObservationStream::append(
    const timing::ProducerObservation& observation) noexcept -> AppendStatus {
  if (!control_.prepared) {
    return AppendStatus::stream_unprepared;
  }
  if (control_.completeness != StreamCompleteness::writing) {
    return AppendStatus::stream_sealed;
  }
  const bool accepted = observation.outcome == protocol::ProducerOutcome::accepted;
  if (accepted != observation.enqueue_linearization.has_value() ||
      accepted != observation.accepted_ordinal.has_value()) {
    return AppendStatus::invalid_observation;
  }
  if (control_.row_count == control_.row_capacity) {
    control_.overflowed = true;
    control_.completeness = StreamCompleteness::sealed_incomplete;
    return AppendStatus::buffer_overflow;
  }

  const auto linearization =
      observation.enqueue_linearization.value_or(timing::ClockSample{0U, 0U});
  const std::array<std::uint64_t, 15> words{
      observation.logical_sequence.value,
      observation.record_index.value,
      observation.scheduled_arrival,
      observation.producer_handle_begin.absolute_nanoseconds,
      observation.producer_handle_begin.relative_picoseconds,
      observation.record_lookup_completion.absolute_nanoseconds,
      observation.record_lookup_completion.relative_picoseconds,
      observation.enqueue_invocation.absolute_nanoseconds,
      observation.enqueue_invocation.relative_picoseconds,
      linearization.absolute_nanoseconds,
      linearization.relative_picoseconds,
      observation.enqueue_attempt_completion.absolute_nanoseconds,
      observation.enqueue_attempt_completion.relative_picoseconds,
      accepted ? observation.accepted_ordinal->value : 0U,
      accepted ? kProducerAcceptedFlags : kProducerFullFlags,
  };
  auto* body = storage_ + static_cast<std::size_t>(control_.row_count *
                                                       layout_.producer_row_bytes +
                                                   layout_.prefix_bytes);
  store_words(body, words);
  ++control_.row_count;
  return AppendStatus::appended;
}

auto ProducerObservationStream::seal_complete() noexcept -> bool {
  if (!control_.prepared || control_.completeness != StreamCompleteness::writing ||
      control_.overflowed) {
    return false;
  }
  control_.completeness = StreamCompleteness::sealed_complete;
  return true;
}

void ProducerObservationStream::seal_incomplete() noexcept {
  if (control_.completeness == StreamCompleteness::writing) {
    control_.completeness = StreamCompleteness::sealed_incomplete;
  }
}

auto ProducerObservationStream::snapshot() const noexcept -> RawStreamSnapshot {
  return {
      protocol::StreamKind::producer,
      run_id_,
      std::span<const std::byte>(
          storage_, static_cast<std::size_t>(control_.row_count * control_.row_bytes)),
      control_.row_count,
      control_.row_capacity,
      control_.row_bytes,
      control_.completeness,
      control_.overflowed};
}

ConsumerObservationStream::ConsumerObservationStream(const protocol::RunId& run_id,
                                                     std::uint64_t row_capacity)
    : run_id_(run_id.value()), layout_(make_row_layout(run_id_)) {
  if (!checked_multiply(row_capacity, layout_.consumer_row_bytes, allocated_bytes_) ||
      allocated_bytes_ > std::numeric_limits<std::size_t>::max()) {
    throw StorageSetupError("consumer raw buffer size overflows host size_t");
  }
  control_.row_capacity = row_capacity;
  control_.row_bytes = layout_.consumer_row_bytes;
  if (allocated_bytes_ != 0U) {
    storage_ = static_cast<std::byte*>(
        ::operator new(static_cast<std::size_t>(allocated_bytes_),
                       std::align_val_t{kRawBufferAlignment}));
  }
}

ConsumerObservationStream::~ConsumerObservationStream() {
  if (storage_ != nullptr) {
    ::operator delete(storage_, std::align_val_t{kRawBufferAlignment});
  }
}

auto ConsumerObservationStream::prepare_for_owner() noexcept -> bool {
  if (control_.prepared || control_.completeness != StreamCompleteness::writing) {
    return false;
  }
  if (allocated_bytes_ != 0U) {
    std::memset(storage_, 0, static_cast<std::size_t>(allocated_bytes_));
    initialize_prefixes(storage_, {control_.row_capacity, layout_.consumer_row_bytes,
                                   layout_.prefix_bytes, run_id_});
  }
  control_.prepared = true;
  return true;
}

auto ConsumerObservationStream::append(
    const timing::ConsumerObservation& observation) noexcept -> AppendStatus {
  if (!control_.prepared) {
    return AppendStatus::stream_unprepared;
  }
  if (control_.completeness != StreamCompleteness::writing) {
    return AppendStatus::stream_sealed;
  }
  if (control_.row_count == control_.row_capacity) {
    control_.overflowed = true;
    control_.completeness = StreamCompleteness::sealed_incomplete;
    return AppendStatus::buffer_overflow;
  }
  const std::array<std::uint64_t, 10> words{
      observation.consumed_ordinal.value,
      observation.observed_record_index.value,
      observation.dequeue_invocation.absolute_nanoseconds,
      observation.dequeue_invocation.relative_picoseconds,
      observation.dequeue_linearization.absolute_nanoseconds,
      observation.dequeue_linearization.relative_picoseconds,
      observation.dequeue_completion.absolute_nanoseconds,
      observation.dequeue_completion.relative_picoseconds,
      observation.consumer_action_completion.absolute_nanoseconds,
      observation.consumer_action_completion.relative_picoseconds,
  };
  auto* body = storage_ + static_cast<std::size_t>(control_.row_count *
                                                       layout_.consumer_row_bytes +
                                                   layout_.prefix_bytes);
  store_words(body, words);
  ++control_.row_count;
  return AppendStatus::appended;
}

auto ConsumerObservationStream::seal_complete() noexcept -> bool {
  if (!control_.prepared || control_.completeness != StreamCompleteness::writing ||
      control_.overflowed) {
    return false;
  }
  control_.completeness = StreamCompleteness::sealed_complete;
  return true;
}

void ConsumerObservationStream::seal_incomplete() noexcept {
  if (control_.completeness == StreamCompleteness::writing) {
    control_.completeness = StreamCompleteness::sealed_incomplete;
  }
}

auto ConsumerObservationStream::snapshot() const noexcept -> RawStreamSnapshot {
  return {
      protocol::StreamKind::consumer,
      run_id_,
      std::span<const std::byte>(
          storage_, static_cast<std::size_t>(control_.row_count * control_.row_bytes)),
      control_.row_count,
      control_.row_capacity,
      control_.row_bytes,
      control_.completeness,
      control_.overflowed};
}

auto decode_external_raw(const protocol::RawObservationEnvelope& envelope,
                         std::span<const std::byte> bytes)
    -> protocol::Result<DecodedRawStream> {
  if (std::get_if<protocol::ExternalStorage>(&envelope.storage) == nullptr) {
    return decode_failure<DecodedRawStream>(
        protocol::ErrorCategory::cross_field, "$out/storage", "RAW-EXTERNAL",
        "physical decoder accepts only external immutable raw artifacts");
  }
  if (envelope.physical_format_record_id.value() != kRawFormatId ||
      envelope.encoding != kRawEncoding || envelope.time_unit != kRawTimeUnit ||
      envelope.endianness != protocol::Endianness::little_endian ||
      envelope.compression != kRawCompression) {
    return decode_failure<DecodedRawStream>(
        protocol::ErrorCategory::unsupported_version, "$out", "RAW-FORMAT-SUITE",
        "raw envelope does not select the accepted Stage 11 format suite");
  }
  if (envelope.logical_row_schema_version != envelope.protocol_version) {
    return decode_failure<DecodedRawStream>(
        protocol::ErrorCategory::unsupported_version, "$out/logical_row_schema_version",
        "RAW-LOGICAL-VERSION",
        "logical row schema and envelope protocol versions must match");
  }
  if (envelope.stream_kind != protocol::StreamKind::joined_derived &&
      !envelope.source_artifacts.empty()) {
    return decode_failure<DecodedRawStream>(
        protocol::ErrorCategory::cross_field, "$out/source_artifacts",
        "RAW-SOURCE-ARTIFACTS",
        "producer and consumer raw streams must not name source artifacts");
  }
  if (workload::sha256(bytes).hex() != envelope.artifact_sha256.hex()) {
    return decode_failure<DecodedRawStream>(
        protocol::ErrorCategory::invalid_hash, "$out/artifact_sha256", "RAW-SHA256",
        "raw artifact SHA-256 does not match its envelope");
  }

  RowLayout layout{};
  try {
    layout = make_row_layout(envelope.run_id.value());
  } catch (const StorageSetupError& error) {
    return decode_failure<DecodedRawStream>(protocol::ErrorCategory::invalid_id,
                                            "$out/run_id", "RAW-RUN-ID", error.what());
  }
  const auto row_bytes = expected_row_bytes(envelope.stream_kind, layout);
  std::uint64_t exact_bytes = 0U;
  if (!checked_multiply(envelope.row_count, row_bytes, exact_bytes) ||
      exact_bytes != envelope.byte_count || exact_bytes != bytes.size()) {
    return decode_failure<DecodedRawStream>(
        protocol::ErrorCategory::cross_field, "$out/byte_count", "RAW-EXACT-SIZE",
        "row count, physical row size, byte count, and artifact size disagree");
  }

  std::vector<DecodedProducerRow> producer_rows;
  std::vector<DecodedConsumerRow> consumer_rows;
  std::vector<protocol::JoinedRecord> joined_rows;
  if (envelope.stream_kind == protocol::StreamKind::producer) {
    producer_rows.reserve(static_cast<std::size_t>(envelope.row_count));
  } else if (envelope.stream_kind == protocol::StreamKind::consumer) {
    consumer_rows.reserve(static_cast<std::size_t>(envelope.row_count));
  } else {
    joined_rows.reserve(static_cast<std::size_t>(envelope.row_count));
  }

  std::uint64_t expected_accepted = 0U;
  for (std::uint64_t index = 0U; index < envelope.row_count; ++index) {
    const auto* row = bytes.data() + static_cast<std::size_t>(index * row_bytes);
    if (!verify_prefix(row, layout, envelope.run_id.value())) {
      return decode_failure<DecodedRawStream>(
          protocol::ErrorCategory::reference_mismatch,
          "$out/rows/" + std::to_string(index) + "/run_id", "RAW-ROW-RUN-ID",
          "row prefix is noncanonical or disagrees with the envelope run_id");
    }
    const auto* body = row + static_cast<std::size_t>(layout.prefix_bytes);
    if (envelope.stream_kind == protocol::StreamKind::producer) {
      std::array<std::uint64_t, 15> words{};
      for (std::size_t word = 0U; word < words.size(); ++word) {
        words[word] = load_u64_le(body + word * sizeof(std::uint64_t));
      }
      if (words[0] != index ||
          (words[14] != kProducerAcceptedFlags && words[14] != kProducerFullFlags)) {
        return decode_failure<DecodedRawStream>(
            protocol::ErrorCategory::cross_field, "$out/rows/" + std::to_string(index),
            "RAW-PRODUCER-ORDER-FLAGS",
            "producer logical sequence or flags are noncanonical");
      }
      const bool accepted = words[14] == kProducerAcceptedFlags;
      if ((accepted && words[13] != expected_accepted) ||
          (!accepted && (words[9] != 0U || words[10] != 0U || words[13] != 0U))) {
        return decode_failure<DecodedRawStream>(
            protocol::ErrorCategory::cross_field, "$out/rows/" + std::to_string(index),
            "RAW-PRODUCER-ABSENCE-ORDINAL",
            "producer ordinal or accepted-only absent values are noncanonical");
      }
      const std::optional<timing::ClockSample> linearization =
          accepted ? std::optional<timing::ClockSample>{{words[9], words[10]}}
                   : std::nullopt;
      const std::optional<workload::AcceptedOrdinal> ordinal =
          accepted ? std::optional<workload::AcceptedOrdinal>{{words[13]}}
                   : std::nullopt;
      producer_rows.push_back(
          {std::string(envelope.run_id.value()),
           timing::ProducerObservation{
               workload::LogicalSequence{words[0]}, workload::RecordIndex{words[1]},
               words[2], timing::ClockSample{words[3], words[4]},
               timing::ClockSample{words[5], words[6]},
               timing::ClockSample{words[7], words[8]}, linearization,
               timing::ClockSample{words[11], words[12]},
               accepted ? protocol::ProducerOutcome::accepted
                        : protocol::ProducerOutcome::full,
               ordinal}});
      expected_accepted += accepted ? 1U : 0U;
    } else if (envelope.stream_kind == protocol::StreamKind::consumer) {
      std::array<std::uint64_t, 10> words{};
      for (std::size_t word = 0U; word < words.size(); ++word) {
        words[word] = load_u64_le(body + word * sizeof(std::uint64_t));
      }
      if (words[0] != index) {
        return decode_failure<DecodedRawStream>(
            protocol::ErrorCategory::cross_field,
            "$out/rows/" + std::to_string(index) + "/consumed_ordinal",
            "RAW-CONSUMER-ORDER",
            "consumer rows must be in contiguous successful-dequeue order");
      }
      consumer_rows.push_back(
          {std::string(envelope.run_id.value()),
           timing::ConsumerObservation{workload::AcceptedOrdinal{words[0]},
                                       workload::RecordIndex{words[1]},
                                       timing::ClockSample{words[2], words[3]},
                                       timing::ClockSample{words[4], words[5]},
                                       timing::ClockSample{words[6], words[7]},
                                       timing::ClockSample{words[8], words[9]}}});
    } else {
      std::array<std::uint64_t, 24> words{};
      for (std::size_t word = 0U; word < words.size(); ++word) {
        words[word] = load_u64_le(body + word * sizeof(std::uint64_t));
      }
      if (words[0] != index) {
        return decode_failure<DecodedRawStream>(
            protocol::ErrorCategory::cross_field,
            "$out/rows/" + std::to_string(index) + "/accepted_ordinal",
            "RAW-JOINED-ORDER",
            "joined rows must be in contiguous accepted-ordinal order");
      }
      joined_rows.push_back(
          {envelope.run_id, words[0],  words[1],  words[2],  words[3],
           words[4],        words[5],  words[6],  words[7],  words[8],
           words[9],        words[10], words[11], words[12], words[13],
           words[14],       words[15], words[16], words[17], words[18],
           words[19],       words[20], words[21], words[22], words[23]});
    }
  }

  protocol::RawObservationEnvelope logical_envelope = envelope;
  DecodedRawStream decoded{envelope.stream_kind, std::move(producer_rows)};
  if (envelope.stream_kind == protocol::StreamKind::producer) {
    std::vector<protocol::ProducerRecord> logical;
    const auto& physical = std::get<std::vector<DecodedProducerRow>>(decoded.rows);
    logical.reserve(physical.size());
    for (const auto& row : physical) {
      logical.push_back(timing::make_producer_record(envelope.run_id, row.observation));
    }
    logical_envelope.storage = protocol::InlineObservationRows{std::move(logical)};
  } else if (envelope.stream_kind == protocol::StreamKind::consumer) {
    decoded.rows = std::move(consumer_rows);
    std::vector<protocol::ConsumerRecord> logical;
    const auto& physical = std::get<std::vector<DecodedConsumerRow>>(decoded.rows);
    logical.reserve(physical.size());
    for (const auto& row : physical) {
      logical.push_back(timing::make_consumer_record(envelope.run_id, row.observation));
    }
    logical_envelope.storage = protocol::InlineObservationRows{std::move(logical)};
  } else {
    decoded.rows = joined_rows;
    logical_envelope.storage = protocol::InlineObservationRows{std::move(joined_rows)};
  }
  const protocol::Stage4SemanticValidator validator;
  const protocol::ProtocolRecord record{logical_envelope};
  auto errors = validator.validate(record);
  if (!errors.empty()) {
    return protocol::Result<DecodedRawStream>::failure(std::move(errors));
  }
  return protocol::Result<DecodedRawStream>::success(decoded);
}

auto encode_joined_rows_for_format_test(const protocol::RunId& run_id,
                                        std::span<const protocol::JoinedRecord> rows)
    -> std::vector<std::byte> {
  const auto layout = make_row_layout(run_id.value());
  std::uint64_t total = 0U;
  if (!checked_multiply(rows.size(), layout.joined_row_bytes, total) ||
      total > std::numeric_limits<std::size_t>::max()) {
    throw StorageSetupError("joined format-test buffer size overflows size_t");
  }
  std::vector<std::byte> output(static_cast<std::size_t>(total));
  initialize_prefixes(output.data(), {rows.size(), layout.joined_row_bytes,
                                      layout.prefix_bytes, run_id.value()});
  for (std::size_t index = 0U; index < rows.size(); ++index) {
    if (rows[index].run_id != run_id) {
      throw StorageSetupError("joined format-test row run_id mismatch");
    }
    auto* body = output.data() +
                 index * static_cast<std::size_t>(layout.joined_row_bytes) +
                 static_cast<std::size_t>(layout.prefix_bytes);
    store_words(body, joined_words(rows[index]));
  }
  return output;
}

} // namespace cpu_prefetch::storage
