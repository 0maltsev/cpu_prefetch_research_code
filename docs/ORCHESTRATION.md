# Stage 14 Block Planning and Access Orchestration

Protocol version: **`2.0.0-pre.2`**

Stage 14 is an offline, non-executing software layer. It creates and validates
prospective block plans and governance records; it does not execute queues,
touch stand controls, open sealed outcome artifacts, or authorize calibration,
pilot, or confirmatory work.

## Factorial proof and deterministic generation

`cpu_prefetch_orchestration` independently constructs the registered product

`5 packages × 2 hardware states × 2 placements × 3 working sets × 3 loads = 180 cells`.

Validation compares sets of typed factor tuples rather than trusting array
length or `uniqueItems`. Cell ordinals must be exactly `0..179`. The first 90
ordinals must be the first frozen hardware whole plot and the next 90 the
second; each plot must contain all 90 package/placement/working-set/load tuples.

Generation receives explicit platform/build/role/ordinal fields, a frozen role
namespace, a distinct block seed subspace, immutable derivation evidence, three
already-derived Philox keys, 18 arrival seed IDs, and six node/event seed IDs.
It performs no seed derivation and reads no run or treatment outcome. Identity
uses explicit fields, not path parsing. The final imported block document has a
zero-self JCS-I64 SHA-256.

Arrival schedules are common across packages and hardware states for the same
placement, working set, and load. Persistent arena event order is common across
packages, states, and loads for a placement/working set. Node-order references
exist only for `L0`/`L1`. Role namespaces and all block seed identities are
nonoverlapping.

## Prospective precision registry

The implementation registers exactly:

| Family | Implemented cardinality/use |
|---|---:|
| H1 max-T | 7 contrasts |
| H2 max-T | 20 contrasts |
| H3 training | 6 contexts × 45 unordered pairs = 270 |
| H3 validation before selection | 6 contexts × 90 ordered pairs = 540 |
| H3 reporting after selection | 6 contexts × 9 alternatives = 54 |

`R12=max(R_H1,R_H2)`, `Rtotal=max(R12,Rtrain+Rval)`, and
`Nruns=180*Rtotal` use checked integer arithmetic. H1/H2 minima and the
go/no-go ceiling, plus H3 training/validation minima, are enforced. Inputs from
training or unsealed validation outcomes cannot size a family, and no
validation-resizing API exists. Missing counts/evidence produce
`NOT_EVALUATED`; the implementation never invents a number.

## Access and sealing ledger

The imported sequence is validated exactly:

`PLANNED → COLLECTED_SEALED → TRAINING_OPEN → SELECTION_FROZEN → VALIDATION_UNSEALED → H3_EVALUATED → H1H2_RELEASED → ARCHIVED`.

Every record is append-only by identity and binds its full canonical source
with a zero-self hash. UTC timestamps are nondecreasing. External inputs and
predecessor access records resolve by exact artifact ID and SHA-256. The
`TRAINING_OPEN` record freezes the exact candidate/context order, 7/20/270/540/54
families, the exact arithmetic-mean-log-p99.9/minimum/candidate-order selection
and tie-break rule, bootstrap identities, all seven count fields, immutable
schema identities, and hashes for delta, bootstrap, separate family-sizing,
and prospective source evidence. Its counts must equal the independently
validated precision plan. Collection/release records name the entire common
active pool; training/selection name exactly all active `H3_TRAIN` blocks;
unseal/evaluation name exactly all active `H3_VALIDATION` blocks. Replaced
originals remain immutable evidence but cannot enter primary outcome access.
Selection accepts only H3-training
artifacts and exactly one registered candidate for each stable context. Unseal
requires the selection record, validation role namespace/artifact,
validation-authority approval, and custodian action. H3 evaluation and H1/H2
release require their complete predecessor/evidence links.

`SELECTION-PAYLOAD-JCS-I64-SHA256-v1` hashes a canonical object containing
exactly `h3_selections`, `training_input_artifacts`, and
`selection_rule_version`; the envelope's independent zero-self hash then binds
that checksum and all governance fields. Training input references must equal
the `TRAINING_ONLY` hashed inputs. Replacement authorization likewise carries
the exact frozen replacement-budget ID and SHA-256, not the budget label alone.

Operational roles are freeze authority, custodian, training analyst,
validation authority, confirmatory analyst, and replacement authority. Each
has an explicit principal. Shared principals fail unless an immutable overlap
authorization artifact names that exact pair. The C++ access check returns a
boolean only after the ledger passes; artifact storage must separately enforce
the approved read.

Amendments are state-preserving append-only records. They must hash-link one
earlier target, cannot branch an already superseded target, and cannot consume
training or validation outcomes.

## Complete-block replacement

Replacement requires all of the following:

- the original block remains present;
- a retained required Stage A run is `INVALID` and makes the original block
  `INCOMPLETE`;
- the run names an invalidating failure record;
- failure resolution, replacement authorization, replacement ID, and frozen
  budget ID/hash references agree exactly;
- the new block preserves role and platform/build context but has a new ID,
  ordinal, seed subspace, and random order; and
- the replacement count remains below the frozen platform budget.

`FULL` and low effective-tail outcomes remain valid and cannot satisfy this
interface. A second branch from an original block is rejected. Budget
exhaustion returns an explicit unresolved study state and no new plan. The API
has no cell-replacement operation.

## External freeze inputs still required

Before final Stage A plans can be accepted, external pilot/platform evidence
must supply concrete prospective repetition counts, role/common namespaces,
master/derived seed catalogs and derivation evidence, platform/build identity,
named segregated authorities and custody mechanism, `R_replacement_max` and
budget evidence, plus every earlier calibration/platform freeze input. Stage
14 synthetic fixtures are not substitutes for those records.
