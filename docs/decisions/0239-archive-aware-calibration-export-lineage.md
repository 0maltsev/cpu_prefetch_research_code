# ADR-0239: Archive-aware calibration and export lineage

- Status: ACCEPTED — engineering compatibility; no estimator change
- Date: 2026-11-03
- Scope: /2 plan compatibility, export preparation and fail-closed signed
  archival-family bridge
- Execution authority: None

## Exact plan identity

D233 introduces an explicit archival-storage plan /2, retaining the same native
captures, scientific durations, repetitions and estimator parameters. The
original D230 evaluator calls the /1 plan validator, so a /2 plan cannot be
evaluated by that entry point. Relabelling it /1 or stripping storage fields
would change the prospective plan identity and invalidate failure-report and
downstream evidence hashes. That is not a compatibility repair.

`tools/stage17_formal_calibration_v2.py` exposes the same
`evaluate(action, plan, run_records, ring_geometry=None)` API and the unchanged
`validate_calibration_record(document)`. It binds the existing D230 evaluator
function code to private globals with its plan-validator lookup replaced
by `stage17_formal_plan_v2.validate_plan`. The latter dispatches /1 unchanged and
validates /2 through the existing native family plus D233 physical-storage
contract. For /2 only, the evaluator's canonical plan hash uses the native
JCS bytes without a trailing LF. The historical D230 /1 evaluator and signed
request/report transport retain their original trailing LF. The /2 export
probe-failure hash and signed-family phase-root hash use the same native bytes.
No shared predecessor module global is reassigned.

The exact original plan object remains the evaluator input. Its canonical
hash uses the original /2 identity, original custody/storage fields and all
original budgets. Failure receipts must bind that same hash. No projected /1
document or substitute prospective family exists. Original packet-byte SHA256
and canonical plan SHA256 retain their distinct established meanings.

All D230 count, coverage, invalid/missing-receipt, clock, rank, geometry,
distance and rational service-rate computations use unchanged function code.
The calibration result schema remains
`cpu-prefetch-stage17-formal-calibration-validation/1`: its fields and semantics
have not changed, and its plan SHA256 binds the /2 source. No scientific
parameters, retry, top-up, quantile or arithmetic rule is added.

## Export preparation successor

`tools/stage17_calibration_export_v2.py` preserves the two D237 APIs:

```text
build_export(*, identity, owner_decision, source_packets)
validate_export(document, *, owner_decision, source_packets)
```

It composes the unchanged D237 implementation in private function globals,
selecting the /2-aware plan validator and D239 calibration evaluator. The
original /2 plan packets, original calibration packets and their full lineage
are retained and checked. Its predecessor APIs continue to reject /2 plans.

This is a software adapter, not a new freeze schema. The D237 /1 export shape
remains sufficient because plan packets already carry explicit byte bindings.
Output state remains UNRESOLVED with the same explicit provenance blockers;
final matrix feasibility remains NOT_EVALUATED and both authority fields remain
false. A valid storage declaration is not proof of physical archival custody,
and an archive round trip is not scientific validation.

## Required authenticated admission integration

The completed EXT007 integration must provide a genuine scoped FROZEN route using
the existing admitted EXT001–006 journal, root, owner/trust and qualified source
bindings. D239 does not create a callback that trusts a supplied verification
boolean. The route must authenticate each v6 request/authorization signature,
attempt/result/completion lineage, chronology, restoration and quiescence, then
connect its canonical logical artifact identities to the archival registry and
representation ledger. Existing v25 `prepare_retention` authenticates a past
v6 request against the predecessor journal and qualified release, but does not
by itself validate all later attempt/completion/custody records.

The archive-aware registry under separate development is a required integration
dependency. Its full logical family must be exact; physical archive hashes and
logical original-byte hashes are different bindings. Reuse D235 verification
and bounded capture spool support for independent D220/D229 checks as required.
No fabricated original-file presence, missing failure omission or raw-validation
flag can replace those checks. D230 math and D232 original schedule provenance
then run against their exact authenticated sources. Analysis code identity is
bound separately from the original qualified capture revision.

The final admission successor must preserve legacy final-freeze semantics and
all unrelated EXT branches. Its Stage 17 scoped freeze may contain validated
d2/mu and complete provisional probe provenance while keeping final exposure
inputs and final feasibility explicitly unevaluated. No final load success or
Phase 18 authority follows. This is a concrete required next integration, not
a declaration that the preparation export alone completes EXT007.

## Signed archival-family bridge

`tools/stage17_operational_semantics_v17.py` implements
`verify_signed_formal_family` with keyword arguments:

```text
repository_root, evidence_root, historical_journal, journal_directory,
artifacts, action_id, admitted_resolutions, allow_synthetic,
pinned_repository_bytes, analysis_limits
```

`artifacts` uses the existing operational `Artifact` representation and six
action-specific authorization, signature, request, attempt, result and
completion roles. Original bytes are re-read with the existing bounded,
nonsymlink artifact reader. The bridge lazily requires actual source-pinned
`stage17_phase_controller_v26.prepare_retention` and
`stage17_output_registry_v12.verify_archived_formal_family`. Neither is replaced
by a production stub or a supplied callback. Missing module, pin or entry point
rejects. Their transitive implementation closure must also be pinned by the
integrating policy, separately from the qualified producer revision.

The controller authenticates the original v6 authority against the historical
journal. That journal must end exactly through EXT006; all six resolution IDs
and hashes must match the outer admitted predecessors. Its original bytes must
match the controller's validated latest-journal hash. A pending EXT007 journal
cannot recursively establish its own predecessors. Historical retention checks
do not authorize a new execution based on the current clock.

The bridge checks actual v6 schemas and original SSHSIG, request/authorization
hashes, phase/session/attempt identities, runtime/release references, original
root identity, durable one-attempt marker, result/completion bindings and the
complete artifact list. The authorization field is `stage18_authority`; other
v6 receipts use `phase18_authority`. Check original UTC ordering through the
attempt, native start/end and supervisor completion within the finite session
and authorization interval. Require reaped leader, gone process group,
restoration and no quarantine. Live restoration uses actual
`{cpu,expected_hex,observed_hex,matches}` rows, compared with all full admitted
prestate MSR values. Recorded resource admission must match and meet the declared
memory/disk on the original filesystem; it does not claim a reservation.

Open the signed phase root through the existing componentwise root verifier.
Its storage location is `<program>/working/<original canonical plan SHA>`.
Call the real archival registry with exactly:

```text
registry, repository_root, directory_fd, result, request,
authorization_sha256, synthetic_test_only, archive_runtime_profile, analysis_limits
```

The registry owns original-checkpoint and complete logical-to-physical inventory
verification, including qualified-decoder archive readback. Its `scope_bindings`
must match signed `program_id`, `implementation_profile_sha256` and
`program_scope_sha256`, plus exact `phase_root_binding` and independently opened
`program_root_binding`. `ledger_head` retains verified `sequence_number` and
SHA256. The initial program-scope hash binds shared intent, not a circular hash
of a phase plan. A correct scope projection alone is not archive verification.
The profile is the actual `prepared.archive_runtime_profile`, loaded against the
qualified EXT006 profile binding and bundle/runtime roots. Registry12 checks its
implementation-profile hash against signed storage; it never discovers a host
runtime by filename or trusts a custody boolean.

Registry12 preserves the original v11 dispatch and adds the native retention
report /2 schema. It checks exact family coverage, canonical output/metadata
budgets, H0 no-write and H1 reverse restoration records, the no-LF native plan
hash, all original checkpoint/custody bindings, and each outer final native
result against its original checkpoint. The shared `ProgramStore` supplies the
actual program/family root, scope and verified ledger tip. Returned inventories
bind original logical identities to exact physical archive/header/role bindings;
they do not make compressed paths interchangeable with original raw files.

Collection completion uses `verify_archived_formal_metadata` with the existing
executor's current absolute deadline and finite custody limits. It independently
checks original ledger records and receipt registration, original archive
headers, regular-file identity, and a bounded streamed whole-physical SHA. It
does not invoke a decoder or construct a `VerifiedArchive`. The output states
`inverse_readback_performed=false` and `scientific_validity=NOT_ASSESSED`.

Full retained verification requires an explicit `AnalysisLimits` object. Its
original bounded JSON bytes and physical binding identify only finite offline
resources: current monotonic deadlines, custody/decoder limits, one readback job
per original artifact, and aggregate parent + broker + codec memory. The parent
must already have its declared AS limit; registry code does not change the
controller's process-wide limit. The dedicated qualified readback client starts
a bounded broker and decoder for each job, with no retries. No historical
collection expiry is repurposed as current analysis authority. Missing client,
profile or finite resource plan rejects. Both paths retain false scientific and
execution authority; full inverse is necessary but insufficient for credit.

Return original lifecycle documents/hashes, the actual archive report and
explicit false scientific-credit, execution and Phase 18 authority boundaries.
The bridge does not execute a capture, sign, modify a journal or grant a freeze.
Any decoder invocation within the registry is bounded read-only custody work.

`verify_manifest_v17` preserves v16 dispatch for unrelated/historical branches
without changing shared module globals. New v6 EXT007 fails closed even when
the two dependencies become available: bounded actual D220/D229/D232 analysis
and scoped freeze admission have not yet been wired. No new self-attested
analysis receipt contract is introduced. The next adapter must resolve captures
through verified inventories/spools, perform actual independent checks under
pinned code and explicit aggregate bounds, and apply D230 v2 math across the
whole prospective family. This analysis is required before scientific credit,
not before archival retention or the next native capture under D233. No new
requirement for analysis during measurement or between every capture is added.

## Verification

`tests/test_stage17_calibration_export_v2.py` reuses existing small D220/D229
software report shapes and complete synthetic 708/3540/180 family metadata.
It checks unchanged derived values, original /2 plan hashes and packet bytes,
full export recomputation, original-version rejection, unchanged predecessor
globals and /1 behavior, /2 invalid-receipt hash enforcement, explicit missing
receipt UNRESOLVED behavior, storage/version/budget rejection, and refusal to
promote an export to FROZEN. No millions-of-events fixture, hardware capture or
archive-presence assertion is introduced. These pure Python changes require
accepted-runtime tests, not native sanitizer or hardware tests.

`tests/test_stage17_operational_semantics_v17.py` uses a temporary local
Ed25519 key and real SSHSIG verifier, schema-valid synthetic v6 receipts and
real temporary root metadata. It tests byte/hash/identity, timing/resource,
restoration/quiescence mutants, wrong signing namespace, historical predecessor
hashes, shared-root/profile/scope/ledger projection, missing/unpinned dependencies
and legacy dispatch. It never mocks successful production EXT007 admission.
Positive archive-registry/controller and full scientific-analysis integration
remain explicitly unverified until those components are available and connected.

`tests/test_stage17_output_registry_v12.py` checks complete 180-capture metadata,
missing/foreign bindings, original restoration order, native plan versus request
transport hashes, and a separate real nine-file archive/ledger fixture. The
small fixture exercises physical corruption, missing ledger membership, outer
final-result drift, and rejection of boolean decoder proofs. Resource tests
bind exact offline limit bytes and reject omitted aggregate memory, stale or
divergent deadlines, and incorrect decoder-job counts. These fixtures do not
claim a complete actual qualified formal family. The lower registry's metadata
tests forbid decoder invocation and detect changed headers/physical bytes.
