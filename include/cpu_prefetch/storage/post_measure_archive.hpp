#ifndef CPU_PREFETCH_STORAGE_POST_MEASURE_ARCHIVE_HPP
#define CPU_PREFETCH_STORAGE_POST_MEASURE_ARCHIVE_HPP

#include <cstddef>
#include <cstdint>
#include <optional>
#include <span>
#include <string>
#include <string_view>

namespace cpu_prefetch::storage {

inline constexpr std::string_view kFormalArchivePolicy =
    "EXT007-FORMAL-LOSSLESS-STAND-PRIMARY-v1";
inline constexpr std::string_view kArchiveRowCodec =
    "RAW-U64LE-COLUMN-MODDELTA8192-ZSTD157-L3-v1";
inline constexpr std::string_view kArchiveByteCodec = "BYTES-4MIB-ZSTD157-L3-v1";
inline constexpr std::uint64_t kArchiveBlockRows = 8192U;
inline constexpr std::uint64_t kArchiveByteBlock = std::uint64_t{4U} * 1024U * 1024U;

enum class ArchiveCodec : std::uint8_t { rows, bytes };

// Frozen external identity. Row geometry must already be bound to the actual
// canonical role/run-ID layout; this opaque-word codec is not a raw validator.
struct ArchiveIdentity final {
  std::string artifact_id;
  std::string artifact_role;
  std::string canonical_format;
  std::optional<std::string> run_id;
  std::optional<std::string> phase;
  std::optional<std::string> worker;
  std::uint64_t canonical_size_bytes;
  std::string canonical_sha256;
  ArchiveCodec codec;
  std::optional<std::uint64_t> row_bytes;
  std::optional<std::string> fallback_reason;
  std::string implementation_profile_sha256;
  std::string encoder_sha256;
  std::string zstd_library_sha256;
};

struct ArchiveLimits final {
  int window_log;
  std::uint64_t maximum_header_bytes;
  std::uint64_t maximum_decoded_block_bytes;
  std::uint64_t maximum_encoded_block_bytes;
  std::uint64_t maximum_archive_bytes;
  std::uint64_t maximum_observed_context_bytes;
  std::uint64_t io_chunk_bytes;
  std::uint64_t maximum_io_calls;
  std::uint64_t deadline_monotonic_ns;
};

struct ArchivePlan final {
  ArchiveIdentity identity;
  ArchiveLimits limits;
};

struct ArchiveScratchRequirements final {
  std::size_t canonical_bytes;
  std::size_t transformed_bytes;
  std::size_t encoded_bytes;
  std::uint64_t block_size_bytes;
  std::uint64_t block_count;
  std::uint64_t maximum_archive_bytes;
};

struct ArchiveScratch final {
  std::span<std::byte> canonical;
  std::span<std::byte> transformed;
  std::span<std::byte> encoded;
};

struct ArchiveCall final {
  std::int64_t return_value;
  int error_number;
};

struct ArchiveStat final {
  ArchiveCall stat_call;
  ArchiveCall flags_call;
  bool regular;
  std::uint64_t device;
  std::uint64_t inode;
  std::uint64_t size_bytes;
  std::int64_t modified_seconds;
  std::int64_t modified_nanoseconds;
  std::int64_t changed_seconds;
  std::int64_t changed_nanoseconds;
};

struct ArchiveClockRead final {
  ArchiveCall call;
  std::uint64_t monotonic_ns;
};

// Test seam is separate from the native API: no production synthetic flag.
class ArchiveFileOperations {
public:
  virtual ~ArchiveFileOperations() = default;
  virtual auto inspect(int descriptor) noexcept -> ArchiveStat = 0;
  virtual auto read(int descriptor, std::span<std::byte> bytes,
                    std::uint64_t offset) noexcept -> ArchiveCall = 0;
  virtual auto write(int descriptor, std::span<const std::byte> bytes,
                     std::uint64_t offset) noexcept -> ArchiveCall = 0;
  virtual auto synchronize(int descriptor) noexcept -> ArchiveCall = 0;
  virtual auto clock() noexcept -> ArchiveClockRead = 0;
};

class LinuxArchiveFileOperations final : public ArchiveFileOperations {
public:
  auto inspect(int descriptor) noexcept -> ArchiveStat override;
  auto read(int descriptor, std::span<std::byte> bytes, std::uint64_t offset) noexcept
      -> ArchiveCall override;
  auto write(int descriptor, std::span<const std::byte> bytes,
             std::uint64_t offset) noexcept -> ArchiveCall override;
  auto synchronize(int descriptor) noexcept -> ArchiveCall override;
  auto clock() noexcept -> ArchiveClockRead override;
};

enum class ArchiveEncodeStop : std::uint8_t {
  complete_staging_synced,
  invalid_plan,
  invalid_scratch,
  invalid_descriptors,
  invalid_source_geometry,
  dependency_mismatch,
  deadline,
  clock_failure,
  io_budget,
  output_quota,
  source_read,
  output_write,
  synchronize,
  source_changed,
  source_hash_mismatch,
  codec_failure,
  context_limit,
  exception,
};

struct ArchiveEncodeResult final {
  ArchiveEncodeStop stop{ArchiveEncodeStop::invalid_plan};
  std::uint64_t source_bytes_read{0U};
  std::uint64_t archive_bytes_written{0U};
  std::uint64_t blocks_written{0U};
  std::uint64_t io_calls{0U};
  std::uint64_t largest_observed_context_bytes{0U};
  std::optional<std::string> observed_canonical_sha256;
  std::optional<std::string> observed_archive_sha256;
  std::optional<ArchiveStat> source_before;
  std::optional<ArchiveStat> source_after;
  std::optional<ArchiveStat> archive_before;
  std::optional<ArchiveCall> failed_call;
  std::uint64_t failed_offset{0U};
  std::string detail;
};

// Cold sizing/header construction only; invalid inputs throw invalid_argument
// or overflow_error. Compression is forbidden during any native measurement.
[[nodiscard]] auto archive_scratch_requirements(const ArchivePlan& plan)
    -> ArchiveScratchRequirements;
[[nodiscard]] auto archive_header_json(const ArchivePlan& plan) -> std::string;

// Borrowed descriptors: source must be read-only and archive an empty distinct
// regular staging file created exclusively by its owner. No close/rename/unlink.
// Positive partial I/O progresses within the explicit call budget; failures,
// zero progress and EINTR stop without retry. Metadata, context and hash state
// allocate cold. The production launcher must enforce D233's finite process AS
// ceiling; ZSTD_sizeof_CCtx is an observation, not a transient peak guarantee.
[[nodiscard]] auto
encode_post_measure_archive(int source_fd, int archive_fd, const ArchivePlan& plan,
                            ArchiveScratch scratch, ArchiveFileOperations& operations)
    -> ArchiveEncodeResult;
[[nodiscard]] auto encode_post_measure_archive(int source_fd, int archive_fd,
                                               const ArchivePlan& plan,
                                               ArchiveScratch scratch)
    -> ArchiveEncodeResult;

} // namespace cpu_prefetch::storage
#endif
