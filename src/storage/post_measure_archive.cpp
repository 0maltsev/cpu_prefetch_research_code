#include "cpu_prefetch/storage/post_measure_archive.hpp"

#include "cpu_prefetch/protocol/json.hpp"
#include "cpu_prefetch/workload/deterministic.hpp"

#include <algorithm>
#include <array>
#include <cerrno>
#include <fcntl.h>
#include <limits>
#include <memory>
#include <openssl/evp.h>
#include <stdexcept>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>
#include <zstd.h>

namespace cpu_prefetch::storage {
namespace {
using Bytes = std::span<const std::byte>;
using Json = protocol::json::Value;
constexpr std::uint64_t kWordBytes = 8U;
constexpr std::uint64_t kFrameHeaderBytes = 64U;
constexpr std::uint64_t kFooterBytes = 56U;

[[nodiscard]] auto add(std::uint64_t lhs, std::uint64_t rhs) -> std::uint64_t {
  if (rhs > std::numeric_limits<std::uint64_t>::max() - lhs) {
    throw std::overflow_error("archive size addition");
  }
  return lhs + rhs;
}
[[nodiscard]] auto multiply(std::uint64_t lhs, std::uint64_t rhs) -> std::uint64_t {
  if (rhs != 0U && lhs > std::numeric_limits<std::uint64_t>::max() / rhs) {
    throw std::overflow_error("archive size multiplication");
  }
  return lhs * rhs;
}
[[nodiscard]] auto size_value(std::uint64_t value) -> std::size_t {
  if (value > std::numeric_limits<std::size_t>::max()) {
    throw std::overflow_error("archive host size");
  }
  return static_cast<std::size_t>(value);
}
[[nodiscard]] auto bytes(std::string_view text) -> Bytes {
  return std::as_bytes(std::span(text.data(), text.size()));
}
[[nodiscard]] auto valid_hash(std::string_view text) -> bool {
  return text.size() == 64U && std::ranges::all_of(text, [](char digit) {
           return (digit >= '0' && digit <= '9') || (digit >= 'a' && digit <= 'f');
         });
}
[[nodiscard]] auto uint_json(std::uint64_t value) -> Json {
  return Json(protocol::json::Number{protocol::json::Number::Kind::unsigned_integer,
                                     std::to_string(value), value});
}
[[nodiscard]] auto optional_json(const std::optional<std::string>& value) -> Json {
  return value ? Json(*value) : Json(nullptr);
}
[[nodiscard]] auto vector_format(std::string_view format) -> bool {
  return format == "NODEORDER-U64LE-v1" || format == "SCHEDULE-DEADLINES-U64LE-v1" ||
         format == "SCHEDULE-ABS-U64BE-v1";
}
[[nodiscard]] auto raw_format(std::string_view format) -> bool {
  return format == "RAW-OBS-U64LE-LP-RUNID-v1" ||
         format == "Q16A-DEMAND-U64LE-LP-RUNID-v1";
}
[[nodiscard]] auto prefix_bytes(const ArchiveIdentity& identity) -> std::uint64_t {
  if (!identity.run_id || identity.run_id->empty() ||
      identity.run_id->size() > std::numeric_limits<std::uint32_t>::max()) {
    throw std::invalid_argument("archive raw run identity");
  }
  return (add(identity.run_id->size(), 11U) / kWordBytes) * kWordBytes;
}
[[nodiscard]] auto expected_row_bytes(const ArchiveIdentity& identity)
    -> std::uint64_t {
  if (vector_format(identity.canonical_format)) {
    if (identity.worker) {
      throw std::invalid_argument("archive vector worker identity");
    }
    return kWordBytes;
  }
  if (!raw_format(identity.canonical_format) || !identity.worker ||
      (*identity.worker != "producer" && *identity.worker != "consumer")) {
    throw std::invalid_argument("archive unsupported raw geometry");
  }
  const auto body = identity.canonical_format == "Q16A-DEMAND-U64LE-LP-RUNID-v1"
                        ? 72U
                        : (*identity.worker == "producer" ? 120U : 80U);
  return add(prefix_bytes(identity), body);
}
void validate(const ArchivePlan& plan) {
  const auto& id = plan.identity;
  const auto& limits = plan.limits;
  if (id.artifact_id.empty() || id.artifact_role.empty() ||
      id.canonical_format.empty() || !valid_hash(id.canonical_sha256) ||
      !valid_hash(id.implementation_profile_sha256) || !valid_hash(id.encoder_sha256) ||
      !valid_hash(id.zstd_library_sha256) || (id.run_id && id.run_id->empty()) ||
      (id.phase && *id.phase != "warmup" && *id.phase != "measurement") ||
      (id.worker && *id.worker != "producer" && *id.worker != "consumer") ||
      limits.window_log < 10 || limits.window_log > 31 ||
      limits.maximum_header_bytes == 0U || limits.maximum_archive_bytes == 0U ||
      limits.maximum_observed_context_bytes == 0U || limits.io_chunk_bytes == 0U ||
      limits.io_chunk_bytes >
          static_cast<std::uint64_t>(std::numeric_limits<ssize_t>::max()) ||
      limits.maximum_io_calls == 0U || limits.deadline_monotonic_ns == 0U ||
      id.canonical_size_bytes >
          static_cast<std::uint64_t>(std::numeric_limits<off_t>::max()) ||
      limits.maximum_archive_bytes >
          static_cast<std::uint64_t>(std::numeric_limits<off_t>::max())) {
    throw std::invalid_argument("archive identity or finite limits");
  }
  if (id.codec == ArchiveCodec::rows) {
    if (!id.row_bytes || *id.row_bytes != expected_row_bytes(id) ||
        id.canonical_size_bytes % *id.row_bytes != 0U || id.fallback_reason) {
      throw std::invalid_argument("archive row geometry");
    }
  } else if (id.codec == ArchiveCodec::bytes) {
    const bool fallback =
        raw_format(id.canonical_format) || vector_format(id.canonical_format);
    if (fallback) {
      static_cast<void>(expected_row_bytes(id));
    }
    if (id.row_bytes ||
        (fallback && (!id.fallback_reason || id.fallback_reason->empty())) ||
        (!fallback && (id.fallback_reason || id.worker))) {
      throw std::invalid_argument("archive byte fallback binding");
    }
  } else {
    throw std::invalid_argument("archive codec");
  }
}
void store_u64(std::span<std::byte> target, std::uint64_t value) {
  for (std::size_t index = 0U; index < 8U; ++index) {
    target[index] = static_cast<std::byte>((value >> (index * 8U)) & 255U);
  }
}
[[nodiscard]] auto load_u64(Bytes source) -> std::uint64_t {
  std::uint64_t value = 0U;
  for (std::size_t index = 0U; index < 8U; ++index) {
    value |= std::to_integer<std::uint64_t>(source[index]) << (index * 8U);
  }
  return value;
}
void transform(Bytes source, std::span<std::byte> destination, std::size_t width) {
  const auto rows = source.size() / width;
  for (std::size_t column = 0U; column < width / 8U; ++column) {
    std::uint64_t previous = 0U;
    for (std::size_t row = 0U; row < rows; ++row) {
      const auto value = load_u64(source.subspan(row * width + column * 8U, 8U));
      store_u64(destination.subspan((column * rows + row) * 8U, 8U), value - previous);
      previous = value;
    }
  }
}
[[nodiscard]] auto prefixes_match(Bytes source, const ArchiveIdentity& identity)
    -> bool {
  if (!raw_format(identity.canonical_format)) {
    return true;
  }
  if (!identity.row_bytes || !identity.run_id) {
    throw std::invalid_argument("archive raw geometry absent");
  }
  const auto width = size_value(*identity.row_bytes);
  const auto prefix = size_value(prefix_bytes(identity));
  const auto& run = *identity.run_id;
  for (std::size_t offset = 0U; offset < source.size(); offset += width) {
    const auto row = source.subspan(offset, width);
    for (std::size_t index = 0U; index < 4U; ++index) {
      if (row[index] != static_cast<std::byte>((run.size() >> (index * 8U)) & 255U)) {
        return false;
      }
    }
    if (!std::ranges::equal(row.subspan(4U, run.size()), bytes(run)) ||
        !std::ranges::all_of(row.subspan(4U + run.size(), prefix - 4U - run.size()),
                             [](std::byte value) { return value == std::byte{0}; })) {
      return false;
    }
  }
  return true;
}
class Digest final {
public:
  Digest() : context_(EVP_MD_CTX_new(), EVP_MD_CTX_free) {
    if (!context_ || EVP_DigestInit_ex(context_.get(), EVP_sha256(), nullptr) != 1) {
      throw std::runtime_error("archive digest initialization");
    }
  }
  void update(Bytes input) {
    if (EVP_DigestUpdate(context_.get(), input.data(), input.size()) != 1) {
      throw std::runtime_error("archive digest update");
    }
  }
  [[nodiscard]] auto finish() -> workload::Sha256Digest {
    std::array<std::byte, 32> output{};
    unsigned int length = 0U;
    if (EVP_DigestFinal_ex(context_.get(),
                           reinterpret_cast<unsigned char*>(output.data()),
                           &length) != 1 ||
        length != output.size()) {
      throw std::runtime_error("archive digest finalization");
    }
    return workload::Sha256Digest(output);
  }

private:
  std::unique_ptr<EVP_MD_CTX, decltype(&EVP_MD_CTX_free)> context_;
};
struct Stop final {
  ArchiveEncodeStop reason;
};
[[nodiscard]] auto same_source(const ArchiveStat& lhs, const ArchiveStat& rhs) -> bool {
  return rhs.stat_call.return_value == 0 && rhs.flags_call.return_value >= 0 &&
         rhs.regular && lhs.device == rhs.device && lhs.inode == rhs.inode &&
         lhs.size_bytes == rhs.size_bytes &&
         lhs.modified_seconds == rhs.modified_seconds &&
         lhs.modified_nanoseconds == rhs.modified_nanoseconds &&
         lhs.changed_seconds == rhs.changed_seconds &&
         lhs.changed_nanoseconds == rhs.changed_nanoseconds;
}
[[nodiscard]] auto range(std::span<std::byte> input)
    -> std::pair<std::uintptr_t, std::uintptr_t> {
  const auto begin = reinterpret_cast<std::uintptr_t>(input.data());
  if (input.size() > std::numeric_limits<std::uintptr_t>::max() - begin ||
      (!input.empty() && input.data() == nullptr)) {
    throw std::invalid_argument("archive scratch pointer overflow");
  }
  return {begin, begin + input.size()};
}
[[nodiscard]] auto disjoint(ArchiveScratch scratch) -> bool {
  const std::array ranges{range(scratch.canonical), range(scratch.transformed),
                          range(scratch.encoded)};
  for (std::size_t first = 0; first < ranges.size(); ++first) {
    for (std::size_t second = first + 1U; second < ranges.size(); ++second) {
      const auto [ab, ae] = ranges[first];
      const auto [bb, be] = ranges[second];
      if (ab != ae && bb != be && ab < be && bb < ae) {
        return false;
      }
    }
  }
  return true;
}
class Writer final {
public:
  Writer(ArchiveFileOperations& operations, const ArchiveLimits& limits,
         ArchiveEncodeResult& result, int descriptor)
      : operations_(operations), limits_(limits), result_(result),
        descriptor_(descriptor) {}
  void time() {
    const auto now = operations_.clock();
    if (now.call.return_value != 0 ||
        (last_clock_ && now.monotonic_ns < *last_clock_)) {
      result_.failed_call = now.call;
      throw Stop{ArchiveEncodeStop::clock_failure};
    }
    last_clock_ = now.monotonic_ns;
    if (now.monotonic_ns >= limits_.deadline_monotonic_ns) {
      throw Stop{ArchiveEncodeStop::deadline};
    }
  }
  void call_budget() {
    time();
    if (result_.io_calls >= limits_.maximum_io_calls) {
      throw Stop{ArchiveEncodeStop::io_budget};
    }
    ++result_.io_calls;
  }
  void write(Bytes input) {
    while (!input.empty()) {
      const auto length = std::min(input.size(), size_value(limits_.io_chunk_bytes));
      if (length > limits_.maximum_archive_bytes - result_.archive_bytes_written) {
        throw Stop{ArchiveEncodeStop::output_quota};
      }
      call_budget();
      const auto part = input.first(length);
      const auto observed =
          operations_.write(descriptor_, part, result_.archive_bytes_written);
      if (observed.return_value <= 0 ||
          static_cast<std::uint64_t>(observed.return_value) > length) {
        result_.failed_call = observed;
        result_.failed_offset = result_.archive_bytes_written;
        throw Stop{ArchiveEncodeStop::output_write};
      }
      const auto written = static_cast<std::size_t>(observed.return_value);
      digest_.update(part.first(written));
      result_.archive_bytes_written += written;
      input = input.subspan(written);
    }
  }
  [[nodiscard]] auto digest() -> workload::Sha256Digest { return digest_.finish(); }

private:
  ArchiveFileOperations& operations_;
  const ArchiveLimits& limits_;
  ArchiveEncodeResult& result_;
  int descriptor_;
  std::optional<std::uint64_t> last_clock_;
  Digest digest_;
};
} // namespace

auto archive_scratch_requirements(const ArchivePlan& plan)
    -> ArchiveScratchRequirements {
  validate(plan);
  const auto block_size =
      plan.identity.codec == ArchiveCodec::rows
          ? multiply(kArchiveBlockRows, expected_row_bytes(plan.identity))
          : kArchiveByteBlock;
  if (block_size == 0U) {
    throw std::invalid_argument("archive zero block extent");
  }
  const auto size = plan.identity.canonical_size_bytes;
  const auto count = size / block_size + (size % block_size != 0U ? 1U : 0U);
  const auto decoded = size_value(std::min(size, block_size));
  const auto encoded = decoded == 0U ? 0U : ZSTD_compressBound(decoded);
  if ((decoded != 0U && (encoded == 0U || ZSTD_isError(encoded) != 0U)) ||
      decoded > plan.limits.maximum_decoded_block_bytes ||
      encoded > plan.limits.maximum_encoded_block_bytes) {
    throw std::invalid_argument("archive block exceeds finite scratch limits");
  }
  const auto worst =
      add(add(16U, plan.limits.maximum_header_bytes),
          add(multiply(count, add(encoded, kFrameHeaderBytes)), kFooterBytes));
  return {decoded, plan.identity.codec == ArchiveCodec::rows ? decoded : 0U,
          encoded, block_size,
          count,   worst};
}
auto archive_header_json(const ArchivePlan& plan) -> std::string {
  const auto requirements = archive_scratch_requirements(plan);
  const auto& id = plan.identity;
  Json::Object object;
  const auto put = [&object](std::string key, std::string_view value) {
    object.emplace(std::move(key), Json(std::string(value)));
  };
  put("schema_version", "cpu-prefetch-formal-archive-header/1");
  put("policy_id", kFormalArchivePolicy);
  put("codec_id",
      id.codec == ArchiveCodec::rows ? kArchiveRowCodec : kArchiveByteCodec);
  put("artifact_id", id.artifact_id);
  put("artifact_role", id.artifact_role);
  put("canonical_format", id.canonical_format);
  put("canonical_sha256", id.canonical_sha256);
  put("implementation_profile_sha256", id.implementation_profile_sha256);
  put("encoder_sha256", id.encoder_sha256);
  put("zstd_library_sha256", id.zstd_library_sha256);
  put("zstd_version", "1.5.7");
  object.emplace("run_id", optional_json(id.run_id));
  object.emplace("phase", optional_json(id.phase));
  object.emplace("worker", optional_json(id.worker));
  object.emplace("fallback_reason", optional_json(id.fallback_reason));
  object.emplace("canonical_size_bytes", uint_json(id.canonical_size_bytes));
  object.emplace("row_bytes", id.row_bytes ? uint_json(*id.row_bytes) : Json(nullptr));
  object.emplace("row_count", id.row_bytes
                                  ? uint_json(id.canonical_size_bytes / *id.row_bytes)
                                  : Json(nullptr));
  object.emplace("block_size_bytes", uint_json(requirements.block_size_bytes));
  object.emplace("block_count", uint_json(requirements.block_count));
  object.emplace("compression_level", uint_json(3U));
  object.emplace("worker_threads", uint_json(1U));
  object.emplace("window_log",
                 uint_json(static_cast<std::uint64_t>(plan.limits.window_log)));
  object.emplace("checksum_flag", uint_json(1U));
  object.emplace("content_size_flag", uint_json(1U));
  object.emplace("dictionary_id_flag", uint_json(0U));
  auto result = protocol::json::canonicalize(Json(std::move(object)));
  if (!result || result.value().size() > plan.limits.maximum_header_bytes) {
    throw std::invalid_argument("archive header serialization or bound");
  }
  return result.value();
}

auto LinuxArchiveFileOperations::inspect(int descriptor) noexcept -> ArchiveStat {
  struct stat status{};
  errno = 0;
  const int stat_result = ::fstat(descriptor, &status);
  const int stat_error = errno;
  errno = 0;
  const int flags = ::fcntl(descriptor, F_GETFL);
  const int flags_error = errno;
  return {{stat_result, stat_result < 0 ? stat_error : 0},
          {flags, flags < 0 ? flags_error : 0},
          stat_result == 0 && S_ISREG(status.st_mode),
          static_cast<std::uint64_t>(status.st_dev),
          static_cast<std::uint64_t>(status.st_ino),
          status.st_size < 0 ? 0U : static_cast<std::uint64_t>(status.st_size),
          status.st_mtim.tv_sec,
          status.st_mtim.tv_nsec,
          status.st_ctim.tv_sec,
          status.st_ctim.tv_nsec};
}
auto LinuxArchiveFileOperations::read(int descriptor, std::span<std::byte> output,
                                      std::uint64_t offset) noexcept -> ArchiveCall {
  if (offset > static_cast<std::uint64_t>(std::numeric_limits<off_t>::max())) {
    return {-1, EOVERFLOW};
  }
  errno = 0;
  const auto result =
      ::pread(descriptor, output.data(), output.size(), static_cast<off_t>(offset));
  return {result, result < 0 ? errno : 0};
}
auto LinuxArchiveFileOperations::write(int descriptor, Bytes input,
                                       std::uint64_t offset) noexcept -> ArchiveCall {
  if (offset > static_cast<std::uint64_t>(std::numeric_limits<off_t>::max())) {
    return {-1, EOVERFLOW};
  }
  errno = 0;
  const auto result =
      ::pwrite(descriptor, input.data(), input.size(), static_cast<off_t>(offset));
  return {result, result < 0 ? errno : 0};
}
auto LinuxArchiveFileOperations::synchronize(int descriptor) noexcept -> ArchiveCall {
  errno = 0;
  const auto result = ::fsync(descriptor);
  return {result, result < 0 ? errno : 0};
}
auto LinuxArchiveFileOperations::clock() noexcept -> ArchiveClockRead {
  timespec value{};
  errno = 0;
  const int result = ::clock_gettime(CLOCK_MONOTONIC, &value);
  return {{result, result < 0 ? errno : 0},
          result == 0 ? static_cast<std::uint64_t>(value.tv_sec) * 1000000000U +
                            static_cast<std::uint64_t>(value.tv_nsec)
                      : 0U};
}

auto encode_post_measure_archive(int source_fd, int archive_fd, const ArchivePlan& plan,
                                 ArchiveScratch scratch,
                                 ArchiveFileOperations& operations)
    -> ArchiveEncodeResult {
  ArchiveEncodeResult result;
  try {
    const auto requirements = archive_scratch_requirements(plan);
    const auto header = archive_header_json(plan);
    if (!disjoint(scratch) || scratch.canonical.size() < requirements.canonical_bytes ||
        scratch.transformed.size() < requirements.transformed_bytes ||
        scratch.encoded.size() < requirements.encoded_bytes) {
      result.stop = ArchiveEncodeStop::invalid_scratch;
      return result;
    }
    if (ZSTD_versionNumber() != 10507U) {
      result.stop = ArchiveEncodeStop::dependency_mismatch;
      return result;
    }
    Writer output(operations, plan.limits, result, archive_fd);
    output.call_budget();
    result.source_before = operations.inspect(source_fd);
    output.call_budget();
    result.archive_before = operations.inspect(archive_fd);
    const auto& source = *result.source_before;
    const auto& target = *result.archive_before;
    if (source_fd < 0 || archive_fd < 0 || source_fd == archive_fd ||
        source.stat_call.return_value != 0 || source.flags_call.return_value < 0 ||
        !source.regular || target.stat_call.return_value != 0 ||
        target.flags_call.return_value < 0 || !target.regular ||
        (source.flags_call.return_value & O_ACCMODE) != O_RDONLY ||
        (target.flags_call.return_value & O_ACCMODE) == O_RDONLY ||
        (target.flags_call.return_value & O_APPEND) != 0 ||
        (source.device == target.device && source.inode == target.inode) ||
        target.size_bytes != 0U ||
        source.size_bytes != plan.identity.canonical_size_bytes) {
      result.stop = ArchiveEncodeStop::invalid_descriptors;
      return result;
    }
    std::unique_ptr<ZSTD_CCtx, decltype(&ZSTD_freeCCtx)> context(ZSTD_createCCtx(),
                                                                 ZSTD_freeCCtx);
    if (!context) {
      throw Stop{ArchiveEncodeStop::codec_failure};
    }
    const auto parameter = [&context](ZSTD_cParameter key, int value) {
      if (ZSTD_isError(ZSTD_CCtx_setParameter(context.get(), key, value)) != 0U) {
        throw Stop{ArchiveEncodeStop::codec_failure};
      }
    };
    parameter(ZSTD_c_compressionLevel, 3);
    parameter(ZSTD_c_nbWorkers, 0);
    parameter(ZSTD_c_windowLog, plan.limits.window_log);
    parameter(ZSTD_c_checksumFlag, 1);
    parameter(ZSTD_c_contentSizeFlag, 1);
    parameter(ZSTD_c_dictIDFlag, 0);
    const auto context_limit = [&]() {
      result.largest_observed_context_bytes =
          std::max(result.largest_observed_context_bytes,
                   static_cast<std::uint64_t>(ZSTD_sizeof_CCtx(context.get())));
      if (result.largest_observed_context_bytes >
          plan.limits.maximum_observed_context_bytes) {
        throw Stop{ArchiveEncodeStop::context_limit};
      }
    };
    context_limit();
    std::array<std::byte, 16> prefix{};
    std::ranges::copy(bytes("CPFA2331"), prefix.begin());
    store_u64(std::span(prefix).subspan(8U), header.size());
    output.write(prefix);
    output.write(bytes(header));
    Digest original;
    for (std::uint64_t ordinal = 0U; ordinal < requirements.block_count; ++ordinal) {
      const auto offset = result.source_bytes_read;
      const auto length = size_value(std::min(
          requirements.block_size_bytes, plan.identity.canonical_size_bytes - offset));
      auto canonical = scratch.canonical.first(length);
      std::size_t filled = 0U;
      while (filled < length) {
        output.call_budget();
        const auto part = canonical.subspan(
            filled, std::min(length - filled, size_value(plan.limits.io_chunk_bytes)));
        const auto observed =
            operations.read(source_fd, part, result.source_bytes_read);
        if (observed.return_value <= 0 ||
            static_cast<std::uint64_t>(observed.return_value) > part.size()) {
          result.failed_call = observed;
          result.failed_offset = result.source_bytes_read;
          throw Stop{ArchiveEncodeStop::source_read};
        }
        const auto count = static_cast<std::size_t>(observed.return_value);
        original.update(part.first(count));
        filled += count;
        result.source_bytes_read += count;
      }
      Bytes payload = canonical;
      if (plan.identity.codec == ArchiveCodec::rows) {
        if (!prefixes_match(canonical, plan.identity)) {
          throw Stop{ArchiveEncodeStop::invalid_source_geometry};
        }
        transform(canonical, scratch.transformed.first(length),
                  size_value(expected_row_bytes(plan.identity)));
        payload = scratch.transformed.first(length);
      }
      output.time();
      const auto compressed =
          ZSTD_compress2(context.get(), scratch.encoded.data(),
                         requirements.encoded_bytes, payload.data(), payload.size());
      output.time();
      context_limit();
      if (ZSTD_isError(compressed) != 0U || compressed > requirements.encoded_bytes) {
        throw Stop{ArchiveEncodeStop::codec_failure};
      }
      const auto frame = scratch.encoded.first(compressed);
      const auto frame_digest = workload::sha256(frame);
      std::array<std::byte, kFrameHeaderBytes> block_header{};
      store_u64(std::span(block_header).subspan(0U, 8U), ordinal);
      store_u64(std::span(block_header).subspan(8U, 8U), offset);
      store_u64(std::span(block_header).subspan(16U, 8U), length);
      store_u64(std::span(block_header).subspan(24U, 8U), compressed);
      std::ranges::copy(frame_digest.bytes(), block_header.begin() + 32);
      output.write(block_header);
      output.write(frame);
      ++result.blocks_written;
    }
    output.call_budget();
    result.source_after = operations.inspect(source_fd);
    if (!same_source(source, *result.source_after)) {
      throw Stop{ArchiveEncodeStop::source_changed};
    }
    const auto canonical_hash = original.finish();
    result.observed_canonical_sha256 = canonical_hash.hex();
    if (*result.observed_canonical_sha256 != plan.identity.canonical_sha256) {
      throw Stop{ArchiveEncodeStop::source_hash_mismatch};
    }
    std::array<std::byte, kFooterBytes> footer{};
    std::ranges::copy(bytes("CPFAEND1"), footer.begin());
    store_u64(std::span(footer).subspan(8U, 8U), result.blocks_written);
    store_u64(std::span(footer).subspan(16U, 8U), result.source_bytes_read);
    std::ranges::copy(canonical_hash.bytes(), footer.begin() + 24);
    output.write(footer);
    result.observed_archive_sha256 = output.digest().hex();
    output.call_budget();
    const auto sync = operations.synchronize(archive_fd);
    if (sync.return_value != 0) {
      result.failed_call = sync;
      throw Stop{ArchiveEncodeStop::synchronize};
    }
    output.time();
    result.stop = ArchiveEncodeStop::complete_staging_synced;
  } catch (const Stop& stopped) {
    result.stop = stopped.reason;
  } catch (const std::invalid_argument& error) {
    result.stop = ArchiveEncodeStop::invalid_plan;
    result.detail = error.what();
  } catch (const std::overflow_error& error) {
    result.stop = ArchiveEncodeStop::invalid_plan;
    result.detail = error.what();
  } catch (const std::exception& error) {
    result.stop = ArchiveEncodeStop::exception;
    result.detail = error.what();
  }
  return result;
}
auto encode_post_measure_archive(int source_fd, int archive_fd, const ArchivePlan& plan,
                                 ArchiveScratch scratch) -> ArchiveEncodeResult {
  LinuxArchiveFileOperations operations;
  return encode_post_measure_archive(source_fd, archive_fd, plan, scratch, operations);
}
} // namespace cpu_prefetch::storage
