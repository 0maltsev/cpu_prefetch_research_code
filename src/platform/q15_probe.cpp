#include "cpu_prefetch/platform/q15_probe.hpp"

#include <cstring>
#include <limits>
#include <memory>
#include <new>

namespace cpu_prefetch::platform {
namespace {

[[nodiscard]] auto checked_buffer_bytes(std::size_t line_count) -> std::size_t {
  if (line_count == 0U || line_count > static_cast<std::size_t>(
                                           std::numeric_limits<std::uint32_t>::max())) {
    throw workload::WorkloadSetupError(
        "Q15 pointer probe line count must fit a nonzero uint32 index domain");
  }
  if (line_count > std::numeric_limits<std::size_t>::max() / kQ15ProbeCacheLineBytes) {
    throw workload::WorkloadSetupError("Q15 pointer probe byte count overflows size_t");
  }
  return line_count * kQ15ProbeCacheLineBytes;
}

[[nodiscard]] auto read_next_index(const std::byte* buffer,
                                   std::size_t line_index) noexcept -> std::uint32_t {
  std::uint32_t next = 0U;
  std::memcpy(&next, buffer + (line_index * kQ15ProbeCacheLineBytes), sizeof(next));
  return next;
}

[[nodiscard]] auto pass_is_usable(const Q15CountedPassEvidence& evidence) noexcept
    -> bool {
  return evidence.counter.time_enabled != 0U &&
         evidence.counter.time_enabled == evidence.counter.time_running &&
         evidence.minor_faults == 0U && evidence.major_faults == 0U;
}

} // namespace

auto Q15ProbeIntegrityEvidence::content_unchanged() const noexcept -> bool {
  return pre_sha256 == post_sha256;
}

auto Q15ProbeIntegrityEvidence::passes_pointer_cycle(
    std::size_t line_count) const noexcept -> bool {
  return content_unchanged() && exact_cycle_before_counted_pass &&
         counted_load_count == line_count && final_index == start_index;
}

Q15PointerProbeBuffer::Q15PointerProbeBuffer(std::size_t line_count)
    : line_count_(line_count), byte_count_(checked_buffer_bytes(line_count)) {
  storage_ = static_cast<std::byte*>(
      ::operator new(byte_count_, std::align_val_t(kQ15ProbeBasePageBytes)));
  try {
    auto preparation =
        prepare_q15_pointer_probe_buffer({storage_, byte_count_}, line_count_);
    start_index_ = preparation.start_index;
    order_ = std::move(preparation.order);
    prepared_sha256_ = preparation.prepared_sha256;
  } catch (...) {
    ::operator delete(storage_, std::align_val_t(kQ15ProbeBasePageBytes));
    storage_ = nullptr;
    throw;
  }
}

auto prepare_q15_pointer_probe_buffer(std::span<std::byte> buffer,
                                      std::size_t line_count)
    -> Q15PointerProbePreparation {
  const auto byte_count = checked_buffer_bytes(line_count);
  if (buffer.size() != byte_count) {
    throw workload::WorkloadSetupError(
        "Q15 external probe buffer size must equal line_count times 64 bytes");
  }
  const auto seed = workload::MasterSeed::from_hex(kQ15PointerProbeSeedHex);
  const workload::DeterministicStream stream(workload::derive_stream_key(
      seed, kQ15PointerProbeNamespace, workload::StreamPurpose::node_order));
  auto order = workload::make_permutation(line_count, stream);
  std::memset(buffer.data(), 0, buffer.size());
  const auto start_index = static_cast<std::uint32_t>(order.front());

  for (std::size_t position = 0U; position < order.size(); ++position) {
    const auto line_index = order[position];
    const auto next_position = position + 1U == order.size() ? 0U : position + 1U;
    const auto next_index = static_cast<std::uint32_t>(order[next_position]);
    std::memcpy(buffer.data() + (line_index * kQ15ProbeCacheLineBytes), &next_index,
                sizeof(next_index));
  }
  if (!validate_q15_pointer_cycle(buffer, line_count, start_index)) {
    throw workload::WorkloadSetupError(
        "Q15 pointer probe construction did not form one exact cycle");
  }
  return {start_index, std::move(order), workload::sha256(buffer)};
}

Q15PointerProbeBuffer::~Q15PointerProbeBuffer() {
  if (storage_ != nullptr) {
    ::operator delete(storage_, std::align_val_t(kQ15ProbeBasePageBytes));
  }
}

auto q15_pointer_probe_key() -> workload::PhiloxKey {
  return workload::derive_stream_key(
      workload::MasterSeed::from_hex(kQ15PointerProbeSeedHex),
      kQ15PointerProbeNamespace, workload::StreamPurpose::node_order);
}

auto validate_q15_pointer_cycle(std::span<const std::byte> buffer,
                                std::size_t line_count, std::uint32_t start_index)
    -> bool {
  if (line_count == 0U ||
      line_count >
          static_cast<std::size_t>(std::numeric_limits<std::uint32_t>::max()) ||
      line_count > std::numeric_limits<std::size_t>::max() / kQ15ProbeCacheLineBytes ||
      buffer.size() != line_count * kQ15ProbeCacheLineBytes ||
      start_index >= line_count) {
    return false;
  }
  std::vector<bool> seen(line_count, false);
  auto current = start_index;
  for (std::size_t load = 0U; load < line_count; ++load) {
    if (current >= line_count || seen[current]) {
      return false;
    }
    seen[current] = true;
    current = read_next_index(buffer.data(), current);
  }
  return current == start_index;
}

auto evaluate_q15_probe_pair(Q15ProbeKind kind, const Q15CountedPassEvidence& h0,
                             const Q15CountedPassEvidence& h1,
                             const Q15ProbeIntegrityEvidence& integrity,
                             std::size_t line_count) noexcept
    -> Q15ProbePairAssessment {
  const bool h0_usable = pass_is_usable(h0);
  const bool h1_usable = pass_is_usable(h1);
  const bool not_multiplexed = h0.counter.time_enabled == h0.counter.time_running &&
                               h1.counter.time_enabled == h1.counter.time_running;
  const bool fault_free = h0.minor_faults == 0U && h0.major_faults == 0U &&
                          h1.minor_faults == 0U && h1.major_faults == 0U;
  const bool integrity_passed = integrity.content_unchanged() &&
                                integrity.counted_load_count == line_count &&
                                (kind == Q15ProbeKind::regular_stream ||
                                 integrity.passes_pointer_cycle(line_count));
  const bool h0_positive = h0.counter.all_pf_count > 0U;
  const bool h1_zero = h1.counter.all_pf_count == 0U;
  const auto classification =
      h0_positive ? Q15PointerClassification::distinguished
                  : Q15PointerClassification::not_distinguishable_where_not_possible;
  const bool accepted = h0_usable && h1_usable && integrity_passed && h1_zero &&
                        (kind == Q15ProbeKind::pointer_dependent || h0_positive);
  return {kind,
          classification,
          not_multiplexed,
          fault_free,
          integrity_passed,
          h0_positive,
          h1_zero,
          accepted,
          kind == Q15ProbeKind::regular_stream ? accepted : accepted && h0_positive};
}

extern "C" [[gnu::noinline]] auto cpu_prefetch_q15_regular_counted_traversal(
    const std::byte* buffer, std::size_t line_count) noexcept -> std::uint64_t {
  std::uint64_t observed = 0U;
#if defined(__clang__)
#pragma clang loop unroll(disable)
#elif defined(__GNUC__)
#pragma GCC unroll 1
#endif
  for (std::size_t line = 0U; line < line_count; ++line) {
    const auto* value = reinterpret_cast<const volatile std::uint64_t*>(
        buffer + (line * kQ15ProbeCacheLineBytes));
    observed = *value;
  }
  return observed;
}

extern "C" [[gnu::noinline]] auto cpu_prefetch_q15_pointer_counted_traversal(
    std::size_t line_count, const std::byte* buffer, std::uint32_t start_index) noexcept
    -> std::uint32_t {
  auto current = start_index;
#if defined(__clang__)
#pragma clang loop unroll(disable)
#elif defined(__GNUC__)
#pragma GCC unroll 1
#endif
  for (std::size_t load = 0U; load < line_count; ++load) {
    const auto* next = reinterpret_cast<const volatile std::uint32_t*>(
        buffer + (static_cast<std::size_t>(current) * kQ15ProbeCacheLineBytes));
    current = *next;
  }
  return current;
}

} // namespace cpu_prefetch::platform
