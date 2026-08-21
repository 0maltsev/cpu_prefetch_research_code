# Protocol and Configuration Model

## Scope

Stage 4 implemented the stable logical concepts now shared by immutable
protocols `2.0.0-pre.1` and `2.0.0-pre.2`. Its
scope did not implement a queue, raw physical format, clock reader, platform
mutation, run controller, reconciliation pipeline, or performance measurement.
The imported schemas remain authoritative and unmodified. No compatibility
schema replaces an imported schema; implementation-owned schedule, platform,
phase-integrity, copy-ledger, and join-audit schemas are explicitly subordinate
contracts and cannot extend imported logical records.

## Validation boundary

Validation is deliberately two-pass:

1. `tools/check_protocol_fixtures.py` uses pinned jsonschema 4.26.x and a Draft
   2020-12 format checker against the seven imported schemas.
2. `cpu_prefetch::protocol::Stage4SemanticValidator` checks record-local rules
   that schemas cannot prove. It never mutates or repairs an input.

The C++ loader also fails closed before constructing a typed record. Unknown
fields, versions, and enum values are rejected. Required values have no
fallback. IDs are opaque nonempty values; run/block identity is never inferred
from a filesystem path. Units must be explicit. Exact schema integers occupy a
signed or unsigned 64-bit domain and never pass through binary64. The exact
offered rate is a numerator/denominator pair.

Errors contain a stable category, JSON path, requirement/rule ID, and message.
Categories are `PARSE_ERROR`, `MISSING_FIELD`, `UNKNOWN_FIELD`,
`INVALID_TYPE`, `UNKNOWN_ENUM`, `UNSUPPORTED_VERSION`, `INVALID_ID`,
`INVALID_HASH`, `INVALID_UNIT`, `OUT_OF_RANGE`, `DUPLICATE_VALUE`,
`CROSS_FIELD`, `MISSING_EVIDENCE`, `REFERENCE_MISMATCH`,
`IMMUTABLE_CONFIGURATION`, and `UNSUPPORTED_NUMBER`.

## Typed concepts

The public model includes:

- exact protocol/schema versions, SHA-256 values, and opaque run, block,
  artifact, platform, build, schedule, namespace, seed, record, and authority
  IDs;
- all registered stage, run-mode, role, package, hardware-state, placement,
  working-set, load, lifecycle, validity, gate, estimability, completeness,
  failure, access, storage, schedule, stream, and artifact-relationship enums;
- exact-rate and RNG/schedule metadata;
- requested and independently verified hardware state;
- producer, consumer, and joined logical rows;
- raw stream envelopes, phase/integrity evidence, manifests, block plans,
  failure records, freeze/access records, amendments, and platform records.

`ScientificConfiguration` is constructed only after load and record-local
semantic validation. It exposes const access and is neither copy-assignable nor
move-assignable. This is stronger than the minimum rule: scientific
configuration cannot be mutated at all after successful loading, including
after measurement begins.

The logical source document is retained with each typed record. Canonical
round-trip tests demonstrate that serialization does not discard fields or
exact integers. Physical encodings remain behind the interface accepted in
ADR-0002. Stage 11 implements accepted `RAW-OBS-U64LE-LP-RUNID-v1` behind that
interface; strict decoding reconstructs these logical row types and applies
record-local validation before returning them.

## Record-local semantic rules implemented

Stage 4 checks:

- decoded inline schedule count, monotonicity, 64-bit overflow, exact
  half-open-horizon membership, external row count, and confirmatory arrival
  family;
- envelope/row run identity, accepted-versus-`FULL` fields, producer/consumer
  timestamp order, joined timestamp order, every derived interval equation,
  and the permitted end-to-end additive identity;
- lifecycle/failure evidence, early-failure non-fabrication, failed-join
  artifact shape, completed-valid Stage A evidence, count identities, zero
  final occupancy, and independent validity/zero-loss/effective-tail/
  estimability states; pre.1 retains its historical applicability-only
  singular contract, while pre.2 requires the D-031 exhaustive, unique,
  UTF-8-ordered blocker array and exact singular/multiple summary mapping;
- exactly 180 Stage A factor tuples and ordinals `0..179`, H0/H1 whole plots,
  ring/linked node-seed nullability, and self-contained replacement
  identity/ordinal/role/subspace rules;
- run-scoped failure identity, Stage A block consequence, and replacement
  evidence;
- record-kind-specific access states, authority roles, required hashes,
  nonempty affected blocks, all six exact H3 context keys, replacement shape,
  and amendment fields;
- explicit H0/H1 platform requests and separate verification records.

## Cross-record rules

`CrossRecordSemanticValidator` is the implementation seam for rules that
cannot be honestly proved without later immutable stores and orchestration.

Stage 12 implements:

- resolving manifest, raw, join-audit, integrity, provenance, schedule, and
  failure references to immutable bytes and matching SHA-256 values;
- reconciling producer and consumer observations by `(run_id,
  accepted_ordinal)`, proving uniqueness/order/counts and treating
  `record_index` only as validation;
- proving external decode counts, envelope/row identities, cross-stream
  timestamps, count identities from actual artifacts, and absence of joined
  data after a failed audit;
- comparing pre/post content and algorithm-identified integrity evidence;
- evaluating lifecycle completion, validity, join, count, zero-loss, tail, and
  D-031 estimability independently, with an invalidating failure record
  required for `INVALID` and no retry/replacement inference.

Stage 14 implements:

- comparing original/replacement records for distinct identity, ordinal, and
  seed subspace, equal immutable role, named failure/authority, and available
  replacement budget;
- role-compatible namespace/seed membership, exact common Stage A block-pool
  membership, and append-only plan lineage;
- predecessor-record existence/hash, access chronology, block-role/namespace
  membership, authority segregation, and the selection/unseal/evaluation/
  release chain used by orchestration.

`Stage14CrossRecordSemanticValidator` performs those checks when supplied the
explicit seed catalogs, prospective precision result, artifact access catalog,
authority policy, and replacement budget. Missing concrete freeze inputs still
block final acceptance and are never defaulted. Stage 12 leaves final
estimability `NOT_EVALUATED` until authoritative block/access results are
injected. No layer accepts an artifact as globally valid merely because its
individual JSON document or a synthetic Stage 14 graph is valid. See
[`ORCHESTRATION.md`](ORCHESTRATION.md).

## Canonical serialization

The accepted suite ID is `JCS-I64-v1`: RFC 8785 property ordering, escaping,
whitespace, and binary64 formatting, extended so every schema integer retains
its exact signed/unsigned 64-bit shortest decimal form. Duplicate object keys,
invalid UTF-8, non-finite numbers, and integers outside that domain fail.

`tests/fixtures/jcs_i64_v1.json` is shared by C++ and an independent Python
checker. It covers `2^53` boundaries, signed/unsigned limits, RFC binary64
examples, negative zero, UTF-16 property order, Unicode, and escaping.

## Compatibility

Accepted compatibility rows are pre.1 input under pre.1 rules and pre.2 input
under pre.2 rules. New documents use pre.2; a Stage 12 record graph must be
entirely pre.2. `1.x`, unknown future versions/enums/algorithm IDs, and mixed
graphs or logical-row/envelope versions fail. ADR-0025/0029 pre.1 derivation
labels remain frozen suite-domain bytes. A migration must be append-only,
versioned, provenance-bearing, and authorized by a later ADR or protocol
amendment as applicable.
