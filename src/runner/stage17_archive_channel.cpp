#include "cpu_prefetch/runner/stage17_archive_channel.hpp"

#include "stage17_formal_input_detail.hpp"

#include <array>
#include <atomic>
#include <cerrno>
#include <climits>
#include <ctime>
#include <poll.h>
#include <signal.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <system_error>
#include <unistd.h>

namespace cpu_prefetch::runner::stage17 {
namespace {
using Value = protocol::json::Value;
using Object = Value::Object;
std::atomic_flag active_deadline = ATOMIC_FLAG_INIT;
[[noreturn]] void deadline_cleanup_failure() noexcept {
  // Never continue into another capture with an uncertain armed process timer.
  // SIGKILL cannot run a handler or produce an unbudgeted core dump.
  static_cast<void>(::kill(::getpid(), SIGKILL));
  ::_exit(125);
}

namespace input = formal_input_detail;
void require(bool condition, const char* message) {
  if (!condition)
    throw std::invalid_argument(message);
}
auto hash(std::string_view value) -> bool {
  return value.size() == 64U && std::all_of(value.begin(), value.end(), [](char c) {
           return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f');
         });
}
auto text(std::string_view value) -> Value { return Value(std::string(value)); }
auto number(std::uint64_t value) -> Value {
  return Value(protocol::json::Number{protocol::json::Number::Kind::unsigned_integer,
                                      std::to_string(value), value});
}
auto remaining_time(std::uint64_t deadline) -> std::uint64_t {
  timespec now{};
  require(::clock_gettime(CLOCK_MONOTONIC, &now) == 0 && now.tv_sec >= 0 &&
              now.tv_nsec >= 0 && now.tv_nsec < 1'000'000'000,
          "archive channel clock unavailable");
  const auto seconds = static_cast<std::uint64_t>(now.tv_sec);
  const auto nanos = static_cast<std::uint64_t>(now.tv_nsec);
  require(seconds <=
              (std::numeric_limits<std::uint64_t>::max() - nanos) / 1'000'000'000U,
          "archive channel clock overflow");
  const auto current = seconds * 1'000'000'000U + nanos;
  require(current < deadline, "archive channel deadline expired");
  return deadline - current;
}
struct ReadyRequest final {
  short event;
  std::uint64_t deadline;
};
void ready(int descriptor, ReadyRequest request) {
  const auto remaining = remaining_time(request.deadline);
  const auto milliseconds =
      remaining / 1'000'000U + (remaining % 1'000'000U != 0U ? 1U : 0U);
  pollfd item{descriptor, request.event, 0};
  const auto result = ::poll(&item, 1U,
                             static_cast<int>(std::min<std::uint64_t>(
                                 milliseconds, static_cast<std::uint64_t>(INT_MAX))));
  require(result == 1 && (item.revents & request.event) != 0 &&
              (item.revents & (POLLERR | POLLHUP | POLLNVAL)) == 0,
          "archive channel unavailable, interrupted or timed out");
}
void peer(const FormalArchiveChannelContext& channel) {
  require(channel.descriptor > 2 && channel.controller_pid > 0,
          "archive channel descriptor/controller is invalid");
  int type = 0;
  socklen_t length = sizeof(type);
  require(::getsockopt(channel.descriptor, SOL_SOCKET, SO_TYPE, &type, &length) == 0 &&
              length == sizeof(type) && type == SOCK_SEQPACKET,
          "archive channel must be SOCK_SEQPACKET");
  sockaddr_un address{};
  length = sizeof(address);
  require(::getsockname(channel.descriptor, reinterpret_cast<sockaddr*>(&address),
                        &length) == 0 &&
              address.sun_family == AF_UNIX,
          "archive channel must be local");
  ucred credentials{};
  length = sizeof(credentials);
  require(::getsockopt(channel.descriptor, SOL_SOCKET, SO_PEERCRED, &credentials,
                       &length) == 0 &&
              length == sizeof(credentials) &&
              credentials.pid == channel.controller_pid &&
              credentials.uid == ::geteuid(),
          "archive channel parent credentials differ");
}
} // namespace

FormalArchiveDeadline::FormalArchiveDeadline(FormalArchiveAbsoluteDeadline absolute) {
  static_cast<void>(remaining_time(absolute.monotonic_ns));
  const auto seconds = absolute.monotonic_ns / 1'000'000'000U;
  if (seconds > static_cast<std::uint64_t>(std::numeric_limits<time_t>::max()))
    throw std::invalid_argument("archive deadline cannot be represented by timer");
  if (active_deadline.test_and_set(std::memory_order_acquire))
    throw std::logic_error("native archive process already owns a deadline timer");
  bool created = false;
  try {
    sigevent event{};
    event.sigev_notify = SIGEV_SIGNAL;
    event.sigev_signo = SIGKILL;
    if (::timer_create(CLOCK_MONOTONIC, &event, &timer_) != 0)
      throw std::system_error(errno, std::generic_category(), "archive timer_create");
    created = true;
    itimerspec setting{};
    setting.it_value.tv_sec = static_cast<time_t>(seconds);
    setting.it_value.tv_nsec =
        static_cast<long>(absolute.monotonic_ns % 1'000'000'000U);
    if (::timer_settime(timer_, TIMER_ABSTIME, &setting, nullptr) != 0)
      throw std::system_error(errno, std::generic_category(), "archive timer_settime");
  } catch (...) {
    if (created && ::timer_delete(timer_) != 0)
      deadline_cleanup_failure();
    active_deadline.clear(std::memory_order_release);
    throw;
  }
}
FormalArchiveDeadline::~FormalArchiveDeadline() noexcept {
  if (::timer_delete(timer_) != 0)
    deadline_cleanup_failure();
  active_deadline.clear(std::memory_order_release);
}

auto validate_formal_archive_channel(const FormalArchiveChannelContext& channel)
    -> protocol::Result<bool> {
  try {
    require(hash(channel.request_sha256) && hash(channel.program_scope_sha256),
            "archive channel scope hashes are malformed");
    peer(channel);
    return protocol::Result<bool>::success(true);
  } catch (const std::exception& exception) {
    return protocol::Result<bool>::failure(
        {protocol::ErrorCategory::cross_field, "$/formal/archive_channel",
         "S17-ARCHIVE-CHECKPOINT-CHANNEL", exception.what()});
  }
}

namespace {
auto exchange_checkpoint(const FormalArchiveChannelContext& channel,
                         const ArtifactBinding& checkpoint,
                         FormalArchiveExchangeLimits limits, bool s180)
    -> protocol::Result<ArtifactBinding> {
  try {
    const auto checkpoint_name =
        s180 ? "s180-e" + std::to_string(limits.ordinal) + "-checkpoint.json"
             : "formal-capture-" + std::to_string(limits.ordinal) +
                   "-final-checkpoint.json";
    const auto receipt_name =
        s180 ? "s180-e" + std::to_string(limits.ordinal) + "-archive-custody.json"
             : "formal-capture-" + std::to_string(limits.ordinal) +
                   "-archive-custody.json";
    require(!s180 || limits.ordinal < 180U,
            "S180 checkpoint ordinal is outside the family");
    require(hash(channel.request_sha256) && hash(channel.program_scope_sha256) &&
                hash(checkpoint.sha256) && checkpoint.size_bytes > 0U &&
                checkpoint.role == (s180 ? "S180_CAPTURE_CHECKPOINT"
                                         : "FORMAL_CAPTURE_FINAL_CHECKPOINT") &&
                checkpoint.schema_identity ==
                    (s180 ? "cpu-prefetch-stage17-s180-capture-checkpoint/1"
                          : "cpu-prefetch-stage17-formal-capture-checkpoint/1") &&
                checkpoint.media_type == "application/json" &&
                checkpoint.file_name == checkpoint_name,
            "archive channel checkpoint binding is malformed");
    peer(channel);
    auto request = protocol::json::canonicalize(Value(Object{
        {"schema_version",
         text(s180 ? "cpu-prefetch-stage17-s180-archive-checkpoint-request/1"
                   : "cpu-prefetch-stage17-archive-checkpoint-request/1")},
        {"request_sha256", text(channel.request_sha256)},
        {"program_scope_sha256", text(channel.program_scope_sha256)},
        {"capture_ordinal", number(limits.ordinal)},
        {"deadline_monotonic_ns", number(limits.deadline_monotonic_ns)},
        {"checkpoint", Value(Object{{"file_name", text(checkpoint.file_name)},
                                    {"size_bytes", number(checkpoint.size_bytes)},
                                    {"sha256", text(checkpoint.sha256)}})}}));
    require(request.has_value(), "archive channel request encoding failed");
    const auto& bytes = request.value();
    require(bytes.size() <= 8192U,
            "archive channel request exceeds fixed packet bound");
    ready(channel.descriptor, {POLLOUT, limits.deadline_monotonic_ns});
    require(::send(channel.descriptor, bytes.data(), bytes.size(),
                   MSG_NOSIGNAL | MSG_DONTWAIT) == static_cast<ssize_t>(bytes.size()),
            "archive checkpoint packet was not sent completely");
    ready(channel.descriptor, {POLLIN, limits.deadline_monotonic_ns});
    std::array<char, 8192U> reply{};
    alignas(cmsghdr) std::array<unsigned char, 256U> ancillary{};
    iovec vector{reply.data(), reply.size()};
    msghdr message{};
    message.msg_iov = &vector;
    message.msg_iovlen = 1U;
    message.msg_control = ancillary.data();
    message.msg_controllen = ancillary.size();
    const auto count =
        ::recvmsg(channel.descriptor, &message, MSG_DONTWAIT | MSG_CMSG_CLOEXEC);
    bool unexpected_control = false;
    for (auto* control = CMSG_FIRSTHDR(&message); control != nullptr;
         control = CMSG_NXTHDR(&message, control)) {
      unexpected_control = true;
      if (control->cmsg_level == SOL_SOCKET && control->cmsg_type == SCM_RIGHTS &&
          control->cmsg_len >= CMSG_LEN(0U)) {
        const auto descriptors = (control->cmsg_len - CMSG_LEN(0U)) / sizeof(int);
        const auto* received = reinterpret_cast<const int*>(CMSG_DATA(control));
        for (std::size_t index = 0U; index < descriptors; ++index)
          static_cast<void>(::close(received[index]));
      }
    }
    require(count > 0 && static_cast<std::size_t>(count) <= reply.size() &&
                (message.msg_flags & (MSG_TRUNC | MSG_CTRUNC)) == 0 &&
                !unexpected_control,
            "archive acknowledgement is empty, oversized or carries descriptors");
    auto parsed = protocol::json::parse(
        std::string_view(reply.data(), static_cast<std::size_t>(count)));
    require(parsed.has_value() && parsed.value().as_object() != nullptr,
            "archive acknowledgement is not an object");
    const auto& response = *parsed.value().as_object();
    input::fields(response, {"schema_version", "request_sha256", "program_scope_sha256",
                             "capture_ordinal", "checkpoint_sha256", "status",
                             "custody_receipt"});
    require(input::text(response, "schema_version") ==
                    (s180 ? "cpu-prefetch-stage17-s180-archive-checkpoint-ack/1"
                          : "cpu-prefetch-stage17-archive-checkpoint-ack/1") &&
                input::text(response, "request_sha256") == channel.request_sha256 &&
                input::text(response, "program_scope_sha256") ==
                    channel.program_scope_sha256 &&
                input::number(response, "capture_ordinal") == limits.ordinal &&
                input::text(response, "checkpoint_sha256") == checkpoint.sha256 &&
                input::text(response, "status") == "ARCHIVED_AND_RELEASED",
            "archive acknowledgement differs from this exact checkpoint");
    const auto& receipt = input::object(response, "custody_receipt");
    input::fields(receipt, {"file_name", "size_bytes", "sha256"});
    require(input::text(receipt, "file_name") == receipt_name &&
                input::number(receipt, "size_bytes") > 0U &&
                hash(input::text(receipt, "sha256")),
            "archive custody receipt binding is malformed");
    peer(channel);
    static_cast<void>(remaining_time(limits.deadline_monotonic_ns));
    return protocol::Result<ArtifactBinding>::success(
        {s180 ? "S180_ARCHIVE_CUSTODY" : "FORMAL_CAPTURE_ARCHIVE_CUSTODY",
         s180 ? "cpu-prefetch-stage17-s180-archive-custody/1"
              : "cpu-prefetch-stage17-formal-archive-custody/1",
         "application/json", input::text(receipt, "file_name"),
         input::number(receipt, "size_bytes"), input::text(receipt, "sha256")});
  } catch (const std::exception& exception) {
    return protocol::Result<ArtifactBinding>::failure(
        {protocol::ErrorCategory::cross_field, "$/formal/archive_channel",
         "S17-ARCHIVE-CHECKPOINT-CHANNEL", exception.what()});
  }
}
} // namespace
auto exchange_formal_archive_checkpoint(const FormalArchiveChannelContext& c,
                                        const ArtifactBinding& b,
                                        FormalArchiveExchangeLimits limits)
    -> protocol::Result<ArtifactBinding> {
  return exchange_checkpoint(c, b, limits, false);
}
auto exchange_s180_archive_checkpoint(const FormalArchiveChannelContext& c,
                                      const ArtifactBinding& b,
                                      FormalArchiveExchangeLimits limits)
    -> protocol::Result<ArtifactBinding> {
  return exchange_checkpoint(c, b, limits, true);
}

} // namespace cpu_prefetch::runner::stage17
