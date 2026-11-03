# ADR-0237: Stage 17 calibration export with explicit unresolved provenance

- Status: ACCEPTED — engineering composition; no scientific method change
- Date: 2026-11-03
- Scope: Offline EXT007 export preparation from original bound evidence
- Execution authority: None

## Purpose and accepted boundary

The Stage 13 calibration decision bundle requires D037 distance calibration,
D035 service calibration and D036 probe provenance before a final load freeze.
Its dependency graph and lifecycle provisions explicitly forbid replacing absent
`Rtotal`, `Nruns=180*Rtotal` and all planned `N_sched` values with placeholders.
Stage 17 may retain provisional calibration evidence. D115 does not grant
Phase 18 authority. D212 supplies the current Q16a window method; D211 supplies
the Q16b fixed completion interval. None of these decisions is changed here.

The legacy `calibration-freeze-v1.schema.json` describes a different final-freeze
boundary. It and the legacy result schemas remain unchanged. New
`stage17-calibration-freeze-v1.schema.json` identifies
`cpu-prefetch-stage17-calibration-freeze/1` under protocol 2.0.0-pre.3 and scope
`STAGE17_EXT007`. This first preparation version deliberately admits only
`state=UNRESOLVED`. It is not an EXT007 resolution or a substitute for signed
operational admission. A separate authenticated successor is required to make
a scoped Stage 17 FROZEN record; changing a success flag cannot do so.

## API and original source bytes

`tools/stage17_calibration_export_v1.py` exposes:

```text
build_export(*, identity, owner_decision, source_packets)
validate_export(document, *, owner_decision, source_packets)
```

`identity` contains exactly `record_id`, `stand_id`, `source_revision` and
`created_at_utc`. The source revision identifies the original producer release,
not a later analysis implementation. A source packet contains exactly
`binding={artifact_id,size_bytes,sha256}` and `utf8_bytes` of Python type `bytes`.
The original byte size and SHA256 are verified before strict duplicate-key JSON
decoding. Floats, nonfinite numbers, malformed UTF-8, ambiguous artifact IDs and
a separately supplied decoded document are rejected.

`owner_decision` is one such packet. `source_packets` contains exactly:

- `plans`: Q16a, Q16b and one Q16c candidate family, each an original packet;
- `calibrations`: original Q16a and Q16b D230 record packets;
- `capture_reports`: a sequence for each action, with exact rows
  `{capture_ordinal,measurement_run_id,validity,report}` where `report` is a
  packet and validity is VALID or INVALID;
- `geometry_sources`: six original packets in context order, each matching the
  corresponding D230 native geometry source binding;
- `lifecycle`: one original packet for each action;
- `probe_design` and `analysis_provenance`: original packets.

Every plan passes the existing full prospective-family contract. Stand and
producer revision agree across the families, and run IDs cannot be reused
between them. Reports cannot replace, duplicate or add planned ordinals or run
identities. Missing reports remain explicit; there is no retry or top-up.

## Independent computations and coverage

For Q16a and Q16b, re-run D230 `evaluate` over the original capture report bytes
and full prospective plans. Compare the entire recomputed result with the
bound original D230 record, including membership, failures, exact integer and
rational arithmetic, units and source bindings. The six explicit geometry
source byte bindings must agree with D230. Later R0/R1/R2 capacities and cache
line widths agree with the six Q16a contexts. R2 uses the exact derived distance
and `q16a-sha256-<original Q16a D230 artifact SHA256>` evidence identity.

Q16c uses actual D229 report fields and D228's full `180*repetitions_per_cell`
membership. Check both phase run identities, method, required evidence flags,
false authority/family claims, count equations, full drain, nonzero measurement
offered count, prospective capacities, and both prepared schedule summaries.
Recompute each prepared U64LE vector hash incrementally from its declared
deadline vector; check its count and source origin. Check the node-order count
against package/capacity and require its retained SHA256. These are report and
plan consistency checks, not a second raw reconciliation or node-order replay.
FULL is valid retained data, with separate zero-loss reporting. An absent report
is MISSING; an explicit invalid report must bind the D230 failure grammar, exact
source identity and all seven scheduled raw artifacts. Either leaves Q16c
coverage unresolved. No result is selected from a favorable subset.

The Q16c prepared-vector hash is not the generator's original U64BE artifact
hash. D232 independently binds the original binary, envelope, derivation and
registered parent namespace; those checks are not replaced by this export.
No new probability calculation, scale selection or event independence claim is
introduced. Q16c inference is explicitly NOT_EVALUATED.

## Provenance that cannot be inferred

Owner, lifecycle, analysis and common-marginal design packets are retained by
their exact original bindings, but their self-asserted `approved`, `admitted`,
`authenticated` or `signature_verified` values grant nothing. This preparation
module does not authenticate SSHSIG signatures, traverse admitted journal/root
state, attest the analysis producer, or interpret arbitrary layout JSON as
native geometry proof. It lists explicit unresolved blockers for owner
authority, signed lifecycle and raw-validation provenance, analysis source,
native geometry, common-marginal design and schedule-generator/namespace
provenance. A source hash proves byte identity only.

Consequently even complete internally consistent reports yield UNRESOLVED.
This is an intermediate evidence document, not a permanently blocked design:
the subsequent admission adapter must reuse the existing authenticated
root/journal/signature/lifecycle policies and separately establish each required
provenance fact before a versioned Stage 17 freeze can be issued. It must retain
the original producer qualification independently of later analysis source.
No callback or caller-supplied success boolean bypasses that requirement here.

## Output and verification

Retain exact derived d2 context records, explicit geometry, mu cell/ref records
in EVENTS_PER_SECOND, and complete Q16c membership/count/report bindings. Retain
all original plan/calibration/lifecycle/owner/design/analysis source bindings.
Seal with the existing calibration canonical zero-self hash grammar. Revalidation
requires all original packets and recomputes the entire document; schema
validation or its self hash alone is insufficient.

`final_matrix_feasibility` is always `state=NOT_EVALUATED`, with null `passes`,
`selected_global_scale` and `matrix_probability_lower`, and explicit unresolved
inputs `Rtotal`, `Nruns`, `N_sched`. Both execution and Phase 18 authority are
false. This format cannot be relabelled as the legacy final freeze. It neither
admits EXT007 nor changes capture/release/runtime policies.

Tests construct complete synthetic 708/3540/180 report families from existing
D220/D229 fixture shapes, not empirical captures or signed execution evidence.
They check known d2/mu values, exact recomputation, schema parity, source hashes,
duplicate/noninteger JSON, missing receipts, FULL retention, method/count/origin
and prepared-vector mutants, authority promotion and legacy-format rejection.
No raw array is materialized by the export; report/plan metadata is resident and
costs scale with their declared family size. This does not certify an operational
memory budget. Accepted-runtime Python verification is required; no native or
hardware test is appropriate for this pure analysis composition.
