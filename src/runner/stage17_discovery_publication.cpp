#include "cpu_prefetch/runner/stage17_discovery_publication.hpp"

#include <algorithm>
#include <concepts>
#include <limits>
#include <stdexcept>
#include <type_traits>

namespace cpu_prefetch::runner::stage17 {
namespace {
using Value = protocol::json::Value;
using Object = Value::Object;
using Array = Value::Array;
using Number = protocol::json::Number;

auto scalar(bool value) -> Value { return Value(value); }
auto scalar(std::string_view value) -> Value { return Value(std::string(value)); }
auto scalar(const char* value) -> Value { return scalar(std::string_view(value)); }
template <std::integral T> auto scalar(T value) -> Value {
  if constexpr (std::is_signed_v<T>) {
    const auto number = static_cast<std::int64_t>(value);
    return Value(Number{Number::Kind::signed_integer, std::to_string(number), number});
  } else {
    const auto number = static_cast<std::uint64_t>(value);
    return Value(
        Number{Number::Kind::unsigned_integer, std::to_string(number), number});
  }
}
template <typename T>
  requires std::is_enum_v<T>
auto scalar(T value) -> Value {
  return scalar(static_cast<std::underlying_type_t<T>>(value));
}
template <typename T> auto scalar(const std::optional<T>& value) -> Value {
  return value.has_value() ? scalar(*value) : Value();
}
template <typename T, typename Encode>
auto maybe(const std::optional<T>& value, Encode encode) -> Value {
  return value.has_value() ? encode(*value) : Value();
}
template <typename Range, typename Encode>
auto sequence(const Range& range, Encode encode) -> Value {
  Array result;
  result.reserve(range.size());
  for (const auto& value : range) {
    result.push_back(encode(value));
  }
  return Value(std::move(result));
}
auto call(const std::optional<platform::LinuxCallResult>& value) -> Value {
  return maybe(value, [](const auto& observed) {
    return Value(Object{{"return_value", scalar(observed.return_value)},
                        {"error_number", scalar(observed.error_number)}});
  });
}
auto clock(const std::optional<timing::ClockReadResult>& value) -> Value {
  return maybe(value, [](const auto& observed) {
    return Value(Object{
        {"status", scalar(observed.status)},
        {"relative_picoseconds", observed.status == timing::ClockReadStatus::ok
                                     ? scalar(observed.sample.relative_picoseconds)
                                     : Value()},
        {"absolute_nanoseconds", observed.status == timing::ClockReadStatus::ok
                                     ? scalar(observed.sample.absolute_nanoseconds)
                                     : Value()}});
  });
}
auto identity(const platform::CpuFamilyModel& value) -> Value {
  return Value(
      Object{{"family", scalar(value.family)}, {"model", scalar(value.model)}});
}
auto owner(const platform::OwnerThreadObservation& value) -> Value {
  return Value(Object{
      {"affinity", call(value.affinity)},
      {"current_cpu", call(value.current_cpu)},
      {"thread_id", call(value.thread_id)},
      {"faults", call(value.faults)},
      {"minor_faults",
       value.faults.zero_return() ? scalar(value.minor_faults) : Value()},
      {"major_faults",
       value.faults.zero_return() ? scalar(value.major_faults) : Value()},
      {"affinity_cpu_count",
       value.affinity.zero_return() ? scalar(value.affinity_cpu_count) : Value()},
      {"requested_cpu_in_affinity", value.affinity.zero_return()
                                        ? scalar(value.requested_cpu_in_affinity)
                                        : Value()}});
}
auto mapping_plan(const platform::OwnerMappingPlan& value) -> Value {
  return Value(
      Object{{"bytes", scalar(value.bytes)},
             {"verified_base_page_bytes", scalar(value.verified_base_page_bytes)},
             {"owner_cpu", scalar(value.owner_cpu)},
             {"requested_node", scalar(value.requested_node)}});
}
auto mapping_result(const std::optional<platform::LinuxMappingResult>& value) -> Value {
  return maybe(value, [](const auto& item) {
    return Value(Object{
        {"address", item.address == nullptr
                        ? Value()
                        : scalar(reinterpret_cast<std::uintptr_t>(item.address))},
        {"error_number", scalar(item.error_number)}});
  });
}
auto mapping(const platform::OwnerMappingEvidence& value) -> Value {
  return Value(Object{{"requested", mapping_plan(value.requested)},
                      {"base_page_bytes", call(value.base_page_bytes)},
                      {"mapping", mapping_result(value.mapping)},
                      {"binding", call(value.binding)},
                      {"no_huge_pages", call(value.no_huge_pages)},
                      {"affinity_request", call(value.affinity_request)},
                      {"before_touch", maybe(value.before_touch, owner)},
                      {"after_touch", maybe(value.after_touch, owner)},
                      {"lock", call(value.lock)},
                      {"read_only", call(value.read_only)},
                      {"unlock", call(value.unlock)},
                      {"unmap", call(value.unmap)},
                      {"prefaulted_pages", scalar(value.prefaulted_pages)},
                      {"stop", scalar(value.stop)},
                      {"cleanup_attempted", scalar(value.cleanup_attempted)}});
}
auto stack(const platform::WorkerStackEvidence& value) -> Value {
  const auto& t = value.thread;
  return Value(Object{
      {"requested", mapping_plan(value.requested)},
      {"base_page_bytes", call(value.base_page_bytes)},
      {"minimum_stack_bytes", call(value.minimum_stack_bytes)},
      {"mapping", mapping_result(value.mapping)},
      {"binding", call(value.binding)},
      {"no_huge_pages", call(value.no_huge_pages)},
      {"guard", call(value.guard)},
      {"before_populate", maybe(value.before_populate, owner)},
      {"after_populate", maybe(value.after_populate, owner)},
      {"populate", call(value.populate)},
      {"lock", call(value.lock)},
      {"unlock", call(value.unlock)},
      {"unmap", call(value.unmap)},
      {"stop", scalar(value.stop)},
      {"cleanup_attempted", scalar(value.cleanup_attempted)},
      {"thread", Value(Object{{"attribute_init", scalar(t.attribute_init)},
                              {"attribute_stack", scalar(t.attribute_stack)},
                              {"attribute_guard", scalar(t.attribute_guard)},
                              {"attribute_affinity", scalar(t.attribute_affinity)},
                              {"create", scalar(t.create)},
                              {"attribute_destroy", scalar(t.attribute_destroy)},
                              {"join", scalar(t.join)}})}});
}
auto platform_error(const platform::Error& value) -> Value {
  return Value(Object{{"category", scalar(value.category)},
                      {"path", scalar(value.path)},
                      {"rule_id", scalar(value.rule_id)},
                      {"message", scalar(value.message)}});
}
auto hardware_preparation(const platform::PrefetchReadbackPreparation& value) -> Value {
  if (value.cpu_count > value.cpus.size())
    throw std::invalid_argument("hardware preparation extent exceeds storage");
  return Value(Object{
      {"attempted", scalar(value.attempted)},
      {"released", scalar(value.released)},
      {"requested_identity", identity(value.requested_identity)},
      {"observed_identity",
       maybe(value.observed_identity,
             [](const auto& observed) {
               return Value(
                   Object{{"value", observed ? identity(observed.value()) : Value()},
                          {"errors", sequence(observed.errors(), platform_error)}});
             })},
      {"mapping_id", scalar(value.mapping_id)},
      {"resolver_errors", sequence(value.resolver_errors, platform_error)},
      {"stop", scalar(value.stop)},
      {"cpu_count", scalar(value.cpu_count)},
      {"cpus",
       sequence(std::span(value.cpus).first(value.cpu_count), [](const auto& cpu) {
         return Value(Object{{"cpu", scalar(cpu.cpu)},
                             {"expected_h0", scalar(cpu.expected_h0)},
                             {"expected_h1", scalar(cpu.expected_h1)},
                             {"open", call(cpu.open)},
                             {"close", call(cpu.close)}});
       })}});
}
auto file_preparation(const platform::FileSnapshotPreparation& value) -> Value {
  const auto& plan = value.plan;
  return Value(Object{
      {"attempted", scalar(value.attempted)},
      {"released", scalar(value.released)},
      {"stop", scalar(value.stop)},
      {"open", call(value.open)},
      {"close", call(value.close)},
      {"plan", Value(Object{{"path_bytes",
                             sequence(plan.path,
                                      [](char byte) {
                                        return scalar(static_cast<unsigned char>(byte));
                                      })},
                            {"byte_capacity", scalar(plan.byte_capacity)},
                            {"chunk_bytes", scalar(plan.chunk_bytes)},
                            {"max_data_reads", scalar(plan.max_data_reads)},
                            {"requested", sequence(plan.requested, [](bool requested) {
                               return scalar(requested);
                             })}})}});
}
auto file_read(const platform::FileSnapshotRead& value) -> Value {
  return Value(Object{{"offset", scalar(value.offset)},
                      {"requested_bytes", scalar(value.requested_bytes)},
                      {"observed", call(value.observed)}});
}
auto file_sample(const platform::FileSnapshotSample& value, std::size_t index)
    -> Value {
  if (value.captured_bytes > value.bytes.size() ||
      value.data_reads > value.reads.size()) {
    throw std::invalid_argument("environment snapshot extent exceeds retained storage");
  }
  return Value(Object{
      {"source_index", scalar(index / platform::kFileSnapshotGroups)},
      {"group_index", scalar(index % platform::kFileSnapshotGroups)},
      {"attempted", scalar(value.attempted)},
      {"stop", scalar(value.stop)},
      {"captured_bytes", scalar(value.captured_bytes)},
      {"byte_capacity", scalar(value.bytes.size())},
      {"data_reads", scalar(value.data_reads)},
      {"read_capacity", scalar(value.reads.size())},
      {"raw_bytes", value.attempted
                        ? sequence(value.bytes.first(value.captured_bytes),
                                   [](std::byte byte) {
                                     return scalar(std::to_integer<unsigned int>(byte));
                                   })
                        : Value()},
      {"reads", sequence(value.reads.first(value.data_reads), file_read)},
      {"eof_probe", file_read(value.eof_probe)},
      {"probe_byte", value.eof_probe.observed.has_value() &&
                             value.eof_probe.observed->nonnegative_return() &&
                             value.eof_probe.observed->return_value == 1
                         ? scalar(std::to_integer<unsigned int>(value.probe_byte))
                         : Value()}});
}
auto reference(const ArtifactBinding& value) -> Value {
  return Value(Object{{"file_name", scalar(value.file_name)},
                      {"role", scalar(value.role)},
                      {"schema_identity", scalar(value.schema_identity)},
                      {"size_bytes", scalar(value.size_bytes)},
                      {"sha256", scalar(value.sha256)}});
}
auto request(const calibration::DiscoveryResidencyRequest& value) -> Value {
  return Value(Object{{"phase", scalar(value.phase)},
                      {"moment", scalar(value.moment)},
                      {"region_index", scalar(value.region_index)},
                      {"offset_ticks", scalar(value.offset_ticks)}});
}
auto thread_file(const platform::ThreadFileRead& value, std::span<const char> raw)
    -> Value {
  std::size_t used = 0U;
  if (value.read.has_value() && value.read->nonnegative_return()) {
    used = std::min(raw.size(), static_cast<std::size_t>(value.read->return_value));
  }
  return Value(Object{
      {"read", call(value.read)},
      {"end_probe", call(value.end_probe)},
      {"end_probe_byte",
       value.end_probe.has_value() && value.end_probe->return_value == 1
           ? scalar(static_cast<unsigned char>(value.end_probe_byte))
           : Value()},
      {"complete", scalar(value.complete)},
      {"raw_bytes", value.read.has_value() && value.read->nonnegative_return()
                        ? sequence(raw.first(used),
                                   [](char byte) {
                                     return scalar(static_cast<unsigned char>(byte));
                                   })
                        : Value()}});
}
auto thread(const platform::ThreadControlSample& value,
            const platform::ThreadMonitorScratch& scratch) -> Value {
  const auto stat = [](const auto& observed) {
    return Value(Object{{"task_id", scalar(observed.task_id)},
                        {"state", scalar(std::string(1U, observed.state))},
                        {"start_time_ticks", scalar(observed.start_time_ticks)},
                        {"minor_faults", scalar(observed.minor_faults)},
                        {"major_faults", scalar(observed.major_faults)},
                        {"last_cpu", scalar(observed.last_cpu)}});
  };
  return Value(Object{
      {"stop", scalar(value.stop)},
      {"stat_before_read", thread_file(value.stat_before_read, scratch.stat_before)},
      {"status_read", thread_file(value.status_read, scratch.status)},
      {"stat_after_read", thread_file(value.stat_after_read, scratch.stat_after)},
      {"stat_before", maybe(value.stat_before, stat)},
      {"stat_after", maybe(value.stat_after, stat)},
      {"status", maybe(value.status,
                       [](const auto& observed) {
                         return Value(Object{
                             {"task_id", scalar(observed.task_id)},
                             {"thread_group_id", scalar(observed.thread_group_id)},
                             {"voluntary_context_switches",
                              scalar(observed.voluntary_context_switches)},
                             {"involuntary_context_switches",
                              scalar(observed.involuntary_context_switches)}});
                       })},
      {"affinity_call", call(value.affinity_call)},
      {"affinity_cpu_count", scalar(value.affinity_cpu_count)},
      {"singleton_affinity_cpu", scalar(value.singleton_affinity_cpu)},
      {"affinity_mask",
       sequence(value.affinity_mask, [](auto word) { return scalar(word); })}});
}
auto hardware(const platform::PrefetchReadbackSample& value) -> Value {
  if (value.cpu_count > value.cpus.size())
    throw std::invalid_argument("hardware sample extent exceeds storage");
  return Value(Object{
      {"attempted", scalar(value.attempted)},
      {"stop", scalar(value.stop)},
      {"requested_state", scalar(value.requested_state)},
      {"prepared_controller_identity",
       maybe(value.prepared_controller_identity, identity)},
      {"mapping_id", scalar(value.mapping_id)},
      {"cpu_count", scalar(value.cpu_count)},
      {"cpus",
       sequence(std::span(value.cpus).first(value.cpu_count), [](const auto& cpu) {
         return Value(Object{
             {"cpu", scalar(cpu.cpu)},
             {"expected_value", scalar(cpu.expected_value)},
             {"read", call(cpu.read)},
             {"observed_value", scalar(cpu.observed_value)},
             {"matches", scalar(cpu.matches)},
             {"raw_bytes",
              !cpu.read.has_value() || !cpu.read->nonnegative_return()
                  ? Value()
                  : sequence(std::span(cpu.raw_bytes)
                                 .first(std::min(
                                     cpu.raw_bytes.size(),
                                     static_cast<std::size_t>(cpu.read->return_value))),
                             [](auto byte) {
                               return scalar(std::to_integer<unsigned int>(byte));
                             })}});
       })}});
}
auto controls(const calibration::DiscoveryControlSample& value) -> Value {
  Array workers;
  for (std::size_t index = 0U; index < 2U; ++index) {
    workers.push_back(maybe(value.workers[index], [&](const auto& observed) {
      return thread(observed, value.scratch[index]);
    }));
  }
  return Value(Object{{"request", request(value.request)},
                      {"attempted", scalar(value.attempted)},
                      {"stop", scalar(value.stop)},
                      {"workers", Value(std::move(workers))},
                      {"hardware", hardware(value.hardware)}});
}
auto residency(const calibration::DiscoveryResidencySample& value) -> Value {
  return Value(Object{
      {"request", request(value.request)},
      {"stop", scalar(value.stop)},
      {"controls", scalar(value.controls)},
      {"wait_first", clock(value.wait_first)},
      {"wait_last", clock(value.wait_last)},
      {"begin", clock(value.begin)},
      {"end", clock(value.end)},
      {"wait_polls", scalar(value.wait_polls)},
      {"prior_controller_tick", scalar(value.prior_controller_tick)},
      {"finished_before", scalar(value.finished_before)},
      {"finished_after", scalar(value.finished_after)},
      {"query", maybe(value.query,
                      [](const auto& observed) {
                        return Value(
                            Object{{"syscall_return", scalar(observed.syscall_return)},
                                   {"error_number", scalar(observed.error_number)}});
                      })},
      {"page_addresses", sequence(value.pages.page_addresses(),
                                  [](const auto* pointer) {
                                    return scalar(
                                        reinterpret_cast<std::uintptr_t>(pointer));
                                  })},
      {"page_status",
       value.query.has_value()
           ? sequence(value.pages.page_status(), [](int node) { return scalar(node); })
           : Value()}});
}
auto worker(const calibration::DiscoveryWorkerResult& value) -> Value {
  return Value(
      Object{{"stop", scalar(value.stop)},
             {"attempts", scalar(value.attempts)},
             {"advanced", scalar(value.advanced)},
             {"full", scalar(value.full)},
             {"empty", scalar(value.empty)},
             {"last_observed_tick", scalar(value.last_observed_tick)},
             {"last_attempt_outcome", scalar(value.last_attempt_outcome)},
             {"last_operation_outcome", scalar(value.last_operation_outcome)},
             {"last_attempt_before_status", scalar(value.last_attempt_before_status)},
             {"last_attempt_after_status", scalar(value.last_attempt_after_status)},
             {"failed_clock_status", scalar(value.failed_clock_status)}});
}
auto drain(const calibration::DiscoveryDrainResult& value) -> Value {
  return Value(Object{{"stop", scalar(value.stop)},
                      {"attempts", scalar(value.attempts)},
                      {"dequeued", scalar(value.dequeued)},
                      {"last_observed_tick", scalar(value.last_observed_tick)},
                      {"failed_clock_status", scalar(value.failed_clock_status)},
                      {"reset_verified", scalar(value.reset_verified)},
                      {"final_audit", maybe(value.final_audit, [](const auto& a) {
                         return Value(Object{
                             {"occupied_slots", scalar(a.occupied_slots)},
                             {"producer_position", scalar(a.producer_position)},
                             {"consumer_position", scalar(a.consumer_position)},
                             {"positions_in_range", scalar(a.positions_in_range)}});
                       })}});
}
auto session(const calibration::DiscoverySessionResult& value) -> Value {
  return Value(Object{
      {"stop", scalar(value.stop)},
      {"warmup_verified", scalar(value.warmup_verified)},
      {"measurement_verified", scalar(value.measurement_verified)},
      {"preparation",
       sequence(value.preparation, [](auto item) { return scalar(item); })},
      {"worker_exception",
       sequence(value.worker_exception, [](auto item) { return scalar(item); })},
      {"private_reset_verified",
       sequence(value.private_reset_verified, [](auto item) { return scalar(item); })},
      {"origins", sequence(value.origins, [](auto item) { return scalar(item); })},
      {"observed_origins",
       sequence(value.observed_origins, [](auto item) { return scalar(item); })},
      {"origin_status",
       sequence(value.origin_status, [](auto item) { return scalar(item); })},
      {"warmup", sequence(value.warmup, worker)},
      {"measurement", sequence(value.measurement, worker)},
      {"warmup_drain", drain(value.warmup_drain)},
      {"measurement_drain", drain(value.measurement_drain)},
      {"observations", sequence(value.observations, [](const auto& item) {
         return Value(Object{{"before", scalar(item.before)},
                             {"during", scalar(item.during)},
                             {"after", scalar(item.after)}});
       })}});
}
auto tls(const platform::ThreadTlsSnapshot& value,
         std::span<const platform::ThreadTlsModule> modules) -> Value {
  if (value.used > modules.size())
    throw std::invalid_argument("TLS extent exceeds retained modules");
  return Value(
      Object{{"stop", scalar(value.stop)},
             {"thread_before", call(value.thread_before)},
             {"thread_after", call(value.thread_after)},
             {"fs_read", call(value.fs_read)},
             {"fs_base", scalar(value.fs_base)},
             {"loader_adds", scalar(value.loader_adds)},
             {"loader_subs", scalar(value.loader_subs)},
             {"iteration_return", scalar(value.iteration_return)},
             {"visited_objects", scalar(value.visited_objects)},
             {"used", scalar(value.used)},
             {"modules", sequence(modules.first(value.used), [](const auto& module) {
                return Value(Object{{"image_base", scalar(module.image_base)},
                                    {"module_id", scalar(module.module_id)},
                                    {"address", scalar(module.address)},
                                    {"bytes", scalar(module.bytes)}});
              })}});
}

auto sample(timing::ClockSample value) -> Value {
  return Value(Object{{"absolute_nanoseconds", scalar(value.absolute_nanoseconds)},
                      {"relative_picoseconds", scalar(value.relative_picoseconds)}});
}
auto producer_primary(const timing::ProducerObservation& value) -> Value {
  return Value(
      Object{{"logical_sequence", scalar(value.logical_sequence.value)},
             {"record_index", scalar(value.record_index.value)},
             {"scheduled_arrival", scalar(value.scheduled_arrival)},
             {"producer_handle_begin", sample(value.producer_handle_begin)},
             {"record_lookup_completion", sample(value.record_lookup_completion)},
             {"enqueue_invocation", sample(value.enqueue_invocation)},
             {"enqueue_linearization", maybe(value.enqueue_linearization, sample)},
             {"enqueue_attempt_completion", sample(value.enqueue_attempt_completion)},
             {"outcome", scalar(value.outcome)},
             {"accepted_ordinal",
              maybe(value.accepted_ordinal, [](auto i) { return scalar(i.value); })}});
}
auto consumer_primary(const timing::ConsumerObservation& value) -> Value {
  return Value(
      Object{{"consumed_ordinal", scalar(value.consumed_ordinal.value)},
             {"observed_record_index", scalar(value.observed_record_index.value)},
             {"dequeue_invocation", sample(value.dequeue_invocation)},
             {"dequeue_linearization", sample(value.dequeue_linearization)},
             {"dequeue_completion", sample(value.dequeue_completion)},
             {"consumer_action_completion", sample(value.consumer_action_completion)}});
}
auto capture(const calibration::RingCaptureResult& value) -> Value {
  return Value(Object{{"outcome", scalar(value.outcome)},
                      {"before_status", scalar(value.before_status)},
                      {"after_status", scalar(value.after_status)},
                      {"operation_outcome", scalar(value.operation_outcome)},
                      {"operation_performed", scalar(value.operation_performed)},
                      {"failed_clock_status", scalar(value.failed_clock_status)}});
}
auto producer_event(const calibration::DiscoveryProducerEventCapture& value) -> Value {
  return Value(Object{
      {"capture", capture(value.capture)},
      {"failed_boundary", scalar(value.failed_boundary)},
      {"requested_attempt",
       maybe(value.requested_attempt,
             [](const auto& a) {
               return Value(
                   Object{{"logical_sequence", scalar(a.logical_sequence.value)},
                          {"scheduled_arrival", scalar(a.scheduled_arrival)},
                          {"candidate_accepted_ordinal",
                           scalar(a.candidate_accepted_ordinal.value)}});
             })},
      {"selected", maybe(value.selected,
                         [](const auto& s) {
                           return Value(Object{
                               {"record_index", scalar(s.record_index.value)},
                               {"record_address",
                                scalar(reinterpret_cast<std::uintptr_t>(s.record))}});
                         })},
      {"handle_begin", clock(value.handle_begin)},
      {"lookup_completion", clock(value.lookup_completion)},
      {"enqueue_invocation", clock(value.enqueue_invocation)},
      {"demand_before", clock(value.demand.before)},
      {"demand_after", clock(value.demand.after)},
      {"enqueue_publication", clock(value.enqueue_publication)},
      {"enqueue_completion", clock(value.enqueue_completion)},
      {"primary", maybe(value.primary, producer_primary)}});
}
auto consumer_event(const calibration::DiscoveryConsumerEventCapture& value) -> Value {
  return Value(Object{
      {"capture", capture(value.capture)},
      {"failed_boundary", scalar(value.failed_boundary)},
      {"candidate_consumed_ordinal",
       maybe(value.candidate_consumed_ordinal, [](auto i) { return scalar(i.value); })},
      {"dequeue_invocation", clock(value.dequeue_invocation)},
      {"demand_before", clock(value.demand.before)},
      {"demand_after", clock(value.demand.after)},
      {"dequeue_observation", clock(value.dequeue_observation)},
      {"operation",
       maybe(value.operation,
             [](const auto& o) {
               return Value(
                   Object{{"status", scalar(o.status)},
                          {"event_address",
                           o.event == nullptr
                               ? Value()
                               : scalar(reinterpret_cast<std::uintptr_t>(o.event))}});
             })},
      {"dequeue_completion", clock(value.dequeue_completion)},
      {"access",
       maybe(value.access,
             [](const auto& a) {
               const bool read =
                   a.status == workload::RecordAccessStatus::valid ||
                   a.status == workload::RecordAccessStatus::record_index_corrupt;
               return Value(Object{
                   {"status", scalar(a.status)},
                   {"record_index", read ? scalar(a.record_index.value) : Value()},
                   {"payload", read ? scalar(a.payload) : Value()}});
             })},
      {"action_completion", clock(value.action_completion)},
      {"primary", maybe(value.primary, consumer_primary)}});
}
auto snapshot(const storage::RawStreamSnapshot& value) -> Value {
  return Value(Object{{"run_id", scalar(value.run_id)},
                      {"stream_kind", scalar(value.stream_kind)},
                      {"row_count", scalar(value.row_count)},
                      {"row_capacity", scalar(value.row_capacity)},
                      {"row_bytes", scalar(value.row_bytes)},
                      {"completeness", scalar(storage::to_string(value.completeness))},
                      {"overflowed", scalar(value.overflowed)},
                      {"retained_bytes", scalar(value.bytes.size())}});
}
auto row_layout(const storage::RowLayout& value) -> Value {
  return Value(Object{{"run_id_bytes", scalar(value.run_id_bytes)},
                      {"prefix_bytes", scalar(value.prefix_bytes)},
                      {"producer_row_bytes", scalar(value.producer_row_bytes)},
                      {"consumer_row_bytes", scalar(value.consumer_row_bytes)},
                      {"joined_row_bytes", scalar(value.joined_row_bytes)}});
}
auto mapped_layout(const calibration::MappedDiscoveryLayout& value) -> Value {
  return Value(Object{
      {"records_bytes", scalar(value.records_bytes)},
      {"producer_bytes", scalar(value.producer_bytes)},
      {"consumer_bytes", scalar(value.consumer_bytes)},
      {"record_order", scalar(value.record_order)},
      {"arena_object", scalar(value.arena_object)},
      {"ring_object", scalar(value.ring_object)},
      {"slots", scalar(value.slots)},
      {"cursors", scalar(value.cursors)},
      {"ring_storage",
       Value(Object{{"slot_bytes", scalar(value.ring_storage.slot_bytes)},
                    {"cursor_bytes", scalar(value.ring_storage.cursor_bytes)}})},
      {"phases", sequence(value.phases, [](const auto& p) {
         return Value(Object{
             {"count", scalar(p.count)},
             {"row", row_layout(p.row)},
             {"raw", Value(Object{{"producer_bytes", scalar(p.raw.producer_bytes)},
                                  {"consumer_bytes", scalar(p.raw.consumer_bytes)}})},
             {"producer_object", scalar(p.producer_object)},
             {"producer_demand", scalar(p.producer_demand)},
             {"producer_issue", scalar(p.producer_issue)},
             {"producer_raw", scalar(p.producer_raw)},
             {"consumer_object", scalar(p.consumer_object)},
             {"consumer_demand", scalar(p.consumer_demand)},
             {"consumer_issue", scalar(p.consumer_issue)},
             {"consumer_raw", scalar(p.consumer_raw)},
             {"drain", scalar(p.drain)}});
       })}});
}
auto arena(const workload::EventArena* value) -> Value {
  if (value == nullptr)
    return Value();
  const auto layout = value->layout();
  const auto current = value->content_checksum();
  Object result{
      {"capacity", scalar(layout.capacity)},
      {"cache_line_bytes", scalar(layout.cache_line_bytes)},
      {"base_page_bytes", scalar(layout.base_page_bytes)},
      {"allocated_bytes", scalar(layout.allocated_bytes)},
      {"distinct_cache_lines", scalar(layout.distinct_cache_lines)},
      {"distinct_pages", scalar(layout.distinct_pages)},
      {"base_page_aligned", scalar(layout.base_page_aligned)},
      {"every_record_line_aligned", scalar(layout.every_record_line_aligned)},
      {"padding_initialized", scalar(layout.padding_initialized)},
      {"storage_address",
       scalar(reinterpret_cast<std::uintptr_t>(value->storage_address()))},
      {"prepared_content_sha256", scalar(value->prepared_content_checksum().hex())},
      {"publication_content_sha256", scalar(current.hex())},
      {"content_unchanged", scalar(current == value->prepared_content_checksum())}};
  const auto retain_hash = [&](const char* name, const char* error_name,
                               const auto& compute) {
    try {
      result.emplace(name, scalar(compute().hex()));
      result.emplace(error_name, Value());
    } catch (const workload::WorkloadSetupError& error) {
      result.emplace(name, Value());
      result.emplace(error_name, scalar(error.what()));
    }
  };
  retain_hash("ordered_index_sha256", "ordered_index_error",
              [&] { return value->ordered_index_checksum(); });
  retain_hash("address_delta_sha256", "address_delta_error",
              [&] { return value->address_delta_checksum(); });
  return Value(std::move(result));
}

auto bytes(std::string_view text) -> std::vector<std::byte> {
  const auto span = std::as_bytes(std::span(text.data(), text.size()));
  return {span.begin(), span.end()};
}
auto prefix(std::size_t ordinal) -> std::string {
  if (ordinal >= 36U) {
    throw std::invalid_argument("discovery capture ordinal outside D178 plan");
  }
  return "discovery-c" + std::string(ordinal < 10U ? "0" : "") +
         std::to_string(ordinal);
}

class Publisher final {
public:
  explicit Publisher(ArtifactSink& sink) : sink_(sink) {}
  auto publish(std::string name, std::string role, std::string schema,
               std::vector<std::byte> payload, std::string media) -> Value {
    auto published =
        sink_.publish({std::move(role), std::move(schema), std::move(media),
                       std::move(name), std::move(payload)});
    if (!published) {
      throw std::runtime_error("discovery artifact publication failed");
    }
    bindings.push_back(std::move(published.value()));
    return reference(bindings.back());
  }
  std::vector<ArtifactBinding> bindings;

private:
  ArtifactSink& sink_;
};

auto phase(Publisher& publisher, const std::string& name,
           const calibration::MappedProducerPhase* producer,
           const calibration::MappedConsumerPhase* consumer) -> Value {
  Object result{{"producer_available", scalar(producer != nullptr)},
                {"consumer_available", scalar(consumer != nullptr)}};
  const auto raw_publish = [&](const auto* value, const char* suffix,
                               const char* role) {
    if (value == nullptr)
      return publisher.publish(name + suffix, role, "RAW-OBS-U64LE-LP-RUNID-v1", {},
                               "application/octet-stream");
    const auto raw = value->primary.snapshot();
    return publisher.publish(name + suffix, role, "RAW-OBS-U64LE-LP-RUNID-v1",
                             {raw.bytes.begin(), raw.bytes.end()},
                             "application/octet-stream");
  };
  result.emplace("producer",
                 raw_publish(producer, "-producer.bin", "DISCOVERY_PRODUCER_RAW"));
  result.emplace("consumer",
                 raw_publish(consumer, "-consumer.bin", "DISCOVERY_CONSUMER_RAW"));
  result.emplace("producer_snapshot", producer == nullptr
                                          ? Value()
                                          : snapshot(producer->primary.snapshot()));
  result.emplace("consumer_snapshot", consumer == nullptr
                                          ? Value()
                                          : snapshot(consumer->primary.snapshot()));
  result.emplace("producer_layout",
                 producer == nullptr ? Value() : row_layout(producer->layout));
  result.emplace("consumer_layout",
                 consumer == nullptr ? Value() : row_layout(consumer->layout));
  if (producer != nullptr) {
    const auto raw = producer->primary.snapshot();
    result.emplace("run_id", scalar(raw.run_id));
    result.emplace("attempted", scalar(producer->attempted));
    result.emplace("accepted", scalar(producer->accepted));
    result.emplace("full", scalar(producer->full));
    result.emplace("producer_row_count", scalar(raw.row_count));
    result.emplace("producer_prefix_complete",
                   scalar(producer->primary_prefix_complete));
    result.emplace("producer_last_append", scalar(producer->last_append));
    result.emplace("producer_current", producer_event(producer->current));
  }
  if (consumer != nullptr) {
    const auto raw = consumer->primary.snapshot();
    result.emplace("consumer_run_id", scalar(raw.run_id));
    result.emplace("consumed_including_drain", scalar(consumer->consumed));
    result.emplace("consumer_row_count", scalar(raw.row_count));
    result.emplace("consumer_prefix_complete",
                   scalar(consumer->primary_prefix_complete));
    result.emplace("checksum", scalar(consumer->state.value));
    result.emplace("initial_checksum", scalar(consumer->initial_state.value));
    result.emplace("capture_horizon_complete",
                   scalar(consumer->capture_horizon_complete));
    result.emplace("drain_requests", scalar(consumer->drain_requests));
    result.emplace("drain_retention_exhausted",
                   scalar(consumer->drain_retention_exhausted));
    result.emplace("consumer_last_append", scalar(consumer->last_append));
    result.emplace("consumer_current", consumer_event(consumer->current));
    result.emplace("consumer_last_join",
                   Value(Object{{"status", scalar(consumer->last_join.status)},
                                {"matched", scalar(consumer->last_join.matched)},
                                {"failed_producer_row",
                                 scalar(consumer->last_join.failed_producer_row)}}));
    if (consumer->drain_requests > consumer->drain_rows.size())
      throw std::invalid_argument("drain extent exceeds retained rows");
    result.emplace(
        "drain_rows",
        sequence(consumer->drain_rows.first(consumer->drain_requests), consumer_event));
  }
  {
    const auto p =
        producer == nullptr
            ? calibration::RingWorkerDemandView{}
            : producer->trace.worker_series(calibration::RingWorker::producer);
    const auto c =
        consumer == nullptr
            ? calibration::RingWorkerDemandView{}
            : consumer->trace.worker_series(calibration::RingWorker::consumer);
    const std::array vectors{p.demand_ticks, p.issue_ticks, c.demand_ticks,
                             c.issue_ticks};
    const std::array names{"producer_demand", "producer_issue", "consumer_demand",
                           "consumer_issue"};
    std::size_t total = 0U;
    for (const auto values : vectors) {
      if (values.size() >
          (std::numeric_limits<std::size_t>::max() - total) / sizeof(std::uint64_t))
        throw std::overflow_error("discovery demand extent overflows");
      total += values.size() * sizeof(std::uint64_t);
    }
    std::vector<std::byte> encoded;
    encoded.reserve(total);
    Array metadata;
    for (std::size_t index = 0U; index < vectors.size(); ++index) {
      const auto values = vectors[index];
      const bool available = index < 2U ? producer != nullptr : consumer != nullptr;
      if (values.size() >
          (encoded.max_size() - encoded.size()) / sizeof(std::uint64_t)) {
        throw std::overflow_error("discovery demand publication extent overflows");
      }
      metadata.emplace_back(
          Object{{"name", scalar(names[index])},
                 {"available", scalar(available)},
                 {"offset_bytes", scalar(encoded.size())},
                 {"count", available ? scalar(values.size()) : Value()}});
      for (const auto value : values) {
        for (unsigned int shift = 0U; shift < 64U; shift += 8U) {
          encoded.push_back(static_cast<std::byte>((value >> shift) & 255U));
        }
      }
    }
    result.emplace("demand",
                   publisher.publish(name + "-demand.bin", "DISCOVERY_DEMAND_RAW",
                                     "DISCOVERY-FOUR-U64LE-VECTORS-v1",
                                     std::move(encoded), "application/octet-stream"));
    result.emplace("demand_vectors", Value(std::move(metadata)));
    result.emplace("producer_nonadvancing",
                   producer == nullptr ? Value() : scalar(p.nonadvancing_count));
    result.emplace("consumer_nonadvancing",
                   consumer == nullptr ? Value() : scalar(c.nonadvancing_count));
  }
  return Value(std::move(result));
}
} // namespace

auto discovery_capture_result_json(
    const calibration::NativeDiscoveryCaptureResult& result) -> protocol::json::Value {
  return Value(
      Object{{"stop", scalar(result.stop)},
             {"session", maybe(result.session, session)},
             {"clock_origin", maybe(result.clock_origin,
                                    [](const auto& origin) {
                                      return Value(Object{
                                          {"status", scalar(origin.status)},
                                          {"absolute_nanoseconds",
                                           origin.status == timing::ClockReadStatus::ok
                                               ? scalar(origin.absolute_nanoseconds)
                                               : Value()}});
                                    })},
             {"core_mapping", mapping(result.core_mapping)},
             {"monitor_mapping", mapping(result.monitor_mapping)},
             {"controller_stack", stack(result.controller_stack)},
             {"worker_mappings",
              maybe(result.worker_mappings,
                    [](const auto& values) { return sequence(values, mapping); })},
             {"worker_stacks",
              maybe(result.worker_stacks,
                    [](const auto& values) { return sequence(values, stack); })},
             {"publication_attempted", scalar(result.publication_attempted)},
             {"publication_succeeded", scalar(result.publication_succeeded)}});
}

auto publish_discovery_capture(ArtifactSink& sink, std::size_t capture_ordinal,
                               const calibration::NativeDiscoveryPublicationView& view)
    -> protocol::Result<std::vector<ArtifactBinding>> {
  try {
    Publisher publisher(sink);
    const auto base = prefix(capture_ordinal);
    Array phases;
    for (std::size_t index = 0U; index < 2U; ++index) {
      phases.push_back(phase(publisher,
                             base + (index == 0U ? "-warmup" : "-measurement"),
                             view.producer[index], view.consumer[index]));
    }
    Array tls_snapshots;
    for (std::size_t index = 0U; index < view.tls_snapshots.size(); ++index) {
      tls_snapshots.push_back(tls(view.tls_snapshots[index], view.tls_modules[index]));
    }
    Array thread_preparations;
    for (std::size_t index = 0U; index < view.thread_preparations.size(); ++index) {
      const auto* prepared = view.thread_preparations[index];
      if (prepared == nullptr) {
        thread_preparations.emplace_back();
        continue;
      }
      thread_preparations.emplace_back(
          Object{{"requested_task_id", scalar(prepared->requested_task_id)},
                 {"attempted", scalar(prepared->attempted)},
                 {"ready", scalar(prepared->ready)},
                 {"directory_open", call(prepared->directory_open)},
                 {"stat_open", call(prepared->stat_open)},
                 {"status_open", call(prepared->status_open)},
                 {"initial",
                  thread(prepared->initial, view.thread_preparation_scratch[index])},
                 {"closes", sequence(prepared->closes, call)}});
    }
    Array environment_samples;
    environment_samples.reserve(view.environment_samples.size());
    for (std::size_t index = 0U; index < view.environment_samples.size(); ++index) {
      environment_samples.push_back(
          file_sample(view.environment_samples[index], index));
    }
    const auto memory = [](std::span<const std::byte> value) {
      return Value(Object{
          {"address", value.data() == nullptr
                          ? Value()
                          : scalar(reinterpret_cast<std::uintptr_t>(value.data()))},
          {"bytes", scalar(value.size())}});
    };
    Object document{
        {"schema_version", scalar("cpu-prefetch-stage17-discovery-control/1")},
        {"capture_ordinal", scalar(capture_ordinal)},
        {"capture_stop_before_publication", scalar(view.result.stop)},
        {"clock_origin",
         maybe(view.result.clock_origin,
               [](const auto& origin) {
                 return Value(Object{{"status", scalar(origin.status)},
                                     {"absolute_nanoseconds",
                                      origin.status == timing::ClockReadStatus::ok
                                          ? scalar(origin.absolute_nanoseconds)
                                          : Value()}});
               })},
        {"publication_attempted", scalar(view.result.publication_attempted)},
        {"publication_succeeded", scalar(view.result.publication_succeeded)},
        {"cleanup_observation_scope", scalar("BEFORE_PUBLICATION_RETURNS_FINAL_CLEANUP_"
                                             "REQUIRES_RETURNED_NATIVE_RESULT")},
        {"core_mapping", mapping(view.result.core_mapping)},
        {"monitor_mapping", mapping(view.result.monitor_mapping)},
        {"controller_stack", stack(view.result.controller_stack)},
        {"worker_mappings", sequence(view.worker_mappings,
                                     [](const auto* item) {
                                       return item == nullptr ? Value()
                                                              : mapping(*item);
                                     })},
        {"worker_stacks", sequence(view.worker_stacks,
                                   [](const auto* item) {
                                     return item == nullptr ? Value() : stack(*item);
                                   })},
        {"result_worker_mappings",
         maybe(view.result.worker_mappings,
               [](const auto& items) { return sequence(items, mapping); })},
        {"result_worker_stacks",
         maybe(view.result.worker_stacks,
               [](const auto& items) { return sequence(items, stack); })},
        {"worker_preparation",
         sequence(view.worker_preparation, [](auto item) { return scalar(item); })},
        {"core", memory(view.core)},
        {"monitor_arena", memory(view.monitor_arena)},
        {"arena", arena(view.arena)},
        {"hardware_preparation", hardware_preparation(view.hardware)},
        {"environment_preparations",
         sequence(view.environment_preparations, file_preparation)},
        {"environment_samples", Value(std::move(environment_samples))},
        {"environment_group_order",
         Value(Array{scalar("WARMUP_BEFORE"), scalar("WARMUP_DURING"),
                     scalar("WARMUP_AFTER"), scalar("MEASUREMENT_BEFORE"),
                     scalar("MEASUREMENT_DURING"), scalar("MEASUREMENT_AFTER")})},
        {"thread_preparations", Value(std::move(thread_preparations))},
        {"layout",
         Value(Object{{"core_bytes", scalar(view.layout.core_bytes)},
                      {"workers", mapped_layout(view.layout.workers)},
                      {"monitor_bytes", scalar(view.layout.monitor_bytes)},
                      {"total_mapping_bytes", scalar(view.layout.total_mapping_bytes)},
                      {"region_bytes", sequence(view.layout.region_bytes,
                                                [](auto n) { return scalar(n); })}})},
        {"session", maybe(view.result.session, session)},
        {"phases", Value(std::move(phases))},
        {"regions", sequence(view.regions,
                             [](const auto& region) {
                               return Value(Object{
                                   {"address", scalar(reinterpret_cast<std::uintptr_t>(
                                                   region.mapping.data()))},
                                   {"bytes", scalar(region.mapping.size())},
                                   {"expected_node", scalar(region.expected_node)}});
                             })},
        {"residency", sequence(view.residency, residency)},
        {"controls", sequence(view.controls, controls)},
        {"tls_snapshots", Value(std::move(tls_snapshots))},
        {"diagnostic_only", scalar(true)},
        {"execution_authority", scalar(false)},
        {"phase18_authority", scalar(false)}};
    auto canonical = protocol::json::canonicalize(Value(std::move(document)));
    if (!canonical) {
      return protocol::Result<std::vector<ArtifactBinding>>::failure(
          canonical.errors());
    }
    static_cast<void>(publisher.publish(base + "-control.json",
                                        "DISCOVERY_CAPTURE_CONTROL",
                                        "cpu-prefetch-stage17-discovery-control/1",
                                        bytes(canonical.value()), "application/json"));
    return protocol::Result<std::vector<ArtifactBinding>>::success(publisher.bindings);
  } catch (const std::exception& error) {
    return protocol::Result<std::vector<ArtifactBinding>>::failure(
        {protocol::ErrorCategory::cross_field, "$/discovery/publication",
         "S17-DISCOVERY-PUBLICATION", error.what()});
  }
}
} // namespace cpu_prefetch::runner::stage17
