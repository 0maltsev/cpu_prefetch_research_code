# Production runner entry profile

## Authority boundary

Q13 accepts ADR-0043's pair and relax mappings. Q14 accepts ADR-0044 through
ADR-0046 and authorizes repository-local completion of the fail-closed runner,
qualification-only records, and candidate-bundle gate. Neither approval
authorizes stand access, dynamic qualification, privileged controls,
calibration, pilot execution, or confirmatory execution. The immutable Stage
16 stand-preflight bundle remains preflight-only and does not gain the runner.

The implementation supplies `cpu_prefetch_runner_core`, the
`cpu_prefetch_runner` admission executable, and the non-collecting
`cpu_prefetch_qualification` schema/profile self-test. The runner has only
`--self-test`, `--help`, and `--validate-admission`; it exposes no execution
command. The library supplies the ticket-gated static execution seam needed by
a later, separately authorized controller. This is production-path software,
not production execution authority. D-047 closes the physical software-
prefetch mapping and strict combined audit; the pilot-candidate target still
requires a clean exact revision and produces no execution authority.

## Frozen entry mappings

| Identity | Frozen value |
|---|---|
| CPU-pair selection | `XEON-CPU-FETCH-P0-NEAR-0-1-FAR-0-26-v1` |
| `NEAR` | producer CPU 0, consumer CPU 1 |
| `FAR` | producer CPU 0, consumer CPU 26 |
| Runner | `STAGE17-STATIC-FIVE-PACKAGE-FAIL-CLOSED-v2` |
| Relax | `X86-PAUSE-ONE-PER-RELAX-SITE-v1` |
| Software prefetch | `X86-64-PREFETCHW-PREFETCHT0-v1` |

The pair choice is bound to the candidate stand and hashed topology evidence.
It is not clock, residency, affinity, or hardware-state qualification.
`X86PauseRelax::relax()` is stateless and contains exactly one `_mm_pause()`.
It has no adaptive count, scheduler call, sleep, memory access, or compiler
fence. The release generated-code check requires GNU and LLVM disassemblers to
find exactly one `PAUSE` and to reject a two-`PAUSE`/`sched_yield` mutant.

## Fail-closed admission

The implementation-owned current Draft 2020-12 shape is
[`runner-admission-v2.schema.json`](../config/schemas/runner-admission-v2.schema.json).
The v1 schema remains readable but cannot arm the v2 profile.
The C++ loader additionally rejects unknown fields/enums, duplicate evidence
kinds or artifact IDs, unsupported packages/placements, an unaccepted pair or
relax/profile identity, zero watchdog values, build/binary/stand/binding drift,
a dirty source build, mutable or ineligible evidence, missing files, symlinks,
and SHA-256 disagreement.

Exactly one immutable, eligible, current-binding reference is required for
each of these kinds:

- protocol snapshot, source release, run plan, warm-up schedule, measurement
  schedule, and seed derivation;
- inventory, requested platform state, independently verified platform state,
  hardware-prefetch mapping, separately accepted software-prefetch mapping,
  clock qualification, queue provenance, runtime atomic/layout evidence, and
  address residency;
- storage budget, two durability domains, calibration freeze, exact execution
  limits, authority/custody, and an exact phase-scoped execution authorization.

`validate_admission_fields` is diagnostic and cannot construct a ticket.
Only `admit_runner` checks both the current trust anchor and every referenced
file before constructing the otherwise inaccessible `AdmissionTicket`.
Relative artifact paths resolve from the admission document directory but are
never used as scientific identities.

The admission command is:

```sh
cpu_prefetch_runner --validate-admission ADMISSION.json \
  --stand-id EXACT_STAND_ID --binding-id EXACT_BINDING_ID
```

No example containing invented platform values is shipped. There is no
default CPU, path, capacity, seed, distance, schedule, limit, hardware state,
authority, or authorization.

## Affined preparation and static specialization boundary

`AffinedObservationPreparation` executes once on each owner thread before the
start barrier. It applies singleton affinity through an injected backend,
independently reads the affinity mask and current CPU, then reads
`CPUID.80000001H:ECX[8]` through a separate injected capability backend. It
calls the private producer or consumer stream's first-touch preparation only
after every check agrees. A mismatch or missing PRFCHW capability cancels the
barrier as `PRE_RUN/worker_preparation`, starts no measurement, and preserves
partial preparation evidence. Repository tests inject fakes and never call
the Linux affinity backend.

`X86RetainingPrefetchEmitter` maps the R1/R2 producer seam to exactly one
`PREFETCHW`, the R1/R2 consumer seam to exactly one `PREFETCHT0`, and the L1
successor seam to exactly one `PREFETCHT0`. R0/L0 and the L1 producer contain
no hint. The explicit instruction template has no compiler memory clobber and
therefore is not a fence. There is no runtime fallback: unsupported PRFCHW
fails preparation.

The controller-side dispatcher accepts only `R0`, `R1`, `R2`, `L0`, or `L1`
and invokes one distinct template specialization before the measurement
executor starts. `execute_static_measurement<Package>` compile-time-checks
that the capture backend declares the same package. The measured executor does
not inspect a package enum or normalize algorithm semantics. The existing
capture backend now exposes its package identity for this check.

The full queue/package/timestamp/private-stream append operation is compiled
for all ten static producer/consumer shapes. GNU and LLVM call-graph audits
reject allocation, I/O, logging, compression, parsing, analysis, blocking or
scheduler calls, hidden queue retries, dynamic dispatch, and a deliberate
`malloc`/`sched_yield` mutant. The strict audit additionally requires the exact
instruction vector for every shape and rejects wrong-write, wrong-read, and
duplicate-read mutants. GCC 16.1.1 and Clang 22.1.6 each pass under both GNU
Binutils 2.46 and LLVM 22.1.6.

## Qualification and authority records

[`qualification-evidence-v1.schema.json`](../config/schemas/qualification-evidence-v1.schema.json)
and typed builders cover selected-pair clock counts, runtime atomic/layout
facts, actual CPU/migration, before/during/after address residency, and the
exact D-047 mapping plus both per-worker PRFCHW observations and codegen gates.
They derive `eligible` from supplied observations and bind stand, pair,
revision, binary, source artifacts, and canonical bytes. They collect nothing.

[`stage17-authorization-v1.schema.json`](../config/schemas/stage17-authorization-v1.schema.json)
defines future Q15 and Q16 envelopes without issuing one. Its semantic check
rejects omnibus/wildcard/latest/unresolved scope, overlapping authority,
invalid expiry, same-domain custody, missing predecessors, run-count drift,
confirmatory namespaces, and enabled prohibited actions.

An exact future record is checked, but never issued or executed, with:

```sh
python3 tools/check_stage17_authorization_schema.py --document AUTHORIZATION.json
```

## Commands

```sh
cmake --preset dev-gcc
cmake --build --preset dev-gcc --target cpu_prefetch_runner cpu_prefetch_runner_tests
ctest --preset dev-gcc --output-on-failure -L runner
cmake --build --preset dev-gcc --target runner-schema-check qualification-schema-check

cmake --preset release-gcc
cmake --build --preset release-gcc --target runner-relax-codegen-check
cmake --build --preset release-gcc --target runner-combined-codegen-audit
cmake --build --preset release-gcc --target runner-combined-codegen-check
```

These commands execute software checks only. They perform no platform control,
calibration, pilot, or scientific measurement.

## Fresh implementation evidence

On 2026-08-22 the Q14 tree passed 207/207 GCC development tests and the complete
Clang/libc++ development suite. After D-047 added capability and mapping tests
plus a fifth qualification artifact kind, a fresh 2026-08-23 pass completed
208/208 development tests under each compiler, 208/208 in both ASan/UBSan
matrices, 208/208 under GCC TSan, and the applicable 206/206 under Clang/libc++
TSan. Both release compilers pass the strict GNU/LLVM combined audit across ten
operations, exact instruction vectors, and four mutants. The clean exact
candidate still must be sealed and verified. No repository-local check or
bundle grants execution authority.

Review corrected four implementation defects before this evidence was
recorded: malformed or empty current identities could match an equally empty
synthetic trust anchor; a fixed test directory allowed independent sanitizer
processes to interfere; and one buffer-width expression triggered the strict
static rule. The fourth made the negative mutant's scheduler operation a tail
call that the audit did not explicitly count; both disassemblers now must see
exactly two `PAUSE` instructions and one call. No empirical or stand evidence
was produced by these checks.
