# ADR-0228: Pure prospective formal service and scheduled family contracts

- Status: ACCEPTED — engineering implementation; verification below
- Date: 2026-11-03
- Scope: Q16b/Q16c declaration checks and unchanged Q16a delegation
- Scientific authority: D035/D036/D037, D211/D212, D223/D226/D227
- Execution authority: None

## Boundary and versioning

`tools/stage17_formal_plan_v1.py` exposes
`validate_plan(action, document) -> FamilyExtent`. The extent and nested budget
types are the existing D221 types, including capture ordinal and `.declared`
budgets. `METHOD`, `CUSTODY`, `VERSION` and repository-relative `SCHEMA` maps
are keyed by Q16a/Q16b/Q16c. Q16a delegates directly to the unchanged
`stage17_formal_ring_plan_v1.validate_plan`; its source and schema are unchanged.

The new service and scheduled plan schemas retain the exact corresponding
native input definitions. Each capture entry has `capture`, `resources`,
`monitoring` and `execution_budget`. Top-level fields follow D227: the common
ring-plan fields without its demand minimum, `repetitions_per_cell`, and, for
Q16c only, `scale_ordinal`. Unknown fields, noncanonical numeric types and
malformed identities are rejected. JSON Schema shape checks are supplemented
by strict integer and full-string identity checks.

## Complete prospective coverage

Q16b requires all 60 cells and at least 59 declared repetitions per cell.
Q16c requires all 180 cells for one explicit candidate from the existing
five-point ladder, with at least one declared repetition per cell. This lower
bound does not establish sufficient precision, feasibility or a final sample
size. Durations, capacities, repetitions, source schedules and operational
budgets remain explicit prospective inputs; this contract supplies none.

Execution order follows D227: hardware state H0 then H1, package R0/R1/R2/L0/L1,
placement NEAR/FAR, working-set class L2/LLC/beyond, load L025/L050/L075 for
Q16c, then repetition. Cell identity remains package-major, separate from
capture ordinal. The software representation does not authorize execution of
that order; the concrete prospective family still requires owner admission.

Warmup and measurement run identities, seed IDs and inherited arena seed values
are unique throughout the family. The arena retains the measurement-seed rule.
Package/context geometry is paired across hardware states; repeated cells keep
their declared native bounds, resources and monitoring unchanged. Package
declarations retain R0's absent distance, R1's registered one-line distance,
R2's explicit prior evidence identifier and linked packages' explicit node-order
seed and base-page alignment. Native layout and calibration-evidence validity
are independently checked at admission.

Q16c checks exact source-vector count, nondecreasing deadlines, the half-open
source horizon, the declared phase duration, producer watchdog coverage and
finite source-vector bytes. Measurement offers at least one arrival; the native
contract permits an explicitly empty warmup source. No claim about elapsed
warmup, monitoring success or observed rates follows from that declaration.
Schedule IDs and schedule seed IDs remain unique, warmup/measurement schedule
namespaces are isolated, and schedule identities are separate from arena
identities. Canonical master-seed values may repeat under disjoint namespaces;
numeric inequality is not a substitute for namespace separation. Source artifact
IDs and hashes are syntax-checked declarations: schedule reproduction, original
source bytes, common schedule-family relationships and the reservation ledger
remain independent admission requirements.

## Finite arithmetic and its limits

All arithmetic is checked unsigned 64-bit arithmetic; capture and family
watchdogs also fit the signed native duration. The raw capacity bound includes
both warmup and measurement producer/consumer streams, including retained drain
events. A primary row has the existing four-byte length-prefixed run ID, padded
to eight bytes, followed by fifteen producer or ten consumer unsigned 64-bit
words. Linked packages add `(capacity + 1) * 8` bytes for node order. Q16c adds
both source schedules at eight bytes per declared arrival. No existing codec
changes, compression or dropped failure evidence is assumed.

Publication memory covers the D227 conservative copy floor: the maximum of the
largest primary stream and the sum of linked node-order plus both schedule
vectors. The returned `largest_raw_copy_bytes` remains the largest individual
artifact; the stricter native copy floor is additionally checked. The capture
output includes all raw capacity extents plus declared metadata. Its watchdog
covers setup, the accepted five-second warmup, measurement, both drains,
publication and cleanup. Its process memory covers declared mappings,
publication memory and other memory.

Family bounds sum every capture watchdog/output plus family overhead, use the
maximum sequential capture memory plus controller memory, and reserve analysis
scratch and disk headroom on top of the **declared family output ceiling**.
Controller memory must at least hold the canonical prospective plan bytes.
These are necessary declaration checks, not proofs that metadata, publication
heap, parsed JSON, native mappings or live free resources suffice. The native
parser recomputes every layout; independent admission binds actual resources,
qualified source/release, prerequisites and authority.

## Verification

The focused software fixtures contain complete 3540-capture Q16b and
180-capture Q16c declarations with small explicit synthetic capacities. Tests
compare native-schema definitions, independent raw byte quantities, cell/order
coverage, the unchanged Q16a delegation and returned extent types. Mutants cover
partial/extra/reordered families, late candidate drift, duplicate identities,
namespace overlap, malformed integers and IDs, package/geometry mismatches,
schedule endpoints/counts/order, outcome-adaptive repeated bounds, overflow and
omitted time/memory/output/scratch components. A positive case retains one
master seed across disjoint schedule namespaces; another permits an empty
declared warmup source. No hardware, elapsed warmup, scientific validity or run
authority is established by these tests.

Accepted offline runtime verification: the 14 focused tests passed, including
both complete families and independent LP-prefix padding boundaries. The 15
retained D221 ring-plan tests also passed. Commands use
`python3 build/ext007-runtime-20261101/run.py -- python3 -B` with
`tests/test_stage17_formal_plan_v1.py` and
`tests/test_stage17_formal_ring_plan_v1.py`. Evidence logs are
`build/stage17-step5-prep/d214-verification/d228-plan-tests-final.log` and
`build/stage17-step5-prep/d214-verification/d228-ring-retained-tests.log`.
No native production source or existing ring contract was changed in this slice.
