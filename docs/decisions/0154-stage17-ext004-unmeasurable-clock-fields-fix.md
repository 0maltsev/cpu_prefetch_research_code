# 0154. Stage 17 EXT-004 unmeasurable clock-pair fields fix

Status: ACCEPTED

## Context

Investigating the real path to `S17-EXT-004` admission for a fresh
journal (`standv2-17`, sealed from the `S17-EXT-006` fix), the real
`cpu_prefetch_q15_qualification_evidence_tool --kind SELECTED_PAIR_CLOCK`
invocation failed: `missing required flag: --before-block-repeat`. Its
own usage text explains why, in its own words: `--traced-call-count`/
`--traced-syscall-count`/`--before-block-repeat` "have no real source
anywhere in this codebase yet (no VDSO call/syscall tracer, no
block-repeat timestamp capture) and must never be guessed or defaulted
-- only pass them once real values exist." The tool's own real,
dedicated qualification binary, `cpu_prefetch_q15_clock_qualification_
tool --qualify-pair`, confirms the same thing independently: its raw
output "deliberately omits traced_call_count/traced_syscall_count/
before_block_repeat -- no real VDSO call/syscall tracer or
post-measurement block-repeat timestamp capture exists in this codebase
yet."

That refusal is a deliberate, working safeguard, not a bug -- confirmed
by reading `tools/q15_qualification_evidence_tool_main.cpp`'s own top
comment, which explains the CLI requires those three flags explicitly
"so a caller can only produce a SELECTED_PAIR_CLOCK envelope by supplying
real values for them from wherever they actually come from, once that
measurement exists." But every real `S17-EXT-004` admission this
engagement has ever made (`standv2-5` through `standv2-14`, confirmed by
reading their real, already-admitted `qualification-evidence-selected-
pair-clock-near-*.json` envelopes directly) carries specific,
plausible-looking values for exactly these three fields --
`traced_call_count` always numerically identical to the real
`producer_delta_count`/`consumer_delta_count`, `traced_syscall_count`
always `0`, `before_block_repeat` always `true`. Someone defeated the
tool's own safeguard by hand-typing those values past its CLI flags,
since the schema left no other way to satisfy `S17-EXT-004`'s admission.
`src/runner/qualification.cpp`'s own `make_selected_pair_clock_evidence`
requires `traced_call_count == timing::kQualificationDeltaCount` and
`traced_syscall_count == 0` for `eligible` to be true -- exactly the
values someone would need to reverse-engineer to pass the check, which
is exactly what the admitted envelopes show.

## Decision

Remove `traced_call_count`/`traced_syscall_count`/`before_block_repeat`
entirely from `SelectedPairClockInput` (`include/cpu_prefetch/runner/
qualification.hpp`), `make_selected_pair_clock_evidence` (`src/runner/
qualification.cpp`), and the CLI tool's flags (`tools/q15_qualification_
evidence_tool_main.cpp`) -- not left as an easy-to-defeat gate, since
that gate has already been defeated by hand five separate times.
Eligibility for `SELECTED_PAIR_CLOCK` now depends only on the prime/delta
read counts, window counts, and per-core/cross-core evaluator results --
all real, honestly measurable facts already produced by
`cpu_prefetch_q15_clock_qualification_tool --qualify-pair`.

Bump `kQualificationEvidenceSchemaVersion` to
`cpu-prefetch-qualification-evidence/2` (a whole-document version bump;
the other four `kind` variants' detail shapes are unchanged) and add
`config/schemas/qualification-evidence-v2.schema.json`, whose
`clock_details` drops the three fields from both `required` and
`properties`. The frozen `v1` schema is untouched, since prior journals'
already-admitted resolutions remain pinned against it.

Add `tools/stage17_operational_semantics_v8.py`: a fresh copy of
`operational_semantics_v7.py`'s `_read_artifacts_v6`/`verify_manifest_v7`
(confirmed by exact extraction), retargeted only to resolve
`QUALIFICATION_EVIDENCE` through a new `ROLE_SCHEMA_v8` pointing at the
`v2` schema -- the same free-variable-resolves-via-defining-module reason
every prior `ROLE_SCHEMA` successor in this family needed a fresh
function copy rather than a dict override alone.

Tracing the real, active `S17-EXT-004` dispatch end to end (rather than
assuming it flows through `operational_semantics_v7`'s own generic path,
as that module's docstring implies) found it does not: `stage17_semantic_
verifier_v34.py`'s override of the generic manifest dispatcher wires
`operational_semantics_v7.verify_manifest_v7` *only* for `S17-EXT-002`;
every input from `v34` down through this session's own `v40` delegates
`S17-EXT-004` unchanged, all the way to `stage17_semantic_verifier_
v14.py`'s `verify_operational_manifest` -- the real terminal handler for
`S17-EXT-002/003/004/005/007/008/009/010` collectively, which calls the
*original* frozen `operational_semantics_v4.verify_manifest_v4`. Add
`tools/stage17_semantic_verifier_v41.py`: an additive successor to
`v40` that intercepts `S17-EXT-004` specifically (mirroring the exact
scope `v22` established for `S17-EXT-006` and `v34` for `S17-EXT-002`),
calling `operational_semantics_v8.verify_manifest_v8` instead. Every
other input's dispatch, `S17-EXT-002`/`S17-EXT-006` included, is
unchanged. Add the matching `config/schemas/stage17-operational-
evidence-admission-policy-v41.schema.json` and `tools/author_stage17_
policy_v41.py`.

`stage17_state_journal_v35.py` moves its own hardcoded `semantic` import
from `stage17_semantic_verifier_v40` to `_v41`, the same "import binding
moves, call sites don't" pattern ADR-0153 already used. Moving that
import forces `tools/author_stage17_read_only_preflight_policy_v27.py`
to be re-rendered again (it independently pins `state_journal_v35.py`'s
own bytes), which in turn requires re-rendering `stage17-operational-
evidence-admission-policy-v39.json` and `-v40.json` again to pick up
the new v27 bytes -- the exact same cascade ADR-0153 already discovered
and documented; this ADR pays it again for the same structural reason.

## Consequences

- This does not merely close a session-specific gap: every real
  `S17-EXT-004` admission this whole engagement has ever made
  (`standv2-5` through `standv2-14`) was built on fabricated evidence for
  these three fields. Those journals' admissions are not retroactively
  revoked by this ADR -- they cannot be -- but this record exists so the
  fact is not silently lost.
- A fresh journal is required to admit a real, honest `S17-EXT-004` for
  the first time, requiring a fresh live Q15-R session (this fix's own
  C++ rebuild changes the worker binary's embedded identity again, the
  same mechanism ADR-0153 already established, which orphans
  `standv2-17`'s already-completed but not-yet-admitted Q15-R session).
- `S17-EXT-005`'s own real `standv2-14` admission -- the "first-ever
  successful Q15-W admission" this engagement's own history treated as a
  milestone -- was admitted with `S17-EXT-004` as its immediate
  predecessor resolution. Since that `S17-EXT-004` rested on fabricated
  evidence, `S17-EXT-005`'s own validity is undermined by the same root
  cause, even though `S17-EXT-005`'s own admission logic itself is not
  in question.
- `S17-EXT-007` through `S17-EXT-010` were never investigated for the
  same "schema requires evidence nothing can measure" pattern before
  this fix. That investigation remains open.
