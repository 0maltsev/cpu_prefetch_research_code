#ifndef CPU_PREFETCH_STORAGE_FINALIZATION_HPP
#define CPU_PREFETCH_STORAGE_FINALIZATION_HPP

#include "cpu_prefetch/storage/artifact_store.hpp"

#include <optional>
#include <string>
#include <vector>

namespace cpu_prefetch::storage {

struct ArtifactPublicationPlan final {
  std::string object_id;
  std::string artifact_id;
  std::string ledger_record_id;
};

struct RawStreamPublicationPlan final {
  RawStreamSnapshot snapshot;
  ArtifactPublicationPlan raw;
  ArtifactPublicationPlan envelope;
};

struct RunObservationFinalizationRequest final {
  std::string run_id;
  bool measurement_completed;
  PhaseIntegrityInput integrity;
  ArtifactPublicationPlan integrity_publication;
  std::optional<RawStreamPublicationPlan> producer;
  std::optional<RawStreamPublicationPlan> consumer;
};

struct PublishedRawStream final {
  PublishObjectResult raw;
  std::optional<RawEnvelopeDocument> envelope_document;
  std::optional<PublishObjectResult> envelope;
};

struct RunObservationFinalizationResult final {
  CopyFinalizationState finalization_state;
  PublishObjectResult integrity;
  std::optional<PublishedRawStream> producer;
  std::optional<PublishedRawStream> consumer;
  std::vector<std::string> failures;
};

[[nodiscard]] auto
finalize_run_observations(LocalAppendOnlyRunStore& store,
                          const RunObservationFinalizationRequest& request)
    -> protocol::Result<RunObservationFinalizationResult>;

} // namespace cpu_prefetch::storage

#endif // CPU_PREFETCH_STORAGE_FINALIZATION_HPP
