# Stage 17 operational authorization successor

Current state: **`PREPARED`**  
Pilot execution readiness: **false**  
Stage 17 complete: **false**  
Stage 18 ready: **false**

ADR-0104 replaces the open-ended pilot governance chain with one finite graph.
ADR-0105 makes that graph persistable without rewriting history. Neither ADR
authorizes stand access or a run:

```text
PREPARED
  -> AUTHORIZED_FOR_READ_ONLY_PREFLIGHT
  -> PREFLIGHT_ACCEPTED
  -> READY_FOR_STAGE17_PHASE_AUTHORIZATION
```

The immutable
[`STAGE17-OPERATIONAL-GRAPH-v1`](../config/stage17/stage17-operational-graph-definition-v1.json)
defines the edges. The immutable
[`STAGE17-EXTERNAL-INPUT-CATALOG-v1`](../config/stage17/stage17-external-input-catalog-v1.json)
defines requirements but contains no mutable resolution status. Separate
`stage17-external-input-resolution-v1` records and
`stage17-state-transition-v1` records are referenced by hash from successive
append-only `stage17-state-journal-v1` snapshots. The checked-in
[`genesis snapshot`](../config/stage17/journal/stage17-state-journal-000000.json)
has no records, so replay computes `PREPARED`, all ten inputs missing, and
`pilot_ready=false`.

The historical successor v1 and `STAGE17-EXTERNAL-INPUTS-v1` checklist remain
byte-immutable definition/templates. Their embedded `current_state` and
per-item `status` fields are not operational state or evidence. Missing,
partial, expired, inaccessible, or hash-mismatched evidence retains the
computed state and stops without automatic retry. The final graph state permits
preparation of an exact phase authorization; it is not itself pilot execution
authority. Pilot readiness additionally requires verified resolutions for all
ten catalog inputs and an unexpired `S17-EXT-010` at an explicit evaluation
time.

`S17-EXT-006` is currently unresolved. The historical release-evidence record
still states the clean source revision and archive metadata and remains
unchanged, but metadata is not proof that the archive/sidecar bytes exist.
The new fixed
[`external custody/integration contract`](../config/stage17/stage17-pilot-candidate-external-contract-v1.json)
requires caller-supplied regular nonsymlink archive and sidecar files, exact
filenames, byte counts, SHA-256 values, sidecar bytes, safe extraction, manifest
identity, 171-entry internal checksum inventory plus its one `SHA256SUMS` file,
internal verification, and no-authority flags. Until
those exact bytes are supplied to the integration checker and a real custody
receipt is recorded, no `S17-EXT-006` resolution is valid.

For pilot governance only, `cpu-prefetch-stage17-pilot-owner` is explicitly
the owner, operator, controller, custodian, and auditor. Reviews must disclose
that collapse and may not claim independence. One hashed authorization may
cover one frozen set of read-only preflight observations; no new PKI ceremony
is required for each observation. Privileged controls and each scientific
phase remain separately bounded actions.

This relaxation does not cross the Stage 18 boundary. The imported
`PLANNED -> COLLECTED_SEALED -> TRAINING_OPEN -> SELECTION_FROZEN ->
VALIDATION_UNSEALED -> H3_EVALUATED -> H1H2_RELEASED -> ARCHIVED` chronology,
validation sealing, predecessor hashes, and release authorities remain strict.
No Stage 17 record can unseal or authorize Stage 18.

## Local verification

```sh
cmake --build --preset dev-gcc --target stage17-operational-successor-check
cmake --build --preset dev-gcc --target stage17-state-journal-check
ctest --preset dev-gcc -R 'runner.stage17_(operational_successor|state_journal)|q15.p4_r_c_executor_no_network_self_test' --output-on-failure
```

Print the computed state and authoritative unresolved-input list:

```sh
/tmp/cpu-prefetch-stage16-deps/python/bin/python \
  tools/check_stage17_state_journal.py --print-status
```

The interpreter path above is the current pre-provisioned development prefix;
another clean environment may use its recorded CMake `Python3_EXECUTABLE`.

The state-journal self-test writes every positive fixture to an isolated
directory, closes and reloads all referenced JSON files, and recomputes their
hashes. Its negative set rejects skip/backward edges, forks, replay, duplicate
sequence numbers, predecessor replacement, incomplete evidence, unknown or
expired authority, graph/catalog drift, weakened Stage 18 chronology, missing
external bytes, and the regression pair `artifact_id=DOES-NOT-EXIST` with a
syntactically valid all-`a` SHA-256.

## Exact next authorization draft

The only next operational draft is
[`S17-EXT-001 read-only preflight authorization`](STAGE17_S17_EXT_001_AUTHORIZATION_DRAFT.md).
Every real owner-supplied field is null, it is not issued, and it cannot be
used as evidence. The first resolution and transition must not be constructed
until the owner supplies the exact target, UTC window, bounds, archive paths,
six frozen read-only command vectors, executable hashes, and output locators.

## Pilot-candidate archive integration boundary

Run the integration checker only with caller-supplied real files:

```sh
cmake --preset dev-gcc \
  -DCPU_PREFETCH_STAGE17_PILOT_CANDIDATE_ARCHIVE=/absolute/custody/path/exact.tar.gz \
  -DCPU_PREFETCH_STAGE17_PILOT_CANDIDATE_SIDECAR=/absolute/custody/path/exact.tar.gz.sha256
cmake --build build/dev-gcc \
  --target stage17-pilot-candidate-artifact-integration-check
```

The command is deliberately not part of the hermetic self-test. A failed or
unavailable byte-identical archive leaves `S17-EXT-006` external-required; it
never falls back to the historical metadata record.

If no custody copy exists, the contracted recovery attempt is a clean detached
worktree at the exact source revision. Choose a new nonexistent worktree path;
the example path is fixed only for reproducibility and must not already exist:

```sh
git worktree add --detach \
  /tmp/cpu-prefetch-s17-release-2b4f16c \
  2b4f16c61c306ade5f4383ac2abb1ad709f772a8
cd /tmp/cpu-prefetch-s17-release-2b4f16c
cmake --preset release-gcc
cmake --build --preset release-gcc --target pilot-candidate-bundle
sha256sum \
  build/release-gcc/pilot-candidate-bundle/cpu-prefetch-pilot-candidate-2.0.0-2b4f16c-clean-f753c3b294b4.tar.gz \
  build/release-gcc/pilot-candidate-bundle/cpu-prefetch-pilot-candidate-2.0.0-2b4f16c-clean-f753c3b294b4.tar.gz.sha256
```

The recovered archive and sidecar must match every byte count and SHA-256 in
the fixed contract. A reproducible build claim without that exact match is a
failed recovery attempt, not release evidence.

## External qualification archive boundary

`execute_d104_p4_r_c.py --self-test` uses synthetic caller-supplied bytes and
never reads the ignored build tree. The exact historical qualification archive
is an external action input governed by
[`Q15-QUALIFICATION-ARCHIVE-EXTERNAL-CONTRACT-v1`](../config/q15/q15-qualification-archive-external-contract-v1.json).
Validate an explicit custody or rebuilt copy separately:

```sh
cmake --preset dev-gcc \
  -DCPU_PREFETCH_Q15_QUALIFICATION_ARCHIVE=/absolute/path/to/exact.tar.gz \
  -DCPU_PREFETCH_Q15_QUALIFICATION_SIDECAR=/absolute/path/to/exact.tar.gz.sha256
cmake --build build/dev-gcc --target q15-qualification-archive-integration-check
```

The contract records the source revision and candidate rebuild commands. A
rebuild is accepted only when both archive and sidecar bytes match the exact
contract; otherwise a byte-identical custody copy is required.

## Preserved predecessors

The machine-checkable
[`STAGE17-D099-D108-PRESERVATION-v1`](../config/stage17/d099-d108-preservation-manifest-v1.json)
binds every decision/evidence artifact. The D-104 preparation continues to
bind its historical executor bytes at Git revision `dc643df...`; ADR-0104 binds
the hermetic successor without rewriting that record. D-105 through D-108
remain unchanged proposed/unaccepted records and are not gates in this
successor.
