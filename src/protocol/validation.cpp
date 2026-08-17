#include "cpu_prefetch/protocol/validation.hpp"

#include <string>

namespace cpu_prefetch::protocol {

auto to_string(ErrorCategory category) -> std::string {
  switch (category) {
  case ErrorCategory::parse_error:
    return "PARSE_ERROR";
  case ErrorCategory::missing_field:
    return "MISSING_FIELD";
  case ErrorCategory::unknown_field:
    return "UNKNOWN_FIELD";
  case ErrorCategory::invalid_type:
    return "INVALID_TYPE";
  case ErrorCategory::unknown_enum:
    return "UNKNOWN_ENUM";
  case ErrorCategory::unsupported_version:
    return "UNSUPPORTED_VERSION";
  case ErrorCategory::invalid_id:
    return "INVALID_ID";
  case ErrorCategory::invalid_hash:
    return "INVALID_HASH";
  case ErrorCategory::invalid_unit:
    return "INVALID_UNIT";
  case ErrorCategory::out_of_range:
    return "OUT_OF_RANGE";
  case ErrorCategory::duplicate_value:
    return "DUPLICATE_VALUE";
  case ErrorCategory::cross_field:
    return "CROSS_FIELD";
  case ErrorCategory::missing_evidence:
    return "MISSING_EVIDENCE";
  case ErrorCategory::reference_mismatch:
    return "REFERENCE_MISMATCH";
  case ErrorCategory::immutable_configuration:
    return "IMMUTABLE_CONFIGURATION";
  case ErrorCategory::unsupported_number:
    return "UNSUPPORTED_NUMBER";
  }
  return "UNKNOWN_ERROR_CATEGORY";
}

} // namespace cpu_prefetch::protocol
