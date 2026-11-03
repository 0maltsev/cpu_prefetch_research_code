#ifndef CPU_PREFETCH_PLATFORM_PREPARED_FILE_SNAPSHOT_HPP
#define CPU_PREFETCH_PLATFORM_PREPARED_FILE_SNAPSHOT_HPP

#include "cpu_prefetch/platform/owner_mapping.hpp"

#include <array>
#include <string_view>

namespace cpu_prefetch::platform {

inline constexpr std::size_t kFileSnapshotGroups = 6U;

struct FileSnapshotPlan final {
  std::string_view path;
  std::size_t byte_capacity;
  std::size_t chunk_bytes;
  std::size_t max_data_reads;
  // Caller binds slots to warmup before/during/after, measurement before/during/after.
  // No source, capacity, chunk count or observation moment is defaulted here.
  std::array<bool, kFileSnapshotGroups> requested;
};

// Pure finite-budget/path-shape validation for cold native layout admission.
// Does not establish source provenance, applicability or path allowlisting.
[[nodiscard]] auto valid_file_snapshot_plan(FileSnapshotPlan plan) noexcept -> bool;

class FileSnapshotOperations {
public:
  virtual ~FileSnapshotOperations() = default;
  [[nodiscard]] virtual auto open_file(const char* path, int flags) noexcept
      -> LinuxCallResult = 0;
  [[nodiscard]] virtual auto read_at(int descriptor, std::span<std::byte> bytes,
                                     std::size_t offset) noexcept
      -> LinuxCallResult = 0;
  [[nodiscard]] virtual auto close_file(int descriptor) noexcept -> LinuxCallResult = 0;
};

class LinuxFileSnapshotOperations final : public FileSnapshotOperations {
public:
  [[nodiscard]] auto open_file(const char* path, int flags) noexcept
      -> LinuxCallResult override;
  [[nodiscard]] auto read_at(int descriptor, std::span<std::byte> bytes,
                             std::size_t offset) noexcept -> LinuxCallResult override;
  [[nodiscard]] auto close_file(int descriptor) noexcept -> LinuxCallResult override;
};

struct FileSnapshotRead final {
  std::size_t offset{};
  std::size_t requested_bytes{};
  std::optional<LinuxCallResult> observed;
};

enum class FileSnapshotStop : std::uint8_t {
  not_started,
  not_prepared,
  invalid_slot,
  output_reused,
  invalid_storage,
  not_requested,
  read_failed,
  invalid_read_count,
  probe_failed,
  byte_capacity_exhausted,
  read_budget_exhausted,
  complete,
};

struct FileSnapshotSample final {
  std::span<std::byte> bytes;
  std::span<FileSnapshotRead> reads;
  bool attempted{false};
  std::size_t captured_bytes{0U};
  std::size_t data_reads{0U};
  FileSnapshotRead eof_probe{};
  std::byte probe_byte{};
  FileSnapshotStop stop{FileSnapshotStop::not_started};
  [[nodiscard]] auto io_complete() const noexcept -> bool {
    return stop == FileSnapshotStop::complete;
  }
};

enum class FileSnapshotPreparationStop : std::uint8_t {
  not_started,
  invalid_plan,
  invalid_storage,
  open_failed,
  ready,
};

struct FileSnapshotPreparation final {
  bool attempted{false};
  bool released{false};
  // Refers to caller-provided frozen_path, not the original plan string.
  FileSnapshotPlan plan{};
  std::optional<LinuxCallResult> open;
  std::optional<LinuxCallResult> close;
  FileSnapshotPreparationStop stop{FileSnapshotPreparationStop::not_started};
};

// Controller-only, one preopened read-only FD per explicit admitted source.
// Caller allocates the object, path storage, all six output objects, six byte
// buffers and six read-record arrays in disjoint prepared monitoring storage.
// frozen_path must have exactly plan.path.size()+1 bytes; every sample must have
// exactly byte_capacity bytes and max_data_reads records. Prepare validates all
// ranges and initializes storage before opening. Keep path/descriptors immutable
// and all storage alive until publication and release; serialize all methods.
//
// Sampling does no allocation, opening, parsing, sleeping or scheduling. Short
// positive reads advance the offset; EINTR and other failures are never retried.
// At most max_data_reads advancing preads plus one single-byte EOF probe occur.
// A zero data read proves EOF without another probe. Exact capacity is accepted
// only if the probe observes EOF; otherwise retained partial bytes remain failed
// data. Each slot is one-use; reusing it never overwrites its earlier evidence.
//
// Reads within/across files are NON-ATOMIC and syscall wall time is not bounded
// by these byte/call budgets. Outer controller timestamps, deadlines and watchdog
// remain mandatory. io_complete() proves only bounded raw delivery: it never
// establishes smaps page policy, frequency/governor/thermal/interrupt validity,
// source applicability or a numeric threshold. Empty EOF is retained as empty
// data, not a fabricated sensor value. Policy/thresholds remain unenforced here.
class PreparedFileSnapshot final {
public:
  explicit PreparedFileSnapshot(FileSnapshotOperations& operations) noexcept
      : operations_(operations) {}
  ~PreparedFileSnapshot();
  PreparedFileSnapshot(const PreparedFileSnapshot&) = delete;
  auto operator=(const PreparedFileSnapshot&) -> PreparedFileSnapshot& = delete;
  PreparedFileSnapshot(PreparedFileSnapshot&&) = delete;
  auto operator=(PreparedFileSnapshot&&) -> PreparedFileSnapshot& = delete;

  [[nodiscard]] auto
  prepare(FileSnapshotPlan plan, std::span<char> frozen_path,
          std::span<FileSnapshotSample, kFileSnapshotGroups> samples) noexcept -> bool;
  [[nodiscard]] auto sample(std::size_t slot) noexcept -> FileSnapshotStop;
  [[nodiscard]] auto release() noexcept -> bool;
  [[nodiscard]] auto preparation() const noexcept -> const FileSnapshotPreparation& {
    return preparation_;
  }

private:
  FileSnapshotOperations& operations_;
  FileSnapshotPreparation preparation_{};
  std::span<FileSnapshotSample> samples_;
  struct Storage final {
    std::span<std::byte> bytes;
    std::span<FileSnapshotRead> reads;
  };
  std::array<Storage, kFileSnapshotGroups> storage_{};
  std::array<bool, kFileSnapshotGroups> attempted_{};
  int descriptor_{-1};
};

} // namespace cpu_prefetch::platform

#endif
