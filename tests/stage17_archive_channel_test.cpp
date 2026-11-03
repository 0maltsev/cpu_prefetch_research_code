#include "cpu_prefetch/runner/stage17_archive_channel.hpp"

#include <gtest/gtest.h>

#include <array>
#include <chrono>
#include <dirent.h>
#include <poll.h>
#include <signal.h>
#include <sys/socket.h>
#include <sys/wait.h>
#include <thread>
#include <unistd.h>

namespace {
using namespace cpu_prefetch::runner::stage17;
class SocketPair final {
public:
  SocketPair() {
    if (::socketpair(AF_UNIX, SOCK_SEQPACKET | SOCK_CLOEXEC, 0, descriptors_.data()) !=
        0)
      throw std::runtime_error("test socketpair failed");
  }
  ~SocketPair() {
    for (const auto fd : descriptors_)
      static_cast<void>(::close(fd));
  }
  SocketPair(const SocketPair&) = delete;
  auto operator=(const SocketPair&) -> SocketPair& = delete;
  auto worker() const noexcept -> int { return descriptors_[0U]; }
  auto parent() const noexcept -> int { return descriptors_[1U]; }

private:
  std::array<int, 2U> descriptors_{};
};
auto deadline(std::chrono::milliseconds duration = std::chrono::seconds(2))
    -> std::uint64_t {
  return static_cast<std::uint64_t>(
      std::chrono::duration_cast<std::chrono::nanoseconds>(
          std::chrono::steady_clock::now().time_since_epoch() + duration)
          .count());
}
auto binding() -> ArtifactBinding {
  return {"FORMAL_CAPTURE_FINAL_CHECKPOINT",
          "cpu-prefetch-stage17-formal-capture-checkpoint/1",
          "application/json",
          "formal-capture-0-final-checkpoint.json",
          100U,
          std::string(64U, 'c')};
}
auto context(const SocketPair& pair) -> FormalArchiveChannelContext {
  return {pair.worker(), static_cast<int>(::getpid()), std::string(64U, 'a'),
          std::string(64U, 'b')};
}
auto acknowledgement() -> std::string {
  return "{\"schema_version\":\"cpu-prefetch-stage17-archive-checkpoint-ack/1\","
         "\"request_sha256\":\"" +
         std::string(64U, 'a') + "\",\"program_scope_sha256\":\"" +
         std::string(64U, 'b') + "\",\"capture_ordinal\":0,\"checkpoint_sha256\":\"" +
         std::string(64U, 'c') +
         "\",\"status\":\"ARCHIVED_AND_RELEASED\",\"custody_receipt\":{"
         "\"file_name\":\"formal-capture-0-archive-custody.json\",\"size_bytes\":200,"
         "\"sha256\":\"" +
         std::string(64U, 'd') + "\"}}";
}
auto exchange(const std::string& reply, std::string* observed = nullptr,
              std::uint64_t* observed_deadline = nullptr) {
  SocketPair pair;
  std::thread parent([&] {
    std::array<char, 8192U> packet{};
    pollfd request{pair.parent(), POLLIN, 0};
    if (::poll(&request, 1U, 2000) != 1 || (request.revents & POLLIN) == 0)
      return;
    const auto count =
        ::recv(pair.parent(), packet.data(), packet.size(), MSG_DONTWAIT);
    if (count > 0 && observed != nullptr)
      *observed = std::string(packet.data(), static_cast<std::size_t>(count));
    static_cast<void>(
        ::send(pair.parent(), reply.data(), reply.size(), MSG_NOSIGNAL | MSG_DONTWAIT));
  });
  const auto absolute = deadline();
  if (observed_deadline != nullptr)
    *observed_deadline = absolute;
  auto result =
      exchange_formal_archive_checkpoint(context(pair), binding(), {0U, absolute});
  parent.join();
  return result;
}

TEST(Stage17ArchiveChannel, BindsOriginalCheckpointBeforeAcceptingCustodyReceipt) {
  std::string observed;
  std::uint64_t absolute = 0U;
  const auto result = exchange(acknowledgement(), &observed, &absolute);
  ASSERT_TRUE(result) << (result ? "" : result.errors().front().message);
  EXPECT_EQ(result.value().file_name, "formal-capture-0-archive-custody.json");
  EXPECT_EQ(result.value().sha256, std::string(64U, 'd'));
  EXPECT_NE(observed.find("cpu-prefetch-stage17-archive-checkpoint-request/1"),
            std::string::npos);
  EXPECT_NE(observed.find(binding().sha256), std::string::npos);
  EXPECT_NE(observed.find(binding().file_name), std::string::npos);
  EXPECT_NE(
      observed.find("\"deadline_monotonic_ns\":" + std::to_string(absolute) + ","),
      std::string::npos);
}

TEST(Stage17ArchiveChannel, RejectsWrongCaptureScopeHashStatusAndReceiptPath) {
  for (const auto& [from, to] : std::array<std::pair<std::string, std::string>, 5U>{
           {{std::string(64U, 'b'), std::string(64U, 'e')},
            {std::string(64U, 'c'), std::string(64U, 'e')},
            {"\"capture_ordinal\":0", "\"capture_ordinal\":1"},
            {"ARCHIVED_AND_RELEASED", "ENCODED_ONLY"},
            {"formal-capture-0-archive-custody.json", "../foreign.json"}}}) {
    auto reply = acknowledgement();
    reply.replace(reply.find(from), from.size(), to);
    EXPECT_FALSE(exchange(reply)) << from;
  }
}

TEST(Stage17ArchiveChannel, RejectsTruncatedOversizedDuplicateOrUnexpectedFields) {
  EXPECT_FALSE(exchange("{"));
  EXPECT_FALSE(exchange(std::string(9000U, 'x')));
  auto extra = acknowledgement();
  extra.insert(1U, "\"unexpected\":false,");
  EXPECT_FALSE(exchange(extra));
  extra = acknowledgement();
  extra.insert(1U, "\"capture_ordinal\":0,");
  EXPECT_FALSE(exchange(extra));
}

TEST(Stage17ArchiveChannel, MissingReplyAndExpiredOrWrongPeerFailClosed) {
  SocketPair pair;
  EXPECT_FALSE(exchange_formal_archive_checkpoint(context(pair), binding(), {0U, 1U}));
  auto wrong = context(pair);
  wrong.controller_pid += 1;
  EXPECT_FALSE(exchange_formal_archive_checkpoint(wrong, binding(), {0U, deadline()}));
  EXPECT_FALSE(exchange_formal_archive_checkpoint(
      context(pair), binding(), {0U, deadline(std::chrono::milliseconds(10))}));
}

struct ChildWait final {
  int status;
  bool forced;
};
auto wait_bounded(pid_t child) -> ChildWait {
  const auto end = std::chrono::steady_clock::now() + std::chrono::seconds(3);
  int status = 0;
  while (std::chrono::steady_clock::now() < end) {
    const auto observed = ::waitpid(child, &status, WNOHANG);
    if (observed == child)
      return {status, false};
    if (observed < 0)
      break;
    const timespec pause{0, 1'000'000};
    static_cast<void>(::nanosleep(&pause, nullptr));
  }
  static_cast<void>(::kill(child, SIGKILL));
  static_cast<void>(::waitpid(child, &status, 0));
  return {status, true};
}
auto task_count() -> std::size_t {
  auto* directory = ::opendir("/proc/self/task");
  if (directory == nullptr)
    throw std::runtime_error("cannot inspect actual child tasks");
  std::size_t count = 0U;
  while (const auto* entry = ::readdir(directory)) {
    if (entry->d_name[0] != '.')
      ++count;
  }
  if (::closedir(directory) != 0)
    throw std::runtime_error("cannot close child task observation");
  return count;
}
TEST(Stage17ArchiveDeadline, KernelTimerAddsNoThreadAndRejectsSecondActiveOwner) {
  const auto child = ::fork();
  ASSERT_GE(child, 0);
  if (child == 0) {
    try {
      const auto before = task_count();
      bool rejected = false;
      {
        FormalArchiveDeadline guard({deadline(std::chrono::seconds(2))});
        if (task_count() != before)
          ::_exit(90);
        try {
          FormalArchiveDeadline duplicate({deadline(std::chrono::seconds(2))});
        } catch (const std::logic_error&) {
          rejected = true;
        }
      }
      if (!rejected || task_count() != before)
        ::_exit(91);
      FormalArchiveDeadline subsequent({deadline(std::chrono::seconds(2))});
    } catch (...) {
      ::_exit(92);
    }
    ::_exit(0);
  }
  const auto outcome = wait_bounded(child);
  ASSERT_FALSE(outcome.forced);
  ASSERT_TRUE(WIFEXITED(outcome.status));
  EXPECT_EQ(WEXITSTATUS(outcome.status), 0);
}
TEST(Stage17ArchiveDeadline, BlockingReadExpiresByKernelSigkill) {
  std::array<int, 2U> block{};
  std::array<int, 2U> ready{};
  ASSERT_EQ(::pipe(block.data()), 0);
  ASSERT_EQ(::pipe(ready.data()), 0);
  const auto child = ::fork();
  ASSERT_GE(child, 0);
  if (child == 0) {
    static_cast<void>(::close(block[1]));
    static_cast<void>(::close(ready[0]));
    try {
      FormalArchiveDeadline guard({deadline(std::chrono::milliseconds(500))});
      const char armed = 'A';
      if (::write(ready[1], &armed, 1U) != 1)
        ::_exit(93);
      char input = 0;
      static_cast<void>(::read(block[0], &input, 1U));
      ::_exit(94); // Returning from this read cannot be accepted as expiry.
    } catch (...) {
      ::_exit(95);
    }
  }
  static_cast<void>(::close(block[0]));
  static_cast<void>(::close(ready[1]));
  pollfd notice{ready[0], POLLIN, 0};
  const bool readable =
      ::poll(&notice, 1U, 1000) == 1 && (notice.revents & POLLIN) != 0;
  char armed = 0;
  const bool reported = readable && ::read(ready[0], &armed, 1U) == 1 && armed == 'A';
  const auto outcome = wait_bounded(child);
  static_cast<void>(::close(ready[0]));
  static_cast<void>(::close(block[1]));
  ASSERT_TRUE(reported);
  ASSERT_FALSE(outcome.forced); // A test watchdog kill is never a timer pass.
  ASSERT_TRUE(WIFSIGNALED(outcome.status));
  EXPECT_EQ(WTERMSIG(outcome.status), SIGKILL);
}
TEST(Stage17ArchiveDeadline, DeletionSurvivesFormerDeadlineAndExpiredInputRejects) {
  EXPECT_THROW(static_cast<void>(FormalArchiveDeadline({1U})), std::invalid_argument);
  const auto child = ::fork();
  ASSERT_GE(child, 0);
  if (child == 0) {
    try {
      {
        FormalArchiveDeadline guard({deadline(std::chrono::milliseconds(500))});
      }
      const timespec pause{0, 700'000'000};
      if (::nanosleep(&pause, nullptr) != 0)
        ::_exit(96);
    } catch (...) {
      ::_exit(97);
    }
    ::_exit(0);
  }
  const auto outcome = wait_bounded(child);
  ASSERT_FALSE(outcome.forced);
  ASSERT_TRUE(WIFEXITED(outcome.status));
  EXPECT_EQ(WEXITSTATUS(outcome.status), 0);
}
} // namespace
