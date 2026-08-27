#include "cpu_prefetch/runner/stage17_fixed_action.hpp"

#include "cpu_prefetch/calibration/calibration.hpp"
#include "cpu_prefetch/foundation/repository_info.hpp"
#include "cpu_prefetch/platform/platform.hpp"
#include "cpu_prefetch/platform/q15_msr.hpp"
#include "cpu_prefetch/queue/linked_spsc.hpp"
#include "cpu_prefetch/queue/ring_spsc.hpp"
#include "cpu_prefetch/runner/runner.hpp"
#include "cpu_prefetch/runner/software_prefetch.hpp"
#include "cpu_prefetch/storage/capture_backend.hpp"
#include "cpu_prefetch/timing/clock.hpp"
#include "cpu_prefetch/workload/packages.hpp"
#include "cpu_prefetch/workload/records.hpp"
#include "cpu_prefetch/workload/working_set.hpp"

#include <openssl/evp.h>

#include <algorithm>
#include <array>
#include <atomic>
#include <cerrno>
#include <charconv>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <ctime>
#include <fcntl.h>
#include <iomanip>
#include <limits>
#include <optional>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <sys/stat.h>
#include <thread>
#include <unistd.h>
#include <utility>
#include <vector>

namespace cpu_prefetch::runner::stage17 {
namespace {

using namespace std::string_view_literals;

using JsonArray = protocol::json::Value::Array;
using JsonObject = protocol::json::Value::Object;
using JsonValue = protocol::json::Value;

constexpr std::size_t kMaximumRequestBytes =
    static_cast<std::size_t>(16U) * 1024U * 1024U;
constexpr std::size_t kMaximumWorkerBytes =
    static_cast<std::size_t>(64U) * 1024U * 1024U;
constexpr std::size_t kCacheLineBytes = 64U;
constexpr std::string_view kResultFileName = "stage17-action-result-v2.json";

[[nodiscard]] auto make_error(protocol::ErrorCategory category, std::string path,
                              std::string rule, std::string message)
    -> protocol::ValidationError {
  return {category, std::move(path), std::move(rule), std::move(message)};
}

template <typename T>
[[nodiscard]] auto failure(std::string path, std::string rule, std::string message)
    -> protocol::Result<T> {
  return protocol::Result<T>::failure(make_error(protocol::ErrorCategory::cross_field,
                                                 std::move(path), std::move(rule),
                                                 std::move(message)));
}

[[nodiscard]] auto uint_value(std::uint64_t value) -> JsonValue {
  return JsonValue(protocol::json::Number{
      protocol::json::Number::Kind::unsigned_integer, std::to_string(value), value});
}

[[nodiscard]] auto string_value(std::string_view value) -> JsonValue {
  return JsonValue(std::string(value));
}

[[nodiscard]] auto member(const JsonObject& object, std::string_view name)
    -> const JsonValue* {
  const auto iterator = object.find(name);
  return iterator == object.end() ? nullptr : &iterator->second;
}

[[nodiscard]] auto string_member(const JsonObject& object, std::string_view name)
    -> const std::string* {
  const auto* value = member(object, name);
  return value == nullptr ? nullptr : value->as_string();
}

[[nodiscard]] auto bool_member(const JsonObject& object, std::string_view name) -> const
    bool* {
  const auto* value = member(object, name);
  return value == nullptr ? nullptr : value->as_bool();
}

[[nodiscard]] auto uint_member(const JsonObject& object, std::string_view name)
    -> std::optional<std::uint64_t> {
  const auto* value = member(object, name);
  if (value == nullptr) {
    return std::nullopt;
  }
  const auto* number = value->as_number();
  if (number == nullptr ||
      number->kind != protocol::json::Number::Kind::unsigned_integer) {
    return std::nullopt;
  }
  return std::get<std::uint64_t>(number->value);
}

[[nodiscard]] auto require_object(const JsonObject& object, std::string_view name)
    -> const JsonObject* {
  const auto* value = member(object, name);
  return value == nullptr ? nullptr : value->as_object();
}

[[nodiscard]] auto exact_fields(const JsonObject& object,
                                std::span<const std::string_view> expected) -> bool {
  if (object.size() != expected.size()) {
    return false;
  }
  return std::all_of(expected.begin(), expected.end(),
                     [&](std::string_view field) { return object.contains(field); });
}

[[nodiscard]] auto canonical(JsonObject object) -> protocol::Result<std::string> {
  return protocol::json::canonicalize(JsonValue(std::move(object)));
}

[[nodiscard]] auto sha256(std::span<const std::byte> bytes) -> std::string {
  std::array<unsigned char, 32U> digest{};
  unsigned int count = 0U;
  auto* context = EVP_MD_CTX_new();
  if (context == nullptr || EVP_DigestInit_ex(context, EVP_sha256(), nullptr) != 1 ||
      (!bytes.empty() && EVP_DigestUpdate(context, bytes.data(), bytes.size()) != 1) ||
      EVP_DigestFinal_ex(context, digest.data(), &count) != 1 ||
      count != digest.size()) {
    EVP_MD_CTX_free(context);
    throw std::runtime_error("SHA-256 failed");
  }
  EVP_MD_CTX_free(context);
  std::ostringstream output;
  output << std::hex << std::setfill('0');
  for (const auto value : digest) {
    output << std::setw(2) << static_cast<unsigned int>(value);
  }
  return output.str();
}

[[nodiscard]] auto sha256(std::string_view bytes) -> std::string {
  return sha256(std::span<const std::byte>(
      reinterpret_cast<const std::byte*>(bytes.data()), bytes.size()));
}

[[nodiscard]] auto utc_now() -> std::string {
  const auto now = std::chrono::system_clock::now();
  const auto seconds = std::chrono::time_point_cast<std::chrono::seconds>(now);
  const auto microseconds =
      std::chrono::duration_cast<std::chrono::microseconds>(now - seconds).count();
  const std::time_t raw = std::chrono::system_clock::to_time_t(seconds);
  std::tm value{};
  if (::gmtime_r(&raw, &value) == nullptr) {
    throw std::runtime_error("cannot convert system UTC");
  }
  std::ostringstream output;
  output << std::put_time(&value, "%Y-%m-%dT%H:%M:%S") << '.' << std::setw(6)
         << std::setfill('0') << microseconds << 'Z';
  return output.str();
}

[[nodiscard]] auto parse_fd(std::string_view value) -> std::optional<int> {
  int descriptor = -1;
  const auto [end, error] =
      std::from_chars(value.data(), value.data() + value.size(), descriptor, 10);
  if (error != std::errc{} || end != value.data() + value.size() || descriptor < 3) {
    return std::nullopt;
  }
  return descriptor;
}

[[nodiscard]] auto read_regular_fd(int descriptor,
                                   std::size_t maximum_bytes = kMaximumRequestBytes)
    -> protocol::Result<std::string> {
  struct stat metadata{};
  if (::fstat(descriptor, &metadata) != 0 || !S_ISREG(metadata.st_mode) ||
      metadata.st_size <= 0 ||
      static_cast<std::uintmax_t>(metadata.st_size) > maximum_bytes) {
    return failure<std::string>("$/request_fd", "S17-WORKER-REQUEST-FD",
                                "request fd is not a bounded regular file");
  }
  std::string bytes(static_cast<std::size_t>(metadata.st_size), '\0');
  std::size_t offset = 0U;
  while (offset < bytes.size()) {
    const auto count = ::pread(descriptor, bytes.data() + offset, bytes.size() - offset,
                               static_cast<off_t>(offset));
    if (count <= 0) {
      return failure<std::string>("$/request_fd", "S17-WORKER-REQUEST-READ",
                                  "request fd could not be read completely");
    }
    offset += static_cast<std::size_t>(count);
  }
  return protocol::Result<std::string>::success(bytes);
}

void validate_output_fd(int descriptor) {
  struct stat metadata{};
  if (::fstat(descriptor, &metadata) != 0 || !S_ISDIR(metadata.st_mode) ||
      metadata.st_uid != ::geteuid() || (metadata.st_mode & 0022) != 0) {
    throw std::runtime_error("output directory fd is unsafe");
  }
}

void write_exclusive(int directory_fd, std::string_view name,
                     std::span<const std::byte> bytes) {
  if (name.empty() || name == "." || name == ".." || name.find('/') != name.npos ||
      name.find('\0') != name.npos) {
    throw std::runtime_error("fixed output name is invalid");
  }
  const auto descriptor =
      ::openat(directory_fd, std::string(name).c_str(),
               O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0600);
  if (descriptor < 0) {
    throw std::runtime_error("cannot create fixed output create-exclusively");
  }
  try {
    std::size_t offset = 0U;
    while (offset < bytes.size()) {
      const auto count =
          ::write(descriptor, bytes.data() + offset, bytes.size() - offset);
      if (count <= 0) {
        throw std::runtime_error("cannot write fixed output completely");
      }
      offset += static_cast<std::size_t>(count);
    }
    if (::fsync(descriptor) != 0) {
      throw std::runtime_error("cannot fsync fixed output");
    }
  } catch (...) {
    static_cast<void>(::close(descriptor));
    throw;
  }
  if (::close(descriptor) != 0 || ::fsync(directory_fd) != 0) {
    throw std::runtime_error("cannot durably publish fixed output");
  }
}

[[nodiscard]] auto bytes(std::string value) -> std::vector<std::byte> {
  std::vector<std::byte> result(value.size());
  std::memcpy(result.data(), value.data(), value.size());
  return result;
}

[[nodiscard]] auto hex_u64(std::uint64_t value) -> std::string {
  std::ostringstream output;
  output << std::hex << std::setw(16) << std::setfill('0') << value;
  return output.str();
}

[[nodiscard]] auto q15_r(const JsonObject& input) -> protocol::Result<ActionOutcome> {
  constexpr std::array fields{"authorization_sha256"sv, "qualification_id"sv};
  if (!exact_fields(input, fields) ||
      string_member(input, "authorization_sha256") == nullptr ||
      string_member(input, "qualification_id") == nullptr) {
    return failure<ActionOutcome>("$/action_inputs", "S17-Q15R-INPUT",
                                  "Q15-R requires its exact fixed input family");
  }
  const auto identity = platform::read_x86_family_model();
  if (!identity || identity.value().family != platform::kIntelFamily6 ||
      identity.value().model != platform::kIntelModel55) {
    return failure<ActionOutcome>("$/action_inputs", "S17-Q15R-CPU",
                                  "Q15-R requires the accepted 06_55H CPU");
  }
  platform::SystemPosixFileOperations files;
  platform::LinuxHardwarePrefetchMsrBackend reader(files,
                                                   platform::FixedMsrAccess::read_only);
  JsonArray values;
  for (const auto cpu : platform::kHardwarePrefetchControlCpus) {
    const auto value = reader.read(cpu);
    if (!value) {
      return failure<ActionOutcome>("$/action_inputs", "S17-Q15R-MSR-READ",
                                    "fixed MSR prestate read failed");
    }
    values.emplace_back(
        JsonObject{{"cpu", uint_value(cpu)},
                   {"complete_value_hex", string_value(hex_u64(value.value()))}});
  }
  queue::RingSpscQueue ring({64U}, {kCacheLineBytes});
  lifecycle::TerminationControl termination({kCacheLineBytes});
  const auto atomics = ring.atomic_lock_free_evidence();
  const auto layout = ring.layout_evidence();
  const auto termination_evidence = termination.evidence();
  auto document = canonical(JsonObject{
      {"schema_version", string_value("cpu-prefetch-stage17-q15-r-output/2")},
      {"qualification_id", string_value(*string_member(input, "qualification_id"))},
      {"authorization_sha256",
       string_value(*string_member(input, "authorization_sha256"))},
      {"cpu_family", uint_value(identity.value().family)},
      {"cpu_model", uint_value(identity.value().model)},
      {"mapping_id", string_value(platform::kHardwarePrefetchMappingId)},
      {"prestate", JsonValue(std::move(values))},
      {"pointer_atomic_lock_free",
       JsonValue(atomics.always_lock_free && atomics.runtime_lock_free)},
      {"queue_layout_passed",
       JsonValue(layout.bases_aligned && layout.ownership_lines_separated)},
      {"termination_atomic_lock_free",
       JsonValue(termination_evidence.always_lock_free &&
                 termination_evidence.runtime_lock_free)},
      {"read_only", JsonValue(true)},
      {"complete", JsonValue(true)},
  });
  if (!document) {
    return protocol::Result<ActionOutcome>::failure(document.errors());
  }
  return protocol::Result<ActionOutcome>::success(
      {{{"Q15_R_READ_ONLY_PRESTATE", "cpu-prefetch-stage17-q15-r-output/2",
         "application/json", "q15-r-output-v2.json", bytes(document.value())}},
       false,
       false,
       "Q15_R_READ_ONLY_COMPLETE"});
}

[[nodiscard]] auto parse_prestate(const JsonObject& input)
    -> protocol::Result<std::array<platform::HardwarePrefetchMsrValue, 3U>> {
  const auto* value = member(input, "prestate");
  const auto* array = value == nullptr ? nullptr : value->as_array();
  if (array == nullptr || array->size() != 3U) {
    return failure<std::array<platform::HardwarePrefetchMsrValue, 3U>>(
        "$/action_inputs/prestate", "S17-Q15W-PRESTATE",
        "Q15-W requires three complete prestate values");
  }
  std::array<platform::HardwarePrefetchMsrValue, 3U> result{};
  for (std::size_t index = 0U; index < result.size(); ++index) {
    const auto* object = (*array)[index].as_object();
    if (object == nullptr ||
        uint_member(*object, "cpu") != platform::kHardwarePrefetchControlCpus[index]) {
      return failure<std::array<platform::HardwarePrefetchMsrValue, 3U>>(
          "$/action_inputs/prestate", "S17-Q15W-PRESTATE-CPU",
          "Q15-W prestate CPU order drifted");
    }
    const auto* text = string_member(*object, "complete_value_hex");
    std::uint64_t parsed = 0U;
    if (text == nullptr || text->size() != 16U) {
      return failure<std::array<platform::HardwarePrefetchMsrValue, 3U>>(
          "$/action_inputs/prestate", "S17-Q15W-PRESTATE-HEX",
          "Q15-W complete prestate must use fixed-width lowercase hex");
    }
    const auto [end, error] =
        std::from_chars(text->data(), text->data() + text->size(), parsed, 16);
    if (error != std::errc{} || end != text->data() + text->size()) {
      return failure<std::array<platform::HardwarePrefetchMsrValue, 3U>>(
          "$/action_inputs/prestate", "S17-Q15W-PRESTATE-HEX",
          "Q15-W complete prestate is malformed");
    }
    result[index] = {platform::kHardwarePrefetchControlCpus[index], parsed};
  }
  return protocol::Result<std::array<platform::HardwarePrefetchMsrValue, 3U>>::success(
      result);
}

[[nodiscard]] auto q15_w(const JsonObject& input) -> protocol::Result<ActionOutcome> {
  const auto prestate = parse_prestate(input);
  const auto* authorization = string_member(input, "authorization_sha256");
  const auto* probe = require_object(input, "probe_evidence");
  if (!prestate || authorization == nullptr || probe == nullptr ||
      string_member(*probe, "artifact_sha256") == nullptr ||
      string_member(*probe, "schema_identity") == nullptr ||
      bool_member(*probe, "regular_stream_accepted") == nullptr ||
      bool_member(*probe, "pointer_stream_accepted") == nullptr) {
    return failure<ActionOutcome>("$/action_inputs", "S17-Q15W-INPUT",
                                  "Q15-W fixed inputs are incomplete");
  }
  const auto plan = platform::make_hardware_prefetch_plan(
      {platform::kIntelFamily6, platform::kIntelModel55},
      protocol::RequestedHardwareState::h1, prestate.value());
  if (!plan) {
    return failure<ActionOutcome>("$/action_inputs/prestate", "S17-Q15W-PLAN",
                                  "Q15-W fixed plan is invalid");
  }
  platform::SystemPosixFileOperations writer_files;
  platform::SystemPosixFileOperations verifier_files;
  platform::LinuxHardwarePrefetchMsrBackend writer(
      writer_files, platform::FixedMsrAccess::read_write);
  platform::LinuxHardwarePrefetchMsrBackend verifier(
      verifier_files, platform::FixedMsrAccess::read_only);
  const auto report = platform::qualify_hardware_prefetch_plan(
      plan.value(), writer, verifier,
      {*bool_member(*probe, "regular_stream_accepted"),
       *bool_member(*probe, "pointer_stream_accepted")});
  JsonArray apply;
  JsonArray restore;
  for (const auto& value : report.apply_readback) {
    apply.emplace_back(
        JsonObject{{"cpu", uint_value(value.cpu)},
                   {"complete_value_hex", string_value(hex_u64(value.value))}});
  }
  for (const auto& value : report.restore_readback) {
    restore.emplace_back(
        JsonObject{{"cpu", uint_value(value.cpu)},
                   {"complete_value_hex", string_value(hex_u64(value.value))}});
  }
  auto document = canonical(JsonObject{
      {"schema_version", string_value("cpu-prefetch-stage17-q15-w-output/2")},
      {"authorization_sha256", string_value(*authorization)},
      {"probe_evidence_schema",
       string_value(*string_member(*probe, "schema_identity"))},
      {"probe_evidence_sha256",
       string_value(*string_member(*probe, "artifact_sha256"))},
      {"apply_readback", JsonValue(std::move(apply))},
      {"restore_readback", JsonValue(std::move(restore))},
      {"applied", JsonValue(report.applied)},
      {"verified", JsonValue(report.verified)},
      {"probes_passed", JsonValue(report.probes_passed)},
      {"restoration_verified", JsonValue(report.restored)},
      {"quarantined", JsonValue(report.quarantined)},
      {"complete",
       JsonValue(report.applied && report.verified && report.probes_passed &&
                 report.restored && !report.quarantined)},
  });
  if (!document) {
    return protocol::Result<ActionOutcome>::failure(document.errors());
  }
  const bool complete = report.applied && report.verified && report.probes_passed &&
                        report.restored && !report.quarantined;
  if (!complete) {
    return failure<ActionOutcome>("$/action_inputs", "S17-Q15W-TRANSACTION",
                                  "Q15-W failed closed after restoration attempt");
  }
  return protocol::Result<ActionOutcome>::success(
      {{{"Q15_W_TRANSACTION", "cpu-prefetch-stage17-q15-w-output/2", "application/json",
         "q15-w-output-v2.json", bytes(document.value())}},
       true,
       false,
       "Q15_W_RESTORED_COMPLETE"});
}

class PicosecondClock final {
public:
  PicosecondClock() : clock_(make_clock()) {}

  [[nodiscard]] auto read() noexcept -> timing::ClockReadResult {
    return clock_.read();
  }

  [[nodiscard]] auto read_ticks() noexcept -> lifecycle::TickRead {
    const auto reading = read();
    return {reading.status == timing::ClockReadStatus::ok,
            reading.status == timing::ClockReadStatus::ok
                ? reading.sample.relative_picoseconds
                : 0U};
  }

private:
  [[nodiscard]] static auto make_clock() -> timing::MonotonicRawClock {
    const auto origin = timing::MonotonicRawClock::capture_origin();
    if (origin.status != timing::ClockReadStatus::ok) {
      throw std::runtime_error("CLOCK_MONOTONIC_RAW origin failed");
    }
    return timing::MonotonicRawClock(timing::ClockOrigin{origin.absolute_nanoseconds});
  }

  timing::MonotonicRawClock clock_;
};

[[nodiscard]] auto load_sealed_runner_ticket(const JsonObject& input)
    -> protocol::Result<AdmissionTicket> {
  const auto* admission_object = require_object(input, "runner_admission");
  const auto* admission_sha = string_member(input, "runner_admission_sha256");
  const auto* evidence_sha = string_member(input, "runner_evidence_set_sha256");
  if (admission_object == nullptr || admission_sha == nullptr ||
      evidence_sha == nullptr) {
    return failure<AdmissionTicket>("$/action_inputs/runner_admission",
                                    "S17-RUN-ADMISSION",
                                    "sealed runner admission is absent");
  }
  const auto admission_document =
      protocol::json::canonicalize(JsonValue(*admission_object));
  if (!admission_document || sha256(admission_document.value()) != *admission_sha) {
    return failure<AdmissionTicket>("$/action_inputs/runner_admission",
                                    "S17-RUN-ADMISSION-HASH",
                                    "sealed runner admission bytes drifted");
  }
  const auto admission = load_admission(admission_document.value());
  if (!admission) {
    return protocol::Result<AdmissionTicket>::failure(admission.errors());
  }
  const int self_fd = ::open("/proc/self/exe", O_RDONLY | O_CLOEXEC);
  const auto self = self_fd >= 0
                        ? read_regular_fd(self_fd, kMaximumWorkerBytes)
                        : failure<std::string>("$/runner_admission", "S17-RUN-SELF",
                                               "fixed worker identity is unavailable");
  if (self_fd >= 0) {
    static_cast<void>(::close(self_fd));
  }
  if (!self || sha256(self.value()) != admission.value().binary_sha256) {
    return failure<AdmissionTicket>(
        "$/runner_admission/binary_sha256", "S17-RUN-BINARY",
        "runner admission does not bind the executing worker");
  }
  const auto repository = foundation::repository_info();
  const AdmissionTrustAnchor trust{
      std::string(repository.source_revision), admission.value().binary_sha256,
      admission.value().stand_id, admission.value().binding_id,
      repository.source_dirty};
  return admit_runner_from_sealed_controller(
      admission.value(), trust,
      {std::string(*admission_sha), std::string(*evidence_sha)});
}

[[nodiscard]] auto q16a(const JsonObject& input) -> protocol::Result<ActionOutcome> {
  constexpr std::array fields{"capacity"sv,
                              "sample_count"sv,
                              "calibration_plan_sha256"sv,
                              "seed_id"sv,
                              "seed_hex"sv,
                              "cache_line_bytes"sv,
                              "base_page_bytes"sv,
                              "runner_admission"sv,
                              "runner_admission_sha256"sv,
                              "runner_evidence_set_sha256"sv};
  const auto capacity = uint_member(input, "capacity");
  const auto samples = uint_member(input, "sample_count");
  const auto* plan_sha = string_member(input, "calibration_plan_sha256");
  const auto* seed_id = string_member(input, "seed_id");
  const auto* seed_hex = string_member(input, "seed_hex");
  const auto cache_line = uint_member(input, "cache_line_bytes");
  const auto base_page = uint_member(input, "base_page_bytes");
  if (!exact_fields(input, fields) || !capacity || !samples || *capacity < 8U ||
      *samples == 0U || seed_id == nullptr || seed_hex == nullptr ||
      seed_hex->size() != 64U || !cache_line || !base_page || *cache_line == 0U ||
      *base_page == 0U || *capacity > std::numeric_limits<std::size_t>::max() ||
      *samples > std::numeric_limits<std::size_t>::max() || plan_sha == nullptr) {
    return failure<ActionOutcome>("$/action_inputs", "S17-Q16A-INPUT",
                                  "Q16a fixed plan input is invalid");
  }
  const auto ticket = load_sealed_runner_ticket(input);
  if (!ticket || ticket.value().package() != protocol::QueuePackage::r0) {
    return ticket
               ? failure<ActionOutcome>("$/action_inputs/runner_admission/package",
                                        "S17-Q16A-TICKET",
                                        "Q16a requires the admitted R0 ring-off ticket")
               : protocol::Result<ActionOutcome>::failure(ticket.errors());
  }
  workload::EventArena arena({static_cast<std::size_t>(*capacity),
                              static_cast<std::size_t>(*cache_line),
                              static_cast<std::size_t>(*base_page),
                              workload::MasterSeed::from_hex(*seed_hex), *seed_id});
  queue::RingSpscQueue ring({static_cast<std::size_t>(*capacity)},
                            {static_cast<std::size_t>(*cache_line)});
  calibration::RingDemandTrace trace(static_cast<std::size_t>(*samples));
  PicosecondClock clock;
  std::atomic<std::uint64_t> phase{0U};
  std::atomic<bool> failed{false};
  LinuxCurrentThreadBindingBackend binding;
  X86CurrentCpuSoftwarePrefetchCapabilityBackend capability;
  const auto count = static_cast<std::size_t>(*samples);
  std::thread producer([&] {
    if (!binding.bind_and_verify(ticket.value().workers().producer_cpu).passes() ||
        !capability.observe().passes()) {
      failed.store(true, std::memory_order_release);
      return;
    }
    for (std::size_t index = 0U; index < count; ++index) {
      while (phase.load(std::memory_order_acquire) != index * 2U &&
             !failed.load(std::memory_order_acquire)) {
        X86PauseRelax{}.relax();
      }
      const auto selection = arena.select(workload::LogicalSequence{index});
      const auto pointer = queue::EventPointer::from(selection.record);
      if (!pointer ||
          calibration::capture_producer_ring_demand(clock, ring, *pointer, trace)
                  .outcome != calibration::RingAttemptOutcome::advanced) {
        failed.store(true, std::memory_order_release);
        return;
      }
      phase.fetch_add(1U, std::memory_order_release);
    }
  });
  std::thread consumer([&] {
    if (!binding.bind_and_verify(ticket.value().workers().consumer_cpu).passes() ||
        !capability.observe().passes()) {
      failed.store(true, std::memory_order_release);
      return;
    }
    for (std::size_t index = 0U; index < count; ++index) {
      while (phase.load(std::memory_order_acquire) != index * 2U + 1U &&
             !failed.load(std::memory_order_acquire)) {
        X86PauseRelax{}.relax();
      }
      if (failed.load(std::memory_order_acquire) ||
          calibration::capture_consumer_ring_demand(clock, ring, trace).outcome !=
              calibration::RingAttemptOutcome::advanced) {
        failed.store(true, std::memory_order_release);
        return;
      }
      phase.fetch_add(1U, std::memory_order_release);
    }
  });
  producer.join();
  consumer.join();
  if (failed.load(std::memory_order_acquire) ||
      phase.load(std::memory_order_acquire) != *samples * 2U) {
    return failure<ActionOutcome>("$/action_inputs", "S17-Q16A-CAPTURE",
                                  "Q16a affined ring-demand capture failed");
  }
  const auto& series = trace.series();
  const auto tick_array = [](const auto& ticks) {
    JsonArray values;
    values.reserve(ticks.size());
    for (const auto tick : ticks) {
      values.emplace_back(uint_value(tick));
    }
    return JsonValue(std::move(values));
  };
  auto document = canonical(JsonObject{
      {"schema_version", string_value("cpu-prefetch-stage17-q16a-output/2")},
      {"calibration_plan_sha256", string_value(*plan_sha)},
      {"seed_id", string_value(*seed_id)},
      {"sample_count", uint_value(*samples)},
      {"producer_demand_count", uint_value(series.producer_demand_ticks.size())},
      {"consumer_demand_count", uint_value(series.consumer_demand_ticks.size())},
      {"producer_issue_count", uint_value(series.producer_issue_ticks.size())},
      {"consumer_issue_count", uint_value(series.consumer_issue_ticks.size())},
      {"producer_full_count", uint_value(series.producer_full_count)},
      {"consumer_empty_count", uint_value(series.consumer_empty_count)},
      {"ring_off", JsonValue(true)},
      {"confirmatory_outcomes_accessed", JsonValue(false)},
      {"complete", JsonValue(true)},
  });
  if (!document) {
    return protocol::Result<ActionOutcome>::failure(document.errors());
  }
  auto trace_document = canonical(JsonObject{
      {"schema_version", string_value("cpu-prefetch-stage17-q16a-trace/2")},
      {"calibration_plan_sha256", string_value(*plan_sha)},
      {"seed_id", string_value(*seed_id)},
      {"producer_demand_ticks", tick_array(series.producer_demand_ticks)},
      {"consumer_demand_ticks", tick_array(series.consumer_demand_ticks)},
      {"producer_issue_ticks", tick_array(series.producer_issue_ticks)},
      {"consumer_issue_ticks", tick_array(series.consumer_issue_ticks)},
      {"producer_full_count", uint_value(series.producer_full_count)},
      {"consumer_empty_count", uint_value(series.consumer_empty_count)},
      {"ring_off", JsonValue(true)},
      {"confirmatory_outcomes_accessed", JsonValue(false)},
  });
  if (!trace_document) {
    return protocol::Result<ActionOutcome>::failure(trace_document.errors());
  }
  return protocol::Result<ActionOutcome>::success(
      {{{"Q16A_RING_DISTANCE_CAPTURE", "cpu-prefetch-stage17-q16a-output/2",
         "application/json", "q16a-output-v2.json", bytes(document.value())},
        {"Q16A_RING_DEMAND_TRACE", "cpu-prefetch-stage17-q16a-trace/2",
         "application/json", "q16a-trace-v2.json", bytes(trace_document.value())}},
       false,
       false,
       "Q16A_CAPTURE_COMPLETE"});
}

struct RunCapture final {
  lifecycle::MeasurementExecutionReport report;
  std::uint64_t checksum;
  std::vector<std::byte> producer_bytes;
  std::vector<std::byte> consumer_bytes;
};

struct CaptureGeometry final {
  std::span<const std::uint64_t> deadlines;
  std::uint64_t origin_ticks;
  std::uint64_t horizon_ticks;
  std::uint64_t duration_ticks;
  std::uint64_t maximum_attempts;
  std::size_t cache_line_bytes;
};

[[nodiscard]] auto uint_array_member(const JsonObject& object, std::string_view name)
    -> std::optional<std::vector<std::uint64_t>> {
  const auto* value = member(object, name);
  const auto* array = value == nullptr ? nullptr : value->as_array();
  if (array == nullptr) {
    return std::nullopt;
  }
  std::vector<std::uint64_t> result;
  result.reserve(array->size());
  for (const auto& item : *array) {
    const auto* number = item.as_number();
    if (number == nullptr ||
        number->kind != protocol::json::Number::Kind::unsigned_integer) {
      return std::nullopt;
    }
    result.push_back(std::get<std::uint64_t>(number->value));
  }
  return result;
}

[[nodiscard]] auto copy_bytes(std::span<const std::byte> source)
    -> std::vector<std::byte> {
  return {source.begin(), source.end()};
}

template <protocol::QueuePackage PackageKind, typename Package>
[[nodiscard]] auto capture_ticketed_run(const AdmissionTicket& ticket, Package& package,
                                        const workload::EventArena& arena,
                                        const protocol::RunId& run_id,
                                        const CaptureGeometry& geometry)
    -> protocol::Result<RunCapture> {
  try {
    storage::ProducerObservationStream producer(run_id, geometry.deadlines.size());
    storage::ConsumerObservationStream consumer(run_id, geometry.deadlines.size());
    workload::ConsumerState consumer_state{0U};
    PicosecondClock clock;
    storage::CapturingObservationBackend backend(clock, arena, package, consumer_state,
                                                 producer, consumer);
    lifecycle::TerminationControl termination({geometry.cache_line_bytes});
    LinuxCurrentThreadBindingBackend binding;
    X86CurrentCpuSoftwarePrefetchCapabilityBackend prefetch_capability;
    AffinedObservationPreparation preparation(binding, prefetch_capability,
                                              ticket.workers(), producer, consumer);
    const auto report = execute_static_prepared_measurement<PackageKind>(
        ticket, {geometry.deadlines, geometry.origin_ticks, geometry.horizon_ticks},
        clock, backend, termination, preparation);
    if (report.failure_phase != lifecycle::ExecutionFailurePhase::none ||
        report.failure_reason != lifecycle::ExecutionFailureReason::none ||
        !report.producer_completed || !report.consumer_drained ||
        report.accepted != report.consumed || !preparation.evidence().passes()) {
      producer.seal_incomplete();
      consumer.seal_incomplete();
      return failure<RunCapture>("$/action_inputs", "S17-RUN-LIFECYCLE",
                                 "ticketed lifecycle did not complete validly");
    }
    if (!producer.seal_complete() || !consumer.seal_complete()) {
      return failure<RunCapture>("$/action_inputs", "S17-RUN-SEAL",
                                 "raw observation streams could not be sealed");
    }
    const auto producer_snapshot = producer.snapshot();
    const auto consumer_snapshot = consumer.snapshot();
    return protocol::Result<RunCapture>::success({report, consumer_state.value,
                                                  copy_bytes(producer_snapshot.bytes),
                                                  copy_bytes(consumer_snapshot.bytes)});
  } catch (const std::exception&) {
    return failure<RunCapture>("$/action_inputs", "S17-RUN-EXECUTION",
                               "ticketed fixed run execution failed");
  }
}

template <protocol::QueuePackage PackageKind, typename Package>
[[nodiscard]] auto capture_ticketed_service_rate(const AdmissionTicket& ticket,
                                                 Package& package,
                                                 const workload::EventArena& arena,
                                                 const protocol::RunId& run_id,
                                                 const CaptureGeometry& geometry)
    -> protocol::Result<RunCapture> {
  try {
    storage::ProducerObservationStream producer(run_id, geometry.maximum_attempts);
    storage::ConsumerObservationStream consumer(run_id, geometry.maximum_attempts);
    workload::ConsumerState checksum{0U};
    PicosecondClock clock;
    storage::CapturingObservationBackend backend(clock, arena, package, checksum,
                                                 producer, consumer);
    lifecycle::TerminationControl termination({geometry.cache_line_bytes});
    LinuxCurrentThreadBindingBackend binding;
    X86CurrentCpuSoftwarePrefetchCapabilityBackend prefetch_capability;
    AffinedObservationPreparation preparation(binding, prefetch_capability,
                                              ticket.workers(), producer, consumer);
    lifecycle::WorkerStartBarrier barrier;
    std::atomic<bool> cancellation{false};
    std::atomic<bool> producer_failed{false};
    lifecycle::MeasurementExecutionReport report;
    std::thread producer_thread([&] {
      if (!preparation.prepare_producer() ||
          barrier.arrive(lifecycle::WorkerRole::producer) !=
              lifecycle::StartBarrierStatus::ready ||
          barrier.worker_wait(ticket.execution_limits().worker_start_poll_limit, [] {
            X86PauseRelax{}.relax();
          }) != lifecycle::StartBarrierStatus::released) {
        producer_failed.store(true, std::memory_order_release);
        cancellation.store(true, std::memory_order_release);
        termination.publish_arrivals_finished();
        return;
      }
      const auto origin = barrier.measurement_origin();
      std::uint64_t logical_sequence = 0U;
      std::uint64_t accepted_ordinal = 0U;
      while (!cancellation.load(std::memory_order_acquire)) {
        const auto reading = clock.read_ticks();
        if (!reading.ok || reading.ticks < origin ||
            geometry.duration_ticks >
                std::numeric_limits<std::uint64_t>::max() - origin) {
          producer_failed.store(true, std::memory_order_release);
          break;
        }
        if (reading.ticks - origin >= geometry.duration_ticks) {
          report.producer_completed = true;
          break;
        }
        if (logical_sequence >= geometry.maximum_attempts) {
          producer_failed.store(true, std::memory_order_release);
          break;
        }
        const auto attempt = backend.try_producer_attempt(
            {logical_sequence, reading.ticks - origin, accepted_ordinal});
        ++report.attempted;
        if (attempt.status != lifecycle::AttemptStatus::complete) {
          producer_failed.store(true, std::memory_order_release);
          break;
        }
        if (attempt.outcome == queue::EnqueueResult::accepted) {
          ++report.accepted;
          ++accepted_ordinal;
        } else {
          ++report.full;
        }
        ++logical_sequence;
      }
      termination.publish_arrivals_finished();
      report.arrivals_finished_published = true;
    });
    std::thread consumer_thread([&] {
      if (!preparation.prepare_consumer() ||
          barrier.arrive(lifecycle::WorkerRole::consumer) !=
              lifecycle::StartBarrierStatus::ready ||
          barrier.worker_wait(ticket.execution_limits().worker_start_poll_limit, [] {
            X86PauseRelax{}.relax();
          }) != lifecycle::StartBarrierStatus::released) {
        cancellation.store(true, std::memory_order_release);
        return;
      }
      while (true) {
        const auto polled = backend.try_consumer_poll(report.consumed);
        if (polled.status == lifecycle::ConsumerPollStatus::item) {
          ++report.consumed;
          continue;
        }
        if (polled.status == lifecycle::ConsumerPollStatus::failure) {
          cancellation.store(true, std::memory_order_release);
          break;
        }
        if (termination.arrivals_finished()) {
          report.consumer_drained = true;
          break;
        }
        X86PauseRelax{}.relax();
      }
    });
    const auto barrier_status =
        barrier.controller_wait(ticket.execution_limits().controller_start_poll_limit,
                                [] { X86PauseRelax{}.relax(); });
    const auto origin = clock.read_ticks();
    if (barrier_status != lifecycle::StartBarrierStatus::ready || !origin.ok ||
        barrier.release_with_measurement_origin(origin.ticks) !=
            lifecycle::StartBarrierStatus::released) {
      cancellation.store(true, std::memory_order_release);
      barrier.cancel();
    } else {
      report.measurement_origin_ticks = origin.ticks;
    }
    producer_thread.join();
    consumer_thread.join();
    if (cancellation.load(std::memory_order_acquire) ||
        producer_failed.load(std::memory_order_acquire) || !report.producer_completed ||
        !report.consumer_drained || report.accepted != report.consumed ||
        !preparation.evidence().passes()) {
      producer.seal_incomplete();
      consumer.seal_incomplete();
      return failure<RunCapture>(
          "$/action_inputs", "S17-Q16B-LIFECYCLE",
          "fixed-duration continuous-ready capture did not complete validly");
    }
    if (!producer.seal_complete() || !consumer.seal_complete()) {
      return failure<RunCapture>("$/action_inputs", "S17-Q16B-SEAL",
                                 "service-rate streams could not be sealed");
    }
    const auto producer_snapshot = producer.snapshot();
    const auto consumer_snapshot = consumer.snapshot();
    return protocol::Result<RunCapture>::success({report, checksum.value,
                                                  copy_bytes(producer_snapshot.bytes),
                                                  copy_bytes(consumer_snapshot.bytes)});
  } catch (const std::exception&) {
    return failure<RunCapture>("$/action_inputs", "S17-Q16B-EXECUTION",
                               "service-rate fixed action failed");
  }
}

template <protocol::QueuePackage PackageKind, typename Package>
[[nodiscard]] auto capture_by_mode(FixedAction action, const AdmissionTicket& ticket,
                                   Package& package, const workload::EventArena& arena,
                                   const protocol::RunId& run_id,
                                   const CaptureGeometry& geometry)
    -> protocol::Result<RunCapture> {
  if (action == FixedAction::q16b) {
    return capture_ticketed_service_rate<PackageKind>(ticket, package, arena, run_id,
                                                      geometry);
  }
  return capture_ticketed_run<PackageKind>(ticket, package, arena, run_id, geometry);
}

[[nodiscard]] auto package_capture(FixedAction action, const JsonObject& input)
    -> protocol::Result<RunCapture> {
  constexpr std::array fields{"capacity"sv,
                              "offered_count"sv,
                              "package"sv,
                              "d2_cache_lines"sv,
                              "plan_sha256"sv,
                              "schedule_sha256"sv,
                              "run_id"sv,
                              "seed_id"sv,
                              "seed_hex"sv,
                              "cache_line_bytes"sv,
                              "base_page_bytes"sv,
                              "runner_admission"sv,
                              "runner_admission_sha256"sv,
                              "runner_evidence_set_sha256"sv,
                              "schedule_deadline_ticks"sv,
                              "schedule_origin_ticks"sv,
                              "schedule_horizon_ticks"sv,
                              "duration_ticks"sv};
  const auto capacity = uint_member(input, "capacity");
  const auto events = uint_member(input, "offered_count");
  const auto* package_name = string_member(input, "package");
  const auto distance = uint_member(input, "d2_cache_lines");
  const auto* seed_id = string_member(input, "seed_id");
  const auto* seed_hex = string_member(input, "seed_hex");
  const auto cache_line = uint_member(input, "cache_line_bytes");
  const auto base_page = uint_member(input, "base_page_bytes");
  const auto* admission_object = require_object(input, "runner_admission");
  const auto* admission_sha = string_member(input, "runner_admission_sha256");
  const auto* evidence_sha = string_member(input, "runner_evidence_set_sha256");
  const auto deadlines = uint_array_member(input, "schedule_deadline_ticks");
  const auto schedule_origin = uint_member(input, "schedule_origin_ticks");
  const auto schedule_horizon = uint_member(input, "schedule_horizon_ticks");
  const auto duration = uint_member(input, "duration_ticks");
  if (!exact_fields(input, fields) || !capacity || !events || !distance ||
      package_name == nullptr || seed_id == nullptr || seed_hex == nullptr ||
      seed_hex->size() != 64U || !cache_line || !base_page || *cache_line == 0U ||
      *base_page == 0U || *capacity < 8U || *events == 0U ||
      *capacity > std::numeric_limits<std::size_t>::max() ||
      admission_object == nullptr || admission_sha == nullptr ||
      evidence_sha == nullptr || deadlines == std::nullopt || !schedule_origin ||
      !schedule_horizon || !duration || *duration == 0U ||
      ((action == FixedAction::q16b && !deadlines->empty()) ||
       (action != FixedAction::q16b && deadlines->size() != *events)) ||
      (action != FixedAction::q16b && *schedule_horizon == 0U)) {
    return failure<RunCapture>("$/action_inputs", "S17-RUN-INPUT",
                               "fixed run geometry is invalid");
  }
  const auto ticket = load_sealed_runner_ticket(input);
  if (!ticket) {
    return protocol::Result<RunCapture>::failure(ticket.errors());
  }
  const auto parsed_run_id =
      protocol::RunId::parse(*string_member(input, "run_id"), "$/action_inputs/run_id");
  if (!parsed_run_id) {
    return protocol::Result<RunCapture>::failure(parsed_run_id.errors());
  }
  const auto admitted_package_name = [&]() -> std::string_view {
    switch (ticket.value().package()) {
    case protocol::QueuePackage::r0:
      return "R0";
    case protocol::QueuePackage::r1:
      return "R1";
    case protocol::QueuePackage::r2:
      return "R2";
    case protocol::QueuePackage::l0:
      return "L0";
    case protocol::QueuePackage::l1:
      return "L1";
    case protocol::QueuePackage::nblfq_mpsc:
    case protocol::QueuePackage::not_applicable:
      return "";
    }
    return "";
  }();
  if (*package_name != admitted_package_name) {
    return failure<RunCapture>("$/action_inputs/package", "S17-RUN-TICKET",
                               "package differs from the admitted ticket");
  }
  try {
    const auto size = static_cast<std::size_t>(*capacity);
    workload::EventArena arena({size, static_cast<std::size_t>(*cache_line),
                                static_cast<std::size_t>(*base_page),
                                workload::MasterSeed::from_hex(*seed_hex), *seed_id});
    runner::X86RetainingPrefetchEmitter emitter;
    if (*package_name == "R0") {
      queue::RingSpscQueue queue({size}, {static_cast<std::size_t>(*cache_line)});
      workload::R0Package package(queue);
      return capture_by_mode<protocol::QueuePackage::r0>(
          action, ticket.value(), package, arena, parsed_run_id.value(),
          {*deadlines, *schedule_origin, *schedule_horizon, *duration, *events,
           static_cast<std::size_t>(*cache_line)});
    }
    if (*package_name == "R1") {
      queue::RingSpscQueue queue({size}, {static_cast<std::size_t>(*cache_line)});
      workload::R1Package package(
          queue, emitter,
          workload::ring_one_line_distance(
              {size, static_cast<std::size_t>(*cache_line), sizeof(void*)}));
      return capture_by_mode<protocol::QueuePackage::r1>(
          action, ticket.value(), package, arena, parsed_run_id.value(),
          {*deadlines, *schedule_origin, *schedule_horizon, *duration, *events,
           static_cast<std::size_t>(*cache_line)});
    }
    if (*package_name == "R2") {
      queue::RingSpscQueue queue({size}, {static_cast<std::size_t>(*cache_line)});
      const auto calibrated = workload::resolve_calibrated_ring_distance(
          {size, static_cast<std::size_t>(*cache_line), sizeof(void*)},
          static_cast<std::size_t>(*distance), "admitted-q16a-freeze");
      workload::R2Package package(queue, emitter, calibrated);
      return capture_by_mode<protocol::QueuePackage::r2>(
          action, ticket.value(), package, arena, parsed_run_id.value(),
          {*deadlines, *schedule_origin, *schedule_horizon, *duration, *events,
           static_cast<std::size_t>(*cache_line)});
    }
    workload::NodeOrderPlan order({size, static_cast<std::size_t>(*cache_line),
                                   static_cast<std::size_t>(*cache_line),
                                   static_cast<std::size_t>(*base_page)},
                                  workload::MasterSeed::from_hex(*seed_hex), *seed_id);
    if (*package_name == "L0") {
      queue::LinkedSpscQueue queue({size}, {static_cast<std::size_t>(*cache_line)},
                                   {static_cast<std::size_t>(*base_page)},
                                   order.order());
      workload::L0Package package(queue);
      return capture_by_mode<protocol::QueuePackage::l0>(
          action, ticket.value(), package, arena, parsed_run_id.value(),
          {*deadlines, *schedule_origin, *schedule_horizon, *duration, *events,
           static_cast<std::size_t>(*cache_line)});
    }
    if (*package_name == "L1") {
      queue::LinkedSpscQueue queue({size}, {static_cast<std::size_t>(*cache_line)},
                                   {static_cast<std::size_t>(*base_page)},
                                   order.order());
      workload::L1Package package(queue, emitter);
      return capture_by_mode<protocol::QueuePackage::l1>(
          action, ticket.value(), package, arena, parsed_run_id.value(),
          {*deadlines, *schedule_origin, *schedule_horizon, *duration, *events,
           static_cast<std::size_t>(*cache_line)});
    }
  } catch (const std::exception&) {
    return failure<RunCapture>("$/action_inputs", "S17-RUN-EXECUTION",
                               "fixed package execution failed");
  }
  return failure<RunCapture>("$/action_inputs/package", "S17-RUN-PACKAGE",
                             "fixed package is not one of the five Stage A packages");
}

[[nodiscard]] auto q16_or_pilot(FixedAction action, const JsonObject& input)
    -> protocol::Result<ActionOutcome> {
  auto capture = package_capture(action, input);
  const auto* plan = string_member(input, "plan_sha256");
  const auto* schedule = string_member(input, "schedule_sha256");
  const auto* run_id = string_member(input, "run_id");
  const auto* seed_id = string_member(input, "seed_id");
  const auto* admission = string_member(input, "runner_admission_sha256");
  const auto planned_attempt_capacity = uint_member(input, "offered_count");
  if (!capture) {
    return protocol::Result<ActionOutcome>::failure(capture.errors());
  }
  if (plan == nullptr || schedule == nullptr || run_id == nullptr ||
      seed_id == nullptr || admission == nullptr || !planned_attempt_capacity) {
    return failure<ActionOutcome>("$/action_inputs", "S17-RUN-LINEAGE",
                                  "fixed run lineage is incomplete");
  }
  const auto accepted = capture.value().report.accepted;
  const auto full = capture.value().report.full;
  const auto consumed = capture.value().report.consumed;
  const auto checksum = capture.value().checksum;
  const bool complete = accepted == consumed;
  const auto schema = action == FixedAction::q16b ? "cpu-prefetch-stage17-q16b-output/2"
                      : action == FixedAction::q16c
                          ? "cpu-prefetch-stage17-q16c-output/2"
                          : "cpu-prefetch-stage17-blinded-pilot-output/2";
  const auto role = action == FixedAction::q16b   ? "Q16B_SERVICE_RATE_CAPTURE"
                    : action == FixedAction::q16c ? "Q16C_ZERO_LOSS_FEASIBILITY_CAPTURE"
                                                  : "STAGE17_BLINDED_PILOT_RUN";
  const auto file = action == FixedAction::q16b ? "q16b-output-v2.json"
                    : action == FixedAction::q16c
                        ? "q16c-output-v2.json"
                        : "stage17-blinded-pilot-output-v2.json";
  auto document = canonical(JsonObject{
      {"schema_version", string_value(schema)},
      {"run_id", string_value(*run_id)},
      {"plan_sha256", string_value(*plan)},
      {"schedule_sha256", string_value(*schedule)},
      {"seed_id", string_value(*seed_id)},
      {"runner_admission_sha256", string_value(*admission)},
      {"package", string_value(*string_member(input, "package"))},
      {"planned_attempt_capacity", uint_value(*planned_attempt_capacity)},
      {"offered_count", uint_value(capture.value().report.attempted)},
      {"accepted_count", uint_value(accepted)},
      {"full_count", uint_value(full)},
      {"consumed_count", uint_value(consumed)},
      {"final_consumer_checksum", uint_value(checksum)},
      {"zero_loss", JsonValue(full == 0U)},
      {"exact_reconciliation_candidate", JsonValue(complete)},
      {"treatment_blind", JsonValue(true)},
      {"confirmatory_outcomes_accessed", JsonValue(false)},
      {"complete", JsonValue(complete)},
  });
  if (!document) {
    return protocol::Result<ActionOutcome>::failure(document.errors());
  }
  if (!complete) {
    return failure<ActionOutcome>("$/action_inputs", "S17-RUN-COUNT",
                                  "fixed run lost an accepted event");
  }
  std::vector<ArtifactPayload> artifacts;
  artifacts.push_back(
      {role, schema, "application/json", file, bytes(document.value())});
  artifacts.push_back({"PRODUCER_RAW_OBSERVATIONS", std::string(storage::kRawFormatId),
                       "application/octet-stream", "producer-raw-v1.bin",
                       std::move(capture.value().producer_bytes)});
  artifacts.push_back({"CONSUMER_RAW_OBSERVATIONS", std::string(storage::kRawFormatId),
                       "application/octet-stream", "consumer-raw-v1.bin",
                       std::move(capture.value().consumer_bytes)});
  return protocol::Result<ActionOutcome>::success(
      {std::move(artifacts), false, false,
       action == FixedAction::blinded_pilot ? "PILOT_RUN_COMPLETE"
                                            : "CALIBRATION_CAPTURE_COMPLETE"});
}

[[nodiscard]] auto validate_request(const JsonObject& request, FixedAction action,
                                    bool synthetic_backend)
    -> protocol::Result<const JsonObject*> {
  constexpr std::array fields{
      "schema_version"sv,  "request_id"sv,          "action_id"sv,
      "stand_id"sv,        "authorization_id"sv,    "attempt_id"sv,
      "runtime_binding"sv, "release_binding"sv,     "predecessor_resolutions"sv,
      "action_inputs"sv,   "synthetic_test_only"sv, "phase18_authority"sv,
  };
  if (!exact_fields(request, fields) ||
      string_member(request, "schema_version") == nullptr ||
      *string_member(request, "schema_version") != kFixedActionRequestSchema ||
      string_member(request, "action_id") == nullptr ||
      *string_member(request, "action_id") != to_string(action) ||
      string_member(request, "request_id") == nullptr ||
      string_member(request, "stand_id") == nullptr ||
      string_member(request, "authorization_id") == nullptr ||
      string_member(request, "attempt_id") == nullptr ||
      require_object(request, "runtime_binding") == nullptr ||
      require_object(request, "release_binding") == nullptr ||
      member(request, "predecessor_resolutions") == nullptr ||
      member(request, "predecessor_resolutions")->as_array() == nullptr ||
      bool_member(request, "synthetic_test_only") == nullptr ||
      *bool_member(request, "synthetic_test_only") != synthetic_backend ||
      bool_member(request, "phase18_authority") == nullptr ||
      *bool_member(request, "phase18_authority")) {
    return failure<const JsonObject*>("$", "S17-WORKER-REQUEST",
                                      "fixed action request contract drifted");
  }
  const auto* runtime = require_object(request, "runtime_binding");
  const auto runtime_size = uint_member(*runtime, "size_bytes");
  if (string_member(*runtime, "role") == nullptr ||
      *string_member(*runtime, "role") != kFixedActionWorkerRole ||
      string_member(*runtime, "profile") == nullptr ||
      *string_member(*runtime, "profile") != kFixedActionRuntimeProfile ||
      string_member(*runtime, "sha256") == nullptr || !runtime_size) {
    return failure<const JsonObject*>("$/runtime_binding", "S17-WORKER-RUNTIME",
                                      "runtime role/profile binding drifted");
  }
  const int self_fd = ::open("/proc/self/exe", O_RDONLY | O_CLOEXEC);
  struct stat metadata{};
  const auto actual =
      self_fd >= 0 ? read_regular_fd(self_fd, kMaximumWorkerBytes)
                   : failure<std::string>("$/runtime_binding", "S17-WORKER-SELF-OPEN",
                                          "executed worker could not be opened");
  if (self_fd >= 0) {
    static_cast<void>(::fstat(self_fd, &metadata));
    static_cast<void>(::close(self_fd));
  }
  const auto actual_sha256 = actual ? sha256(actual.value()) : std::string{};
  if (!actual || !S_ISREG(metadata.st_mode) ||
      actual_sha256 != *string_member(*runtime, "sha256") ||
      static_cast<std::uint64_t>(metadata.st_size) != *runtime_size) {
    return failure<const JsonObject*>(
        "$/runtime_binding", "S17-WORKER-SELF",
        "executed worker bytes differ from admission: actual=" + actual_sha256 +
            ", expected=" + *string_member(*runtime, "sha256"));
  }
  return protocol::Result<const JsonObject*>::success(
      require_object(request, "action_inputs"));
}

} // namespace

auto to_string(FixedAction action) noexcept -> std::string_view {
  switch (action) {
  case FixedAction::q15_r:
    return "Q15-R";
  case FixedAction::q15_w:
    return "Q15-W";
  case FixedAction::q16a:
    return "Q16a";
  case FixedAction::q16b:
    return "Q16b";
  case FixedAction::q16c:
    return "Q16c";
  case FixedAction::blinded_pilot:
    return "STAGE17-BLINDED-PILOT";
  }
  return "UNKNOWN";
}

auto parse_fixed_action(std::string_view value) -> protocol::Result<FixedAction> {
  for (const auto action :
       {FixedAction::q15_r, FixedAction::q15_w, FixedAction::q16a, FixedAction::q16b,
        FixedAction::q16c, FixedAction::blinded_pilot}) {
    if (to_string(action) == value) {
      return protocol::Result<FixedAction>::success(action);
    }
  }
  return failure<FixedAction>("$/action_id", "S17-WORKER-ACTION",
                              "unknown fixed Stage 17 action");
}

auto LinuxFixedActionOperations::execute(
    FixedAction action, const protocol::json::Value::Object& action_inputs)
    -> protocol::Result<ActionOutcome> {
  switch (action) {
  case FixedAction::q15_r:
    return q15_r(action_inputs);
  case FixedAction::q15_w:
    return q15_w(action_inputs);
  case FixedAction::q16a:
    return q16a(action_inputs);
  case FixedAction::q16b:
  case FixedAction::q16c:
  case FixedAction::blinded_pilot:
    return q16_or_pilot(action, action_inputs);
  }
  return failure<ActionOutcome>("$/action_id", "S17-WORKER-DISPATCH",
                                "fixed action dispatcher is incomplete");
}

auto run_fixed_action_worker(int argc, char** argv, FixedActionOperations& operations)
    -> int {
  if (argc != 10 || std::string_view(argv[1]) != "--execute-fixed-stage17-action-v2" ||
      std::string_view(argv[3]) != "--request-fd" ||
      std::string_view(argv[5]) != "--context-fd" ||
      std::string_view(argv[7]) != "--output-dir-fd" ||
      std::string_view(argv[9]) != "--fixed-dispatch-end") {
    throw std::runtime_error("fixed dispatcher argv contract rejected");
  }
  const auto action = parse_fixed_action(argv[2]);
  const auto request_fd = parse_fd(argv[4]);
  const auto context_fd = parse_fd(argv[6]);
  const auto output_fd = parse_fd(argv[8]);
  if (!action || !request_fd || !context_fd || !output_fd) {
    throw std::runtime_error("fixed dispatcher action/fd contract rejected");
  }
  validate_output_fd(*output_fd);
  const auto started_at = utc_now();
  const auto started = std::chrono::steady_clock::now();
  const auto request_bytes = read_regular_fd(*request_fd);
  if (!request_bytes) {
    throw std::runtime_error("fixed dispatcher request read failed");
  }
  const auto parsed = protocol::json::parse(request_bytes.value());
  if (!parsed || parsed.value().as_object() == nullptr) {
    throw std::runtime_error("fixed dispatcher request JSON rejected");
  }
  const auto& request = *parsed.value().as_object();
  const auto context_bytes = read_regular_fd(*context_fd);
  if (!context_bytes) {
    throw std::runtime_error("fixed dispatcher context read failed");
  }
  const auto parsed_context = protocol::json::parse(context_bytes.value());
  const auto* context = parsed_context && parsed_context.value().as_object() != nullptr
                            ? parsed_context.value().as_object()
                            : nullptr;
  constexpr std::array context_fields{
      "schema_version"sv, "authorization_id"sv, "authorization_sha256"sv,
      "request_id"sv,     "request_sha256"sv,   "attempt_id"sv,
      "action_id"sv,      "phase18_authority"sv};
  if (context == nullptr || !exact_fields(*context, context_fields) ||
      string_member(*context, "schema_version") == nullptr ||
      *string_member(*context, "schema_version") != kFixedActionContextSchema ||
      string_member(*context, "authorization_id") == nullptr ||
      string_member(*context, "authorization_sha256") == nullptr ||
      string_member(*context, "request_id") == nullptr ||
      string_member(*context, "request_sha256") == nullptr ||
      string_member(*context, "attempt_id") == nullptr ||
      string_member(*context, "action_id") == nullptr ||
      bool_member(*context, "phase18_authority") == nullptr ||
      *bool_member(*context, "phase18_authority") ||
      *string_member(*context, "authorization_id") !=
          *string_member(request, "authorization_id") ||
      *string_member(*context, "request_id") != *string_member(request, "request_id") ||
      *string_member(*context, "request_sha256") != sha256(request_bytes.value()) ||
      *string_member(*context, "attempt_id") != *string_member(request, "attempt_id") ||
      *string_member(*context, "action_id") != to_string(action.value())) {
    throw std::runtime_error("fixed dispatcher authority context rejected");
  }
  const auto inputs =
      validate_request(request, action.value(), operations.synthetic_test_only());
  if (!inputs) {
    throw std::runtime_error("fixed dispatcher request semantics rejected: " +
                             inputs.errors().front().rule_id + ": " +
                             inputs.errors().front().message);
  }
  const auto outcome = operations.execute(action.value(), *inputs.value());
  if (!outcome) {
    throw std::runtime_error(
        "fixed action operation failed closed: " + outcome.errors().front().rule_id +
        ": " + outcome.errors().front().message);
  }
  JsonArray artifact_bindings;
  for (const auto& artifact : outcome.value().artifacts) {
    write_exclusive(*output_fd, artifact.file_name, artifact.bytes);
    artifact_bindings.emplace_back(JsonObject{
        {"role", string_value(artifact.role)},
        {"schema_identity", string_value(artifact.schema_identity)},
        {"media_type", string_value(artifact.media_type)},
        {"file_name", string_value(artifact.file_name)},
        {"size_bytes", uint_value(artifact.bytes.size())},
        {"sha256", string_value(sha256(artifact.bytes))},
    });
  }
  const auto* runtime = require_object(request, "runtime_binding");
  const auto* release = require_object(request, "release_binding");
  const auto completed_at = utc_now();
  const auto duration = std::chrono::duration_cast<std::chrono::nanoseconds>(
                            std::chrono::steady_clock::now() - started)
                            .count();
  JsonObject result{
      {"schema_version", string_value(kFixedActionResultSchema)},
      {"result_id", string_value(*string_member(request, "attempt_id") + ":result")},
      {"request_id", string_value(*string_member(request, "request_id"))},
      {"request_sha256", string_value(sha256(request_bytes.value()))},
      {"action_id", string_value(to_string(action.value()))},
      {"stand_id", string_value(*string_member(request, "stand_id"))},
      {"authorization_id", string_value(*string_member(request, "authorization_id"))},
      {"authorization_sha256",
       string_value(*string_member(*context, "authorization_sha256"))},
      {"attempt_id", string_value(*string_member(request, "attempt_id"))},
      {"runtime_binding", JsonValue(*runtime)},
      {"release_binding", JsonValue(*release)},
      {"predecessor_resolutions",
       JsonValue(*member(request, "predecessor_resolutions")->as_array())},
      {"artifacts", JsonValue(std::move(artifact_bindings))},
      {"started_at_utc", string_value(started_at)},
      {"completed_at_utc", string_value(completed_at)},
      {"duration_ns", uint_value(static_cast<std::uint64_t>(duration))},
      {"terminal_state", string_value(outcome.value().terminal_state)},
      {"restoration_verified", JsonValue(outcome.value().restoration_verified)},
      {"quarantined", JsonValue(outcome.value().quarantined)},
      {"synthetic_test_only", JsonValue(operations.synthetic_test_only())},
      {"phase18_authority", JsonValue(false)},
  };
  const auto encoded = canonical(std::move(result));
  if (!encoded) {
    throw std::runtime_error("fixed action result serialization failed");
  }
  write_exclusive(*output_fd, kResultFileName, bytes(encoded.value()));
  return 0;
}

} // namespace cpu_prefetch::runner::stage17
