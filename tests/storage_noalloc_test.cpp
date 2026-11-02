#include <gtest/gtest.h>

#include "cpu_prefetch/calibration/discovery_residency_observer.hpp"
#include "cpu_prefetch/storage/raw_observations.hpp"
#include "discovery_backend_test_support.hpp"

#include <array>
#include <atomic>
#include <cstddef>
#include <cstdlib>
#include <memory>
#include <new>
#include <optional>
#include <span>
#include <stdexcept>
#include <string>

namespace {
std::atomic<std::size_t> allocation_count{0U};
}

void* operator new(std::size_t size) {
  allocation_count.fetch_add(1U, std::memory_order_relaxed);
  if (void* memory = std::malloc(size); memory != nullptr) {
    return memory;
  }
  throw std::bad_alloc();
}

void* operator new[](std::size_t size) { return ::operator new(size); }

void* operator new(std::size_t size, const std::nothrow_t&) noexcept {
  allocation_count.fetch_add(1U, std::memory_order_relaxed);
  return std::malloc(size);
}

void* operator new[](std::size_t size, const std::nothrow_t& tag) noexcept {
  return ::operator new(size, tag);
}

void* operator new(std::size_t size, std::align_val_t alignment) {
  allocation_count.fetch_add(1U, std::memory_order_relaxed);
  void* memory = nullptr;
  if (posix_memalign(&memory, static_cast<std::size_t>(alignment), size) == 0) {
    return memory;
  }
  throw std::bad_alloc();
}

void* operator new[](std::size_t size, std::align_val_t alignment) {
  return ::operator new(size, alignment);
}

void* operator new(std::size_t size, std::align_val_t alignment,
                   const std::nothrow_t&) noexcept {
  allocation_count.fetch_add(1U, std::memory_order_relaxed);
  void* memory = nullptr;
  return posix_memalign(&memory, static_cast<std::size_t>(alignment), size) == 0
             ? memory
             : nullptr;
}

void* operator new[](std::size_t size, std::align_val_t alignment,
                     const std::nothrow_t& tag) noexcept {
  return ::operator new(size, alignment, tag);
}

void operator delete(void* pointer) noexcept { std::free(pointer); }
void operator delete[](void* pointer) noexcept { std::free(pointer); }
void operator delete(void* pointer, std::size_t) noexcept { std::free(pointer); }
void operator delete[](void* pointer, std::size_t) noexcept { std::free(pointer); }
void operator delete(void* pointer, std::align_val_t) noexcept { std::free(pointer); }
void operator delete[](void* pointer, std::align_val_t) noexcept { std::free(pointer); }
void operator delete(void* pointer, std::size_t, std::align_val_t) noexcept {
  std::free(pointer);
}
void operator delete[](void* pointer, std::size_t, std::align_val_t) noexcept {
  std::free(pointer);
}
void operator delete(void* pointer, const std::nothrow_t&) noexcept {
  std::free(pointer);
}
void operator delete[](void* pointer, const std::nothrow_t&) noexcept {
  std::free(pointer);
}
void operator delete(void* pointer, std::align_val_t, const std::nothrow_t&) noexcept {
  std::free(pointer);
}
void operator delete[](void* pointer, std::align_val_t,
                       const std::nothrow_t&) noexcept {
  std::free(pointer);
}

namespace {

auto run_id() -> cpu_prefetch::protocol::RunId {
  auto parsed = cpu_prefetch::protocol::RunId::parse("noalloc", "$test/run_id");
  if (!parsed) {
    throw std::logic_error("invalid test run ID");
  }
  return std::move(parsed).value();
}

TEST(StorageHotWriter, ProducerAndConsumerAppendAllocateNothingAfterPreparation) {
  const auto id = run_id();
  cpu_prefetch::storage::ProducerObservationStream producer(id, 1U);
  cpu_prefetch::storage::ConsumerObservationStream consumer(id, 1U);
  ASSERT_TRUE(producer.prepare_for_owner());
  ASSERT_TRUE(consumer.prepare_for_owner());
  const cpu_prefetch::timing::ProducerObservation producer_row{
      cpu_prefetch::workload::LogicalSequence{0U},
      cpu_prefetch::workload::RecordIndex{7U},
      1U,
      {1U, 2U},
      {2U, 3U},
      {3U, 4U},
      cpu_prefetch::timing::ClockSample{4U, 5U},
      {5U, 6U},
      cpu_prefetch::protocol::ProducerOutcome::accepted,
      cpu_prefetch::workload::AcceptedOrdinal{0U}};
  const cpu_prefetch::timing::ConsumerObservation consumer_row{
      cpu_prefetch::workload::AcceptedOrdinal{0U},
      cpu_prefetch::workload::RecordIndex{7U},
      {6U, 7U},
      {7U, 8U},
      {8U, 9U},
      {9U, 10U}};

  const auto before = allocation_count.load(std::memory_order_relaxed);
  const auto producer_status = producer.append(producer_row);
  const auto consumer_status = consumer.append(consumer_row);
  const auto producer_snapshot = producer.snapshot();
  const auto consumer_snapshot = consumer.snapshot();
  const auto after = allocation_count.load(std::memory_order_relaxed);

  EXPECT_EQ(producer_status, cpu_prefetch::storage::AppendStatus::appended);
  EXPECT_EQ(consumer_status, cpu_prefetch::storage::AppendStatus::appended);
  EXPECT_EQ(producer_snapshot.row_count, 1U);
  EXPECT_EQ(consumer_snapshot.row_count, 1U);
  EXPECT_EQ(after, before);
}

TEST(StorageHotWriter, CallerOwnedPreparationAppendSealSnapshotAllocateNothing) {
  namespace storage = cpu_prefetch::storage;
  const auto id = run_id();
  const auto requirements = storage::raw_stream_storage_requirements(id, 1U, 1U);
  alignas(64) std::array<std::byte, 1024U> producer_bytes{};
  alignas(64) std::array<std::byte, 1024U> consumer_bytes{};
  storage::ProducerObservationStream producer(
      id, 1U, std::span(producer_bytes).first(requirements.producer_bytes));
  storage::ConsumerObservationStream consumer(
      id, 1U, std::span(consumer_bytes).first(requirements.consumer_bytes));
  const cpu_prefetch::timing::ProducerObservation producer_row{
      {0U},
      {7U},
      1U,
      {1U, 2U},
      {2U, 3U},
      {3U, 4U},
      cpu_prefetch::timing::ClockSample{4U, 5U},
      {5U, 6U},
      cpu_prefetch::protocol::ProducerOutcome::accepted,
      cpu_prefetch::workload::AcceptedOrdinal{0U}};
  const cpu_prefetch::timing::ConsumerObservation consumer_row{
      {0U}, {7U}, {6U, 7U}, {7U, 8U}, {8U, 9U}, {9U, 10U}};
  const auto before = allocation_count.load(std::memory_order_relaxed);
  const bool prepared = producer.prepare_for_owner() && consumer.prepare_for_owner();
  const auto p_status = producer.append(producer_row);
  const auto c_status = consumer.append(consumer_row);
  const bool sealed = producer.seal_complete() && consumer.seal_complete();
  const auto p = producer.snapshot();
  const auto c = consumer.snapshot();
  const auto after = allocation_count.load(std::memory_order_relaxed);
  EXPECT_TRUE(prepared);
  EXPECT_TRUE(sealed);
  EXPECT_EQ(p_status, storage::AppendStatus::appended);
  EXPECT_EQ(c_status, storage::AppendStatus::appended);
  EXPECT_EQ(p.bytes.data(), producer_bytes.data());
  EXPECT_EQ(c.bytes.data(), consumer_bytes.data());
  EXPECT_EQ(after, before);
}

TEST(StorageHotWriter, DiscoveryPhaseCaptureDrainJoinAndResetAllocateNothing) {
  namespace support = cpu_prefetch::test_support;
  namespace calibration = cpu_prefetch::calibration;
  auto preparation = std::make_unique<support::SoftwareOnlyDiscoveryPreparation<64U>>();
  support::DiscoveryTestClock clock;
  auto plan = support::kDiscoveryTestPlan;
  plan.warmup_attempt_capacity = 64U;
  plan.measurement_attempt_capacity = 64U;
  calibration::DiscoveryRingPhaseBackend backend(plan, clock, *preparation);
  ASSERT_TRUE(backend.prepare_producer());
  ASSERT_TRUE(backend.prepare_consumer());
  const auto before = allocation_count.load(std::memory_order_relaxed);
  bool valid = true;
  for (unsigned index = 0U; index < 16U; ++index) {
    valid = backend.warmup_producer_attempt(0U).outcome ==
                calibration::RingAttemptOutcome::advanced &&
            valid;
    valid = backend.warmup_consumer_attempt().outcome ==
                calibration::RingAttemptOutcome::advanced &&
            valid;
  }
  valid = backend.warmup_producer_attempt(0U).outcome ==
              calibration::RingAttemptOutcome::advanced &&
          valid;
  std::array<calibration::DiscoveryWorkerResult, 2U> workers{
      calibration::DiscoveryWorkerResult{
          calibration::DiscoveryWorkerStop::fixed_deadline},
      calibration::DiscoveryWorkerResult{
          calibration::DiscoveryWorkerStop::fixed_deadline}};
  workers[0U].attempts = 17U;
  workers[0U].advanced = 17U;
  workers[1U].attempts = 16U;
  workers[1U].advanced = 16U;
  valid = backend.validate_warmup(workers) && valid;
  const auto origin = clock.read();
  const auto drain = backend.drain_warmup(
      {origin.sample.relative_picoseconds, 1'000'000U, 9U, 1U, true});
  valid = drain.stop == calibration::DiscoveryDrainStop::complete &&
          drain.reset_verified && valid;
  valid = backend.reset_consumer() && backend.reset_producer() && valid;
  const auto after = allocation_count.load(std::memory_order_relaxed);
  EXPECT_TRUE(valid);
  EXPECT_EQ(after, before);
  EXPECT_EQ(preparation->warmup.consumer.last_join.status,
            calibration::DiscoveryJoinStatus::exact);
  EXPECT_EQ(preparation->warmup.consumer.consumed, 17U);
}

TEST(StorageHotWriter, PlannedResidencySnapshotsAllocateNothing) {
  namespace calibration = cpu_prefetch::calibration;
  namespace platform = cpu_prefetch::platform;
  using Phase = calibration::DiscoverySessionPhase;
  using Moment = calibration::DiscoveryResidencyMoment;
  alignas(4096) std::array<std::byte, 4096U> mapping{};
  std::array<void*, 6U> addresses{};
  std::array<int, 6U> nodes{};
  auto prepare_query = [&](std::size_t index) {
    return platform::PreparedPageResidencyQuery(mapping, 4096U,
                                                std::span(addresses).subspan(index, 1U),
                                                std::span(nodes).subspan(index, 1U));
  };
  std::array queries{prepare_query(0U), prepare_query(1U), prepare_query(2U),
                     prepare_query(3U), prepare_query(4U), prepare_query(5U)};
  std::array<calibration::DiscoveryResidencySample, 6U> samples{
      calibration::DiscoveryResidencySample{{Phase::warmup, Moment::before, 0U, 0U},
                                            queries[0U]},
      calibration::DiscoveryResidencySample{{Phase::warmup, Moment::during, 0U, 0U},
                                            queries[1U]},
      calibration::DiscoveryResidencySample{{Phase::warmup, Moment::after, 0U, 0U},
                                            queries[2U]},
      calibration::DiscoveryResidencySample{
          {Phase::measurement, Moment::before, 0U, 0U}, queries[3U]},
      calibration::DiscoveryResidencySample{
          {Phase::measurement, Moment::during, 0U, 0U}, queries[4U]},
      calibration::DiscoveryResidencySample{{Phase::measurement, Moment::after, 0U, 0U},
                                            queries[5U]}};
  const std::array<calibration::DiscoveryResidencyRegion, 1U> regions{{{mapping, 1U}}};
  cpu_prefetch::test_support::DiscoveryTestClock clock;
  cpu_prefetch::test_support::DiscoveryTestRelax relax;
  struct Query final {
    auto query_pages(std::span<void* const>, std::span<int> status) const noexcept
        -> platform::PageResidencyQueryResult {
      for (auto& node : status) {
        node = 1;
      }
      return {0, 0};
    }
  } query;
  auto plan = cpu_prefetch::test_support::kDiscoveryTestPlan;
  calibration::PreparedDiscoveryResidencyObserver observer(
      plan, calibration::DiscoveryResidencyControls{4096U, 10U}, regions, samples,
      clock, query, relax);
  const std::atomic<std::uint32_t> finished{0U};
  const auto before = allocation_count.load(std::memory_order_relaxed);
  bool valid = true;
  for (const auto phase : {Phase::warmup, Phase::measurement}) {
    valid = observer.before_phase(phase) && valid;
    const auto origin = clock.read();
    valid = observer.during_phase(
                phase, {origin.sample.relative_picoseconds, plan.warmup_duration_ticks},
                finished) &&
            valid;
    valid = observer.after_phase(phase) && valid;
  }
  const auto after = allocation_count.load(std::memory_order_relaxed);
  EXPECT_TRUE(valid);
  EXPECT_EQ(after, before);
  for (const auto& sample : samples) {
    EXPECT_EQ(sample.stop, calibration::DiscoveryResidencyStop::sampled);
    EXPECT_TRUE(sample.query.has_value());
  }
}

} // namespace
