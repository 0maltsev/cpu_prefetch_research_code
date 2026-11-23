// Software-only persistent pipe peer. No hardware/probe backend or production linkage.
#include "cpu_prefetch/protocol/json.hpp"
#include "cpu_prefetch/workload/working_set.hpp"
#include <array>
#include <cstdio>
#include <fcntl.h>
#include <filesystem>
#include <fstream>
#include <span>
#include <stdexcept>
#include <string>
#include <sys/stat.h>
#include <unistd.h>
#include <vector>

namespace {
using namespace cpu_prefetch;
using V = protocol::json::Value;
using O = V::Object;
auto n(std::uint64_t x) -> V {
  return V(protocol::json::Number{protocol::json::Number::Kind::unsigned_integer,
                                  std::to_string(x), x});
}
auto text(const O& o, const char* k) -> std::string { return *o.at(k).as_string(); }
auto encoded(const O& o) -> std::string {
  return protocol::json::canonicalize(V(o)).value();
}
auto digest(const std::string& s) -> std::string {
  return workload::sha256(std::as_bytes(std::span(s.data(), s.size()))).hex();
}
auto parse(const std::string& s) -> O {
  auto value = protocol::json::parse(s);
  if (!value || !value.value().as_object())
    throw std::runtime_error("fixture JSON");
  return *value.value().as_object();
}
auto file(const std::filesystem::path& p) -> std::string {
  std::ifstream input(p);
  return {std::istreambuf_iterator<char>(input), {}};
}
auto bytes(int fd) -> std::string {
  struct stat st{};
  if (::fstat(fd, &st) != 0 || st.st_size <= 0 || st.st_size > 65536)
    throw std::runtime_error("fixture FD");
  std::string s(static_cast<std::size_t>(st.st_size), '\0');
  if (::pread(fd, s.data(), s.size(), 0) != static_cast<ssize_t>(s.size()))
    throw std::runtime_error("fixture read");
  return s;
}
void publish(int fd, const std::filesystem::path& name, const std::string& s) {
  int output = ::openat(fd, name.c_str(),
                        O_CREAT | O_EXCL | O_WRONLY | O_NOFOLLOW | O_CLOEXEC, 0600);
  if (output < 0 ||
      ::write(output, s.data(), s.size()) != static_cast<ssize_t>(s.size()) ||
      ::fsync(output) != 0)
    throw std::runtime_error("fixture publication");
  static_cast<void>(::close(output));
  static_cast<void>(::fsync(fd));
}
void exact_read(int fd, char* data, std::size_t count) {
  while (count) {
    auto got = ::read(fd, data, count);
    if (got <= 0)
      throw std::runtime_error("fixture control EOF");
    data += got;
    count -= static_cast<std::size_t>(got);
  }
}
auto packet(int fd) -> std::string {
  std::array<unsigned char, 4> head{};
  exact_read(fd, reinterpret_cast<char*>(head.data()), 4);
  std::size_t size = 0;
  for (auto b : head)
    size = (size << 8U) | b;
  if (size == 0 || size > 65536)
    throw std::runtime_error("fixture packet bound");
  std::string s(size, '\0');
  exact_read(fd, s.data(), size);
  return s;
}
auto result(int output, const O& request, const std::string& raw, const O& context,
            const std::filesystem::path& templates, bool read,
            const std::string& buffer_hash, std::size_t buffer_size) -> std::string {
  static const std::array names{
      "q15-r-output-v3.json", "q15-r-atomic-layout-raw-v1.json",
      "q15-r-address-residency-raw-v1.json", "q15-r-software-prefetch-raw-v1.json",
      "q15-r-cpu-migration-raw-v1.json"};
  static const std::array roles{"Q15_R_READ_ONLY_PRESTATE", "Q15_R_ATOMIC_LAYOUT_RAW",
                                "Q15_R_ADDRESS_RESIDENCY_RAW",
                                "Q15_R_SOFTWARE_PREFETCH_RAW",
                                "Q15_R_CPU_MIGRATION_RAW"};
  V::Array artifacts;
  const auto& inputs = *request.at("action_inputs").as_object();
  const auto count = read ? names.size() : 1;
  for (std::size_t i = 0; i < count; ++i) {
    const std::string name = read ? names[i] : "q15-w-output-v3.json";
    auto value = parse(file(templates / name));
    for (const auto* key : {"session_id", "qualification_id", "attempt_id",
                            "q15_r_attempt_sha256", "q15_r_result_sha256"})
      if (value.contains(key))
        value[key] = inputs.at(key);
    if (value.contains("authorization_sha256"))
      value["authorization_sha256"] = context.at("authorization_sha256");
    if (read && i == 0) {
      value["buffer_content_sha256"] = V(buffer_hash);
      value["buffer_size_bytes"] = n(buffer_size);
    }
    const auto data = encoded(value);
    publish(output, name, data);
    artifacts.emplace_back(
        O{{"role", V(std::string(read ? roles[i] : "Q15_W_TRANSACTION"))},
          {"schema_identity", value.at("schema_version")},
          {"media_type", V(std::string("application/json"))},
          {"file_name", V(name)},
          {"size_bytes", n(data.size())},
          {"sha256", V(digest(data))}});
  }
  O out{
      {"schema_version", V(std::string("cpu-prefetch-stage17-phase-action-result/4"))},
      {"result_id", V(text(request, "attempt_id") + ":result")},
      {"request_sha256", V(digest(raw))},
      {"authorization_sha256", context.at("authorization_sha256")},
      {"artifacts", V(artifacts)},
      {"started_at_utc", V(std::string("2026-11-23T00:00:00Z"))},
      {"completed_at_utc", V(std::string("2026-11-23T00:00:00Z"))},
      {"duration_ns", n(1)},
      {"terminal_state",
       V(std::string(read ? "Q15_R_READ_ONLY_COMPLETE" : "Q15_W_RESTORED_COMPLETE"))},
      {"restoration_verified", V(!read)},
      {"quarantined", V(false)}};
  for (const auto* key :
       {"request_id", "action_id", "stand_id", "authorization_id", "attempt_id",
        "runtime_binding", "release_binding", "predecessor_resolutions",
        "synthetic_test_only", "phase18_authority"})
    out[key] = request.at(key);
  const auto data = encoded(out);
  publish(output,
          read ? "stage17-q15-r-result-v4.json" : "stage17-q15-w-result-v4.json", data);
  return digest(data);
}
} // namespace

auto main(int argc, char** argv) -> int {
  try {
    if (argc != 11 || std::string_view(argv[1]) != "--execute-stage17-q15-session-v1")
      return 90;
    const int request_fd = std::stoi(argv[3]), context_fd = std::stoi(argv[5]),
              control = std::stoi(argv[7]), output = std::stoi(argv[9]);
    std::array<char, 4096> path{};
    const auto size = ::readlink(("/proc/self/fd/" + std::to_string(output)).c_str(),
                                 path.data(), path.size() - 1);
    if (size <= 0)
      return 91;
    const auto parent =
        std::filesystem::path(std::string(path.data(), static_cast<std::size_t>(size)))
            .parent_path();
    for (int i = 0; !std::filesystem::exists(parent / "compaction/worker-q15.json");
         ++i) {
      if (i > 500)
        return 92;
      static_cast<void>(::usleep(10000));
    }
    auto raw = bytes(request_fd);
    auto request = parse(raw);
    auto context = parse(bytes(context_fd));
    if (text(context, "request_sha256") != digest(raw))
      return 93;
    const auto& platform = *request.at("action_inputs")
                                .as_object()
                                ->at("probe_platform_binding")
                                .as_object();
    const auto llc = std::get<std::uint64_t>(
        platform.at("verified_local_llc_bytes").as_number()->value);
    std::vector<std::byte> buffer(static_cast<std::size_t>(2 * llc), std::byte{0xa5});
    const auto buffer_hash = workload::sha256(buffer).hex();
    const auto address = reinterpret_cast<std::uintptr_t>(buffer.data());
    const auto mode = file(parent / "q15-test-mode");
    if (mode == "console")
      for (int i = 0; i < 1000; ++i)
        static_cast<void>(std::puts("bounded software fixture output"));
    auto hash = result(output, request, raw, context, parent / "q15-fixtures", true,
                       buffer_hash, buffer.size());
    const auto ready =
        encoded(O{{"schema_version",
                   V(std::string("cpu-prefetch-stage17-q15-session-waiting/1"))},
                  {"session_id", request.at("session_id")},
                  {"q15_r_request_sha256", V(digest(raw))},
                  {"q15_r_result_sha256", V(hash)},
                  {"state", V(std::string("H0_SEALED_WAITING_FOR_Q15_W"))},
                  {"same_buffer_retained", V(true)},
                  {"phase18_authority", V(false)}});
    if (mode == "delayed-ready") {
      const int fd = ::openat(output, "stage17-q15-session-waiting-v1.json",
                              O_CREAT | O_EXCL | O_WRONLY | O_CLOEXEC, 0600);
      if (fd < 0)
        return 96;
      std::ofstream(parent / "q15-ready-incomplete") << "not published";
      for (int i = 0; !std::filesystem::exists(parent / "q15-close-publication"); ++i) {
        if (i > 500)
          return 97;
        static_cast<void>(::usleep(10000));
      }
      if (::write(fd, ready.data(), ready.size()) !=
              static_cast<ssize_t>(ready.size()) ||
          ::fsync(fd) != 0)
        return 98;
      static_cast<void>(::close(fd));
      static_cast<void>(::fsync(output));
    } else {
      publish(output, "stage17-q15-session-waiting-v1.json", ready);
    }
    raw = packet(control);
    auto write = parse(raw);
    auto write_context = parse(packet(control));
    if (text(write_context, "request_sha256") != digest(raw) ||
        text(write, "session_id") != text(request, "session_id"))
      return 94;
    std::ofstream(parent / "q15-write-entered") << ::getpid();
    if (mode == "timeout")
      for (;;)
        static_cast<void>(::pause());
    if (mode == "exit-write")
      return 7;
    if (mode == "escape") {
      if (::fork() == 0) {
        static_cast<void>(::setsid());
        static_cast<void>(::close(1));
        static_cast<void>(::close(2));
        for (;;)
          static_cast<void>(::pause());
      }
    }
    if (reinterpret_cast<std::uintptr_t>(buffer.data()) != address ||
        workload::sha256(buffer).hex() != buffer_hash)
      return 95;
    static_cast<void>(result(output, write, raw, write_context, parent / "q15-fixtures",
                             false, buffer_hash, buffer.size()));
    return 0;
  } catch (const std::exception& e) {
    static_cast<void>(std::fprintf(stderr, "Q15 fixture: %s\n", e.what()));
    return 99;
  }
}
