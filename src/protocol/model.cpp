#include "cpu_prefetch/protocol/model.hpp"

#include <array>
#include <cstddef>
#include <cstdint>
#include <string>
#include <string_view>
#include <utility>

namespace cpu_prefetch::protocol {
namespace {

using namespace std::string_view_literals;

template <typename Enum, std::size_t Size>
auto parse_enum_value(std::string_view text, std::string path, std::string rule_id,
                      const std::array<std::pair<std::string_view, Enum>, Size>& values)
    -> Result<Enum> {
  for (const auto& [name, value] : values) {
    if (name == text) {
      return Result<Enum>::success(value);
    }
  }
  return Result<Enum>::failure({ErrorCategory::unknown_enum, std::move(path),
                                std::move(rule_id),
                                "unknown enum value: " + std::string(text)});
}

constexpr auto hex_value(char character) -> int {
  if (character >= '0' && character <= '9') {
    return character - '0';
  }
  if (character >= 'a' && character <= 'f') {
    return 10 + character - 'a';
  }
  return -1;
}

} // namespace

auto Sha256::parse(std::string_view text, std::string path) -> Result<Sha256> {
  if (text.size() != 64) {
    return Result<Sha256>::failure({ErrorCategory::invalid_hash, std::move(path),
                                    "DAT-SHA256",
                                    "SHA-256 must contain 64 lowercase hex digits"});
  }
  std::array<std::byte, 32> bytes{};
  for (std::size_t index = 0; index < bytes.size(); ++index) {
    const int high = hex_value(text[index * 2]);
    const int low = hex_value(text[index * 2 + 1]);
    if (high < 0 || low < 0) {
      return Result<Sha256>::failure(
          {ErrorCategory::invalid_hash, std::move(path), "DAT-SHA256",
           "SHA-256 must contain only lowercase hexadecimal digits"});
    }
    bytes[index] = static_cast<std::byte>((high << 4) | low);
  }
  return Result<Sha256>::success(Sha256(bytes));
}

auto Sha256::hex() const -> std::string {
  constexpr std::array<char, 16> digits = {'0', '1', '2', '3', '4', '5', '6', '7',
                                           '8', '9', 'a', 'b', 'c', 'd', 'e', 'f'};
  std::string output;
  output.reserve(64);
  for (std::byte byte : bytes_) {
    const auto value = std::to_integer<unsigned int>(byte);
    output.push_back(digits[(value >> 4U) & 0x0fU]);
    output.push_back(digits[value & 0x0fU]);
  }
  return output;
}

auto parse_protocol_version(std::string_view text, std::string path)
    -> Result<ProtocolVersion> {
  if (text == kOldestReadableProtocolVersion) {
    return Result<ProtocolVersion>::success(ProtocolVersion::v2_0_0_pre_1);
  }
  if (text == kPreviousProtocolVersion) {
    return Result<ProtocolVersion>::success(ProtocolVersion::v2_0_0_pre_2);
  }
  if (text == kProtocolVersion) {
    return Result<ProtocolVersion>::success(ProtocolVersion::v2_0_0_pre_3);
  }
  return Result<ProtocolVersion>::failure(
      {ErrorCategory::unsupported_version, std::move(path), "GOV-004",
       "only protocol/schema versions 2.0.0-pre.1, 2.0.0-pre.2, and "
       "2.0.0-pre.3 are readable; "
       "no implicit migration exists"});
}

#define CPU_PREFETCH_DEFINE_ENUM_PARSER(function_name, type_name, rule, ...)           \
  auto parse_##function_name(std::string_view text, std::string path)                  \
      -> Result<type_name> {                                                           \
    const std::array values{__VA_ARGS__};                                              \
    return parse_enum_value(text, std::move(path), rule, values);                      \
  }

CPU_PREFETCH_DEFINE_ENUM_PARSER(stage, Stage, "DAT-STAGE",
                                std::pair{"CALIBRATION"sv, Stage::calibration},
                                std::pair{"PILOT"sv, Stage::pilot},
                                std::pair{"STAGE_A"sv, Stage::stage_a},
                                std::pair{"STAGE_B"sv, Stage::stage_b},
                                std::pair{"STAGE_C"sv, Stage::stage_c},
                                std::pair{"DIAGNOSTIC"sv, Stage::diagnostic});
CPU_PREFETCH_DEFINE_ENUM_PARSER(
    run_mode, RunMode, "DAT-RUN-MODE", std::pair{"LATENCY"sv, RunMode::latency},
    std::pair{"SERVICE_RATE_CALIBRATION"sv, RunMode::service_rate_calibration},
    std::pair{"D2_CALIBRATION"sv, RunMode::d2_calibration},
    std::pair{"COUNTER_DIAGNOSTIC"sv, RunMode::counter_diagnostic},
    std::pair{"EXPLORATORY"sv, RunMode::exploratory});
CPU_PREFETCH_DEFINE_ENUM_PARSER(
    lifecycle_state, LifecycleState, "LIF-001",
    std::pair{"PLANNED"sv, LifecycleState::planned},
    std::pair{"PRE_RUN_FAILURE"sv, LifecycleState::pre_run_failure},
    std::pair{"WARMUP_FAILURE"sv, LifecycleState::warmup_failure},
    std::pair{"RESET_FAILURE"sv, LifecycleState::reset_failure},
    std::pair{"MEASUREMENT_STARTED"sv, LifecycleState::measurement_started},
    std::pair{"MEASUREMENT_FAILURE"sv, LifecycleState::measurement_failure},
    std::pair{"DRAIN_FAILURE"sv, LifecycleState::drain_failure},
    std::pair{"COMPLETED"sv, LifecycleState::completed});
CPU_PREFETCH_DEFINE_ENUM_PARSER(join_status, JoinStatus, "DAT-JOIN",
                                std::pair{"NOT_ATTEMPTED"sv, JoinStatus::not_attempted},
                                std::pair{"FAILED"sv, JoinStatus::failed},
                                std::pair{"PASSED"sv, JoinStatus::passed});
CPU_PREFETCH_DEFINE_ENUM_PARSER(
    block_role, BlockRole, "BLK-ROLE", std::pair{"H3_TRAIN"sv, BlockRole::h3_train},
    std::pair{"H3_VALIDATION"sv, BlockRole::h3_validation},
    std::pair{"H1H2_SUPPLEMENTAL"sv, BlockRole::h1h2_supplemental},
    std::pair{"NOT_APPLICABLE"sv, BlockRole::not_applicable});
CPU_PREFETCH_DEFINE_ENUM_PARSER(
    queue_package, QueuePackage, "DAT-PACKAGE", std::pair{"R0"sv, QueuePackage::r0},
    std::pair{"R1"sv, QueuePackage::r1}, std::pair{"R2"sv, QueuePackage::r2},
    std::pair{"L0"sv, QueuePackage::l0}, std::pair{"L1"sv, QueuePackage::l1},
    std::pair{"NBLFQ_MPSC"sv, QueuePackage::nblfq_mpsc},
    std::pair{"NOT_APPLICABLE"sv, QueuePackage::not_applicable});
CPU_PREFETCH_DEFINE_ENUM_PARSER(requested_hardware_state, RequestedHardwareState,
                                "HWP-REQUESTED",
                                std::pair{"H0"sv, RequestedHardwareState::h0},
                                std::pair{"H1"sv, RequestedHardwareState::h1},
                                std::pair{"NOT_APPLICABLE"sv,
                                          RequestedHardwareState::not_applicable});
CPU_PREFETCH_DEFINE_ENUM_PARSER(
    verified_hardware_state, VerifiedHardwareState, "HWP-VERIFIED",
    std::pair{"VERIFIED_DEFAULT"sv, VerifiedHardwareState::verified_default},
    std::pair{"VERIFIED_CHANGED"sv, VerifiedHardwareState::verified_changed},
    std::pair{"VERIFICATION_FAILED"sv, VerifiedHardwareState::verification_failed},
    std::pair{"UNKNOWN"sv, VerifiedHardwareState::unknown},
    std::pair{"NOT_APPLICABLE"sv, VerifiedHardwareState::not_applicable});
CPU_PREFETCH_DEFINE_ENUM_PARSER(placement, Placement, "DAT-PLACEMENT",
                                std::pair{"NEAR"sv, Placement::near},
                                std::pair{"FAR"sv, Placement::far},
                                std::pair{"STAGE_C_OTHER"sv, Placement::stage_c_other},
                                std::pair{"NOT_APPLICABLE"sv,
                                          Placement::not_applicable});
CPU_PREFETCH_DEFINE_ENUM_PARSER(
    working_set_class, WorkingSetClass, "DAT-WORKING-SET",
    std::pair{"L2_RESIDENT"sv, WorkingSetClass::l2_resident},
    std::pair{"LLC_RESIDENT"sv, WorkingSetClass::llc_resident},
    std::pair{"BEYOND_LLC"sv, WorkingSetClass::beyond_llc},
    std::pair{"NOT_APPLICABLE"sv, WorkingSetClass::not_applicable});
CPU_PREFETCH_DEFINE_ENUM_PARSER(
    load_level, LoadLevel, "DAT-LOAD", std::pair{"L025"sv, LoadLevel::l025},
    std::pair{"L050"sv, LoadLevel::l050}, std::pair{"L075"sv, LoadLevel::l075},
    std::pair{"CALIBRATION_READY"sv, LoadLevel::calibration_ready},
    std::pair{"STAGE_C_OTHER"sv, LoadLevel::stage_c_other},
    std::pair{"NOT_APPLICABLE"sv, LoadLevel::not_applicable});
CPU_PREFETCH_DEFINE_ENUM_PARSER(run_validity, RunValidity, "LIF-VALIDITY",
                                std::pair{"NOT_EVALUATED"sv,
                                          RunValidity::not_evaluated},
                                std::pair{"VALID"sv, RunValidity::valid},
                                std::pair{"INVALID"sv, RunValidity::invalid});
CPU_PREFETCH_DEFINE_ENUM_PARSER(gate_status, GateStatus, "LIF-GATE",
                                std::pair{"NOT_EVALUATED"sv, GateStatus::not_evaluated},
                                std::pair{"PASS"sv, GateStatus::pass},
                                std::pair{"FAIL"sv, GateStatus::fail},
                                std::pair{"NOT_APPLICABLE"sv,
                                          GateStatus::not_applicable});
CPU_PREFETCH_DEFINE_ENUM_PARSER(
    confirmatory_estimability, ConfirmatoryEstimability, "LIF-ESTIMABILITY",
    std::pair{"NOT_EVALUATED"sv, ConfirmatoryEstimability::not_evaluated},
    std::pair{"ESTIMABLE"sv, ConfirmatoryEstimability::estimable},
    std::pair{"BLOCKED_ZERO_LOSS"sv, ConfirmatoryEstimability::blocked_zero_loss},
    std::pair{"BLOCKED_EFFECTIVE_TAIL"sv,
              ConfirmatoryEstimability::blocked_effective_tail},
    std::pair{"BLOCKED_INVALID_RUN"sv, ConfirmatoryEstimability::blocked_invalid_run},
    std::pair{"BLOCKED_INCOMPLETE_BLOCK"sv,
              ConfirmatoryEstimability::blocked_incomplete_block},
    std::pair{"BLOCKED_ACCESS_LEAKAGE"sv,
              ConfirmatoryEstimability::blocked_access_leakage},
    std::pair{"BLOCKED_MULTIPLE"sv, ConfirmatoryEstimability::blocked_multiple},
    std::pair{"NOT_APPLICABLE"sv, ConfirmatoryEstimability::not_applicable});
CPU_PREFETCH_DEFINE_ENUM_PARSER(
    confirmatory_blocker, ConfirmatoryBlocker, "LIF-CONFIRMATORY-BLOCKER",
    std::pair{"BLOCKED_ACCESS_LEAKAGE"sv, ConfirmatoryBlocker::blocked_access_leakage},
    std::pair{"BLOCKED_EFFECTIVE_TAIL"sv, ConfirmatoryBlocker::blocked_effective_tail},
    std::pair{"BLOCKED_INCOMPLETE_BLOCK"sv,
              ConfirmatoryBlocker::blocked_incomplete_block},
    std::pair{"BLOCKED_INVALID_RUN"sv, ConfirmatoryBlocker::blocked_invalid_run},
    std::pair{"BLOCKED_ZERO_LOSS"sv, ConfirmatoryBlocker::blocked_zero_loss});
CPU_PREFETCH_DEFINE_ENUM_PARSER(
    block_completeness, BlockCompleteness, "BLK-COMPLETENESS",
    std::pair{"NOT_EVALUATED"sv, BlockCompleteness::not_evaluated},
    std::pair{"COMPLETE"sv, BlockCompleteness::complete},
    std::pair{"INCOMPLETE"sv, BlockCompleteness::incomplete},
    std::pair{"NOT_APPLICABLE"sv, BlockCompleteness::not_applicable});
CPU_PREFETCH_DEFINE_ENUM_PARSER(
    access_state, AccessState, "ACC-STATE",
    std::pair{"PLANNED"sv, AccessState::planned},
    std::pair{"COLLECTED_SEALED"sv, AccessState::collected_sealed},
    std::pair{"TRAINING_OPEN"sv, AccessState::training_open},
    std::pair{"SELECTION_FROZEN"sv, AccessState::selection_frozen},
    std::pair{"VALIDATION_UNSEALED"sv, AccessState::validation_unsealed},
    std::pair{"H3_EVALUATED"sv, AccessState::h3_evaluated},
    std::pair{"H1H2_RELEASED"sv, AccessState::h1h2_released},
    std::pair{"ARCHIVED"sv, AccessState::archived});

#undef CPU_PREFETCH_DEFINE_ENUM_PARSER

} // namespace cpu_prefetch::protocol
