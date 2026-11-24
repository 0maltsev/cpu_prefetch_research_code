#include "cpu_prefetch/runner/stage17_formal_checkpoint.hpp"

#include <gtest/gtest.h>

namespace {
using namespace cpu_prefetch;
using namespace runner::stage17;
using Value = protocol::json::Value;
using Object = Value::Object;
auto text(std::string s) -> Value { return Value(std::move(s)); }
auto number(std::uint64_t n) -> Value {
  return Value(protocol::json::Number{protocol::json::Number::Kind::unsigned_integer,
                                      std::to_string(n), n});
}
auto capture() -> Object {
  return {{"ordinal", number(7U)},
          {"hardware_state", text("H1")},
          {"warmup", Value(Object{{"run_id", text("warmup-7")}})},
          {"measurement", Value(Object{{"run_id", text("measurement-7")}})}};
}
auto final_result(std::uint64_t stop = 14U) -> Value {
  return Value(Object{{"stop", number(stop)},
                      {"publication_attempted", Value(true)},
                      {"publication_succeeded", Value(true)},
                      {"retained_failure_detail", text("opaque original fact")}});
}
auto artifacts(std::size_t count) -> std::vector<ArtifactBinding> {
  std::vector<ArtifactBinding> result;
  result.reserve(count);
  for (std::size_t i = 0U; i < count; ++i)
    result.push_back({"RAW", "original-format", "application/octet-stream",
                      "original-" + std::to_string(i) + ".bin", i,
                      std::string(64U, 'b')});
  return result;
}
class Sink final : public ArtifactSink {
public:
  bool fail{false};
  std::vector<ArtifactPayload> published;
  auto publish(ArtifactPayload payload) -> protocol::Result<ArtifactBinding> override {
    if (fail)
      return protocol::Result<ArtifactBinding>::failure(
          {protocol::ErrorCategory::cross_field, "$", "TEST-FSYNC", "sync failed"});
    ArtifactBinding binding{payload.role,         payload.schema_identity,
                            payload.media_type,   payload.file_name,
                            payload.bytes.size(), std::string(64U, 'c')};
    published.push_back(std::move(payload));
    return protocol::Result<ArtifactBinding>::success(binding);
  }
  auto document() const -> Value {
    const auto& bytes = published.at(0U).bytes;
    auto parsed = protocol::json::parse(
        std::string_view(reinterpret_cast<const char*>(bytes.data()), bytes.size()));
    if (!parsed)
      throw std::runtime_error("test receipt is not JSON");
    return parsed.value();
  }
};

TEST(Stage17FormalCheckpoint, PreservesOriginalFinalResultAndAllBindings) {
  for (const auto action : {FixedAction::q16a, FixedAction::q16b, FixedAction::q16c}) {
    Sink sink;
    const auto count = action == FixedAction::q16a   ? 9U
                       : action == FixedAction::q16b ? 6U
                                                     : 8U;
    const auto originals = artifacts(count);
    const auto final = final_result();
    const auto result = publish_formal_checkpoint(sink, action, std::string(64U, 'a'),
                                                  capture(), final, originals, true);
    ASSERT_TRUE(result);
    ASSERT_EQ(sink.published.size(), 1U);
    EXPECT_EQ(result.value().file_name, "formal-capture-7-final-checkpoint.json");
    const auto document = sink.document();
    const auto& object = *document.as_object();
    EXPECT_EQ(object.at("native_result_after_cleanup"), final);
    EXPECT_EQ(*object.at("scientific_validity").as_string(), "NOT_ASSESSED");
    EXPECT_FALSE(*object.at("execution_authority").as_bool());
    EXPECT_EQ(object.at("artifacts").as_array()->size(), originals.size());
    EXPECT_EQ(
        *object.at("capture_identity").as_object()->at("warmup_run_id").as_string(),
        "warmup-7");
  }
}

TEST(Stage17FormalCheckpoint, RetainsFailedAndEmptyPrefixesWithoutClaimingCompletion) {
  for (const auto count : {0U, 2U, 9U}) {
    Sink sink;
    const auto final = final_result(12U);
    ASSERT_TRUE(publish_formal_checkpoint(sink, FixedAction::q16a,
                                          std::string(64U, 'a'), capture(), final,
                                          artifacts(count), false));
    const auto document = sink.document();
    EXPECT_EQ(document.as_object()->at("native_result_after_cleanup"), final);
    EXPECT_FALSE(*document.as_object()->at("native_complete").as_bool());
    EXPECT_EQ(document.as_object()->at("artifacts").as_array()->size(), count);
  }
}

TEST(Stage17FormalCheckpoint, RejectsFalseCompletionAndUnsafeIdentityBeforeWriting) {
  Sink sink;
  const auto attempt = [&](const Object& item, const auto& bindings, bool complete) {
    return publish_formal_checkpoint(sink, FixedAction::q16a, std::string(64U, 'a'),
                                     item, final_result(), bindings, complete);
  };
  EXPECT_FALSE(attempt(capture(), artifacts(8U), true));
  EXPECT_FALSE(attempt(capture(), artifacts(9U), false));
  auto duplicates = artifacts(9U);
  duplicates[1U] = duplicates[0U];
  EXPECT_FALSE(attempt(capture(), duplicates, true));
  duplicates = artifacts(9U);
  duplicates[0U].file_name = "../original.bin";
  EXPECT_FALSE(attempt(capture(), duplicates, true));
  auto identity = capture();
  identity.at("measurement") = identity.at("warmup");
  EXPECT_FALSE(attempt(identity, artifacts(9U), true));
  EXPECT_FALSE(publish_formal_checkpoint(sink, FixedAction::blinded_pilot,
                                         std::string(64U, 'a'), capture(),
                                         final_result(), artifacts(9U), true));
  EXPECT_FALSE(publish_formal_checkpoint(sink, FixedAction::q16a, "bad", capture(),
                                         final_result(), artifacts(9U), true));
  EXPECT_TRUE(sink.published.empty());
}

TEST(Stage17FormalCheckpoint, PropagatesDurablePublicationFailure) {
  Sink sink;
  sink.fail = true;
  const auto result =
      publish_formal_checkpoint(sink, FixedAction::q16a, std::string(64U, 'a'),
                                capture(), final_result(), artifacts(9U), true);
  ASSERT_FALSE(result);
  ASSERT_EQ(result.errors().size(), 1U);
  EXPECT_EQ(result.errors()[0U].rule_id, "TEST-FSYNC");
  EXPECT_TRUE(sink.published.empty());
}

TEST(Stage17FormalCheckpoint, FailedWriterRetainsSuccessfulPrefixInOuterReceipt) {
  for (const auto successful : {0U, 1U, 3U, 8U}) {
    Sink sink;
    std::vector<ArtifactBinding> prefix;
    FormalPublicationTrackingSink tracked(sink, prefix);
    // The enclosing writer returns failure and never returns its local vector.
    const auto writer = [&]() -> protocol::Result<std::vector<ArtifactBinding>> {
      for (std::size_t i = 0U; i <= successful; ++i) {
        sink.fail = i == successful;
        auto result = tracked.publish({"RAW",
                                       "original-format",
                                       "application/octet-stream",
                                       "original-" + std::to_string(i) + ".bin",
                                       {}});
        if (!result)
          return protocol::Result<std::vector<ArtifactBinding>>::failure(
              result.errors());
      }
      return protocol::Result<std::vector<ArtifactBinding>>::success({});
    };
    EXPECT_FALSE(writer());
    ASSERT_EQ(prefix.size(), successful);
    ASSERT_EQ(sink.published.size(), successful);
    Sink receipt;
    auto final_object = *final_result(12U).as_object();
    final_object.at("publication_succeeded") = Value(false);
    const auto final = Value(std::move(final_object));
    ASSERT_TRUE(publish_formal_checkpoint(receipt, FixedAction::q16a,
                                          std::string(64U, 'a'), capture(), final,
                                          prefix, false));
    const auto document = receipt.document();
    const auto& rows = *document.as_object()->at("artifacts").as_array();
    ASSERT_EQ(rows.size(), successful);
    for (std::size_t i = 0U; i < successful; ++i) {
      EXPECT_EQ(*rows[i].as_object()->at("file_name").as_string(),
                sink.published[i].file_name);
      EXPECT_EQ(*rows[i].as_object()->at("sha256").as_string(), prefix[i].sha256);
    }
    EXPECT_FALSE(*document.as_object()->at("native_complete").as_bool());
  }
}

TEST(Stage17FormalCheckpoint, WriterExceptionDoesNotDiscardSuccessfulBindings) {
  Sink sink;
  std::vector<ArtifactBinding> prefix;
  FormalPublicationTrackingSink tracked(sink, prefix);
  EXPECT_THROW(
      {
        ASSERT_TRUE(tracked.publish(
            {"RAW", "original-format", "application/octet-stream", "one.bin", {}}));
        throw std::runtime_error("later writer serialization failed");
      },
      std::runtime_error);
  ASSERT_EQ(prefix.size(), 1U);
  EXPECT_EQ(prefix[0].file_name, "one.bin");
  EXPECT_EQ(sink.published.size(), 1U);
}
} // namespace
