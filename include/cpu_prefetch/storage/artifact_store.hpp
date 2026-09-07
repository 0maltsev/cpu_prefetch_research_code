#ifndef CPU_PREFETCH_STORAGE_ARTIFACT_STORE_HPP
#define CPU_PREFETCH_STORAGE_ARTIFACT_STORE_HPP

#include "cpu_prefetch/storage/artifacts.hpp"

#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <optional>
#include <set>
#include <span>
#include <string>
#include <vector>

namespace cpu_prefetch::storage {

struct LocalStorageDomain final {
  std::string storage_domain_id;
  std::filesystem::path root;
};

enum class PublicationFaultPoint : std::uint8_t {
  none,
  storage_exhausted,
  partial_staging_write,
  after_staging_sync,
  readback_mismatch,
  after_primary_publish,
  before_ledger_write,
  partial_ledger_write,
};

struct PublicationFaultPlan final {
  PublicationFaultPoint point{PublicationFaultPoint::none};
  std::size_t domain_index{0U};
  std::uint64_t partial_bytes{0U};
};

enum class RunStoreOpenMode : std::uint8_t {
  create_new,
  recover_existing,
};

struct LocalRunStoreConfig final {
  std::string run_id;
  std::string verification_timestamp;
  std::vector<LocalStorageDomain> domains;
  PublicationFaultPlan fault;
  RunStoreOpenMode open_mode{RunStoreOpenMode::create_new};
};

struct PublishObjectRequest final {
  std::string object_id;
  std::string object_role;
  std::string artifact_id;
  std::string ledger_record_id;
  std::span<const std::byte> bytes;
  std::string expected_sha256;
  StreamCompleteness stream_completeness;
};

struct PublishObjectResult final {
  CopyFinalizationState finalization_state;
  std::vector<CopyEvidence> copies;
  std::vector<std::string> failures;
  CanonicalDocument ledger;
  bool ledger_persisted;
};

struct RecoveryResult final {
  bool promoted;
  bool already_published;
  std::optional<CopyEvidence> copy;
  std::string failure;
};

// Linux local correctness backend. Domain names and roots are explicit inputs;
// two local paths are not evidence that real production failure domains exist.
class LocalAppendOnlyRunStore final {
public:
  explicit LocalAppendOnlyRunStore(LocalRunStoreConfig config);

  LocalAppendOnlyRunStore(const LocalAppendOnlyRunStore&) = delete;
  LocalAppendOnlyRunStore& operator=(const LocalAppendOnlyRunStore&) = delete;
  LocalAppendOnlyRunStore(LocalAppendOnlyRunStore&&) = delete;
  LocalAppendOnlyRunStore& operator=(LocalAppendOnlyRunStore&&) = delete;

  [[nodiscard]] auto publish(const PublishObjectRequest& request)
      -> protocol::Result<PublishObjectResult>;
  [[nodiscard]] auto
  recover_staging(std::size_t domain_index, std::string_view object_id,
                  std::uint64_t expected_byte_count, std::string_view expected_sha256)
      -> RecoveryResult;
  [[nodiscard]] auto artifact_uri(std::size_t domain_index,
                                  std::string_view object_id) const -> std::string;
  [[nodiscard]] auto run_directories() const noexcept
      -> const std::vector<std::filesystem::path>& {
    return run_directories_;
  }

private:
  LocalRunStoreConfig config_;
  std::vector<std::filesystem::path> run_directories_;
  std::set<std::string> object_ids_;
  std::set<std::string> artifact_ids_;
};

} // namespace cpu_prefetch::storage

#endif // CPU_PREFETCH_STORAGE_ARTIFACT_STORE_HPP
