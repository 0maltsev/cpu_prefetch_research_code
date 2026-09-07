#include <gtest/gtest.h>

#include "cpu_prefetch/workload/packages.hpp"
#include "cpu_prefetch/workload/records.hpp"
#include "cpu_prefetch/workload/working_set.hpp"

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <stdexcept>
#include <type_traits>
#include <vector>

namespace {

using cpu_prefetch::protocol::QueuePackage;
using cpu_prefetch::protocol::WorkingSetClass;
using cpu_prefetch::queue::ArenaAlignmentBytes;
using cpu_prefetch::queue::CacheLineBytes;
using cpu_prefetch::queue::DequeueStatus;
using cpu_prefetch::queue::EnqueueResult;
using cpu_prefetch::queue::EventPointer;
using cpu_prefetch::queue::LinkedSpscQueue;
using cpu_prefetch::queue::QueueCapacity;
using cpu_prefetch::queue::RingSpscQueue;
using cpu_prefetch::workload::AcceptedOrdinal;
using cpu_prefetch::workload::AddressPatternSummary;
using cpu_prefetch::workload::CacheCapacityEvidence;
using cpu_prefetch::workload::ConsumerState;
using cpu_prefetch::workload::DeterministicStream;
using cpu_prefetch::workload::EventArena;
using cpu_prefetch::workload::EventArenaConfig;
using cpu_prefetch::workload::L0Package;
using cpu_prefetch::workload::LogicalSequence;
using cpu_prefetch::workload::MasterSeed;
using cpu_prefetch::workload::NodeOrderConfig;
using cpu_prefetch::workload::NodeOrderPlan;
using cpu_prefetch::workload::PhiloxKey;
using cpu_prefetch::workload::R0Package;
using cpu_prefetch::workload::RecordAccessStatus;
using cpu_prefetch::workload::RecordIndex;
using cpu_prefetch::workload::SharedFootprintCandidate;
using cpu_prefetch::workload::StreamPurpose;
using cpu_prefetch::workload::WorkloadSetupError;

constexpr CacheLineBytes kLine{64U};
constexpr ArenaAlignmentBytes kPage{4096U};

MasterSeed test_seed() {
  return MasterSeed::from_hex("000102030405060708090a0b0c0d0e0f"
                              "101112131415161718191a1b1c1d1e1f");
}

EventArena make_arena(std::size_t capacity = 8U,
                      std::string seed_namespace = "stage6-test") {
  return EventArena(EventArenaConfig{capacity, kLine.value, kPage.value, test_seed(),
                                     std::move(seed_namespace)});
}

EventPointer required_pointer(const void* pointer) {
  const auto result = EventPointer::from(pointer);
  if (!result.has_value()) {
    throw std::logic_error("test record pointer was unexpectedly null");
  }
  return *result;
}

struct FakePrefetchEmitter final {
  std::array<const void*, 32> producer_targets{};
  std::array<const void*, 32> consumer_targets{};
  std::array<const void*, 32> successor_targets{};
  std::size_t producer_count{0U};
  std::size_t consumer_count{0U};
  std::size_t successor_count{0U};

  void ring_producer_write(const void* target) noexcept {
    producer_targets[producer_count++] = target;
  }
  void ring_consumer_read(const void* target) noexcept {
    consumer_targets[consumer_count++] = target;
  }
  void successor_header(const void* target) noexcept {
    successor_targets[successor_count++] = target;
  }
};

TEST(DeterministicSuite, ParsesSeedAndMatchesPhiloxAndHmacKnownAnswers) {
  EXPECT_THROW((void)MasterSeed::from_hex("00"), WorkloadSetupError);
  EXPECT_THROW((void)MasterSeed::from_hex("g00102030405060708090a0b0c0d0e0f"
                                          "101112131415161718191a1b1c1d1e1f"),
               WorkloadSetupError);

  const auto zero = cpu_prefetch::workload::philox4x32_10(0U, PhiloxKey{{0U, 0U}});
  EXPECT_EQ(zero.words, (std::array<std::uint32_t, 4>{0x6627e8d5U, 0xe169c58dU,
                                                      0xbc57ac4cU, 0x9b00dbd8U}));

  const auto event_key = cpu_prefetch::workload::derive_stream_key(
      test_seed(), "stage6-test", StreamPurpose::event_order);
  EXPECT_EQ(event_key.words, (std::array<std::uint32_t, 2>{0x204497c9U, 0x221fbf67U}));
  const DeterministicStream stream(event_key);
  EXPECT_EQ(stream.draw(0U), 0x22585625d47ac20bULL);
  EXPECT_EQ(stream.draw(1U), 0x039075e0b49801faULL);

  const auto permutation = cpu_prefetch::workload::make_permutation(8U, stream);
  EXPECT_EQ(permutation, (std::vector<std::size_t>{7U, 4U, 0U, 5U, 2U, 6U, 1U, 3U}));
  EXPECT_THROW((void)cpu_prefetch::workload::make_permutation(0U, stream),
               WorkloadSetupError);
}

TEST(DeterministicSuite, PurposeDomainsProduceDistinctStableStreams) {
  std::array<PhiloxKey, 4> keys{
      cpu_prefetch::workload::derive_stream_key(test_seed(), "stage6-test",
                                                StreamPurpose::event_order),
      cpu_prefetch::workload::derive_stream_key(test_seed(), "stage6-test",
                                                StreamPurpose::node_order),
      cpu_prefetch::workload::derive_stream_key(test_seed(), "stage6-test",
                                                StreamPurpose::event_payload),
      cpu_prefetch::workload::derive_stream_key(test_seed(), "stage6-test",
                                                StreamPurpose::initial_consumer_state)};
  for (std::size_t left = 0; left < keys.size(); ++left) {
    for (std::size_t right = left + 1U; right < keys.size(); ++right) {
      EXPECT_NE(keys[left], keys[right]);
    }
  }
  EXPECT_THROW((void)cpu_prefetch::workload::derive_stream_key(
                   test_seed(), "", StreamPurpose::event_order),
               WorkloadSetupError);
  EXPECT_EQ(
      cpu_prefetch::workload::initial_consumer_state(test_seed(), "stage6-test").value,
      0x80b849f89efe505dULL);
}

TEST(EventArena, DeterministicOneLineRecordsAndCyclicLookup) {
  auto first = make_arena();
  auto second = make_arena();
  const auto layout = first.layout();
  EXPECT_EQ(layout.capacity, 8U);
  EXPECT_EQ(layout.allocated_bytes, 8U * kLine.value);
  EXPECT_EQ(layout.distinct_cache_lines, 8U);
  EXPECT_EQ(layout.distinct_pages, 1U);
  EXPECT_TRUE(layout.base_page_aligned);
  EXPECT_TRUE(layout.every_record_line_aligned);
  EXPECT_TRUE(layout.padding_initialized);
  EXPECT_TRUE(std::ranges::equal(first.record_order(), second.record_order()));
  EXPECT_EQ(first.prepared_content_checksum(), second.prepared_content_checksum());
  EXPECT_EQ(first.ordered_index_checksum(), second.ordered_index_checksum());
  EXPECT_EQ(first.address_delta_checksum(), second.address_delta_checksum());
  EXPECT_EQ(first.prepared_content_checksum().hex(),
            "a14a1bde2dacaf6622af22ccb0b05b3c98b95a40741f9c25e85625ad2e393d60");
  EXPECT_EQ(first.ordered_index_checksum().hex(),
            "af670b376e5b3784d7d3fa5fb326fd630d05f2a9d0e8c2fcf1f325232dbfa73b");
  EXPECT_EQ(first.address_delta_checksum().hex(),
            "e36232c7069da78a765c528361837744233ca7ed54554d836bf58e4c9503aa12");

  for (std::size_t index = 0; index < first.capacity(); ++index) {
    EXPECT_EQ(first.physical_record(index).record_index, index);
    EXPECT_EQ(first.physical_record(index).payload,
              second.physical_record(index).payload);
  }
  const auto at_zero = first.select(LogicalSequence{0U});
  const auto at_repeat = first.select(LogicalSequence{8U});
  EXPECT_EQ(at_zero.record_index, at_repeat.record_index);
  EXPECT_EQ(at_zero.record, at_repeat.record);
}

TEST(EventArena, DetectsUnexpectedPointersIndexCorruptionAndContentChanges) {
  auto arena = make_arena();
  ConsumerState state{1U};
  const auto selection = arena.select(LogicalSequence{2U});
  const auto valid = arena.access_and_mix(selection.record, state);
  EXPECT_EQ(valid.status, RecordAccessStatus::valid);
  EXPECT_EQ(valid.record_index, selection.record_index);

  std::uint64_t unrelated = 0U;
  EXPECT_EQ(arena.access_and_mix(&unrelated, state).status,
            RecordAccessStatus::outside_arena);
  const auto* interior = reinterpret_cast<const std::byte*>(selection.record) + 8U;
  EXPECT_EQ(arena.access_and_mix(interior, state).status,
            RecordAccessStatus::not_record_start);

  auto* mutable_record = const_cast<cpu_prefetch::workload::EventRecord*>(
      &arena.physical_record(selection.record_index.value));
  const auto original_index = mutable_record->record_index;
  const auto original_payload = mutable_record->payload;
  const auto before = arena.content_checksum();
  mutable_record->record_index ^= 1U;
  EXPECT_EQ(arena.access_and_mix(selection.record, state).status,
            RecordAccessStatus::record_index_corrupt);
  EXPECT_NE(arena.content_checksum(), before);
  mutable_record->record_index = original_index;
  mutable_record->payload ^= 0x80U;
  EXPECT_NE(arena.content_checksum(), before);
  mutable_record->payload = original_payload;
  auto* padding = reinterpret_cast<std::byte*>(mutable_record) +
                  sizeof(cpu_prefetch::workload::EventRecord);
  *padding ^= std::byte{0x01};
  EXPECT_NE(arena.content_checksum(), before);
  *padding ^= std::byte{0x01};
  EXPECT_EQ(arena.content_checksum(), arena.prepared_content_checksum());
}

TEST(Integrity, MixerOrderAndSignedClosureDeltasAreExact) {
  EXPECT_EQ(
      cpu_prefetch::workload::mix_consumer_state(
          ConsumerState{0x0123456789abcdefULL}, RecordIndex{7U}, 0xfedcba9876543210ULL),
      ConsumerState{0x1c7164a8f0967d9aULL});
  const std::array<std::size_t, 4> order{2U, 0U, 3U, 1U};
  const auto deltas =
      cpu_prefetch::workload::make_cyclic_address_deltas(order, kLine.value);
  EXPECT_EQ(deltas, (std::vector<std::int64_t>{-128, 192, -128, 64}));
  const auto order_hash = cpu_prefetch::workload::ordered_index_sha256(order);
  const auto delta_hash = cpu_prefetch::workload::address_delta_sha256(deltas);
  const std::array<std::size_t, 4> reordered{2U, 0U, 1U, 3U};
  EXPECT_NE(order_hash, cpu_prefetch::workload::ordered_index_sha256(reordered));
  EXPECT_NE(delta_hash, cpu_prefetch::workload::address_delta_sha256(
                            cpu_prefetch::workload::make_cyclic_address_deltas(
                                reordered, kLine.value)));
  const std::array<std::size_t, 4> duplicate{0U, 1U, 1U, 3U};
  EXPECT_THROW((void)cpu_prefetch::workload::ordered_index_sha256(duplicate),
               WorkloadSetupError);
}

TEST(WorkingSet, SelectsProtocolBoundariesForAllThreeClasses) {
  const CacheCapacityEvidence cache{64U, 4096U, 65'536U};
  const std::array<SharedFootprintCandidate, 7> candidates{
      SharedFootprintCandidate{8U, 512U, 600U},
      SharedFootprintCandidate{16U, 1024U, 1200U},
      SharedFootprintCandidate{32U, 2048U, 2000U},
      SharedFootprintCandidate{64U, 9000U, 10'000U},
      SharedFootprintCandidate{128U, 16'000U, 18'000U},
      SharedFootprintCandidate{512U, 100'000U, 150'000U},
      SharedFootprintCandidate{1024U, 140'000U, 160'000U}};
  EXPECT_EQ(cpu_prefetch::workload::select_common_capacity(WorkingSetClass::l2_resident,
                                                           cache, candidates)
                .selected.capacity,
            32U);
  EXPECT_EQ(cpu_prefetch::workload::select_common_capacity(
                WorkingSetClass::llc_resident, cache, candidates)
                .selected.capacity,
            128U);
  EXPECT_EQ(cpu_prefetch::workload::select_common_capacity(WorkingSetClass::beyond_llc,
                                                           cache, candidates)
                .selected.capacity,
            1024U);

  const std::array<SharedFootprintCandidate, 1> lower_boundary{
      SharedFootprintCandidate{8U, 256U, 256U}};
  EXPECT_THROW((void)cpu_prefetch::workload::select_common_capacity(
                   WorkingSetClass::l2_resident, cache, lower_boundary),
               WorkloadSetupError);
  const std::array<SharedFootprintCandidate, 1> one_family_only{
      SharedFootprintCandidate{8U, 512U, 3000U}};
  EXPECT_THROW((void)cpu_prefetch::workload::select_common_capacity(
                   WorkingSetClass::l2_resident, cache, one_family_only),
               WorkloadSetupError);

  const auto accounted =
      cpu_prefetch::workload::make_shared_footprint_candidate(8U, 512U, 128U, 256U);
  EXPECT_EQ(accounted.ring_bytes, 640U);
  EXPECT_EQ(accounted.linked_bytes, 768U);
  EXPECT_THROW((void)cpu_prefetch::workload::make_shared_footprint_candidate(
                   7U, 512U, 128U, 256U),
               WorkloadSetupError);
}

TEST(WorkingSet, NodePlanIsDeterministicBijectionWithLineAndPageEvidence) {
  const NodeOrderConfig geometry{8U, kLine.value, kLine.value, kPage.value};
  const NodeOrderPlan first(geometry, test_seed(), "stage6-test");
  const NodeOrderPlan second(geometry, test_seed(), "stage6-test");
  EXPECT_TRUE(std::ranges::equal(first.order(), second.order()));
  EXPECT_TRUE(std::ranges::equal(first.deltas(), second.deltas()));
  EXPECT_EQ(first.ordered_index_checksum(), second.ordered_index_checksum());
  EXPECT_EQ(first.address_delta_checksum(), second.address_delta_checksum());
  EXPECT_EQ(first.order().size(), 9U);
  std::vector<std::size_t> sorted(first.order().begin(), first.order().end());
  std::ranges::sort(sorted);
  for (std::size_t index = 0; index < sorted.size(); ++index) {
    EXPECT_EQ(sorted[index], index);
  }
  const AddressPatternSummary& summary = first.summary();
  EXPECT_EQ(summary.transition_count, 9U);
  EXPECT_EQ(summary.distinct_line_count, 9U);
  EXPECT_EQ(summary.shortest_period, 9U);
  EXPECT_EQ(summary.distinct_page_count, 1U);
  EXPECT_THROW(NodeOrderPlan({7U, kLine.value, kLine.value, kPage.value}, test_seed(),
                             "stage6-test"),
               WorkloadSetupError);
  EXPECT_THROW(
      NodeOrderPlan({8U, 96U, kLine.value, kPage.value}, test_seed(), "stage6-test"),
      WorkloadSetupError);
}

TEST(Packages, RingTargetsAndDistanceValidationPreserveR1AndR2Semantics) {
  RingSpscQueue ring(QueueCapacity{64U}, kLine);
  FakePrefetchEmitter emitter;
  const auto d1 = cpu_prefetch::workload::ring_one_line_distance(
      {ring.capacity(), kLine.value, sizeof(void*)});
  EXPECT_EQ(d1.slots(), 8U);
  EXPECT_EQ(d1.cache_lines(), 1U);
  const auto expected_producer = ring.producer_slot_target(d1.slots());
  cpu_prefetch::workload::R1Package package(ring, emitter, d1);
  std::uint64_t event = 1U;
  EXPECT_EQ(package.try_enqueue(required_pointer(&event)), EnqueueResult::accepted);
  ASSERT_EQ(emitter.producer_count, 1U);
  EXPECT_EQ(emitter.producer_targets[0], expected_producer);
  const auto expected_consumer = ring.consumer_slot_target(d1.slots());
  EXPECT_EQ(package.try_dequeue().status, DequeueStatus::item);
  ASSERT_EQ(emitter.consumer_count, 1U);
  EXPECT_EQ(emitter.consumer_targets[0], expected_consumer);

  const auto d2 = cpu_prefetch::workload::resolve_calibrated_ring_distance(
      {ring.capacity(), kLine.value, sizeof(void*)}, 2U, "calibration-record-1");
  EXPECT_EQ(d2.distance().slots(), 16U);
  EXPECT_EQ(d2.distance().cache_lines(), 2U);
  EXPECT_EQ(d2.calibration_evidence_id(), "calibration-record-1");
  EXPECT_THROW((void)cpu_prefetch::workload::resolve_calibrated_ring_distance(
                   {ring.capacity(), kLine.value, sizeof(void*)}, 1U, "evidence"),
               WorkloadSetupError);
  EXPECT_THROW((void)cpu_prefetch::workload::resolve_calibrated_ring_distance(
                   {32U, kLine.value, sizeof(void*)}, 2U, "evidence"),
               WorkloadSetupError);
  EXPECT_THROW((void)cpu_prefetch::workload::resolve_calibrated_ring_distance(
                   {ring.capacity(), kLine.value, sizeof(void*)}, 2U, ""),
               WorkloadSetupError);
  EXPECT_THROW((void)cpu_prefetch::workload::ring_one_line_distance(
                   {8U, kLine.value, sizeof(void*)}),
               WorkloadSetupError);
}

TEST(Packages, LinkedL1TargetsOnlyAcquiredSuccessorHeader) {
  auto arena = make_arena();
  const NodeOrderPlan plan({8U, kLine.value, kLine.value, kPage.value}, test_seed(),
                           "stage6-test");
  LinkedSpscQueue queue(QueueCapacity{8U}, kLine, kPage, plan.order());
  EXPECT_EQ(queue.node_stride_bytes(), plan.node_stride_bytes());
  FakePrefetchEmitter emitter;
  cpu_prefetch::workload::L1Package package(queue, emitter);
  const auto selection = arena.select(LogicalSequence{0U});
  ASSERT_EQ(package.try_enqueue(required_pointer(selection.record)),
            EnqueueResult::accepted);
  const auto audit = queue.audit_quiescent();
  ASSERT_EQ(audit.reachable_order.size(), 2U);
  const auto node_index = audit.reachable_order.back();
  const auto* expected_target = static_cast<const std::byte*>(queue.node_arena_base()) +
                                (node_index * queue.node_stride_bytes());
  const auto result = package.try_dequeue();
  ASSERT_EQ(result.status, DequeueStatus::item);
  ASSERT_EQ(emitter.successor_count, 1U);
  EXPECT_EQ(emitter.successor_targets[0], expected_target);
  EXPECT_EQ(emitter.producer_count, 0U);
  EXPECT_EQ(emitter.consumer_count, 0U);
  ConsumerState state{0U};
  EXPECT_EQ(arena.access_and_mix(result.event, state).status,
            RecordAccessStatus::valid);
}

TEST(Packages, AllFivePackagesDemandTheSameImmutableRecordAction) {
  auto arena = make_arena();
  const auto selection = arena.select(LogicalSequence{5U});
  const auto pointer = required_pointer(selection.record);
  const auto expected = cpu_prefetch::workload::mix_consumer_state(
      ConsumerState{7U}, RecordIndex{selection.record->record_index},
      selection.record->payload);

  RingSpscQueue r0_queue(QueueCapacity{64U}, kLine);
  R0Package r0(r0_queue);
  ASSERT_EQ(r0.try_enqueue(pointer), EnqueueResult::accepted);
  ConsumerState r0_state{7U};
  EXPECT_EQ(arena.access_and_mix(r0.try_dequeue().event, r0_state).status,
            RecordAccessStatus::valid);

  RingSpscQueue r1_queue(QueueCapacity{64U}, kLine);
  FakePrefetchEmitter r1_emitter;
  cpu_prefetch::workload::R1Package r1(r1_queue, r1_emitter,
                                       cpu_prefetch::workload::ring_one_line_distance(
                                           {64U, kLine.value, sizeof(void*)}));
  ASSERT_EQ(r1.try_enqueue(pointer), EnqueueResult::accepted);
  ConsumerState r1_state{7U};
  EXPECT_EQ(arena.access_and_mix(r1.try_dequeue().event, r1_state).status,
            RecordAccessStatus::valid);

  RingSpscQueue r2_queue(QueueCapacity{64U}, kLine);
  FakePrefetchEmitter r2_emitter;
  const auto d2 = cpu_prefetch::workload::resolve_calibrated_ring_distance(
      {64U, kLine.value, sizeof(void*)}, 2U, "synthetic-calibration");
  cpu_prefetch::workload::R2Package r2(r2_queue, r2_emitter, d2);
  ASSERT_EQ(r2.try_enqueue(pointer), EnqueueResult::accepted);
  ConsumerState r2_state{7U};
  EXPECT_EQ(arena.access_and_mix(r2.try_dequeue().event, r2_state).status,
            RecordAccessStatus::valid);

  const NodeOrderPlan plan({8U, kLine.value, kLine.value, kPage.value}, test_seed(),
                           "stage6-test");
  LinkedSpscQueue l0_queue(QueueCapacity{8U}, kLine, kPage, plan.order());
  L0Package l0(l0_queue);
  ASSERT_EQ(l0.try_enqueue(pointer), EnqueueResult::accepted);
  ConsumerState l0_state{7U};
  EXPECT_EQ(arena.access_and_mix(l0.try_dequeue().event, l0_state).status,
            RecordAccessStatus::valid);

  LinkedSpscQueue l1_queue(QueueCapacity{8U}, kLine, kPage, plan.order());
  FakePrefetchEmitter l1_emitter;
  cpu_prefetch::workload::L1Package l1(l1_queue, l1_emitter);
  ASSERT_EQ(l1.try_enqueue(pointer), EnqueueResult::accepted);
  ConsumerState l1_state{7U};
  EXPECT_EQ(arena.access_and_mix(l1.try_dequeue().event, l1_state).status,
            RecordAccessStatus::valid);

  EXPECT_EQ(r0_state, expected);
  EXPECT_EQ(r1_state, expected);
  EXPECT_EQ(r2_state, expected);
  EXPECT_EQ(l0_state, expected);
  EXPECT_EQ(l1_state, expected);
  EXPECT_EQ(r1_emitter.producer_count, 1U);
  EXPECT_EQ(r1_emitter.consumer_count, 1U);
  EXPECT_EQ(r2_emitter.producer_count, 1U);
  EXPECT_EQ(r2_emitter.consumer_count, 1U);
  EXPECT_EQ(l1_emitter.successor_count, 1U);
}

TEST(EventArena, RejectsImplicitOrInvalidPlatformAndCapacityFacts) {
  const EventArena boundary(
      EventArenaConfig{1U, 64U, 4096U, test_seed(), "boundary-test"});
  EXPECT_EQ(boundary.capacity(), 1U);
  EXPECT_EQ(boundary.select(LogicalSequence{0U}).record,
            boundary.select(LogicalSequence{1U}).record);
  EXPECT_THROW(EventArena(EventArenaConfig{0U, 64U, 4096U, test_seed(), "test"}),
               WorkloadSetupError);
  EXPECT_THROW(EventArena(EventArenaConfig{7U, 64U, 4096U, test_seed(), "test"}),
               WorkloadSetupError);
  EXPECT_THROW(EventArena(EventArenaConfig{8U, 48U, 4096U, test_seed(), "test"}),
               WorkloadSetupError);
  EXPECT_THROW(EventArena(EventArenaConfig{8U, 64U, 0U, test_seed(), "test"}),
               WorkloadSetupError);
  EXPECT_THROW(EventArena(EventArenaConfig{8U, 64U, 4096U, test_seed(), ""}),
               WorkloadSetupError);
}

static_assert(!std::is_same_v<RecordIndex, LogicalSequence>);
static_assert(!std::is_same_v<RecordIndex, AcceptedOrdinal>);
static_assert(R0Package::package == QueuePackage::r0);
static_assert(L0Package::package == QueuePackage::l0);

} // namespace
