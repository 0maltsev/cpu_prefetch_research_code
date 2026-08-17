#include "cpu_prefetch/protocol/json.hpp"

#include <algorithm>
#include <array>
#include <charconv>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <string>
#include <system_error>
#include <utility>

namespace cpu_prefetch::protocol::json {
namespace {

constexpr auto is_digit(char value) noexcept -> bool {
  return value >= '0' && value <= '9';
}

auto append_utf8(std::string& output, std::uint32_t code_point) -> bool {
  if (code_point <= 0x7fU) {
    output.push_back(static_cast<char>(code_point));
  } else if (code_point <= 0x7ffU) {
    output.push_back(static_cast<char>(0xc0U | (code_point >> 6U)));
    output.push_back(static_cast<char>(0x80U | (code_point & 0x3fU)));
  } else if (code_point <= 0xffffU) {
    if (code_point >= 0xd800U && code_point <= 0xdfffU) {
      return false;
    }
    output.push_back(static_cast<char>(0xe0U | (code_point >> 12U)));
    output.push_back(static_cast<char>(0x80U | ((code_point >> 6U) & 0x3fU)));
    output.push_back(static_cast<char>(0x80U | (code_point & 0x3fU)));
  } else if (code_point <= 0x10ffffU) {
    output.push_back(static_cast<char>(0xf0U | (code_point >> 18U)));
    output.push_back(static_cast<char>(0x80U | ((code_point >> 12U) & 0x3fU)));
    output.push_back(static_cast<char>(0x80U | ((code_point >> 6U) & 0x3fU)));
    output.push_back(static_cast<char>(0x80U | (code_point & 0x3fU)));
  } else {
    return false;
  }
  return true;
}

auto decode_utf8(std::string_view input) -> Result<std::vector<std::uint32_t>> {
  std::vector<std::uint32_t> code_points;
  for (std::size_t index = 0; index < input.size();) {
    const auto first = static_cast<unsigned char>(input[index]);
    std::uint32_t code_point = 0;
    std::size_t length = 0;
    if (first <= 0x7fU) {
      code_point = first;
      length = 1;
    } else if ((first & 0xe0U) == 0xc0U) {
      code_point = first & 0x1fU;
      length = 2;
    } else if ((first & 0xf0U) == 0xe0U) {
      code_point = first & 0x0fU;
      length = 3;
    } else if ((first & 0xf8U) == 0xf0U) {
      code_point = first & 0x07U;
      length = 4;
    } else {
      return Result<std::vector<std::uint32_t>>::failure(
          {ErrorCategory::parse_error, "$", "JCS-UTF8", "invalid UTF-8 lead byte"});
    }
    if (index + length > input.size()) {
      return Result<std::vector<std::uint32_t>>::failure(
          {ErrorCategory::parse_error, "$", "JCS-UTF8", "truncated UTF-8 sequence"});
    }
    for (std::size_t offset = 1; offset < length; ++offset) {
      const auto next = static_cast<unsigned char>(input[index + offset]);
      if ((next & 0xc0U) != 0x80U) {
        return Result<std::vector<std::uint32_t>>::failure(
            {ErrorCategory::parse_error, "$", "JCS-UTF8",
             "invalid UTF-8 continuation byte"});
      }
      code_point = (code_point << 6U) | (next & 0x3fU);
    }
    const bool overlong = (length == 2 && code_point < 0x80U) ||
                          (length == 3 && code_point < 0x800U) ||
                          (length == 4 && code_point < 0x10000U);
    if (overlong || code_point > 0x10ffffU ||
        (code_point >= 0xd800U && code_point <= 0xdfffU)) {
      return Result<std::vector<std::uint32_t>>::failure(
          {ErrorCategory::parse_error, "$", "JCS-UTF8", "invalid UTF-8 scalar value"});
    }
    code_points.push_back(code_point);
    index += length;
  }
  return Result<std::vector<std::uint32_t>>::success(code_points);
}

class Parser {
public:
  explicit Parser(std::string_view input) : input_(input) {}

  auto parse_document() -> Result<Value> {
    skip_space();
    auto value = parse_value("$");
    if (!value) {
      return value;
    }
    skip_space();
    if (position_ != input_.size()) {
      return fail("$", "trailing content after the JSON value");
    }
    return value;
  }

private:
  auto fail(std::string path, std::string message) const -> Result<Value> {
    return Result<Value>::failure({ErrorCategory::parse_error, std::move(path),
                                   "JSON-PARSE", std::move(message)});
  }

  void skip_space() {
    while (position_ < input_.size()) {
      const char value = input_[position_];
      if (value != ' ' && value != '\t' && value != '\n' && value != '\r') {
        break;
      }
      ++position_;
    }
  }

  auto parse_value(const std::string& path) -> Result<Value> {
    if (position_ >= input_.size()) {
      return fail(path, "expected a JSON value");
    }
    switch (input_[position_]) {
    case 'n':
      return parse_literal("null", Value(nullptr), path);
    case 't':
      return parse_literal("true", Value(true), path);
    case 'f':
      return parse_literal("false", Value(false), path);
    case '"': {
      auto string = parse_string(path);
      if (!string) {
        return Result<Value>::failure(string.errors());
      }
      return Result<Value>::success(Value(std::move(string).value()));
    }
    case '[':
      return parse_array(path);
    case '{':
      return parse_object(path);
    default:
      if (input_[position_] == '-' || is_digit(input_[position_])) {
        return parse_number(path);
      }
      return fail(path, "unexpected byte while parsing JSON value");
    }
  }

  auto parse_literal(std::string_view literal, const Value& value,
                     const std::string& path) -> Result<Value> {
    if (input_.substr(position_, literal.size()) != literal) {
      return fail(path, "invalid JSON literal");
    }
    position_ += literal.size();
    return Result<Value>::success(value);
  }

  auto parse_hex4(std::string path) -> Result<std::uint32_t> {
    if (position_ + 4 > input_.size()) {
      return Result<std::uint32_t>::failure({ErrorCategory::parse_error,
                                             std::move(path), "JSON-UNICODE",
                                             "truncated Unicode escape"});
    }
    std::uint32_t value = 0;
    for (int digit_index = 0; digit_index < 4; ++digit_index) {
      const char character = input_[position_++];
      std::uint32_t digit = 0;
      if (character >= '0' && character <= '9') {
        digit = static_cast<std::uint32_t>(character - '0');
      } else if (character >= 'a' && character <= 'f') {
        digit = 10U + static_cast<std::uint32_t>(character - 'a');
      } else if (character >= 'A' && character <= 'F') {
        digit = 10U + static_cast<std::uint32_t>(character - 'A');
      } else {
        return Result<std::uint32_t>::failure({ErrorCategory::parse_error,
                                               std::move(path), "JSON-UNICODE",
                                               "non-hexadecimal Unicode escape"});
      }
      value = (value << 4U) | digit;
    }
    return Result<std::uint32_t>::success(value);
  }

  auto parse_string(const std::string& path) -> Result<std::string> {
    ++position_;
    std::string output;
    while (position_ < input_.size()) {
      const auto byte = static_cast<unsigned char>(input_[position_++]);
      if (byte == '"') {
        auto decoded = decode_utf8(output);
        if (!decoded) {
          auto errors = decoded.errors();
          errors.front().path = path;
          return Result<std::string>::failure(std::move(errors));
        }
        return Result<std::string>::success(output);
      }
      if (byte < 0x20U) {
        return Result<std::string>::failure({ErrorCategory::parse_error, path,
                                             "JSON-STRING",
                                             "unescaped control byte in string"});
      }
      if (byte != '\\') {
        output.push_back(static_cast<char>(byte));
        continue;
      }
      if (position_ >= input_.size()) {
        return Result<std::string>::failure({ErrorCategory::parse_error, path,
                                             "JSON-STRING", "truncated string escape"});
      }
      const char escaped = input_[position_++];
      switch (escaped) {
      case '"':
      case '\\':
      case '/':
        output.push_back(escaped);
        break;
      case 'b':
        output.push_back('\b');
        break;
      case 'f':
        output.push_back('\f');
        break;
      case 'n':
        output.push_back('\n');
        break;
      case 'r':
        output.push_back('\r');
        break;
      case 't':
        output.push_back('\t');
        break;
      case 'u': {
        auto first = parse_hex4(path);
        if (!first) {
          return Result<std::string>::failure(first.errors());
        }
        std::uint32_t code_point = first.value();
        if (code_point >= 0xd800U && code_point <= 0xdbffU) {
          if (position_ + 2 > input_.size() || input_[position_] != '\\' ||
              input_[position_ + 1] != 'u') {
            return Result<std::string>::failure(
                {ErrorCategory::parse_error, path, "JSON-UNICODE",
                 "high surrogate is not followed by a low surrogate"});
          }
          position_ += 2;
          auto second = parse_hex4(path);
          if (!second) {
            return Result<std::string>::failure(second.errors());
          }
          if (second.value() < 0xdc00U || second.value() > 0xdfffU) {
            return Result<std::string>::failure({ErrorCategory::parse_error, path,
                                                 "JSON-UNICODE",
                                                 "invalid low surrogate"});
          }
          code_point =
              0x10000U + ((code_point - 0xd800U) << 10U) + (second.value() - 0xdc00U);
        } else if (code_point >= 0xdc00U && code_point <= 0xdfffU) {
          return Result<std::string>::failure({ErrorCategory::parse_error, path,
                                               "JSON-UNICODE",
                                               "unpaired low surrogate"});
        }
        if (!append_utf8(output, code_point)) {
          return Result<std::string>::failure({ErrorCategory::parse_error, path,
                                               "JSON-UNICODE",
                                               "invalid Unicode scalar value"});
        }
        break;
      }
      default:
        return Result<std::string>::failure(
            {ErrorCategory::parse_error, path, "JSON-STRING", "unknown string escape"});
      }
    }
    return Result<std::string>::failure(
        {ErrorCategory::parse_error, path, "JSON-STRING", "unterminated string"});
  }

  auto parse_array(const std::string& path) -> Result<Value> {
    ++position_;
    skip_space();
    Value::Array values;
    if (position_ < input_.size() && input_[position_] == ']') {
      ++position_;
      return Result<Value>::success(Value(std::move(values)));
    }
    for (std::size_t index = 0;; ++index) {
      auto value = parse_value(path + "/" + std::to_string(index));
      if (!value) {
        return value;
      }
      values.push_back(std::move(value).value());
      skip_space();
      if (position_ >= input_.size()) {
        return fail(path, "unterminated array");
      }
      if (input_[position_] == ']') {
        ++position_;
        return Result<Value>::success(Value(std::move(values)));
      }
      if (input_[position_] != ',') {
        return fail(path, "expected comma in array");
      }
      ++position_;
      skip_space();
    }
  }

  auto parse_object(const std::string& path) -> Result<Value> {
    ++position_;
    skip_space();
    Value::Object values;
    if (position_ < input_.size() && input_[position_] == '}') {
      ++position_;
      return Result<Value>::success(Value(std::move(values)));
    }
    for (;;) {
      if (position_ >= input_.size() || input_[position_] != '"') {
        return fail(path, "object key must be a string");
      }
      auto key = parse_string(path);
      if (!key) {
        return Result<Value>::failure(key.errors());
      }
      skip_space();
      if (position_ >= input_.size() || input_[position_] != ':') {
        return fail(path, "expected colon after object key");
      }
      ++position_;
      skip_space();
      const std::string child_path = path + "/" + key.value();
      auto value = parse_value(child_path);
      if (!value) {
        return value;
      }
      auto [iterator, inserted] =
          values.emplace(std::move(key).value(), std::move(value).value());
      if (!inserted) {
        return Result<Value>::failure({ErrorCategory::duplicate_value, child_path,
                                       "JSON-DUPLICATE-KEY",
                                       "duplicate object member"});
      }
      static_cast<void>(iterator);
      skip_space();
      if (position_ >= input_.size()) {
        return fail(path, "unterminated object");
      }
      if (input_[position_] == '}') {
        ++position_;
        return Result<Value>::success(Value(std::move(values)));
      }
      if (input_[position_] != ',') {
        return fail(path, "expected comma in object");
      }
      ++position_;
      skip_space();
    }
  }

  auto parse_number(const std::string& path) -> Result<Value> {
    const std::size_t begin = position_;
    if (input_[position_] == '-') {
      ++position_;
      if (position_ >= input_.size()) {
        return fail(path, "truncated number");
      }
    }
    if (input_[position_] == '0') {
      ++position_;
      if (position_ < input_.size() && is_digit(input_[position_])) {
        return fail(path, "leading zero in number");
      }
    } else if (input_[position_] >= '1' && input_[position_] <= '9') {
      while (position_ < input_.size() && is_digit(input_[position_])) {
        ++position_;
      }
    } else {
      return fail(path, "invalid number integer part");
    }
    bool binary64 = false;
    if (position_ < input_.size() && input_[position_] == '.') {
      binary64 = true;
      ++position_;
      if (position_ >= input_.size() || !is_digit(input_[position_])) {
        return fail(path, "fraction requires at least one digit");
      }
      while (position_ < input_.size() && is_digit(input_[position_])) {
        ++position_;
      }
    }
    if (position_ < input_.size() &&
        (input_[position_] == 'e' || input_[position_] == 'E')) {
      binary64 = true;
      ++position_;
      if (position_ < input_.size() &&
          (input_[position_] == '+' || input_[position_] == '-')) {
        ++position_;
      }
      if (position_ >= input_.size() || !is_digit(input_[position_])) {
        return fail(path, "exponent requires at least one digit");
      }
      while (position_ < input_.size() && is_digit(input_[position_])) {
        ++position_;
      }
    }
    const std::string lexical(input_.substr(begin, position_ - begin));
    if (binary64) {
      double value = 0.0;
      const auto result =
          std::from_chars(lexical.data(), lexical.data() + lexical.size(), value,
                          std::chars_format::general);
      if (result.ec != std::errc{} || result.ptr != lexical.data() + lexical.size() ||
          !std::isfinite(value)) {
        return Result<Value>::failure({ErrorCategory::out_of_range, path,
                                       "JSON-NUMBER-RANGE",
                                       "number is outside finite binary64 range"});
      }
      return Result<Value>::success(
          Value(Number{Number::Kind::binary64, lexical, value}));
    }
    if (!lexical.empty() && lexical.front() == '-') {
      std::int64_t value = 0;
      const auto result =
          std::from_chars(lexical.data(), lexical.data() + lexical.size(), value);
      if (result.ec != std::errc{} || result.ptr != lexical.data() + lexical.size()) {
        return Result<Value>::failure(
            {ErrorCategory::out_of_range, path, "JCS-I64-RANGE",
             "negative integer is outside signed 64-bit range"});
      }
      return Result<Value>::success(
          Value(Number{Number::Kind::signed_integer, lexical, value}));
    }
    std::uint64_t value = 0;
    const auto result =
        std::from_chars(lexical.data(), lexical.data() + lexical.size(), value);
    if (result.ec != std::errc{} || result.ptr != lexical.data() + lexical.size()) {
      return Result<Value>::failure(
          {ErrorCategory::out_of_range, path, "JCS-I64-RANGE",
           "nonnegative integer is outside unsigned 64-bit range"});
    }
    return Result<Value>::success(
        Value(Number{Number::Kind::unsigned_integer, lexical, value}));
  }

  std::string_view input_;
  std::size_t position_ = 0;
};

auto utf16_key(std::string_view text) -> Result<std::vector<std::uint16_t>> {
  auto decoded = decode_utf8(text);
  if (!decoded) {
    return Result<std::vector<std::uint16_t>>::failure(decoded.errors());
  }
  std::vector<std::uint16_t> units;
  for (std::uint32_t code_point : decoded.value()) {
    if (code_point <= 0xffffU) {
      units.push_back(static_cast<std::uint16_t>(code_point));
    } else {
      code_point -= 0x10000U;
      units.push_back(static_cast<std::uint16_t>(0xd800U + (code_point >> 10U)));
      units.push_back(static_cast<std::uint16_t>(0xdc00U + (code_point & 0x3ffU)));
    }
  }
  return Result<std::vector<std::uint16_t>>::success(units);
}

auto append_string(std::string_view text, std::string& output) -> Result<bool> {
  auto decoded = decode_utf8(text);
  if (!decoded) {
    return Result<bool>::failure(decoded.errors());
  }
  output.push_back('"');
  constexpr std::array<char, 16> hex = {'0', '1', '2', '3', '4', '5', '6', '7',
                                        '8', '9', 'a', 'b', 'c', 'd', 'e', 'f'};
  for (std::size_t index = 0; index < text.size();) {
    const auto byte = static_cast<unsigned char>(text[index]);
    if (byte >= 0x20U && byte != '"' && byte != '\\') {
      if (byte < 0x80U) {
        output.push_back(static_cast<char>(byte));
        ++index;
      } else {
        std::size_t length = 2;
        if ((byte & 0xf0U) == 0xe0U) {
          length = 3;
        } else if ((byte & 0xf8U) == 0xf0U) {
          length = 4;
        }
        output.append(text.substr(index, length));
        index += length;
      }
      continue;
    }
    ++index;
    switch (byte) {
    case '"':
      output += "\\\"";
      break;
    case '\\':
      output += "\\\\";
      break;
    case '\b':
      output += "\\b";
      break;
    case '\t':
      output += "\\t";
      break;
    case '\n':
      output += "\\n";
      break;
    case '\f':
      output += "\\f";
      break;
    case '\r':
      output += "\\r";
      break;
    default:
      output += "\\u00";
      output.push_back(hex[(byte >> 4U) & 0x0fU]);
      output.push_back(hex[byte & 0x0fU]);
      break;
    }
  }
  output.push_back('"');
  return Result<bool>::success(true);
}

auto canonical_binary64(double value) -> Result<std::string> {
  if (!std::isfinite(value)) {
    return Result<std::string>::failure({ErrorCategory::unsupported_number, "$",
                                         "JCS-NONFINITE",
                                         "JCS does not encode non-finite numbers"});
  }
  if (value == 0.0) {
    return Result<std::string>::success("0");
  }
  std::array<char, 128> buffer{};
  auto converted = std::to_chars(buffer.data(), buffer.data() + buffer.size(), value,
                                 std::chars_format::general);
  if (converted.ec != std::errc{}) {
    return Result<std::string>::failure({ErrorCategory::unsupported_number, "$",
                                         "JCS-BINARY64",
                                         "binary64 shortest conversion failed"});
  }
  std::string shortest(buffer.data(), converted.ptr);
  const bool negative = shortest.front() == '-';
  std::size_t cursor = negative ? 1U : 0U;
  const auto exponent_marker = shortest.find_first_of("eE", cursor);
  const auto coefficient_end =
      exponent_marker == std::string::npos ? shortest.size() : exponent_marker;
  const auto decimal_point = shortest.find('.', cursor);
  const std::size_t integer_digits =
      decimal_point != std::string::npos && decimal_point < coefficient_end
          ? decimal_point - cursor
          : coefficient_end - cursor;
  std::string digits;
  for (std::size_t index = cursor; index < coefficient_end; ++index) {
    if (shortest[index] != '.') {
      digits.push_back(shortest[index]);
    }
  }
  int exponent = 0;
  if (exponent_marker != std::string::npos) {
    auto exponent_text = shortest.substr(exponent_marker + 1);
    if (!exponent_text.empty() && exponent_text.front() == '+') {
      exponent_text.erase(exponent_text.begin());
    }
    const auto parsed = std::from_chars(
        exponent_text.data(), exponent_text.data() + exponent_text.size(), exponent);
    if (parsed.ec != std::errc{}) {
      return Result<std::string>::failure({ErrorCategory::unsupported_number, "$",
                                           "JCS-BINARY64",
                                           "binary64 exponent conversion failed"});
    }
  }
  const int decimal_position = static_cast<int>(integer_digits) + exponent;
  const double magnitude = std::abs(value);
  std::string output = negative ? "-" : "";
  if (magnitude >= 1e-6 && magnitude < 1e21) {
    if (decimal_position <= 0) {
      output += "0.";
      output.append(static_cast<std::size_t>(-decimal_position), '0');
      output += digits;
    } else if (decimal_position >= static_cast<int>(digits.size())) {
      output += digits;
      output.append(static_cast<std::size_t>(decimal_position) - digits.size(), '0');
    } else {
      output.append(digits.data(), static_cast<std::size_t>(decimal_position));
      output.push_back('.');
      output.append(digits.data() + decimal_position,
                    digits.size() - static_cast<std::size_t>(decimal_position));
    }
  } else {
    output.push_back(digits.front());
    if (digits.size() > 1) {
      output.push_back('.');
      output.append(digits.begin() + 1, digits.end());
    }
    const int scientific_exponent = decimal_position - 1;
    output.push_back('e');
    output.push_back(scientific_exponent >= 0 ? '+' : '-');
    output += std::to_string(std::abs(scientific_exponent));
  }
  return Result<std::string>::success(output);
}

auto append_canonical(const Value& value, std::string& output) -> Result<bool> {
  if (value.is_null()) {
    output += "null";
    return Result<bool>::success(true);
  }
  if (const auto* boolean = value.as_bool()) {
    output += *boolean ? "true" : "false";
    return Result<bool>::success(true);
  }
  if (const auto* number = value.as_number()) {
    std::array<char, 32> buffer{};
    if (number->kind == Number::Kind::signed_integer) {
      const auto converted = std::to_chars(buffer.data(), buffer.data() + buffer.size(),
                                           std::get<std::int64_t>(number->value));
      output.append(buffer.data(), converted.ptr);
      return Result<bool>::success(true);
    }
    if (number->kind == Number::Kind::unsigned_integer) {
      const auto converted = std::to_chars(buffer.data(), buffer.data() + buffer.size(),
                                           std::get<std::uint64_t>(number->value));
      output.append(buffer.data(), converted.ptr);
      return Result<bool>::success(true);
    }
    auto canonical = canonical_binary64(std::get<double>(number->value));
    if (!canonical) {
      return Result<bool>::failure(canonical.errors());
    }
    output += canonical.value();
    return Result<bool>::success(true);
  }
  if (const auto* string = value.as_string()) {
    return append_string(*string, output);
  }
  if (const auto* array = value.as_array()) {
    output.push_back('[');
    for (std::size_t index = 0; index < array->size(); ++index) {
      if (index != 0) {
        output.push_back(',');
      }
      auto appended = append_canonical((*array)[index], output);
      if (!appended) {
        return appended;
      }
    }
    output.push_back(']');
    return Result<bool>::success(true);
  }
  const auto& object = *value.as_object();
  struct OrderedMember {
    const std::string* key;
    const Value* value;
    std::vector<std::uint16_t> utf16;
  };
  std::vector<OrderedMember> members;
  members.reserve(object.size());
  for (const auto& [key, child] : object) {
    auto encoded_key = utf16_key(key);
    if (!encoded_key) {
      return Result<bool>::failure(encoded_key.errors());
    }
    members.push_back(OrderedMember{&key, &child, std::move(encoded_key).value()});
  }
  std::sort(members.begin(), members.end(), [](const auto& left, const auto& right) {
    return left.utf16 < right.utf16;
  });
  output.push_back('{');
  for (std::size_t index = 0; index < members.size(); ++index) {
    if (index != 0) {
      output.push_back(',');
    }
    auto key_result = append_string(*members[index].key, output);
    if (!key_result) {
      return key_result;
    }
    output.push_back(':');
    auto child_result = append_canonical(*members[index].value, output);
    if (!child_result) {
      return child_result;
    }
  }
  output.push_back('}');
  return Result<bool>::success(true);
}

} // namespace

auto Value::is_null() const noexcept -> bool {
  return std::holds_alternative<std::nullptr_t>(storage_);
}

auto Value::as_bool() const -> const bool* { return std::get_if<bool>(&storage_); }
auto Value::as_number() const -> const Number* {
  return std::get_if<Number>(&storage_);
}
auto Value::as_string() const -> const std::string* {
  return std::get_if<std::string>(&storage_);
}
auto Value::as_array() const -> const Array* { return std::get_if<Array>(&storage_); }
auto Value::as_object() const -> const Object* {
  return std::get_if<Object>(&storage_);
}

auto parse(std::string_view input) -> Result<Value> {
  return Parser(input).parse_document();
}

auto canonicalize(const Value& value) -> Result<std::string> {
  std::string output;
  auto result = append_canonical(value, output);
  if (!result) {
    return Result<std::string>::failure(result.errors());
  }
  return Result<std::string>::success(output);
}

} // namespace cpu_prefetch::protocol::json
