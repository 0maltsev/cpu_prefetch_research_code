# D-031 Stage 12 simultaneous-blocker decision bundle

- **Protocol source reviewed:** immutable `protocol/2.0.0-pre.1/`; accepted
  amendment imported as immutable `protocol/2.0.0-pre.2/`
- **Decision:** D-031, confirmatory-estimability representation when independent
  blockers coexist
- **Classification:** scientific representation and protocol compatibility
- **Approval questions:** Q10 (scientific representation) and Q11 (versioned
  import, implementation ADR, and Stage 12 only)
- **State:** `ACCEPTED_Q10_Q11_IMPLEMENTED_STAGE12`
- **Implementation state:** Q11 authorized and ADR-0034 records the completed
  Stage 12 implementation; measurement remains prohibited

## Decision record

| Field | Value |
|---|---|
| ID | D-031 |
| Classification | Scientific representation; logical schema and compatibility |
| Options considered | Fixed singular priority; any applicable singular reason; versioned multi-reason extension; legacy field plus non-normative sidecar |
| Recommended option | Versioned multi-reason protocol extension with a deterministic, non-priority summary |
| Current state | Q10 accepted the recommended option and Q11 authorized/imported `2.0.0-pre.2`, ADR-0034, and Stage 12 on 2026-08-21 |
| Evidence | Protocol requires independent disposition fields, but `2.0.0-pre.1` exposes one singular estimability enum and specifies no precedence |
| Scientific effect | Preserves every independently material reason that blocks dependent confirmation; does not alter validity, zero-loss, effective-tail, completeness, access, replacement, or rerun rules |
| Compatibility effect | Requires a new normative protocol/schema version; `2.0.0-pre.1` remains immutable and readable but cannot represent the new final disposition |
| Owner | Protocol owner and statistical owner jointly |
| Deadline / gate | Before Stage 12 accepts or seals final run dispositions |
| Supersession rule | A later versioned protocol amendment and ADR may replace this rule prospectively; existing artifacts are never rewritten or reinterpreted |

## Why a decision is required

The protocol fixes independent fields for lifecycle, join status, run validity,
count reconciliation, zero-loss status, effective-tail status, confirmatory
estimability, and block completeness. It also fixes one singular
`confirmatory_estimability` value from:

```text
NOT_EVALUATED
ESTIMABLE
BLOCKED_ZERO_LOSS
BLOCKED_EFFECTIVE_TAIL
BLOCKED_INVALID_RUN
BLOCKED_INCOMPLETE_BLOCK
BLOCKED_ACCESS_LEAKAGE
NOT_APPLICABLE
```

More than one underlying gate can fail at the same time. Examples include a
valid run with both `FULL` observations and low `N_eff`, or an invalid run in
an incomplete original block. The protocol says those gate fields are
independent, but it neither defines a priority among the singular blocker
tokens nor provides a collection that can retain all applicable reasons.

Stage 4 therefore correctly performs only local applicability checks: it
rejects `ESTIMABLE` when a known local gate fails, accepts only a blocker whose
own gate fails, and deliberately does not invent precedence. That is safe for
typed-model validation but insufficient for deterministic final-disposition
artifacts in Stage 12.

## Immutable constraints

Any accepted solution must preserve all of the following:

1. Run validity, zero loss, effective tail, block completeness, and access
   chronology remain independent facts.
2. A correctly reconciled `FULL` outcome remains valid data, fails the
   zero-loss gate, and never authorizes repetition or replacement.
3. Genuine low `N_eff` remains valid data, fails the effective-tail gate, and
   never authorizes repetition, extension, or selective removal.
4. Only protocol-defined invalidity can make a required complete block eligible
   for the separately authorized complete-block replacement process.
5. `confirmatory_estimability` is descriptive. It cannot create invalidity,
   authorize replacement, or decide which raw observations are retained.
6. Access leakage is established only from the authoritative cross-record
   access/sealing chronology; Stage 12 cannot infer it from a local manifest.
7. The imported `2.0.0-pre.1` snapshot and its schemas are never edited.
8. A repository compatibility schema cannot silently redefine the normative
   imported contract.

## Options considered

### Option A — fixed priority in the existing singular field

Define a total order over the five `BLOCKED_*` reasons and emit the first
applicable reason.

- **Advantage:** retains the current field shape and can keep old readers
  syntactically compatible.
- **Risk:** hides other scientifically material blockers in the summary and
  makes the chosen order part of scientific reporting semantics.
- **Decision requirement:** an exact order must come from protocol/statistical
  authority. The repository must not invent one.
- **Recommendation:** not selected.

### Option B — allow any applicable singular reason

Continue the permissive Stage 4 behavior as the final policy.

- **Advantage:** no schema change.
- **Risk:** two conforming writers can produce different canonical manifests
  from identical facts; downstream summaries can depend on writer choice.
- **Recommendation:** rejected for final artifacts. It remains only a safe
  pre-decision validation posture.

### Option C — versioned multi-reason representation

Create a new protocol/schema version that retains the singular summary and adds
an exhaustive blocker set.

- **Advantage:** deterministic and lossless; no blocker receives scientific
  priority; legacy single-blocker meanings remain recognizable.
- **Cost:** requires a versioned protocol amendment, reader updates, new schema
  fixtures, and an explicit compatibility boundary.
- **Recommendation:** **accepted by Q10**.

### Option D — legacy singular field plus implementation sidecar

Keep the normative manifest unchanged and put the blocker set in an
implementation-owned artifact.

- **Advantage:** avoids an immediate schema edit.
- **Risk:** splits one scientific fact between normative and non-normative
  sources, while leaving the manifest itself ambiguous.
- **Recommendation:** not selected unless a later protocol amendment explicitly
  authorizes it as a migration format.

## Recommended normative contract

Q10 acceptance selects the following amendment request. Names remain exact unless
the protocol amendment records an explicit supersession before implementation.

### Logical fields

The amended final-disposition object contains:

- the existing `confirmatory_estimability` field;
- a required `confirmatory_blockers` array;
- a new singular summary token, `BLOCKED_MULTIPLE`.

`confirmatory_blockers` uses only these existing blocker tokens:

```text
BLOCKED_ZERO_LOSS
BLOCKED_EFFECTIVE_TAIL
BLOCKED_INVALID_RUN
BLOCKED_INCOMPLETE_BLOCK
BLOCKED_ACCESS_LEAKAGE
```

The array has `uniqueItems: true`. Canonical serialization orders values by
their UTF-8 token bytes. That order is only a byte-level canonicalization rule;
it is not blocker priority.

### Exact mapping

| Authoritative gate result at final evaluation | Summary | Blocker array |
|---|---|---|
| Disposition not yet fully evaluable | `NOT_EVALUATED` | Empty |
| Confirmatory estimation does not apply | `NOT_APPLICABLE` | Empty |
| Every applicable gate evaluated and passed | `ESTIMABLE` | Empty |
| Exactly one applicable gate failed | Matching existing `BLOCKED_*` token | Singleton matching token |
| Two or more applicable gates failed | `BLOCKED_MULTIPLE` | Every applicable failed-gate token |

The applicability mapping is exact:

| Blocker token | Authoritative source fact |
|---|---|
| `BLOCKED_ZERO_LOSS` | `zero_loss_status == FAIL` |
| `BLOCKED_EFFECTIVE_TAIL` | `effective_tail_status == FAIL` |
| `BLOCKED_INVALID_RUN` | `validity == INVALID` |
| `BLOCKED_INCOMPLETE_BLOCK` | `block_completeness == INCOMPLETE` |
| `BLOCKED_ACCESS_LEAKAGE` | The authoritative cross-record access/sealing validator has established leakage |

Every applicable failed-gate token must be present and no inapplicable token
may be present. A singleton summary must equal its array member.
`BLOCKED_MULTIPLE` requires at least two members. `ESTIMABLE`,
`NOT_APPLICABLE`, and `NOT_EVALUATED` require an empty array.

Final evaluation requires every applicable gate to have authoritative evidence.
Until then, the summary remains `NOT_EVALUATED`; known independent fields and
their evidence remain visible and must not be rewritten to pass. In particular,
Stage 12 may implement and test aggregation with injected access evidence, but
it must not seal a production final disposition before the later access/sealing
validator supplies that evidence.

### No change to outcome or replacement semantics

The blocker set is a faithful summary of separate gate facts. It does not:

- change a valid `FULL` or low-`N_eff` run to invalid;
- cause a rerun, horizon extension, or hidden retry;
- authorize replacement;
- choose a primary failure category;
- suppress warnings or failure evidence; or
- alter which raw or partial artifacts are retained.

An invalid run and an incomplete block may therefore legitimately contribute
both corresponding blocker tokens. The complete-block replacement protocol
continues to operate from invalidity, block lineage, authority, and budget—not
from this array.

## Compatibility and migration boundary

The current run-manifest schema has `additionalProperties: false` and does not
contain `confirmatory_blockers` or `BLOCKED_MULTIPLE`. Consequently, this
contract cannot be introduced as an implementation-only extension to
`2.0.0-pre.1`.

The Q10 acceptance required protocol/statistical authority to publish a new
versioned protocol snapshot containing at least:

1. the amended data dictionary and normative run-manifest schema;
2. the exact multi-reason semantic rules above;
3. updated examples and compatibility statement;
4. authoritative file hashes and import manifest; and
5. a statement that the amendment changes representation, not the independent
   scientific gate or replacement semantics.

Repository import and implementation then follow these rules:

- retain `protocol/2.0.0-pre.1/` byte-for-byte;
- import the new snapshot alongside it and verify all hashes;
- reject mixed protocol/schema versions in one sealed artifact graph;
- preserve old artifacts under their original version;
- if migration is needed, emit a new derived disposition artifact with source
  IDs/hashes and converter version; never overwrite or reinterpret the source;
- fail closed on unknown summary tokens or malformed blocker sets.

Q11 assigned `2.0.0-pre.2`; its import manifest and authoritative hashes now
satisfy this boundary. The pre.1 snapshot remains unchanged.

## Required Stage 12 verification after amendment import

Q11 separately authorized Stage 12 only. Its implementation and ADR-0034 add
at least:

- exhaustive truth-table tests over validity, zero loss, effective tail,
  completeness, access, applicability, and evaluation completeness;
- simultaneous `FULL` plus low-`N_eff` coverage;
- invalid-run plus incomplete-block coverage;
- access-leakage combinations using an injected cross-record result;
- missing, duplicate, extra, mismatched, and noncanonical blocker-array tests;
- `NOT_EVALUATED`, `NOT_APPLICABLE`, singleton, multiple, and estimable tests;
- canonical round-trip and cross-version negative tests;
- proof that blocker aggregation cannot authorize retry or replacement; and
- schema plus semantic validation against the newly imported snapshot.

## Evidence reviewed

- `EXPERIMENT_IMPLEMENTATION_SPEC.md` sections 2 and 11.2: independent status
  fields, partial failure, valid `FULL`, retained low `N_eff`, and no repeat.
- `handoff/DATA_DICTIONARY.md`: stable enum and the independence of validity,
  zero loss, and effective tail.
- `handoff/schemas/run-manifest.schema.json`: singular closed enum, closed
  object, and no simultaneous-reason rule.
- `handoff/ACCESS_AND_SEALING_PROTOCOL.md`: access leakage is a cross-record,
  authority- and chronology-dependent fact.
- Stage 4 semantic validator and
  `SimultaneousGateFailuresDoNotInventReasonPrecedence` test: applicability is
  checked without fabricating priority.

At bundle preparation, the relevant imported SHA-256 values are:

| Imported artifact | SHA-256 |
|---|---|
| `EXPERIMENT_IMPLEMENTATION_SPEC.md` | `3795f53cfd0b06d94c2fdafa90e71372fc4f0eccd09d084382668f74f2b715ca` |
| `handoff/DATA_DICTIONARY.md` | `c0c29e44ebfa5d3a8628180e748a11ea6095c1167ef5301c6bedd9518b9fd9da` |
| `handoff/schemas/run-manifest.schema.json` | `ef460636ac56bdf32aa2bcde1bbdca3f64c5dc80d7258707ec7e1e8e51a078f2` |

## Approval record

Q10 was accepted on 2026-08-21 by the user explicitly acting as both protocol
and statistical owner:

```text
Q10 - accept the D-031 bundle as protocol and statistical owner
```

Q10 selected Option C and authorized the versioned multi-reason amendment path.
Q11 then authorized creation/import of immutable `2.0.0-pre.2`, ADR-0034, and
Stage 12 only. Neither approval authorizes editing immutable `2.0.0-pre.1` or
running calibration, pilot, or confirmatory measurements.

ADR-0034 was created after the amended snapshot was imported and verified.
Options A, B, and D remain unselected.

## Gate after approval

Q11 closed this gate: the amended snapshot is imported beside unchanged pre.1,
hash-verified, traced, and implemented under ADR-0034. The exact next safe
action is preparation and approval of the Stage 13 calibration decision/input
bundle. Calibration execution and all performance measurement remain
prohibited.
