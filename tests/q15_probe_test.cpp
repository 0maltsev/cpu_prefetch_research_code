#include "cpu_prefetch/platform/q15_probe.hpp"

#include <gtest/gtest.h>

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <limits>
#include <span>
#include <vector>

namespace {

using cpu_prefetch::platform::Q15CountedPassEvidence;
using cpu_prefetch::platform::Q15CounterReading;
using cpu_prefetch::platform::Q15PointerClassification;
using cpu_prefetch::platform::Q15PointerProbeBuffer;
using cpu_prefetch::platform::Q15ProbeIntegrityEvidence;
using cpu_prefetch::platform::Q15ProbeKind;

[[nodiscard]] auto pass(std::uint64_t count) -> Q15CountedPassEvidence {
  return {{count, 100U, 100U}, 0U, 0U};
}

[[nodiscard]] auto integrity(const Q15PointerProbeBuffer& buffer,
                             std::uint32_t final_index) -> Q15ProbeIntegrityEvidence {
  return {buffer.prepared_sha256(),
          cpu_prefetch::workload::sha256(buffer.bytes()),
          static_cast<std::uint64_t>(buffer.line_count()),
          buffer.start_index(),
          final_index,
          cpu_prefetch::platform::validate_q15_pointer_cycle(
              buffer.bytes(), buffer.line_count(), buffer.start_index())};
}

TEST(Q15ProbeDeterminism, AcceptedMasterSeedKeyOrderAndRawBufferHashMatchGolden) {
  const auto key = cpu_prefetch::platform::q15_pointer_probe_key();
  EXPECT_EQ(key.words[0], 0x2a805cfaU);
  EXPECT_EQ(key.words[1], 0xa4038e43U);

  Q15PointerProbeBuffer buffer(8U);
  constexpr std::array<std::size_t, 8U> expected{5U, 2U, 6U, 3U, 0U, 7U, 4U, 1U};
  EXPECT_TRUE(std::equal(buffer.order().begin(), buffer.order().end(), expected.begin(),
                         expected.end()));
  EXPECT_EQ(buffer.start_index(), 5U);
  EXPECT_EQ(buffer.byte_count(), 8U * 64U);
  EXPECT_EQ(reinterpret_cast<std::uintptr_t>(buffer.data()) % 4096U, 0U);
  EXPECT_EQ(buffer.prepared_sha256().hex(),
            "7cefdcad16f83055ae3a1b3219ebfcfe8b131a82afa959fe0fc348818724d540");
}

TEST(Q15ProbeDeterminism, CompleteCycleHasOneIndexPerLineAndZeroFilledRemainder) {
  Q15PointerProbeBuffer buffer(16U);
  std::vector<bool> seen(buffer.line_count(), false);
  auto current = buffer.start_index();
  for (std::size_t load = 0U; load < buffer.line_count(); ++load) {
    ASSERT_LT(current, buffer.line_count());
    EXPECT_FALSE(seen[current]);
    seen[current] = true;
    std::uint32_t next = 0U;
    std::memcpy(&next, buffer.data() + (static_cast<std::size_t>(current) * 64U),
                sizeof(next));
    current = next;
  }
  EXPECT_EQ(current, buffer.start_index());
  EXPECT_TRUE(std::all_of(seen.begin(), seen.end(), [](bool value) { return value; }));
  for (std::size_t line = 0U; line < buffer.line_count(); ++line) {
    const auto bytes = buffer.bytes().subspan(line * 64U, 64U);
    EXPECT_TRUE(std::all_of(bytes.begin() + 4, bytes.end(),
                            [](std::byte value) { return value == std::byte{0}; }));
  }
}

TEST(Q15ProbeTraversal, RegularAndPointerBodiesCompleteExactDemandedLoads) {
  Q15PointerProbeBuffer buffer(8U);
  std::uint64_t expected_regular = 0U;
  for (std::size_t line = 0U; line < buffer.line_count(); ++line) {
    std::memcpy(&expected_regular, buffer.data() + (line * 64U),
                sizeof(expected_regular));
  }
  EXPECT_EQ(cpu_prefetch::platform::cpu_prefetch_q15_regular_counted_traversal(
                buffer.data(), buffer.line_count()),
            expected_regular);
  const auto final = cpu_prefetch::platform::cpu_prefetch_q15_pointer_counted_traversal(
      buffer.line_count(), buffer.data(), buffer.start_index());
  EXPECT_EQ(final, buffer.start_index());
  EXPECT_TRUE(integrity(buffer, final).passes_pointer_cycle(buffer.line_count()));
}

TEST(Q15ProbeValidation, RejectsMalformedOrNoncyclicBuffersAndInvalidCounts) {
  Q15PointerProbeBuffer buffer(8U);
  EXPECT_FALSE(cpu_prefetch::platform::validate_q15_pointer_cycle(
      buffer.bytes().first(buffer.byte_count() - 1U), buffer.line_count(),
      buffer.start_index()));
  EXPECT_FALSE(cpu_prefetch::platform::validate_q15_pointer_cycle(
      buffer.bytes(), buffer.line_count(), 8U));

  auto corrupt = std::vector<std::byte>(buffer.bytes().begin(), buffer.bytes().end());
  const std::uint32_t self = buffer.start_index();
  std::memcpy(corrupt.data() + (static_cast<std::size_t>(self) * 64U), &self,
              sizeof(self));
  EXPECT_FALSE(cpu_prefetch::platform::validate_q15_pointer_cycle(
      corrupt, buffer.line_count(), buffer.start_index()));

  EXPECT_THROW((Q15PointerProbeBuffer{0U}), cpu_prefetch::workload::WorkloadSetupError);
  if constexpr (sizeof(std::size_t) > sizeof(std::uint32_t)) {
    EXPECT_THROW(
        (Q15PointerProbeBuffer{
            static_cast<std::size_t>(std::numeric_limits<std::uint32_t>::max()) + 1U}),
        cpu_prefetch::workload::WorkloadSetupError);
  }
}

TEST(Q15ProbeIntegrity, RequiresFullHashEqualityExactCycleAndExactClosure) {
  Q15PointerProbeBuffer buffer(8U);
  auto evidence = integrity(buffer, buffer.start_index());
  EXPECT_TRUE(evidence.passes_pointer_cycle(buffer.line_count()));
  evidence.counted_load_count -= 1U;
  EXPECT_FALSE(evidence.passes_pointer_cycle(buffer.line_count()));
  evidence.counted_load_count += 1U;
  evidence.final_index = static_cast<std::uint32_t>((buffer.start_index() + 1U) % 8U);
  EXPECT_FALSE(evidence.passes_pointer_cycle(buffer.line_count()));
  evidence.final_index = buffer.start_index();
  evidence.exact_cycle_before_counted_pass = false;
  EXPECT_FALSE(evidence.passes_pointer_cycle(buffer.line_count()));
}

TEST(Q15ProbeClassification, AppliesRegularAndWherePossiblePointerRulesExactly) {
  Q15PointerProbeBuffer buffer(8U);
  const auto valid_integrity = integrity(buffer, buffer.start_index());

  const auto regular = cpu_prefetch::platform::evaluate_q15_probe_pair(
      Q15ProbeKind::regular_stream, pass(9U), pass(0U), valid_integrity,
      buffer.line_count());
  EXPECT_TRUE(regular.accepted);
  EXPECT_TRUE(regular.distinguished);
  EXPECT_TRUE(regular.counter_not_multiplexed);
  EXPECT_TRUE(regular.counted_pass_fault_free);

  const auto pointer_zero = cpu_prefetch::platform::evaluate_q15_probe_pair(
      Q15ProbeKind::pointer_dependent, pass(0U), pass(0U), valid_integrity,
      buffer.line_count());
  EXPECT_TRUE(pointer_zero.accepted);
  EXPECT_FALSE(pointer_zero.distinguished);
  EXPECT_EQ(pointer_zero.pointer_classification,
            Q15PointerClassification::not_distinguishable_where_not_possible);

  const auto pointer_positive = cpu_prefetch::platform::evaluate_q15_probe_pair(
      Q15ProbeKind::pointer_dependent, pass(1U), pass(0U), valid_integrity,
      buffer.line_count());
  EXPECT_TRUE(pointer_positive.accepted);
  EXPECT_TRUE(pointer_positive.distinguished);
  EXPECT_EQ(pointer_positive.pointer_classification,
            Q15PointerClassification::distinguished);
}

TEST(Q15ProbeClassification, FailsClosedOnH1FaultMultiplexOrIntegrityMismatch) {
  Q15PointerProbeBuffer buffer(8U);
  auto valid_integrity = integrity(buffer, buffer.start_index());
  auto h0 = pass(4U);
  auto h1 = pass(1U);
  EXPECT_FALSE(
      cpu_prefetch::platform::evaluate_q15_probe_pair(
          Q15ProbeKind::regular_stream, h0, h1, valid_integrity, buffer.line_count())
          .accepted);

  h1 = pass(0U);
  h1.counter.time_running -= 1U;
  EXPECT_FALSE(
      cpu_prefetch::platform::evaluate_q15_probe_pair(
          Q15ProbeKind::regular_stream, h0, h1, valid_integrity, buffer.line_count())
          .accepted);
  h1 = pass(0U);
  h1.minor_faults = 1U;
  EXPECT_FALSE(
      cpu_prefetch::platform::evaluate_q15_probe_pair(
          Q15ProbeKind::regular_stream, h0, h1, valid_integrity, buffer.line_count())
          .accepted);
  h1 = pass(0U);
  h1.counter.time_enabled = 0U;
  h1.counter.time_running = 0U;
  EXPECT_FALSE(
      cpu_prefetch::platform::evaluate_q15_probe_pair(
          Q15ProbeKind::regular_stream, h0, h1, valid_integrity, buffer.line_count())
          .accepted);
  h1 = pass(0U);
  valid_integrity.post_sha256 =
      cpu_prefetch::workload::sha256(std::span<const std::byte>{});
  EXPECT_FALSE(
      cpu_prefetch::platform::evaluate_q15_probe_pair(
          Q15ProbeKind::regular_stream, h0, h1, valid_integrity, buffer.line_count())
          .accepted);
}

} // namespace
