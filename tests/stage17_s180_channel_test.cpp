#include "cpu_prefetch/runner/stage17_s180_channel_sink.hpp"
#include <chrono>
#include <gtest/gtest.h>
#include <poll.h>
#include <sys/socket.h>
#include <thread>
#include <unistd.h>
namespace {
using namespace cpu_prefetch::runner::stage17;
struct Pair final {
  std::array<int, 2U> fds{};
  Pair() {
    if (::socketpair(AF_UNIX, SOCK_SEQPACKET | SOCK_CLOEXEC, 0, fds.data()) != 0)
      throw std::runtime_error("socketpair failed");
  }
  ~Pair() {
    for (auto fd : fds)
      static_cast<void>(::close(fd));
  }
  Pair(const Pair&) = delete;
  auto operator=(const Pair&) -> Pair& = delete;
  auto context() const -> FormalArchiveChannelContext {
    return {fds[0U], static_cast<int>(::getpid()), std::string(64U, 'a'),
            std::string(64U, 'b')};
  }
};
auto deadline() -> std::uint64_t {
  return static_cast<std::uint64_t>(
             std::chrono::duration_cast<std::chrono::nanoseconds>(
                 std::chrono::steady_clock::now().time_since_epoch())
                 .count()) +
         2'000'000'000U;
}
auto binding() -> ArtifactBinding {
  return {"S180_CAPTURE_CHECKPOINT",
          "cpu-prefetch-stage17-s180-capture-checkpoint/1",
          "application/json",
          "s180-e0-checkpoint.json",
          100U,
          std::string(64U, 'c')};
}
auto ack() -> std::string {
  return "{\"schema_version\":\"cpu-prefetch-stage17-s180-archive-checkpoint-ack/"
         "1\",\"request_sha256\":\"" +
         std::string(64U, 'a') + "\",\"program_scope_sha256\":\"" +
         std::string(64U, 'b') + "\",\"capture_ordinal\":0,\"checkpoint_sha256\":\"" +
         std::string(64U, 'c') +
         "\",\"status\":\"ARCHIVED_AND_RELEASED\",\"custody_receipt\":{\"file_name\":"
         "\"s180-e0-archive-custody.json\",\"size_bytes\":200,\"sha256\":\"" +
         std::string(64U, 'd') + "\"}}";
}
auto respond(Pair& p, const std::string& reply, std::string& observed) -> std::thread {
  return std::thread([&p, &reply, &observed] {
    pollfd fd{p.fds[1U], POLLIN, 0};
    if (::poll(&fd, 1U, 2000) != 1)
      return;
    std::array<char, 8192U> data{};
    const auto count = ::recv(p.fds[1U], data.data(), data.size(), 0);
    if (count > 0)
      observed.assign(data.data(), static_cast<std::size_t>(count));
    static_cast<void>(::send(p.fds[1U], reply.data(), reply.size(), MSG_NOSIGNAL));
  });
}
struct Output final : ArtifactSink {
  std::size_t published{0U};
  auto publish(ArtifactPayload a)
      -> cpu_prefetch::protocol::Result<ArtifactBinding> override {
    ++published;
    return cpu_prefetch::protocol::Result<ArtifactBinding>::success(
        {a.role, a.schema_identity, a.media_type, a.file_name, a.bytes.size(),
         std::string(64U, 'e')});
  }
};
TEST(S180Channel, NewWireReturnsOnlyScopedS180CustodyAndLegacyRejectsIt) {
  Pair p;
  std::string observed;
  const auto reply = ack();
  auto parent = respond(p, reply, observed);
  auto result =
      exchange_s180_archive_checkpoint(p.context(), binding(), {0U, deadline()});
  parent.join();
  ASSERT_TRUE(result);
  EXPECT_EQ(result.value().role, "S180_ARCHIVE_CUSTODY");
  EXPECT_NE(observed.find("cpu-prefetch-stage17-s180-archive-checkpoint-request/1"),
            std::string::npos);
  EXPECT_FALSE(
      exchange_formal_archive_checkpoint(p.context(), binding(), {0U, deadline()}));
}
TEST(S180Channel, WrongScopeLegacyAckOrFailedEvidenceCannotContinue) {
  for (const auto& change : std::array<std::pair<std::string, std::string>, 4U>{
           {{std::string(64U, 'b'), std::string(64U, 'e')},
            {"s180-archive-checkpoint-ack/1", "archive-checkpoint-ack/1"},
            {"ARCHIVED_AND_RELEASED", "ARCHIVED_FAILED_EVIDENCE"},
            {"s180-e0-archive-custody.json", "../foreign.json"}}}) {
    Pair p;
    std::string observed;
    auto reply = ack();
    reply.replace(reply.find(change.first), change.first.size(), change.second);
    auto parent = respond(p, reply, observed);
    auto result =
        exchange_s180_archive_checkpoint(p.context(), binding(), {0U, deadline()});
    parent.join();
    EXPECT_FALSE(result);
  }
}
TEST(S180Channel, BridgeLatchesFailureButRetainsFinalFailurePublication) {
  Pair p;
  Output output;
  std::array<std::uint64_t, 180U> intervals{};
  intervals.fill(3'000'000'000U);
  S180ChannelSink sink(output, p.context(), intervals, 1024U);
  std::string observed;
  auto reply = ack();
  reply.replace(reply.find("ARCHIVED_AND_RELEASED"), 21U, "ARCHIVED_FAILED_EVIDENCE");
  auto parent = respond(p, reply, observed);
  auto result = sink.archive_checkpoint(binding(), deadline());
  parent.join();
  EXPECT_FALSE(result);
  EXPECT_FALSE(sink.has_archive_checkpoint());
  EXPECT_FALSE(sink.archive_checkpoint(binding(), deadline()));
  EXPECT_TRUE(sink.publish({"S180_SESSION_RESULT",
                            "software-only/1",
                            "application/json",
                            "final.json",
                            {}}));
  EXPECT_EQ(output.published, 1U);
}
TEST(S180Channel, InvalidBoundsOrForeignCheckpointFailBeforeExchange) {
  Pair p;
  Output output;
  std::array<std::uint64_t, 180U> intervals{};
  intervals.fill(3'000'000'000U);
  EXPECT_THROW((S180ChannelSink{output, p.context(), intervals, 0U}),
               std::invalid_argument);
  auto bad = intervals;
  bad[9U] = 0U;
  EXPECT_THROW((S180ChannelSink{output, p.context(), bad, 1024U}),
               std::invalid_argument);
  S180ChannelSink sink(output, p.context(), intervals, 1024U);
  auto wrong = binding();
  wrong.file_name = "s180-e1-checkpoint.json";
  EXPECT_FALSE(sink.archive_checkpoint(wrong, deadline()));
  EXPECT_FALSE(sink.has_archive_checkpoint());
}
} // namespace
