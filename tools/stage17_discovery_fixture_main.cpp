// Software-only cross-language test tool. Never a native worker or release probe.
// Real R0 backend/session/codec/publisher; injected clock and scheduling only.
#include "cpu_prefetch/runner/stage17_discovery_publication.hpp"

#include <atomic>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
#include <thread>

namespace {
using namespace cpu_prefetch;
namespace stage17 = runner::stage17;
using Value = protocol::json::Value;

auto member(const Value& value, std::string_view name) -> const Value& {
  if (value.as_object() == nullptr)
    throw std::invalid_argument("fixture input is not an object");
  return value.as_object()->at(std::string(name));
}
auto text(const Value& value) -> std::string {
  if (value.as_string() == nullptr)
    throw std::invalid_argument("fixture requires string");
  return *value.as_string();
}
auto number(const Value& value) -> std::uint64_t {
  const auto* n = value.as_number();
  if (n != nullptr) {
    if (const auto* u = std::get_if<std::uint64_t>(&n->value))
      return *u;
    if (const auto* s = std::get_if<std::int64_t>(&n->value); s != nullptr && *s >= 0)
      return static_cast<std::uint64_t>(*s);
  }
  throw std::invalid_argument("fixture requires unsigned integer");
}
auto run_id(const Value& capture, std::string_view phase) -> protocol::RunId {
  auto parsed = protocol::RunId::parse(text(member(member(capture, phase), "run_id")),
                                       "$fixture/run_id");
  if (!parsed)
    throw std::invalid_argument("fixture invalid run ID");
  return std::move(parsed).value();
}
auto bounded(const Value& object, std::string_view name, std::uint64_t maximum)
    -> std::uint64_t {
  const auto value = number(member(object, name));
  if (value == 0U || value > maximum)
    throw std::invalid_argument("fixture software resource bound exceeded");
  return value;
}

struct PhaseCapacity final {
  std::uint64_t attempts;
  std::size_t drain_rows;
};

// Cold fixture storage: declaration order preserves reference/span lifetimes.
// NOLINTNEXTLINE(clang-analyzer-optin.performance.Padding)
struct Phase final {
  protocol::RunId id;
  storage::ProducerObservationStream producer_stream;
  storage::ConsumerObservationStream consumer_stream;
  std::vector<std::uint64_t> pd, pi, cd, ci;
  calibration::CallerOwnedRingDemandWorker producer_worker, consumer_worker;
  calibration::CallerOwnedRingDemandTrace trace;
  std::vector<calibration::DiscoveryConsumerEventCapture> drain_rows;
  calibration::MappedProducerPhase producer;
  calibration::MappedConsumerPhase consumer;

  Phase(protocol::RunId identity, PhaseCapacity capacity)
      : id(std::move(identity)), producer_stream(id, capacity.attempts),
        consumer_stream(id, capacity.attempts), pd(capacity.attempts),
        pi(capacity.attempts), cd(capacity.attempts), ci(capacity.attempts),
        producer_worker(calibration::RingWorker::producer, pd, pi),
        consumer_worker(calibration::RingWorker::consumer, cd, ci),
        trace(producer_worker, consumer_worker), drain_rows(capacity.drain_rows),
        producer(trace, producer_stream, storage::make_row_layout(id.value())),
        consumer(trace, consumer_stream, storage::make_row_layout(id.value()), {17U},
                 drain_rows) {}
};

struct Preparation final {
  Phase warmup, measurement;
  workload::EventArena event_arena;
  queue::RingSpscQueue queue;
  Preparation(const Value& capture, const calibration::DiscoverySessionPlan& plan)
      : warmup(run_id(capture, "warmup"),
               {plan.warmup_attempt_capacity, plan.drain_attempt_capacity}),
        measurement(run_id(capture, "measurement"),
                    {plan.measurement_attempt_capacity, plan.drain_attempt_capacity}),
        event_arena({bounded(member(capture, "geometry"), "capacity", 4096U),
                     bounded(member(capture, "geometry"), "cache_line_bytes", 4096U),
                     bounded(member(capture, "geometry"), "base_page_bytes", 65536U),
                     workload::MasterSeed::from_hex(
                         text(member(member(capture, "arena_seed"), "seed_hex"))),
                     text(member(member(capture, "arena_seed"), "namespace_id"))}),
        queue({event_arena.capacity()}, {event_arena.cache_line_bytes()}) {}
  auto prepare_producer() const noexcept -> bool { return true; }
  auto prepare_consumer() const noexcept -> bool { return true; }
  auto producer_phase(bool warm) noexcept -> calibration::MappedProducerPhase& {
    return warm ? warmup.producer : measurement.producer;
  }
  auto consumer_phase(bool warm) noexcept -> calibration::MappedConsumerPhase& {
    return warm ? warmup.consumer : measurement.consumer;
  }
  auto arena() const noexcept -> const workload::EventArena& { return event_arena; }
  auto ring() noexcept -> queue::RingSpscQueue& { return queue; }
};

class SyntheticClock final {
public:
  static constexpr std::uint64_t absolute_origin = 10'000'000U;
  std::atomic<std::uint64_t> step_ns{1U};
  std::atomic<std::uint64_t> deadline_ticks{0U};
  auto read() noexcept -> timing::ClockReadResult {
    const auto step = step_ns.load();
    const auto ns = now_.fetch_add(step) + step;
    return {timing::ClockReadStatus::ok, {absolute_origin + ns, ns * 1000U}};
  }
  void reach_deadline() noexcept {
    const auto target = deadline_ticks.load() / 1000U;
    auto previous = now_.load();
    while (previous < target && !now_.compare_exchange_weak(previous, target)) {
    }
  }

private:
  std::atomic<std::uint64_t> now_{0U};
};

struct Relax final {
  void relax() const noexcept { std::this_thread::yield(); }
};

// These scheduling waits model preemption between the worker admission clock
// and event invocation. They are deliberately outside the real event backend.
// No test-tool machine code is evidence for production measured-loop codegen.
class ScheduledBackend final {
  using Base = calibration::DiscoveryRingPhaseBackend<SyntheticClock, Preparation>;

public:
  ScheduledBackend(calibration::DiscoverySessionPlan plan, SyntheticClock& clock,
                   Preparation& preparation, std::string_view mode,
                   std::atomic<bool>& measurement_stop)
      : backend_(plan, clock, preparation), clock_(clock), mode_(mode),
        measurement_stop_(measurement_stop) {}
  auto prepare_producer() -> bool { return backend_.prepare_producer(); }
  auto prepare_consumer() -> bool { return backend_.prepare_consumer(); }
  auto reset_producer() noexcept -> bool { return backend_.reset_producer(); }
  auto reset_consumer() noexcept -> bool { return backend_.reset_consumer(); }
  auto ring() noexcept -> queue::RingSpscQueue& { return backend_.ring(); }
  auto validate_warmup(
      const std::array<calibration::DiscoveryWorkerResult, 2U>& workers) noexcept
      -> bool {
    return backend_.validate_warmup(workers);
  }
  auto validate_measurement(
      const std::array<calibration::DiscoveryWorkerResult, 2U>& workers) noexcept
      -> bool {
    return backend_.validate_measurement(workers);
  }
  auto drain_warmup(calibration::DiscoveryDrainWindow window) noexcept
      -> calibration::DiscoveryDrainResult {
    return backend_.drain_warmup(window);
  }
  auto drain_measurement(calibration::DiscoveryDrainWindow window) noexcept
      -> calibration::DiscoveryDrainResult {
    return backend_.drain_measurement(window);
  }
  auto warmup_producer_attempt(std::uint64_t tick) noexcept
      -> calibration::RingCaptureResult {
    const auto result = backend_.warmup_producer_attempt(tick);
    if (result.operation_outcome == calibration::RingAttemptOutcome::advanced)
      advanced(0U);
    return result;
  }
  auto measurement_producer_attempt(std::uint64_t tick) noexcept
      -> calibration::RingCaptureResult {
    const auto result = backend_.measurement_producer_attempt(tick);
    if (result.operation_outcome == calibration::RingAttemptOutcome::advanced)
      advanced(1U);
    return result;
  }
  auto warmup_consumer_attempt() noexcept -> calibration::RingCaptureResult {
    return consume(true);
  }
  auto measurement_consumer_attempt() noexcept -> calibration::RingCaptureResult {
    return consume(false);
  }

private:
  void advanced(std::size_t phase) noexcept {
    if (produced_[phase].fetch_add(1U) == 1U) {
      for (std::uint64_t poll = 0U; poll < 1'000'000U; ++poll) {
        if (consumer_entered_[phase].load())
          break;
        std::this_thread::yield();
      }
    }
  }
  auto consume(bool warm) noexcept -> calibration::RingCaptureResult {
    consumer_entered_[warm ? 0U : 1U].store(true);
    for (std::uint64_t poll = 0U; poll < 1'000'000U; ++poll) {
      if (produced_[warm ? 0U : 1U].load() >= 2U &&
          clock_.deadline_ticks.load() != 0U &&
          (warm || mode_ != "capacity" || measurement_stop_.load())) {
        if (!warm && mode_ == "crossing")
          clock_.reach_deadline();
        const auto result = warm ? backend_.warmup_consumer_attempt()
                                 : backend_.measurement_consumer_attempt();
        // Preserve pending real events for the ordinary bounded drain.
        if (warm || mode_ != "capacity")
          clock_.reach_deadline();
        return result;
      }
      std::this_thread::yield();
    }
    return {calibration::RingAttemptOutcome::trace_failure, std::nullopt, std::nullopt,
            std::nullopt, false};
  }
  Base backend_;
  SyntheticClock& clock_;
  std::string_view mode_;
  std::atomic<bool>& measurement_stop_;
  std::array<std::atomic<std::uint64_t>, 2U> produced_{};
  std::array<std::atomic<bool>, 2U> consumer_entered_{};
};

struct Observer final {
  SyntheticClock& clock;
  calibration::DiscoverySessionPlan plan;
  auto before_phase(calibration::DiscoverySessionPhase phase) noexcept -> bool {
    const auto duration = phase == calibration::DiscoverySessionPhase::warmup
                              ? plan.warmup_duration_ticks
                              : plan.measurement_duration_ticks;
    clock.deadline_ticks.store(0U);
    clock.step_ns.store(std::max(std::uint64_t{1U}, duration / 1'000'000U));
    return true;
  }
  auto during_phase(calibration::DiscoverySessionPhase,
                    calibration::DiscoveryObservationWindow window,
                    const std::atomic<std::uint32_t>&) noexcept -> bool {
    clock.deadline_ticks.store(window.origin_ticks + window.duration_ticks);
    return true;
  }
  auto after_phase(calibration::DiscoverySessionPhase) noexcept -> bool {
    clock.step_ns.store(1U);
    return true;
  }
};

void write(const std::filesystem::path& path, std::span<const std::byte> bytes) {
  if (std::filesystem::exists(path))
    throw std::invalid_argument("fixture refuses existing output");
  std::ofstream output(path, std::ios::binary);
  output.write(reinterpret_cast<const char*>(bytes.data()),
               static_cast<std::streamsize>(bytes.size()));
  if (!output)
    throw std::runtime_error("fixture output failed");
}
void write_json(const std::filesystem::path& path, const Value& value) {
  auto encoded = protocol::json::canonicalize(value);
  if (!encoded)
    throw std::runtime_error("fixture JSON encoding failed");
  write(path, std::as_bytes(std::span(encoded.value())));
}
class Sink final : public stage17::ArtifactSink {
public:
  explicit Sink(std::filesystem::path root) : root_(std::move(root)) {}
  auto publish(stage17::ArtifactPayload value)
      -> protocol::Result<stage17::ArtifactBinding> override {
    write(root_ / value.file_name, value.bytes);
    return protocol::Result<stage17::ArtifactBinding>::success(
        {value.role, value.schema_identity, value.media_type, value.file_name,
         value.bytes.size(), workload::sha256(value.bytes).hex()});
  }

private:
  std::filesystem::path root_;
};

auto run(int argc, char** argv) -> int {
  if (argc != 4 || (std::string_view(argv[3]) != "normal" &&
                    std::string_view(argv[3]) != "crossing" &&
                    std::string_view(argv[3]) != "capacity"))
    throw std::invalid_argument(
        "usage: fixture capture.json output-directory normal|crossing|capacity");
  std::ifstream input(argv[1]);
  const std::string bytes{std::istreambuf_iterator<char>(input), {}};
  if (bytes.size() > 65536U)
    throw std::invalid_argument("fixture input too large");
  auto parsed = protocol::json::parse(bytes);
  if (!parsed)
    throw std::invalid_argument("fixture input invalid JSON");
  const auto& capture = parsed.value();
  const auto& budget = member(capture, "budget");
  const calibration::DiscoverySessionPlan plan{
      bounded(capture, "warmup_ns", 10'000'000'000U) * 1000U,
      bounded(capture, "measurement_ns", 10'000'000'000U) * 1000U,
      bounded(budget, "warmup_attempt_capacity", 4096U),
      bounded(budget, "measurement_attempt_capacity", 4096U),
      bounded(budget, "drain_ns", 10'000'000'000U) * 1000U,
      bounded(budget, "drain_attempt_capacity", 4097U),
      bounded(budget, "barrier_poll_limit", 1'000'000U)};
  Preparation preparation(capture, plan);
  SyntheticClock clock;
  Relax relax;
  Observer observer{clock, plan};
  calibration::DiscoverySessionStorage session_storage;
  calibration::StandardDiscoveryThreads threads;
  ScheduledBackend backend(plan, clock, preparation, argv[3],
                           session_storage.measurement_stop);
  calibration::NativeDiscoveryCaptureResult result;
  result.session = calibration::run_discovery_session(
      plan, clock, backend, relax, observer, threads, session_storage);
  result.clock_origin = timing::AbsoluteClockReadResult{
      timing::ClockReadStatus::ok, SyntheticClock::absolute_origin};
  // No native capture ran: preserve not_started and absent native hardware facts.
  const calibration::NativeDiscoveryCaptureLayout layout{};
  const platform::PrefetchReadbackPreparation hardware{};
  const calibration::NativeDiscoveryPublicationView view{
      result,
      layout,
      {},
      {},
      {},
      {},
      {},
      hardware,
      {},
      {&preparation.warmup.producer, &preparation.measurement.producer},
      {&preparation.warmup.consumer, &preparation.measurement.consumer},
      {},
      {},
      &preparation.event_arena};
  const std::filesystem::path root(argv[2]);
  std::filesystem::create_directories(root);
  Sink sink(root);
  result.publication_attempted = true;
  const auto published = stage17::publish_discovery_capture(
      sink, number(member(capture, "ordinal")), view);
  result.publication_succeeded = static_cast<bool>(published);
  write_json(root / "fixture-final-result.json",
             stage17::discovery_capture_result_json(result));
  write_json(root / "fixture-scope.json",
             Value(Value::Object{{"synthetic", Value(true)},
                                 {"execution_authority", Value(false)},
                                 {"hardware_claim", Value(false)},
                                 {"mode", Value(std::string(argv[3]))}}));
  const auto expected_stop = std::string_view(argv[3]) == "capacity"
                                 ? calibration::DiscoverySessionStop::trace_capacity
                                 : calibration::DiscoverySessionStop::complete;
  if (!published || result.session->stop != expected_stop)
    throw std::runtime_error("software session/publication did not complete");
  return 0;
}
} // namespace

auto main(int argc, char** argv) -> int {
  try {
    return run(argc, argv);
  } catch (const std::exception& error) {
    std::cerr << "software discovery fixture: " << error.what() << '\n';
    return 1;
  }
}
