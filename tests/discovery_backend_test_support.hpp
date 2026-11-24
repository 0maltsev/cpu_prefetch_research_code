#ifndef CPU_PREFETCH_TESTS_DISCOVERY_BACKEND_TEST_SUPPORT_HPP
#define CPU_PREFETCH_TESTS_DISCOVERY_BACKEND_TEST_SUPPORT_HPP

#include "cpu_prefetch/calibration/caller_owned_trace.hpp"
#include "cpu_prefetch/calibration/discovery_ring_backend.hpp"

#include <array>
#include <atomic>
#include <limits>
#include <stdexcept>
#include <string>
#include <thread>

namespace cpu_prefetch::test_support {

inline auto discovery_test_run_id(std::string text) -> protocol::RunId {
  auto parsed = protocol::RunId::parse(std::move(text), "$test/run_id");
  if (!parsed) {
    throw std::logic_error("invalid test run ID");
  }
  return std::move(parsed).value();
}

class DiscoveryTestClock final {
public:
  auto read() noexcept -> timing::ClockReadResult {
    const auto tick = next_.fetch_add(1U, std::memory_order_relaxed) + 1U;
    return {tick == fail_at_.load(std::memory_order_relaxed)
                ? timing::ClockReadStatus::call_failed
                : timing::ClockReadStatus::ok,
            {tick, 1000U * tick}};
  }
  void fail_after_reads(std::uint64_t successful_reads) noexcept {
    fail_at_.store(next_.load(std::memory_order_relaxed) + successful_reads + 1U,
                   std::memory_order_relaxed);
  }

private:
  std::atomic<std::uint64_t> next_{0U};
  std::atomic<std::uint64_t> fail_at_{std::numeric_limits<std::uint64_t>::max()};
};

template <std::size_t Capacity> struct DiscoveryTestPhase final {
  alignas(64) std::array<std::byte, Capacity * 256U> producer_bytes{};
  alignas(64) std::array<std::byte, Capacity * 256U> consumer_bytes{};
  storage::ProducerObservationStream producer_stream;
  storage::ConsumerObservationStream consumer_stream;
  protocol::RunId id;
  storage::RowLayout layout;
  std::array<std::uint64_t, Capacity> producer_demand{};
  std::array<std::uint64_t, Capacity> producer_issue{};
  std::array<std::uint64_t, Capacity> consumer_demand{};
  std::array<std::uint64_t, Capacity> consumer_issue{};
  calibration::CallerOwnedRingDemandWorker producer_worker{
      calibration::RingWorker::producer, producer_demand, producer_issue};
  calibration::CallerOwnedRingDemandWorker consumer_worker{
      calibration::RingWorker::consumer, consumer_demand, consumer_issue};
  calibration::CallerOwnedRingDemandTrace trace{producer_worker, consumer_worker};
  std::array<calibration::DiscoveryConsumerEventCapture, 9U> drain_rows{};
  calibration::DiscoveryProducerPhase<calibration::CallerOwnedRingDemandTrace> producer;
  calibration::DiscoveryConsumerPhase<calibration::CallerOwnedRingDemandTrace> consumer;

  explicit DiscoveryTestPhase(std::string identity)
      : DiscoveryTestPhase(discovery_test_run_id(std::move(identity))) {}
  ~DiscoveryTestPhase() = default;

private:
  explicit DiscoveryTestPhase(protocol::RunId identity)
      : producer_stream(identity, Capacity,
                        std::span(producer_bytes)
                            .first(storage::raw_stream_storage_requirements(
                                       identity, Capacity, Capacity)
                                       .producer_bytes)),
        consumer_stream(identity, Capacity,
                        std::span(consumer_bytes)
                            .first(storage::raw_stream_storage_requirements(
                                       identity, Capacity, Capacity)
                                       .consumer_bytes)),
        id(std::move(identity)), layout(storage::make_row_layout(id.value())),
        producer(trace, producer_stream, layout),
        consumer(trace, consumer_stream, layout, {17U}, drain_rows) {}
};

// Software-only storage/provider: these arrays carry no affinity, residency,
// hardware qualification or execution authority. Real queue and codec only.
template <std::size_t Capacity, std::size_t MeasurementCapacity = Capacity>
class SoftwareOnlyDiscoveryPreparation final {
public:
  DiscoveryTestPhase<Capacity> warmup{"discovery-test-warmup"};
  DiscoveryTestPhase<MeasurementCapacity> measurement{"discovery-test-measurement"};
  workload::EventArena event_arena{
      {8U, 64U, 4096U, workload::MasterSeed::from_hex(std::string(64U, '0')),
       "discovery-backend-software-test"}};
  queue::RingSpscQueue queue{{8U}, {64U}};
  std::thread::id producer_owner;
  std::thread::id consumer_owner;
  bool reject_producer{false};
  bool reject_consumer_reset{false};

  auto prepare_producer() -> bool {
    producer_owner = std::this_thread::get_id();
    return !reject_producer;
  }
  auto prepare_consumer() -> bool {
    consumer_owner = std::this_thread::get_id();
    return true;
  }
  auto producer_phase(bool is_warmup) noexcept
      -> calibration::DiscoveryProducerPhase<calibration::CallerOwnedRingDemandTrace>& {
    return is_warmup ? warmup.producer : measurement.producer;
  }
  auto consumer_phase(bool is_warmup) noexcept
      -> calibration::DiscoveryConsumerPhase<calibration::CallerOwnedRingDemandTrace>& {
    return is_warmup ? warmup.consumer : measurement.consumer;
  }
  auto arena() const noexcept -> const workload::EventArena& { return event_arena; }
  auto ring() noexcept -> queue::RingSpscQueue& { return queue; }
  auto before_measurement_producer() const noexcept -> bool {
    return producer_owner == std::this_thread::get_id();
  }
  auto before_measurement_consumer() const noexcept -> bool {
    return !reject_consumer_reset && consumer_owner == std::this_thread::get_id();
  }
};

struct DiscoveryTestRelax final {
  void relax() const noexcept { std::this_thread::yield(); }
};

inline constexpr calibration::DiscoverySessionPlan kDiscoveryTestPlan{
    20'000'000U, 20'000'000U, 20'000U, 20'000U, 1'000'000U, 9U, 1'000'000U};

} // namespace cpu_prefetch::test_support

#endif
