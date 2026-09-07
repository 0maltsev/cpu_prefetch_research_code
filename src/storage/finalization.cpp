#include "cpu_prefetch/storage/finalization.hpp"

#include "cpu_prefetch/workload/deterministic.hpp"

#include <utility>

namespace cpu_prefetch::storage {
namespace {

template <typename T>
[[nodiscard]] auto fail(protocol::ErrorCategory category, std::string path,
                        std::string rule, std::string message) -> protocol::Result<T> {
  return protocol::Result<T>::failure(
      {category, std::move(path), std::move(rule), std::move(message)});
}

[[nodiscard]] auto is_complete(const PublishObjectResult& result) noexcept -> bool {
  return result.finalization_state == CopyFinalizationState::sealed_complete &&
         result.ledger_persisted;
}

[[nodiscard]] auto has_verified_primary(const PublishObjectResult& result) noexcept
    -> bool {
  return !result.copies.empty() && result.copies.front().verified;
}

void append_publish_failures(std::string_view prefix, const PublishObjectResult& result,
                             std::vector<std::string>& failures) {
  for (const auto& failure : result.failures) {
    failures.emplace_back(std::string(prefix) + ": " + failure);
  }
}

[[nodiscard]] auto publish_stream(LocalAppendOnlyRunStore& store,
                                  const RawStreamPublicationPlan& plan,
                                  const ArtifactRefText& integrity_reference)
    -> protocol::Result<PublishedRawStream> {
  if (plan.snapshot.completeness == StreamCompleteness::writing) {
    return fail<PublishedRawStream>(protocol::ErrorCategory::cross_field,
                                    "$input/snapshot", "STO-UNSEALED-STREAM",
                                    "a writing stream cannot be finalized");
  }
  const auto sha = workload::sha256(plan.snapshot.bytes).hex();
  auto raw = store.publish({plan.raw.object_id,
                            plan.snapshot.stream_kind == protocol::StreamKind::producer
                                ? "PRODUCER_RAW"
                                : "CONSUMER_RAW",
                            plan.raw.artifact_id, plan.raw.ledger_record_id,
                            plan.snapshot.bytes, sha, plan.snapshot.completeness});
  if (!raw) {
    return protocol::Result<PublishedRawStream>::failure(raw.errors());
  }

  std::optional<RawEnvelopeDocument> envelope_document;
  std::optional<PublishObjectResult> envelope_result;
  if (has_verified_primary(raw.value())) {
    auto envelope = make_external_raw_envelope(
        {plan.raw.artifact_id,
         std::string(plan.snapshot.run_id),
         plan.snapshot.stream_kind,
         store.artifact_uri(0U, plan.raw.object_id),
         plan.snapshot.row_count,
         static_cast<std::uint64_t>(plan.snapshot.bytes.size()),
         sha,
         integrity_reference,
         {}});
    if (!envelope) {
      return protocol::Result<PublishedRawStream>::failure(envelope.errors());
    }
    const auto envelope_bytes = std::span<const std::byte>(
        reinterpret_cast<const std::byte*>(envelope.value().document.bytes.data()),
        envelope.value().document.bytes.size());
    auto published_envelope = store.publish(
        {plan.envelope.object_id, "RAW_OBSERVATION_ENVELOPE", plan.envelope.artifact_id,
         plan.envelope.ledger_record_id, envelope_bytes,
         envelope.value().document.sha256, StreamCompleteness::sealed_complete});
    if (!published_envelope) {
      return protocol::Result<PublishedRawStream>::failure(published_envelope.errors());
    }
    envelope_document = envelope.value();
    envelope_result = published_envelope.value();
  }
  return protocol::Result<PublishedRawStream>::success(
      {raw.value(), std::move(envelope_document), std::move(envelope_result)});
}

} // namespace

auto finalize_run_observations(LocalAppendOnlyRunStore& store,
                               const RunObservationFinalizationRequest& request)
    -> protocol::Result<RunObservationFinalizationResult> {
  if (request.run_id.empty() || request.integrity.run_id != request.run_id ||
      request.integrity_publication.artifact_id != request.integrity.artifact_id) {
    return fail<RunObservationFinalizationResult>(
        protocol::ErrorCategory::reference_mismatch, "$input", "STO-FINALIZE-RUN-ID",
        "finalization, integrity, and publication identities disagree");
  }
  for (const auto* stream : {request.producer ? &*request.producer : nullptr,
                             request.consumer ? &*request.consumer : nullptr}) {
    if (stream != nullptr && stream->snapshot.run_id != request.run_id) {
      return fail<RunObservationFinalizationResult>(
          protocol::ErrorCategory::reference_mismatch, "$input/stream/run_id",
          "STO-FINALIZE-STREAM-ID", "stream run_id disagrees with finalization run_id");
    }
  }
  auto integrity_document = make_phase_integrity_document(request.integrity);
  if (!integrity_document) {
    return protocol::Result<RunObservationFinalizationResult>::failure(
        integrity_document.errors());
  }
  const auto integrity_bytes = std::span<const std::byte>(
      reinterpret_cast<const std::byte*>(integrity_document.value().bytes.data()),
      integrity_document.value().bytes.size());
  auto integrity = store.publish(
      {request.integrity_publication.object_id, "PHASE_INTEGRITY_REPORT",
       request.integrity_publication.artifact_id,
       request.integrity_publication.ledger_record_id, integrity_bytes,
       integrity_document.value().sha256, StreamCompleteness::sealed_complete});
  if (!integrity) {
    return protocol::Result<RunObservationFinalizationResult>::failure(
        integrity.errors());
  }

  std::vector<std::string> failures;
  append_publish_failures("phase integrity", integrity.value(), failures);
  const ArtifactRefText integrity_reference{request.integrity.artifact_id,
                                            integrity_document.value().sha256};
  std::optional<PublishedRawStream> producer;
  std::optional<PublishedRawStream> consumer;
  if (request.producer.has_value()) {
    auto result = publish_stream(store, *request.producer, integrity_reference);
    if (!result) {
      return protocol::Result<RunObservationFinalizationResult>::failure(
          result.errors());
    }
    append_publish_failures("producer raw", result.value().raw, failures);
    const auto& producer_envelope = result.value().envelope;
    if (producer_envelope.has_value()) {
      append_publish_failures("producer envelope", *producer_envelope, failures);
    } else {
      failures.emplace_back(
          "producer envelope absent because no verified primary exists");
    }
    if (request.producer->snapshot.overflowed) {
      failures.emplace_back(
          "BUFFER_OVERFLOW: invalidating measurement failure; rows were not truncated");
    }
    producer = result.value();
  } else {
    failures.emplace_back("producer stream absent; no artifact fabricated");
  }
  if (request.consumer.has_value()) {
    auto result = publish_stream(store, *request.consumer, integrity_reference);
    if (!result) {
      return protocol::Result<RunObservationFinalizationResult>::failure(
          result.errors());
    }
    append_publish_failures("consumer raw", result.value().raw, failures);
    const auto& consumer_envelope = result.value().envelope;
    if (consumer_envelope.has_value()) {
      append_publish_failures("consumer envelope", *consumer_envelope, failures);
    } else {
      failures.emplace_back(
          "consumer envelope absent because no verified primary exists");
    }
    if (request.consumer->snapshot.overflowed) {
      failures.emplace_back(
          "BUFFER_OVERFLOW: invalidating measurement failure; rows were not truncated");
    }
    consumer = result.value();
  } else {
    failures.emplace_back("consumer stream absent; no artifact fabricated");
  }

  const auto stream_complete = [](const std::optional<PublishedRawStream>& stream) {
    return stream.has_value() && is_complete(stream->raw) &&
           stream->envelope.has_value() && is_complete(*stream->envelope);
  };
  const bool complete = request.measurement_completed &&
                        is_complete(integrity.value()) && stream_complete(producer) &&
                        stream_complete(consumer) && failures.empty();
  if (!request.measurement_completed) {
    failures.emplace_back(
        "measurement did not complete; finalization remains incomplete");
  }
  return protocol::Result<RunObservationFinalizationResult>::success(
      {complete ? CopyFinalizationState::sealed_complete
                : CopyFinalizationState::incomplete,
       integrity.value(), std::move(producer), std::move(consumer),
       std::move(failures)});
}

} // namespace cpu_prefetch::storage
