#include "cpu_prefetch/runner/stage17_fixed_action.hpp"

#include "cpu_prefetch/calibration/calibration.hpp"
#include "cpu_prefetch/foundation/repository_info.hpp"
#include "cpu_prefetch/platform/platform.hpp"
#include "cpu_prefetch/platform/q15_msr.hpp"
#include "cpu_prefetch/platform/q15_runtime.hpp"
#include "cpu_prefetch/queue/linked_spsc.hpp"
#include "cpu_prefetch/queue/ring_spsc.hpp"
#include "cpu_prefetch/reconciliation/reconciliation.hpp"
#include "cpu_prefetch/runner/runner.hpp"
#include "cpu_prefetch/runner/software_prefetch.hpp"
#include "cpu_prefetch/storage/artifacts.hpp"
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
#include <map>
#include <memory>
#include <optional>
#include <ranges>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <sys/socket.h>
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
constexpr std::string_view kResultFileName = "stage17-action-result-v3.json";

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

[[nodiscard]] auto is_sha256_hex(std::string_view value) noexcept -> bool {
  return value.size() == 64U && std::ranges::all_of(value, [](const char item) {
           return (item >= '0' && item <= '9') || (item >= 'a' && item <= 'f');
         });
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

class DirectoryArtifactSink final : public ArtifactSink {
public:
  explicit DirectoryArtifactSink(int directory_fd) noexcept
      : directory_fd_(directory_fd) {}

  [[nodiscard]] auto publish(ArtifactPayload artifact)
      -> protocol::Result<ArtifactBinding> override {
    try {
      const auto digest = sha256(artifact.bytes);
      const auto size = static_cast<std::uint64_t>(artifact.bytes.size());
      write_exclusive(directory_fd_, artifact.file_name, artifact.bytes);
      return protocol::Result<ArtifactBinding>::success(
          {std::move(artifact.role), std::move(artifact.schema_identity),
           std::move(artifact.media_type), std::move(artifact.file_name), size,
           digest});
    } catch (const std::exception& exception) {
      return failure<ArtifactBinding>("$/artifacts", "S17-ARTIFACT-PUBLISH",
                                      exception.what());
    }
  }

private:
  int directory_fd_;
};

[[nodiscard]] auto
publish_all(ArtifactSink& sink, std::vector<ArtifactPayload> payloads,
            bool restoration_verified, bool quarantined, std::string terminal_state)
    -> protocol::Result<ActionOutcome> {
  std::vector<ArtifactBinding> artifacts;
  artifacts.reserve(payloads.size());
  for (auto& payload : payloads) {
    auto published = sink.publish(std::move(payload));
    if (!published) {
      return protocol::Result<ActionOutcome>::failure(published.errors());
    }
    artifacts.push_back(std::move(published.value()));
  }
  return protocol::Result<ActionOutcome>::success({std::move(artifacts),
                                                   restoration_verified, quarantined,
                                                   std::move(terminal_state)});
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

struct Q15PhaseSession final {
  platform::LinuxQ15PlatformOperations platform;
  platform::LinuxQ15PerfOperations perf;
  std::unique_ptr<platform::Q15PreparedProbeMemory> memory;
  std::array<platform::HardwarePrefetchMsrValue, 3U> prestate{};
  std::optional<platform::Q15ProbePassObservation> h0_regular;
  std::optional<platform::Q15ProbePassObservation> h0_pointer;
  std::string session_id;
};

[[nodiscard]] auto probe_observation(const platform::Q15ProbePassObservation& value,
                                     const platform::Q15PreparedProbeMemory& memory)
    -> JsonValue {
  const auto integrity =
      value.integrity.content_unchanged() &&
      (value.kind == platform::Q15ProbeKind::regular_stream ||
       value.integrity.passes_pointer_cycle(value.integrity.counted_load_count));
  return JsonValue(JsonObject{
      {"counter_value", uint_value(value.counted.counter.all_pf_count)},
      {"minor_faults", uint_value(value.counted.minor_faults)},
      {"major_faults", uint_value(value.counted.major_faults)},
      {"cpu_verified", JsonValue(value.cpu_passes(memory.cpu()))},
      {"residency_verified",
       JsonValue(value.residency_passes(memory.numa_node(), memory.page_count()))},
      {"integrity_verified", JsonValue(integrity)},
  });
}

[[nodiscard]] auto assessed_probe(const platform::Q15ProbePassObservation& h0,
                                  const platform::Q15ProbePassObservation& h1,
                                  std::size_t line_count) -> JsonValue {
  const auto assessment = platform::evaluate_q15_probe_pair(
      h0.kind, h0.counted, h1.counted, h1.integrity, line_count);
  return JsonValue(JsonObject{
      {"counter_value", uint_value(h1.counted.counter.all_pf_count)},
      {"accepted", JsonValue(assessment.accepted)},
      {"integrity_verified", JsonValue(assessment.integrity_passed)},
  });
}

[[nodiscard]] auto load_q15_phase_session(const JsonObject& input)
    -> protocol::Result<std::shared_ptr<Q15PhaseSession>> {
  constexpr std::array fields{"authorization_sha256"sv, "qualification_id"sv,
                              "attempt_id"sv, "session_id"sv,
                              "probe_platform_binding"sv};
  const auto* binding = require_object(input, "probe_platform_binding");
  constexpr std::array binding_fields{"cpu"sv, "numa_node"sv,
                                      "verified_local_llc_bytes"sv,
                                      "verified_base_page_bytes"sv};
  const auto cpu = binding == nullptr ? std::optional<std::uint64_t>{}
                                      : uint_member(*binding, "cpu");
  const auto node = binding == nullptr ? std::optional<std::uint64_t>{}
                                       : uint_member(*binding, "numa_node");
  const auto llc = binding == nullptr
                       ? std::optional<std::uint64_t>{}
                       : uint_member(*binding, "verified_local_llc_bytes");
  const auto page = binding == nullptr
                        ? std::optional<std::uint64_t>{}
                        : uint_member(*binding, "verified_base_page_bytes");
  if (!exact_fields(input, fields) || binding == nullptr ||
      !exact_fields(*binding, binding_fields) || !cpu || !node || !llc || !page ||
      *cpu > std::numeric_limits<std::uint32_t>::max() ||
      *node > std::numeric_limits<std::uint32_t>::max() || *llc == 0U || *page == 0U ||
      string_member(input, "authorization_sha256") == nullptr ||
      string_member(input, "qualification_id") == nullptr ||
      string_member(input, "attempt_id") == nullptr ||
      string_member(input, "session_id") == nullptr) {
    return failure<std::shared_ptr<Q15PhaseSession>>(
        "$/action_inputs", "S17-Q15R-INPUT",
        "Q15-R requires its exact fixed session and platform binding");
  }
  const auto identity = platform::read_x86_family_model();
  if (!identity || identity.value().family != platform::kIntelFamily6 ||
      identity.value().model != platform::kIntelModel55) {
    return failure<std::shared_ptr<Q15PhaseSession>>(
        "$/action_inputs", "S17-Q15R-CPU", "Q15-R requires the accepted 06_55H CPU");
  }
  auto session = std::make_shared<Q15PhaseSession>();
  platform::SystemPosixFileOperations files;
  platform::LinuxHardwarePrefetchMsrBackend reader(files,
                                                   platform::FixedMsrAccess::read_only);
  for (std::size_t index = 0U; index < session->prestate.size(); ++index) {
    const auto selected_cpu = platform::kHardwarePrefetchControlCpus[index];
    const auto value = reader.read(selected_cpu);
    if (!value) {
      return failure<std::shared_ptr<Q15PhaseSession>>(
          "$/action_inputs", "S17-Q15R-MSR-READ", "fixed MSR prestate read failed");
    }
    session->prestate[index] = {selected_cpu, value.value()};
  }
  auto memory = platform::Q15PreparedProbeMemory::create(
      {static_cast<std::uint32_t>(*cpu), static_cast<std::uint32_t>(*node), *llc,
       *page},
      session->platform);
  if (!memory) {
    return failure<std::shared_ptr<Q15PhaseSession>>(
        "$/action_inputs/probe_platform_binding", "S17-Q15R-MEMORY",
        "private same-buffer mapping preparation failed");
  }
  session->memory = std::move(memory.value());
  session->session_id = *string_member(input, "session_id");
  auto regular =
      platform::run_q15_probe_pass(platform::Q15ProbeKind::regular_stream,
                                   *session->memory, session->perf, session->platform);
  if (!regular) {
    return failure<std::shared_ptr<Q15PhaseSession>>(
        "$/action_inputs/probe_platform_binding", "S17-Q15R-REGULAR-PROBE",
        "real H0 regular-stream probe failed");
  }
  auto pointer =
      platform::run_q15_probe_pass(platform::Q15ProbeKind::pointer_dependent,
                                   *session->memory, session->perf, session->platform);
  if (!pointer) {
    return failure<std::shared_ptr<Q15PhaseSession>>(
        "$/action_inputs/probe_platform_binding", "S17-Q15R-POINTER-PROBE",
        "real H0 pointer-stream probe failed");
  }
  session->h0_regular = std::move(regular.value());
  session->h0_pointer = std::move(pointer.value());
  return protocol::Result<std::shared_ptr<Q15PhaseSession>>::success(session);
}

[[nodiscard]] auto publish_q15_r(const JsonObject& input, Q15PhaseSession& session,
                                 ArtifactSink& sink)
    -> protocol::Result<ActionOutcome> {
  if (!session.h0_regular || !session.h0_pointer) {
    return failure<ActionOutcome>(
        "$/action_inputs/probe_platform_binding", "S17-Q15R-PROBE-MISSING",
        "Q15-R requires both completed H0 probe observations");
  }
  const auto& regular_observation = session.h0_regular.value();
  const auto& pointer_observation = session.h0_pointer.value();
  const auto observation_passes = [&session](const auto& observation) {
    return observation.counted.minor_faults == 0U &&
           observation.counted.major_faults == 0U &&
           observation.cpu_passes(session.memory->cpu()) &&
           observation.residency_passes(session.memory->numa_node(),
                                        session.memory->page_count()) &&
           observation.integrity.content_unchanged() &&
           (observation.kind == platform::Q15ProbeKind::regular_stream ||
            observation.integrity.passes_pointer_cycle(session.memory->line_count()));
  };
  if (!observation_passes(regular_observation) ||
      !observation_passes(pointer_observation)) {
    return failure<ActionOutcome>(
        "$/action_inputs/probe_platform_binding", "S17-Q15R-PROBE-EVIDENCE",
        "H0 probe affinity, residency, fault, or integrity evidence failed");
  }
  JsonArray values;
  for (const auto& value : session.prestate) {
    values.emplace_back(
        JsonObject{{"cpu", uint_value(value.cpu)},
                   {"complete_value_hex", string_value(hex_u64(value.value))}});
  }
  queue::RingSpscQueue ring({64U}, {kCacheLineBytes});
  lifecycle::TerminationControl termination({kCacheLineBytes});
  const auto atomics = ring.atomic_lock_free_evidence();
  const auto layout = ring.layout_evidence();
  const auto termination_evidence = termination.evidence();
  auto document = canonical(JsonObject{
      {"schema_version", string_value("cpu-prefetch-stage17-q15-r-output/3")},
      {"qualification_id", string_value(*string_member(input, "qualification_id"))},
      {"authorization_sha256",
       string_value(*string_member(input, "authorization_sha256"))},
      {"attempt_id", string_value(*string_member(input, "attempt_id"))},
      {"session_id", string_value(session.session_id)},
      {"cpu_family", uint_value(platform::kIntelFamily6)},
      {"cpu_model", uint_value(platform::kIntelModel55)},
      {"mapping_id", string_value(platform::kHardwarePrefetchMappingId)},
      {"prestate", JsonValue(std::move(values))},
      {"buffer_size_bytes", uint_value(session.memory->byte_count())},
      {"buffer_content_sha256", string_value(session.memory->prepared_sha256().hex())},
      {"regular_probe", probe_observation(regular_observation, *session.memory)},
      {"pointer_probe", probe_observation(pointer_observation, *session.memory)},
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
  return publish_all(
      sink,
      {{"Q15_R_READ_ONLY_PRESTATE", "cpu-prefetch-stage17-q15-r-output/3",
        "application/json", "q15-r-output-v3.json", bytes(document.value())}},
      false, false, "Q15_R_READ_ONLY_COMPLETE");
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

class PilotWholePlotControl final {
public:
  explicit PilotWholePlotControl(
      std::array<platform::HardwarePrefetchMsrValue, 3U> prestate)
      : prestate_(prestate),
        writer_(writer_files_, platform::FixedMsrAccess::read_write),
        verifier_(verifier_files_, platform::FixedMsrAccess::read_only) {
    apply_readback_.reserve(prestate_.size());
    restore_readback_.reserve(prestate_.size());
  }

  ~PilotWholePlotControl() noexcept { static_cast<void>(leave()); }

  PilotWholePlotControl(const PilotWholePlotControl&) = delete;
  auto operator=(const PilotWholePlotControl&) -> PilotWholePlotControl& = delete;

  [[nodiscard]] auto enter(std::string_view state) -> bool {
    if (entered_ || (state != "H0" && state != "H1")) {
      return false;
    }
    for (const auto& expected : prestate_) {
      const auto observed = verifier_.read(expected.cpu);
      if (!observed || observed.value() != expected.value) {
        return false;
      }
    }
    requested_state_ = std::string(state);
    if (state == "H1") {
      const auto plan = platform::make_hardware_prefetch_plan(
          {platform::kIntelFamily6, platform::kIntelModel55},
          protocol::RequestedHardwareState::h1, prestate_);
      if (!plan) {
        return false;
      }
      for (const auto& requested : plan.value().requested) {
        const auto applied = writer_.write(requested.cpu, requested.value);
        if (!applied.succeeded) {
          static_cast<void>(leave());
          return false;
        }
        written_.push_back(requested);
        const auto observed = verifier_.read(requested.cpu);
        if (!observed || observed.value() != requested.value) {
          static_cast<void>(leave());
          return false;
        }
        apply_readback_.push_back({requested.cpu, observed.value()});
      }
    }
    entered_ = true;
    return true;
  }

  // Operational callers check this result explicitly. The destructor invokes
  // the same path as a fail-stop fallback, so an unexpected exception must not
  // be converted into apparent restoration success.
  [[nodiscard]] auto leave() noexcept -> bool {
    bool restored = true;
    for (auto position = written_.rbegin(); position != written_.rend(); ++position) {
      const auto prior = std::ranges::find_if(prestate_, [position](const auto& value) {
        return value.cpu == position->cpu;
      });
      if (prior == prestate_.end()) {
        restored = false;
        continue;
      }
      const auto written = writer_.write(prior->cpu, prior->value);
      const auto observed = verifier_.read(prior->cpu);
      const auto* observed_value = observed.value_if();
      if (!written.succeeded || observed_value == nullptr ||
          *observed_value != prior->value) {
        restored = false;
      } else {
        restore_readback_.push_back({prior->cpu, *observed_value});
      }
    }
    if (entered_ && requested_state_ == "H0") {
      for (const auto& expected : prestate_) {
        const auto observed = verifier_.read(expected.cpu);
        const auto* observed_value = observed.value_if();
        if (observed_value == nullptr || *observed_value != expected.value) {
          restored = false;
        }
      }
    }
    entered_ = false;
    written_.clear();
    return restored;
  }

  [[nodiscard]] auto apply_readback() const noexcept
      -> std::span<const platform::HardwarePrefetchMsrValue> {
    return apply_readback_;
  }
  [[nodiscard]] auto restore_readback() const noexcept
      -> std::span<const platform::HardwarePrefetchMsrValue> {
    return restore_readback_;
  }

private:
  std::array<platform::HardwarePrefetchMsrValue, 3U> prestate_;
  platform::SystemPosixFileOperations writer_files_;
  platform::SystemPosixFileOperations verifier_files_;
  platform::LinuxHardwarePrefetchMsrBackend writer_;
  platform::LinuxHardwarePrefetchMsrBackend verifier_;
  std::vector<platform::HardwarePrefetchMsrValue> written_;
  std::vector<platform::HardwarePrefetchMsrValue> apply_readback_;
  std::vector<platform::HardwarePrefetchMsrValue> restore_readback_;
  std::string requested_state_;
  bool entered_{false};
};

[[nodiscard]] auto publish_calibration_hardware_evidence(
    ArtifactSink& sink, FixedAction action, std::string_view plan_sha,
    std::string_view q15_w_result_sha, std::size_t run_count,
    const PilotWholePlotControl& control) -> protocol::Result<ArtifactBinding> {
  JsonArray apply;
  for (const auto& value : control.apply_readback()) {
    apply.emplace_back(JsonObject{
        {"cpu", uint_value(value.cpu)},
        {"complete_value_hex", string_value(hex_u64(value.value))},
    });
  }
  JsonArray restore;
  for (const auto& value : control.restore_readback()) {
    restore.emplace_back(JsonObject{
        {"cpu", uint_value(value.cpu)},
        {"complete_value_hex", string_value(hex_u64(value.value))},
    });
  }
  const auto action_id = std::string(to_string(action));
  auto document = canonical(JsonObject{
      {"schema_version",
       string_value("cpu-prefetch-stage17-calibration-hardware-state/1")},
      {"action_id", string_value(action_id)},
      {"plan_sha256", string_value(plan_sha)},
      {"mapping_id", string_value(platform::kHardwarePrefetchMappingId)},
      {"q15_w_result_sha256", string_value(q15_w_result_sha)},
      {"whole_plot_order",
       JsonValue(JsonArray{string_value("H0"), string_value("H1")})},
      {"apply_readback", JsonValue(std::move(apply))},
      {"restore_readback", JsonValue(std::move(restore))},
      {"run_count", uint_value(run_count)},
      {"restoration_verified", JsonValue(true)},
      {"phase18_authority", JsonValue(false)},
  });
  if (!document) {
    return protocol::Result<ArtifactBinding>::failure(document.errors());
  }
  return sink.publish({
      "STAGE17_CALIBRATION_HARDWARE_STATE",
      "cpu-prefetch-stage17-calibration-hardware-state/1",
      "application/json",
      std::string("stage17-") + action_id + "-hardware-state-v1.json",
      bytes(document.value()),
  });
}

[[nodiscard]] auto q15_w(const JsonObject& input, Q15PhaseSession& session,
                         ArtifactSink& sink) -> protocol::Result<ActionOutcome> {
  constexpr std::array fields{"authorization_sha256"sv, "q15_r_attempt_sha256"sv,
                              "q15_r_result_sha256"sv, "session_id"sv, "prestate"sv};
  const auto prestate = parse_prestate(input);
  const auto* authorization = string_member(input, "authorization_sha256");
  const auto* q15_r_attempt = string_member(input, "q15_r_attempt_sha256");
  const auto* q15_r_result = string_member(input, "q15_r_result_sha256");
  const auto* session_id = string_member(input, "session_id");
  if (!exact_fields(input, fields) || !prestate || authorization == nullptr ||
      q15_r_attempt == nullptr || q15_r_result == nullptr || session_id == nullptr ||
      *session_id != session.session_id || prestate.value() != session.prestate ||
      session.memory == nullptr || !session.h0_regular || !session.h0_pointer ||
      workload::sha256(session.memory->bytes()) != session.memory->prepared_sha256()) {
    return failure<ActionOutcome>("$/action_inputs", "S17-Q15W-INPUT",
                                  "Q15-W requires the exact live Q15-R session");
  }
  platform::SystemPosixFileOperations live_files;
  platform::LinuxHardwarePrefetchMsrBackend live_reader(
      live_files, platform::FixedMsrAccess::read_only);
  for (const auto& expected : session.prestate) {
    const auto observed = live_reader.read(expected.cpu);
    if (!observed || observed.value() != expected.value) {
      return failure<ActionOutcome>(
          "$/action_inputs/prestate", "S17-Q15W-LIVE-PRESTATE",
          "live complete MSR prestate differs from sealed Q15-R evidence");
    }
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
  std::vector<platform::HardwarePrefetchMsrValue> written;
  std::vector<platform::HardwarePrefetchMsrValue> apply_readback;
  std::vector<platform::HardwarePrefetchMsrValue> restore_readback;
  bool apply_verified = true;
  for (const auto& requested : plan.value().requested) {
    const auto applied = writer.write(requested.cpu, requested.value);
    if (!applied.succeeded) {
      apply_verified = false;
      break;
    }
    written.push_back(requested);
    const auto observed = verifier.read(requested.cpu);
    if (!observed || observed.value() != requested.value) {
      apply_verified = false;
      break;
    }
    apply_readback.push_back({requested.cpu, observed.value()});
  }
  std::optional<platform::Q15ProbePassObservation> h1_regular;
  std::optional<platform::Q15ProbePassObservation> h1_pointer;
  if (apply_verified) {
    auto regular =
        platform::run_q15_probe_pass(platform::Q15ProbeKind::regular_stream,
                                     *session.memory, session.perf, session.platform);
    if (regular) {
      h1_regular = std::move(regular.value());
      auto pointer =
          platform::run_q15_probe_pass(platform::Q15ProbeKind::pointer_dependent,
                                       *session.memory, session.perf, session.platform);
      if (pointer) {
        h1_pointer = std::move(pointer.value());
      }
    }
  }
  bool restoration_verified = true;
  for (auto position = written.rbegin(); position != written.rend(); ++position) {
    const auto prior =
        std::ranges::find_if(session.prestate, [position](const auto& value) {
          return value.cpu == position->cpu;
        });
    if (prior == session.prestate.end()) {
      restoration_verified = false;
      continue;
    }
    const auto restored = writer.write(prior->cpu, prior->value);
    const auto observed = verifier.read(prior->cpu);
    if (!restored.succeeded || !observed || observed.value() != prior->value) {
      restoration_verified = false;
      continue;
    }
    restore_readback.push_back({prior->cpu, observed.value()});
  }
  restoration_verified =
      restoration_verified && restore_readback.size() == session.prestate.size();
  const bool regular_accepted =
      h1_regular.has_value() &&
      platform::evaluate_q15_probe_pair(
          platform::Q15ProbeKind::regular_stream, session.h0_regular->counted,
          h1_regular->counted, h1_regular->integrity, session.memory->line_count())
          .accepted;
  const bool pointer_accepted =
      h1_pointer.has_value() &&
      platform::evaluate_q15_probe_pair(
          platform::Q15ProbeKind::pointer_dependent, session.h0_pointer->counted,
          h1_pointer->counted, h1_pointer->integrity, session.memory->line_count())
          .accepted;
  JsonArray apply;
  JsonArray restore;
  for (const auto& value : apply_readback) {
    apply.emplace_back(
        JsonObject{{"cpu", uint_value(value.cpu)},
                   {"complete_value_hex", string_value(hex_u64(value.value))}});
  }
  for (const auto& value : restore_readback) {
    restore.emplace_back(
        JsonObject{{"cpu", uint_value(value.cpu)},
                   {"complete_value_hex", string_value(hex_u64(value.value))}});
  }
  auto document = canonical(JsonObject{
      {"schema_version", string_value("cpu-prefetch-stage17-q15-w-output/3")},
      {"authorization_sha256", string_value(*authorization)},
      {"q15_r_attempt_sha256", string_value(*q15_r_attempt)},
      {"q15_r_result_sha256", string_value(*q15_r_result)},
      {"session_id", string_value(*session_id)},
      {"live_prestate_matches", JsonValue(true)},
      {"apply_readback", JsonValue(std::move(apply))},
      {"regular_probe",
       h1_regular ? assessed_probe(*session.h0_regular, *h1_regular,
                                   session.memory->line_count())
                  : JsonValue(JsonObject{{"counter_value", uint_value(0U)},
                                         {"accepted", JsonValue(false)},
                                         {"integrity_verified", JsonValue(false)}})},
      {"pointer_probe",
       h1_pointer ? assessed_probe(*session.h0_pointer, *h1_pointer,
                                   session.memory->line_count())
                  : JsonValue(JsonObject{{"counter_value", uint_value(0U)},
                                         {"accepted", JsonValue(false)},
                                         {"integrity_verified", JsonValue(false)}})},
      {"restore_readback", JsonValue(std::move(restore))},
      {"restoration_verified", JsonValue(restoration_verified)},
      {"quarantine_operation",
       JsonValue(JsonObject{{"performed", JsonValue(false)},
                            {"reason", string_value("RESTORATION_VERIFIED")}})},
      {"complete", JsonValue(apply_verified && regular_accepted && pointer_accepted &&
                             restoration_verified)},
  });
  if (!document) {
    return protocol::Result<ActionOutcome>::failure(document.errors());
  }
  const bool complete =
      apply_verified && regular_accepted && pointer_accepted && restoration_verified;
  if (!complete) {
    return failure<ActionOutcome>("$/action_inputs", "S17-Q15W-TRANSACTION",
                                  "Q15-W failed closed after restoration attempt");
  }
  return publish_all(
      sink,
      {{"Q15_W_TRANSACTION", "cpu-prefetch-stage17-q15-w-output/3", "application/json",
        "q15-w-output-v3.json", bytes(document.value())}},
      true, false, "Q15_W_RESTORED_COMPLETE");
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
  const auto* evidence_value = member(*admission_object, "evidence");
  const auto evidence_document =
      evidence_value == nullptr
          ? protocol::Result<std::string>::failure(
                make_error(protocol::ErrorCategory::missing_field,
                           "$/action_inputs/runner_admission/evidence",
                           "S17-RUN-EVIDENCE-SET", "runner evidence family is absent"))
          : protocol::json::canonicalize(*evidence_value);
  if (!admission_document || !evidence_document ||
      sha256(admission_document.value()) != *admission_sha ||
      sha256(evidence_document.value()) != *evidence_sha) {
    return failure<AdmissionTicket>("$/action_inputs/runner_admission",
                                    "S17-RUN-ADMISSION-HASH",
                                    "sealed runner admission/evidence bytes drifted");
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

[[nodiscard]] auto q16a_capture(const JsonObject& input, const std::string& prefix)
    -> protocol::Result<std::vector<ArtifactPayload>> {
  constexpr std::array fields{"capacity"sv,
                              "sample_count"sv,
                              "calibration_plan_sha256"sv,
                              "seed_id"sv,
                              "seed_hex"sv,
                              "cache_line_bytes"sv,
                              "base_page_bytes"sv,
                              "runner_admission"sv,
                              "runner_admission_sha256"sv,
                              "runner_evidence_set_sha256"sv,
                              "context_ordinal"sv,
                              "repetition_ordinal"sv,
                              "hardware_state"sv,
                              "placement"sv,
                              "working_set_class"sv};
  const auto capacity = uint_member(input, "capacity");
  const auto samples = uint_member(input, "sample_count");
  const auto* plan_sha = string_member(input, "calibration_plan_sha256");
  const auto* seed_id = string_member(input, "seed_id");
  const auto* seed_hex = string_member(input, "seed_hex");
  const auto cache_line = uint_member(input, "cache_line_bytes");
  const auto base_page = uint_member(input, "base_page_bytes");
  const auto context = uint_member(input, "context_ordinal");
  const auto repetition = uint_member(input, "repetition_ordinal");
  const auto* hardware_state = string_member(input, "hardware_state");
  const auto* placement = string_member(input, "placement");
  const auto* working_set = string_member(input, "working_set_class");
  if (!exact_fields(input, fields) || !capacity || !samples || *capacity < 8U ||
      *samples == 0U || seed_id == nullptr || seed_hex == nullptr ||
      seed_hex->size() != 64U || !cache_line || !base_page || *cache_line == 0U ||
      *base_page == 0U || *capacity > std::numeric_limits<std::size_t>::max() ||
      *samples > std::numeric_limits<std::size_t>::max() || plan_sha == nullptr ||
      !context || *context >= 12U || !repetition || hardware_state == nullptr ||
      (*hardware_state != "H0" && *hardware_state != "H1") || placement == nullptr ||
      (*placement != "NEAR" && *placement != "FAR") || working_set == nullptr ||
      (*working_set != "L2_RESIDENT" && *working_set != "LLC_RESIDENT" &&
       *working_set != "BEYOND_LLC")) {
    return failure<std::vector<ArtifactPayload>>("$/action_inputs", "S17-Q16A-INPUT",
                                                 "Q16a fixed plan input is invalid");
  }
  const auto ticket = load_sealed_runner_ticket(input);
  if (!ticket || ticket.value().package() != protocol::QueuePackage::r0) {
    return ticket ? failure<std::vector<ArtifactPayload>>(
                        "$/action_inputs/runner_admission/package", "S17-Q16A-TICKET",
                        "Q16a requires the admitted R0 ring-off ticket")
                  : protocol::Result<std::vector<ArtifactPayload>>::failure(
                        ticket.errors());
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
    return failure<std::vector<ArtifactPayload>>(
        "$/action_inputs", "S17-Q16A-CAPTURE",
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
      {"schema_version", string_value("cpu-prefetch-stage17-q16a-output/3")},
      {"calibration_plan_sha256", string_value(*plan_sha)},
      {"seed_id", string_value(*seed_id)},
      {"context_ordinal", uint_value(*context)},
      {"repetition_ordinal", uint_value(*repetition)},
      {"hardware_state", string_value(*string_member(input, "hardware_state"))},
      {"placement", string_value(*string_member(input, "placement"))},
      {"working_set_class", string_value(*string_member(input, "working_set_class"))},
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
    return protocol::Result<std::vector<ArtifactPayload>>::failure(document.errors());
  }
  auto trace_document = canonical(JsonObject{
      {"schema_version", string_value("cpu-prefetch-stage17-q16a-trace/3")},
      {"calibration_plan_sha256", string_value(*plan_sha)},
      {"seed_id", string_value(*seed_id)},
      {"context_ordinal", uint_value(*context)},
      {"repetition_ordinal", uint_value(*repetition)},
      {"hardware_state", string_value(*string_member(input, "hardware_state"))},
      {"placement", string_value(*string_member(input, "placement"))},
      {"working_set_class", string_value(*string_member(input, "working_set_class"))},
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
    return protocol::Result<std::vector<ArtifactPayload>>::failure(
        trace_document.errors());
  }
  return protocol::Result<std::vector<ArtifactPayload>>::success(
      {{"Q16A_RING_DISTANCE_CAPTURE", "cpu-prefetch-stage17-q16a-output/3",
        "application/json", prefix + "output-v3.json", bytes(document.value())},
       {"Q16A_RING_DEMAND_TRACE", "cpu-prefetch-stage17-q16a-trace/3",
        "application/json", prefix + "trace-v3.json", bytes(trace_document.value())}});
}

[[nodiscard]] auto q16a_plan(const JsonObject& input, ArtifactSink& sink)
    -> protocol::Result<ActionOutcome> {
  constexpr std::array fields{"plan_sha256"sv, "hardware_control"sv, "captures"sv};
  constexpr std::array hardware_fields{"mapping_id"sv, "q15_w_result_sha256"sv,
                                       "prestate"sv};
  const auto* plan_sha = string_member(input, "plan_sha256");
  const auto* hardware_control = require_object(input, "hardware_control");
  const auto hardware_prestate =
      hardware_control == nullptr
          ? failure<std::array<platform::HardwarePrefetchMsrValue, 3U>>(
                "$/action_inputs/hardware_control", "S17-Q16A-HARDWARE",
                "Q16a hardware-control binding is absent")
          : parse_prestate(*hardware_control);
  const auto* captures_value = member(input, "captures");
  const auto* captures =
      captures_value == nullptr ? nullptr : captures_value->as_array();
  if (!exact_fields(input, fields) || plan_sha == nullptr || captures == nullptr ||
      captures->empty() || hardware_control == nullptr ||
      !exact_fields(*hardware_control, hardware_fields) || !hardware_prestate ||
      string_member(*hardware_control, "mapping_id") == nullptr ||
      *string_member(*hardware_control, "mapping_id") !=
          platform::kHardwarePrefetchMappingId ||
      string_member(*hardware_control, "q15_w_result_sha256") == nullptr) {
    return failure<ActionOutcome>("$/action_inputs", "S17-Q16A-PLAN-FAMILY",
                                  "Q16a requires one frozen capture family");
  }
  const std::set<std::string> states{"H0", "H1"};
  const std::set<std::string> placements{"NEAR", "FAR"};
  const std::set<std::string> working_sets{"L2_RESIDENT", "LLC_RESIDENT", "BEYOND_LLC"};
  std::map<std::string, std::size_t> per_context;
  std::set<std::string> run_ids;
  std::vector<ArtifactBinding> bindings;
  bindings.reserve(captures->size() * 2U + 1U);
  PilotWholePlotControl whole_plot_control(hardware_prestate.value());
  std::string active_state;
  std::set<std::string> completed_states;
  for (std::size_t index = 0U; index < captures->size(); ++index) {
    const auto* capture = (*captures)[index].as_object();
    const auto* state =
        capture == nullptr ? nullptr : string_member(*capture, "hardware_state");
    const auto* placement =
        capture == nullptr ? nullptr : string_member(*capture, "placement");
    const auto* working_set =
        capture == nullptr ? nullptr : string_member(*capture, "working_set_class");
    const auto* run_id =
        capture == nullptr ? nullptr : string_member(*capture, "seed_id");
    const auto context = capture == nullptr ? std::optional<std::uint64_t>{}
                                            : uint_member(*capture, "context_ordinal");
    const auto repetition = capture == nullptr
                                ? std::optional<std::uint64_t>{}
                                : uint_member(*capture, "repetition_ordinal");
    if (capture == nullptr || state == nullptr || !states.contains(*state) ||
        placement == nullptr || !placements.contains(*placement) ||
        working_set == nullptr || !working_sets.contains(*working_set) ||
        run_id == nullptr || !run_ids.insert(*run_id).second || !context ||
        *context >= 12U || !repetition ||
        string_member(*capture, "calibration_plan_sha256") == nullptr ||
        *string_member(*capture, "calibration_plan_sha256") != *plan_sha) {
      return failure<ActionOutcome>("$/action_inputs/captures",
                                    "S17-Q16A-CAPTURE-FAMILY",
                                    "Q16a capture context/lineage is invalid");
    }
    if (active_state != *state) {
      if (!active_state.empty()) {
        if (!whole_plot_control.leave()) {
          return failure<ActionOutcome>(
              "$/action_inputs/hardware_control", "S17-Q16A-RESTORE",
              "Q16a prior hardware whole plot could not be restored");
        }
        completed_states.insert(active_state);
      }
      if (completed_states.contains(*state) || !whole_plot_control.enter(*state)) {
        return failure<ActionOutcome>("$/action_inputs/hardware_control",
                                      "S17-Q16A-HARDWARE-ENTER",
                                      "Q16a hardware whole-plot order/readback failed");
      }
      active_state = *state;
    }
    const auto key = *state + "/" + *placement + "/" + *working_set;
    ++per_context[key];
    auto payloads = q16a_capture(*capture, [&] {
      std::ostringstream stream;
      stream << "q16a-c" << std::setw(2) << std::setfill('0') << *context << "-r"
             << std::setw(3) << *repetition << '-';
      return stream.str();
    }());
    if (!payloads) {
      return protocol::Result<ActionOutcome>::failure(payloads.errors());
    }
    for (auto& payload : payloads.value()) {
      auto published = sink.publish(std::move(payload));
      if (!published) {
        return protocol::Result<ActionOutcome>::failure(published.errors());
      }
      bindings.push_back(std::move(published.value()));
    }
  }
  if (per_context.size() != 12U ||
      std::any_of(per_context.begin(), per_context.end(),
                  [](const auto& item) { return item.second < 59U; })) {
    return failure<ActionOutcome>("$/action_inputs/captures", "S17-Q16A-MATRIX",
                                  "Q16a six-context/two-state matrix is incomplete");
  }
  if (!whole_plot_control.leave()) {
    return failure<ActionOutcome>(
        "$/action_inputs/hardware_control", "S17-Q16A-FINAL-RESTORE",
        "Q16a final hardware whole plot could not be restored");
  }
  auto hardware = publish_calibration_hardware_evidence(
      sink, FixedAction::q16a, *plan_sha,
      *string_member(*hardware_control, "q15_w_result_sha256"), captures->size(),
      whole_plot_control);
  if (!hardware) {
    return protocol::Result<ActionOutcome>::failure(hardware.errors());
  }
  bindings.push_back(std::move(hardware.value()));
  return protocol::Result<ActionOutcome>::success(
      {std::move(bindings), true, false, "Q16A_CAPTURE_COMPLETE"});
}

struct RunCapture final {
  lifecycle::MeasurementExecutionReport report;
  lifecycle::MeasurementExecutionReport warmup_report;
  std::uint64_t checksum;
  std::vector<std::byte> producer_bytes;
  std::vector<std::byte> consumer_bytes;
  workload::Sha256Digest event_records_pre;
  workload::Sha256Digest event_records_post;
  workload::Sha256Digest ordered_index;
  workload::Sha256Digest address_delta;
  std::vector<std::uint64_t> expected_record_indices;
  bool warmup_reset_verified;
  AffinedPreparationEvidence affinity;
  platform::Q15ResidencySnapshot residency_before;
  platform::Q15ResidencySnapshot residency_during;
  platform::Q15ResidencySnapshot residency_after;
  std::uint32_t expected_numa_node;
};

struct PlatformEventMemoryConfig final {
  std::size_t byte_count;
  std::uint32_t node;
};

class PlatformEventMemory final {
public:
  explicit PlatformEventMemory(PlatformEventMemoryConfig config)
      : byte_count_(config.byte_count), node_(config.node) {
    auto mapped = operations_.map_private_anonymous(byte_count_);
    if (!mapped) {
      throw std::runtime_error("event mapping failed");
    }
    address_ = mapped.value();
    if (!operations_.bind_memory({address_, byte_count_, node_}).succeeded ||
        !operations_.disable_transparent_huge_pages(address_, byte_count_).succeeded) {
      static_cast<void>(operations_.unmap(address_, byte_count_));
      address_ = nullptr;
      throw std::runtime_error("event mapping NUMA/page policy failed");
    }
  }

  ~PlatformEventMemory() {
    if (address_ != nullptr) {
      static_cast<void>(operations_.unmap(address_, byte_count_));
    }
  }

  PlatformEventMemory(const PlatformEventMemory&) = delete;
  auto operator=(const PlatformEventMemory&) -> PlatformEventMemory& = delete;

  [[nodiscard]] auto bytes() const noexcept -> std::span<std::byte> {
    return {address_, byte_count_};
  }
  [[nodiscard]] auto operations() noexcept -> platform::LinuxQ15PlatformOperations& {
    return operations_;
  }
  [[nodiscard]] auto node() const noexcept -> std::uint32_t { return node_; }

private:
  platform::LinuxQ15PlatformOperations operations_;
  std::byte* address_{nullptr};
  std::size_t byte_count_{0U};
  std::uint32_t node_{0U};
};

struct PilotPersistentContextConfig final {
  std::size_t capacity;
  std::size_t cache_line_bytes;
  std::size_t base_page_bytes;
  std::uint32_t node;
  std::string seed_hex;
  std::string seed_id;
};

class PilotPersistentContext final {
public:
  explicit PilotPersistentContext(PilotPersistentContextConfig config)
      : capacity_(config.capacity), cache_line_bytes_(config.cache_line_bytes),
        base_page_bytes_(config.base_page_bytes), node_(config.node),
        seed_hex_(std::move(config.seed_hex)), seed_id_(std::move(config.seed_id)),
        memory_({capacity_ * cache_line_bytes_, node_}),
        arena_({capacity_, cache_line_bytes_, base_page_bytes_,
                workload::MasterSeed::from_hex(seed_hex_), seed_id_},
               memory_.bytes()),
        ring_({capacity_}, {cache_line_bytes_}),
        order_({capacity_, cache_line_bytes_, cache_line_bytes_, base_page_bytes_},
               workload::MasterSeed::from_hex(seed_hex_), seed_id_),
        linked_({capacity_}, {cache_line_bytes_}, {base_page_bytes_}, order_.order()) {}

  PilotPersistentContext(const PilotPersistentContext&) = delete;
  auto operator=(const PilotPersistentContext&) -> PilotPersistentContext& = delete;

  [[nodiscard]] auto matches(std::size_t capacity, std::size_t cache_line_bytes,
                             std::size_t base_page_bytes, std::uint32_t node,
                             std::string_view seed_hex,
                             std::string_view seed_id) const noexcept -> bool {
    return capacity_ == capacity && cache_line_bytes_ == cache_line_bytes &&
           base_page_bytes_ == base_page_bytes && node_ == node &&
           seed_hex_ == seed_hex && seed_id_ == seed_id;
  }
  [[nodiscard]] auto arena() noexcept -> workload::EventArena& { return arena_; }
  [[nodiscard]] auto ring() noexcept -> queue::RingSpscQueue& { return ring_; }
  [[nodiscard]] auto linked() noexcept -> queue::LinkedSpscQueue& { return linked_; }
  [[nodiscard]] auto operations() noexcept -> platform::LinuxQ15PlatformOperations& {
    return memory_.operations();
  }

private:
  std::size_t capacity_;
  std::size_t cache_line_bytes_;
  std::size_t base_page_bytes_;
  std::uint32_t node_;
  std::string seed_hex_;
  std::string seed_id_;
  PlatformEventMemory memory_;
  workload::EventArena arena_;
  queue::RingSpscQueue ring_;
  workload::NodeOrderPlan order_;
  queue::LinkedSpscQueue linked_;
};

using PilotPersistentContexts =
    std::map<std::string, std::unique_ptr<PilotPersistentContext>>;

class PilotObservationPreparation final {
public:
  PilotObservationPreparation(CurrentThreadBindingBackend& binding_backend,
                              CurrentCpuSoftwarePrefetchCapabilityBackend& capability,
                              WorkerPair workers,
                              storage::ProducerObservationStream& producer,
                              storage::ConsumerObservationStream& consumer,
                              platform::Q15PlatformOperations& platform,
                              const workload::EventArena& arena,
                              std::uint32_t expected_node) noexcept
      : affined_(binding_backend, capability, workers, producer, consumer),
        platform_(platform), arena_(arena), expected_node_(expected_node) {}

  [[nodiscard]] auto prepare_producer() noexcept -> bool {
    return affined_.prepare_producer();
  }
  [[nodiscard]] auto prepare_consumer() noexcept -> bool {
    return affined_.prepare_consumer();
  }
  [[nodiscard]] auto observe_during_measurement() -> bool {
    auto observed =
        platform_.query_residency(const_cast<std::byte*>(arena_.storage_address()),
                                  arena_.allocated_bytes(), arena_.base_page_bytes());
    if (!observed ||
        !observed.value().passes(expected_node_,
                                 arena_.allocated_bytes() / arena_.base_page_bytes())) {
      return false;
    }
    during_ = std::move(observed.value());
    return true;
  }
  [[nodiscard]] auto evidence() const noexcept -> AffinedPreparationEvidence {
    return affined_.evidence();
  }
  [[nodiscard]] auto during() const -> const platform::Q15ResidencySnapshot& {
    return during_;
  }

private:
  AffinedObservationPreparation affined_;
  platform::Q15PlatformOperations& platform_;
  const workload::EventArena& arena_;
  std::uint32_t expected_node_;
  platform::Q15ResidencySnapshot during_;
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
                                        const CaptureGeometry& geometry,
                                        platform::Q15PlatformOperations& platform_ops,
                                        std::uint32_t expected_node)
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
    const auto before =
        platform_ops.query_residency(const_cast<std::byte*>(arena.storage_address()),
                                     arena.allocated_bytes(), arena.base_page_bytes());
    if (!before || !before.value().passes(expected_node, arena.allocated_bytes() /
                                                             arena.base_page_bytes())) {
      return failure<RunCapture>("$/action_inputs", "S17-RUN-RESIDENCY-BEFORE",
                                 "producer-home page residency failed before run");
    }
    PilotObservationPreparation preparation(binding, prefetch_capability,
                                            ticket.workers(), producer, consumer,
                                            platform_ops, arena, expected_node);
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
    const auto after =
        platform_ops.query_residency(const_cast<std::byte*>(arena.storage_address()),
                                     arena.allocated_bytes(), arena.base_page_bytes());
    if (!after || !after.value().passes(expected_node, arena.allocated_bytes() /
                                                           arena.base_page_bytes())) {
      return failure<RunCapture>("$/action_inputs", "S17-RUN-RESIDENCY-AFTER",
                                 "producer-home page residency failed after run");
    }
    std::vector<std::uint64_t> expected;
    expected.reserve(geometry.deadlines.size());
    for (std::uint64_t sequence = 0U; sequence < geometry.deadlines.size();
         ++sequence) {
      expected.push_back(arena.select({sequence}).record_index.value);
    }
    return protocol::Result<RunCapture>::success(
        {report,
         lifecycle::detail::failure_report(lifecycle::ExecutionFailurePhase::none,
                                           lifecycle::ExecutionFailureReason::none, 0U),
         consumer_state.value, copy_bytes(producer_snapshot.bytes),
         copy_bytes(consumer_snapshot.bytes), arena.prepared_content_checksum(),
         arena.content_checksum(), arena.ordered_index_checksum(),
         arena.address_delta_checksum(), std::move(expected), false,
         preparation.evidence(), before.value(), preparation.during(), after.value(),
         expected_node});
  } catch (const std::exception&) {
    return failure<RunCapture>("$/action_inputs", "S17-RUN-EXECUTION",
                               "ticketed fixed run execution failed");
  }
}

template <protocol::QueuePackage PackageKind, typename Package>
[[nodiscard]] auto capture_ticketed_service_rate(
    const AdmissionTicket& ticket, Package& package, const workload::EventArena& arena,
    const protocol::RunId& run_id, const CaptureGeometry& geometry,
    platform::Q15PlatformOperations& platform_ops, std::uint32_t expected_node)
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
    const auto before =
        platform_ops.query_residency(const_cast<std::byte*>(arena.storage_address()),
                                     arena.allocated_bytes(), arena.base_page_bytes());
    if (!before || !before.value().passes(expected_node, arena.allocated_bytes() /
                                                             arena.base_page_bytes())) {
      return failure<RunCapture>("$/action_inputs", "S17-RUN-RESIDENCY-BEFORE",
                                 "producer-home page residency failed before run");
    }
    PilotObservationPreparation preparation(binding, prefetch_capability,
                                            ticket.workers(), producer, consumer,
                                            platform_ops, arena, expected_node);
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
      if (!preparation.observe_during_measurement()) {
        cancellation.store(true, std::memory_order_release);
      }
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
    const auto after =
        platform_ops.query_residency(const_cast<std::byte*>(arena.storage_address()),
                                     arena.allocated_bytes(), arena.base_page_bytes());
    if (!after || !after.value().passes(expected_node, arena.allocated_bytes() /
                                                           arena.base_page_bytes())) {
      return failure<RunCapture>("$/action_inputs", "S17-RUN-RESIDENCY-AFTER",
                                 "producer-home page residency failed after run");
    }
    std::vector<std::uint64_t> expected;
    expected.reserve(static_cast<std::size_t>(report.attempted));
    for (std::uint64_t sequence = 0U; sequence < report.attempted; ++sequence) {
      expected.push_back(arena.select({sequence}).record_index.value);
    }
    return protocol::Result<RunCapture>::success(
        {report,
         lifecycle::detail::failure_report(lifecycle::ExecutionFailurePhase::none,
                                           lifecycle::ExecutionFailureReason::none, 0U),
         checksum.value, copy_bytes(producer_snapshot.bytes),
         copy_bytes(consumer_snapshot.bytes), arena.prepared_content_checksum(),
         arena.content_checksum(), arena.ordered_index_checksum(),
         arena.address_delta_checksum(), std::move(expected), false,
         preparation.evidence(), before.value(), preparation.during(), after.value(),
         expected_node});
  } catch (const std::exception&) {
    return failure<RunCapture>("$/action_inputs", "S17-Q16B-EXECUTION",
                               "service-rate fixed action failed");
  }
}

template <protocol::QueuePackage PackageKind, typename Package>
[[nodiscard]] auto capture_by_mode(FixedAction action, const AdmissionTicket& ticket,
                                   Package& package, const workload::EventArena& arena,
                                   const protocol::RunId& run_id,
                                   const CaptureGeometry& geometry,
                                   platform::Q15PlatformOperations& platform_ops,
                                   std::uint32_t expected_node)
    -> protocol::Result<RunCapture> {
  if (action == FixedAction::q16b) {
    return capture_ticketed_service_rate<PackageKind>(
        ticket, package, arena, run_id, geometry, platform_ops, expected_node);
  }
  return capture_ticketed_run<PackageKind>(ticket, package, arena, run_id, geometry,
                                           platform_ops, expected_node);
}

template <protocol::QueuePackage PackageKind, typename Queue, typename Package>
[[nodiscard]] auto capture_pilot_after_warmup(
    const AdmissionTicket& ticket, Queue& queue, Package& package,
    const workload::EventArena& arena, const protocol::RunId& warmup_run_id,
    const CaptureGeometry& warmup_geometry, const protocol::RunId& run_id,
    const CaptureGeometry& measurement_geometry,
    platform::Q15PlatformOperations& platform_ops, std::uint32_t expected_node)
    -> protocol::Result<RunCapture> {
  auto warmup =
      capture_ticketed_run<PackageKind>(ticket, package, arena, warmup_run_id,
                                        warmup_geometry, platform_ops, expected_node);
  if (!warmup || !queue.reset_quiescent() ||
      arena.content_checksum() != arena.prepared_content_checksum()) {
    return failure<RunCapture>("$/action_inputs/warmup", "S17-PILOT-WARMUP-RESET",
                               "warm-up did not drain and reset in place");
  }
  auto measurement = capture_ticketed_run<PackageKind>(ticket, package, arena, run_id,
                                                       measurement_geometry,
                                                       platform_ops, expected_node);
  if (!measurement) {
    return measurement;
  }
  measurement.value().warmup_report = warmup.value().report;
  measurement.value().warmup_reset_verified = true;
  return measurement;
}

[[nodiscard]] auto
package_capture(FixedAction action, const JsonObject& input,
                PilotPersistentContexts* persistent_contexts = nullptr)
    -> protocol::Result<RunCapture> {
  constexpr std::array q16b_fields{"capacity"sv,
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
                                   "duration_ticks"sv,
                                   "shared_memory_node"sv,
                                   "cell_ordinal"sv,
                                   "repetition_ordinal"sv,
                                   "hardware_state"sv,
                                   "placement"sv,
                                   "working_set_class"sv,
                                   "q16a_result_sha256"sv};
  constexpr std::array q16c_fields{"capacity"sv,
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
                                   "duration_ticks"sv,
                                   "shared_memory_node"sv,
                                   "cell_ordinal"sv,
                                   "repetition_ordinal"sv,
                                   "hardware_state"sv,
                                   "placement"sv,
                                   "working_set_class"sv,
                                   "load_level"sv,
                                   "q16a_result_sha256"sv,
                                   "q16b_result_sha256"sv};
  constexpr std::array pilot_fields{
      "cell_ordinal"sv,
      "repetition_ordinal"sv,
      "hardware_state"sv,
      "placement"sv,
      "working_set_class"sv,
      "load_level"sv,
      "capacity"sv,
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
      "duration_ticks"sv,
      "warmup_run_id"sv,
      "warmup_schedule_sha256"sv,
      "warmup_seed_id"sv,
      "warmup_schedule_deadline_ticks"sv,
      "warmup_schedule_origin_ticks"sv,
      "warmup_schedule_horizon_ticks"sv,
      "shared_memory_node"sv,
  };
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
  const auto shared_node = uint_member(input, "shared_memory_node");
  const bool is_pilot = action == FixedAction::blinded_pilot;
  const auto warmup_deadlines =
      is_pilot ? uint_array_member(input, "warmup_schedule_deadline_ticks")
               : std::optional<std::vector<std::uint64_t>>{};
  const auto warmup_origin = uint_member(input, "warmup_schedule_origin_ticks");
  const auto warmup_horizon = uint_member(input, "warmup_schedule_horizon_ticks");
  const auto* warmup_run_id = string_member(input, "warmup_run_id");
  const auto* warmup_schedule_sha = string_member(input, "warmup_schedule_sha256");
  const auto* warmup_seed_id = string_member(input, "warmup_seed_id");
  const bool exact_input = is_pilot ? exact_fields(input, pilot_fields)
                           : action == FixedAction::q16b
                               ? exact_fields(input, q16b_fields)
                               : exact_fields(input, q16c_fields);
  if (!exact_input || !capacity || !events || !distance || !shared_node ||
      package_name == nullptr || seed_id == nullptr || seed_hex == nullptr ||
      seed_hex->size() != 64U || !cache_line || !base_page || *cache_line == 0U ||
      *base_page == 0U || *capacity < 8U || *events == 0U ||
      *shared_node > std::numeric_limits<std::uint32_t>::max() ||
      *capacity > std::numeric_limits<std::size_t>::max() ||
      admission_object == nullptr || admission_sha == nullptr ||
      evidence_sha == nullptr || deadlines == std::nullopt || !schedule_origin ||
      !schedule_horizon || !duration || *duration == 0U ||
      ((action == FixedAction::q16b && !deadlines->empty()) ||
       (action != FixedAction::q16b && deadlines->size() != *events)) ||
      (action != FixedAction::q16b && *schedule_horizon == 0U) ||
      (is_pilot && (!warmup_deadlines || warmup_deadlines->empty() || !warmup_origin ||
                    !warmup_horizon || *warmup_horizon == 0U ||
                    warmup_run_id == nullptr || warmup_schedule_sha == nullptr ||
                    warmup_seed_id == nullptr || *warmup_seed_id == *seed_id ||
                    *warmup_run_id == *string_member(input, "run_id") ||
                    warmup_deadlines->back() >= *warmup_horizon))) {
    return failure<RunCapture>("$/action_inputs", "S17-RUN-INPUT",
                               "fixed run geometry is invalid");
  }
  const auto ticket = load_sealed_runner_ticket(input);
  if (!ticket) {
    return protocol::Result<RunCapture>::failure(ticket.errors());
  }
  LinuxCurrentThreadBindingBackend owner_binding;
  if (!owner_binding.bind_and_verify(ticket.value().workers().producer_cpu).passes()) {
    return failure<RunCapture>("$/action_inputs", "S17-RUN-PRODUCER-FIRST-TOUCH",
                               "producer affinity was not verified before allocation");
  }
  const auto parsed_run_id =
      protocol::RunId::parse(*string_member(input, "run_id"), "$/action_inputs/run_id");
  if (!parsed_run_id) {
    return protocol::Result<RunCapture>::failure(parsed_run_id.errors());
  }
  const auto parsed_warmup_run_id =
      is_pilot ? protocol::RunId::parse(*warmup_run_id, "$/action_inputs/warmup_run_id")
               : protocol::Result<protocol::RunId>::success(parsed_run_id.value());
  if (!parsed_warmup_run_id) {
    return protocol::Result<RunCapture>::failure(parsed_warmup_run_id.errors());
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
  if (is_pilot) {
    const auto* placement = string_member(input, "placement");
    const auto expected_placement =
        ticket.value().placement() == protocol::Placement::near ? "NEAR"sv : "FAR"sv;
    if (placement == nullptr || *placement != expected_placement) {
      return failure<RunCapture>(
          "$/action_inputs/placement", "S17-RUN-PLACEMENT-TICKET",
          "pilot placement differs from the admitted worker pair");
    }
  }
  try {
    const auto size = static_cast<std::size_t>(*capacity);
    if (size > std::numeric_limits<std::size_t>::max() /
                   static_cast<std::size_t>(*cache_line)) {
      return failure<RunCapture>("$/action_inputs/capacity", "S17-RUN-ARENA-SIZE",
                                 "event arena byte count overflows size_t");
    }
    std::unique_ptr<PlatformEventMemory> run_memory;
    std::unique_ptr<workload::EventArena> run_arena;
    PilotPersistentContext* persistent = nullptr;
    if (is_pilot) {
      if (persistent_contexts == nullptr) {
        return failure<RunCapture>("$/action_inputs", "S17-PILOT-PERSISTENCE",
                                   "pilot persistent context registry is absent");
      }
      const auto* placement = string_member(input, "placement");
      const auto* working_set = string_member(input, "working_set_class");
      const auto* load = string_member(input, "load_level");
      const auto repetition = uint_member(input, "repetition_ordinal");
      if (placement == nullptr || working_set == nullptr || load == nullptr ||
          !repetition) {
        return failure<RunCapture>("$/action_inputs", "S17-PILOT-PERSISTENCE-KEY",
                                   "pilot persistent context key is incomplete");
      }
      const auto key = *placement + "/" + *working_set + "/" + *load + "/" +
                       std::to_string(*repetition);
      auto [entry, inserted] = persistent_contexts->try_emplace(key, nullptr);
      if (inserted) {
        entry->second =
            std::make_unique<PilotPersistentContext>(PilotPersistentContextConfig{
                size, static_cast<std::size_t>(*cache_line),
                static_cast<std::size_t>(*base_page),
                static_cast<std::uint32_t>(*shared_node), *seed_hex, *seed_id});
      }
      persistent = entry->second.get();
      if (persistent == nullptr ||
          !persistent->matches(size, static_cast<std::size_t>(*cache_line),
                               static_cast<std::size_t>(*base_page),
                               static_cast<std::uint32_t>(*shared_node), *seed_hex,
                               *seed_id)) {
        return failure<RunCapture>(
            "$/action_inputs", "S17-PILOT-PERSISTENCE-DRIFT",
            "paired pilot treatments do not share one frozen arena mapping");
      }
    } else {
      run_memory = std::make_unique<PlatformEventMemory>(
          PlatformEventMemoryConfig{size * static_cast<std::size_t>(*cache_line),
                                    static_cast<std::uint32_t>(*shared_node)});
      run_arena = std::make_unique<workload::EventArena>(
          workload::EventArenaConfig{size, static_cast<std::size_t>(*cache_line),
                                     static_cast<std::size_t>(*base_page),
                                     workload::MasterSeed::from_hex(*seed_hex),
                                     *seed_id},
          run_memory->bytes());
    }
    auto& arena = persistent != nullptr ? persistent->arena() : *run_arena;
    auto& event_operations =
        persistent != nullptr ? persistent->operations() : run_memory->operations();
    runner::X86RetainingPrefetchEmitter emitter;
    if (*package_name == "R0") {
      std::unique_ptr<queue::RingSpscQueue> run_queue;
      if (persistent == nullptr) {
        run_queue = std::make_unique<queue::RingSpscQueue>(
            queue::QueueCapacity{size},
            queue::CacheLineBytes{static_cast<std::size_t>(*cache_line)});
      }
      auto& queue = persistent != nullptr ? persistent->ring() : *run_queue;
      workload::R0Package package(queue);
      if (is_pilot) {
        if (!queue.reset_quiescent()) {
          return failure<RunCapture>("$/action_inputs", "S17-PILOT-RING-RESET",
                                     "persistent ring did not reset before warm-up");
        }
        return capture_pilot_after_warmup<protocol::QueuePackage::r0>(
            ticket.value(), queue, package, arena, parsed_warmup_run_id.value(),
            {*warmup_deadlines, *warmup_origin, *warmup_horizon, *warmup_horizon,
             warmup_deadlines->size(), static_cast<std::size_t>(*cache_line)},
            parsed_run_id.value(),
            {*deadlines, *schedule_origin, *schedule_horizon, *duration, *events,
             static_cast<std::size_t>(*cache_line)},
            event_operations, static_cast<std::uint32_t>(*shared_node));
      }
      return capture_by_mode<protocol::QueuePackage::r0>(
          action, ticket.value(), package, arena, parsed_run_id.value(),
          {*deadlines, *schedule_origin, *schedule_horizon, *duration, *events,
           static_cast<std::size_t>(*cache_line)},
          event_operations, static_cast<std::uint32_t>(*shared_node));
    }
    if (*package_name == "R1") {
      std::unique_ptr<queue::RingSpscQueue> run_queue;
      if (persistent == nullptr) {
        run_queue = std::make_unique<queue::RingSpscQueue>(
            queue::QueueCapacity{size},
            queue::CacheLineBytes{static_cast<std::size_t>(*cache_line)});
      }
      auto& queue = persistent != nullptr ? persistent->ring() : *run_queue;
      workload::R1Package package(
          queue, emitter,
          workload::ring_one_line_distance(
              {size, static_cast<std::size_t>(*cache_line), sizeof(void*)}));
      if (is_pilot) {
        if (!queue.reset_quiescent()) {
          return failure<RunCapture>("$/action_inputs", "S17-PILOT-RING-RESET",
                                     "persistent ring did not reset before warm-up");
        }
        return capture_pilot_after_warmup<protocol::QueuePackage::r1>(
            ticket.value(), queue, package, arena, parsed_warmup_run_id.value(),
            {*warmup_deadlines, *warmup_origin, *warmup_horizon, *warmup_horizon,
             warmup_deadlines->size(), static_cast<std::size_t>(*cache_line)},
            parsed_run_id.value(),
            {*deadlines, *schedule_origin, *schedule_horizon, *duration, *events,
             static_cast<std::size_t>(*cache_line)},
            event_operations, static_cast<std::uint32_t>(*shared_node));
      }
      return capture_by_mode<protocol::QueuePackage::r1>(
          action, ticket.value(), package, arena, parsed_run_id.value(),
          {*deadlines, *schedule_origin, *schedule_horizon, *duration, *events,
           static_cast<std::size_t>(*cache_line)},
          event_operations, static_cast<std::uint32_t>(*shared_node));
    }
    if (*package_name == "R2") {
      std::unique_ptr<queue::RingSpscQueue> run_queue;
      if (persistent == nullptr) {
        run_queue = std::make_unique<queue::RingSpscQueue>(
            queue::QueueCapacity{size},
            queue::CacheLineBytes{static_cast<std::size_t>(*cache_line)});
      }
      auto& queue = persistent != nullptr ? persistent->ring() : *run_queue;
      const auto calibrated = workload::resolve_calibrated_ring_distance(
          {size, static_cast<std::size_t>(*cache_line), sizeof(void*)},
          static_cast<std::size_t>(*distance), "admitted-q16a-freeze");
      workload::R2Package package(queue, emitter, calibrated);
      if (is_pilot) {
        if (!queue.reset_quiescent()) {
          return failure<RunCapture>("$/action_inputs", "S17-PILOT-RING-RESET",
                                     "persistent ring did not reset before warm-up");
        }
        return capture_pilot_after_warmup<protocol::QueuePackage::r2>(
            ticket.value(), queue, package, arena, parsed_warmup_run_id.value(),
            {*warmup_deadlines, *warmup_origin, *warmup_horizon, *warmup_horizon,
             warmup_deadlines->size(), static_cast<std::size_t>(*cache_line)},
            parsed_run_id.value(),
            {*deadlines, *schedule_origin, *schedule_horizon, *duration, *events,
             static_cast<std::size_t>(*cache_line)},
            event_operations, static_cast<std::uint32_t>(*shared_node));
      }
      return capture_by_mode<protocol::QueuePackage::r2>(
          action, ticket.value(), package, arena, parsed_run_id.value(),
          {*deadlines, *schedule_origin, *schedule_horizon, *duration, *events,
           static_cast<std::size_t>(*cache_line)},
          event_operations, static_cast<std::uint32_t>(*shared_node));
    }
    std::unique_ptr<workload::NodeOrderPlan> run_order;
    std::unique_ptr<queue::LinkedSpscQueue> run_queue;
    if (persistent == nullptr) {
      run_order = std::make_unique<workload::NodeOrderPlan>(
          workload::NodeOrderConfig{size, static_cast<std::size_t>(*cache_line),
                                    static_cast<std::size_t>(*cache_line),
                                    static_cast<std::size_t>(*base_page)},
          workload::MasterSeed::from_hex(*seed_hex), *seed_id);
      run_queue = std::make_unique<queue::LinkedSpscQueue>(
          queue::QueueCapacity{size},
          queue::CacheLineBytes{static_cast<std::size_t>(*cache_line)},
          queue::ArenaAlignmentBytes{static_cast<std::size_t>(*base_page)},
          run_order->order());
    }
    auto& linked_queue = persistent != nullptr ? persistent->linked() : *run_queue;
    if (*package_name == "L0") {
      workload::L0Package package(linked_queue);
      if (is_pilot) {
        if (!linked_queue.reset_quiescent()) {
          return failure<RunCapture>(
              "$/action_inputs", "S17-PILOT-LINKED-RESET",
              "persistent linked queue did not reset before warm-up");
        }
        return capture_pilot_after_warmup<protocol::QueuePackage::l0>(
            ticket.value(), linked_queue, package, arena, parsed_warmup_run_id.value(),
            {*warmup_deadlines, *warmup_origin, *warmup_horizon, *warmup_horizon,
             warmup_deadlines->size(), static_cast<std::size_t>(*cache_line)},
            parsed_run_id.value(),
            {*deadlines, *schedule_origin, *schedule_horizon, *duration, *events,
             static_cast<std::size_t>(*cache_line)},
            event_operations, static_cast<std::uint32_t>(*shared_node));
      }
      return capture_by_mode<protocol::QueuePackage::l0>(
          action, ticket.value(), package, arena, parsed_run_id.value(),
          {*deadlines, *schedule_origin, *schedule_horizon, *duration, *events,
           static_cast<std::size_t>(*cache_line)},
          event_operations, static_cast<std::uint32_t>(*shared_node));
    }
    if (*package_name == "L1") {
      workload::L1Package package(linked_queue, emitter);
      if (is_pilot) {
        if (!linked_queue.reset_quiescent()) {
          return failure<RunCapture>(
              "$/action_inputs", "S17-PILOT-LINKED-RESET",
              "persistent linked queue did not reset before warm-up");
        }
        return capture_pilot_after_warmup<protocol::QueuePackage::l1>(
            ticket.value(), linked_queue, package, arena, parsed_warmup_run_id.value(),
            {*warmup_deadlines, *warmup_origin, *warmup_horizon, *warmup_horizon,
             warmup_deadlines->size(), static_cast<std::size_t>(*cache_line)},
            parsed_run_id.value(),
            {*deadlines, *schedule_origin, *schedule_horizon, *duration, *events,
             static_cast<std::size_t>(*cache_line)},
            event_operations, static_cast<std::uint32_t>(*shared_node));
      }
      return capture_by_mode<protocol::QueuePackage::l1>(
          action, ticket.value(), package, arena, parsed_run_id.value(),
          {*deadlines, *schedule_origin, *schedule_horizon, *duration, *events,
           static_cast<std::size_t>(*cache_line)},
          event_operations, static_cast<std::uint32_t>(*shared_node));
    }
  } catch (const std::exception&) {
    return failure<RunCapture>("$/action_inputs", "S17-RUN-EXECUTION",
                               "fixed package execution failed");
  }
  return failure<RunCapture>("$/action_inputs/package", "S17-RUN-PACKAGE",
                             "fixed package is not one of the five Stage A packages");
}

[[nodiscard]] auto page_nodes(const platform::Q15ResidencySnapshot& snapshot)
    -> JsonArray {
  JsonArray result;
  result.reserve(snapshot.page_nodes.size());
  for (const auto node : snapshot.page_nodes) {
    if (node < 0) {
      throw std::runtime_error("negative page residency result");
    }
    result.push_back(uint_value(static_cast<std::uint64_t>(node)));
  }
  return result;
}

[[nodiscard]] auto run_artifacts(FixedAction action, const JsonObject& input,
                                 RunCapture capture, const std::string& prefix)
    -> protocol::Result<std::vector<ArtifactPayload>> {
  const auto* run_id_text = string_member(input, "run_id");
  const auto* plan = string_member(input, "plan_sha256");
  const auto* schedule = string_member(input, "schedule_sha256");
  const auto* seed_id = string_member(input, "seed_id");
  const auto* admission = string_member(input, "runner_admission_sha256");
  const auto planned_attempt_capacity = uint_member(input, "offered_count");
  const auto* package = string_member(input, "package");
  const auto cell_ordinal = uint_member(input, "cell_ordinal");
  const auto repetition_ordinal = uint_member(input, "repetition_ordinal");
  const auto* hardware_state = string_member(input, "hardware_state");
  const auto* placement = string_member(input, "placement");
  const auto* working_set_class = string_member(input, "working_set_class");
  const auto* load_level = string_member(input, "load_level");
  const bool requires_factor_binding = action != FixedAction::q16a;
  const bool requires_load =
      action == FixedAction::blinded_pilot || action == FixedAction::q16c;
  if (run_id_text == nullptr || plan == nullptr || schedule == nullptr ||
      seed_id == nullptr || admission == nullptr || !planned_attempt_capacity ||
      package == nullptr || prefix.empty() || prefix.find('/') != prefix.npos ||
      (requires_factor_binding &&
       (!cell_ordinal || !repetition_ordinal || hardware_state == nullptr ||
        placement == nullptr || working_set_class == nullptr)) ||
      (requires_load && load_level == nullptr)) {
    return failure<std::vector<ArtifactPayload>>(
        "$/action_inputs", "S17-RUN-LINEAGE",
        "fixed run lineage or generated output prefix is incomplete");
  }
  const auto run_id = protocol::RunId::parse(*run_id_text, "$/action_inputs/run_id");
  if (!run_id) {
    return protocol::Result<std::vector<ArtifactPayload>>::failure(run_id.errors());
  }
  const auto accepted = capture.report.accepted;
  const auto full = capture.report.full;
  const auto consumed = capture.report.consumed;
  if (accepted != consumed || capture.report.attempted != accepted + full ||
      capture.expected_record_indices.size() != capture.report.attempted) {
    return failure<std::vector<ArtifactPayload>>(
        "$/action_inputs", "S17-RUN-COUNT",
        "fixed run count equations or immutable record mapping failed");
  }

  const auto producer_sha = sha256(capture.producer_bytes);
  const auto consumer_sha = sha256(capture.consumer_bytes);
  const std::string integrity_id = prefix + "PHASE-INTEGRITY";
  auto integrity = storage::make_phase_integrity_document({integrity_id,
                                                           *run_id_text,
                                                           {capture.checksum},
                                                           capture.event_records_pre,
                                                           capture.event_records_post,
                                                           capture.ordered_index,
                                                           capture.address_delta});
  if (!integrity) {
    return protocol::Result<std::vector<ArtifactPayload>>::failure(integrity.errors());
  }
  const auto producer_file = prefix + "producer-raw-v1.bin";
  const auto consumer_file = prefix + "consumer-raw-v1.bin";
  const auto producer_id = prefix + "PRODUCER-RAW";
  const auto consumer_id = prefix + "CONSUMER-RAW";
  auto producer_envelope = storage::make_external_raw_envelope(
      {producer_id,
       *run_id_text,
       protocol::StreamKind::producer,
       producer_file,
       capture.report.attempted,
       static_cast<std::uint64_t>(capture.producer_bytes.size()),
       producer_sha,
       {integrity_id, integrity.value().sha256},
       {}});
  auto consumer_envelope = storage::make_external_raw_envelope(
      {consumer_id,
       *run_id_text,
       protocol::StreamKind::consumer,
       consumer_file,
       consumed,
       static_cast<std::uint64_t>(capture.consumer_bytes.size()),
       consumer_sha,
       {integrity_id, integrity.value().sha256},
       {}});
  if (!producer_envelope || !consumer_envelope) {
    return protocol::Result<std::vector<ArtifactPayload>>::failure(
        !producer_envelope ? producer_envelope.errors() : consumer_envelope.errors());
  }
  auto decoded_producer = storage::decode_external_raw(
      producer_envelope.value().envelope, capture.producer_bytes);
  auto decoded_consumer = storage::decode_external_raw(
      consumer_envelope.value().envelope, capture.consumer_bytes);
  if (!decoded_producer || !decoded_consumer) {
    return protocol::Result<std::vector<ArtifactPayload>>::failure(
        !decoded_producer ? decoded_producer.errors() : decoded_consumer.errors());
  }
  std::vector<protocol::ProducerRecord> producer_rows;
  for (const auto& row : std::get<std::vector<storage::DecodedProducerRow>>(
           decoded_producer.value().rows)) {
    producer_rows.push_back(
        timing::make_producer_record(run_id.value(), row.observation));
  }
  std::vector<protocol::ConsumerRecord> consumer_rows;
  for (const auto& row : std::get<std::vector<storage::DecodedConsumerRow>>(
           decoded_consumer.value().rows)) {
    consumer_rows.push_back(
        timing::make_consumer_record(run_id.value(), row.observation));
  }
  auto joined = reconciliation::reconcile(run_id.value(), producer_rows, consumer_rows,
                                          capture.expected_record_indices);
  if (joined.status != protocol::JoinStatus::passed || !joined.issues.empty()) {
    return failure<std::vector<ArtifactPayload>>(
        "$/action_inputs", "S17-RUN-RECONCILIATION",
        "exact accepted-ordinal reconciliation failed");
  }
  auto joined_bytes =
      storage::encode_joined_rows_for_format_test(run_id.value(), joined.joined_rows);
  const auto joined_sha = sha256(joined_bytes);
  const auto joined_file = prefix + "joined-raw-v1.bin";
  const auto joined_id = prefix + "JOINED-DERIVED";
  auto joined_envelope = storage::make_external_raw_envelope(
      {joined_id,
       *run_id_text,
       protocol::StreamKind::joined_derived,
       joined_file,
       joined.accepted_rows,
       static_cast<std::uint64_t>(joined_bytes.size()),
       joined_sha,
       {integrity_id, integrity.value().sha256},
       {{producer_id, producer_sha}, {consumer_id, consumer_sha}}});
  if (!joined_envelope) {
    return protocol::Result<std::vector<ArtifactPayload>>::failure(
        joined_envelope.errors());
  }
  auto summary = canonical(JsonObject{
      {"schema_version",
       string_value(action == FixedAction::q16b ? "cpu-prefetch-stage17-q16b-output/3"
                    : action == FixedAction::q16c
                        ? "cpu-prefetch-stage17-q16c-output/3"
                        : "cpu-prefetch-stage17-blinded-pilot-run/3")},
      {"run_id", string_value(*run_id_text)},
      {"plan_sha256", string_value(*plan)},
      {"schedule_sha256", string_value(*schedule)},
      {"seed_id", string_value(*seed_id)},
      {"runner_admission_sha256", string_value(*admission)},
      {"package", string_value(*package)},
      {"cell_ordinal",
       requires_factor_binding ? uint_value(*cell_ordinal) : JsonValue(nullptr)},
      {"repetition_ordinal",
       requires_factor_binding ? uint_value(*repetition_ordinal) : JsonValue(nullptr)},
      {"hardware_state",
       requires_factor_binding ? string_value(*hardware_state) : JsonValue(nullptr)},
      {"placement",
       requires_factor_binding ? string_value(*placement) : JsonValue(nullptr)},
      {"working_set_class",
       requires_factor_binding ? string_value(*working_set_class) : JsonValue(nullptr)},
      {"load_level", requires_load ? string_value(*load_level) : JsonValue(nullptr)},
      {"planned_attempt_capacity", uint_value(*planned_attempt_capacity)},
      {"offered_count", uint_value(capture.report.attempted)},
      {"accepted_count", uint_value(accepted)},
      {"full_count", uint_value(full)},
      {"consumed_count", uint_value(consumed)},
      {"final_consumer_checksum", uint_value(capture.checksum)},
      {"zero_loss", JsonValue(full == 0U)},
      {"join_status", string_value("PASSED")},
      {"warmup_reset_verified", JsonValue(action != FixedAction::blinded_pilot ||
                                          capture.warmup_reset_verified)},
      {"treatment_blind", JsonValue(true)},
      {"confirmatory_outcomes_accessed", JsonValue(false)},
      {"complete", JsonValue(true)},
  });
  auto join_audit = canonical(JsonObject{
      {"schema_version", string_value("cpu-prefetch-stage17-join-audit/3")},
      {"run_id", string_value(*run_id_text)},
      {"producer_raw_sha256", string_value(producer_sha)},
      {"consumer_raw_sha256", string_value(consumer_sha)},
      {"joined_raw_sha256", string_value(joined_sha)},
      {"producer_rows", uint_value(joined.producer_rows)},
      {"accepted_rows", uint_value(joined.accepted_rows)},
      {"full_rows", uint_value(joined.full_rows)},
      {"consumer_rows", uint_value(joined.consumer_rows)},
      {"join_status", string_value("PASSED")},
      {"record_index_is_event_identity", JsonValue(false)},
  });
  auto pages = canonical(JsonObject{
      {"schema_version", string_value("cpu-prefetch-stage17-page-residency/3")},
      {"run_id", string_value(*run_id_text)},
      {"expected_numa_node", uint_value(capture.expected_numa_node)},
      {"before_page_nodes", JsonValue(page_nodes(capture.residency_before))},
      {"during_page_nodes", JsonValue(page_nodes(capture.residency_during))},
      {"after_page_nodes", JsonValue(page_nodes(capture.residency_after))},
      {"producer_cpu", uint_value(capture.affinity.producer_binding.actual_cpu)},
      {"consumer_cpu", uint_value(capture.affinity.consumer_binding.actual_cpu)},
      {"producer_migrated", JsonValue(false)},
      {"consumer_migrated", JsonValue(false)},
      {"verified", JsonValue(capture.affinity.passes())},
  });
  if (!summary || !join_audit || !pages) {
    return protocol::Result<std::vector<ArtifactPayload>>::failure(
        !summary ? summary.errors()
                 : (!join_audit ? join_audit.errors() : pages.errors()));
  }
  std::vector<ArtifactPayload> artifacts;
  artifacts.reserve(10U);
  artifacts.push_back({"PRODUCER_RAW_OBSERVATIONS", std::string(storage::kRawFormatId),
                       "application/octet-stream", producer_file,
                       std::move(capture.producer_bytes)});
  artifacts.push_back({"CONSUMER_RAW_OBSERVATIONS", std::string(storage::kRawFormatId),
                       "application/octet-stream", consumer_file,
                       std::move(capture.consumer_bytes)});
  artifacts.push_back({"PHASE_INTEGRITY", std::string(storage::kPhaseIntegritySchema),
                       "application/json", prefix + "phase-integrity-v1.json",
                       bytes(integrity.value().bytes)});
  artifacts.push_back({"PRODUCER_RAW_ENVELOPE", std::string(protocol::kProtocolVersion),
                       "application/json", prefix + "producer-envelope-v1.json",
                       bytes(producer_envelope.value().document.bytes)});
  artifacts.push_back({"CONSUMER_RAW_ENVELOPE", std::string(protocol::kProtocolVersion),
                       "application/json", prefix + "consumer-envelope-v1.json",
                       bytes(consumer_envelope.value().document.bytes)});
  artifacts.push_back({"JOINED_RAW_OBSERVATIONS", std::string(storage::kRawFormatId),
                       "application/octet-stream", joined_file,
                       std::move(joined_bytes)});
  artifacts.push_back({"JOINED_RAW_ENVELOPE", std::string(protocol::kProtocolVersion),
                       "application/json", prefix + "joined-envelope-v1.json",
                       bytes(joined_envelope.value().document.bytes)});
  artifacts.push_back({"JOIN_AUDIT", "cpu-prefetch-stage17-join-audit/3",
                       "application/json", prefix + "join-audit-v3.json",
                       bytes(join_audit.value())});
  artifacts.push_back({"PAGE_RESIDENCY_PROVENANCE",
                       "cpu-prefetch-stage17-page-residency/3", "application/json",
                       prefix + "page-residency-v3.json", bytes(pages.value())});
  artifacts.push_back(
      {action == FixedAction::q16b   ? "Q16B_SERVICE_RATE_CAPTURE"
       : action == FixedAction::q16c ? "Q16C_ZERO_LOSS_FEASIBILITY_CAPTURE"
                                     : "STAGE17_BLINDED_PILOT_RUN",
       action == FixedAction::q16b   ? "cpu-prefetch-stage17-q16b-output/3"
       : action == FixedAction::q16c ? "cpu-prefetch-stage17-q16c-output/3"
                                     : "cpu-prefetch-stage17-blinded-pilot-run/3",
       "application/json", prefix + "run-summary-v3.json", bytes(summary.value())});
  return protocol::Result<std::vector<ArtifactPayload>>::success(artifacts);
}

[[nodiscard]] auto q16_or_pilot(FixedAction action, const JsonObject& input,
                                ArtifactSink& sink) -> protocol::Result<ActionOutcome> {
  if (action == FixedAction::blinded_pilot) {
    constexpr std::array input_fields{"plan_sha256"sv, "pilot_plan"sv};
    constexpr std::array plan_fields{
        "schema_version"sv,
        "plan_id"sv,
        "plan_core_sha256"sv,
        "protocol_version"sv,
        "stand_id"sv,
        "repetitions_per_cell"sv,
        "whole_plot_order"sv,
        "hardware_control"sv,
        "cells"sv,
        "treatment_blind"sv,
        "confirmatory_outcomes_accessed"sv,
        "synthetic_test_only"sv,
        "phase18_authority"sv,
    };
    constexpr std::array cell_fields{
        "cell_ordinal"sv,      "package"sv,    "hardware_state"sv, "placement"sv,
        "working_set_class"sv, "load_level"sv, "runs"sv,
    };
    const auto* plan_sha = string_member(input, "plan_sha256");
    const auto* plan = require_object(input, "pilot_plan");
    const auto* hardware_control =
        plan == nullptr ? nullptr : require_object(*plan, "hardware_control");
    const auto hardware_prestate =
        hardware_control == nullptr
            ? failure<std::array<platform::HardwarePrefetchMsrValue, 3U>>(
                  "$/action_inputs/pilot_plan/hardware_control", "S17-PILOT-HARDWARE",
                  "pilot hardware control is absent")
            : parse_prestate(*hardware_control);
    if (!exact_fields(input, input_fields) || plan_sha == nullptr || plan == nullptr ||
        !exact_fields(*plan, plan_fields) ||
        string_member(*plan, "schema_version") == nullptr ||
        *string_member(*plan, "schema_version") !=
            "cpu-prefetch-stage17-pilot-plan/3" ||
        string_member(*plan, "protocol_version") == nullptr ||
        *string_member(*plan, "protocol_version") != protocol::kProtocolVersion ||
        string_member(*plan, "plan_id") == nullptr ||
        string_member(*plan, "plan_core_sha256") == nullptr ||
        !is_sha256_hex(*string_member(*plan, "plan_core_sha256")) ||
        string_member(*plan, "stand_id") == nullptr || hardware_control == nullptr ||
        !hardware_prestate ||
        string_member(*hardware_control, "mapping_id") == nullptr ||
        *string_member(*hardware_control, "mapping_id") !=
            platform::kHardwarePrefetchMappingId ||
        string_member(*hardware_control, "q15_w_result_sha256") == nullptr ||
        bool_member(*plan, "synthetic_test_only") == nullptr ||
        *bool_member(*plan, "synthetic_test_only") ||
        bool_member(*plan, "treatment_blind") == nullptr ||
        !*bool_member(*plan, "treatment_blind") ||
        bool_member(*plan, "confirmatory_outcomes_accessed") == nullptr ||
        *bool_member(*plan, "confirmatory_outcomes_accessed") ||
        bool_member(*plan, "phase18_authority") == nullptr ||
        *bool_member(*plan, "phase18_authority")) {
      return failure<ActionOutcome>("$/action_inputs/pilot_plan", "S17-PILOT-PLAN",
                                    "pilot requires the closed frozen plan family");
    }
    const auto canonical_plan = canonical(*plan);
    if (!canonical_plan || sha256(canonical_plan.value()) != *plan_sha) {
      return failure<ActionOutcome>("$/action_inputs/plan_sha256",
                                    "S17-PILOT-PLAN-HASH",
                                    "pilot plan canonical bytes/hash drifted");
    }
    const auto repetitions = uint_member(*plan, "repetitions_per_cell");
    const auto* cells_value = member(*plan, "cells");
    const auto* cells = cells_value == nullptr ? nullptr : cells_value->as_array();
    const auto* whole_value = member(*plan, "whole_plot_order");
    const auto* whole = whole_value == nullptr ? nullptr : whole_value->as_array();
    if (!repetitions || *repetitions == 0U || cells == nullptr ||
        cells->size() != 180U || whole == nullptr || whole->size() != 2U ||
        (*whole)[0].as_string() == nullptr || (*whole)[1].as_string() == nullptr ||
        *(*whole)[0].as_string() == *(*whole)[1].as_string() ||
        !((*(*whole)[0].as_string() == "H0" && *(*whole)[1].as_string() == "H1") ||
          (*(*whole)[0].as_string() == "H1" && *(*whole)[1].as_string() == "H0"))) {
      return failure<ActionOutcome>("$/action_inputs/pilot_plan", "S17-PILOT-MATRIX",
                                    "pilot requires two complete 90-cell whole plots");
    }
    const std::set<std::string> packages{"R0", "R1", "R2", "L0", "L1"};
    const std::set<std::string> placements{"NEAR", "FAR"};
    const std::set<std::string> working_sets{"L2_RESIDENT", "LLC_RESIDENT",
                                             "BEYOND_LLC"};
    const std::set<std::string> loads{"L025", "L050", "L075"};
    std::set<std::uint64_t> ordinals;
    std::set<std::string> combinations;
    std::set<std::string> run_ids;
    std::vector<ArtifactBinding> bindings;
    bindings.reserve(static_cast<std::size_t>(*repetitions) * 1800U + 1U);
    PilotPersistentContexts persistent_contexts;
    std::uint64_t execution_ordinal = 0U;
    PilotWholePlotControl whole_plot_control(hardware_prestate.value());
    std::string active_whole_plot;
    for (const auto& cell_value : *cells) {
      const auto* cell = cell_value.as_object();
      const auto cell_ordinal = cell == nullptr ? std::optional<std::uint64_t>{}
                                                : uint_member(*cell, "cell_ordinal");
      const auto* package = cell == nullptr ? nullptr : string_member(*cell, "package");
      const auto* hardware =
          cell == nullptr ? nullptr : string_member(*cell, "hardware_state");
      const auto* placement =
          cell == nullptr ? nullptr : string_member(*cell, "placement");
      const auto* working_set =
          cell == nullptr ? nullptr : string_member(*cell, "working_set_class");
      const auto* load = cell == nullptr ? nullptr : string_member(*cell, "load_level");
      const auto* runs_value = cell == nullptr ? nullptr : member(*cell, "runs");
      const auto* runs = runs_value == nullptr ? nullptr : runs_value->as_array();
      const auto expected_whole =
          *(*whole)[execution_ordinal < 90U ? 0U : 1U].as_string();
      if (active_whole_plot != expected_whole) {
        if (!active_whole_plot.empty() && !whole_plot_control.leave()) {
          return failure<ActionOutcome>(
              "$/action_inputs/pilot_plan/hardware_control",
              "S17-PILOT-HARDWARE-RESTORE",
              "prior whole-plot hardware state could not be restored");
        }
        if (!whole_plot_control.enter(expected_whole)) {
          return failure<ActionOutcome>(
              "$/action_inputs/pilot_plan/hardware_control", "S17-PILOT-HARDWARE-ENTER",
              "whole-plot hardware state live-read/apply/readback failed");
        }
        active_whole_plot = expected_whole;
      }
      if (cell == nullptr || !exact_fields(*cell, cell_fields) || !cell_ordinal ||
          *cell_ordinal >= 180U || !ordinals.insert(*cell_ordinal).second ||
          package == nullptr || !packages.contains(*package) || hardware == nullptr ||
          *hardware != expected_whole || placement == nullptr ||
          !placements.contains(*placement) || working_set == nullptr ||
          !working_sets.contains(*working_set) || load == nullptr ||
          !loads.contains(*load) || runs == nullptr || runs->size() != *repetitions) {
        return failure<ActionOutcome>("$/action_inputs/pilot_plan/cells",
                                      "S17-PILOT-CELL",
                                      "pilot cell/whole-plot/repetition shape drifted");
      }
      const auto combination = *package + "/" + *hardware + "/" + *placement + "/" +
                               *working_set + "/" + *load;
      if (!combinations.insert(combination).second) {
        return failure<ActionOutcome>("$/action_inputs/pilot_plan/cells",
                                      "S17-PILOT-DUPLICATE-CELL",
                                      "pilot factorial combination is duplicated");
      }
      for (std::uint64_t repetition = 0U; repetition < *repetitions; ++repetition) {
        const auto* run = (*runs)[static_cast<std::size_t>(repetition)].as_object();
        const auto* run_id = run == nullptr ? nullptr : string_member(*run, "run_id");
        if (run == nullptr || run_id == nullptr || !run_ids.insert(*run_id).second ||
            string_member(*run, "package") == nullptr ||
            *string_member(*run, "package") != *package ||
            uint_member(*run, "cell_ordinal") != *cell_ordinal ||
            uint_member(*run, "repetition_ordinal") != repetition ||
            string_member(*run, "hardware_state") == nullptr ||
            *string_member(*run, "hardware_state") != *hardware ||
            string_member(*run, "placement") == nullptr ||
            *string_member(*run, "placement") != *placement ||
            string_member(*run, "working_set_class") == nullptr ||
            *string_member(*run, "working_set_class") != *working_set ||
            string_member(*run, "load_level") == nullptr ||
            *string_member(*run, "load_level") != *load ||
            member(*run, "plan_sha256") != nullptr) {
          return failure<ActionOutcome>(
              "$/action_inputs/pilot_plan/cells/runs", "S17-PILOT-RUN",
              "pilot run identity/package or closed shape drifted");
        }
        auto materialized_run = *run;
        materialized_run.emplace("plan_sha256", string_value(*plan_sha));
        auto capture = package_capture(FixedAction::blinded_pilot, materialized_run,
                                       &persistent_contexts);
        if (!capture) {
          return protocol::Result<ActionOutcome>::failure(capture.errors());
        }
        std::ostringstream prefix;
        prefix << "pilot-c" << std::setw(3) << std::setfill('0') << *cell_ordinal
               << "-r" << std::setw(3) << repetition << '-';
        auto payloads = run_artifacts(FixedAction::blinded_pilot, materialized_run,
                                      std::move(capture.value()), prefix.str());
        if (!payloads) {
          return protocol::Result<ActionOutcome>::failure(payloads.errors());
        }
        for (auto& payload : payloads.value()) {
          auto published = sink.publish(std::move(payload));
          if (!published) {
            return protocol::Result<ActionOutcome>::failure(published.errors());
          }
          bindings.push_back(std::move(published.value()));
        }
      }
      ++execution_ordinal;
    }
    if (!whole_plot_control.leave()) {
      return failure<ActionOutcome>(
          "$/action_inputs/pilot_plan/hardware_control",
          "S17-PILOT-HARDWARE-FINAL-RESTORE",
          "final whole-plot hardware state restoration/readback failed");
    }
    if (ordinals.size() != 180U || combinations.size() != 180U ||
        run_ids.size() != static_cast<std::size_t>(*repetitions) * 180U) {
      return failure<ActionOutcome>("$/action_inputs/pilot_plan", "S17-PILOT-COMPLETE",
                                    "pilot Cartesian product is incomplete");
    }
    JsonArray apply_readback;
    for (const auto& value : whole_plot_control.apply_readback()) {
      apply_readback.emplace_back(JsonObject{
          {"cpu", uint_value(value.cpu)},
          {"complete_value_hex", string_value(hex_u64(value.value))},
      });
    }
    JsonArray restore_readback;
    for (const auto& value : whole_plot_control.restore_readback()) {
      restore_readback.emplace_back(JsonObject{
          {"cpu", uint_value(value.cpu)},
          {"complete_value_hex", string_value(hex_u64(value.value))},
      });
    }
    auto hardware_evidence = canonical(JsonObject{
        {"schema_version", string_value("cpu-prefetch-stage17-pilot-hardware-state/1")},
        {"mapping_id", string_value(platform::kHardwarePrefetchMappingId)},
        {"q15_w_result_sha256",
         string_value(*string_member(*hardware_control, "q15_w_result_sha256"))},
        {"whole_plot_order", JsonValue(*whole)},
        {"apply_readback", JsonValue(std::move(apply_readback))},
        {"restore_readback", JsonValue(std::move(restore_readback))},
        {"cell_count", uint_value(180U)},
        {"restoration_verified", JsonValue(true)},
        {"phase18_authority", JsonValue(false)},
    });
    if (!hardware_evidence) {
      return protocol::Result<ActionOutcome>::failure(hardware_evidence.errors());
    }
    auto hardware_binding = sink.publish(
        {"STAGE17_PILOT_HARDWARE_STATE", "cpu-prefetch-stage17-pilot-hardware-state/1",
         "application/json", "stage17-pilot-hardware-state-v1.json",
         bytes(hardware_evidence.value())});
    if (!hardware_binding) {
      return protocol::Result<ActionOutcome>::failure(hardware_binding.errors());
    }
    bindings.push_back(std::move(hardware_binding.value()));
    JsonArray artifact_index;
    artifact_index.reserve(bindings.size());
    for (const auto& item : bindings) {
      artifact_index.emplace_back(JsonObject{
          {"role", string_value(item.role)},
          {"schema_identity", string_value(item.schema_identity)},
          {"file_name", string_value(item.file_name)},
          {"size_bytes", uint_value(item.size_bytes)},
          {"sha256", string_value(item.sha256)},
      });
    }
    auto manifest = canonical(JsonObject{
        {"schema_version",
         string_value("cpu-prefetch-stage17-sealed-pilot-artifact-manifest/3")},
        {"plan_id", string_value(*string_member(*plan, "plan_id"))},
        {"plan_sha256", string_value(*plan_sha)},
        {"cell_count", uint_value(180U)},
        {"repetitions_per_cell", uint_value(*repetitions)},
        {"run_count", uint_value(run_ids.size())},
        {"artifact_count", uint_value(bindings.size())},
        {"artifacts", JsonValue(std::move(artifact_index))},
        {"treatment_blind", JsonValue(true)},
        {"confirmatory_outcomes_accessed", JsonValue(false)},
        {"sealed", JsonValue(true)},
        {"phase18_authority", JsonValue(false)},
    });
    if (!manifest) {
      return protocol::Result<ActionOutcome>::failure(manifest.errors());
    }
    auto manifest_binding = sink.publish(
        {"SEALED_PILOT_ARTIFACT_MANIFEST",
         "cpu-prefetch-stage17-sealed-pilot-artifact-manifest/3", "application/json",
         "stage17-sealed-pilot-manifest-v3.json", bytes(manifest.value())});
    if (!manifest_binding) {
      return protocol::Result<ActionOutcome>::failure(manifest_binding.errors());
    }
    bindings.push_back(std::move(manifest_binding.value()));
    return protocol::Result<ActionOutcome>::success(
        {std::move(bindings), true, false, "PILOT_COMPLETE_SEALED"});
  }
  constexpr std::array q16b_plan_fields{"plan_sha256"sv, "q16a_result_sha256"sv,
                                        "hardware_control"sv, "runs"sv};
  constexpr std::array q16c_plan_fields{"plan_sha256"sv, "q16a_result_sha256"sv,
                                        "q16b_result_sha256"sv, "hardware_control"sv,
                                        "runs"sv};
  constexpr std::array hardware_fields{"mapping_id"sv, "q15_w_result_sha256"sv,
                                       "prestate"sv};
  const auto* parent_plan = string_member(input, "plan_sha256");
  const auto* q16a_result = string_member(input, "q16a_result_sha256");
  const auto* q16b_result = string_member(input, "q16b_result_sha256");
  const auto* hardware_control = require_object(input, "hardware_control");
  const auto hardware_prestate =
      hardware_control == nullptr
          ? failure<std::array<platform::HardwarePrefetchMsrValue, 3U>>(
                "$/action_inputs/hardware_control", "S17-Q16-HARDWARE",
                "Q16 hardware-control binding is absent")
          : parse_prestate(*hardware_control);
  const auto* runs_value = member(input, "runs");
  const auto* runs = runs_value == nullptr ? nullptr : runs_value->as_array();
  const bool exact_plan = action == FixedAction::q16b
                              ? exact_fields(input, q16b_plan_fields)
                              : exact_fields(input, q16c_plan_fields);
  if (!exact_plan || parent_plan == nullptr || q16a_result == nullptr ||
      (action == FixedAction::q16c && q16b_result == nullptr) || runs == nullptr ||
      runs->empty() || hardware_control == nullptr ||
      !exact_fields(*hardware_control, hardware_fields) || !hardware_prestate ||
      string_member(*hardware_control, "mapping_id") == nullptr ||
      *string_member(*hardware_control, "mapping_id") !=
          platform::kHardwarePrefetchMappingId ||
      string_member(*hardware_control, "q15_w_result_sha256") == nullptr) {
    return failure<ActionOutcome>("$/action_inputs", "S17-Q16-PLAN-FAMILY",
                                  "Q16 action requires one exact frozen run family");
  }
  const std::set<std::string> packages{"R0", "R1", "R2", "L0", "L1"};
  const std::set<std::string> states{"H0", "H1"};
  const std::set<std::string> placements{"NEAR", "FAR"};
  const std::set<std::string> working_sets{"L2_RESIDENT", "LLC_RESIDENT", "BEYOND_LLC"};
  const std::set<std::string> loads{"L025", "L050", "L075"};
  std::map<std::string, std::size_t> per_cell;
  std::set<std::string> run_ids;
  std::vector<ArtifactBinding> bindings;
  bindings.reserve(runs->size() * 10U + 1U);
  PilotWholePlotControl whole_plot_control(hardware_prestate.value());
  std::string active_state;
  std::set<std::string> completed_states;
  for (std::size_t index = 0U; index < runs->size(); ++index) {
    const auto* run = (*runs)[index].as_object();
    const auto* package = run == nullptr ? nullptr : string_member(*run, "package");
    const auto* state =
        run == nullptr ? nullptr : string_member(*run, "hardware_state");
    const auto* placement = run == nullptr ? nullptr : string_member(*run, "placement");
    const auto* working_set =
        run == nullptr ? nullptr : string_member(*run, "working_set_class");
    const auto* load = run == nullptr ? nullptr : string_member(*run, "load_level");
    const auto* run_id = run == nullptr ? nullptr : string_member(*run, "run_id");
    const auto ordinal = run == nullptr ? std::optional<std::uint64_t>{}
                                        : uint_member(*run, "cell_ordinal");
    const auto repetition = run == nullptr ? std::optional<std::uint64_t>{}
                                           : uint_member(*run, "repetition_ordinal");
    if (run == nullptr || package == nullptr || !packages.contains(*package) ||
        state == nullptr || !states.contains(*state) || placement == nullptr ||
        !placements.contains(*placement) || working_set == nullptr ||
        !working_sets.contains(*working_set) || run_id == nullptr ||
        !run_ids.insert(*run_id).second || !ordinal || !repetition ||
        string_member(*run, "plan_sha256") == nullptr ||
        *string_member(*run, "plan_sha256") != *parent_plan ||
        string_member(*run, "q16a_result_sha256") == nullptr ||
        *string_member(*run, "q16a_result_sha256") != *q16a_result ||
        (action == FixedAction::q16c &&
         (load == nullptr || !loads.contains(*load) ||
          string_member(*run, "q16b_result_sha256") == nullptr ||
          *string_member(*run, "q16b_result_sha256") != *q16b_result))) {
      return failure<ActionOutcome>("$/action_inputs/runs", "S17-Q16-RUN-FAMILY",
                                    "Q16 run context/lineage is invalid");
    }
    if (active_state != *state) {
      if (!active_state.empty()) {
        if (!whole_plot_control.leave()) {
          return failure<ActionOutcome>(
              "$/action_inputs/hardware_control", "S17-Q16-RESTORE",
              "Q16 prior hardware whole plot could not be restored");
        }
        completed_states.insert(active_state);
      }
      if (completed_states.contains(*state) || !whole_plot_control.enter(*state)) {
        return failure<ActionOutcome>("$/action_inputs/hardware_control",
                                      "S17-Q16-HARDWARE-ENTER",
                                      "Q16 hardware whole-plot order/readback failed");
      }
      active_state = *state;
    }
    const auto key = *package + "/" + *state + "/" + *placement + "/" + *working_set +
                     (action == FixedAction::q16c ? "/" + *load : std::string{});
    ++per_cell[key];
    auto capture = package_capture(action, *run);
    if (!capture) {
      return protocol::Result<ActionOutcome>::failure(capture.errors());
    }
    std::ostringstream prefix;
    prefix << (action == FixedAction::q16b ? "q16b-r" : "q16c-r") << std::setw(5)
           << std::setfill('0') << index << '-';
    auto artifacts =
        run_artifacts(action, *run, std::move(capture.value()), prefix.str());
    if (!artifacts) {
      return protocol::Result<ActionOutcome>::failure(artifacts.errors());
    }
    for (auto& payload : artifacts.value()) {
      auto published = sink.publish(std::move(payload));
      if (!published) {
        return protocol::Result<ActionOutcome>::failure(published.errors());
      }
      bindings.push_back(std::move(published.value()));
    }
  }
  const std::size_t expected_cells = action == FixedAction::q16b ? 60U : 180U;
  const std::size_t minimum_runs = action == FixedAction::q16b ? 59U : 1U;
  if (per_cell.size() != expected_cells ||
      std::any_of(per_cell.begin(), per_cell.end(), [minimum_runs](const auto& item) {
        return item.second < minimum_runs;
      })) {
    return failure<ActionOutcome>("$/action_inputs/runs", "S17-Q16-MATRIX",
                                  "Q16 frozen matrix is incomplete");
  }
  if (!whole_plot_control.leave()) {
    return failure<ActionOutcome>(
        "$/action_inputs/hardware_control", "S17-Q16-FINAL-RESTORE",
        "Q16 final hardware whole plot could not be restored");
  }
  auto hardware = publish_calibration_hardware_evidence(
      sink, action, *parent_plan,
      *string_member(*hardware_control, "q15_w_result_sha256"), runs->size(),
      whole_plot_control);
  if (!hardware) {
    return protocol::Result<ActionOutcome>::failure(hardware.errors());
  }
  bindings.push_back(std::move(hardware.value()));
  return protocol::Result<ActionOutcome>::success(
      {std::move(bindings), true, false, "CALIBRATION_CAPTURE_COMPLETE"});
}

[[nodiscard]] auto validate_request(const JsonObject& request, FixedAction action,
                                    bool synthetic_backend)
    -> protocol::Result<const JsonObject*> {
  constexpr std::array fields{
      "schema_version"sv,
      "request_id"sv,
      "action_id"sv,
      "stand_id"sv,
      "authorization_id"sv,
      "attempt_id"sv,
      "runtime_binding"sv,
      "release_binding"sv,
      "evidence_root_binding"sv,
      "predecessor_resolutions"sv,
      "action_inputs"sv,
      "synthetic_test_only"sv,
      "phase18_authority"sv,
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
      require_object(request, "evidence_root_binding") == nullptr ||
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

[[nodiscard]] auto validate_context(const JsonObject& context,
                                    const JsonObject& request,
                                    std::string_view request_bytes, FixedAction action)
    -> bool {
  constexpr std::array context_fields{"schema_version"sv,
                                      "authorization_id"sv,
                                      "authorization_sha256"sv,
                                      "request_id"sv,
                                      "request_sha256"sv,
                                      "attempt_id"sv,
                                      "action_id"sv,
                                      "fixed_action_definition_sha256"sv,
                                      "runtime_sha256"sv,
                                      "release_sha256"sv,
                                      "predecessor_sha256s"sv,
                                      "synthetic_test_only"sv,
                                      "phase18_authority"sv};
  return exact_fields(context, context_fields) &&
         string_member(context, "schema_version") != nullptr &&
         *string_member(context, "schema_version") == kFixedActionContextSchema &&
         string_member(context, "authorization_id") != nullptr &&
         string_member(context, "authorization_sha256") != nullptr &&
         string_member(context, "request_id") != nullptr &&
         string_member(context, "request_sha256") != nullptr &&
         string_member(context, "attempt_id") != nullptr &&
         string_member(context, "action_id") != nullptr &&
         string_member(context, "fixed_action_definition_sha256") != nullptr &&
         string_member(context, "runtime_sha256") != nullptr &&
         string_member(context, "release_sha256") != nullptr &&
         member(context, "predecessor_sha256s") != nullptr &&
         member(context, "predecessor_sha256s")->as_array() != nullptr &&
         bool_member(context, "synthetic_test_only") != nullptr &&
         bool_member(context, "phase18_authority") != nullptr &&
         !*bool_member(context, "phase18_authority") &&
         *string_member(context, "authorization_id") ==
             *string_member(request, "authorization_id") &&
         *string_member(context, "request_id") ==
             *string_member(request, "request_id") &&
         *string_member(context, "request_sha256") == sha256(request_bytes) &&
         *string_member(context, "attempt_id") ==
             *string_member(request, "attempt_id") &&
         *string_member(context, "action_id") == to_string(action);
}

[[nodiscard]] auto emit_action_result(
    int output_fd, std::string_view result_name, const JsonObject& request,
    std::string_view request_bytes, const JsonObject& context, FixedAction action,
    const ActionOutcome& outcome, bool synthetic_test_only, std::string_view started_at,
    std::chrono::steady_clock::time_point started) -> std::string {
  JsonArray artifact_bindings;
  for (const auto& artifact : outcome.artifacts) {
    artifact_bindings.emplace_back(JsonObject{
        {"role", string_value(artifact.role)},
        {"schema_identity", string_value(artifact.schema_identity)},
        {"media_type", string_value(artifact.media_type)},
        {"file_name", string_value(artifact.file_name)},
        {"size_bytes", uint_value(artifact.size_bytes)},
        {"sha256", string_value(artifact.sha256)},
    });
  }
  const auto* runtime = require_object(request, "runtime_binding");
  const auto* release = require_object(request, "release_binding");
  const auto duration = std::chrono::duration_cast<std::chrono::nanoseconds>(
                            std::chrono::steady_clock::now() - started)
                            .count();
  JsonObject result{
      {"schema_version", string_value(kFixedActionResultSchema)},
      {"result_id", string_value(*string_member(request, "attempt_id") + ":result")},
      {"request_id", string_value(*string_member(request, "request_id"))},
      {"request_sha256", string_value(sha256(request_bytes))},
      {"action_id", string_value(to_string(action))},
      {"stand_id", string_value(*string_member(request, "stand_id"))},
      {"authorization_id", string_value(*string_member(request, "authorization_id"))},
      {"authorization_sha256",
       string_value(*string_member(context, "authorization_sha256"))},
      {"attempt_id", string_value(*string_member(request, "attempt_id"))},
      {"runtime_binding", JsonValue(*runtime)},
      {"release_binding", JsonValue(*release)},
      {"predecessor_resolutions",
       JsonValue(*member(request, "predecessor_resolutions")->as_array())},
      {"artifacts", JsonValue(std::move(artifact_bindings))},
      {"started_at_utc", string_value(started_at)},
      {"completed_at_utc", string_value(utc_now())},
      {"duration_ns", uint_value(static_cast<std::uint64_t>(duration))},
      {"terminal_state", string_value(outcome.terminal_state)},
      {"restoration_verified", JsonValue(outcome.restoration_verified)},
      {"quarantined", JsonValue(outcome.quarantined)},
      {"synthetic_test_only", JsonValue(synthetic_test_only)},
      {"phase18_authority", JsonValue(false)},
  };
  const auto encoded = canonical(std::move(result));
  if (!encoded) {
    throw std::runtime_error("fixed action result serialization failed");
  }
  write_exclusive(output_fd, result_name, bytes(encoded.value()));
  return sha256(encoded.value());
}

[[nodiscard]] auto receive_packet(int descriptor) -> std::string {
  std::array<unsigned char, 4U> length_bytes{};
  std::size_t length_offset = 0U;
  while (length_offset != length_bytes.size()) {
    const auto count = ::read(descriptor, length_bytes.data() + length_offset,
                              length_bytes.size() - length_offset);
    if (count < 0 && errno == EINTR) {
      continue;
    }
    if (count <= 0) {
      throw std::runtime_error("Q15 session control frame is absent");
    }
    length_offset += static_cast<std::size_t>(count);
  }
  const auto length = (static_cast<std::size_t>(length_bytes[0]) << 24U) |
                      (static_cast<std::size_t>(length_bytes[1]) << 16U) |
                      (static_cast<std::size_t>(length_bytes[2]) << 8U) |
                      static_cast<std::size_t>(length_bytes[3]);
  if (length == 0U || length > kMaximumRequestBytes) {
    throw std::runtime_error("Q15 session control packet is absent or oversized");
  }
  std::string buffer(length, '\0');
  std::size_t offset = 0U;
  while (offset != length) {
    const auto count = ::read(descriptor, buffer.data() + offset, length - offset);
    if (count < 0 && errno == EINTR) {
      continue;
    }
    if (count <= 0) {
      throw std::runtime_error("Q15 session control frame was truncated");
    }
    offset += static_cast<std::size_t>(count);
  }
  return buffer;
}

} // namespace

auto self_executable_sha256() -> protocol::Result<std::string> {
  const int descriptor = ::open("/proc/self/exe", O_RDONLY | O_CLOEXEC);
  if (descriptor < 0) {
    return failure<std::string>("$/runtime", "S17-RUNTIME-SELF-OPEN",
                                "cannot open mapped executable identity");
  }
  std::vector<std::byte> payload;
  std::array<std::byte, static_cast<std::size_t>(64U) * 1024U> buffer{};
  for (;;) {
    const auto count = ::read(descriptor, buffer.data(), buffer.size());
    if (count < 0 && errno == EINTR) {
      continue;
    }
    if (count < 0) {
      static_cast<void>(::close(descriptor));
      return failure<std::string>("$/runtime", "S17-RUNTIME-SELF-READ",
                                  "mapped executable read failed");
    }
    if (count == 0) {
      break;
    }
    if (payload.size() + static_cast<std::size_t>(count) > kMaximumWorkerBytes) {
      static_cast<void>(::close(descriptor));
      return failure<std::string>("$/runtime", "S17-RUNTIME-SELF-SIZE",
                                  "mapped executable exceeds fixed bound");
    }
    payload.insert(payload.end(), buffer.begin(),
                   buffer.begin() + static_cast<std::ptrdiff_t>(count));
  }
  static_cast<void>(::close(descriptor));
  if (payload.empty()) {
    return failure<std::string>("$/runtime", "S17-RUNTIME-SELF-EMPTY",
                                "mapped executable is empty");
  }
  return protocol::Result<std::string>::success(sha256(payload));
}

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
    FixedAction action, const protocol::json::Value::Object& action_inputs,
    ArtifactSink& sink) -> protocol::Result<ActionOutcome> {
  switch (action) {
  case FixedAction::q15_r:
  case FixedAction::q15_w:
    return failure<ActionOutcome>(
        "$/action_id", "S17-Q15-PHASE-SESSION-REQUIRED",
        "Q15-R/Q15-W are accepted only through the phase-spanning same-buffer "
        "session entrypoint");
  case FixedAction::q16a:
    return q16a_plan(action_inputs, sink);
  case FixedAction::q16b:
  case FixedAction::q16c:
  case FixedAction::blinded_pilot:
    return q16_or_pilot(action, action_inputs, sink);
  }
  return failure<ActionOutcome>("$/action_id", "S17-WORKER-DISPATCH",
                                "fixed action dispatcher is incomplete");
}

auto run_fixed_action_worker(int argc, char** argv, FixedActionOperations& operations)
    -> int {
  if (argc != 10 || std::string_view(argv[1]) != "--execute-fixed-stage17-action-v3" ||
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
  if (context == nullptr ||
      !validate_context(*context, request, request_bytes.value(), action.value())) {
    throw std::runtime_error("fixed dispatcher authority context rejected");
  }
  const auto inputs =
      validate_request(request, action.value(), operations.synthetic_test_only());
  if (!inputs) {
    throw std::runtime_error("fixed dispatcher request semantics rejected: " +
                             inputs.errors().front().rule_id + ": " +
                             inputs.errors().front().message);
  }
  DirectoryArtifactSink sink(*output_fd);
  const auto outcome = operations.execute(action.value(), *inputs.value(), sink);
  if (!outcome) {
    throw std::runtime_error(
        "fixed action operation failed closed: " + outcome.errors().front().rule_id +
        ": " + outcome.errors().front().message);
  }
  static_cast<void>(
      emit_action_result(*output_fd, kResultFileName, request, request_bytes.value(),
                         *context, action.value(), outcome.value(),
                         operations.synthetic_test_only(), started_at, started));
  return 0;
}

auto run_q15_phase_session_worker(int argc, char** argv) -> int {
  if (argc != 11 || std::string_view(argv[1]) != "--execute-stage17-q15-session-v1" ||
      std::string_view(argv[2]) != "--q15-r-request-fd" ||
      std::string_view(argv[4]) != "--q15-r-context-fd" ||
      std::string_view(argv[6]) != "--q15-w-control-fd" ||
      std::string_view(argv[8]) != "--output-dir-fd" ||
      std::string_view(argv[10]) != "--fixed-dispatch-end") {
    throw std::runtime_error("Q15 phase-session argv contract rejected");
  }
  const auto q15_r_request_fd = parse_fd(argv[3]);
  const auto q15_r_context_fd = parse_fd(argv[5]);
  const auto control_fd = parse_fd(argv[7]);
  const auto output_fd = parse_fd(argv[9]);
  if (!q15_r_request_fd || !q15_r_context_fd || !control_fd || !output_fd) {
    throw std::runtime_error("Q15 phase-session fd contract rejected");
  }
  validate_output_fd(*output_fd);
  const auto q15_r_started_at = utc_now();
  const auto q15_r_started = std::chrono::steady_clock::now();
  const auto q15_r_request_bytes = read_regular_fd(*q15_r_request_fd);
  const auto q15_r_context_bytes = read_regular_fd(*q15_r_context_fd);
  if (!q15_r_request_bytes || !q15_r_context_bytes) {
    throw std::runtime_error("Q15-R sealed input read failed");
  }
  const auto parsed_request = protocol::json::parse(q15_r_request_bytes.value());
  const auto parsed_context = protocol::json::parse(q15_r_context_bytes.value());
  const auto* q15_r_request =
      parsed_request && parsed_request.value().as_object() != nullptr
          ? parsed_request.value().as_object()
          : nullptr;
  const auto* q15_r_context =
      parsed_context && parsed_context.value().as_object() != nullptr
          ? parsed_context.value().as_object()
          : nullptr;
  if (q15_r_request == nullptr || q15_r_context == nullptr ||
      !validate_context(*q15_r_context, *q15_r_request, q15_r_request_bytes.value(),
                        FixedAction::q15_r)) {
    throw std::runtime_error("Q15-R authority context rejected");
  }
  const auto q15_r_inputs = validate_request(*q15_r_request, FixedAction::q15_r, false);
  if (!q15_r_inputs) {
    throw std::runtime_error("Q15-R request semantics rejected");
  }
  auto q15_r_bound_inputs = *q15_r_inputs.value();
  q15_r_bound_inputs.insert_or_assign(
      "authorization_sha256",
      string_value(*string_member(*q15_r_context, "authorization_sha256")));
  auto session = load_q15_phase_session(q15_r_bound_inputs);
  if (!session) {
    throw std::runtime_error("Q15-R same-buffer session preparation failed: " +
                             session.errors().front().rule_id);
  }
  DirectoryArtifactSink sink(*output_fd);
  const auto q15_r_outcome = publish_q15_r(q15_r_bound_inputs, *session.value(), sink);
  if (!q15_r_outcome) {
    throw std::runtime_error("Q15-R evidence publication failed");
  }
  const auto q15_r_result_sha = emit_action_result(
      *output_fd, "stage17-q15-r-result-v3.json", *q15_r_request,
      q15_r_request_bytes.value(), *q15_r_context, FixedAction::q15_r,
      q15_r_outcome.value(), false, q15_r_started_at, q15_r_started);
  const auto waiting = canonical(JsonObject{
      {"schema_version", string_value("cpu-prefetch-stage17-q15-session-waiting/1")},
      {"session_id", string_value(session.value()->session_id)},
      {"q15_r_request_sha256", string_value(sha256(q15_r_request_bytes.value()))},
      {"q15_r_result_sha256", string_value(q15_r_result_sha)},
      {"state", string_value("H0_SEALED_WAITING_FOR_Q15_W")},
      {"same_buffer_retained", JsonValue(true)},
      {"phase18_authority", JsonValue(false)},
  });
  if (!waiting) {
    throw std::runtime_error("Q15 waiting record serialization failed");
  }
  write_exclusive(*output_fd, "stage17-q15-session-waiting-v1.json",
                  bytes(waiting.value()));

  const auto q15_w_request_bytes = receive_packet(*control_fd);
  const auto q15_w_context_bytes = receive_packet(*control_fd);
  const auto q15_w_started_at = utc_now();
  const auto q15_w_started = std::chrono::steady_clock::now();
  const auto parsed_q15_w_request = protocol::json::parse(q15_w_request_bytes);
  const auto parsed_q15_w_context = protocol::json::parse(q15_w_context_bytes);
  const auto* q15_w_request =
      parsed_q15_w_request && parsed_q15_w_request.value().as_object() != nullptr
          ? parsed_q15_w_request.value().as_object()
          : nullptr;
  const auto* q15_w_context =
      parsed_q15_w_context && parsed_q15_w_context.value().as_object() != nullptr
          ? parsed_q15_w_context.value().as_object()
          : nullptr;
  if (q15_w_request == nullptr || q15_w_context == nullptr ||
      !validate_context(*q15_w_context, *q15_w_request, q15_w_request_bytes,
                        FixedAction::q15_w)) {
    throw std::runtime_error("Q15-W authority context rejected");
  }
  const auto q15_w_inputs = validate_request(*q15_w_request, FixedAction::q15_w, false);
  if (!q15_w_inputs ||
      string_member(*q15_w_inputs.value(), "q15_r_result_sha256") == nullptr ||
      *string_member(*q15_w_inputs.value(), "q15_r_result_sha256") !=
          q15_r_result_sha) {
    throw std::runtime_error("Q15-W sealed Q15-R lineage rejected");
  }
  auto q15_w_bound_inputs = *q15_w_inputs.value();
  q15_w_bound_inputs.insert_or_assign(
      "authorization_sha256",
      string_value(*string_member(*q15_w_context, "authorization_sha256")));
  const auto q15_w_outcome = q15_w(q15_w_bound_inputs, *session.value(), sink);
  if (!q15_w_outcome) {
    throw std::runtime_error("Q15-W transaction failed closed: " +
                             q15_w_outcome.errors().front().rule_id);
  }
  static_cast<void>(emit_action_result(
      *output_fd, "stage17-q15-w-result-v3.json", *q15_w_request, q15_w_request_bytes,
      *q15_w_context, FixedAction::q15_w, q15_w_outcome.value(), false,
      q15_w_started_at, q15_w_started));
  return 0;
}

auto run_test_q15_phase_session_worker(int argc, char** argv,
                                       FixedActionOperations& operations) -> int {
  if (!operations.synthetic_test_only() || argc != 11 ||
      std::string_view(argv[1]) != "--execute-stage17-q15-session-v1" ||
      std::string_view(argv[2]) != "--q15-r-request-fd" ||
      std::string_view(argv[4]) != "--q15-r-context-fd" ||
      std::string_view(argv[6]) != "--q15-w-control-fd" ||
      std::string_view(argv[8]) != "--output-dir-fd" ||
      std::string_view(argv[10]) != "--fixed-dispatch-end") {
    throw std::runtime_error("test Q15 phase-session argv contract rejected");
  }
  const auto request_fd = parse_fd(argv[3]);
  const auto context_fd = parse_fd(argv[5]);
  const auto control_fd = parse_fd(argv[7]);
  const auto output_fd = parse_fd(argv[9]);
  if (!request_fd || !context_fd || !control_fd || !output_fd) {
    throw std::runtime_error("test Q15 phase-session fd contract rejected");
  }
  validate_output_fd(*output_fd);
  const auto q15r_request_bytes = read_regular_fd(*request_fd);
  const auto q15r_context_bytes = read_regular_fd(*context_fd);
  if (!q15r_request_bytes || !q15r_context_bytes) {
    throw std::runtime_error("test Q15-R sealed input read failed");
  }
  const auto q15r_parsed = protocol::json::parse(q15r_request_bytes.value());
  const auto q15r_context_parsed = protocol::json::parse(q15r_context_bytes.value());
  const auto* q15r_request = q15r_parsed && q15r_parsed.value().as_object() != nullptr
                                 ? q15r_parsed.value().as_object()
                                 : nullptr;
  const auto* q15r_context =
      q15r_context_parsed && q15r_context_parsed.value().as_object() != nullptr
          ? q15r_context_parsed.value().as_object()
          : nullptr;
  if (q15r_request == nullptr || q15r_context == nullptr ||
      !validate_context(*q15r_context, *q15r_request, q15r_request_bytes.value(),
                        FixedAction::q15_r)) {
    throw std::runtime_error("test Q15-R authority context rejected");
  }
  const auto q15r_inputs = validate_request(*q15r_request, FixedAction::q15_r, true);
  if (!q15r_inputs) {
    throw std::runtime_error("test Q15-R request semantics rejected");
  }
  DirectoryArtifactSink sink(*output_fd);
  const auto q15r_started_at = utc_now();
  const auto q15r_started = std::chrono::steady_clock::now();
  auto q15r_bound_inputs = *q15r_inputs.value();
  q15r_bound_inputs.insert_or_assign(
      "authorization_sha256",
      string_value(*string_member(*q15r_context, "authorization_sha256")));
  const auto q15r_outcome =
      operations.execute(FixedAction::q15_r, q15r_bound_inputs, sink);
  if (!q15r_outcome) {
    throw std::runtime_error("test Q15-R operation failed closed");
  }
  const auto q15r_result_sha =
      emit_action_result(*output_fd, "stage17-q15-r-result-v3.json", *q15r_request,
                         q15r_request_bytes.value(), *q15r_context, FixedAction::q15_r,
                         q15r_outcome.value(), true, q15r_started_at, q15r_started);
  const auto* session_id = string_member(q15r_bound_inputs, "session_id");
  if (session_id == nullptr) {
    throw std::runtime_error("test Q15-R session identity is absent");
  }
  const auto waiting = canonical(JsonObject{
      {"schema_version", string_value("cpu-prefetch-stage17-q15-session-waiting/1")},
      {"session_id", string_value(*session_id)},
      {"q15_r_request_sha256", string_value(sha256(q15r_request_bytes.value()))},
      {"q15_r_result_sha256", string_value(q15r_result_sha)},
      {"state", string_value("H0_SEALED_WAITING_FOR_Q15_W")},
      {"same_buffer_retained", JsonValue(true)},
      {"phase18_authority", JsonValue(false)},
  });
  if (!waiting) {
    throw std::runtime_error("test Q15 waiting serialization failed");
  }
  write_exclusive(*output_fd, "stage17-q15-session-waiting-v1.json",
                  bytes(waiting.value()));
  const auto q15w_request_bytes = receive_packet(*control_fd);
  const auto q15w_context_bytes = receive_packet(*control_fd);
  const auto q15w_parsed = protocol::json::parse(q15w_request_bytes);
  const auto q15w_context_parsed = protocol::json::parse(q15w_context_bytes);
  const auto* q15w_request = q15w_parsed && q15w_parsed.value().as_object() != nullptr
                                 ? q15w_parsed.value().as_object()
                                 : nullptr;
  const auto* q15w_context =
      q15w_context_parsed && q15w_context_parsed.value().as_object() != nullptr
          ? q15w_context_parsed.value().as_object()
          : nullptr;
  if (q15w_request == nullptr || q15w_context == nullptr ||
      !validate_context(*q15w_context, *q15w_request, q15w_request_bytes,
                        FixedAction::q15_w)) {
    throw std::runtime_error("test Q15-W authority context rejected");
  }
  const auto q15w_inputs = validate_request(*q15w_request, FixedAction::q15_w, true);
  if (!q15w_inputs ||
      string_member(*q15w_inputs.value(), "q15_r_result_sha256") == nullptr ||
      *string_member(*q15w_inputs.value(), "q15_r_result_sha256") != q15r_result_sha) {
    throw std::runtime_error("test Q15-W exact Q15-R lineage rejected");
  }
  const auto q15w_started_at = utc_now();
  const auto q15w_started = std::chrono::steady_clock::now();
  auto q15w_bound_inputs = *q15w_inputs.value();
  q15w_bound_inputs.insert_or_assign(
      "authorization_sha256",
      string_value(*string_member(*q15w_context, "authorization_sha256")));
  const auto q15w_outcome =
      operations.execute(FixedAction::q15_w, q15w_bound_inputs, sink);
  if (!q15w_outcome) {
    throw std::runtime_error("test Q15-W operation failed closed");
  }
  static_cast<void>(emit_action_result(*output_fd, "stage17-q15-w-result-v3.json",
                                       *q15w_request, q15w_request_bytes, *q15w_context,
                                       FixedAction::q15_w, q15w_outcome.value(), true,
                                       q15w_started_at, q15w_started));
  return 0;
}

} // namespace cpu_prefetch::runner::stage17
