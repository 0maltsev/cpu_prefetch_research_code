#include "cpu_prefetch/schedule/schedule.hpp"
#include "cpu_prefetch/workload/deterministic.hpp"

#include <gtest/gtest.h>

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <fstream>
#include <iterator>
#include <span>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <variant>
#include <vector>

namespace {

using cpu_prefetch::protocol::DocumentKind;
using cpu_prefetch::protocol::ProtocolRecord;
using cpu_prefetch::protocol::ScheduleRecord;
using cpu_prefetch::schedule::NamespaceRole;
using cpu_prefetch::schedule::ScheduleUse;

auto read_text(std::string_view path) -> std::string {
  std::ifstream input(std::string(path), std::ios::binary);
  return {std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>()};
}

auto read_bytes(std::string_view path) -> std::vector<std::byte> {
  const auto text = read_text(path);
  std::vector<std::byte> result;
  result.reserve(text.size());
  std::ranges::transform(text, std::back_inserter(result),
                         [](char value) { return static_cast<std::byte>(value); });
  return result;
}

auto load_golden() -> ScheduleRecord {
  const auto loaded = cpu_prefetch::protocol::load_document(
      DocumentKind::schedule, read_text(CPU_PREFETCH_STAGE7_GOLDEN_ENVELOPE));
  if (!loaded) {
    throw std::runtime_error(loaded.errors().front().message);
  }
  return std::get<ScheduleRecord>(loaded.value());
}

auto has_rule(const std::vector<cpu_prefetch::protocol::ValidationError>& errors,
              std::string_view rule) -> bool {
  return std::ranges::any_of(
      errors, [rule](const auto& error) { return error.rule_id == rule; });
}

auto decode_record(const ScheduleRecord& record, std::span<const std::byte> artifact)
    -> cpu_prefetch::protocol::Result<cpu_prefetch::schedule::PreparedSchedule> {
  return cpu_prefetch::schedule::decode_and_validate(
      record, artifact, read_text(CPU_PREFETCH_STAGE7_GOLDEN_DERIVATION));
}

void replace_once(std::string& text, std::string_view from, std::string_view to) {
  const auto position = text.find(from);
  if (position == std::string::npos) {
    throw std::runtime_error("test mutation source was not found");
  }
  text.replace(position, from.size(), to);
}

TEST(ScheduleGolden, AcceptedPhiloxAndDecodedArtifactMatch) {
  const auto seed = cpu_prefetch::workload::MasterSeed::from_hex(
      "000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f");
  const auto key = cpu_prefetch::workload::derive_stream_key(
      seed, "stage7-schedule-test",
      cpu_prefetch::workload::StreamPurpose::arrival_schedule);
  EXPECT_EQ(key.words[0], 0x3f0bb803U);
  EXPECT_EQ(key.words[1], 0x84b3f51cU);
  const cpu_prefetch::workload::DeterministicStream stream(key);
  EXPECT_EQ(stream.draw(0U), 0x97a43571a6326b9aULL);
  EXPECT_EQ(stream.draw(1U), 0x56c3c6fdd95d24b5ULL);
  EXPECT_EQ(stream.draw(2U), 0x6c6f5fb1b58c9a53ULL);
  EXPECT_EQ(stream.draw(3U), 0xe5323de41d1a3f26ULL);

  const auto record = load_golden();
  const auto artifact = read_bytes(CPU_PREFETCH_STAGE7_GOLDEN_ARTIFACT);
  const auto decoded = decode_record(record, artifact);
  ASSERT_TRUE(decoded) << decoded.errors().front().message;
  EXPECT_EQ(decoded.value().deadlines().size(), 104U);
  EXPECT_EQ(decoded.value().artifact_sha256(),
            "18f1da603f3d4383bb08410ffb0e41a8c4df336871765e633b4f116f1b22e81c");
  EXPECT_EQ(decoded.value().decoded_deadlines_sha256(),
            "a07a349e5e95ff170036ffb21361d4d85dc9073177de7687c263ff254517a441");
  EXPECT_EQ(decoded.value().schedule_sha256(),
            "df42859564d5075cca591b663e9db8a34da1e8a6ee4d81983d797db2bc6944f9");
  constexpr std::array<std::uint64_t, 12> first{52,  160, 246, 257, 296, 365,
                                                413, 570, 688, 872, 963, 1059};
  constexpr std::array<std::uint64_t, 12> last{8963, 9091, 9164, 9299, 9471, 9495,
                                               9605, 9656, 9835, 9868, 9902, 9998};
  EXPECT_TRUE(
      std::ranges::equal(decoded.value().deadlines().first(first.size()), first));
  EXPECT_TRUE(std::ranges::equal(decoded.value().deadlines().last(last.size()), last));
}

TEST(ScheduleDecoder, RejectsMalformedBytesCountsAndHashes) {
  const auto record = load_golden();
  auto artifact = read_bytes(CPU_PREFETCH_STAGE7_GOLDEN_ARTIFACT);

  artifact.front() ^= std::byte{1};
  const auto corrupt = decode_record(record, artifact);
  ASSERT_FALSE(corrupt);
  EXPECT_TRUE(has_rule(corrupt.errors(), "SCH-ARTIFACT-HASH"));

  artifact.pop_back();
  const auto truncated = decode_record(record, artifact);
  ASSERT_FALSE(truncated);
  EXPECT_TRUE(has_rule(truncated.errors(), "SCH-ARTIFACT-SIZE"));

  auto wrong_count = record;
  wrong_count.offered_count -= 1U;
  const auto count =
      decode_record(wrong_count, read_bytes(CPU_PREFETCH_STAGE7_GOLDEN_ARTIFACT));
  ASSERT_FALSE(count);
  EXPECT_TRUE(has_rule(count.errors(), "SCH-ROW-COUNT"));

  auto wrong_decoded_hash = record;
  const auto parsed_hash = cpu_prefetch::protocol::Sha256::parse(
      std::string(64U, '0'), "$out/decoded_deadlines_sha256");
  ASSERT_TRUE(parsed_hash);
  wrong_decoded_hash.decoded_deadlines_sha256 = parsed_hash.value();
  const auto checksum = decode_record(wrong_decoded_hash,
                                      read_bytes(CPU_PREFETCH_STAGE7_GOLDEN_ARTIFACT));
  ASSERT_FALSE(checksum);
  EXPECT_TRUE(has_rule(checksum.errors(), "SCH-DECODED-HASH"));

  auto wrong_envelope_hash = record;
  wrong_envelope_hash.schedule_sha256 = parsed_hash.value();
  const auto envelope = decode_record(wrong_envelope_hash,
                                      read_bytes(CPU_PREFETCH_STAGE7_GOLDEN_ARTIFACT));
  ASSERT_FALSE(envelope);
  EXPECT_TRUE(has_rule(envelope.errors(), "SCH-ENVELOPE-HASH"));
}

TEST(ScheduleDecoder, RejectsOrderingHorizonEncodingRateAndSuiteViolations) {
  const auto record = load_golden();

  auto decreasing = record;
  decreasing.deadline_storage =
      cpu_prefetch::protocol::InlineDeadlineStorage{{10U, 9U}};
  decreasing.offered_count = 2U;
  decreasing.origin_ticks = 0U;
  decreasing.horizon_ticks = 20U;
  const auto order = decode_record(decreasing, {});
  ASSERT_FALSE(order);
  EXPECT_TRUE(has_rule(order.errors(), "SCH-NONDECREASING"));

  auto at_horizon = decreasing;
  at_horizon.deadline_storage = cpu_prefetch::protocol::InlineDeadlineStorage{{20U}};
  at_horizon.offered_count = 1U;
  const auto boundary = decode_record(at_horizon, {});
  ASSERT_FALSE(boundary);
  EXPECT_TRUE(has_rule(boundary.errors(), "SCH-HALF-OPEN"));

  auto delta = record;
  delta.deadline_encoding =
      cpu_prefetch::protocol::DeadlineEncoding::delta_integer_ticks;
  const auto encoding =
      decode_record(delta, read_bytes(CPU_PREFETCH_STAGE7_GOLDEN_ARTIFACT));
  ASSERT_FALSE(encoding);
  EXPECT_TRUE(has_rule(encoding.errors(), "SCH-SUITE-ENCODING"));

  auto noncanonical_rate = record;
  noncanonical_rate.nominal_offered_rate = {2U, 200U};
  const auto rate =
      decode_record(noncanonical_rate, read_bytes(CPU_PREFETCH_STAGE7_GOLDEN_ARTIFACT));
  ASSERT_FALSE(rate);
  EXPECT_TRUE(has_rule(rate.errors(), "SCH-RATE-CANONICAL"));

  auto wrong_suite = record;
  wrong_suite.rng.version = "2";
  const auto suite =
      decode_record(wrong_suite, read_bytes(CPU_PREFETCH_STAGE7_GOLDEN_ARTIFACT));
  ASSERT_FALSE(suite);
  EXPECT_TRUE(has_rule(suite.errors(), "SCH-SUITE-ID"));
}

TEST(ScheduleDecoder, RejectsDerivationMismatchAndRecordHashCorruption) {
  const auto record = load_golden();
  auto derivation = read_text(CPU_PREFETCH_STAGE7_GOLDEN_DERIVATION);
  replace_once(derivation, "stage7-schedule-test", "different-namespace");
  const auto errors =
      cpu_prefetch::schedule::validate_derivation_record(record, derivation);
  EXPECT_TRUE(has_rule(errors, "SCH-DERIVATION-NAMESPACE"));
  EXPECT_TRUE(has_rule(errors, "SCH-DERIVATION-HASH"));

  const auto decoded = cpu_prefetch::schedule::decode_and_validate(
      record, read_bytes(CPU_PREFETCH_STAGE7_GOLDEN_ARTIFACT), derivation);
  ASSERT_FALSE(decoded);
  EXPECT_TRUE(has_rule(decoded.errors(), "SCH-DERIVATION-NAMESPACE"));
}

TEST(ScheduleSerialization, CanonicalSourceRoundTripsWithoutInformationLoss) {
  const auto text = read_text(CPU_PREFETCH_STAGE7_GOLDEN_ENVELOPE);
  const auto parsed = cpu_prefetch::protocol::json::parse(text);
  ASSERT_TRUE(parsed);
  const auto first = cpu_prefetch::protocol::json::canonicalize(parsed.value());
  ASSERT_TRUE(first);
  const auto reparsed = cpu_prefetch::protocol::json::parse(first.value());
  ASSERT_TRUE(reparsed);
  const auto second = cpu_prefetch::protocol::json::canonicalize(reparsed.value());
  ASSERT_TRUE(second);
  EXPECT_EQ(first.value(), second.value());

  const auto loaded =
      cpu_prefetch::protocol::load_document(DocumentKind::schedule, first.value());
  ASSERT_TRUE(loaded);
  const auto& record = std::get<ScheduleRecord>(loaded.value());
  const auto decoded =
      decode_record(record, read_bytes(CPU_PREFETCH_STAGE7_GOLDEN_ARTIFACT));
  EXPECT_TRUE(decoded) << decoded.errors().front().message;
}

TEST(ScheduleRelationships, ExplicitNamespaceRolesAreDisjointAndKindCompatible) {
  const auto base = load_golden();
  std::array<ScheduleRecord, 7> records{base, base, base, base, base, base, base};
  const std::array roles{NamespaceRole::warmup,        NamespaceRole::calibration,
                         NamespaceRole::pilot,         NamespaceRole::h3_train,
                         NamespaceRole::h3_validation, NamespaceRole::h1h2_supplemental,
                         NamespaceRole::diagnostic};
  const std::array kinds{cpu_prefetch::protocol::ScheduleKind::warmup,
                         cpu_prefetch::protocol::ScheduleKind::calibration,
                         cpu_prefetch::protocol::ScheduleKind::pilot,
                         cpu_prefetch::protocol::ScheduleKind::confirmatory,
                         cpu_prefetch::protocol::ScheduleKind::confirmatory,
                         cpu_prefetch::protocol::ScheduleKind::confirmatory,
                         cpu_prefetch::protocol::ScheduleKind::diagnostic};
  std::vector<ScheduleUse> uses;
  uses.reserve(records.size());
  for (std::size_t index = 0; index < records.size(); ++index) {
    const auto namespace_id = cpu_prefetch::protocol::NamespaceId::parse(
        "namespace-" + std::to_string(index), "$test/namespace_id");
    ASSERT_TRUE(namespace_id);
    records[index].namespace_id = namespace_id.value();
    records[index].schedule_kind = kinds[index];
    uses.push_back({&records[index], roles[index], "treatment-" + std::to_string(index),
                    "family-" + std::to_string(index)});
  }
  EXPECT_TRUE(cpu_prefetch::schedule::validate_schedule_uses(uses).empty());

  const std::array collision{
      ScheduleUse{&base, NamespaceRole::h3_train, "R0-H0", "family-a"},
      ScheduleUse{&base, NamespaceRole::h3_validation, "R1-H1", "family-b"}};
  const auto errors = cpu_prefetch::schedule::validate_schedule_uses(collision);
  EXPECT_TRUE(has_rule(errors, "SCH-NAMESPACE-DISJOINT"));
}

TEST(ScheduleRelationships, MatchedTreatmentsRequireOneExactCommonSchedule) {
  const auto base = load_golden();
  const std::array matched{
      ScheduleUse{&base, NamespaceRole::h3_train, "R0-H0", "matched-family"},
      ScheduleUse{&base, NamespaceRole::h3_train, "R1-H1", "matched-family"}};
  EXPECT_TRUE(cpu_prefetch::schedule::validate_schedule_uses(matched).empty());

  auto changed = base;
  changed.horizon_ticks += 1U;
  const std::array mismatch{
      ScheduleUse{&base, NamespaceRole::h3_train, "R0-H0", "matched-family"},
      ScheduleUse{&changed, NamespaceRole::h3_train, "R1-H1", "matched-family"}};
  const auto errors = cpu_prefetch::schedule::validate_schedule_uses(mismatch);
  EXPECT_TRUE(has_rule(errors, "SCH-COMMON-FAMILY"));
  EXPECT_TRUE(has_rule(errors, "SCH-NAMESPACE-COLLISION"));
}

} // namespace
