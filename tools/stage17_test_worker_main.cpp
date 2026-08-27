#include "cpu_prefetch/runner/stage17_fixed_action.hpp"

#include <cstddef>
#include <cstring>
#include <exception>
#include <iostream>
#include <string>
#include <string_view>
#include <vector>

#if defined(__SANITIZE_ADDRESS__)
extern "C" const char* __asan_default_options() { return "detect_leaks=0"; }
#elif defined(__has_feature)
#if __has_feature(address_sanitizer)
extern "C" const char* __asan_default_options() { return "detect_leaks=0"; }
#endif
#endif

namespace {

using cpu_prefetch::protocol::ErrorCategory;
using cpu_prefetch::protocol::Result;
using cpu_prefetch::protocol::ValidationError;
using cpu_prefetch::runner::stage17::ActionOutcome;
using cpu_prefetch::runner::stage17::ArtifactPayload;
using cpu_prefetch::runner::stage17::FixedAction;
using cpu_prefetch::runner::stage17::FixedActionOperations;

class TestLinkedOperations final : public FixedActionOperations {
public:
  [[nodiscard]] auto
  execute(FixedAction action,
          const cpu_prefetch::protocol::json::Value::Object& action_inputs)
      -> Result<ActionOutcome> override {
    const auto nonce = action_inputs.find("fixture_nonce");
    if (action_inputs.size() != 1U || nonce == action_inputs.end() ||
        nonce->second.as_string() == nullptr || nonce->second.as_string()->empty()) {
      return Result<ActionOutcome>::failure(ValidationError{
          ErrorCategory::cross_field, "$/action_inputs", "S17-TEST-BACKEND-INPUT",
          "test-linked backend requires exactly one nonempty fixture nonce"});
    }
    const auto action_name =
        std::string(cpu_prefetch::runner::stage17::to_string(action));
    const auto payload =
        std::string("{\"action_id\":\"") + action_name +
        "\",\"complete\":true,\"fixture_nonce\":\"" + *nonce->second.as_string() +
        "\",\"schema_version\":\"cpu-prefetch-stage17-test-action-output/2\","
        "\"synthetic_test_only\":true}\n";
    std::vector<std::byte> encoded(payload.size());
    std::memcpy(encoded.data(), payload.data(), payload.size());
    const bool restored = action == FixedAction::q15_w;
    return Result<ActionOutcome>::success(
        {{{"SYNTHETIC_FIXED_ACTION_OUTPUT", "cpu-prefetch-stage17-test-action-output/2",
           "application/json", "synthetic-fixed-action-output-v2.json",
           std::move(encoded)}},
         restored,
         false,
         "SYNTHETIC_TEST_LINKED_COMPLETE"});
  }

  [[nodiscard]] auto synthetic_test_only() const noexcept -> bool override {
    return true;
  }
};

} // namespace

int main(int argc, char** argv) {
  try {
    TestLinkedOperations operations;
    return cpu_prefetch::runner::stage17::run_fixed_action_worker(argc, argv,
                                                                  operations);
  } catch (const std::exception& exception) {
    std::cerr << "stage17-test-worker: FAIL: " << exception.what() << '\n';
  } catch (...) {
    std::cerr << "stage17-test-worker: FAIL: non-standard exception\n";
  }
  return 1;
}
