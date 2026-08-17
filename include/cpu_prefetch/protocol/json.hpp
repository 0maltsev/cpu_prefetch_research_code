#ifndef CPU_PREFETCH_PROTOCOL_JSON_HPP
#define CPU_PREFETCH_PROTOCOL_JSON_HPP

#include <compare>
#include <cstdint>
#include <map>
#include <string>
#include <string_view>
#include <variant>
#include <vector>

#include "cpu_prefetch/protocol/validation.hpp"

namespace cpu_prefetch::protocol::json {

struct Number {
  enum class Kind : std::uint8_t { signed_integer, unsigned_integer, binary64 };

  Kind kind;
  std::string lexical;
  std::variant<std::int64_t, std::uint64_t, double> value;

  auto operator==(const Number&) const -> bool = default;
};

class Value {
public:
  using Array = std::vector<Value>;
  using Object = std::map<std::string, Value, std::less<>>;
  using Storage =
      std::variant<std::nullptr_t, bool, Number, std::string, Array, Object>;

  Value() : storage_(nullptr) {}
  explicit Value(std::nullptr_t) : storage_(nullptr) {}
  explicit Value(bool value) : storage_(value) {}
  explicit Value(Number value) : storage_(std::move(value)) {}
  explicit Value(std::string value) : storage_(std::move(value)) {}
  explicit Value(Array value) : storage_(std::move(value)) {}
  explicit Value(Object value) : storage_(std::move(value)) {}

  [[nodiscard]] auto storage() const noexcept -> const Storage& { return storage_; }
  [[nodiscard]] auto is_null() const noexcept -> bool;
  [[nodiscard]] auto as_bool() const -> const bool*;
  [[nodiscard]] auto as_number() const -> const Number*;
  [[nodiscard]] auto as_string() const -> const std::string*;
  [[nodiscard]] auto as_array() const -> const Array*;
  [[nodiscard]] auto as_object() const -> const Object*;

  auto operator==(const Value&) const -> bool = default;

private:
  Storage storage_;
};

[[nodiscard]] auto parse(std::string_view input) -> Result<Value>;

// ADR-0015's JCS-I64-v1 profile: RFC 8785 ordering/string/whitespace and
// binary64 number formatting, except exact schema integers remain exact signed
// or unsigned 64-bit values and never pass through binary64.
[[nodiscard]] auto canonicalize(const Value& value) -> Result<std::string>;

} // namespace cpu_prefetch::protocol::json

#endif
