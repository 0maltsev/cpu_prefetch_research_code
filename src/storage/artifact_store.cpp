#include "cpu_prefetch/storage/artifact_store.hpp"

#include "cpu_prefetch/workload/deterministic.hpp"

#include <array>
#include <cerrno>
#include <cstring>
#include <fcntl.h>
#include <limits>
#include <openssl/evp.h>
#include <sys/stat.h>
#include <unistd.h>
#include <utility>

namespace cpu_prefetch::storage {
namespace {

class FileDescriptor final {
public:
  explicit FileDescriptor(int value = -1) noexcept : value_(value) {}
  ~FileDescriptor() {
    if (value_ >= 0) {
      static_cast<void>(::close(value_));
    }
  }

  FileDescriptor(const FileDescriptor&) = delete;
  FileDescriptor& operator=(const FileDescriptor&) = delete;
  FileDescriptor(FileDescriptor&& other) noexcept
      : value_(std::exchange(other.value_, -1)) {}
  FileDescriptor& operator=(FileDescriptor&& other) noexcept {
    if (this != &other) {
      if (value_ >= 0) {
        static_cast<void>(::close(value_));
      }
      value_ = std::exchange(other.value_, -1);
    }
    return *this;
  }

  [[nodiscard]] auto get() const noexcept -> int { return value_; }

private:
  int value_;
};

struct FileIdentity final {
  bool ok;
  std::uint64_t byte_count;
  std::string sha256;
  std::string failure;
};

struct LedgerPublication final {
  std::string_view record_id;
  std::string_view bytes;
};

[[nodiscard]] auto bytes_sha256(std::string_view text) -> std::string {
  return workload::sha256(
             std::span<const std::byte>(reinterpret_cast<const std::byte*>(text.data()),
                                        text.size()))
      .hex();
}

[[nodiscard]] auto object_name(std::string_view object_id) -> std::string {
  return "object-" + bytes_sha256(object_id);
}

[[nodiscard]] auto run_name(std::string_view run_id) -> std::string {
  return "run-" + bytes_sha256(run_id);
}

[[nodiscard]] auto errno_failure(std::string_view operation) -> std::string {
  return std::string(operation) + ": " + std::strerror(errno);
}

void require_directory(const std::filesystem::path& path, std::string_view field) {
  std::error_code error;
  const auto status = std::filesystem::status(path, error);
  if (error || !std::filesystem::is_directory(status)) {
    throw StorageSetupError(std::string(field) + " must name an existing directory");
  }
}

void create_unique_directory(const std::filesystem::path& path,
                             std::string_view field) {
  std::error_code error;
  if (!std::filesystem::create_directory(path, error)) {
    throw StorageSetupError(std::string(field) + " must be unique: " +
                            (error ? error.message() : "already exists"));
  }
}

[[nodiscard]] auto fsync_directory(const std::filesystem::path& path) -> bool {
  const FileDescriptor descriptor(
      ::open(path.c_str(), O_RDONLY | O_DIRECTORY | O_CLOEXEC));
  return descriptor.get() >= 0 && ::fsync(descriptor.get()) == 0;
}

[[nodiscard]] auto write_complete(int descriptor, std::span<const std::byte> bytes,
                                  std::optional<std::uint64_t> stop_after)
    -> std::optional<std::string> {
  std::size_t written = 0U;
  while (written < bytes.size()) {
    auto remaining = bytes.size() - written;
    if (stop_after.has_value()) {
      if (written >= *stop_after) {
        return std::string("simulated partial write");
      }
      const auto allowed = static_cast<std::size_t>(
          std::min<std::uint64_t>(remaining, *stop_after - written));
      remaining = allowed;
    }
    const auto result = ::write(descriptor, bytes.data() + written, remaining);
    if (result < 0 && errno == EINTR) {
      continue;
    }
    if (result <= 0) {
      return errno_failure("write");
    }
    written += static_cast<std::size_t>(result);
  }
  if (stop_after.has_value() && written == *stop_after && written < bytes.size()) {
    return std::string("simulated partial write");
  }
  return std::nullopt;
}

[[nodiscard]] auto file_identity(const std::filesystem::path& path) -> FileIdentity {
  const FileDescriptor descriptor(::open(path.c_str(), O_RDONLY | O_CLOEXEC));
  if (descriptor.get() < 0) {
    return {false, 0U, {}, errno_failure("open for readback")};
  }
  struct stat status{};
  if (::fstat(descriptor.get(), &status) != 0 || status.st_size < 0) {
    return {false, 0U, {}, errno_failure("fstat")};
  }
  EVP_MD_CTX* raw_context = EVP_MD_CTX_new();
  if (raw_context == nullptr) {
    return {false, 0U, {}, "OpenSSL SHA-256 context allocation failed"};
  }
  struct ContextGuard final {
    EVP_MD_CTX* context;
    ~ContextGuard() { EVP_MD_CTX_free(context); }
  } guard{raw_context};
  if (EVP_DigestInit_ex(raw_context, EVP_sha256(), nullptr) != 1) {
    return {false, 0U, {}, "OpenSSL SHA-256 initialization failed"};
  }
  std::array<std::byte, std::size_t{64U} * 1024U> buffer{};
  std::uint64_t count = 0U;
  while (true) {
    const auto read_count = ::read(descriptor.get(), buffer.data(), buffer.size());
    if (read_count < 0 && errno == EINTR) {
      continue;
    }
    if (read_count < 0) {
      return {false, 0U, {}, errno_failure("readback")};
    }
    if (read_count == 0) {
      break;
    }
    const auto unsigned_count = static_cast<std::uint64_t>(read_count);
    if (unsigned_count > std::numeric_limits<std::uint64_t>::max() - count ||
        EVP_DigestUpdate(raw_context, buffer.data(),
                         static_cast<std::size_t>(read_count)) != 1) {
      return {false, 0U, {}, "readback size or SHA-256 update failed"};
    }
    count += unsigned_count;
  }
  std::array<unsigned char, 32> digest{};
  unsigned int digest_size = 0U;
  if (EVP_DigestFinal_ex(raw_context, digest.data(), &digest_size) != 1 ||
      digest_size != digest.size()) {
    return {false, 0U, {}, "OpenSSL SHA-256 finalization failed"};
  }
  constexpr char hex[] = "0123456789abcdef";
  std::string digest_hex;
  digest_hex.resize(64U);
  for (std::size_t index = 0U; index < digest.size(); ++index) {
    digest_hex[index * 2U] = hex[digest[index] >> 4U];
    digest_hex[index * 2U + 1U] = hex[digest[index] & 0x0fU];
  }
  return {true, count, std::move(digest_hex), {}};
}

[[nodiscard]] auto publish_one(const LocalRunStoreConfig& config,
                               const std::filesystem::path& run_directory,
                               std::size_t domain_index, std::string_view object_id,
                               std::span<const std::byte> bytes,
                               std::string_view expected_sha256)
    -> std::variant<CopyEvidence, std::string> {
  const auto name = object_name(object_id);
  const auto staging = run_directory / "staging" / name;
  const auto published = run_directory / "objects" / name;
  const FileDescriptor output(
      ::open(staging.c_str(), O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC, 0440));
  if (output.get() < 0) {
    return errno_failure("unique staging create");
  }
  if (config.fault.point == PublicationFaultPoint::storage_exhausted &&
      config.fault.domain_index == domain_index) {
    return std::string("simulated storage exhaustion (ENOSPC)");
  }
  const bool partial =
      config.fault.point == PublicationFaultPoint::partial_staging_write &&
      config.fault.domain_index == domain_index;
  const auto write_error =
      write_complete(output.get(), bytes,
                     partial ? std::optional<std::uint64_t>{config.fault.partial_bytes}
                             : std::nullopt);
  if (write_error.has_value()) {
    return *write_error;
  }
  if (::fsync(output.get()) != 0) {
    return errno_failure("staging fsync");
  }
  if (config.fault.point == PublicationFaultPoint::after_staging_sync &&
      config.fault.domain_index == domain_index) {
    return std::string("simulated crash after staging sync");
  }
  const auto staging_identity = file_identity(staging);
  if (!staging_identity.ok || staging_identity.byte_count != bytes.size() ||
      staging_identity.sha256 != expected_sha256) {
    return staging_identity.ok ? std::string("staging readback identity mismatch")
                               : staging_identity.failure;
  }
  if (::link(staging.c_str(), published.c_str()) != 0) {
    return errno_failure("atomic no-replace publication");
  }
  if (!fsync_directory(run_directory / "objects")) {
    return std::string("published-object directory fsync failed");
  }
  auto published_identity = file_identity(published);
  if (!published_identity.ok) {
    return published_identity.failure;
  }
  if (config.fault.point == PublicationFaultPoint::readback_mismatch &&
      config.fault.domain_index == domain_index && published_identity.ok) {
    published_identity.sha256.assign(64U, '0');
  }
  const bool verified = published_identity.ok &&
                        published_identity.byte_count == bytes.size() &&
                        published_identity.sha256 == expected_sha256;
  CopyEvidence evidence{config.domains[domain_index].storage_domain_id,
                        published.string(),
                        published_identity.byte_count,
                        published_identity.sha256,
                        config.verification_timestamp,
                        true,
                        verified};
  if (!verified) {
    return evidence;
  }
  if (::unlink(staging.c_str()) != 0 || !fsync_directory(run_directory / "staging")) {
    return std::string("verified publication retained but staging cleanup failed");
  }
  return evidence;
}

[[nodiscard]] auto persist_ledger(const LocalRunStoreConfig& config,
                                  const std::filesystem::path& run_directory,
                                  const LedgerPublication& publication) -> bool {
  if (config.fault.point == PublicationFaultPoint::before_ledger_write) {
    return false;
  }
  const auto name = object_name(publication.record_id);
  const auto staging = run_directory / "ledger-staging" / name;
  const auto published = run_directory / "ledger" / name;
  const FileDescriptor output(
      ::open(staging.c_str(), O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC, 0440));
  if (output.get() < 0) {
    return false;
  }
  const auto bytes = std::span<const std::byte>(
      reinterpret_cast<const std::byte*>(publication.bytes.data()),
      publication.bytes.size());
  const bool partial =
      config.fault.point == PublicationFaultPoint::partial_ledger_write;
  const auto error =
      write_complete(output.get(), bytes,
                     partial ? std::optional<std::uint64_t>{config.fault.partial_bytes}
                             : std::nullopt);
  if (error.has_value() || ::fsync(output.get()) != 0) {
    return false;
  }
  const auto expected_sha256 = bytes_sha256(publication.bytes);
  const auto staging_identity = file_identity(staging);
  if (!staging_identity.ok || staging_identity.byte_count != publication.bytes.size() ||
      staging_identity.sha256 != expected_sha256) {
    return false;
  }
  if (::link(staging.c_str(), published.c_str()) != 0 ||
      !fsync_directory(run_directory / "ledger")) {
    return false;
  }
  const auto published_identity = file_identity(published);
  if (!published_identity.ok ||
      published_identity.byte_count != publication.bytes.size() ||
      published_identity.sha256 != expected_sha256) {
    return false;
  }
  return ::unlink(staging.c_str()) == 0 &&
         fsync_directory(run_directory / "ledger-staging");
}

template <typename T>
[[nodiscard]] auto fail(protocol::ErrorCategory category, std::string path,
                        std::string rule, std::string message) -> protocol::Result<T> {
  return protocol::Result<T>::failure(
      {category, std::move(path), std::move(rule), std::move(message)});
}

} // namespace

LocalAppendOnlyRunStore::LocalAppendOnlyRunStore(LocalRunStoreConfig config)
    : config_(std::move(config)) {
  if (config_.run_id.empty() || config_.verification_timestamp.empty()) {
    throw StorageSetupError("run store requires explicit run ID and timestamp");
  }
  if (config_.domains.size() != 2U || config_.domains[0].storage_domain_id.empty() ||
      config_.domains[1].storage_domain_id.empty() ||
      config_.domains[0].storage_domain_id == config_.domains[1].storage_domain_id) {
    throw StorageSetupError(
        "DUR2 local store requires exactly two distinct storage domain IDs");
  }
  require_directory(config_.domains[0].root, "primary storage root");
  require_directory(config_.domains[1].root, "secondary storage root");
  std::error_code first_error;
  std::error_code second_error;
  const auto first =
      std::filesystem::weakly_canonical(config_.domains[0].root, first_error);
  const auto second =
      std::filesystem::weakly_canonical(config_.domains[1].root, second_error);
  if (first_error || second_error || first == second) {
    throw StorageSetupError("storage roots must be two distinct canonical paths");
  }

  run_directories_.reserve(config_.domains.size());
  for (const auto& domain : config_.domains) {
    const auto run_directory = domain.root / run_name(config_.run_id);
    if (config_.open_mode == RunStoreOpenMode::create_new) {
      create_unique_directory(run_directory, "append-only run directory");
      create_unique_directory(run_directory / "staging", "run staging directory");
      create_unique_directory(run_directory / "objects", "run objects directory");
      create_unique_directory(run_directory / "ledger-staging",
                              "run ledger-staging directory");
      create_unique_directory(run_directory / "ledger", "run ledger directory");
      if (!fsync_directory(run_directory) || !fsync_directory(domain.root)) {
        throw StorageSetupError("run-directory durability sync failed");
      }
    } else {
      require_directory(run_directory, "existing append-only run directory");
      require_directory(run_directory / "staging", "existing staging directory");
      require_directory(run_directory / "objects", "existing objects directory");
      require_directory(run_directory / "ledger-staging",
                        "existing ledger-staging directory");
      require_directory(run_directory / "ledger", "existing ledger directory");
    }
    run_directories_.push_back(run_directory);
  }
}

auto LocalAppendOnlyRunStore::publish(const PublishObjectRequest& request)
    -> protocol::Result<PublishObjectResult> {
  if (config_.open_mode == RunStoreOpenMode::recover_existing) {
    return fail<PublishObjectResult>(
        protocol::ErrorCategory::immutable_configuration, "$input", "STO-RECOVERY-ONLY",
        "an existing run directory may only recover exact staging objects");
  }
  if (request.object_id.empty() || request.object_role.empty() ||
      request.artifact_id.empty() || request.ledger_record_id.empty()) {
    return fail<PublishObjectResult>(
        protocol::ErrorCategory::invalid_id, "$input", "STO-PUBLISH-ID",
        "publication identities and role must be nonempty");
  }
  if (!object_ids_.insert(request.object_id).second) {
    return fail<PublishObjectResult>(
        protocol::ErrorCategory::duplicate_value, "$input/object_id",
        "STO-DUPLICATE-OBJECT-ID",
        "append-only object ID is already reserved and cannot be overwritten");
  }
  if (!artifact_ids_.insert(request.artifact_id).second) {
    return fail<PublishObjectResult>(
        protocol::ErrorCategory::duplicate_value, "$input/artifact_id",
        "STO-DUPLICATE-ARTIFACT-ID",
        "artifact ID is already reserved and cannot identify another object");
  }
  const auto actual_sha = workload::sha256(request.bytes).hex();
  std::vector<CopyEvidence> copies;
  std::vector<std::string> failures;
  if (actual_sha != request.expected_sha256) {
    failures.emplace_back("input bytes do not match expected SHA-256");
  } else {
    for (std::size_t index = 0U; index < run_directories_.size(); ++index) {
      const auto result =
          publish_one(config_, run_directories_[index], index, request.object_id,
                      request.bytes, request.expected_sha256);
      if (const auto* copy = std::get_if<CopyEvidence>(&result); copy != nullptr) {
        copies.push_back(*copy);
        if (!copy->verified) {
          failures.emplace_back("domain " + copy->storage_domain_id +
                                " readback identity mismatch");
          break;
        }
      } else {
        failures.push_back(config_.domains[index].storage_domain_id + ": " +
                           std::get<std::string>(result));
        break;
      }
      if (index == 0U &&
          config_.fault.point == PublicationFaultPoint::after_primary_publish) {
        failures.emplace_back("simulated crash after primary publication");
        break;
      }
    }
  }
  const bool complete =
      request.stream_completeness == StreamCompleteness::sealed_complete &&
      copies.size() == 2U && copies[0].verified && copies[1].verified &&
      failures.empty();
  const auto state = complete ? CopyFinalizationState::sealed_complete
                              : CopyFinalizationState::incomplete;
  auto ledger = make_copy_ledger_document(
      {request.ledger_record_id, config_.run_id, request.object_id, request.object_role,
       request.artifact_id, static_cast<std::uint64_t>(request.bytes.size()),
       request.expected_sha256, request.stream_completeness, state, copies, failures});
  if (!ledger) {
    return protocol::Result<PublishObjectResult>::failure(ledger.errors());
  }
  const bool persisted =
      persist_ledger(config_, run_directories_.front(),
                     {request.ledger_record_id, ledger.value().bytes});
  if (!persisted) {
    failures.emplace_back("copy ledger persistence failed");
    ledger = make_copy_ledger_document(
        {request.ledger_record_id, config_.run_id, request.object_id,
         request.object_role, request.artifact_id,
         static_cast<std::uint64_t>(request.bytes.size()), request.expected_sha256,
         request.stream_completeness, CopyFinalizationState::incomplete, copies,
         failures});
    if (!ledger) {
      return protocol::Result<PublishObjectResult>::failure(ledger.errors());
    }
  }
  return protocol::Result<PublishObjectResult>::success(
      {persisted ? state : CopyFinalizationState::incomplete, copies, failures,
       ledger.value(), persisted});
}

auto LocalAppendOnlyRunStore::recover_staging(std::size_t domain_index,
                                              std::string_view object_id,
                                              std::uint64_t expected_byte_count,
                                              std::string_view expected_sha256)
    -> RecoveryResult {
  if (domain_index >= run_directories_.size() || object_id.empty()) {
    return {false, false, std::nullopt, "invalid recovery domain or object ID"};
  }
  const auto name = object_name(object_id);
  const auto staging = run_directories_[domain_index] / "staging" / name;
  const auto published = run_directories_[domain_index] / "objects" / name;
  std::error_code error;
  if (std::filesystem::exists(published, error) && !error) {
    const auto identity = file_identity(published);
    const bool verified = identity.ok && identity.byte_count == expected_byte_count &&
                          identity.sha256 == expected_sha256;
    if (!verified) {
      return {false, true, std::nullopt,
              "existing published object disagrees with expected identity"};
    }
    return {false,
            true,
            CopyEvidence{config_.domains[domain_index].storage_domain_id,
                         published.string(), identity.byte_count, identity.sha256,
                         config_.verification_timestamp, true, true},
            {}};
  }
  const auto identity = file_identity(staging);
  if (!identity.ok || identity.byte_count != expected_byte_count ||
      identity.sha256 != expected_sha256) {
    return {false, false, std::nullopt,
            identity.ok ? "staging candidate identity mismatch" : identity.failure};
  }
  if (::link(staging.c_str(), published.c_str()) != 0 ||
      !fsync_directory(run_directories_[domain_index] / "objects")) {
    return {false, false, std::nullopt, errno_failure("recovery no-replace publish")};
  }
  const auto final_identity = file_identity(published);
  const bool verified = final_identity.ok &&
                        final_identity.byte_count == expected_byte_count &&
                        final_identity.sha256 == expected_sha256;
  if (!verified) {
    return {true, false, std::nullopt,
            "recovered publication failed independent readback"};
  }
  return {true,
          false,
          CopyEvidence{config_.domains[domain_index].storage_domain_id,
                       published.string(), final_identity.byte_count,
                       final_identity.sha256, config_.verification_timestamp, true,
                       true},
          {}};
}

auto LocalAppendOnlyRunStore::artifact_uri(std::size_t domain_index,
                                           std::string_view object_id) const
    -> std::string {
  if (domain_index >= run_directories_.size() || object_id.empty()) {
    throw StorageSetupError("artifact URI request has invalid domain or object ID");
  }
  return (run_directories_[domain_index] / "objects" / object_name(object_id)).string();
}

} // namespace cpu_prefetch::storage
