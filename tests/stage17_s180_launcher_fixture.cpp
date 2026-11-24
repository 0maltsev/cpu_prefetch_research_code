// Test-only owned-process endpoint. Never linked into the production worker.
#include "cpu_prefetch/foundation/repository_info.hpp"
#include "cpu_prefetch/runner/stage17_s180_channel_sink.hpp"
#include "cpu_prefetch/runner/stage17_s180_input.hpp"
#include "cpu_prefetch/runner/stage17_s180_worker.hpp"
#include "cpu_prefetch/workload/working_set.hpp"
#include <array>
#include <charconv>
#include <chrono>
#include <csignal>
#include <cstdio>
#include <fcntl.h>
#include <stdexcept>
#include <sys/stat.h>
#include <unistd.h>

namespace {
using namespace cpu_prefetch;
using namespace runner::stage17;
using V = protocol::json::Value;
using O = V::Object;
auto number(const O& o, const char* k) -> std::uint64_t {
  return std::get<std::uint64_t>(o.at(k).as_number()->value);
}
auto text(const O& o, const char* k) -> std::string { return *o.at(k).as_string(); }
auto n(std::uint64_t x) -> V {
  return V(protocol::json::Number{protocol::json::Number::Kind::unsigned_integer,
                                  std::to_string(x), x});
}
auto read(int fd, std::size_t maximum) -> std::string {
  struct stat st{};
  if (::fstat(fd, &st) != 0 || st.st_size <= 0 ||
      static_cast<std::uint64_t>(st.st_size) > maximum)
    throw std::runtime_error("fixture input extent");
  std::string raw(static_cast<std::size_t>(st.st_size), '\0');
  if (::pread(fd, raw.data(), raw.size(), 0) != static_cast<ssize_t>(raw.size()))
    throw std::runtime_error("fixture input read");
  return raw;
}
auto parse(const std::string& raw) -> O {
  auto v = protocol::json::parse(raw);
  if (!v || !v.value().as_object())
    throw std::runtime_error("fixture JSON");
  return *v.value().as_object();
}
void write(int directory, const char* name, const std::string& raw) {
  auto fd = ::openat(directory, name,
                     O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC | O_NOFOLLOW, 0600);
  if (fd < 0 ||
      ::write(fd, raw.data(), raw.size()) != static_cast<ssize_t>(raw.size()) ||
      ::fsync(fd) != 0)
    throw std::runtime_error("fixture publication");
  static_cast<void>(::close(fd));
}
struct NoOutput final : ArtifactSink {
  auto publish(ArtifactPayload) -> protocol::Result<ArtifactBinding> override {
    throw std::logic_error("test uses existing synthetic checkpoint");
  }
};
} // namespace
auto main(int argc, char** argv) -> int {
  try {
    if (argc == 2 &&
        std::string_view(argv[1]) == "--stage17-s180-runtime-identity-v1") {
      const auto image = inspect_s180_executable();
      if (!image)
        throw std::runtime_error("fixture image");
      auto raw = protocol::json::canonicalize(
          V(O{{"role", V(std::string(kS180WorkerRole))},
              {"profile", V(std::string(kS180WorkerProfile))},
              {"sha256", V(image.value().sha256)},
              {"size_bytes", n(image.value().size_bytes)},
              {"source_revision",
               V(std::string(foundation::repository_info().source_revision))},
              {"source_dirty", V(true)},
              {"synthetic_test_only", V(true)},
              {"execution_authority", V(false)},
              {"phase18_authority", V(false)}}));
      static_cast<void>(std::puts(raw.value().c_str()));
      return 0;
    }
    if (argc != 9 || std::string_view(argv[1]) != "--execute-stage17-s180-session-v1" ||
        std::string_view(argv[2]) != "--request-fd" ||
        std::string_view(argv[4]) != "--context-fd" ||
        std::string_view(argv[6]) != "--output-dir-fd" ||
        std::string_view(argv[8]) != "--fixed-dispatch-end")
      throw std::runtime_error("fixture fixed argv");
    auto fd = [](const char* s) {
      int v{};
      auto r = std::from_chars(s, s + std::char_traits<char>::length(s), v);
      if (r.ec != std::errc{})
        throw std::runtime_error("fixture fd");
      return v;
    };
    const auto request_fd = fd(argv[3]), context_fd = fd(argv[5]),
               directory = fd(argv[7]);
    constexpr int seals = F_SEAL_WRITE | F_SEAL_GROW | F_SEAL_SHRINK | F_SEAL_SEAL;
    if ((::fcntl(request_fd, F_GET_SEALS) & seals) != seals ||
        (::fcntl(context_fd, F_GET_SEALS) & seals) != seals)
      throw std::runtime_error("fixture unsealed request/context");
    const auto raw = read(request_fd, std::size_t{16U} * std::size_t{1024U} * 1024U);
    const auto request = parse(raw),
               context = parse(read(context_fd, std::size_t{1024U} * 1024U));
    const auto& source = *context.at("schedule_source_context").as_object();
    const auto channel = static_cast<int>(
        number(*context.at("archive_channel").as_object(), "descriptor"));
    const std::array<int, 4U> reserved{request_fd, context_fd, directory, channel};
    auto input =
        parse_s180_session_input(*request.at("plan").as_object(), source, reserved);
    if (!input)
      throw std::runtime_error(input.errors().front().message);
    const auto& bindings = *source.at("bindings").as_array();
    if (bindings.size() != 36U)
      throw std::runtime_error("fixture source count");
    for (const auto& value : bindings) {
      const auto& b = *value.as_object();
      const auto source_fd = static_cast<int>(number(b, "descriptor"));
      const auto bytes = read(source_fd, std::size_t{1024U} * 1024U);
      if (workload::sha256(std::as_bytes(std::span(bytes.data(), bytes.size())))
              .hex() != text(b, "canonical_sha256"))
        throw std::runtime_error("fixture source hash");
    }
    write(directory, "software-launcher-started.txt", "36 sealed sources read\n");
    const auto mode = text(request, "session_id");
    if (mode == "software-launcher-interrupt") {
      static_cast<void>(::kill(::getppid(), SIGTERM));
      for (;;)
        ::pause();
    }
    if (mode == "software-launcher-spam") {
      std::array<char, 65536U> noise{};
      for (;;)
        static_cast<void>(::write(STDOUT_FILENO, noise.data(), noise.size()));
    }
    if (mode == "software-launcher-descendant") {
      auto child = ::fork();
      if (child < 0)
        throw std::runtime_error("fixture fork");
      if (child == 0) {
        static_cast<void>(::setsid());
        for (;;)
          ::pause();
      }
      return 23;
    }
    if (mode == "software-launcher-exit") {
      static_cast<void>(std::puts("test-only early exit"));
      return 23;
    }
    if (mode == "software-launcher-stop") {
      const auto checkpoint_fd = ::openat(directory, "s180-e0-checkpoint.json",
                                          O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
      if (checkpoint_fd < 0)
        throw std::runtime_error("fixture checkpoint");
      const auto checkpoint_raw = read(checkpoint_fd, 131072U);
      static_cast<void>(::close(checkpoint_fd));
      ArtifactBinding checkpoint{
          "S180_CAPTURE_CHECKPOINT",
          "cpu-prefetch-stage17-s180-capture-checkpoint/1",
          "application/json",
          "s180-e0-checkpoint.json",
          checkpoint_raw.size(),
          workload::sha256(
              std::as_bytes(std::span(checkpoint_raw.data(), checkpoint_raw.size())))
              .hex()};
      NoOutput output;
      std::array<std::uint64_t, 180U> intervals{};
      intervals.fill(90'000'000'000U);
      S180ChannelSink sink(
          output,
          {channel, static_cast<int>(::getppid()), text(context, "request_sha256"),
           text(*context.at("archive_channel").as_object(), "program_scope_sha256")},
          intervals, 131072U);
      const auto now = std::chrono::steady_clock::now().time_since_epoch();
      const auto deadline =
          static_cast<std::uint64_t>(
              std::chrono::duration_cast<std::chrono::nanoseconds>(now).count()) +
          90'000'000'000U;
      FormalArchiveDeadline guard({deadline});
      const auto result = sink.archive_checkpoint(checkpoint, deadline);
      if (result)
        throw std::runtime_error("fixture failed capture received normal ACK");
      ::usleep(50000U);
      write(directory, "software-launcher-native-restored.txt",
            "test-only normal stop finalization\n");
      return 2;
    }
    throw std::runtime_error("fixture unknown software case");
  } catch (const std::exception& e) {
    static_cast<void>(std::fprintf(stderr, "%s\n", e.what()));
    return 1;
  }
}
