#ifndef CPU_PREFETCH_QUALIFICATION_Q15_PRESTATE_HPP
#define CPU_PREFETCH_QUALIFICATION_Q15_PRESTATE_HPP

#include "cpu_prefetch/protocol/model.hpp"

#include <chrono>
#include <cstddef>
#include <cstdint>
#include <optional>
#include <span>
#include <string>
#include <string_view>
#include <vector>

namespace cpu_prefetch::qualification {

inline constexpr std::string_view kQ15StandPrestateCollectorContractId =
    "Q15-R-STAND-PRESTATE-COLLECTOR-CONTRACT-v1";
inline constexpr std::string_view kQ15StandPrestateArtifactSchemaVersion =
    "cpu-prefetch-q15-r-stand-prestate/1";
inline constexpr std::string_view kQ15StandPrestateArtifactHashProfile =
    "Q15-R-PRESTATE-JCS-I64-ZEROSELF-SHA256-v1";
inline constexpr std::string_view kQ15StandPrestateCollectorContractSha256 =
    "4123735a940da144e00247957d0210216cde4bf19fbdbea0378b52dab2161b87";
inline constexpr std::string_view kQ15SelectedReleaseArchiveSha256 =
    "8e8ad6d781b2bffadcfc10cf3b12d5666c7a1d4c7d7e291d7318a19503e6ab01";

struct Q15StandPrestateLimits final {
  std::size_t maximum_command_count;
  std::size_t maximum_stdout_bytes_per_command;
  std::size_t maximum_stderr_bytes_per_command;
  std::size_t maximum_total_captured_bytes;
  std::size_t maximum_artifact_bytes;
  std::chrono::seconds per_command_timeout;
  std::chrono::seconds external_total_watchdog;

  auto operator==(const Q15StandPrestateLimits&) const -> bool = default;
};

inline constexpr Q15StandPrestateLimits kQ15StandPrestateLimits{
    25U,
    1'048'576U,
    1'048'576U,
    16'777'216U,
    67'108'864U,
    std::chrono::seconds(30),
    std::chrono::seconds(900)};

struct Q15StandPrestateCommand final {
  std::string id;
  std::string observation_kind;
  std::vector<std::string> argv;
  std::vector<int> accepted_exit_codes;

  auto operator==(const Q15StandPrestateCommand&) const -> bool = default;
};

[[nodiscard]] auto q15_stand_prestate_command_contract()
    -> std::span<const Q15StandPrestateCommand>;

struct Q15StandPrestateExecution final {
  bool launched{};
  bool timed_out{};
  bool output_limit_exceeded{};
  std::optional<int> exit_code;
  std::optional<int> terminating_signal;
  int spawn_error{};
  std::string stdout_bytes;
  std::string stderr_bytes;
};

class Q15StandPrestateExecutor {
public:
  virtual ~Q15StandPrestateExecutor() = default;
  [[nodiscard]] virtual auto execute(const Q15StandPrestateCommand& command,
                                     const Q15StandPrestateLimits& limits)
      -> Q15StandPrestateExecution = 0;
};

class Q15StandPrestateClock {
public:
  virtual ~Q15StandPrestateClock() = default;
  [[nodiscard]] virtual auto now_utc() -> std::string = 0;
};

class SystemQ15StandPrestateExecutor final : public Q15StandPrestateExecutor {
public:
  [[nodiscard]] auto execute(const Q15StandPrestateCommand& command,
                             const Q15StandPrestateLimits& limits)
      -> Q15StandPrestateExecution override;
};

class SystemQ15StandPrestateClock final : public Q15StandPrestateClock {
public:
  [[nodiscard]] auto now_utc() -> std::string override;
};

struct Q15StandPrestateContext final {
  std::string capture_id;
  std::string authorization_sha256;
  std::string collector_binary_sha256;
  std::string collector_contract_sha256;
  std::string source_revision;
  std::string selected_release_archive_sha256;
  std::string stand_id;
};

struct Q15StandPrestateObservation final {
  std::string command_id;
  std::string observation_kind;
  std::vector<std::string> argv;
  std::string started_at_utc;
  std::string ended_at_utc;
  bool launched{};
  bool timed_out{};
  bool output_limit_exceeded{};
  std::optional<int> exit_code;
  std::optional<int> terminating_signal;
  int spawn_error{};
  std::string stdout_hex;
  std::string stderr_hex;
  bool accepted{};
};

enum class Q15StandPrestateCompletion : std::uint8_t { complete, partial_failed };

[[nodiscard]] auto to_string(Q15StandPrestateCompletion completion) noexcept
    -> std::string_view;

struct Q15StandPrestateArtifact final {
  Q15StandPrestateContext context;
  Q15StandPrestateCompletion completion;
  std::vector<Q15StandPrestateObservation> observations;
  std::optional<std::string> failed_command_id;
  std::optional<std::string> failure_category;
  std::string artifact_sha256;
  std::string canonical_json;
};

[[nodiscard]] auto
validate_q15_stand_prestate_artifact(const Q15StandPrestateArtifact& artifact)
    -> std::vector<protocol::ValidationError>;

[[nodiscard]] auto collect_q15_stand_prestate(const Q15StandPrestateContext& context,
                                              Q15StandPrestateExecutor& executor,
                                              Q15StandPrestateClock& clock)
    -> protocol::Result<Q15StandPrestateArtifact>;

} // namespace cpu_prefetch::qualification

#endif // CPU_PREFETCH_QUALIFICATION_Q15_PRESTATE_HPP
