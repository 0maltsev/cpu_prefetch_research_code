#include "cpu_prefetch/protocol/json.hpp"
#include "cpu_prefetch/storage/post_measure_archive.hpp"
#include "cpu_prefetch/workload/deterministic.hpp"

#include <array>
#include <charconv>
#include <dlfcn.h>
#include <fcntl.h>
#include <iostream>
#include <limits>
#include <memory>
#include <openssl/evp.h>
#include <set>
#include <stdexcept>
#include <sys/resource.h>
#include <unistd.h>
#include <vector>
#include <zstd.h>

namespace {
namespace storage = cpu_prefetch::storage;
namespace json = cpu_prefetch::protocol::json;
using Json = json::Value;
void require(bool condition, const char* message) {
  if (!condition) {
    throw std::runtime_error(message);
  }
}
auto unsigned_value(const Json& value) -> std::uint64_t {
  const auto* number = value.as_number();
  require(number != nullptr && number->kind == json::Number::Kind::unsigned_integer,
          "archive plan exact unsigned integer required");
  return std::get<std::uint64_t>(number->value);
}
auto text_value(const Json& value) -> const std::string& {
  require(value.as_string() != nullptr, "archive plan string required");
  return *value.as_string();
}
auto optional_text(const Json& value) -> std::optional<std::string> {
  return value.is_null() ? std::nullopt : std::optional(text_value(value));
}
auto optional_uint(const Json& value) -> std::optional<std::uint64_t> {
  return value.is_null() ? std::nullopt : std::optional(unsigned_value(value));
}
auto object(const Json& value, std::initializer_list<std::string_view> keys)
    -> const Json::Object& {
  require(value.as_object() != nullptr && value.as_object()->size() == keys.size(),
          "archive plan field count");
  for (auto key : keys) {
    require(value.as_object()->contains(key), "archive plan missing field");
  }
  return *value.as_object();
}
auto parse_plan(std::string_view input) -> storage::ArchivePlan {
  auto parsed = json::parse(input);
  require(static_cast<bool>(parsed), "archive plan JSON parse");
  auto canonical = json::canonicalize(parsed.value());
  require(canonical && canonical.value() == input,
          "archive plan must be canonical JCS-I64 without LF");
  const auto& root = object(parsed.value(), {"identity", "limits"});
  const auto& id =
      object(root.at("identity"),
             {"artifact_id", "artifact_role", "canonical_format", "run_id", "phase",
              "worker", "canonical_size_bytes", "canonical_sha256", "codec_id",
              "row_bytes", "fallback_reason", "implementation_profile_sha256",
              "encoder_sha256", "zstd_library_sha256"});
  const auto& limits =
      object(root.at("limits"),
             {"window_log", "maximum_header_bytes", "maximum_decoded_block_bytes",
              "maximum_encoded_block_bytes", "maximum_archive_bytes",
              "maximum_observed_context_bytes", "io_chunk_bytes", "maximum_io_calls",
              "deadline_monotonic_ns"});
  const auto& codec = text_value(id.at("codec_id"));
  require(codec == storage::kArchiveRowCodec || codec == storage::kArchiveByteCodec,
          "archive codec not accepted");
  const auto window = unsigned_value(limits.at("window_log"));
  require(window <= 31U, "archive window range");
  return {{text_value(id.at("artifact_id")), text_value(id.at("artifact_role")),
           text_value(id.at("canonical_format")), optional_text(id.at("run_id")),
           optional_text(id.at("phase")), optional_text(id.at("worker")),
           unsigned_value(id.at("canonical_size_bytes")),
           text_value(id.at("canonical_sha256")),
           codec == storage::kArchiveRowCodec ? storage::ArchiveCodec::rows
                                              : storage::ArchiveCodec::bytes,
           optional_uint(id.at("row_bytes")), optional_text(id.at("fallback_reason")),
           text_value(id.at("implementation_profile_sha256")),
           text_value(id.at("encoder_sha256")),
           text_value(id.at("zstd_library_sha256"))},
          {static_cast<int>(window), unsigned_value(limits.at("maximum_header_bytes")),
           unsigned_value(limits.at("maximum_decoded_block_bytes")),
           unsigned_value(limits.at("maximum_encoded_block_bytes")),
           unsigned_value(limits.at("maximum_archive_bytes")),
           unsigned_value(limits.at("maximum_observed_context_bytes")),
           unsigned_value(limits.at("io_chunk_bytes")),
           unsigned_value(limits.at("maximum_io_calls")),
           unsigned_value(limits.at("deadline_monotonic_ns"))}};
}
struct Arguments final {
  int source;
  int archive;
  int plan;
  int result;
  std::size_t plan_limit;
  std::size_t result_limit;
};
auto arguments(int argc, char** argv) -> Arguments {
  require(argc == 14 && std::string_view(argv[1]) == "--encode-stage17-archive-v1",
          "archive encoder requires versioned fd-only arguments");
  std::array<std::uint64_t, 6> values{};
  constexpr std::array names{"--source-fd", "--archive-fd",      "--plan-fd",
                             "--result-fd", "--plan-byte-limit", "--result-byte-limit"};
  for (std::size_t index = 0U; index < names.size(); ++index) {
    require(std::string_view(argv[2U + index * 2U]) == names[index],
            "archive encoder argument order/name");
    const std::string_view value(argv[3U + index * 2U]);
    const auto parsed =
        std::from_chars(value.data(), value.data() + value.size(), values[index]);
    require(parsed.ec == std::errc{} && parsed.ptr == value.data() + value.size(),
            "archive encoder numeric argument");
    require(index >= 4U ? values[index] > 0U &&
                              values[index] <= std::numeric_limits<std::size_t>::max()
                        : values[index] <= static_cast<std::uint64_t>(
                                               std::numeric_limits<int>::max()),
            "archive encoder argument bounds");
  }
  const std::set<std::uint64_t> descriptors(values.begin(), values.begin() + 4);
  require(descriptors.size() == 4U, "archive encoder descriptors alias");
  return {static_cast<int>(values[0]),         static_cast<int>(values[1]),
          static_cast<int>(values[2]),         static_cast<int>(values[3]),
          static_cast<std::size_t>(values[4]), static_cast<std::size_t>(values[5])};
}
void time_check(storage::LinuxArchiveFileOperations& operations,
                const storage::ArchiveLimits& limits) {
  const auto now = operations.clock();
  require(now.call.return_value == 0 && now.monotonic_ns < limits.deadline_monotonic_ns,
          "archive dependency deadline/clock");
}
// Only two source-qualified runtime images are opened cold. Their supplied
// profile hashes are checked against the actual running executable/library.
auto hash_dependency(const char* path, const storage::ArchiveLimits& limits,
                     storage::LinuxArchiveFileOperations& operations) -> std::string {
  const int descriptor = ::open(path, O_RDONLY | O_CLOEXEC);
  require(descriptor >= 0, "archive dependency open");
  struct Close final {
    int fd;
    ~Close() { static_cast<void>(::close(fd)); }
  } close{descriptor};
  const auto before = operations.inspect(descriptor);
  require(before.stat_call.return_value == 0 && before.regular,
          "archive dependency regular file");
  std::unique_ptr<EVP_MD_CTX, decltype(&EVP_MD_CTX_free)> digest(EVP_MD_CTX_new(),
                                                                 EVP_MD_CTX_free);
  require(digest && EVP_DigestInit_ex(digest.get(), EVP_sha256(), nullptr) == 1,
          "archive dependency digest init");
  std::vector<std::byte> buffer(
      static_cast<std::size_t>(std::min(limits.io_chunk_bytes, before.size_bytes)));
  std::uint64_t offset = 0U;
  std::uint64_t calls = 0U;
  while (offset < before.size_bytes) {
    time_check(operations, limits);
    require(calls++ < limits.maximum_io_calls, "archive dependency I/O budget");
    auto block = std::span(buffer).first(static_cast<std::size_t>(
        std::min<std::uint64_t>(buffer.size(), before.size_bytes - offset)));
    const auto read = operations.read(descriptor, block, offset);
    require(read.return_value > 0 &&
                static_cast<std::uint64_t>(read.return_value) <= block.size(),
            "archive dependency read failed");
    const auto length = static_cast<std::size_t>(read.return_value);
    require(EVP_DigestUpdate(digest.get(), block.data(), length) == 1,
            "archive dependency digest update");
    offset += length;
  }
  const auto after = operations.inspect(descriptor);
  require(after.stat_call.return_value == 0 && before.device == after.device &&
              before.inode == after.inode && before.size_bytes == after.size_bytes &&
              before.changed_seconds == after.changed_seconds &&
              before.changed_nanoseconds == after.changed_nanoseconds &&
              before.modified_seconds == after.modified_seconds &&
              before.modified_nanoseconds == after.modified_nanoseconds,
          "archive dependency changed");
  std::array<std::byte, 32> hash{};
  unsigned int length = 0U;
  require(EVP_DigestFinal_ex(digest.get(),
                             reinterpret_cast<unsigned char*>(hash.data()),
                             &length) == 1 &&
              length == hash.size(),
          "archive dependency digest final");
  return cpu_prefetch::workload::Sha256Digest(hash).hex();
}
auto number(std::uint64_t value) -> Json {
  return Json(
      json::Number{json::Number::Kind::unsigned_integer, std::to_string(value), value});
}
auto signed_number(std::int64_t value) -> Json {
  return Json(
      json::Number{json::Number::Kind::signed_integer, std::to_string(value), value});
}
auto call_json(storage::ArchiveCall call) -> Json {
  return Json(Json::Object{{"return_value", signed_number(call.return_value)},
                           {"errno", signed_number(call.error_number)}});
}
auto stat_json(const std::optional<storage::ArchiveStat>& value) -> Json {
  if (!value) {
    return Json(nullptr);
  }
  return Json(
      Json::Object{{"stat_call", call_json(value->stat_call)},
                   {"flags_call", call_json(value->flags_call)},
                   {"regular", Json(value->regular)},
                   {"device", number(value->device)},
                   {"inode", number(value->inode)},
                   {"size_bytes", number(value->size_bytes)},
                   {"modified_seconds", signed_number(value->modified_seconds)},
                   {"modified_nanoseconds", signed_number(value->modified_nanoseconds)},
                   {"changed_seconds", signed_number(value->changed_seconds)},
                   {"changed_nanoseconds", signed_number(value->changed_nanoseconds)}});
}
auto result_json(const storage::ArchiveEncodeResult& result) -> std::string {
  constexpr std::array names{"COMPLETE_STAGING_SYNCED",
                             "INVALID_PLAN",
                             "INVALID_SCRATCH",
                             "INVALID_DESCRIPTORS",
                             "INVALID_SOURCE_GEOMETRY",
                             "DEPENDENCY_MISMATCH",
                             "DEADLINE",
                             "CLOCK_FAILURE",
                             "IO_BUDGET",
                             "OUTPUT_QUOTA",
                             "SOURCE_READ",
                             "OUTPUT_WRITE",
                             "SYNCHRONIZE",
                             "SOURCE_CHANGED",
                             "SOURCE_HASH_MISMATCH",
                             "CODEC_FAILURE",
                             "CONTEXT_LIMIT",
                             "EXCEPTION"};
  auto value = Json(Json::Object{
      {"schema_version",
       Json(std::string("cpu-prefetch-formal-archive-encoder-result/1"))},
      {"stop", Json(std::string(names.at(static_cast<std::size_t>(result.stop))))},
      {"source_bytes_read", number(result.source_bytes_read)},
      {"archive_bytes_written", number(result.archive_bytes_written)},
      {"blocks_written", number(result.blocks_written)},
      {"io_calls", number(result.io_calls)},
      {"largest_observed_context_bytes", number(result.largest_observed_context_bytes)},
      {"observed_canonical_sha256", result.observed_canonical_sha256
                                        ? Json(*result.observed_canonical_sha256)
                                        : Json(nullptr)},
      {"observed_archive_sha256", result.observed_archive_sha256
                                      ? Json(*result.observed_archive_sha256)
                                      : Json(nullptr)},
      {"source_before", stat_json(result.source_before)},
      {"source_after", stat_json(result.source_after)},
      {"archive_before", stat_json(result.archive_before)},
      {"failed_call",
       result.failed_call ? call_json(*result.failed_call) : Json(nullptr)},
      {"failed_offset", number(result.failed_offset)},
      {"detail", Json(result.detail)}});
  auto document = json::canonicalize(value);
  require(static_cast<bool>(document), "archive result serialization");
  return document.value();
}
} // namespace
int main(int argc, char** argv) {
  try {
    const auto args = arguments(argc, argv);
    rlimit limit{};
    require(::getrlimit(RLIMIT_AS, &limit) == 0 && limit.rlim_cur != RLIM_INFINITY &&
                limit.rlim_cur > 0U && limit.rlim_cur <= 2ULL * 1024U * 1024U * 1024U,
            "encoder requires finite RLIMIT_AS at most 2 GiB");
    storage::LinuxArchiveFileOperations operations;
    const std::array descriptors{args.source, args.archive, args.plan, args.result};
    std::set<std::pair<std::uint64_t, std::uint64_t>> identities;
    for (const auto descriptor : descriptors) {
      const auto status = operations.inspect(descriptor);
      require(status.stat_call.return_value == 0 &&
                  status.flags_call.return_value >= 0 && status.regular &&
                  identities.emplace(status.device, status.inode).second,
              "encoder descriptor type/identity differs");
      if (descriptor == args.result || descriptor == args.archive) {
        require(status.size_bytes == 0U &&
                    (status.flags_call.return_value & O_ACCMODE) != O_RDONLY &&
                    (status.flags_call.return_value & O_APPEND) == 0,
                "encoder requires empty writable nonappend output");
      } else {
        require((status.flags_call.return_value & O_ACCMODE) == O_RDONLY,
                "encoder requires read-only input");
      }
    }
    const auto plan_stat = operations.inspect(args.plan);
    require(plan_stat.size_bytes > 0U && plan_stat.size_bytes <= args.plan_limit,
            "encoder plan exceeds explicit bound");
    std::string input(static_cast<std::size_t>(plan_stat.size_bytes), '\0');
    const auto read =
        operations.read(args.plan, std::as_writable_bytes(std::span(input)), 0U);
    require(read.return_value == static_cast<std::int64_t>(input.size()),
            "encoder plan one-shot read incomplete");
    const auto plan = parse_plan(input);
    const auto sizing = storage::archive_scratch_requirements(plan);
    require(hash_dependency("/proc/self/exe", plan.limits, operations) ==
                plan.identity.encoder_sha256,
            "encoder executable hash mismatch");
    Dl_info library{};
    // POSIX dladdr resolves the actually linked function's image, not a supplied path.
    require(::dladdr(reinterpret_cast<const void*>(&ZSTD_versionNumber), &library) !=
                    0 &&
                library.dli_fname != nullptr,
            "encoder linked zstd image unavailable");
    require(ZSTD_versionNumber() == 10507U &&
                hash_dependency(library.dli_fname, plan.limits, operations) ==
                    plan.identity.zstd_library_sha256,
            "encoder actual zstd image differs");
    std::vector<std::byte> canonical(sizing.canonical_bytes),
        transformed(sizing.transformed_bytes), encoded(sizing.encoded_bytes);
    const auto result = storage::encode_post_measure_archive(
        args.source, args.archive, plan, {canonical, transformed, encoded}, operations);
    const auto document = result_json(result);
    require(document.size() <= args.result_limit,
            "encoder result exceeds explicit output bound; preserve staging/source");
    const auto written =
        operations.write(args.result, std::as_bytes(std::span(document)), 0U);
    require(written.return_value == static_cast<std::int64_t>(document.size()),
            "encoder result incomplete write; preserve staging/source");
    require(operations.synchronize(args.result).return_value == 0,
            "encoder result fsync failed; preserve staging/source");
    return result.stop == storage::ArchiveEncodeStop::complete_staging_synced ? 0 : 1;
  } catch (const std::exception& error) {
    std::cerr << "archive encoder: " << error.what() << '\n';
    return 2;
  }
}
