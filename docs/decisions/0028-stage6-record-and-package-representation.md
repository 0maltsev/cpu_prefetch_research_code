# ADR-0028: Stage 6 record and package representation

- Status: `ACCEPTED`
- Date: 2026-08-17
- Classification: Physical record layout / package binding
- Decision owners: Repository owner; data-plane owner; queue owner
- Protocol version: `2.0.0-pre.1`
- Supersedes: None
- Lifecycle gate: Stage 6 implementation

## Context and scientific constraints

Stage A requires exactly one measured-line immutable event record, a persistent
common arena, five non-normalized package mechanisms, page-aligned linked-node
storage, and no platform-dependent defaults. The platform prefetch instruction
form and calibrated R2 distance remain later evidence and cannot be invented.

## Options considered

1. A compile-time host-cache-line record and runtime package selector.
2. Variable-size records with embedded logical identity and virtual policies.
3. A runtime-validated line-strided arena with a fixed two-word header, inert
   padding, and statically bound concrete package policies.

## Decision

Select option 3. Each record line begins with immutable unsigned 64-bit
`record_index` and aligned unsigned 64-bit `payload`; the remaining exact bytes
are zeroed inert padding. Arena line size, capacity, and allocation/page
alignment are mandatory explicit inputs. Preparation constructs and first
touches all records before sealing the arena for worker access.

Strong types keep record index, logical sequence, and accepted ordinal
distinct. Worker lookup returns an in-process pointer plus record index; durable
identity and checksums use indices and within-arena offsets/deltas only.

R0, R1, R2, L0, and L1 are distinct concrete policies. R1 computes
`d1=ceil(B/sizeof(pointer))`; R2 accepts only an externally calibrated whole-line
distance at least two lines and no more than `C/4`, rejecting cap collapse. Ring
policies expose producer write-intent and consumer retaining-read slot targets.
L1 exposes exactly one retaining-read successor-header target after the
successor acquire and before its event field demand. No event record or linked
recycler is a target. Platform instruction encoding stays behind a non-owning,
statically bound emitter interface and is not implemented in Stage 6.

Capacity selection consumes explicit cache evidence and actual ring/linked
footprints; it applies the protocol inequalities and never supplies a cache or
page default.

## Evidence

- Owner authorization to implement Stage 6 and acceptance of Q5 on 2026-08-17.
- Imported implementation specification Sections 3.1 through 4.2 and 11.1.
- ADR-0002, ADR-0003, ADR-0012, ADR-0016, and ADR-0024.

## Consequences and compatibility

Scientific effect: this maps the fixed record and package semantics without
selecting a platform prefetch form, capacity, or R2 calibration value.
Compatibility effect: record offsets/padding, alignment, target formulas,
static specialization, and distance validation are release-bound generated-code
and integrity obligations. A runtime treatment branch, event target, hidden
allocation, or default platform value is incompatible.

## Verification and acceptance tests

All Stage 6 invariant, target, corruption, checksum, no-allocation, sanitizer,
and dual-disassembler checks are required. Linked queue source changes caused
by the exact L1 seam and page alignment require Stage 5 provenance hashes and
queue generated-code evidence to be refreshed.

## Rollback or supersession

Layout or package-site changes require a superseding ADR and complete record,
queue, sanitizer, and generated-code requalification. Treatment semantics or a
different distance rule require protocol review and normally an amendment.

## Protocol-amendment assessment

No amendment is required; the representation implements the imported semantics
and leaves every platform-dependent value unresolved.
