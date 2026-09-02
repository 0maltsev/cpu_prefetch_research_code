# ADR-0134: Stage 17 read-only preflight archive identity source

- **Status:** `ACCEPTED`
- **Decision ID:** D-134
- **Classification:** implementation correctness, latent defect predating
  this session, semantic-context wiring for a fixed observation
- **Owner:** repository/platform/security/pilot owner
- **Gate:** before any real `S17-EXT-001` read-only preflight action can
  execute against any pilot-candidate bundle generation newer than
  `STAGE17-PILOT-CANDIDATE-BUNDLE-v1`

## Context

Unlike ADR-0130/ADR-0131/ADR-0132 (latent defects this session's real
executions first reached) and unlike ADR-0133 (a defect this session
itself introduced), this defect predates the whole real-admission effort
and was masked by two earlier, unrelated problems until now: the sixth
real `S17-EXT-001` admission's real `--execute` failed with
`REMOTE_NONZERO_EXIT`/`RuntimeError: archive size` at observation
`S17-RO-PREFLIGHT-002-ARCHIVE-AND-SIDECAR-BYTE-VERIFICATION`, and the
seventh real admission -- against the identical real, byte-verified
`STAGE17-PILOT-CANDIDATE-BUNDLE-v11` archive, independently confirmed
present on both the local machine and the real stand with matching size
(9,850,147 bytes) and SHA-256 (`b1a696cf...`) both before and after the
failure -- failed with the exact same error a second time.

Reading `resolution.semantic_context["pilot_contract"]` directly and
read-only for the real evidence-7 journal (no SSH, no stand contact)
shows it resolves to the full parsed contents of `config/stage17/
stage17-pilot-candidate-external-contract-v1.json`: a static,
catalog-pinned file (`catalog["fixed_evidence_contracts"][0]`, itself
part of the frozen genesis) describing the very first pilot-candidate
bundle ever sealed in this repository -- `source_revision` `2b4f16c...`,
`bundle_profile` `STAGE17-PILOT-CANDIDATE-BUNDLE-v1`, archive size
5,582,257 bytes, 171 files. `tools/stage17_read_only_preflight_semantic_
verifier_v15.py` (~line 578-590) builds the fixed observation's
`collector_context["archive_size_bytes"]`/`archive_sha256`/`sidecar_
size_bytes`/`sidecar_sha256`/`manifest_sha256`/`internal_file_count`
entirely from this static `pilot_contract`, not from whatever archive
was actually passed to `author-ext001` and actually staged on the stand.
Confirmed directly, not assumed: `tools/stage17_operational_cli_v11.py`'s
`author_ext001` (~line 992-1050) validates only that `pilot_archive`/
`pilot_sidecar`/`bundle_root_locator` exist and are not symlinks -- it
never computes or records their real size/SHA-256 anywhere. The dynamic,
correct part of `contract["pilot_candidate"]` is only `archive_locator`/
`sidecar_locator`/`bundle_root_locator` (plain path strings); the
identity those paths are checked against on the real stand is always the
frozen v1 baseline, regardless of which bundle generation is passed.

This file's own `custody_recovery.acceptance_rule` text --
`REBUILT_ARCHIVE_AND_SIDECAR_MUST_MATCH_EVERY_CONTRACTED_BYTE_SIZE_AND_
SHA256_OR_S17_EXT_006_REMAINS_UNRESOLVED` -- and `tools/check_stage17_
pilot_candidate_artifact.py`'s own default (`DEFAULT_CONTRACT` = the same
v1 file, overridable only via an explicit, never-used `--contract` flag)
both indicate this file's real purpose is pinning a permanent,
reproducible-build baseline for **S17-EXT-006** (release custody), a
separate external input this repository has not yet resolved for real.
`S17-EXT-001`'s fixed action plan reusing it as the expected identity for
whatever candidate bundle is actually being preflighted is a conceptual
mismatch, not a missing-file omission: no `stage17-pilot-candidate-
external-contract-v11.json` should be authored to "catch up" the frozen
baseline, since `S17-EXT-006`'s reproducibility claim is specifically
about the original `2b4f16c` revision. `S17-EXT-001`'s own archive check
must instead verify the remote bytes match what was actually captured
and admitted for the current resolution.

Real evidence preserved from both failures: `/home/omaltsev/stage17-
owner-evidence/ext001-preflight-output/stage17-read-only-preflight-
failure-v8.json` (sixth admission) and `/home/omaltsev/stage17-owner-
evidence/ext001-preflight-output-7/stage17-read-only-preflight-failure-
v8.json` (seventh admission), both `reason_category: REMOTE_NONZERO_EXIT`,
`failed_observation_id: S17-RO-PREFLIGHT-002-ARCHIVE-AND-SIDECAR-BYTE-
VERIFICATION`, `failed_stage: TRANSPORT`, `retry_allowed: false`,
`terminal_cleanup_outcome: NORMAL_LEADER_REAPED_GROUP_QUIESCENT`. Neither
attempt retried the one-shot action; both journals were confirmed
unaffected (each stayed at 1 resolution/1 transition,
`AUTHORIZED_FOR_READ_ONLY_PREFLIGHT`).

## Decision

Add `config/schemas/stage17-read-only-preflight-supporting-contract-
v14.schema.json` as an additive successor to `v13`, adding required
fields under `pilot_candidate` for the *actually captured* archive and
sidecar identity: `archive_size_bytes`, `archive_sha256`, `sidecar_size_
bytes`, `sidecar_sha256`, `manifest_sha256`, `internal_file_count` (the
same six values `collector_context` ultimately needs), leaving `contract`
(the pointer to the frozen `S17-EXT-006` baseline file) present and
unchanged in meaning -- it stays available for a future `S17-EXT-006`
resolution but is no longer read for `S17-EXT-001`'s archive check.

`author_ext001` gains a successor in `tools/stage17_operational_cli_v11.py`
(edited in place, per this repository's own established precedent: no
sealed `S17-EXT-001` envelope pins `cli_v11.py`'s own bytes, only the
preflight-plan policy's `implementations` entries) that computes these
six values for real, directly from the `pilot_archive`/`pilot_sidecar`/
`bundle_root_locator` paths actually passed on the command line -- archive
and sidecar size/SHA-256 via the same `streaming_binding` helper already
used for `pinned_known_hosts`/`transport_identity`; `manifest_sha256`/
`internal_file_count` by reading `bundle_root_locator/BUNDLE_MANIFEST.json`
and counting `SHA256SUMS` entries, mirroring the read already performed
inside `verify_pilot_candidate_artifact` -- and records them into the new
`supporting-contract-v14` fields, using schema version `cpu-prefetch-
stage17-read-only-preflight-supporting-contract/14`.

Add `tools/stage17_read_only_preflight_semantic_verifier_v16.py` as an
additive successor to `v15`, identical except its `collector_context`
construction reads `archive_size_bytes`/`archive_sha256`/`sidecar_size_
bytes`/`sidecar_sha256`/`manifest_sha256`/`internal_file_count` from the
resolution's own captured `contract["pilot_candidate"]` fields (the real,
just-admitted bundle) instead of from `semantic_context["pilot_
contract"]` (the frozen `S17-EXT-006` baseline, no longer consulted for
this purpose at all).

`tools/stage17_read_only_preflight_executor_v18.py` is an additive
successor to `v17`, identical except `import stage17_read_only_preflight_
semantic_verifier_v16 as current_semantic`, with `current_journal`
proactively rebound to whatever journal generation `cli_v11.py` uses once
this ADR's own preflight-plan/operational-policy successors exist, per
the lockstep lesson ADR-0130/ADR-0131/ADR-0132/ADR-0133 already
established. `EXECUTOR_ID` updates to `v18`.

A new preflight-plan policy successor (mirroring `v19`) rebinds
`implementations.executor` to `v18` and `implementations.semantic_
verifier` to `v16` and records the new `supporting_contract_schema_
identity`; a new operational-policy successor (mirroring `v27`) binds the
new files' real hashes; `cli_v11.py`'s `journal_runtime` import and
`author-ext001`'s `policy_path` literal are repointed so a new real
`S17-EXT-001` admission uses the corrected chain. As every prior ADR in
this chain already establishes for the same structural reason: the
seventh real resolution, already admitted under the ADR-0133 chain, is
permanently pinned to the old `semantic_verifier_v15`/`supporting-
contract/13` wiring and can never be executed by this fix either. An
**eighth** real `S17-EXT-001` admission, against this new chain, will be
required before a real execution can succeed. Sealing a new real bundle
(mirroring `v8`/`v9`/`v10`/`v11`) containing this fix is also required,
since the new executor/semantic-verifier/schema files must themselves be
present in whatever bundle is staged and checked on the stand.

## Effects

Fixes the real, reproduced, deterministic `REMOTE_NONZERO_EXIT`/`archive
size` failure that stops the fixed action plan's second observation from
ever passing against any pilot-candidate bundle newer than the very first
one ever sealed, on any real host -- this was never transient; it was
masked by two unrelated earlier problems (a missing local `--execute`
privilege, then a bundle not yet staged on the stand) until this session's
sixth and seventh real admissions both reached it and both failed
identically. No scientific design, transport mechanics, credential
handling, security guarantee, or SSH/fixed six-observation action plan
*structure* changes -- only which source `collector_context`'s archive/
sidecar identity is drawn from for `S17-EXT-001` specifically. Does not
touch the genesis graph/catalog, `S17-EXT-006`'s own frozen baseline
contract, or any file any other accepted ADR's closure depends on. Does
not by itself make the seventh resolution executable (it is pinned to the
old wiring forever, same structural reason as every prior ADR in this
chain); it only removes a defect that would otherwise reproduce on any
real host, including an eighth resolution admitted after this fix.

## Verification and supersession

Acceptance requires: a positive regression proving a `v14` supporting
contract authored against the real `v11` bundle records `archive_size_
bytes: 9850147`/`archive_sha256: b1a696cf...` (the real, independently
verified values) rather than the `v1` baseline's `5582257`/`d1c44bc0...`;
a positive regression proving `semantic_verifier_v16`'s `collector_
context` for that resolution embeds the same real values, and that a
locally rendered `S17-RO-PREFLIGHT-002-ARCHIVE-AND-SIDECAR-BYTE-
VERIFICATION` program's embedded `expected_archive_size` literal equals
the real archive's real, current size on disk; a regression proving the
`v13`/`v15` chain (and `check_stage17_executor_v13` through `v17_action_
readiness.py`) remain completely unaffected and importable/usable exactly
as before; confirmation via `git diff` that no file in any previously
accepted or accepted-adjacent closure changed, and specifically that
`config/stage17/stage17-pilot-candidate-external-contract-v1.json` and
the genesis graph/catalog are untouched. Any later change to which source
feeds a fixed observation's `collector_context` requires another
prospective successor under the same standard applied since ADR-0108.
