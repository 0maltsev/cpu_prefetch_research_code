# Production runner entry profile

## Authority boundary

Q13 accepts ADR-0043 and authorizes implementation of the fail-closed runner
entry profile only. It does not authorize privileged controls, calibration,
pilot execution, or confirmatory execution. The Stage 16 stand-preflight
bundle remains preflight-only and intentionally does not gain the runner.

The implementation supplies `cpu_prefetch_runner_core` and the
`cpu_prefetch_runner` admission executable. The executable has only
`--self-test`, `--help`, and `--validate-admission`; it exposes no execution
command. The library supplies the ticket-gated static execution seam needed by
a later, separately authorized controller. This is production-path software,
not a production execution authority or a completed combined-worker release.

## Frozen Q13 mappings

| Identity | Frozen value |
|---|---|
| CPU-pair selection | `XEON-CPU-FETCH-P0-NEAR-0-1-FAR-0-26-v1` |
| `NEAR` | producer CPU 0, consumer CPU 1 |
| `FAR` | producer CPU 0, consumer CPU 26 |
| Runner | `STAGE17-STATIC-FIVE-PACKAGE-FAIL-CLOSED-v1` |
| Relax | `X86-PAUSE-ONE-PER-RELAX-SITE-v1` |

The pair choice is bound to the candidate stand and hashed topology evidence.
It is not clock, residency, affinity, or hardware-state qualification.
`X86PauseRelax::relax()` is stateless and contains exactly one `_mm_pause()`.
It has no adaptive count, scheduler call, sleep, memory access, or compiler
fence. The release generated-code check requires GNU and LLVM disassemblers to
find exactly one `PAUSE` and to reject a two-`PAUSE`/`sched_yield` mutant.

## Fail-closed admission

The implementation-owned Draft 2020-12 shape is
[`runner-admission-v1.schema.json`](../config/schemas/runner-admission-v1.schema.json).
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
  hardware-prefetch mapping, clock qualification, queue provenance, runtime
  atomic/layout evidence, and address residency;
- storage budget, two durability domains, calibration freeze, exact execution
  limits, authority/custody, and a separate pilot-execution authorization.

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

## Static specialization boundary

The controller-side dispatcher accepts only `R0`, `R1`, `R2`, `L0`, or `L1`
and invokes one distinct template specialization before the measurement
executor starts. `execute_static_measurement<Package>` compile-time-checks
that the capture backend declares the same package. The measured executor does
not inspect a package enum or normalize algorithm semantics. The existing
capture backend now exposes its package identity for this check.

The real platform prefetch emitter, affined combined worker, final controller
preparation/finalization adapter, and release-specific combined call-graph
audit remain blocked. Component and relax checks cannot substitute for that
later evidence.

## Commands

```sh
cmake --preset dev-gcc
cmake --build --preset dev-gcc --target cpu_prefetch_runner cpu_prefetch_runner_tests
ctest --preset dev-gcc --output-on-failure -L runner
cmake --build --preset dev-gcc --target runner-schema-check

cmake --preset release-gcc
cmake --build --preset release-gcc --target runner-relax-codegen-check
```

These commands execute software checks only. They perform no platform control,
calibration, pilot, or scientific measurement.

## Fresh implementation evidence

On 2026-08-22 the complete GCC development suite passed 198/198. The runner
label passed 11/11 in both GCC and Clang release builds and in all four
ASan/UBSan and TSan presets, including a concurrent four-preset invocation.
Both release compilers passed the strict GNU/LLVM one-`PAUSE` audit and its
negative mutant. The 69-file warnings-as-errors static pass, format check,
Draft 2020-12 runner-schema fixtures, imported-protocol integrity check,
document check, and safe release-policy/CI-command-parity checks also passed.

Review corrected four implementation defects before this evidence was
recorded: malformed or empty current identities could match an equally empty
synthetic trust anchor; a fixed test directory allowed independent sanitizer
processes to interfere; and one buffer-width expression triggered the strict
static rule. The fourth made the negative mutant's scheduler operation a tail
call that the audit did not explicitly count; both disassemblers now must see
exactly two `PAUSE` instructions and one call. No empirical or stand evidence
was produced by these checks.
