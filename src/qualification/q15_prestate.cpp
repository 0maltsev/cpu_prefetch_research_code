#include "cpu_prefetch/qualification/q15_prestate.hpp"

#include "cpu_prefetch/protocol/json.hpp"
#include "cpu_prefetch/workload/deterministic.hpp"

#include <fcntl.h>
#include <poll.h>
#include <spawn.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#include <algorithm>
#include <array>
#include <cerrno>
#include <chrono>
#include <cstdio>
#include <cstring>
#include <limits>
#include <stdexcept>
#include <string>
#include <system_error>
#include <utility>

namespace cpu_prefetch::qualification {
namespace {

using protocol::ErrorCategory;
using protocol::ValidationError;
using protocol::json::Value;
using JsonArray = Value::Array;
using JsonObject = Value::Object;

[[nodiscard]] auto error(ErrorCategory category, std::string path, std::string rule,
                         std::string message) -> ValidationError {
  return {category, std::move(path), std::move(rule), std::move(message)};
}

[[nodiscard]] auto signed_value(std::int64_t value) -> Value {
  return Value(protocol::json::Number{protocol::json::Number::Kind::signed_integer,
                                      std::to_string(value), value});
}

[[nodiscard]] auto nullable_signed(std::optional<int> value) -> Value {
  return value.has_value() ? signed_value(*value) : Value(nullptr);
}

[[nodiscard]] auto string_array(std::span<const std::string> values) -> Value {
  JsonArray output;
  output.reserve(values.size());
  for (const auto& value : values) {
    output.emplace_back(value);
  }
  return Value(std::move(output));
}

[[nodiscard]] auto hex_bytes(std::string_view input) -> std::string {
  static constexpr std::string_view alphabet = "0123456789abcdef";
  std::string output;
  output.reserve(input.size() * 2U);
  for (const char character : input) {
    const auto value = static_cast<unsigned char>(character);
    output.push_back(alphabet[value >> 4U]);
    output.push_back(alphabet[value & 0x0fU]);
  }
  return output;
}

[[nodiscard]] auto valid_identifier(std::string_view value) -> bool {
  return !value.empty() && value.size() <= 128U &&
         std::all_of(value.begin(), value.end(), [](char character) {
           return (character >= 'a' && character <= 'z') ||
                  (character >= 'A' && character <= 'Z') ||
                  (character >= '0' && character <= '9') || character == '-' ||
                  character == '_' || character == '.';
         });
}

[[nodiscard]] auto valid_rfc3339_nanoseconds(std::string_view value) -> bool {
  if (value.size() != 30U || value[4] != '-' || value[7] != '-' || value[10] != 'T' ||
      value[13] != ':' || value[16] != ':' || value[19] != '.' || value[29] != 'Z') {
    return false;
  }
  for (std::size_t index = 0U; index < value.size(); ++index) {
    if (index == 4U || index == 7U || index == 10U || index == 13U || index == 16U ||
        index == 19U || index == 29U) {
      continue;
    }
    if (value[index] < '0' || value[index] > '9') {
      return false;
    }
  }
  return true;
}

[[nodiscard]] auto valid_lower_hex(std::string_view value) -> bool {
  return value.size() % 2U == 0U &&
         std::all_of(value.begin(), value.end(), [](char character) {
           return (character >= '0' && character <= '9') ||
                  (character >= 'a' && character <= 'f');
         });
}

[[nodiscard]] auto validate_context(const Q15StandPrestateContext& context)
    -> std::vector<ValidationError> {
  std::vector<ValidationError> errors;
  if (!valid_identifier(context.capture_id)) {
    errors.push_back(error(ErrorCategory::invalid_id, "$/capture_id", "P4R-ID",
                           "capture ID must be an opaque portable identifier"));
  }
  for (const auto [value, path] :
       {std::pair<std::string_view, std::string_view>{context.authorization_sha256,
                                                      "$/authorization_sha256"},
        {context.collector_binary_sha256, "$/collector_binary_sha256"},
        {context.collector_contract_sha256, "$/collector_contract_sha256"},
        {context.selected_release_archive_sha256,
         "$/selected_release_archive_sha256"}}) {
    if (!protocol::Sha256::parse(value, std::string(path))) {
      errors.push_back(error(ErrorCategory::invalid_hash, std::string(path),
                             "P4R-SHA256", "required binding is not SHA-256"));
    }
  }
  if (context.collector_contract_sha256 != kQ15StandPrestateCollectorContractSha256) {
    errors.push_back(error(ErrorCategory::reference_mismatch,
                           "$/collector_contract_sha256", "P4R-CONTRACT-HASH",
                           "collector contract hash differs from the frozen contract"));
  }
  if (context.selected_release_archive_sha256 != kQ15SelectedReleaseArchiveSha256) {
    errors.push_back(error(ErrorCategory::reference_mismatch,
                           "$/selected_release_archive_sha256", "P4R-RELEASE-HASH",
                           "selected release differs from D-065"));
  }
  if (context.stand_id != "XEON-CPU-FETCH") {
    errors.push_back(error(ErrorCategory::reference_mismatch, "$/stand_id", "P4R-STAND",
                           "stand ID differs from the accepted target"));
  }
  if (context.source_revision.size() != 40U ||
      !std::all_of(context.source_revision.begin(), context.source_revision.end(),
                   [](char character) {
                     return (character >= '0' && character <= '9') ||
                            (character >= 'a' && character <= 'f');
                   })) {
    errors.push_back(error(ErrorCategory::invalid_id, "$/source_revision", "P4R-SOURCE",
                           "source revision must be a full Git hash"));
  }
  return errors;
}

[[nodiscard]] auto accepted_exit(const Q15StandPrestateCommand& command,
                                 const Q15StandPrestateExecution& execution) -> bool {
  return execution.launched && !execution.timed_out &&
         !execution.output_limit_exceeded && execution.spawn_error == 0 &&
         execution.exit_code.has_value() && !execution.terminating_signal.has_value() &&
         std::ranges::find(command.accepted_exit_codes, *execution.exit_code) !=
             command.accepted_exit_codes.end();
}

[[nodiscard]] auto failure_category(const Q15StandPrestateCommand& command,
                                    const Q15StandPrestateExecution& execution,
                                    bool total_limit_exceeded) -> std::string {
  if (!execution.launched) {
    return "SPAWN_FAILURE";
  }
  if (execution.timed_out) {
    return "COMMAND_TIMEOUT";
  }
  if (execution.output_limit_exceeded) {
    return "COMMAND_OUTPUT_LIMIT";
  }
  if (total_limit_exceeded) {
    return "TOTAL_OUTPUT_LIMIT";
  }
  if (execution.spawn_error != 0) {
    return "CAPTURE_FAILURE";
  }
  if (execution.terminating_signal.has_value()) {
    return "COMMAND_SIGNAL";
  }
  if (!execution.exit_code.has_value()) {
    return "MISSING_EXIT_STATUS";
  }
  if (std::ranges::find(command.accepted_exit_codes, *execution.exit_code) ==
      command.accepted_exit_codes.end()) {
    return "UNEXPECTED_EXIT_CODE";
  }
  return "UNKNOWN_FAILURE";
}

[[nodiscard]] auto artifact_document(const Q15StandPrestateArtifact& artifact,
                                     std::string artifact_sha256) -> Value {
  JsonArray observations;
  observations.reserve(artifact.observations.size());
  for (const auto& observation : artifact.observations) {
    observations.emplace_back(JsonObject{
        {"accepted", Value(observation.accepted)},
        {"argv", string_array(observation.argv)},
        {"command_id", Value(observation.command_id)},
        {"ended_at_utc", Value(observation.ended_at_utc)},
        {"exit_code", nullable_signed(observation.exit_code)},
        {"launched", Value(observation.launched)},
        {"observation_kind", Value(observation.observation_kind)},
        {"output_limit_exceeded", Value(observation.output_limit_exceeded)},
        {"spawn_error", signed_value(observation.spawn_error)},
        {"started_at_utc", Value(observation.started_at_utc)},
        {"stderr_hex", Value(observation.stderr_hex)},
        {"stdout_hex", Value(observation.stdout_hex)},
        {"terminating_signal", nullable_signed(observation.terminating_signal)},
        {"timed_out", Value(observation.timed_out)},
    });
  }
  return Value(JsonObject{
      {"artifact_hash_profile",
       Value(std::string(kQ15StandPrestateArtifactHashProfile))},
      {"artifact_sha256", Value(std::move(artifact_sha256))},
      {"authorization_sha256", Value(artifact.context.authorization_sha256)},
      {"canonicalization", Value(std::string(protocol::kCanonicalizationSuite))},
      {"capture_id", Value(artifact.context.capture_id)},
      {"collector_binary_sha256", Value(artifact.context.collector_binary_sha256)},
      {"collector_contract_id",
       Value(std::string(kQ15StandPrestateCollectorContractId))},
      {"collector_contract_sha256", Value(artifact.context.collector_contract_sha256)},
      {"completion_state", Value(std::string(to_string(artifact.completion)))},
      {"failed_command_id", artifact.failed_command_id.has_value()
                                ? Value(*artifact.failed_command_id)
                                : Value(nullptr)},
      {"failure_category", artifact.failure_category.has_value()
                               ? Value(*artifact.failure_category)
                               : Value(nullptr)},
      {"observations", Value(std::move(observations))},
      {"protocol_version", Value(std::string(protocol::kProtocolVersion))},
      {"schema_version", Value(std::string(kQ15StandPrestateArtifactSchemaVersion))},
      {"selected_release_archive_sha256",
       Value(artifact.context.selected_release_archive_sha256)},
      {"source_revision", Value(artifact.context.source_revision)},
      {"stand_id", Value(artifact.context.stand_id)},
  });
}

[[nodiscard]] auto canonical_and_hash(Q15StandPrestateArtifact& artifact)
    -> protocol::Result<std::string> {
  const auto zero =
      protocol::json::canonicalize(artifact_document(artifact, std::string(64U, '0')));
  if (!zero) {
    return protocol::Result<std::string>::failure(zero.errors());
  }
  const auto bytes = std::as_bytes(std::span(zero.value().data(), zero.value().size()));
  artifact.artifact_sha256 = workload::sha256(bytes).hex();
  const auto canonical = protocol::json::canonicalize(
      artifact_document(artifact, artifact.artifact_sha256));
  if (!canonical) {
    return protocol::Result<std::string>::failure(canonical.errors());
  }
  return protocol::Result<std::string>::success(canonical.value());
}

void close_descriptor(int& descriptor) noexcept {
  if (descriptor >= 0) {
    static_cast<void>(::close(descriptor));
    descriptor = -1;
  }
}

void drain_descriptor(int& descriptor, std::string& output, std::size_t maximum,
                      Q15StandPrestateExecution& result) {
  std::array<char, 8192U> buffer{};
  while (descriptor >= 0) {
    const auto count = ::read(descriptor, buffer.data(), buffer.size());
    if (count > 0) {
      const auto size = static_cast<std::size_t>(count);
      if (size > maximum - std::min(maximum, output.size())) {
        result.output_limit_exceeded = true;
        close_descriptor(descriptor);
        return;
      }
      output.append(buffer.data(), size);
      continue;
    }
    if (count == 0) {
      close_descriptor(descriptor);
      return;
    }
    if (errno == EINTR) {
      continue;
    }
    if (errno == EAGAIN || errno == EWOULDBLOCK) {
      return;
    }
    result.spawn_error = errno;
    close_descriptor(descriptor);
    return;
  }
}

[[nodiscard]] auto commands() -> std::vector<Q15StandPrestateCommand> {
  const auto stat = [](std::string id, std::string kind, std::string path) {
    return Q15StandPrestateCommand{
        std::move(id),
        std::move(kind),
        {"/usr/bin/stat", "--format=%n|%F|%a|%u|%g|%s|%d|%i", "--", std::move(path)},
        {0, 1}};
  };
  std::vector<Q15StandPrestateCommand> result{
      {"P4R-001",
       "KERNEL_MACHINE",
       {"/usr/bin/uname", "--kernel-name", "--kernel-release", "--machine"},
       {0}},
      {"P4R-002", "HOSTNAME", {"/usr/bin/hostname"}, {0}},
      {"P4R-003",
       "COMMON_GROUP",
       {"/usr/bin/getent", "group", "cpu-prefetch-q15"},
       {0, 2}},
      {"P4R-004",
       "OPERATOR_PRINCIPAL",
       {"/usr/bin/getent", "passwd", "cpu-prefetch-q15-operator"},
       {0, 2}},
      {"P4R-005",
       "CONTROLLER_PRINCIPAL",
       {"/usr/bin/getent", "passwd", "cpu-prefetch-q15-controller"},
       {0, 2}},
      {"P4R-006",
       "CUSTODIAN_PRINCIPAL",
       {"/usr/bin/getent", "passwd", "cpu-prefetch-q15-custodian"},
       {0, 2}},
      {"P4R-007",
       "AUDITOR_PRINCIPAL",
       {"/usr/bin/getent", "passwd", "cpu-prefetch-q15-auditor"},
       {0, 2}},
      {"P4R-008",
       "SETUP_EXECUTABLE_METADATA",
       {"/usr/bin/stat", "--format=%n|%F|%a|%u|%g|%s|%d|%i", "--", "/usr/bin/getent",
        "/usr/sbin/groupadd", "/usr/sbin/useradd", "/usr/sbin/usermod",
        "/usr/bin/install", "/usr/sbin/runuser", "/usr/bin/test", "/usr/bin/chmod",
        "/usr/sbin/nologin", "/usr/bin/ssh-keygen"},
       {0, 1}},
      {"P4R-009",
       "SETUP_EXECUTABLE_SHA256",
       {"/usr/bin/sha256sum", "--", "/usr/bin/getent", "/usr/sbin/groupadd",
        "/usr/sbin/useradd", "/usr/sbin/usermod", "/usr/bin/install",
        "/usr/sbin/runuser", "/usr/bin/test", "/usr/bin/chmod", "/usr/sbin/nologin",
        "/usr/bin/ssh-keygen"},
       {0, 1}},
      stat("P4R-010", "PRIMARY_DEVICE_METADATA", "/dev/md3"),
      stat("P4R-011", "PRIMARY_PARENT_METADATA", "/var/lib/cpu-prefetch"),
      stat("P4R-012", "PRIMARY_ROOT_METADATA", "/var/lib/cpu-prefetch/q15-r"),
      stat("P4R-013", "CONTROLLER_STAGING_METADATA",
           "/var/lib/cpu-prefetch/q15-r/controller-staging"),
      stat("P4R-014", "SEALED_METADATA", "/var/lib/cpu-prefetch/q15-r/sealed"),
      stat("P4R-015", "RECEIPTS_METADATA", "/var/lib/cpu-prefetch/q15-r/receipts"),
      stat("P4R-016", "AUDIT_METADATA", "/var/lib/cpu-prefetch/q15-r/audit"),
      stat("P4R-017", "TRUST_PARENT_METADATA", "/etc/cpu-prefetch"),
      stat("P4R-018", "TRUST_ROOT_METADATA", "/etc/cpu-prefetch/q15"),
      stat("P4R-019", "ALLOWED_SIGNERS_DESTINATION_METADATA",
           "/etc/cpu-prefetch/q15/allowed_signers"),
      {"P4R-020",
       "ROOT_MOUNT",
       {"/usr/bin/findmnt", "--json", "--target", "/", "--output",
        "TARGET,SOURCE,FSTYPE,OPTIONS,PROPAGATION"},
       {0, 1}},
      {"P4R-021",
       "VAR_LIB_MOUNT",
       {"/usr/bin/findmnt", "--json", "--target", "/var/lib", "--output",
        "TARGET,SOURCE,FSTYPE,OPTIONS,PROPAGATION"},
       {0, 1}},
      {"P4R-022",
       "ETC_MOUNT",
       {"/usr/bin/findmnt", "--json", "--target", "/etc", "--output",
        "TARGET,SOURCE,FSTYPE,OPTIONS,PROPAGATION"},
       {0, 1}},
      {"P4R-023",
       "MOUNT_TABLE",
       {"/usr/bin/findmnt", "--json", "--output",
        "TARGET,SOURCE,FSTYPE,OPTIONS,PROPAGATION"},
       {0, 1}},
      {"P4R-024",
       "FILESYSTEM_SPACE",
       {"/usr/bin/df", "--block-size=1",
        "--output=source,fstype,size,used,avail,target", "--", "/", "/var/lib", "/etc"},
       {0, 1}},
      {"P4R-025",
       "COLLECTOR_TOOL_METADATA",
       {"/usr/bin/stat", "--format=%n|%F|%a|%u|%g|%s|%d|%i", "--", "/usr/bin/uname",
        "/usr/bin/hostname", "/usr/bin/stat", "/usr/bin/findmnt", "/usr/bin/df",
        "/usr/bin/sha256sum"},
       {0, 1}},
  };
  return result;
}

} // namespace

auto q15_stand_prestate_command_contract() -> std::span<const Q15StandPrestateCommand> {
  static const auto value = commands();
  return value;
}

auto to_string(Q15StandPrestateCompletion completion) noexcept -> std::string_view {
  switch (completion) {
  case Q15StandPrestateCompletion::complete:
    return "COMPLETE";
  case Q15StandPrestateCompletion::partial_failed:
    return "PARTIAL_FAILED";
  }
  return "UNKNOWN";
}

auto SystemQ15StandPrestateClock::now_utc() -> std::string {
  timespec timestamp{};
  if (::clock_gettime(CLOCK_REALTIME, &timestamp) != 0) {
    throw std::system_error(errno, std::generic_category(), "clock_gettime failed");
  }
  std::tm utc{};
  if (::gmtime_r(&timestamp.tv_sec, &utc) == nullptr) {
    throw std::system_error(errno, std::generic_category(), "gmtime_r failed");
  }
  std::array<char, 32U> output{};
  const auto count = std::snprintf(
      output.data(), output.size(), "%04d-%02d-%02dT%02d:%02d:%02d.%09ldZ",
      utc.tm_year + 1900, utc.tm_mon + 1, utc.tm_mday, utc.tm_hour, utc.tm_min,
      utc.tm_sec, timestamp.tv_nsec);
  if (count != 30) {
    throw std::runtime_error("RFC3339 UTC formatting failed");
  }
  return std::string(output.data(), static_cast<std::size_t>(count));
}

auto SystemQ15StandPrestateExecutor::execute(const Q15StandPrestateCommand& command,
                                             const Q15StandPrestateLimits& limits)
    -> Q15StandPrestateExecution {
  Q15StandPrestateExecution result{};
  if (command.argv.empty() || command.argv.front().empty() ||
      command.argv.front().front() != '/') {
    result.spawn_error = EINVAL;
    return result;
  }

  std::array<int, 2U> stdout_pipe{-1, -1};
  std::array<int, 2U> stderr_pipe{-1, -1};
  if (::pipe2(stdout_pipe.data(), O_CLOEXEC) != 0 ||
      ::pipe2(stderr_pipe.data(), O_CLOEXEC) != 0) {
    result.spawn_error = errno;
    close_descriptor(stdout_pipe[0]);
    close_descriptor(stdout_pipe[1]);
    close_descriptor(stderr_pipe[0]);
    close_descriptor(stderr_pipe[1]);
    return result;
  }

  posix_spawn_file_actions_t actions{};
  auto action_error = ::posix_spawn_file_actions_init(&actions);
  const bool actions_initialized = action_error == 0;
  if (action_error == 0) {
    action_error =
        ::posix_spawn_file_actions_adddup2(&actions, stdout_pipe[1], STDOUT_FILENO);
  }
  if (action_error == 0) {
    action_error =
        ::posix_spawn_file_actions_adddup2(&actions, stderr_pipe[1], STDERR_FILENO);
  }
  for (const auto descriptor :
       {stdout_pipe[0], stdout_pipe[1], stderr_pipe[0], stderr_pipe[1]}) {
    if (action_error == 0) {
      action_error = ::posix_spawn_file_actions_addclose(&actions, descriptor);
    }
  }
  if (action_error != 0) {
    result.spawn_error = action_error;
    if (actions_initialized) {
      static_cast<void>(::posix_spawn_file_actions_destroy(&actions));
    }
    for (auto& descriptor : stdout_pipe) {
      close_descriptor(descriptor);
    }
    for (auto& descriptor : stderr_pipe) {
      close_descriptor(descriptor);
    }
    return result;
  }

  std::vector<char*> argv;
  argv.reserve(command.argv.size() + 1U);
  for (const auto& argument : command.argv) {
    argv.push_back(const_cast<char*>(argument.c_str()));
  }
  argv.push_back(nullptr);
  std::array<char, 7U> lang{"LANG=C"};
  std::array<char, 9U> lc_all{"LC_ALL=C"};
  std::array<char, 8U> timezone{"TZ=UTC0"};
  std::array<char*, 4U> environment{lang.data(), lc_all.data(), timezone.data(),
                                    nullptr};
  pid_t child = -1;
  const auto spawn_error = ::posix_spawn(&child, command.argv.front().c_str(), &actions,
                                         nullptr, argv.data(), environment.data());
  static_cast<void>(::posix_spawn_file_actions_destroy(&actions));
  close_descriptor(stdout_pipe[1]);
  close_descriptor(stderr_pipe[1]);
  if (spawn_error != 0) {
    result.spawn_error = spawn_error;
    close_descriptor(stdout_pipe[0]);
    close_descriptor(stderr_pipe[0]);
    return result;
  }
  result.launched = true;

  for (const auto descriptor : {stdout_pipe[0], stderr_pipe[0]}) {
    const auto flags = ::fcntl(descriptor, F_GETFL, 0);
    if (flags < 0 || ::fcntl(descriptor, F_SETFL, flags | O_NONBLOCK) != 0) {
      result.spawn_error = errno;
    }
  }
  const auto deadline = std::chrono::steady_clock::now() + limits.per_command_timeout;
  int status = 0;
  bool child_exited = false;
  while ((!child_exited || stdout_pipe[0] >= 0 || stderr_pipe[0] >= 0) &&
         !result.timed_out && !result.output_limit_exceeded &&
         result.spawn_error == 0) {
    drain_descriptor(stdout_pipe[0], result.stdout_bytes,
                     limits.maximum_stdout_bytes_per_command, result);
    drain_descriptor(stderr_pipe[0], result.stderr_bytes,
                     limits.maximum_stderr_bytes_per_command, result);
    if (!child_exited) {
      const auto waited = ::waitpid(child, &status, WNOHANG);
      if (waited == child) {
        child_exited = true;
      } else if (waited < 0 && errno != EINTR) {
        result.spawn_error = errno;
      }
    }
    if (child_exited && stdout_pipe[0] < 0 && stderr_pipe[0] < 0) {
      break;
    }
    if (std::chrono::steady_clock::now() >= deadline) {
      result.timed_out = true;
      break;
    }
    std::array<pollfd, 2U> poll_descriptors{{
        {stdout_pipe[0], POLLIN | POLLHUP, 0},
        {stderr_pipe[0], POLLIN | POLLHUP, 0},
    }};
    const auto poll_result =
        ::poll(poll_descriptors.data(), poll_descriptors.size(), 50);
    if (poll_result < 0 && errno != EINTR) {
      result.spawn_error = errno;
    }
  }

  if (!child_exited) {
    static_cast<void>(::kill(child, SIGKILL));
    while (::waitpid(child, &status, 0) < 0 && errno == EINTR) {
    }
    child_exited = true;
  }
  drain_descriptor(stdout_pipe[0], result.stdout_bytes,
                   limits.maximum_stdout_bytes_per_command, result);
  drain_descriptor(stderr_pipe[0], result.stderr_bytes,
                   limits.maximum_stderr_bytes_per_command, result);
  close_descriptor(stdout_pipe[0]);
  close_descriptor(stderr_pipe[0]);
  if (child_exited) {
    if (WIFEXITED(status)) {
      result.exit_code = WEXITSTATUS(status);
    } else if (WIFSIGNALED(status)) {
      result.terminating_signal = WTERMSIG(status);
    }
  }
  return result;
}

auto validate_q15_stand_prestate_artifact(const Q15StandPrestateArtifact& artifact)
    -> std::vector<ValidationError> {
  auto errors = validate_context(artifact.context);

  const auto contract = q15_stand_prestate_command_contract();
  if (artifact.observations.empty() || artifact.observations.size() > contract.size()) {
    errors.push_back(error(ErrorCategory::out_of_range, "$/observations", "P4R-COUNT",
                           "observation prefix length is invalid"));
  }
  std::size_t total_captured = 0U;
  std::optional<std::string> expected_failure_category;
  for (std::size_t index = 0U;
       index < artifact.observations.size() && index < contract.size(); ++index) {
    const auto& observation = artifact.observations[index];
    const auto& command = contract[index];
    if (observation.command_id != command.id ||
        observation.observation_kind != command.observation_kind ||
        observation.argv != command.argv) {
      errors.push_back(error(ErrorCategory::reference_mismatch,
                             "$/observations/" + std::to_string(index),
                             "P4R-COMMAND-BINDING",
                             "observation differs from the fixed command contract"));
    }
    if (!valid_rfc3339_nanoseconds(observation.started_at_utc) ||
        !valid_rfc3339_nanoseconds(observation.ended_at_utc) ||
        observation.ended_at_utc < observation.started_at_utc) {
      errors.push_back(error(ErrorCategory::cross_field,
                             "$/observations/" + std::to_string(index), "P4R-TIMESTAMP",
                             "UTC boundaries must be ordered RFC3339 nanoseconds"));
    }
    if (!valid_lower_hex(observation.stdout_hex) ||
        !valid_lower_hex(observation.stderr_hex)) {
      errors.push_back(error(ErrorCategory::cross_field,
                             "$/observations/" + std::to_string(index), "P4R-HEX",
                             "captured output must be lowercase whole-byte hex"));
    }
    const auto stdout_size = observation.stdout_hex.size() / 2U;
    const auto stderr_size = observation.stderr_hex.size() / 2U;
    const bool per_command_size_exceeded =
        stdout_size > kQ15StandPrestateLimits.maximum_stdout_bytes_per_command ||
        stderr_size > kQ15StandPrestateLimits.maximum_stderr_bytes_per_command;
    const auto addition = stdout_size + stderr_size;
    const bool total_limit_exceeded =
        addition > kQ15StandPrestateLimits.maximum_total_captured_bytes -
                       std::min(kQ15StandPrestateLimits.maximum_total_captured_bytes,
                                total_captured);
    if (!total_limit_exceeded) {
      total_captured += addition;
    }
    if (per_command_size_exceeded && !observation.output_limit_exceeded) {
      errors.push_back(error(
          ErrorCategory::out_of_range, "$/observations/" + std::to_string(index),
          "P4R-OUTPUT-SIZE", "oversized output must be marked as a bounded failure"));
    }
    if (observation.spawn_error < 0 ||
        (observation.exit_code.has_value() &&
         (*observation.exit_code < 0 || *observation.exit_code > 255)) ||
        (observation.terminating_signal.has_value() &&
         *observation.terminating_signal <= 0)) {
      errors.push_back(error(
          ErrorCategory::out_of_range, "$/observations/" + std::to_string(index),
          "P4R-EXECUTION-STATE", "captured process status is outside its domain"));
    }
    const Q15StandPrestateExecution execution{
        observation.launched,
        observation.timed_out,
        observation.output_limit_exceeded,
        observation.exit_code,
        observation.terminating_signal,
        observation.spawn_error,
        {},
        {},
    };
    const bool expected_accepted =
        accepted_exit(command, execution) && !total_limit_exceeded;
    if (observation.accepted != expected_accepted) {
      errors.push_back(error(
          ErrorCategory::cross_field, "$/observations/" + std::to_string(index),
          "P4R-ACCEPTANCE", "accepted flag disagrees with the fixed process contract"));
    }
    if (!expected_accepted && index + 1U == artifact.observations.size()) {
      expected_failure_category =
          failure_category(command, execution, total_limit_exceeded);
    }
    if (index + 1U < artifact.observations.size() && !observation.accepted) {
      errors.push_back(
          error(ErrorCategory::cross_field, "$/observations/" + std::to_string(index),
                "P4R-STOP-FIRST", "no observation may follow a failed command"));
    }
  }
  if (artifact.completion == Q15StandPrestateCompletion::complete) {
    if (artifact.observations.size() != contract.size() ||
        std::ranges::any_of(artifact.observations,
                            [](const auto& value) { return !value.accepted; }) ||
        artifact.failed_command_id.has_value() ||
        artifact.failure_category.has_value()) {
      errors.push_back(error(ErrorCategory::cross_field, "$/completion_state",
                             "P4R-COMPLETE",
                             "complete artifact requires every accepted command"));
    }
  } else if (artifact.observations.empty() || artifact.observations.back().accepted ||
             !artifact.failed_command_id.has_value() ||
             artifact.failed_command_id != artifact.observations.back().command_id ||
             !artifact.failure_category.has_value()) {
    errors.push_back(error(ErrorCategory::cross_field, "$/completion_state",
                           "P4R-PARTIAL",
                           "partial artifact must identify its final failed command"));
  }
  if (artifact.completion == Q15StandPrestateCompletion::partial_failed &&
      artifact.failure_category != expected_failure_category) {
    errors.push_back(error(ErrorCategory::cross_field, "$/failure_category",
                           "P4R-FAILURE-CATEGORY",
                           "failure category disagrees with the final observation"));
  }

  auto regenerated = artifact;
  regenerated.artifact_sha256.clear();
  regenerated.canonical_json.clear();
  const auto canonical = canonical_and_hash(regenerated);
  if (!canonical || regenerated.artifact_sha256 != artifact.artifact_sha256 ||
      canonical.value() != artifact.canonical_json) {
    errors.push_back(error(ErrorCategory::invalid_hash, "$/artifact_sha256",
                           "P4R-ARTIFACT-HASH",
                           "canonical bytes or zero-self SHA-256 do not match"));
  }
  if (artifact.canonical_json.size() > kQ15StandPrestateLimits.maximum_artifact_bytes) {
    errors.push_back(error(ErrorCategory::out_of_range, "$/artifact",
                           "P4R-ARTIFACT-SIZE", "artifact exceeds the fixed bound"));
  }
  return errors;
}

auto collect_q15_stand_prestate(const Q15StandPrestateContext& context,
                                Q15StandPrestateExecutor& executor,
                                Q15StandPrestateClock& clock)
    -> protocol::Result<Q15StandPrestateArtifact> {
  Q15StandPrestateArtifact artifact{
      context, Q15StandPrestateCompletion::complete, {}, std::nullopt, std::nullopt, {},
      {}};
  // Validate all context bindings before executing the first command.
  auto context_errors = validate_context(context);
  if (!context_errors.empty()) {
    return protocol::Result<Q15StandPrestateArtifact>::failure(
        std::move(context_errors));
  }

  const auto contract = q15_stand_prestate_command_contract();
  artifact.observations.reserve(contract.size());
  std::size_t total_captured = 0U;
  for (const auto& command : contract) {
    const auto started = clock.now_utc();
    auto execution = executor.execute(command, kQ15StandPrestateLimits);
    if (execution.stdout_bytes.size() >
            kQ15StandPrestateLimits.maximum_stdout_bytes_per_command ||
        execution.stderr_bytes.size() >
            kQ15StandPrestateLimits.maximum_stderr_bytes_per_command) {
      execution.output_limit_exceeded = true;
    }
    const auto ended = clock.now_utc();
    const auto addition = execution.stdout_bytes.size() + execution.stderr_bytes.size();
    const bool total_limit_exceeded =
        addition > kQ15StandPrestateLimits.maximum_total_captured_bytes -
                       std::min(kQ15StandPrestateLimits.maximum_total_captured_bytes,
                                total_captured);
    if (!total_limit_exceeded) {
      total_captured += addition;
    }
    const bool accepted = accepted_exit(command, execution) && !total_limit_exceeded;
    artifact.observations.push_back(
        {command.id, command.observation_kind, command.argv, started, ended,
         execution.launched, execution.timed_out, execution.output_limit_exceeded,
         execution.exit_code, execution.terminating_signal, execution.spawn_error,
         hex_bytes(execution.stdout_bytes), hex_bytes(execution.stderr_bytes),
         accepted});
    if (!accepted) {
      artifact.completion = Q15StandPrestateCompletion::partial_failed;
      artifact.failed_command_id = command.id;
      artifact.failure_category =
          failure_category(command, execution, total_limit_exceeded);
      break;
    }
  }
  auto canonical = canonical_and_hash(artifact);
  if (!canonical) {
    return protocol::Result<Q15StandPrestateArtifact>::failure(canonical.errors());
  }
  artifact.canonical_json = std::move(canonical).value();
  const auto errors = validate_q15_stand_prestate_artifact(artifact);
  if (!errors.empty()) {
    return protocol::Result<Q15StandPrestateArtifact>::failure(errors);
  }
  return protocol::Result<Q15StandPrestateArtifact>::success(artifact);
}

} // namespace cpu_prefetch::qualification
