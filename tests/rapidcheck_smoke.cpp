#include <rapidcheck.h>

#include "cpu_prefetch/protocol/json.hpp"

#include <algorithm>
#include <cstdint>
#include <exception>
#include <iostream>
#include <string>
#include <vector>

int main() {
  try {
    const bool framework_passed = rc::check("reversing a vector twice preserves it",
                                            [](const std::vector<int>& input) {
                                              auto copy = input;
                                              std::reverse(copy.begin(), copy.end());
                                              std::reverse(copy.begin(), copy.end());
                                              RC_ASSERT(copy == input);
                                            });
    const bool exact_integer_passed = rc::check(
        "JCS-I64 preserves every generated uint64 value", [](std::uint64_t input) {
          const std::string text = "{\"value\":" + std::to_string(input) + "}";
          const auto parsed = cpu_prefetch::protocol::json::parse(text);
          RC_ASSERT(parsed.has_value());
          const auto canonical =
              cpu_prefetch::protocol::json::canonicalize(parsed.value());
          RC_ASSERT(canonical.has_value());
          RC_ASSERT(canonical.value() == text);
        });
    return framework_passed && exact_integer_passed ? 0 : 1;
  } catch (const std::exception& error) {
    std::cerr << "RapidCheck smoke test failed with exception: " << error.what()
              << '\n';
  } catch (...) {
    std::cerr << "RapidCheck smoke test failed with an unknown exception\n";
  }
  return 2;
}
