#include "cpu_prefetch/protocol/json.hpp"
#include "cpu_prefetch/qualification/q15_prestate.hpp"

#include <gtest/gtest.h>

#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdio>
#include <fstream>
#include <iterator>
#include <string>
#include <string_view>
#include <variant>
#include <vector>

namespace {

using cpu_prefetch::qualification::Q15StandPrestateClock;
using cpu_prefetch::qualification::Q15StandPrestateCompletion;
using cpu_prefetch::qualification::Q15StandPrestateContext;
using cpu_prefetch::qualification::Q15StandPrestateExecution;
using cpu_prefetch::qualification::Q15StandPrestateExecutor;
using cpu_prefetch::qualification::Q15StandPrestateLimits;

[[nodiscard]] auto context() -> Q15StandPrestateContext {
  using namespace cpu_prefetch::qualification;
  return {
      "Q15-R-P4-R-SYNTHETIC-CAPTURE-01",
      std::string(64U, '2'),
      std::string(64U, '3'),
      std::string(kQ15StandPrestateCollectorContractSha256),
      std::string(40U, 'a'),
      std::string(kQ15SelectedReleaseArchiveSha256),
      "XEON-CPU-FETCH",
  };
}

class FakeClock final : public Q15StandPrestateClock {
public:
  [[nodiscard]] auto now_utc() -> std::string override {
    std::array<char, 32U> value{};
    const auto count =
        std::snprintf(value.data(), value.size(), "2026-08-25T00:00:%02zu.%09zuZ",
                      (calls_ / 1'000'000'000U) % 60U, calls_ % 1'000'000'000U);
    ++calls_;
    return std::string(value.data(), static_cast<std::size_t>(count));
  }

private:
  std::size_t calls_{};
};

class FakeExecutor final : public Q15StandPrestateExecutor {
public:
  [[nodiscard]] auto
  execute(const cpu_prefetch::qualification::Q15StandPrestateCommand& command,
          const Q15StandPrestateLimits&) -> Q15StandPrestateExecution override {
    observed_ids.push_back(command.id);
    if (calls < scripted.size()) {
      return scripted[calls++];
    }
    ++calls;
    return {true, false, false, 0, std::nullopt, 0, "stdout-" + command.id + "\n", {}};
  }

  std::vector<Q15StandPrestateExecution> scripted;
  std::vector<std::string> observed_ids;
  std::size_t calls{};
};

[[nodiscard]] auto accepted(int exit_code = 0) -> Q15StandPrestateExecution {
  return {true, false, false, exit_code, std::nullopt, 0, "value\n", {}};
}

TEST(Q15StandPrestate, ContractHasOnlyExactAbsoluteArgvAndNoPlaceholders) {
  using cpu_prefetch::qualification::kQ15StandPrestateLimits;
  using cpu_prefetch::qualification::q15_stand_prestate_command_contract;
  const auto commands = q15_stand_prestate_command_contract();
  ASSERT_EQ(commands.size(), kQ15StandPrestateLimits.maximum_command_count);
  for (std::size_t index = 0U; index < commands.size(); ++index) {
    const auto expected = "P4R-" + std::string(index + 1U < 10U ? "00" : "0") +
                          std::to_string(index + 1U);
    EXPECT_EQ(commands[index].id, expected);
    ASSERT_FALSE(commands[index].argv.empty());
    EXPECT_EQ(commands[index].argv.front().front(), '/');
    EXPECT_NE(commands[index].argv.front(), "/bin/sh");
    EXPECT_NE(commands[index].argv.front(), "/usr/bin/env");
    for (const auto& argument : commands[index].argv) {
      EXPECT_EQ(argument.find('@'), std::string::npos);
    }
  }
}

TEST(Q15StandPrestate, CompiledCommandContractExactlyMatchesAcceptedJson) {
  using cpu_prefetch::protocol::json::Number;
  using cpu_prefetch::qualification::q15_stand_prestate_command_contract;
  const auto path = std::string(CPU_PREFETCH_SOURCE_DIR) +
                    "/config/q15/q15-r-stand-prestate-collector-contract-v1.json";
  std::ifstream input(path, std::ios::binary);
  ASSERT_TRUE(input.good());
  const std::string bytes((std::istreambuf_iterator<char>(input)),
                          std::istreambuf_iterator<char>());
  const auto parsed = cpu_prefetch::protocol::json::parse(bytes);
  ASSERT_TRUE(parsed.has_value());
  const auto* root = parsed.value().as_object();
  ASSERT_NE(root, nullptr);
  const auto* expected_commands = root->at("commands").as_array();
  ASSERT_NE(expected_commands, nullptr);
  const auto actual_commands = q15_stand_prestate_command_contract();
  ASSERT_EQ(expected_commands->size(), actual_commands.size());

  for (std::size_t index = 0U; index < actual_commands.size(); ++index) {
    const auto* expected = expected_commands->at(index).as_object();
    ASSERT_NE(expected, nullptr);
    ASSERT_NE(expected->at("id").as_string(), nullptr);
    EXPECT_EQ(*expected->at("id").as_string(), actual_commands[index].id);
    ASSERT_NE(expected->at("observation_kind").as_string(), nullptr);
    EXPECT_EQ(*expected->at("observation_kind").as_string(),
              actual_commands[index].observation_kind);
    const auto* expected_argv = expected->at("argv").as_array();
    ASSERT_NE(expected_argv, nullptr);
    ASSERT_EQ(expected_argv->size(), actual_commands[index].argv.size());
    for (std::size_t argument = 0U; argument < expected_argv->size(); ++argument) {
      ASSERT_NE(expected_argv->at(argument).as_string(), nullptr);
      EXPECT_EQ(*expected_argv->at(argument).as_string(),
                actual_commands[index].argv[argument]);
    }
    const auto* expected_codes = expected->at("accepted_exit_codes").as_array();
    ASSERT_NE(expected_codes, nullptr);
    ASSERT_EQ(expected_codes->size(),
              actual_commands[index].accepted_exit_codes.size());
    for (std::size_t code = 0U; code < expected_codes->size(); ++code) {
      const auto* number = expected_codes->at(code).as_number();
      ASSERT_NE(number, nullptr);
      const auto expected_code =
          number->kind == Number::Kind::signed_integer
              ? static_cast<int>(std::get<std::int64_t>(number->value))
              : static_cast<int>(std::get<std::uint64_t>(number->value));
      EXPECT_EQ(expected_code, actual_commands[index].accepted_exit_codes[code]);
    }
  }
}

TEST(Q15StandPrestate, CompleteArtifactIsCanonicalDeterministicAndHashBound) {
  FakeExecutor first_executor;
  FakeClock first_clock;
  const auto first = cpu_prefetch::qualification::collect_q15_stand_prestate(
      context(), first_executor, first_clock);
  ASSERT_TRUE(first.has_value());
  EXPECT_EQ(first.value().completion, Q15StandPrestateCompletion::complete);
  EXPECT_EQ(first.value().observations.size(), 25U);
  EXPECT_EQ(first_executor.calls, 25U);
  EXPECT_TRUE(first.value().failed_command_id == std::nullopt);
  EXPECT_TRUE(first.value().failure_category == std::nullopt);
  EXPECT_TRUE(cpu_prefetch::protocol::Sha256::parse(first.value().artifact_sha256,
                                                    "$/artifact_sha256"));
  EXPECT_TRUE(
      cpu_prefetch::qualification::validate_q15_stand_prestate_artifact(first.value())
          .empty());
  const auto parsed = cpu_prefetch::protocol::json::parse(first.value().canonical_json);
  ASSERT_TRUE(parsed.has_value());
  const auto canonical = cpu_prefetch::protocol::json::canonicalize(parsed.value());
  ASSERT_TRUE(canonical.has_value());
  EXPECT_EQ(canonical.value(), first.value().canonical_json);

  FakeExecutor second_executor;
  FakeClock second_clock;
  const auto second = cpu_prefetch::qualification::collect_q15_stand_prestate(
      context(), second_executor, second_clock);
  ASSERT_TRUE(second.has_value());
  EXPECT_EQ(second.value().canonical_json, first.value().canonical_json);
}

TEST(Q15StandPrestate, AbsentAccountsAreAcceptedObservations) {
  FakeExecutor executor;
  executor.scripted.resize(7U, accepted());
  for (std::size_t index = 2U; index < 7U; ++index) {
    executor.scripted[index] = accepted(2);
  }
  FakeClock clock;
  const auto artifact = cpu_prefetch::qualification::collect_q15_stand_prestate(
      context(), executor, clock);
  ASSERT_TRUE(artifact.has_value());
  EXPECT_EQ(artifact.value().completion, Q15StandPrestateCompletion::complete);
  for (std::size_t index = 2U; index < 7U; ++index) {
    EXPECT_TRUE(artifact.value().observations[index].accepted);
    EXPECT_EQ(artifact.value().observations[index].exit_code, 2);
  }
}

TEST(Q15StandPrestate, UnexpectedExitStopsOnceAndPreservesPartialArtifact) {
  FakeExecutor executor;
  executor.scripted = {accepted(), accepted(), accepted(9)};
  FakeClock clock;
  const auto artifact = cpu_prefetch::qualification::collect_q15_stand_prestate(
      context(), executor, clock);
  ASSERT_TRUE(artifact.has_value());
  EXPECT_EQ(artifact.value().completion, Q15StandPrestateCompletion::partial_failed);
  EXPECT_EQ(executor.calls, 3U);
  EXPECT_EQ(artifact.value().observations.size(), 3U);
  EXPECT_EQ(artifact.value().failed_command_id, "P4R-003");
  EXPECT_EQ(artifact.value().failure_category, "UNEXPECTED_EXIT_CODE");
  EXPECT_FALSE(artifact.value().observations.back().accepted);
}

TEST(Q15StandPrestate, SpawnTimeoutSignalAndOutputFailuresRemainDistinct) {
  const std::array failures{
      Q15StandPrestateExecution{
          false, false, false, std::nullopt, std::nullopt, 2, {}, {}},
      Q15StandPrestateExecution{true, true, false, std::nullopt, 9, 0, {}, {}},
      Q15StandPrestateExecution{true, false, false, std::nullopt, 11, 0, {}, {}},
      Q15StandPrestateExecution{true, false, true, 0, std::nullopt, 0, {}, {}},
  };
  const std::array<std::string_view, 4U> categories{
      "SPAWN_FAILURE", "COMMAND_TIMEOUT", "COMMAND_SIGNAL", "COMMAND_OUTPUT_LIMIT"};
  for (std::size_t index = 0U; index < failures.size(); ++index) {
    FakeExecutor executor;
    executor.scripted = {failures[index]};
    FakeClock clock;
    const auto artifact = cpu_prefetch::qualification::collect_q15_stand_prestate(
        context(), executor, clock);
    ASSERT_TRUE(artifact.has_value());
    EXPECT_EQ(artifact.value().failure_category, categories[index]);
    EXPECT_EQ(executor.calls, 1U);
  }
}

TEST(Q15StandPrestate, BackendCannotBypassPerCommandOutputLimit) {
  FakeExecutor executor;
  auto oversized = accepted();
  oversized.stdout_bytes.assign(cpu_prefetch::qualification::kQ15StandPrestateLimits
                                        .maximum_stdout_bytes_per_command +
                                    1U,
                                'x');
  executor.scripted = {std::move(oversized)};
  FakeClock clock;
  const auto artifact = cpu_prefetch::qualification::collect_q15_stand_prestate(
      context(), executor, clock);
  ASSERT_TRUE(artifact.has_value());
  EXPECT_EQ(artifact.value().failure_category, "COMMAND_OUTPUT_LIMIT");
  EXPECT_EQ(executor.calls, 1U);
}

TEST(Q15StandPrestate, InvalidContextFailsBeforeExecutorCall) {
  auto invalid = context();
  invalid.authorization_sha256 = "bad";
  invalid.stand_id = "other";
  FakeExecutor executor;
  FakeClock clock;
  const auto artifact =
      cpu_prefetch::qualification::collect_q15_stand_prestate(invalid, executor, clock);
  EXPECT_FALSE(artifact.has_value());
  EXPECT_EQ(executor.calls, 0U);
  ASSERT_GE(artifact.errors().size(), 2U);
}

TEST(Q15StandPrestate, ValidatorRejectsCommandAndHashCorruption) {
  FakeExecutor executor;
  FakeClock clock;
  const auto artifact = cpu_prefetch::qualification::collect_q15_stand_prestate(
      context(), executor, clock);
  ASSERT_TRUE(artifact.has_value());

  auto wrong_command = artifact.value();
  wrong_command.observations[0].argv[0] = "/bin/sh";
  const auto command_errors =
      cpu_prefetch::qualification::validate_q15_stand_prestate_artifact(wrong_command);
  EXPECT_TRUE(std::ranges::any_of(command_errors, [](const auto& value) {
    return value.rule_id == "P4R-COMMAND-BINDING";
  }));

  auto wrong_hash = artifact.value();
  wrong_hash.artifact_sha256.assign(64U, '0');
  const auto hash_errors =
      cpu_prefetch::qualification::validate_q15_stand_prestate_artifact(wrong_hash);
  EXPECT_TRUE(std::ranges::any_of(hash_errors, [](const auto& value) {
    return value.rule_id == "P4R-ARTIFACT-HASH";
  }));
}

TEST(Q15StandPrestate, ValidatorRejectsForgedExecutionAndEncodingState) {
  FakeExecutor executor;
  FakeClock clock;
  const auto artifact = cpu_prefetch::qualification::collect_q15_stand_prestate(
      context(), executor, clock);
  ASSERT_TRUE(artifact.has_value());

  auto forged_acceptance = artifact.value();
  forged_acceptance.observations[0].exit_code = 9;
  const auto acceptance_errors =
      cpu_prefetch::qualification::validate_q15_stand_prestate_artifact(
          forged_acceptance);
  EXPECT_TRUE(std::ranges::any_of(acceptance_errors, [](const auto& value) {
    return value.rule_id == "P4R-ACCEPTANCE";
  }));

  auto malformed_encoding = artifact.value();
  malformed_encoding.observations[0].stdout_hex = "ABC";
  malformed_encoding.observations[0].ended_at_utc = "2026-08-24T23:59:59.999999999Z";
  const auto encoding_errors =
      cpu_prefetch::qualification::validate_q15_stand_prestate_artifact(
          malformed_encoding);
  EXPECT_TRUE(std::ranges::any_of(
      encoding_errors, [](const auto& value) { return value.rule_id == "P4R-HEX"; }));
  EXPECT_TRUE(std::ranges::any_of(encoding_errors, [](const auto& value) {
    return value.rule_id == "P4R-TIMESTAMP";
  }));
}

TEST(Q15StandPrestate, ValidatorRejectsForgedFailureCategory) {
  FakeExecutor executor;
  executor.scripted = {accepted(9)};
  FakeClock clock;
  const auto artifact = cpu_prefetch::qualification::collect_q15_stand_prestate(
      context(), executor, clock);
  ASSERT_TRUE(artifact.has_value());
  auto forged = artifact.value();
  forged.failure_category = "SPAWN_FAILURE";
  const auto errors =
      cpu_prefetch::qualification::validate_q15_stand_prestate_artifact(forged);
  EXPECT_TRUE(std::ranges::any_of(errors, [](const auto& value) {
    return value.rule_id == "P4R-FAILURE-CATEGORY";
  }));
}

} // namespace
