#ifndef CPU_PREFETCH_RUNNER_STAGE17_S180_SESSION_HPP
#define CPU_PREFETCH_RUNNER_STAGE17_S180_SESSION_HPP
#include "cpu_prefetch/runner/stage17_s180_publication.hpp"
#include "cpu_prefetch/runner/stage17_s180_sources.hpp"
namespace cpu_prefetch::runner::stage17 {
inline constexpr std::string_view kS180BlueprintSha256 =
    "e95183365023a06b9da0d6cdff042bce556b9eb60c701dfb0f9e6df6ca22685c";
inline constexpr std::uint64_t kS180OperationalCapNs = 86'400'000'000'000U;
struct S180CaptureInput final {
  calibration::NativePilotCapturePlan native;
  calibration::NativePilotCaptureLayout expected_layout;
  std::uint64_t watchdog_ns;
  std::uint64_t archive_ns;
  std::uint64_t max_output_bytes;
  std::uint64_t metadata_bytes;
};
struct S180SessionInput final {
  protocol::json::Value::Object blueprint;
  std::string source_revision;
  std::vector<calibration::MappedPilotDataPlan> contexts;
  std::array<std::array<S180SourceArtifact, 2U>, 18U> source_artifacts;
  std::vector<S180CaptureInput> captures; // Exact frozen execution order.
  FormalScheduleSourceContext sources;
  std::span<const int> reserved_descriptors;
  std::uint64_t setup_ns;
  std::uint64_t whole_plot_transition_ns;
  std::uint64_t whole_plot_recovery_ns;
  std::uint64_t finalization_ns;
  std::uint64_t final_metadata_bytes;
  std::uint64_t memory_bytes;
  std::uint64_t max_output_bytes;
};
struct S180SessionShape final {
  std::array<std::size_t, 180U> cells;
  std::array<std::size_t, 180U> contexts;
  std::array<std::size_t, 180U> source_groups;
  std::uint64_t watchdog_ns;
  std::uint64_t shared_mapping_bytes;
  std::uint64_t retained_vector_bytes;
};
// Pure cold validation of exact frozen scientific identity and finite bounds.
// It does not authenticate an input or qualify any requested platform value.
[[nodiscard]] auto validate_s180_session(const S180SessionInput&)
    -> protocol::Result<S180SessionShape>;
// The same declaration/budget checks without a physical source context. Used
// only for prospective sizing; no source bytes, descriptors or authority checked.
[[nodiscard]] auto validate_s180_prospective_declaration(const S180SessionInput&)
    -> protocol::Result<S180SessionShape>;
struct S180SessionAuthority final {
  std::string session_id;
  std::string plan_sha256;
  std::string program_scope_sha256;
  std::uint64_t window_start_monotonic_ns;
  std::uint64_t window_end_monotonic_ns;
};
enum class S180SessionStop : std::uint8_t {
  not_started,
  complete,
  authority_failed,
  preparation_failed,
  marker_failed,
  hardware_failed,
  capture_failed,
  archive_failed,
  recovery_failed,
  restoration_failed,
  cleanup_failed,
  final_publication_failed,
  exception
};
struct S180SessionResult final {
  S180SessionStop stop{S180SessionStop::not_started};
  std::size_t attempted{0U}, completed{0U};
  bool restoration_attempted{false}, restoration_verified{false};
  bool cleanup_attempted{false}, cleanup_verified{false};
  bool final_publication_succeeded{false};
};
// Cold controller interface. Production and separately linked software tests
// share the same fixed S180 state machine. No runtime backend/plugin selector.
class S180SessionOperations {
public:
  virtual ~S180SessionOperations() = default;
  virtual auto now_monotonic_ns() const noexcept -> std::optional<std::uint64_t> = 0;
  virtual auto prepare(const S180SessionShape&) -> bool = 0;
  virtual auto mark_attempt(std::size_t) -> bool = 0;
  virtual auto enter(protocol::RequestedHardwareState) -> bool = 0;
  virtual auto capture(std::size_t) -> bool = 0;
  // Called once even after failed capture, to retain its original evidence.
  virtual auto archive(std::size_t, bool native_complete) -> bool = 0;
  virtual auto restore() noexcept -> bool = 0;
  virtual auto recover(std::uint64_t duration_ns) -> bool = 0;
  virtual auto release_contexts() noexcept -> bool = 0;
  virtual auto finish(const S180SessionResult&) -> bool = 0;
};
[[nodiscard]] auto run_s180_session(const S180SessionInput&,
                                    const S180SessionAuthority&, S180SessionOperations&)
    -> protocol::Result<S180SessionResult>;
// This distinct sink requires the qualified parent S180 broker. Historical
// generic archive sinks cannot be passed accidentally. It still supplies no
// admission or scientific validity; the authenticated worker route owns those.
class S180ArchiveSink : public ArtifactSink {
public:
  virtual auto s180_program_scope_sha256() const noexcept -> std::string_view = 0;
};
[[nodiscard]] auto run_native_s180_session(const S180SessionInput&,
                                           const S180SessionAuthority&,
                                           S180ArchiveSink&)
    -> protocol::Result<ActionOutcome>;
} // namespace cpu_prefetch::runner::stage17
#endif
