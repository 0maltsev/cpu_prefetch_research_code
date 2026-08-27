#include "cpu_prefetch/protocol/json.hpp"
#include "cpu_prefetch/runner/stage17_fixed_action.hpp"

#include <gtest/gtest.h>

#include <array>
#include <string>
#include <string_view>

namespace {

using cpu_prefetch::runner::stage17::FixedAction;
using cpu_prefetch::runner::stage17::LinuxFixedActionOperations;

[[nodiscard]] auto object(std::string_view text)
    -> cpu_prefetch::protocol::json::Value::Object {
  const auto parsed = cpu_prefetch::protocol::json::parse(text);
  EXPECT_TRUE(parsed.has_value());
  EXPECT_NE(parsed.value().as_object(), nullptr);
  return *parsed.value().as_object();
}

TEST(Stage17FixedAction, RingDistanceCaptureRequiresSealedRunnerAdmission) {
  LinuxFixedActionOperations operations;
  const auto result = operations.execute(
      FixedAction::q16a,
      object(
          R"({"base_page_bytes":4096,"cache_line_bytes":64,"calibration_plan_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","capacity":8,"sample_count":4,"seed_hex":"0000000000000000000000000000000000000000000000000000000000000000","seed_id":"SYNTHETIC-Q16A-SEED"})"));
  ASSERT_FALSE(result.has_value());
  ASSERT_FALSE(result.errors().empty());
  EXPECT_EQ(result.errors().front().rule_id, "S17-Q16A-INPUT");
}

TEST(Stage17FixedAction, CalibrationAndPilotRejectPathWithoutTicketAndSchedule) {
  constexpr std::array packages{"R0", "R1", "R2", "L0", "L1"};
  constexpr std::array actions{FixedAction::q16b, FixedAction::q16c,
                               FixedAction::blinded_pilot};
  LinuxFixedActionOperations operations;
  for (const auto action : actions) {
    for (const auto* package : packages) {
      const std::string input =
          std::string(
              R"({"base_page_bytes":4096,"cache_line_bytes":64,"capacity":64,"d2_cache_lines":2,"offered_count":16,"package":")") +
          package +
          R"(","plan_sha256":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","run_id":"synthetic-stage17-fixed-run","runner_admission_sha256":"cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc","schedule_sha256":"dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd","seed_hex":"0000000000000000000000000000000000000000000000000000000000000000","seed_id":"SYNTHETIC-STAGE17-SEED"})";
      const auto result = operations.execute(action, object(input));
      ASSERT_FALSE(result.has_value()) << package;
      ASSERT_FALSE(result.errors().empty());
      EXPECT_EQ(result.errors().front().rule_id, "S17-RUN-INPUT");
    }
  }
}

TEST(Stage17FixedAction, ExpandedOrMalformedScientificInputFailsClosed) {
  LinuxFixedActionOperations operations;
  const auto result = operations.execute(
      FixedAction::blinded_pilot,
      object(
          R"({"base_page_bytes":4096,"cache_line_bytes":64,"capacity":8,"command":"forbidden","d2_cache_lines":2,"offered_count":1,"package":"R0","plan_sha256":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","run_id":"synthetic-stage17-fixed-run","runner_admission_sha256":"cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc","schedule_sha256":"dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd","seed_hex":"0000000000000000000000000000000000000000000000000000000000000000","seed_id":"SYNTHETIC-STAGE17-SEED"})"));
  EXPECT_FALSE(result.has_value());
}

} // namespace
