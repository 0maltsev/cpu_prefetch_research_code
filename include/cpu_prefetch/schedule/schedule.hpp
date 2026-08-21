#ifndef CPU_PREFETCH_SCHEDULE_SCHEDULE_HPP
#define CPU_PREFETCH_SCHEDULE_SCHEDULE_HPP

#include <cstddef>
#include <cstdint>
#include <span>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

#include "cpu_prefetch/protocol/model.hpp"
#include "cpu_prefetch/protocol/validation.hpp"

namespace cpu_prefetch::schedule {

inline constexpr std::string_view kScheduleAlgorithm =
    "POISSON-EXPONENTIAL-PHILOX-DECIMAL80-FLOOR-ABS-PS";
inline constexpr std::string_view kScheduleVersion = "1";
inline constexpr std::string_view kScheduleSuite =
    "POISSON-EXPONENTIAL-PHILOX-DECIMAL80-FLOOR-ABS-PS-v1";
inline constexpr std::string_view kScheduleTimeUnit = "ps";
inline constexpr std::string_view kScheduleArtifactFormat = "SCHEDULE-ABS-U64BE-v1";
inline constexpr std::string_view kScheduleOverflowRule =
    "SCHEDULE-U64-ABS-FAIL-CLOSED-v1";
inline constexpr std::string_view kDecodedHashAlgorithm =
    "DECODED-DEADLINES-U64BE-SHA256-v1";
inline constexpr std::string_view kEnvelopeHashProfile =
    "SCHEDULE-JCS-I64-ZEROSELF-SHA256-v1";
inline constexpr std::string_view kDerivationSchema =
    "cpu-prefetch-schedule-derivation-v1";
inline constexpr std::string_view kDerivationHashProfile =
    "SCHEDULE-DERIVATION-JCS-I64-ZEROSELF-SHA256-v1";
// ADR-0029 froze this label into key and decoded-deadline hash preimages.
// Protocol document upgrades do not rewrite those deterministic bytes.
inline constexpr std::string_view kDerivationDomainProtocolVersion = "2.0.0-pre.1";

class PreparedSchedule final {
public:
  [[nodiscard]] auto deadlines() const noexcept -> std::span<const std::uint64_t> {
    return deadlines_;
  }
  [[nodiscard]] auto artifact_sha256() const noexcept -> std::string_view {
    return artifact_sha256_;
  }
  [[nodiscard]] auto decoded_deadlines_sha256() const noexcept -> std::string_view {
    return decoded_deadlines_sha256_;
  }
  [[nodiscard]] auto schedule_sha256() const noexcept -> std::string_view {
    return schedule_sha256_;
  }

private:
  friend auto decode_and_validate(const protocol::ScheduleRecord&,
                                  std::span<const std::byte>, std::string_view)
      -> protocol::Result<PreparedSchedule>;

  PreparedSchedule(std::vector<std::uint64_t> deadlines, std::string artifact_sha256,
                   std::string decoded_deadlines_sha256, std::string schedule_sha256)
      : deadlines_(std::move(deadlines)), artifact_sha256_(std::move(artifact_sha256)),
        decoded_deadlines_sha256_(std::move(decoded_deadlines_sha256)),
        schedule_sha256_(std::move(schedule_sha256)) {}

  std::vector<std::uint64_t> deadlines_;
  std::string artifact_sha256_;
  std::string decoded_deadlines_sha256_;
  std::string schedule_sha256_;
};

[[nodiscard]] auto decode_and_validate(const protocol::ScheduleRecord& record,
                                       std::span<const std::byte> artifact_bytes,
                                       std::string_view derivation_record_json)
    -> protocol::Result<PreparedSchedule>;

[[nodiscard]] auto validate_derivation_record(const protocol::ScheduleRecord& schedule,
                                              std::string_view derivation_record_json)
    -> std::vector<protocol::ValidationError>;

enum class NamespaceRole : std::uint8_t {
  warmup,
  calibration,
  pilot,
  h3_train,
  h3_validation,
  h1h2_supplemental,
  diagnostic,
};

struct ScheduleUse final {
  const protocol::ScheduleRecord* schedule;
  NamespaceRole namespace_role;
  std::string treatment_id;
  std::string common_schedule_family_id;
};

// Roles and matched-family membership are explicit planning metadata. This
// validator never derives either identity from a namespace or filesystem path.
[[nodiscard]] auto validate_schedule_uses(std::span<const ScheduleUse> uses)
    -> std::vector<protocol::ValidationError>;

} // namespace cpu_prefetch::schedule

#endif // CPU_PREFETCH_SCHEDULE_SCHEDULE_HPP
