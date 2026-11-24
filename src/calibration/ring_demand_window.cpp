#include "cpu_prefetch/calibration/ring_demand_window.hpp"

#include <array>
#include <cstring>
#include <limits>

namespace cpu_prefetch::calibration {
namespace {

using Status = RingDemandWindowStatus;
constexpr auto maximum = std::numeric_limits<std::uint64_t>::max();

auto store_word(std::byte* destination, std::uint64_t value) noexcept -> void {
  for (std::size_t index = 0U; index < 8U; ++index) {
    destination[index] = static_cast<std::byte>((value >> (index * 8U)) & 255U);
  }
}

[[nodiscard]] auto load_word(const std::byte* source) noexcept -> std::uint64_t {
  std::uint64_t value = 0U;
  for (std::size_t index = 0U; index < 8U; ++index) {
    value |= std::to_integer<std::uint64_t>(source[index]) << (index * 8U);
  }
  return value;
}

struct Range final {
  const void* address;
  std::size_t bytes;
};

[[nodiscard]] auto valid_range(Range range) noexcept -> bool {
  const auto begin = reinterpret_cast<std::uintptr_t>(range.address);
  return range.bytes == 0U ||
         (begin != 0U &&
          range.bytes <= std::numeric_limits<std::uintptr_t>::max() - begin);
}

[[nodiscard]] auto overlaps(Range left, Range right) noexcept -> bool {
  if (left.bytes == 0U || right.bytes == 0U) {
    return false;
  }
  const auto first = reinterpret_cast<std::uintptr_t>(left.address);
  const auto second = reinterpret_cast<std::uintptr_t>(right.address);
  return first < second + right.bytes && second < first + left.bytes;
}

[[nodiscard]] auto valid_worker(RingWorker worker) noexcept -> bool {
  return worker == RingWorker::producer || worker == RingWorker::consumer;
}

[[nodiscard]] auto shape(const RingDemandSnapshot& stream) noexcept -> bool {
  if (stream.format_id != kRingDemandFormatId || !valid_worker(stream.worker) ||
      stream.run_id.empty() ||
      stream.run_id.size() > std::numeric_limits<std::uint32_t>::max() ||
      stream.row_count > stream.row_capacity ||
      !valid_range({stream.bytes.data(), stream.bytes.size()})) {
    return false;
  }
  const auto prefix =
      (4U + static_cast<std::uint64_t>(stream.run_id.size()) + 7U) & ~std::uint64_t{7U};
  const auto row_bytes = prefix + kRingDemandBodyBytes;
  return stream.row_bytes == row_bytes && stream.row_capacity <= maximum / row_bytes &&
         stream.row_capacity * row_bytes <= std::numeric_limits<std::size_t>::max() &&
         stream.row_count * row_bytes == stream.bytes.size();
}

[[nodiscard]] auto sample_status(timing::ClockOrigin origin,
                                 timing::ClockSample sample) noexcept -> Status {
  const auto result =
      timing::relative_clock_sample(origin, sample.absolute_nanoseconds);
  if (result.status == timing::ClockReadStatus::overflow) {
    return Status::arithmetic_overflow;
  }
  return result.status == timing::ClockReadStatus::ok &&
                 result.sample.relative_picoseconds == sample.relative_picoseconds
             ? Status::complete
             : Status::clock_binding_mismatch;
}

[[nodiscard]] auto buffers_disjoint(const RingDemandSnapshot& stream,
                                    ServiceIntervalClock clock,
                                    RingDemandWindowBuffers buffers) noexcept -> bool {
  if (buffers.demand.size() > std::numeric_limits<std::size_t>::max() / 8U ||
      buffers.issue.size() > std::numeric_limits<std::size_t>::max() / 8U) {
    return false;
  }
  const std::array outputs{Range{buffers.demand.data(), buffers.demand.size_bytes()},
                           Range{buffers.issue.data(), buffers.issue.size_bytes()}};
  const std::array inputs{
      Range{stream.bytes.data(), stream.bytes.size()},
      Range{stream.run_id.data(), stream.run_id.size()},
      Range{stream.format_id.data(), stream.format_id.size()},
      Range{clock.clock_suite_id.data(), clock.clock_suite_id.size()},
      Range{clock.time_unit.data(), clock.time_unit.size()},
      Range{&stream, sizeof(stream)}};
  for (const auto output : outputs) {
    if (!valid_range(output)) {
      return false;
    }
    for (const auto input : inputs) {
      if (!valid_range(input) || overlaps(output, input)) {
        return false;
      }
    }
  }
  return !overlaps(outputs[0U], outputs[1U]);
}

} // namespace

auto ring_demand_layout(const protocol::RunId& run_id) -> RingDemandLayout {
  const auto primary = storage::make_row_layout(run_id.value());
  return {primary.run_id_bytes, primary.prefix_bytes,
          primary.prefix_bytes + kRingDemandBodyBytes};
}

auto ring_demand_storage_requirements(const protocol::RunId& run_id,
                                      std::uint64_t row_capacity) -> std::size_t {
  const auto layout = ring_demand_layout(run_id);
  if (row_capacity > maximum / layout.row_bytes ||
      row_capacity * layout.row_bytes > std::numeric_limits<std::size_t>::max()) {
    throw storage::StorageSetupError("ring demand buffer size overflows");
  }
  return static_cast<std::size_t>(row_capacity * layout.row_bytes);
}

RingDemandStream::RingDemandStream(const protocol::RunId& run_id, RingWorker worker,
                                   std::uint64_t row_capacity,
                                   std::span<std::byte> external_storage)
    : run_id_(run_id.value()), worker_(worker), layout_(ring_demand_layout(run_id)),
      storage_(external_storage), capacity_(row_capacity) {
  const auto bytes = ring_demand_storage_requirements(run_id, row_capacity);
  const Range buffer{storage_.data(), storage_.size()};
  const Range self{this, sizeof(*this)};
  const Range identity{run_id_.data(), run_id_.size()};
  if (!valid_worker(worker) || storage_.size() != bytes || !valid_range(buffer) ||
      !valid_range(self) || !valid_range(identity) || overlaps(buffer, self) ||
      overlaps(buffer, identity) ||
      (bytes != 0U && reinterpret_cast<std::uintptr_t>(buffer.address) %
                              storage::kRawBufferAlignment !=
                          0U)) {
    throw storage::StorageSetupError(
        "ring demand requires disjoint aligned exact storage");
  }
}

auto RingDemandStream::prepare_for_owner() noexcept -> bool {
  if (prepared_ || completeness_ != storage::StreamCompleteness::writing) {
    return false;
  }
  if (!storage_.empty()) {
    std::memset(storage_.data(), 0, storage_.size());
  }
  for (std::uint64_t row = 0U; row < capacity_; ++row) {
    auto* prefix = storage_.data() + static_cast<std::size_t>(row * layout_.row_bytes);
    for (std::size_t index = 0U; index < 4U; ++index) {
      prefix[index] =
          static_cast<std::byte>((layout_.run_id_bytes >> (index * 8U)) & 255U);
    }
    std::memcpy(prefix + 4U, run_id_.data(), run_id_.size());
  }
  prepared_ = true;
  return true;
}

auto RingDemandStream::append(const RingDemandRecord& record) noexcept
    -> storage::AppendStatus {
  if (!prepared_) {
    return storage::AppendStatus::stream_unprepared;
  }
  if (completeness_ != storage::StreamCompleteness::writing) {
    return storage::AppendStatus::stream_sealed;
  }
  if (count_ == capacity_) {
    overflowed_ = true;
    completeness_ = storage::StreamCompleteness::sealed_incomplete;
    return storage::AppendStatus::buffer_overflow;
  }
  const std::array<std::uint64_t, 9U> words{
      record.attempt_ordinal,
      static_cast<std::uint64_t>(record.outcome),
      record.advancing_ordinal,
      static_cast<std::uint64_t>(record.before.status),
      record.before.sample.absolute_nanoseconds,
      record.before.sample.relative_picoseconds,
      static_cast<std::uint64_t>(record.after.status),
      record.after.sample.absolute_nanoseconds,
      record.after.sample.relative_picoseconds};
  auto* body = storage_.data() + static_cast<std::size_t>(count_ * layout_.row_bytes +
                                                          layout_.prefix_bytes);
  for (std::size_t index = 0U; index < words.size(); ++index) {
    store_word(body + index * 8U, words[index]);
  }
  ++count_;
  return storage::AppendStatus::appended;
}

auto RingDemandStream::seal_complete() noexcept -> bool {
  if (!prepared_ || completeness_ != storage::StreamCompleteness::writing ||
      overflowed_) {
    return false;
  }
  completeness_ = storage::StreamCompleteness::sealed_complete;
  return true;
}

void RingDemandStream::seal_incomplete() noexcept {
  if (completeness_ == storage::StreamCompleteness::writing) {
    completeness_ = storage::StreamCompleteness::sealed_incomplete;
  }
}

auto RingDemandStream::snapshot() const noexcept -> RingDemandSnapshot {
  return {kRingDemandFormatId,
          worker_,
          run_id_,
          storage_.first(static_cast<std::size_t>(count_ * layout_.row_bytes)),
          count_,
          capacity_,
          layout_.row_bytes,
          completeness_,
          overflowed_};
}

auto read_ring_demand_row(const RingDemandSnapshot& stream,
                          std::uint64_t index) noexcept
    -> std::optional<RingDemandRecord> {
  if (!shape(stream) || index >= stream.row_count) {
    return std::nullopt;
  }
  const auto* prefix =
      stream.bytes.data() + static_cast<std::size_t>(index * stream.row_bytes);
  std::uint64_t length = 0U;
  for (std::size_t byte = 0U; byte < 4U; ++byte) {
    length |= std::to_integer<std::uint64_t>(prefix[byte]) << (byte * 8U);
  }
  if (length != stream.run_id.size() ||
      std::memcmp(prefix + 4U, stream.run_id.data(), stream.run_id.size()) != 0) {
    return std::nullopt;
  }
  const auto prefix_bytes = stream.row_bytes - kRingDemandBodyBytes;
  for (std::size_t byte = 4U + stream.run_id.size(); byte < prefix_bytes; ++byte) {
    if (prefix[byte] != std::byte{0U}) {
      return std::nullopt;
    }
  }
  std::array<std::uint64_t, 9U> words{};
  for (std::size_t word = 0U; word < words.size(); ++word) {
    words[word] =
        load_word(prefix + static_cast<std::size_t>(prefix_bytes) + word * 8U);
  }
  if (words[1U] > 2U || words[3U] > 4U || words[6U] > 4U) {
    return std::nullopt;
  }
  return RingDemandRecord{
      words[0U],
      static_cast<RingAttemptOutcome>(words[1U]),
      words[2U],
      {static_cast<timing::ClockReadStatus>(words[3U]), {words[4U], words[5U]}},
      {static_cast<timing::ClockReadStatus>(words[6U]), {words[7U], words[8U]}}};
}

auto classify_ring_demand_window(
    const RingDemandSnapshot& stream, const protocol::RunId& expected_run_id,
    RingWorker expected_worker, RingDemandPhase phase, ServiceIntervalClock clock,
    std::optional<std::uint64_t> minimum_observations_per_series,
    RingDemandWindowBuffers buffers) noexcept -> RingDemandWindowResult {
  if (stream.run_id != expected_run_id.value() || stream.worker != expected_worker ||
      !valid_worker(expected_worker)) {
    return {Status::identity_mismatch};
  }
  const bool measurement = phase == RingDemandPhase::measurement;
  if ((!measurement && phase != RingDemandPhase::warmup) ||
      (measurement && (!minimum_observations_per_series.has_value() ||
                       *minimum_observations_per_series == 0U)) ||
      (!measurement && minimum_observations_per_series.has_value())) {
    return {Status::invalid_phase_contract};
  }
  if (clock.clock_suite_id != timing::kClockSuiteId ||
      clock.time_unit != storage::kRawTimeUnit ||
      clock.ticks_per_second != 1'000'000'000'000U) {
    return {Status::clock_domain_mismatch};
  }
  if (clock.duration_ticks == 0U) {
    return {Status::invalid_duration};
  }
  const timing::ClockOrigin origin{clock.clock_origin_absolute_nanoseconds};
  const auto origin_status = sample_status(origin, clock.measurement_origin);
  if (origin_status != Status::complete) {
    return {origin_status};
  }
  const auto begin = clock.measurement_origin.relative_picoseconds;
  if (clock.duration_ticks > maximum - begin) {
    return {Status::arithmetic_overflow};
  }
  const auto end = begin + clock.duration_ticks;
  const auto end_ns = end / 1000U + (end % 1000U == 0U ? 0U : 1U);
  if (end_ns > maximum - origin.absolute_nanoseconds) {
    return {Status::arithmetic_overflow};
  }
  if (stream.completeness != storage::StreamCompleteness::sealed_complete ||
      stream.overflowed) {
    return {Status::stream_incomplete};
  }
  if (!shape(stream)) {
    return {Status::malformed_stream};
  }
  if (!buffers_disjoint(stream, clock, buffers)) {
    return {Status::overlapping_output};
  }
  std::uint64_t advances = 0U;
  std::uint64_t outside = 0U;
  std::uint64_t demand_count = 0U;
  std::uint64_t eligible_advances = 0U;
  std::uint64_t previous_end = begin;
  std::optional<std::uint64_t> previous_eligible_start;
  for (std::uint64_t index = 0U; index < stream.row_count; ++index) {
    const auto row = read_ring_demand_row(stream, index);
    if (!row.has_value()) {
      return {Status::malformed_row, std::nullopt, index};
    }
    if (row->before.status != timing::ClockReadStatus::ok ||
        row->after.status != timing::ClockReadStatus::ok) {
      return {Status::clock_failure, std::nullopt, index};
    }
    for (const auto sample : {row->before.sample, row->after.sample}) {
      const auto status = sample_status(origin, sample);
      if (status != Status::complete) {
        return {status, std::nullopt, index};
      }
    }
    const bool advanced = row->outcome == RingAttemptOutcome::advanced;
    if (!advanced && !((expected_worker == RingWorker::producer &&
                        row->outcome == RingAttemptOutcome::full) ||
                       (expected_worker == RingWorker::consumer &&
                        row->outcome == RingAttemptOutcome::empty))) {
      return {Status::invalid_outcome, std::nullopt, index};
    }
    if (row->attempt_ordinal != index ||
        row->advancing_ordinal != (advanced ? advances : 0U)) {
      return {Status::ordinal_mismatch, std::nullopt, index};
    }
    const auto start = row->before.sample.relative_picoseconds;
    const auto finish = row->after.sample.relative_picoseconds;
    if (start < begin) {
      return {Status::before_measurement_origin, std::nullopt, index};
    }
    if (start < previous_end || finish < start) {
      return {Status::timestamp_order, std::nullopt, index};
    }
    previous_end = finish;
    advances += advanced ? 1U : 0U;
    if (start >= end) {
      ++outside;
    } else if (measurement) {
      if (finish == start) {
        return {Status::nonpositive_demand, std::nullopt, index};
      }
      ++demand_count;
      if (advanced) {
        if (previous_eligible_start.has_value() && start <= *previous_eligible_start) {
          return {Status::nonpositive_issue, std::nullopt, index};
        }
        previous_eligible_start = start;
        ++eligible_advances;
      }
    }
  }
  const auto issue_count = eligible_advances == 0U ? 0U : eligible_advances - 1U;
  if (measurement && (demand_count < *minimum_observations_per_series ||
                      issue_count < *minimum_observations_per_series)) {
    return {Status::insufficient_observations};
  }
  if (demand_count > buffers.demand.size() || issue_count > buffers.issue.size()) {
    return {Status::output_capacity};
  }
  // The owner is quiescent and the complete immutable byte range was checked
  // above. No output aliases it, so the second pass cannot change its validity.
  std::size_t demand_index = 0U;
  std::size_t issue_index = 0U;
  previous_eligible_start.reset();
  if (measurement) {
    for (std::uint64_t index = 0U; index < stream.row_count; ++index) {
      const auto row = read_ring_demand_row(stream, index);
      if (!row.has_value()) {
        return {Status::malformed_row, std::nullopt, index};
      }
      const auto start = row->before.sample.relative_picoseconds;
      if (start >= end) {
        continue;
      }
      buffers.demand[demand_index++] = row->after.sample.relative_picoseconds - start;
      if (row->outcome == RingAttemptOutcome::advanced) {
        if (previous_eligible_start.has_value()) {
          buffers.issue[issue_index++] = start - *previous_eligible_start;
        }
        previous_eligible_start = start;
      }
    }
  }
  return {Status::complete, RingDemandWindowSeries{phase,
                                                   clock,
                                                   end,
                                                   stream.row_count,
                                                   advances,
                                                   outside,
                                                   eligible_advances,
                                                   {buffers.demand.first(demand_index),
                                                    buffers.issue.first(issue_index),
                                                    demand_count - eligible_advances},
                                                   measurement}};
}

} // namespace cpu_prefetch::calibration
