// Software-only serializer bridge. Real R0 capture/streams/arena/publisher;
// scripted clock/lifecycle and typed synthetic platform observations. Never a
// production worker, native hardware capture, or qualification artifact.
#include "cpu_prefetch/runner/software_prefetch.hpp"
#include "cpu_prefetch/runner/stage17_formal_ring_publication.hpp"
#include "cpu_prefetch/runner/stage17_formal_scheduled_publication.hpp"
#include "cpu_prefetch/runner/stage17_formal_service_publication.hpp"

#include <algorithm>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <memory>
#include <sstream>

namespace {
using namespace cpu_prefetch;
namespace c = calibration;
namespace p = platform;
namespace s = storage;
namespace stage = runner::stage17;
using Value = protocol::json::Value;
using Object = Value::Object;
constexpr std::uint64_t kOrigin = 1'000'000U;
constexpr std::size_t kPage = 4096U;
constexpr std::uint64_t kRows = 16U;
constexpr std::string_view kMapping = "INTEL-06_3EH-MSR-1A4-DISABLE-0_3-v1";

void require(bool value, const char* message) {
  if (!value)
    throw std::runtime_error(message);
}
auto at(const Value& value, std::string_view key) -> const Value& {
  require(value.as_object() != nullptr, "fixture object required");
  return value.as_object()->at(std::string(key));
}
auto number(const Value& value) -> std::uint64_t {
  const auto* n = value.as_number();
  require(n != nullptr && n->kind == protocol::json::Number::Kind::unsigned_integer,
          "fixture unsigned integer required");
  return std::get<std::uint64_t>(n->value);
}
auto text(const Value& value) -> const std::string& {
  require(value.as_string() != nullptr && value.as_string()->size() <= 256U,
          "fixture bounded text required");
  return *value.as_string();
}
auto array(const Value& value, std::size_t count) -> const Value::Array& {
  require(value.as_array() != nullptr && value.as_array()->size() == count,
          "fixture array size differs");
  return *value.as_array();
}
auto integer(std::uint64_t n) -> Value {
  return Value(protocol::json::Number{protocol::json::Number::Kind::unsigned_integer,
                                      std::to_string(n), n});
}
auto sample(std::uint64_t tick) -> timing::ClockSample {
  require(tick % 1000U == 0U, "fixture clock precision");
  return {kOrigin + tick / 1000U, tick};
}
auto clock_at(std::uint64_t tick) -> timing::ClockReadResult {
  return {timing::ClockReadStatus::ok, sample(tick)};
}
auto call(std::int64_t n = 0) -> p::LinuxCallResult { return {n, 0}; }
void write(const std::filesystem::path& path, std::span<const std::byte> bytes) {
  require(!std::filesystem::exists(path), "fixture output already exists");
  std::ofstream file(path, std::ios::binary);
  file.exceptions(std::ios::badbit | std::ios::failbit);
  file.write(reinterpret_cast<const char*>(bytes.data()),
             static_cast<std::streamsize>(bytes.size()));
}
void write_json(const std::filesystem::path& path, const Value& value) {
  auto encoded = protocol::json::canonicalize(value);
  require(static_cast<bool>(encoded), "fixture JSON canonicalization failed");
  write(path, std::as_bytes(std::span(encoded.value())));
}
class Sink final : public stage::ArtifactSink {
public:
  explicit Sink(std::filesystem::path root) : root_(std::move(root)) {}
  auto publish(stage::ArtifactPayload value)
      -> protocol::Result<stage::ArtifactBinding> override {
    write(root_ / value.file_name, value.bytes);
    return protocol::Result<stage::ArtifactBinding>::success(
        {value.role, value.schema_identity, value.media_type, value.file_name,
         value.bytes.size(), workload::sha256(value.bytes).hex()});
  }

private:
  std::filesystem::path root_;
};
struct Clock final {
  auto origin() const noexcept -> timing::ClockOrigin { return {kOrigin}; }
  std::uint64_t next{100'000U};
  auto read() noexcept -> timing::ClockReadResult {
    const auto tick = next;
    next += 1000U;
    return {timing::ClockReadStatus::ok, {kOrigin + tick / 1000U, tick}};
  }
};
struct Phase final {
  protocol::RunId id;
  s::ProducerObservationStream producer_stream;
  s::ConsumerObservationStream consumer_stream;
  queue::detail::AlignedBlock producer_bytes;
  queue::detail::AlignedBlock consumer_bytes;
  c::RingDemandStream producer_demand;
  c::RingDemandStream consumer_demand;
  c::FormalRingProducerPhase producer;
  c::FormalRingConsumerPhase consumer;
  explicit Phase(const std::string& name)
      : id(protocol::RunId::parse(name, "$fixture").value()),
        producer_stream(id, kRows), consumer_stream(id, kRows),
        producer_bytes(c::ring_demand_storage_requirements(id, kRows), 64U),
        consumer_bytes(c::ring_demand_storage_requirements(id, kRows), 64U),
        producer_demand(id, c::RingWorker::producer, kRows,
                        {producer_bytes.data(), producer_bytes.size()}),
        consumer_demand(id, c::RingWorker::consumer, kRows,
                        {consumer_bytes.data(), consumer_bytes.size()}),
        producer{producer_demand, producer_stream, s::make_row_layout(id.value()), {}},
        consumer{consumer_demand, consumer_stream, s::make_row_layout(id.value()),
                 {17U},           {17U},           {}} {}
};
struct Preparation final {
  Phase warmup;
  Phase measurement;
  workload::EventArena records;
  queue::RingSpscQueue queue;
  explicit Preparation(const Value& capture)
      : warmup(text(at(at(capture, "warmup"), "run_id"))),
        measurement(text(at(at(capture, "measurement"), "run_id"))),
        records(
            {static_cast<std::size_t>(number(at(at(capture, "geometry"), "capacity"))),
             64U, kPage,
             workload::MasterSeed::from_hex(
                 text(at(at(capture, "arena_seed"), "seed_hex"))),
             text(at(at(capture, "arena_seed"), "namespace_id"))}),
        queue(
            {static_cast<std::size_t>(number(at(at(capture, "geometry"), "capacity")))},
            {64U}) {}
  auto prepare_producer() const noexcept -> bool { return true; }
  auto prepare_consumer() const noexcept -> bool { return true; }
  auto before_measurement_producer() const noexcept -> bool { return true; }
  auto before_measurement_consumer() const noexcept -> bool { return true; }
  auto producer_phase(bool first) noexcept -> c::FormalRingProducerPhase& {
    return first ? warmup.producer : measurement.producer;
  }
  auto consumer_phase(bool first) noexcept -> c::FormalRingConsumerPhase& {
    return first ? warmup.consumer : measurement.consumer;
  }
  auto arena() const noexcept -> const workload::EventArena& { return records; }
  auto ring() noexcept -> queue::RingSpscQueue& { return queue; }
};

// Executes actual event capture and quiescent joins/reset, without pretending
// that this scripted single-thread driver exercised the native owner lifecycle.
auto run_script(Preparation& preparation, std::uint64_t duration)
    -> c::ServiceSessionResult {
  c::ServiceSessionPlan plan{{{{5'000'000'000'000U, kRows, kRows, 1'000'000'000U},
                               {duration, kRows, kRows, 1'000'000'000U}}},
                             1000U};
  Clock clock;
  c::FormalRingSessionBackend backend(plan, clock, preparation);
  c::ServiceSessionResult result;
  result.clock_origin = timing::ClockOrigin{kOrigin};
  result.prepared = {backend.prepare_producer(), backend.prepare_consumer()};
  require(result.prepared[0U] && result.prepared[1U], "software stream preparation");
  for (std::size_t i = 0U; i < 2U; ++i) {
    const auto selected =
        i == 0U ? c::ServicePhase::warmup : c::ServicePhase::measurement;
    const auto begin = i == 0U ? 100'000U : 5'000'001'000'000U;
    const auto end = begin + plan.phases[i].duration_ticks;
    auto& state = result.phases[i];
    state.origin_status = timing::ClockReadStatus::ok;
    state.observed_origin = begin;
    state.origin_sample = sample(begin);
    state.window = c::service_window(begin, plan.phases[i]);
    state.released = state.before_observed = state.during_observed =
        state.after_observed = true;
    auto& phase = backend.phase(selected);
    for (std::uint64_t n = 0U; n < 4U; ++n) {
      clock.next = begin + 1000U + n * 20'000U;
      const auto offered = phase.try_producer_attempt({n, clock.next, n});
      require(offered.status == lifecycle::AttemptStatus::complete &&
                  offered.outcome == queue::EnqueueResult::accepted,
              "software enqueue");
      if (n == 3U)
        clock.next = end + 200'000U;
      const auto consumed = phase.try_consumer_poll(n);
      require(consumed.status == lifecycle::ConsumerPollStatus::item,
              "software consume");
    }
    clock.next = end + 210'000U;
    require(phase.try_consumer_poll(4U).status == lifecycle::ConsumerPollStatus::empty,
            "software terminal empty");
    state.producer = {timing::ClockReadStatus::ok, end, 4U, 4U, 0U, true, true};
    state.consumer = {timing::ClockReadStatus::ok, end + 220'000U, 4U, 5U, 1U, true};
    state.drain_checkpoint = clock_at(end + 400'000U);
    state.validated = backend.validate_quiescent(selected, state);
    require(state.validated, "software quiescent primary join");
    if (i == 0U) {
      result.private_reset = {backend.reset_producer(), backend.reset_consumer()};
      result.queue_reset = backend.reset_quiescent();
      require(result.private_reset[0U] && result.private_reset[1U] &&
                  result.queue_reset,
              "software reset");
    }
  }
  backend.finalize_joined();
  result.stop = c::ServiceSessionStop::complete;
  return result;
}

auto owner(std::uint32_t cpu, int tid) -> p::OwnerThreadObservation {
  return {call(), call(cpu), call(tid), call(), 0, 0, 1, true};
}
auto mapping(p::OwnerMappingPlan plan, std::byte* address, int tid)
    -> p::OwnerMappingEvidence {
  p::OwnerMappingEvidence result{};
  result.requested = plan;
  result.base_page_bytes = call(kPage);
  result.mapping = p::LinuxMappingResult{address, 0};
  result.binding = result.no_huge_pages = result.affinity_request = result.lock =
      result.read_only = call();
  result.before_touch = result.after_touch = owner(plan.owner_cpu, tid);
  result.prefaulted_pages = plan.bytes / kPage;
  result.stop = p::OwnerMappingStop::ready;
  return result;
}
auto stack(p::OwnerMappingPlan plan, std::byte* address, int tid)
    -> p::WorkerStackEvidence {
  p::WorkerStackEvidence result{};
  result.requested = plan;
  result.base_page_bytes = result.minimum_stack_bytes = call(kPage);
  result.mapping = p::LinuxMappingResult{address, 0};
  result.binding = result.no_huge_pages = result.guard = result.populate = result.lock =
      call();
  result.before_populate = result.after_populate = owner(plan.owner_cpu, tid);
  result.thread = {0, 0, 0, 0, 0, 0, 0};
  result.stop = p::WorkerStackStop::ready;
  return result;
}
struct ThreadIdentity final {
  int tid;
  std::uint32_t cpu;
};
struct ThreadEvidence final {
  std::array<char, kPage> stat{};
  std::array<char, kPage> status{};
  std::array<unsigned long, 1U> mask{};
  p::ThreadMonitorScratch scratch;
  p::ThreadControlSample observed;
  explicit ThreadEvidence(ThreadIdentity identity) : scratch{stat, status, stat, mask} {
    const auto [tid, cpu] = identity;
    std::array<std::string, 50U> fields;
    fields.fill("0");
    fields[0U] = "R";
    fields[7U] = "10";
    fields[19U] = "1234";
    fields[36U] = std::to_string(cpu);
    std::string raw = std::to_string(tid) + " (test (thread))";
    for (const auto& field : fields)
      raw += " " + field;
    raw += "\n";
    const auto status_text =
        "Pid:\t" + std::to_string(tid) +
        "\nTgid:\t100\nvoluntary_ctxt_switches:\t3\nnonvoluntary_ctxt_switches:\t4\n";
    require(raw.size() < stat.size() && status_text.size() < status.size(),
            "thread fixture extent");
    std::copy(raw.begin(), raw.end(), stat.begin());
    std::copy(status_text.begin(), status_text.end(), status.begin());
    observed.stat_before_read = observed.stat_after_read = {
        call(static_cast<std::int64_t>(raw.size())), call(), {}, true};
    observed.status_read = {
        call(static_cast<std::int64_t>(status_text.size())), call(), {}, true};
    observed.stat_before = observed.stat_after = p::parse_thread_stat(raw);
    observed.status = p::parse_thread_status(status_text);
    require(observed.stat_before.has_value() && observed.status.has_value(),
            "fixture proc parsing");
    mask[0U] = 1UL << cpu;
    observed.affinity_call = call(sizeof(unsigned long));
    observed.affinity_mask = mask;
    observed.affinity_cpu_count = 1U;
    observed.singleton_affinity_cpu = cpu;
    observed.stop = p::ThreadMonitorStop::sampled;
  }
};
class Files final : public p::FileSnapshotOperations {
public:
  std::string contents;
  auto open_file(const char*, int) noexcept -> p::LinuxCallResult override {
    return call(42);
  }
  auto read_at(int, std::span<std::byte> bytes, std::size_t offset) noexcept
      -> p::LinuxCallResult override {
    if (offset > contents.size())
      return {-1, EINVAL};
    const auto count = std::min(bytes.size(), contents.size() - offset);
    std::copy_n(reinterpret_cast<const std::byte*>(contents.data() + offset), count,
                bytes.data());
    return call(static_cast<std::int64_t>(count));
  }
  auto close_file(int) noexcept -> p::LinuxCallResult override { return call(); }
};
struct Evidence final {
  std::array<std::unique_ptr<queue::detail::AlignedBlock>, 7U> allocations;
  std::array<c::DiscoveryResidencyRegion, 7U> regions{};
  std::array<p::OwnerMappingEvidence, 3U> maps{};
  std::array<p::WorkerStackEvidence, 2U> stacks{};
  p::OwnerMappingEvidence core{};
  p::OwnerMappingEvidence monitor{};
  p::WorkerStackEvidence controller{};
  std::array<p::ThreadTlsModule, 6U> modules{};
  std::array<p::ThreadTlsSnapshot, 6U> tls{};
  p::PrefetchReadbackPreparation hardware{};
  std::array<p::ThreadMonitorPreparation, 2U> preparation{};
  std::vector<std::unique_ptr<ThreadEvidence>> threads;
  std::array<c::DiscoveryControlSample, 6U> controls{};
  std::vector<std::vector<void*>> addresses;
  std::vector<std::vector<int>> nodes;
  std::vector<std::unique_ptr<p::PreparedPageResidencyQuery>> queries;
  std::vector<c::DiscoveryResidencySample> residency;
  Files files;
  p::PreparedFileSnapshot reader{files};
  std::array<char, 17U> frozen_path{};
  std::array<std::vector<std::byte>, 6U> file_bytes;
  std::array<std::vector<p::FileSnapshotRead>, 6U> file_reads;
  std::array<p::FileSnapshotSample, 6U> samples{};
  std::array<p::FileSnapshotPreparation, 1U> file_preparations{};
  c::NativeFormalRingCaptureLayout layout{};

  template <typename Backend>
  Evidence(const Value& input, const Backend& backend,
           const c::ServiceSessionResult& session) {
    const auto& resources = at(input, "resources");
    const auto& monitoring = at(input, "monitoring");
    const auto& sizes = array(at(resources, "region_bytes"), 7U);
    for (std::size_t i = 0U; i < 7U; ++i) {
      const auto bytes = static_cast<std::size_t>(number(sizes[i]));
      require(bytes > 0U && bytes <= 65536U && bytes % kPage == 0U,
              "bounded fixture region");
      layout.region_bytes[i] = bytes;
      if (i == 0U)
        regions[i] = {
            {const_cast<std::byte*>(backend.records.storage_address()), bytes}, 0U};
      else {
        const bool is_stack = i == 3U || i == 4U || i == 6U;
        allocations[i] = std::make_unique<queue::detail::AlignedBlock>(
            bytes + (is_stack ? kPage : 0U), kPage);
        regions[i] = {{allocations[i]->data() + (is_stack ? kPage : 0U), bytes}, 0U};
      }
    }
    layout.core_bytes = layout.region_bytes[5U];
    layout.monitor_bytes =
        static_cast<std::size_t>(number(at(resources, "monitor_bytes")));
    require(layout.monitor_bytes == 131072U, "fixed fixture monitor bound");
    allocations[0U] =
        std::make_unique<queue::detail::AlignedBlock>(layout.monitor_bytes, kPage);
    layout.total_mapping_bytes =
        static_cast<std::size_t>(number(at(resources, "total_mapping_bytes")));
    for (std::size_t i = 0U; i < 3U; ++i) {
      const auto cpu = i == 2U ? 1U : 0U;
      maps[i] = mapping({layout.region_bytes[i], kPage, cpu, 0U},
                        regions[i].mapping.data(), 101 + static_cast<int>(cpu));
    }
    for (std::size_t i = 0U; i < 2U; ++i)
      stacks[i] =
          stack({layout.region_bytes[i + 3U], kPage, static_cast<std::uint32_t>(i), 0U},
                allocations[i + 3U]->data(), 101 + static_cast<int>(i));
    core = mapping({layout.core_bytes, kPage, 2U, 0U}, regions[5U].mapping.data(), 103);
    monitor =
        mapping({layout.monitor_bytes, kPage, 2U, 0U}, allocations[0U]->data(), 103);
    controller =
        stack({layout.region_bytes[6U], kPage, 2U, 0U}, allocations[6U]->data(), 103);
    for (std::size_t i = 0U; i < 6U; ++i) {
      const auto role = i < 4U ? i % 2U : 2U;
      const auto region = role < 2U ? role + 3U : 6U;
      const auto base =
          reinterpret_cast<std::uintptr_t>(regions[region].mapping.data());
      modules[i] = {0U, 1U, base + 128U, 32U};
      tls[i] = {p::ThreadTlsStop::complete,
                call(101 + static_cast<std::int64_t>(role)),
                call(101 + static_cast<std::int64_t>(role)),
                call(),
                base + 512U,
                2U,
                0U,
                0,
                2U,
                1U};
    }
    hardware.attempted = hardware.released = true;
    hardware.requested_identity = {6U, 62U};
    hardware.observed_identity = p::Result<p::CpuFamilyModel>::success({6U, 62U});
    hardware.mapping_id = kMapping;
    hardware.cpu_count = 3U;
    hardware.stop = p::PrefetchReadbackPreparationStop::ready;
    constexpr std::array<std::uint32_t, 3U> cpus{0U, 1U, 8U};
    for (std::size_t i = 0U; i < 3U; ++i)
      hardware.cpus[i] = {cpus[i], 0U, 15U, call(10 + static_cast<std::int64_t>(i)),
                          call()};
    for (std::size_t i = 0U; i < 14U; ++i)
      threads.push_back(std::make_unique<ThreadEvidence>(ThreadIdentity{
          101 + static_cast<int>(i % 2U), static_cast<std::uint32_t>(i % 2U)}));
    for (std::size_t i = 0U; i < 2U; ++i)
      preparation[i] = {101 + static_cast<int>(i),
                        true,
                        false,
                        call(10),
                        call(11),
                        call(12),
                        threads[i]->observed,
                        {call(), call(), call()}};
    addresses.resize(42U);
    nodes.resize(42U);
    queries.reserve(42U);
    residency.reserve(42U);
    const auto& offsets = array(at(monitoring, "during_offset_ticks"), 2U);
    for (std::size_t group = 0U; group < 6U; ++group) {
      const auto phase = group / 3U;
      const auto moment = group % 3U;
      const auto& window = session.phases[phase].window;
      if (!window.has_value())
        throw std::runtime_error("missing fixture phase window");
      const auto begin = window->origin_ticks;
      const auto end = window->producer_deadline_ticks;
      const auto offset = moment == 1U ? number(offsets[phase]) : 0U;
      auto& control = controls[group];
      control.request = {static_cast<c::DiscoverySessionPhase>(phase),
                         static_cast<c::DiscoveryResidencyMoment>(moment), 5U, offset};
      control.attempted = true;
      control.stop = c::DiscoveryControlStop::sampled;
      for (std::size_t role = 0U; role < 2U; ++role) {
        control.scratch[role] = threads[2U + group * 2U + role]->scratch;
        control.workers[role] = threads[2U + group * 2U + role]->observed;
      }
      auto& hw = control.hardware;
      hw.attempted = true;
      hw.requested_state = protocol::RequestedHardwareState::h0;
      hw.prepared_controller_identity = p::CpuFamilyModel{6U, 62U};
      hw.mapping_id = kMapping;
      hw.cpu_count = 3U;
      hw.stop = p::PrefetchReadbackStop::sampled;
      for (std::size_t j = 0U; j < 3U; ++j)
        hw.cpus[j] = {cpus[j], 0U, call(8), {}, 0U, true};
      for (std::size_t region = 0U; region < 7U; ++region) {
        const auto index = group * 7U + region;
        const auto count = moment == 1U ? 1U : regions[region].mapping.size() / kPage;
        addresses[index].resize(count);
        nodes[index].resize(count);
        queries.push_back(std::make_unique<p::PreparedPageResidencyQuery>(
            regions[region].mapping.first(count * kPage), kPage, addresses[index],
            nodes[index]));
        std::fill(nodes[index].begin(), nodes[index].end(), 0);
        residency.emplace_back(
            c::DiscoveryResidencyRequest{
                static_cast<c::DiscoverySessionPhase>(phase),
                static_cast<c::DiscoveryResidencyMoment>(moment), region, offset},
            *queries.back());
        auto& row = residency.back();
        const auto tick = (moment == 0U   ? begin - 20'000U
                           : moment == 1U ? begin + offset
                                          : end + 300'000U) +
                          region * 2000U;
        row.begin = clock_at(tick);
        row.end = clock_at(tick + 1000U);
        row.query = p::PageResidencyQueryResult{0, 0};
        row.stop = c::DiscoveryResidencyStop::sampled;
        row.controls = region == 5U ? c::DiscoveryObservationStatus::accepted
                                    : c::DiscoveryObservationStatus::not_configured;
        if (moment == 1U) {
          row.wait_first = row.wait_last = clock_at(tick);
          row.wait_polls = 1U;
          row.finished_before = row.finished_after = 0U;
        }
      }
    }
    std::ostringstream smaps;
    auto smaps_regions = regions;
    std::sort(smaps_regions.begin(), smaps_regions.end(),
              [](const auto& left, const auto& right) {
                return reinterpret_cast<std::uintptr_t>(left.mapping.data()) <
                       reinterpret_cast<std::uintptr_t>(right.mapping.data());
              });
    for (const auto& region : smaps_regions) {
      const auto address = reinterpret_cast<std::uintptr_t>(region.mapping.data());
      const auto size = region.mapping.size() / 1024U;
      smaps << std::hex << address << '-' << address + region.mapping.size() << std::dec
            << " rw-p 00000000 00:00 0 /software-fixture\nSize: " << size
            << " kB\nKernelPageSize: 4 kB\nMMUPageSize: 4 kB\nAnonHugePages: 0 "
               "kB\nLocked: "
            << size << " kB\nVmFlags: rd wr mr mw me lo\n";
    }
    files.contents = smaps.str();
    for (std::size_t i = 0U; i < 6U; ++i) {
      file_bytes[i].resize(16384U);
      file_reads[i].resize(32U);
      samples[i].bytes = file_bytes[i];
      samples[i].reads = file_reads[i];
    }
    require(reader.prepare({"/proc/self/smaps",
                            16384U,
                            1024U,
                            32U,
                            {true, true, true, true, true, true}},
                           frozen_path, samples),
            "synthetic file preparation");
    for (std::size_t i = 0U; i < 6U; ++i)
      require(reader.sample(i) == p::FileSnapshotStop::complete,
              "synthetic file snapshot");
    require(reader.release(), "synthetic file close");
    file_preparations[0U] = reader.preparation();
  }
  auto view() -> c::NativeCaptureObservationView {
    c::NativeCaptureObservationView result{
        regions,
        residency,
        controls,
        {},
        tls,
        hardware,
        {&preparation[0U], &preparation[1U]},
        regions[5U].mapping,
        {allocations[0U]->data(), allocations[0U]->size()}};
    for (std::size_t i = 0U; i < 6U; ++i)
      result.tls_modules[i] = std::span(&modules[i], 1U);
    result.worker_mappings = {&maps[0U], &maps[1U], &maps[2U]};
    result.worker_stacks = {&stacks[0U], &stacks[1U]};
    result.worker_preparation = {c::MappedDiscoveryPreparationStop::ready,
                                 c::MappedDiscoveryPreparationStop::ready};
    result.thread_preparation_scratch = {threads[0U]->scratch, threads[1U]->scratch};
    result.environment_preparations = file_preparations;
    result.environment_samples = samples;
    return result;
  }
};
void verify_input(const Value& input, std::string_view mode) {
  require(input.as_object() != nullptr && input.as_object()->size() == 4U,
          "fixture input fields");
  const auto& cap = at(input, "capture");
  const auto& res = at(input, "resources");
  const auto& g = at(cap, "geometry");
  const auto& mon = at(input, "monitoring");
  require(mode == "ring" || mode == "service" || mode == "scheduled", "fixture mode");
  require(text(at(cap, "schema_version")) ==
                  "cpu-prefetch-stage17-formal-" + std::string(mode) + "-capture/1" &&
              text(at(cap, "method_id")) ==
                  (mode == "ring"      ? c::kRingDistanceWindowMethodId
                   : mode == "service" ? c::kServiceRateMethodId
                                       : c::kMatrixFeasibilityMethodId) &&
              (text(at(cap, "package")) == "R0" ||
               (mode != "ring" && text(at(cap, "package")) == "L1")) &&
              text(at(cap, "hardware_state")) == "H0" &&
              text(at(cap, "placement")) == "NEAR",
          "software fixture identity");
  require(
      number(at(g, "capacity")) >= 8U && number(at(g, "capacity")) <= 1024U &&
          number(at(g, "cache_line_bytes")) == 64U &&
          number(at(g, "base_page_bytes")) == kPage &&
          number(at(g, "producer_cpu")) == 0U && number(at(g, "consumer_cpu")) == 1U &&
          number(at(g, "producer_node")) == 0U && number(at(g, "consumer_node")) == 0U,
      "software fixture geometry");
  require(
      number(at(cap, "warmup_ns")) == 5'000'000'000U &&
          number(at(cap, "measurement_ns")) >= 1'000'000U &&
          number(at(cap, "measurement_ns")) <= 5'000'000'000U &&
          (mode != "ring" || number(at(cap, "minimum_observations_per_series")) == 1U),
      "software fixture durations");
  if (mode == "scheduled") {
    const auto& schedules = array(at(cap, "schedules"), 2U);
    for (std::size_t i = 0U; i < 2U; ++i) {
      const auto origin = number(at(schedules[i], "source_origin_ticks"));
      const auto end = number(at(schedules[i], "source_horizon_ticks"));
      const auto duration =
          number(at(cap, i == 0U ? "warmup_ns" : "measurement_ns")) * 1000U;
      require(end > origin && end - origin == duration &&
                  number(at(schedules[i], "offered_count")) == 4U,
              "bounded fixture schedule horizon");
      std::uint64_t previous = origin;
      for (const auto& item : array(at(schedules[i], "deadline_ticks"), 4U)) {
        const auto tick = number(item);
        require(previous <= tick && tick < end, "bounded fixture schedule order");
        previous = tick;
      }
    }
  }
  require(number(at(res, "initial_consumer_state")) == 17U &&
              number(at(mon, "control_region_index")) == 5U,
          "software fixture controls");
  for (const auto& phase : array(at(res, "phase_capacity"), 2U))
    for (const auto name : {"producer_primary_rows", "consumer_primary_rows",
                            "producer_demand_rows", "consumer_demand_rows"})
      if (mode == "ring" ||
          std::string_view(name).find("demand") == std::string_view::npos)
        require(number(at(phase, name)) == kRows, "fixed software raw storage");
}

struct PrimaryPhase final {
  protocol::RunId id;
  s::ProducerObservationStream producer_stream;
  s::ConsumerObservationStream consumer_stream;
  c::FormalServiceProducerPhase producer;
  c::FormalServiceConsumerPhase consumer;
  explicit PrimaryPhase(const std::string& name)
      : id(protocol::RunId::parse(name, "$fixture").value()),
        producer_stream(id, kRows), consumer_stream(id, kRows),
        producer{producer_stream, s::make_row_layout(id.value())},
        consumer{consumer_stream, s::make_row_layout(id.value()), {17U}, {17U}} {}
};
template <typename Queue, typename Package> struct ServicePreparation final {
  PrimaryPhase warmup;
  PrimaryPhase measurement;
  std::size_t capacity;
  queue::detail::AlignedBlock backing;
  workload::EventArena records;
  std::array<std::span<const std::uint64_t>, 2U> schedules{};
  std::array<std::size_t, 2U> offsets{};
  Queue& queue_ref;
  Package& package_ref;
  auto order_storage() -> std::span<std::size_t> {
    require(capacity <= backing.size() / 72U, "bounded fixture records/order storage");
    auto* start = reinterpret_cast<std::size_t*>(backing.data() + capacity * 64U);
    for (std::size_t i = 0U; i < capacity; ++i)
      std::construct_at(start + i, 0U);
    return {start, capacity};
  }
  ServicePreparation(const Value& input, Queue& queue, Package& package, bool scheduled)
      : warmup(text(at(at(at(input, "capture"), "warmup"), "run_id"))),
        measurement(text(at(at(at(input, "capture"), "measurement"), "run_id"))),
        capacity(static_cast<std::size_t>(
            number(at(at(at(input, "capture"), "geometry"), "capacity")))),
        backing(static_cast<std::size_t>(
                    number(array(at(at(input, "resources"), "region_bytes"), 7U)[0U])),
                kPage),
        records({capacity, 64U, kPage,
                 workload::MasterSeed::from_hex(
                     text(at(at(at(input, "capture"), "arena_seed"), "seed_hex"))),
                 text(at(at(at(input, "capture"), "arena_seed"), "namespace_id"))},
                {backing.data(), capacity * 64U}, order_storage()),
        queue_ref(queue), package_ref(package) {
    if (scheduled) {
      const auto& sources = array(at(at(input, "capture"), "schedules"), 2U);
      auto offset = (capacity * 72U + 63U) & ~std::size_t{63U};
      for (std::size_t phase = 0U; phase < 2U; ++phase) {
        const auto& values = array(at(sources[phase], "deadline_ticks"), 4U);
        require(offset <= backing.size() && 32U <= backing.size() - offset,
                "fixture schedule storage bound");
        offsets[phase] = offset;
        auto* data = reinterpret_cast<std::uint64_t*>(backing.data() + offset);
        for (std::size_t row = 0U; row < 4U; ++row)
          std::construct_at(data + row, number(values[row]));
        schedules[phase] = {data, 4U};
        offset = (offset + 32U + 63U) & ~std::size_t{63U};
      }
    }
  }
  auto prepare_producer() const noexcept -> bool { return true; }
  auto prepare_consumer() const noexcept -> bool { return true; }
  auto before_measurement_producer() const noexcept -> bool { return true; }
  auto before_measurement_consumer() const noexcept -> bool { return true; }
  auto producer_phase(bool first) noexcept -> c::FormalServiceProducerPhase& {
    return first ? warmup.producer : measurement.producer;
  }
  auto consumer_phase(bool first) noexcept -> c::FormalServiceConsumerPhase& {
    return first ? warmup.consumer : measurement.consumer;
  }
  auto run_id(bool first) const noexcept -> const protocol::RunId& {
    return first ? warmup.id : measurement.id;
  }
  auto arena() const noexcept -> const workload::EventArena& { return records; }
  auto queue() noexcept -> Queue& { return queue_ref; }
  auto package() noexcept -> Package& { return package_ref; }
};

template <c::FormalCapturePurpose Purpose, typename PreparationType>
auto run_service_script(const Value& capture, PreparationType& preparation)
    -> c::ScheduledSessionResult {
  c::ServiceSessionPlan plan{
      {{{5'000'000'000'000U, kRows, kRows, 1'000'000'000U},
        {number(at(capture, "measurement_ns")) * 1000U, kRows, kRows, 1'000'000'000U}}},
      1000U};
  Clock clock;
  c::FormalServiceSessionBackend<Clock, PreparationType, Purpose> backend(plan, clock,
                                                                          preparation);
  c::ScheduledSessionResult result;
  auto& session = result.lifecycle;
  session.clock_origin = clock.origin();
  session.prepared = {backend.prepare_producer(), backend.prepare_consumer()};
  require(session.prepared[0U] && session.prepared[1U], "service software preparation");
  for (std::size_t i = 0U; i < 2U; ++i) {
    const auto selected =
        i == 0U ? c::ServicePhase::warmup : c::ServicePhase::measurement;
    const auto begin = i == 0U ? 100'000U : 5'000'001'000'000U;
    const auto end = begin + plan.phases[i].duration_ticks;
    auto& state = session.phases[i];
    auto& evidence = result.schedules[i];
    state.origin_status = timing::ClockReadStatus::ok;
    state.observed_origin = begin;
    state.origin_sample = sample(begin);
    state.window = c::service_window(begin, plan.phases[i]);
    state.released = state.before_observed = state.during_observed =
        state.after_observed = true;
    auto& phase = backend.phase(selected);
    if constexpr (Purpose == c::FormalCapturePurpose::scheduled) {
      const auto& source = array(at(capture, "schedules"), 2U)[i];
      evidence.offered = number(at(source, "offered_count"));
      require(evidence.offered == 4U, "fixture four scheduled arrivals");
      evidence.source_origin_ticks = number(at(source, "source_origin_ticks"));
      evidence.source_horizon_ticks = number(at(source, "source_horizon_ticks"));
      evidence.mapped_schedule_validated = true;
    }
    std::uint64_t producer_completion = 0U;
    for (std::uint64_t n = 0U; n < 4U; ++n) {
      clock.next = begin + 1000U + n * 20'000U;
      auto due = clock.next;
      if constexpr (Purpose == c::FormalCapturePurpose::scheduled) {
        const auto source = preparation.schedules[i][static_cast<std::size_t>(n)];
        require(source >= evidence.source_origin_ticks &&
                    source < evidence.source_horizon_ticks,
                "fixture schedule endpoint");
        due = begin + (source - evidence.source_origin_ticks);
        clock.next = std::max(clock.next, due);
        evidence.mapped_last_deadline = due;
      }
      const auto produced = phase.try_producer_attempt({n, due, n});
      require(produced.status == lifecycle::AttemptStatus::complete &&
                  produced.outcome == queue::EnqueueResult::accepted,
              "service fixture enqueue");
      if (n == 3U) {
        producer_completion = clock.next;
        evidence.producer_completion = clock.read();
        evidence.all_arrivals_attempted = true;
        clock.next = end + 200'000U;
      }
      require(phase.try_consumer_poll(n).status == lifecycle::ConsumerPollStatus::item,
              "service fixture consume");
    }
    clock.next = end + 210'000U;
    require(phase.try_consumer_poll(4U).status == lifecycle::ConsumerPollStatus::empty,
            "service fixture terminal empty");
    const auto stopped =
        Purpose == c::FormalCapturePurpose::scheduled ? producer_completion : end;
    state.producer = {
        timing::ClockReadStatus::ok, stopped, 4U, 4U, 0U, stopped >= end, true};
    state.consumer = {timing::ClockReadStatus::ok, end + 220'000U, 4U, 5U, 1U, true};
    state.drain_checkpoint = clock_at(end + 400'000U);
    state.validated = backend.validate_quiescent(selected, state);
    require(state.validated, "service fixture full join");
    if (i == 0U) {
      session.private_reset = {backend.reset_producer(), backend.reset_consumer()};
      session.queue_reset = backend.reset_quiescent();
      require(session.private_reset[0U] && session.private_reset[1U] &&
                  session.queue_reset,
              "service fixture reset");
    }
  }
  backend.finalize_joined();
  session.stop = c::ServiceSessionStop::complete;
  return result;
}

template <c::FormalCapturePurpose Purpose, typename Queue, typename Package>
void publish_service_fixture(const Value& input, const std::filesystem::path& output,
                             Queue& queue, Package& package,
                             std::span<const std::size_t> order) {
  constexpr bool scheduled = Purpose == c::FormalCapturePurpose::scheduled;
  ServicePreparation backend(input, queue, package, scheduled);
  const auto& capture = at(input, "capture");
  auto session = run_service_script<Purpose>(capture, backend);
  Evidence evidence(input, backend, session.lifecycle);
  using Result = std::conditional_t<scheduled, c::NativeFormalScheduledCaptureResult,
                                    c::NativeFormalServiceCaptureResult>;
  using Layout = std::conditional_t<scheduled, c::NativeFormalScheduledCaptureLayout,
                                    c::NativeFormalServiceCaptureLayout>;
  Result result;
  Layout layout{};
  layout.core_bytes = evidence.layout.core_bytes;
  layout.monitor_bytes = evidence.layout.monitor_bytes;
  layout.total_mapping_bytes = evidence.layout.total_mapping_bytes;
  layout.region_bytes = evidence.layout.region_bytes;
  layout.workers.record_order = backend.capacity * 64U;
  layout.workers.records_bytes = layout.region_bytes[0U];
  layout.workers.schedule_offsets = backend.offsets;
  for (std::size_t i = 0U; i < 2U; ++i)
    layout.workers.schedule_counts[i] = backend.schedules[i].size();
  if constexpr (scheduled)
    result.session = session;
  else
    result.session = session.lifecycle;
  result.stop = c::NativeCaptureStop::complete;
  result.clock_origin =
      timing::AbsoluteClockReadResult{timing::ClockReadStatus::ok, kOrigin};
  result.core_mapping = evidence.core;
  result.monitor_mapping = evidence.monitor;
  result.controller_stack = evidence.controller;
  result.publication_attempted = true;
  Sink sink(output);
  const auto ordinal = static_cast<std::size_t>(number(at(capture, "ordinal")));
  if constexpr (scheduled) {
    c::NativeFormalScheduledPublicationView view{
        result,
        layout,
        evidence.view(),
        {&backend.warmup.producer, &backend.measurement.producer},
        {&backend.warmup.consumer, &backend.measurement.consumer},
        &backend.records,
        order};
    for (std::size_t i = 0U; i < 2U; ++i)
      view.schedules[i] = lifecycle::PreparedScheduleView{
          backend.schedules[i], session.schedules[i].source_origin_ticks,
          session.schedules[i].source_horizon_ticks};
    require(static_cast<bool>(stage::publish_formal_scheduled_capture(
                sink, ordinal, *capture.as_object(), view)),
            "scheduled fixture publication");
  } else {
    c::NativeFormalServicePublicationView view{
        result,
        layout,
        evidence.view(),
        {&backend.warmup.producer, &backend.measurement.producer},
        {&backend.warmup.consumer, &backend.measurement.consumer},
        &backend.records,
        order};
    require(
        static_cast<bool>(stage::publish_formal_service_capture(sink, ordinal, view)),
        "service fixture publication");
  }
  result.publication_succeeded = true;
  result.worker_mappings = evidence.maps;
  result.worker_stacks = evidence.stacks;
  const auto cleaned = [](auto& item) {
    item.cleanup_attempted = true;
    item.unlock = call();
    item.unmap = call();
  };
  for (auto& item : *result.worker_mappings)
    cleaned(item);
  for (auto& item : *result.worker_stacks)
    cleaned(item);
  cleaned(result.core_mapping);
  cleaned(result.monitor_mapping);
  cleaned(result.controller_stack);
  if constexpr (scheduled)
    write_json(output / "fixture-final-result.json",
               stage::formal_scheduled_capture_result_json(result));
  else
    write_json(output / "fixture-final-result.json",
               stage::formal_service_capture_result_json(result));
  write_json(
      output / "fixture-scope.json",
      Value(Object{{"synthetic", Value(true)},
                   {"hardware_claim", Value(false)},
                   {"execution_authority", Value(false)},
                   {"production_worker", Value(false)},
                   {"native_lifecycle_executed", Value(false)},
                   {"raw_artifacts", integer(scheduled ? 7U : 5U)},
                   {"driver",
                    Value(std::string("SCRIPTED_TYPED_BACKEND_SYNTHETIC_PLATFORM"))}}));
}
void run_formal(const Value& input, const std::filesystem::path& output,
                std::string_view mode) {
  const auto& capture = at(input, "capture");
  const auto capacity =
      static_cast<std::size_t>(number(at(at(capture, "geometry"), "capacity")));
  const auto dispatch = [&](auto& queue, auto& package,
                            std::span<const std::size_t> order) {
    if (mode == "scheduled")
      publish_service_fixture<c::FormalCapturePurpose::scheduled>(input, output, queue,
                                                                  package, order);
    else
      publish_service_fixture<c::FormalCapturePurpose::service_rate>(
          input, output, queue, package, order);
  };
  if (text(at(capture, "package")) == "R0") {
    queue::RingSpscQueue queue({capacity}, {64U});
    workload::R0Package package(queue);
    dispatch(queue, package, {});
  } else {
    const auto& plan = at(capture, "linked_order");
    const workload::DeterministicStream stream(workload::derive_stream_key(
        workload::MasterSeed::from_hex(text(at(plan, "seed_hex"))),
        text(at(plan, "namespace_id")), workload::StreamPurpose::node_order));
    const auto order = workload::make_permutation(capacity + 1U, stream);
    queue::LinkedSpscQueue queue({capacity}, {64U}, {kPage}, order);
    runner::X86PrefetchT0OnlyEmitter emitter;
    workload::L1Package package(queue, emitter);
    dispatch(queue, package, order);
  }
}
struct FixturePaths final {
  std::filesystem::path config;
  std::filesystem::path output;
};
void run(const FixturePaths& paths, std::string_view mode) {
  const auto& [config, output] = paths;
  require(std::filesystem::file_size(config) <= 65536U, "fixture input too large");
  std::ifstream input_file(config);
  const std::string body{std::istreambuf_iterator<char>(input_file), {}};
  auto parsed = protocol::json::parse(body);
  require(static_cast<bool>(parsed), "fixture JSON parse");
  const auto& input = parsed.value();
  verify_input(input, mode);
  require(std::filesystem::create_directory(output),
          "new fixture output directory required");
  if (mode != "ring") {
    run_formal(input, output, mode);
    return;
  }
  const auto& capture = at(input, "capture");
  Preparation backend(capture);
  auto session = run_script(backend, number(at(capture, "measurement_ns")) * 1000U);
  Evidence evidence(input, backend, session);
  c::NativeFormalRingCaptureResult result;
  result.stop = c::NativeCaptureStop::complete;
  result.session = session;
  result.clock_origin =
      timing::AbsoluteClockReadResult{timing::ClockReadStatus::ok, kOrigin};
  result.core_mapping = evidence.core;
  result.monitor_mapping = evidence.monitor;
  result.controller_stack = evidence.controller;
  result.publication_attempted = true;
  c::NativeFormalRingPublicationView view{
      result,
      evidence.layout,
      evidence.view(),
      {&backend.warmup.producer, &backend.measurement.producer},
      {&backend.warmup.consumer, &backend.measurement.consumer},
      &backend.records};
  Sink sink(output);
  const auto published = stage::publish_formal_ring_capture(
      sink, static_cast<std::size_t>(number(at(capture, "ordinal"))), 1U, view);
  require(static_cast<bool>(published), "formal fixture publication failed");
  result.publication_succeeded = true;
  result.worker_mappings = evidence.maps;
  result.worker_stacks = evidence.stacks;
  const auto cleaned = [](auto& item) {
    item.cleanup_attempted = true;
    item.unlock = call();
    item.unmap = call();
  };
  for (auto& item : *result.worker_mappings)
    cleaned(item);
  for (auto& item : *result.worker_stacks)
    cleaned(item);
  cleaned(result.core_mapping);
  cleaned(result.monitor_mapping);
  cleaned(result.controller_stack);
  write_json(output / "fixture-final-result.json",
             stage::formal_ring_capture_result_json(result));
  write_json(
      output / "fixture-scope.json",
      Value(Object{
          {"synthetic", Value(true)},
          {"hardware_claim", Value(false)},
          {"execution_authority", Value(false)},
          {"production_worker", Value(false)},
          {"native_lifecycle_executed", Value(false)},
          {"raw_artifacts", integer(8U)},
          {"driver",
           Value(std::string("SCRIPTED_REAL_R0_BACKEND_TYPED_SYNTHETIC_PLATFORM"))}}));
}
} // namespace
int main(int argc, char** argv) {
  try {
    require(argc == 3 || (argc == 5 && std::string_view(argv[1]) == "--mode"),
            "usage: stage17_formal_ring_fixture [--mode service|scheduled] input.json "
            "NEW-output-directory");
    const auto offset = argc == 3 ? 1 : 3;
    run(FixturePaths{argv[offset], argv[offset + 1]}, argc == 3 ? "ring" : argv[2]);
    return 0;
  } catch (const std::exception& error) {
    std::cerr << error.what() << '\n';
    return 1;
  }
}
