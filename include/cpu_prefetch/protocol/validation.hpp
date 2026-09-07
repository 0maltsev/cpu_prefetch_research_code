#ifndef CPU_PREFETCH_PROTOCOL_VALIDATION_HPP
#define CPU_PREFETCH_PROTOCOL_VALIDATION_HPP

#include <cstdint>
#include <memory>
#include <string>
#include <utility>
#include <vector>

namespace cpu_prefetch::protocol {

enum class ErrorCategory : std::uint8_t {
  parse_error,
  missing_field,
  unknown_field,
  invalid_type,
  unknown_enum,
  unsupported_version,
  invalid_id,
  invalid_hash,
  invalid_unit,
  out_of_range,
  duplicate_value,
  cross_field,
  missing_evidence,
  reference_mismatch,
  immutable_configuration,
  unsupported_number,
};

[[nodiscard]] auto to_string(ErrorCategory category) -> std::string;

struct ValidationError {
  ErrorCategory category;
  std::string path;
  std::string rule_id;
  std::string message;

  auto operator==(const ValidationError&) const -> bool = default;
};

template <typename T> class Result {
public:
  static auto success(const T& value) -> Result { return Result(value); }

  static auto failure(ValidationError error) -> Result {
    std::vector<ValidationError> errors;
    errors.push_back(std::move(error));
    return Result(std::move(errors));
  }

  static auto failure(std::vector<ValidationError> errors) -> Result {
    return Result(std::move(errors));
  }

  [[nodiscard]] auto has_value() const noexcept -> bool { return value_ != nullptr; }

  explicit operator bool() const noexcept { return has_value(); }

  [[nodiscard]] auto value() & -> T& { return *value_; }
  [[nodiscard]] auto value() const& -> const T& { return *value_; }
  [[nodiscard]] auto value() && -> T&& { return std::move(*value_); }

  [[nodiscard]] auto errors() const -> const std::vector<ValidationError>& {
    return errors_;
  }

private:
  explicit Result(const T& value) : value_(std::make_unique<T>(value)) {}
  explicit Result(std::vector<ValidationError> errors) : errors_(std::move(errors)) {}

  std::unique_ptr<T> value_;
  std::vector<ValidationError> errors_;
};

class SemanticValidator;

} // namespace cpu_prefetch::protocol

#endif
