# 0175. Stage 17 `cpu-prefetch-v5` software-prefetch mapping: a second, PRFCHW-free `X86-64-PREFETCHT0-ONLY-v1`

Status: ACCEPTED

## Context

ADR-0174 (PROPOSED) documented a real, live finding on `cpu-prefetch-v5`
(Intel Xeon E5-2667 v2, Ivy Bridge-EP, family 6 model `0x3E`): building
`S17-EXT-004` against a real, held-open Q15-R session produced 4 of 5
required `QUALIFICATION_EVIDENCE` kinds with real `eligible: true`
data, but `SOFTWARE_PREFETCH_MAPPING` genuinely failed, because this
CPU lacks the PRFCHW instruction (Intel only added PRFCHW support
starting with Broadwell; confirmed both from the real captured CPUID
observation -- `producer_prfchw_supported: false`, `consumer_prfchw_
supported: false` -- and independently via a fresh `/proc/cpuinfo`
read showing no `prefetchw` flag). `include/cpu_prefetch/runner/
software_prefetch.hpp`'s own `SoftwarePrefetchCapabilityObservation::
passes()` hard-requires `prfchw_supported`, and there was exactly one
registered software-prefetch mapping in this codebase
(`kSoftwarePrefetchMappingId`, `"X86-64-PREFETCHW-PREFETCHT0-v1"`),
requiring PRFCHW for its producer-write role. ADR-0174 recorded three
undecided options; this ADR formally accepts **Option 2**: register a
second, honestly-scoped, PRFCHW-free mapping.

### Engaging with ADR-0047 honestly

ADR-0047 (the original software-prefetch-mapping design decision)
explicitly considered and rejected using `PREFETCHT0` for the
producer-write role too, reasoning that doing so would silently let a
write-intent site default to a read-intent hint on hardware that *does*
have a correct write-intent instruction (PRFCHW) available. This ADR
does not reopen that choice for PRFCHW-capable CPUs: the new mapping is
registered via a **static, CPU-family/model-keyed registry**
(`kSoftwarePrefetchMappings`, mirroring `platform.hpp`'s own
`kHardwarePrefetchMappings` pattern exactly), never a runtime capability
probe dynamically choosing behavior. Family 6 model `0x55` (`06_55H`,
the original stand) is architecturally incapable of ever resolving to
the new mapping; family 6 model `0x3E` (`06_3EH`, `cpu-prefetch-v5`) is
architecturally incapable of ever resolving to the old one. There is no
live choice point where "prefer the write-intent hint when available"
could be silently violated -- the new mapping exists only for hardware
that has no write-intent hint to lose.

## Decision

Add `kSoftwarePrefetchMappingIdT0Only` (`"X86-64-PREFETCHT0-ONLY-v1"`)
and a new concrete emitter class, `X86PrefetchT0OnlyEmitter`, with the
same three method names/signatures as the existing `X86RetainingPrefetch
Emitter` (`ring_producer_write`, `ring_consumer_read`,
`successor_header`), all three real PREFETCHT0, registered in
`kSoftwarePrefetchMappings` against `06_3EH`.

## Evidence this is load-bearing, not cosmetic

`X86RetainingPrefetchEmitter` was confirmed, by direct code read, to be
genuinely load-bearing in real measurement runs, not merely a
qualification-evidence attestation: `src/runner/stage17_fixed_
action.cpp`'s `package_capture` instantiates it once per real action
dispatch and passes it by template parameter into `workload::
R1Package<T>`/`R2Package<T>`/`L1Package<T>`, whose `try_enqueue`/
`try_dequeue` call `emitter_.ring_producer_write`/`ring_consumer_read`
on every real producer/consumer operation in Q16a/b/c/pilot/
confirmatory runs; `include/cpu_prefetch/queue/linked_spsc.hpp`'s
`try_dequeue_observed` calls `prefetch.successor_header` on every real
L1 dequeue. `tools/check_runner_combined_codegen.py` independently
confirms the exact real call-site counts.

## Implementation

- `include/cpu_prefetch/runner/software_prefetch.hpp`: added
  `kSoftwarePrefetchMappingIdT0Only`, `X86PrefetchT0OnlyEmitter`,
  `SoftwarePrefetchMapping`, `kSoftwarePrefetchMappings` (the static
  registry), and declared `find_software_prefetch_mapping`/
  `is_accepted_software_prefetch_mapping_id`; both defined in
  `src/runner/runner.cpp` alongside the existing
  `X86CurrentCpuSoftwarePrefetchCapabilityBackend::observe()`, mirroring
  `find_hardware_prefetch_mapping`'s exact shape in `platform.cpp`.
- `src/runner/qualification.cpp`'s `make_software_prefetch_mapping_
  evidence`: generalized to compute `eligible` correctly for either
  registered mapping -- the T0-only mapping's own capability requirement
  is `true` unconditionally (it never issues PRFCHW, so it needs nothing
  beyond the baseline PREFETCHT0 support every accepted x86-64 target
  already has), gated behind the mapping id actually being one of the
  two registered identities, never an unconditional pass for an
  unrecognized one. `ring_producer_instruction` is now conditional
  (`PREFETCHW` for the original, `PREFETCHT0` for the new one).
- `src/runner/stage17_fixed_action.cpp`'s `package_capture`: resolves
  this run's own real software-prefetch mapping via a fresh
  `platform::read_x86_family_model()` call (this function has no
  existing resolved identity in scope, unlike `publish_q15_r`/`q15_w`,
  which already had `session.identity` sealed), fails closed
  (`S17-RUN-SOFTWARE-PREFETCH-CPU`) for R1/R2/L1 packages on an
  unregistered CPU, and dispatches via `std::visit` over
  `std::variant<X86RetainingPrefetchEmitter, X86PrefetchT0OnlyEmitter>`
  wrapping each of the R1/R2/L1 branches -- the compiler genuinely
  instantiates both `R1Package<X86RetainingPrefetchEmitter>` and
  `R1Package<X86PrefetchT0OnlyEmitter>` (etc.) as two separate, real
  code paths, exactly what the extended codegen check (below)
  disassembles; a single runtime-branching wrapper emitter was
  considered and rejected, since it would make the shipped binary
  instantiate a third, unverified template configuration. `publish_q15_r`
  was also fixed to resolve its own `Q15_R_SOFTWARE_PREFETCH_RAW`
  artifact's `mapping_id` from `session.identity` via the new registry,
  instead of a hardcoded literal naming the original mapping
  unconditionally -- a real, pre-existing bug this ADR also closes.
- `tools/runner_combined_codegen_probe.cpp`/`_mutant.cpp`/`check_
  runner_combined_codegen.py`: extended in place (confirmed safe: no
  in-repo or out-of-repo record pins this script's own hash) with 6 new
  probe symbols (`t0only_{r1,r2,l1}_{producer,consumer}`) instantiating
  the real `R1Package<X86PrefetchT0OnlyEmitter>`/etc., one new mutant
  (`cpu_prefetch_combined_wrong_producer_t0only_mutant`), and `schema_
  version` bumped to `cpu-prefetch-runner-combined-codegen/3`. Verified
  for real against a built binary: the new T0-only producer symbol
  genuinely emits `prefetcht0`, and the new mutant is genuinely rejected
  (`expected=['prefetcht0'], observed=['prefetchw']`).
- `src/qualification/q15_collectors.cpp`'s `assess_codegen_report`:
  widened to accept schema `/2` or `/3` and either registered mapping id
  (`is_accepted_software_prefetch_mapping_id`).
- New schemas, additive, every document that validated before still
  validates: `config/schemas/qualification-evidence-v3.schema.json`
  (widens `mapping_id` to an `enum` of both IDs, with `ring_producer_
  instruction` conditional on which one via `if`/`then`; `qualification-
  evidence-v1`/`v2` are pinned inside frozen policy generations and left
  untouched) and `config/schemas/stage17-q15-r-software-prefetch-raw-
  v2.schema.json` (same `mapping_id` widening; `v1` is likewise pinned
  and left untouched). `config/schemas/q15-qualification-authorization-
  v1.schema.json` was widened **in place** (confirmed unpinned by any
  frozen policy generation) mirroring its own already-widened `hardware_
  prefetch_mapping_id` sibling field. `config/schemas/q15-qualification-
  authorization-v2.schema.json` was **not** touched: it is a frozen,
  historical, single-stand-pinned schema (`stand_id`/`source_revision`/
  `archive_sha256`/`runner_sha256` are all hardcoded `const`s to one
  specific `XEON-CPU-FETCH` build) for an unrelated, superseded
  standalone "fixed controller" subsystem, and its own bytes are pinned
  by `config/q15/q15-r-controller-profile-v1.json`'s `source_bindings` --
  confirmed the hard way, by a real `q15.fixed_controller_profile` test
  failure after an initial, mistaken in-place edit, reverted before
  landing. `config/schemas/q15-r-decision-input-v1.schema.json` was
  widened in place (confirmed only the *data* file `config/q15/q15-r-
  decision-input-v1.json` is pinned there, not the schema).
- `tools/verify_stand_bundle.py`: the two live gates checking a real
  bundle's own `software_prefetch_mapping_id`/combined-codegen-report
  fields now accept either registered mapping id and schema `/2` or
  `/3`.
- `tools/stage17_operational_semantics_v11.py` (new, additive successor
  to `v8`): retargets `ROLE_SCHEMA_v8`'s `QUALIFICATION_EVIDENCE` and
  `Q15_R_SOFTWARE_PREFETCH_RAW` entries to the new v3/v2 schemas; `_read_
  artifacts_v11`/`verify_manifest_v11` are faithful copies of `v8`'s own
  bodies, broadened only to resolve roles through this module's own
  retargeted table -- the same free-variable-resolves-via-defining-
  module reason every predecessor in this chain already gives.
- `tools/stage17_semantic_verifier_v53.py` (new, additive successor to
  `v52`): intercepts `S17-EXT-004` specifically (mirroring the exact
  scope `v41.py` itself established) and calls `stage17_operational_
  semantics_v11.verify_manifest_v11` instead of `v8`'s own `verify_
  manifest_v8`; every other input's dispatch, `S17-EXT-006` included, is
  unchanged, delegated to `predecessor.verify_input` (`v52`), which
  still resolves `S17-EXT-006` through `v41`'s own `verify_s17_ext_006`
  exactly as before. `VERIFIER_VERSION` bumped to `"53"`; `required`
  grows by exactly one entry, `tools/stage17_operational_semantics_
  v11.py`.
- `tools/author_stage17_policy_v53.py` (new, additive successor to
  `v52`): adds `stage17_operational_semantics_v11` to `ROOTS` (the
  static AST-walk discovery roots `discover_python_closure` starts
  from -- confirmed this is a manually-maintained list, not purely
  transitive, the same way `v8` itself was added to it by an earlier
  generation) so its own bytes, and the new schemas it reaches through
  `verify_manifest_v11`, are discovered and pinned into this
  generation's runtime closure. Re-pins `src/runner/stage17_fixed_
  action.cpp`'s changed bytes, the same single compiled worker source
  file every prior generation in this chain already re-pinned.
- `tools/stage17_state_journal_v47.py` (new, additive successor to
  `v46`): repoints the journal chain's own `semantic` reassignment to
  `stage17_semantic_verifier_v53` -- confirmed this file is outside
  `author_stage17_policy_vNN.py`'s own closure/pinning mechanism
  entirely (no `author_stage17_policy_vNN.py` or `stage17_semantic_
  verifier_vNN.py` generation has ever referenced `stage17_state_
  journal_v44/45/46.py` by name), existing purely for the local
  admission wrapper scripts' own convenience when repointing
  `journal_runtime` at runtime -- kept current here for the same reason.

## Tests

- `tests/runner_model_test.cpp`: `SoftwarePrefetchT0OnlyMappingIsFrozen
  AndEmitsOnlyPrefetchT0` (frozen-constant assertion + direct exercise
  of all three emitter methods), `SoftwarePrefetchMappingRegistryCovers
  Adr0047AndAdr0175Only` (both registered pairs resolve, an unregistered
  one returns `nullopt`, garbage mapping ids rejected), and
  `SoftwarePrefetchT0OnlyMappingIsEligibleWithoutPrfchw` (the T0-only
  mapping is `eligible: true` without PRFCHW given passing codegen
  attestation, `eligible: false` if codegen attestation is missing, and
  `eligible: false` for any unregistered mapping id regardless of other
  fields -- codegen attestation and registry membership are never
  bypassed by mapping choice).

Verified for real: full `dev-gcc` build and `ctest` (same 6
pre-existing failures this engagement already tracks as an unrelated
baseline, confirmed unchanged -- two real, new regressions were caught
and fixed during this change: `runner.qualification_self_test`'s own
hardcoded `kQualificationEvidenceSchemaVersion` literal needed bumping
to `/3`, and the mistaken in-place edit to `q15-qualification-
authorization-v2.schema.json` above, caught via `q15.fixed_controller_
profile`'s real failure and reverted). `runner-combined-codegen-check`
built and run for real against the extended probe/mutant, confirmed
PASS with the new T0-only symbols' real disassembly and the new
mutant's real rejection, both inspected directly in the JSON report, not
assumed from the summary line alone.

## Authority boundary

This ADR does not itself authorize a live Q15-W/Q16/pilot run on
`cpu-prefetch-v5`. It makes `SOFTWARE_PREFETCH_MAPPING` qualification
evidence honestly producible as `eligible: true` on this stand's real
hardware -- one of five `S17-EXT-004` gates. A fresh, live, held-open
Q15-R session and a real `S17-EXT-004` manifest built against this
generation (policy v53) are still required, following the same
authoring chain ADR-0173's implementation note 8 and ADR-0174 already
documented for the predecessor gaps in this lineage.
