#ifndef CPU_PREFETCH_RUNNER_STAGE17_FIXED_ACTION_HPP
#define CPU_PREFETCH_RUNNER_STAGE17_FIXED_ACTION_HPP

#include "cpu_prefetch/protocol/json.hpp"
#include "cpu_prefetch/protocol/validation.hpp"

#include <cstdint>
#include <span>
#include <string>
#include <string_view>
#include <vector>

namespace cpu_prefetch::runner::stage17 {

inline constexpr std::string_view kFixedActionWorkerRole =
    "STAGE17_FIXED_ACTION_WORKER";
inline constexpr std::string_view kFixedActionRuntimeProfile =
    "STAGE17-FIXED-ACTION-WORKER-v4";
inline constexpr std::string_view kFixedActionRequestSchema =
    "cpu-prefetch-stage17-fixed-action-request/4";
inline constexpr std::string_view kFixedActionResultSchema =
    "cpu-prefetch-stage17-phase-action-result/4";
inline constexpr std::string_view kFixedActionContextSchema =
    "cpu-prefetch-stage17-fixed-action-context/4";

enum class FixedAction : std::uint8_t {
  q15_r,
  q15_w,
  q16a,
  q16b,
  q16c,
  blinded_pilot,
};

[[nodiscard]] auto to_string(FixedAction action) noexcept -> std::string_view;
[[nodiscard]] auto parse_fixed_action(std::string_view value)
    -> protocol::Result<FixedAction>;
[[nodiscard]] auto self_executable_sha256() -> protocol::Result<std::string>;

struct ArtifactPayload final {
  std::string role;
  std::string schema_identity;
  std::string media_type{"application/json"};
  std::string file_name;
  std::vector<std::byte> bytes;
};

struct ArtifactBinding final {
  std::string role;
  std::string schema_identity;
  std::string media_type;
  std::string file_name;
  std::uint64_t size_bytes;
  std::string sha256;
};

class ArtifactSink {
public:
  virtual ~ArtifactSink() = default;
  [[nodiscard]] virtual auto publish(ArtifactPayload artifact)
      -> protocol::Result<ArtifactBinding> = 0;
};

struct ActionOutcome final {
  std::vector<ArtifactBinding> artifacts;
  bool restoration_verified;
  bool quarantined;
  std::string terminal_state;
};

struct PilotSessionAuthority final {
  std::string session_id;
  std::string authorization_id;
  std::string authorization_sha256;
  std::string request_sha256;
  std::string stand_id;
  std::uint64_t issued_at_epoch_seconds;
  std::uint64_t expires_at_epoch_seconds;
  std::uint64_t per_run_deadline_seconds;
  bool synthetic_test_only;
};

// The production and test-linked workers share parsing, exact dispatcher,
// create-exclusive output, and typed result construction.  Only the concrete
// operations implementation differs at link/entry-point construction time;
// the production executable has no flag or dependency that can select the
// test implementation.
class FixedActionOperations {
public:
  virtual ~FixedActionOperations() = default;
  [[nodiscard]] virtual auto execute(FixedAction action,
                                     const protocol::json::Value::Object& action_inputs,
                                     ArtifactSink& sink)
      -> protocol::Result<ActionOutcome> = 0;
  [[nodiscard]] virtual auto
  execute_pilot_session(const protocol::json::Value::Object& action_inputs,
                        ArtifactSink& sink, const PilotSessionAuthority& authority)
      -> protocol::Result<ActionOutcome>;
  [[nodiscard]] virtual auto synthetic_test_only() const noexcept -> bool = 0;
};

class LinuxFixedActionOperations final : public FixedActionOperations {
public:
  [[nodiscard]] auto execute(FixedAction action,
                             const protocol::json::Value::Object& action_inputs,
                             ArtifactSink& sink)
      -> protocol::Result<ActionOutcome> override;
  [[nodiscard]] auto
  execute_pilot_session(const protocol::json::Value::Object& action_inputs,
                        ArtifactSink& sink, const PilotSessionAuthority& authority)
      -> protocol::Result<ActionOutcome> override;
  [[nodiscard]] auto synthetic_test_only() const noexcept -> bool override {
    return false;
  }
};

// Internal fd-only worker boundary. Accepted argv is exactly:
//   --execute-fixed-stage17-action-v4 ACTION --request-fd N --context-fd N
//   --output-dir-fd N --fixed-dispatch-end
// The caller cannot provide a command, plugin, stdin, output name, backend, or
// experiment-definition path.  Returns 0 only after a typed result and every
// declared artifact have been durably written create-exclusively.
[[nodiscard]] auto run_fixed_action_worker(int argc, char** argv,
                                           FixedActionOperations& operations) -> int;

// Q15-R and Q15-W share one long-lived Linux process and one private anonymous
// mapping. The q15-w control fd carries exactly two bounded SOCK_SEQPACKET
// messages (request then authority context) after the separately admitted
// Q15-W authorization exists. The ordinary one-shot dispatcher rejects both
// Q15 actions.
[[nodiscard]] auto run_q15_phase_session_worker(int argc, char** argv) -> int;
[[nodiscard]] auto run_test_q15_phase_session_worker(int argc, char** argv,
                                                     FixedActionOperations& operations)
    -> int;

// The pilot is a durable session, not one 180-second action.  One compiled
// process retains mappings across the frozen run order; each run receives its
// own durable marker, actual-UTC guard, and 180-second fail-stop watchdog.
[[nodiscard]] auto run_pilot_session_worker(int argc, char** argv,
                                            FixedActionOperations& operations) -> int;

} // namespace cpu_prefetch::runner::stage17

#endif // CPU_PREFETCH_RUNNER_STAGE17_FIXED_ACTION_HPP
