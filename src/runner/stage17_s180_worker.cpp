#include "cpu_prefetch/runner/stage17_s180_worker.hpp"
#include "cpu_prefetch/foundation/repository_info.hpp"
#include "cpu_prefetch/runner/stage17_s180_channel_sink.hpp"
#include "stage17_formal_input_detail.hpp"
#include <cerrno>
#include <charconv>
#include <chrono>
#include <fcntl.h>
#include <fstream>
#include <openssl/evp.h>
#include <set>
#include <sys/stat.h>
#include <unistd.h>

namespace cpu_prefetch::runner::stage17 {
namespace {
using namespace formal_input_detail;
constexpr std::size_t input_limit = std::size_t{16U} * 1024U * 1024U;
constexpr std::size_t context_limit = std::size_t{1024U} * 1024U;
void require(bool b, const char* message) {
  if (!b)
    throw std::invalid_argument(message);
}
auto digest(std::span<const std::byte> bytes) -> std::string {
  return workload::sha256(bytes).hex();
}
auto digest(std::string_view s) -> std::string {
  return digest(std::as_bytes(std::span(s.data(), s.size())));
}
auto canonical(const Object& o) -> std::string {
  auto raw = protocol::json::canonicalize(Value(o));
  require(raw.has_value(), "S180 canonical input is invalid");
  return std::move(raw.value());
}
auto hash(const Object& o, std::string_view key) -> const std::string& {
  const auto& s = text(o, key);
  require(protocol::Sha256::parse(s, "$s180").has_value(),
          "S180 authority hash invalid");
  return s;
}
auto fd(std::string_view s) -> int {
  int value = -1;
  const auto [end, ec] = std::from_chars(s.data(), s.data() + s.size(), value);
  require(ec == std::errc{} && end == s.data() + s.size() && value > 2,
          "S180 inherited descriptor invalid");
  return value;
}
auto descriptor(const Object& o, std::string_view key) -> int {
  const auto value = number(o, key);
  require(value > 2U &&
              value <= static_cast<std::uint64_t>(std::numeric_limits<int>::max()),
          "S180 descriptor out of range");
  return static_cast<int>(value);
}
auto read(int descriptor, std::size_t maximum, bool sealed) -> std::string {
  struct stat before{};
  require(::fstat(descriptor, &before) == 0 && S_ISREG(before.st_mode) &&
              before.st_size > 0 &&
              static_cast<std::uintmax_t>(before.st_size) <= maximum,
          "S180 descriptor is not bounded regular input");
  const auto flags = ::fcntl(descriptor, F_GETFL);
  require(flags >= 0 && (flags & O_ACCMODE) == O_RDONLY, "S180 input is not read-only");
  if (sealed) {
    constexpr auto required = F_SEAL_WRITE | F_SEAL_GROW | F_SEAL_SHRINK | F_SEAL_SEAL;
    const auto seals = ::fcntl(descriptor, F_GET_SEALS);
    require(seals >= 0 && (seals & required) == required,
            "S180 input lacks immutable seals");
  }
  std::string raw(static_cast<std::size_t>(before.st_size), '\0');
  std::size_t offset = 0U;
  while (offset < raw.size()) {
    const auto count = ::pread(descriptor, raw.data() + offset, raw.size() - offset,
                               static_cast<off_t>(offset));
    require(count > 0, "S180 descriptor read failed");
    offset += static_cast<std::size_t>(count);
  }
  struct stat after{};
  require(::fstat(descriptor, &after) == 0 && after.st_dev == before.st_dev &&
              after.st_ino == before.st_ino && after.st_size == before.st_size &&
              after.st_mtim.tv_sec == before.st_mtim.tv_sec &&
              after.st_mtim.tv_nsec == before.st_mtim.tv_nsec,
          "S180 input changed during read");
  return raw;
}
auto parse(const std::string& raw) -> Object {
  auto doc = protocol::json::parse(raw);
  require(doc && doc.value().as_object(), "S180 input must be a JSON object");
  return *doc.value().as_object();
}
auto now() -> std::uint64_t {
  const auto value = std::chrono::duration_cast<std::chrono::nanoseconds>(
                         std::chrono::steady_clock::now().time_since_epoch())
                         .count();
  require(value >= 0, "S180 monotonic clock unavailable");
  return static_cast<std::uint64_t>(value);
}
auto boot_id() -> std::string {
  std::ifstream f("/proc/sys/kernel/random/boot_id");
  std::string value;
  require(static_cast<bool>(std::getline(f, value)) && value.size() == 36U,
          "S180 actual boot identity unavailable");
  return value;
}
void boolean(const Object& o, std::string_view key, bool expected) {
  const auto* b = member(o, key).as_bool();
  require(b && *b == expected, "S180 boolean scope/backend differs");
}
class DirectoryOutput final : public ArtifactSink {
public:
  explicit DirectoryOutput(int fd) : directory_(fd) {}
  auto publish(ArtifactPayload a) -> protocol::Result<ArtifactBinding> override {
    try {
      require(!a.file_name.empty() && a.file_name != "." && a.file_name != ".." &&
                  a.file_name.find('/') == std::string::npos &&
                  a.file_name.find('\0') == std::string::npos,
              "S180 fixed output name invalid");
      const auto d = digest(a.bytes);
      const auto out =
          ::openat(directory_, a.file_name.c_str(),
                   O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0600);
      require(out >= 0, "S180 original output already exists or cannot be created");
      try {
        std::size_t offset = 0U;
        while (offset < a.bytes.size()) {
          const auto count =
              ::write(out, a.bytes.data() + offset, a.bytes.size() - offset);
          require(count > 0, "S180 original output write failed");
          offset += static_cast<std::size_t>(count);
        }
        require(::fsync(out) == 0, "S180 original output fsync failed");
      } catch (...) {
        static_cast<void>(::close(out));
        throw;
      }
      require(::close(out) == 0 && ::fsync(directory_) == 0,
              "S180 output publication durability failed");
      return protocol::Result<ArtifactBinding>::success(
          {std::move(a.role), std::move(a.schema_identity), std::move(a.media_type),
           std::move(a.file_name), a.bytes.size(), d});
    } catch (const std::exception& e) {
      return protocol::Result<ArtifactBinding>::failure(
          {protocol::ErrorCategory::cross_field, "$s180/output",
           "S17-S180-WORKER-OUTPUT", e.what()});
    }
  }

private:
  int directory_;
};
class WorkerSink final : public S180ArchiveSink {
public:
  WorkerSink(int directory, FormalArchiveChannelContext context,
             std::array<std::uint64_t, 180U> intervals, std::uint64_t bound)
      : output_(directory), channel_(output_, std::move(context), intervals, bound),
        directory_(directory), bound_(bound) {}
  auto publish(ArtifactPayload a) -> protocol::Result<ArtifactBinding> override {
    return channel_.publish(std::move(a));
  }
  auto has_archive_checkpoint() const noexcept -> bool override {
    return !failed_ && channel_.has_archive_checkpoint();
  }
  auto s180_program_scope_sha256() const noexcept -> std::string_view override {
    return channel_.s180_program_scope_sha256();
  }
  auto archive_checkpoint(const ArtifactBinding& b, std::uint64_t deadline)
      -> protocol::Result<ArtifactBinding> override {
    try {
      require(!failed_, "S180 worker custody channel has stopped");
      auto result = channel_.archive_checkpoint(b, deadline);
      if (!result) {
        failed_ = true;
        return result;
      }
      const auto& ref = result.value();
      require(ref.size_bytes <= bound_ &&
                  bound_ <= std::numeric_limits<std::size_t>::max(),
              "S180 custody byte bound differs");
      const auto handle = ::openat(directory_, ref.file_name.c_str(),
                                   O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
      require(handle >= 0, "S180 ACK lacks durable custody receipt");
      std::string raw;
      try {
        raw = read(handle, static_cast<std::size_t>(bound_), false);
      } catch (...) {
        static_cast<void>(::close(handle));
        throw;
      }
      require(::close(handle) == 0 && raw.size() == ref.size_bytes &&
                  digest(raw) == ref.sha256 && now() < deadline,
              "S180 durable custody bytes or deadline differ from ACK");
      return result;
    } catch (const std::exception& e) {
      failed_ = true;
      return protocol::Result<ArtifactBinding>::failure(
          {protocol::ErrorCategory::cross_field, "$s180/custody",
           "S17-S180-WORKER-CUSTODY", e.what()});
    }
  }

private:
  DirectoryOutput output_;
  S180ChannelSink channel_;
  int directory_;
  std::uint64_t bound_;
  bool failed_{false};
};
auto text_value(std::string_view s) -> Value { return Value(std::string(s)); }
auto number_value(std::uint64_t v) -> Value {
  return Value(protocol::json::Number{protocol::json::Number::Kind::unsigned_integer,
                                      std::to_string(v), v});
}
} // namespace
auto inspect_s180_executable() -> protocol::Result<S180ExecutableIdentity> {
  auto handle = ::open("/proc/self/exe", O_RDONLY | O_CLOEXEC);
  try {
    struct stat before{};
    require(handle >= 0 && ::fstat(handle, &before) == 0 && S_ISREG(before.st_mode) &&
                before.st_size > 0 &&
                static_cast<std::uintmax_t>(before.st_size) <=
                    std::uintmax_t{256U} * 1024U * 1024U,
            "S180 executable extent is invalid");
    std::unique_ptr<EVP_MD_CTX, decltype(&EVP_MD_CTX_free)> ctx(EVP_MD_CTX_new(),
                                                                &EVP_MD_CTX_free);
    require(ctx && EVP_DigestInit_ex(ctx.get(), EVP_sha256(), nullptr) == 1,
            "S180 executable hash initialization failed");
    std::array<char, 65536U> block{};
    std::uint64_t count = 0U;
    for (;;) {
      const auto amount = ::read(handle, block.data(), block.size());
      if (amount < 0 && errno == EINTR)
        continue;
      require(amount >= 0, "S180 executable read failed");
      if (amount == 0)
        break;
      count += static_cast<std::uint64_t>(amount);
      require(count <= static_cast<std::uint64_t>(before.st_size) &&
                  EVP_DigestUpdate(ctx.get(), block.data(),
                                   static_cast<std::size_t>(amount)) == 1,
              "S180 executable changed or hash update failed");
    }
    struct stat after{};
    require(::fstat(handle, &after) == 0 && after.st_dev == before.st_dev &&
                after.st_ino == before.st_ino && after.st_size == before.st_size &&
                after.st_mtim.tv_sec == before.st_mtim.tv_sec &&
                after.st_mtim.tv_nsec == before.st_mtim.tv_nsec &&
                count == static_cast<std::uint64_t>(before.st_size),
            "S180 executable identity changed during hashing");
    std::array<unsigned char, EVP_MAX_MD_SIZE> bytes{};
    unsigned int length = 0U;
    require(EVP_DigestFinal_ex(ctx.get(), bytes.data(), &length) == 1 && length == 32U,
            "S180 executable final hash failed");
    std::string sha;
    constexpr std::string_view hex = "0123456789abcdef";
    for (unsigned int i = 0U; i < length; ++i) {
      sha.push_back(hex[bytes[i] >> 4U]);
      sha.push_back(hex[bytes[i] & 15U]);
    }
    const auto closed = ::close(handle);
    handle = -1;
    require(closed == 0, "S180 executable close failed");
    return protocol::Result<S180ExecutableIdentity>::success({std::move(sha), count});
  } catch (const std::exception& e) {
    if (handle >= 0)
      static_cast<void>(::close(handle));
    return protocol::Result<S180ExecutableIdentity>::failure(
        {protocol::ErrorCategory::cross_field, "$s180/runtime", "S17-S180-EXECUTABLE",
         e.what()});
  }
}
auto LinuxS180WorkerOperations::execute(const S180SessionInput& input,
                                        const S180SessionAuthority& authority,
                                        S180ArchiveSink& sink)
    -> protocol::Result<ActionOutcome> {
  return run_native_s180_session(input, authority, sink);
}

auto s180_epoch_authority_covers_window(S180EpochWindow w) noexcept -> bool {
  if (w.remaining_monotonic_ns == 0U ||
      w.issued_at_epoch_seconds > w.observed_epoch_seconds ||
      w.observed_epoch_seconds >= w.expires_at_epoch_seconds)
    return false;
  const auto seconds = w.remaining_monotonic_ns / 1'000'000'000U +
                       (w.remaining_monotonic_ns % 1'000'000'000U != 0U ? 1U : 0U);
  return seconds < w.expires_at_epoch_seconds - w.observed_epoch_seconds;
}
auto run_s180_session_worker(int argc, char** argv, S180WorkerOperations& operations)
    -> int {
  require(argc == 9 &&
              std::string_view(argv[1]) == "--execute-stage17-s180-session-v1" &&
              std::string_view(argv[2]) == "--request-fd" &&
              std::string_view(argv[4]) == "--context-fd" &&
              std::string_view(argv[6]) == "--output-dir-fd" &&
              std::string_view(argv[8]) == "--fixed-dispatch-end",
          "S180 internal argv contract differs");
  const auto request_fd = fd(argv[3]), context_fd = fd(argv[5]),
             output_fd = fd(argv[7]);
  require(std::set<int>{request_fd, context_fd, output_fd}.size() == 3U,
          "S180 inherited descriptors alias");
  struct stat directory{};
  require(::fstat(output_fd, &directory) == 0 && S_ISDIR(directory.st_mode) &&
              directory.st_uid == ::geteuid() && (directory.st_mode & 0022) == 0,
          "S180 output root is unsafe");
  const auto request_raw = read(request_fd, input_limit, true),
             context_raw = read(context_fd, context_limit, true);
  const auto request = parse(request_raw), context = parse(context_raw);
  fields(request,
         {"schema_version", "session_id", "request_id", "attempt_id",
          "authorization_id", "stand_id", "plan", "runtime_binding", "release_binding",
          "prerequisite_bindings", "synthetic_test_only", "phase18_authority"});
  fields(context, {"schema_version",
                   "session_id",
                   "request_id",
                   "attempt_id",
                   "authorization_id",
                   "authorization_sha256",
                   "request_sha256",
                   "plan_sha256",
                   "runtime_sha256",
                   "release_sha256",
                   "prerequisite_bindings",
                   "readiness_scope",
                   "issued_at_epoch_seconds",
                   "expires_at_epoch_seconds",
                   "window_start_monotonic_ns",
                   "window_end_monotonic_ns",
                   "schedule_source_context",
                   "archive_channel",
                   "output_directory",
                   "boot_id",
                   "synthetic_test_only",
                   "phase18_authority"});
  require(text(request, "schema_version") ==
                  "cpu-prefetch-stage17-s180-session-request/1" &&
              text(context, "schema_version") ==
                  "cpu-prefetch-stage17-s180-session-context/1" &&
              text(context, "readiness_scope") == "D310-S180-SCOPED-READY-v1",
          "S180 scoped context version/readiness differs");
  for (const auto key : {"session_id", "request_id", "attempt_id", "authorization_id"})
    require(opaque_text(request, key) == opaque_text(context, key),
            "S180 authority/request identity differs");
  static_cast<void>(hash(context, "authorization_sha256"));
  require(hash(context, "request_sha256") == digest(request_raw),
          "S180 original request hash differs");
  boolean(request, "synthetic_test_only", operations.synthetic_test_only());
  boolean(context, "synthetic_test_only", operations.synthetic_test_only());
  boolean(request, "phase18_authority", false);
  boolean(context, "phase18_authority", false);
  const auto& plan = object(request, "plan");
  const auto& blueprint = object(plan, "blueprint");
  require(text(request, "stand_id") == text(blueprint, "stand_id") &&
              hash(context, "plan_sha256") == digest(canonical(plan)),
          "S180 stand or exact plan binding differs");
  const auto& runtime = object(request, "runtime_binding");
  fields(runtime, {"role", "profile", "sha256", "size_bytes"});
  const auto& release = object(request, "release_binding");
  fields(release, {"source_revision", "worker_sha256"});
  const auto executable = inspect_s180_executable();
  require(executable && text(runtime, "role") == kS180WorkerRole &&
              text(runtime, "profile") == kS180WorkerProfile &&
              hash(runtime, "sha256") == executable.value().sha256 &&
              number(runtime, "size_bytes") == executable.value().size_bytes &&
              hash(release, "worker_sha256") == executable.value().sha256 &&
              hash(context, "runtime_sha256") == executable.value().sha256 &&
              hash(context, "release_sha256") == executable.value().sha256,
          "S180 actual executable differs from admission");
  const auto source = foundation::repository_info();
  require((operations.synthetic_test_only() || !source.source_dirty) &&
              text(release, "source_revision") == source.source_revision &&
              text(plan, "source_revision") == source.source_revision,
          "S180 requires exact clean release source");
  const auto& prereq = object(request, "prerequisite_bindings");
  fields(prereq, {"calibration_freeze_sha256", "ext007_resolution_sha256",
                  "ext008_resolution_sha256", "ext009_resolution_sha256",
                  "ext010_authorization_sha256", "qualification_sha256",
                  "compatibility_sha256", "runtime_profile_sha256"});
  for (const auto& [key, value] : prereq) {
    static_cast<void>(value);
    static_cast<void>(hash(prereq, key));
  }
  require(canonical(prereq) == canonical(object(context, "prerequisite_bindings")) &&
              hash(prereq, "calibration_freeze_sha256") ==
                  hash(object(blueprint, "calibration_freeze"), "sha256") &&
              hash(prereq, "ext007_resolution_sha256") ==
                  hash(object(blueprint, "ext007_resolution"), "sha256") &&
              hash(prereq, "ext010_authorization_sha256") ==
                  hash(context, "authorization_sha256"),
          "S180 scoped prerequisite lineage differs");
  require(text(context, "boot_id") == boot_id(),
          "S180 operational window belongs to another boot");
  const auto& root = object(context, "output_directory");
  fields(root, {"device", "inode"});
  require(number(root, "device") == static_cast<std::uint64_t>(directory.st_dev) &&
              number(root, "inode") == static_cast<std::uint64_t>(directory.st_ino),
          "S180 output root differs from parent admission");
  const auto& channel = object(context, "archive_channel");
  fields(channel, {"descriptor", "controller_pid", "program_scope_sha256"});
  const auto channel_fd = descriptor(channel, "descriptor");
  const std::array<int, 4U> reserved{request_fd, context_fd, output_fd, channel_fd};
  require(std::set<int>(reserved.begin(), reserved.end()).size() == 4U &&
              number(channel, "controller_pid") ==
                  static_cast<std::uint64_t>(::getppid()),
          "S180 archive peer or reserved descriptors differ");
  const auto parsed = parse_s180_session_input(
      plan, object(context, "schedule_source_context"), reserved);
  require(parsed.has_value(),
          parsed ? "S180 input accepted" : parsed.errors().front().message.c_str());
  const auto input = parsed.value().input();
  const auto shape = validate_s180_session(input);
  require(shape.has_value(), "S180 native family validation failed");
  const auto& storage = object(plan, "storage");
  require(hash(channel, "program_scope_sha256") ==
              hash(storage, "program_scope_sha256"),
          "S180 archive program scope differs");
  S180SessionAuthority authority{opaque_text(request, "session_id"),
                                 hash(context, "plan_sha256"),
                                 hash(channel, "program_scope_sha256"),
                                 number(context, "window_start_monotonic_ns"),
                                 number(context, "window_end_monotonic_ns")};
  const auto current = now();
  const auto epoch_signed = std::chrono::duration_cast<std::chrono::seconds>(
                                std::chrono::system_clock::now().time_since_epoch())
                                .count();
  require(epoch_signed >= 0, "S180 epoch clock unavailable");
  const auto epoch = static_cast<std::uint64_t>(epoch_signed);
  require(
      authority.window_end_monotonic_ns > authority.window_start_monotonic_ns &&
          authority.window_end_monotonic_ns - authority.window_start_monotonic_ns ==
              kS180OperationalCapNs &&
          current >= authority.window_start_monotonic_ns &&
          current < authority.window_end_monotonic_ns &&
          shape.value().watchdog_ns <= authority.window_end_monotonic_ns - current &&
          input.sources.deadline_monotonic_ns > current &&
          input.sources.deadline_monotonic_ns <= authority.window_end_monotonic_ns &&
          input.sources.deadline_monotonic_ns - current <= input.setup_ns,
      "S180 operational/source window is expired or inadequate");
  const auto remaining = authority.window_end_monotonic_ns - current;
  require(s180_epoch_authority_covers_window(
              {number(context, "issued_at_epoch_seconds"),
               number(context, "expires_at_epoch_seconds"), epoch, remaining}),
          "S180 authority is future, expired or ends before the operational window");
  std::array<std::uint64_t, 180U> intervals{};
  for (std::size_t i = 0U; i < 180U; ++i)
    intervals[i] = input.captures[i].archive_ns;
  WorkerSink sink(output_fd,
                  {channel_fd, static_cast<int>(::getppid()), digest(request_raw),
                   authority.program_scope_sha256},
                  intervals, number(storage, "maximum_custody_receipt_bytes"));
  const auto marker = canonical(Object{
      {"schema_version", text_value("cpu-prefetch-stage17-s180-session-entry/1")},
      {"session_id", text_value(authority.session_id)},
      {"request_sha256", text_value(digest(request_raw))},
      {"plan_sha256", text_value(authority.plan_sha256)},
      {"authorization_sha256", text_value(hash(context, "authorization_sha256"))},
      {"prerequisite_bindings", Value(prereq)},
      {"source_revision", text_value(input.source_revision)},
      {"runtime_sha256", text_value(executable.value().sha256)},
      {"boot_id", text_value(text(context, "boot_id"))},
      {"window_start_monotonic_ns", number_value(authority.window_start_monotonic_ns)},
      {"window_end_monotonic_ns", number_value(authority.window_end_monotonic_ns)},
      {"synthetic_test_only", Value(operations.synthetic_test_only())},
      {"execution_authority", Value(false)},
      {"phase18_authority", Value(false)}});
  require(marker.size() <= number(object(plan, "budget"), "entry_metadata_bytes"),
          "S180 entry marker exceeds reserved metadata");
  const auto bytes = std::as_bytes(std::span(marker.data(), marker.size()));
  const auto written = sink.publish({"S180_SESSION_ENTRY",
                                     "cpu-prefetch-stage17-s180-session-entry/1",
                                     "application/json",
                                     "s180-session-entry.json",
                                     {bytes.begin(), bytes.end()}});
  require(written.has_value(), "S180 entry marker could not be published once");
  const auto outcome = operations.execute(input, authority, sink);
  require(outcome.has_value(), "S180 session execution failed closed");
  return outcome.value().terminal_state == "S180_PILOT_FAMILY_COMPLETED" &&
                 outcome.value().restoration_verified && !outcome.value().quarantined
             ? 0
             : 1;
}
} // namespace cpu_prefetch::runner::stage17
