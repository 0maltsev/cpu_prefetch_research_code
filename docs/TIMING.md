# Stage 8 Timing Model

Protocol version: **`2.0.0-pre.2`**; clock suite unchanged from pre.1

This document describes the non-measuring Stage 8 implementation of accepted
D-009/ADR-0030. The implementation does not select worker CPUs, qualify an
experiment stand, choose the physical raw-row encoding, run a scientific
comparison, or subtract timestamp overhead.

## Clock contract

The production clock suite is
`LINUX-CLOCK-MONOTONIC-RAW-VDSO-PS-v1`. Each read calls the glibc ABI
`clock_gettime(CLOCK_MONOTONIC_RAW)` and places
`std::atomic_signal_fence(std::memory_order_seq_cst)` immediately before and
after the call. These are compiler-only fences: they add no C++ inter-thread
synchronization and are not a replacement for the queue's release/acquire
operations.

`ClockSample` retains both the absolute integer nanoseconds returned by the
clock and the logical picosecond value. Given the immutable origin sampled by
the controller at the completed start barrier, conversion is exactly:

```text
relative_ps = (absolute_ns - origin_absolute_ns) * 1000
```

Seconds/nanoseconds construction, origin subtraction, and multiplication are
checked before use. Invalid `tv_nsec`, call failure, underflow, or overflow
fails closed. Values are not rounded: every successful value is a multiple of
1000 ps. `MonotonicRawClock::capture_origin()` only supplies the read; the
Stage 10 controller remains responsible for placing it at the accepted barrier
completion point and resolving/priming the clock before worker release.

The code can prove that the versioned x86-64 vDSO symbol exists. Proof that the
glibc sequence actually takes no syscall fallback is deliberately an external
qualification input: D-009 requires a 10,000,000-call traced probe with zero
syscalls and failures on the exact release/stand.

## Exact observation boundaries

The timestamped queue seam is a static template call. It has no virtual
dispatch, retry, blocking wait, allocation, exception, logging, or runtime
treatment selection.

| Symbol | Implemented point |
|---|---|
| `a_i` | Validated schedule deadline minus schedule origin; no clock read |
| `b_i` | First read after the due-deadline poll exits, before handling |
| `c_i` | First read after deterministic record lookup |
| `u_i` | Last read before the one `try_enqueue` call |
| `p_i` | Accepted only: read immediately before ring-slot or linked-successor release publication |
| `r_i^e` | First read after the enqueue attempt returns `ACCEPTED` or `FULL` |
| `v_i` | Last read before each dequeue poll; retained only for the successful poll |
| `q_i` | Read immediately after the acquire observes an item, before reuse, prefetch, or record action |
| `r_i^d` | First read after successful dequeue returns |
| `f_i` | First read after immutable index/payload loads and private checksum mix |

The queue boundary observer preserves algorithm-specific semantics. For the
ring, `p` precedes the slot release store and `q` follows the successful slot
acquire load before the slot-clear release. For the linked queue, `p` precedes
the successor-link release store and `q` follows the successful successor
acquire load before L1 prefetch, recycler work, or record access. R0/R1/R2 and
L0/L1 remain distinct static package specializations.

An empty dequeue takes `v` but emits no consumer observation. A `FULL` producer
observation contains `b,c,u,r^e`, outcome `FULL`, and neither `p` nor accepted
ordinal. A clock failure emits no fabricated observation. A failure at linked
`p`, after a recycler node has been prepared but before publication, is a
terminal run failure; the run must stop and rebuild its prepared queue rather
than continue from that partial state. This is consistent with D-009's
fail-closed rule and is not a retry path.

In-memory `ProducerObservation` and `ConsumerObservation` retain absolute raw
nanoseconds and converted picoseconds. Conversion to the imported logical row
types preserves the picosecond fields. Stage 8 did not select a durable codec.
Q9 later accepted D-010/ADR-0032, which Stage 11 implements and binds
without changing these timestamp meanings.

## Post-run equations

`derive_joined_record` is an offline operation. It accepts only a complete
`ACCEPTED` producer row and a consumer row with matching `run_id`, accepted
ordinal, and validation record index. Equal timestamps are valid. Each local
stream must be nondecreasing, and `p_i <= q_i`; response overlap is allowed, so
the code does not invent a total order between `r_i^e` and consumer invocation.

| Field | Exact equation | Role |
|---|---|---|
| Producer lateness | `b_i - a_i` | Nested diagnostic |
| Pointer lookup | `c_i - b_i` | Nested diagnostic |
| Enqueue service | `r_i^e - u_i` | Nested diagnostic |
| Admission delay | `p_i - a_i` | Additive primary component |
| Queue residence | `q_i - p_i` | Additive primary component |
| Dequeue service | `r_i^d - v_i` | Nested diagnostic |
| Post-dequeue delivery | `f_i - q_i` | Additive primary component |
| Consumer action | `f_i - r_i^d` | Nested diagnostic |
| End to end | `f_i - a_i` | Primary latency |

The validator proves exactly
`end_to_end = admission + residence + post_dequeue_delivery`. The other
intervals are nested diagnostics and are never added to that identity. A
negative implied interval, mismatched identity, `FULL` input, or failed
additive reconciliation returns a stable semantic error and no joined row.

## Qualification interface and gates

The implementation separates calculation from platform collection so Phase 9
can supply explicit CPU identities and affinity evidence without an invented
default. It implements the exact `CLOCK-QUAL-LMRV1` evaluations:

- static bare-metal Linux x86-64, TSC clocksource/invariance, no override or
  unstable report, vDSO symbol/execution, 10,000,000-call zero-syscall probe,
  generated-code pass, and resolution no worse than 1,000 ps;
- per selected core: exactly 100,000 prime reads, 10,000,000 retained deltas,
  zero failures/regressions, at most 10 ties, inverse-ECDF p99.9 no greater
  than 1,000,000 ps, p99.999 no greater than 10,000,000 ps, and explicit
  singleton-affinity/CPU readback;
- per direction of the selected pair: exactly 100,000 four-timestamp exchanges
  in each of three windows spanning at least 60 seconds, zero causal
  regressions, nonempty intersection inside +/-100,000 ps, width no greater
  than 200,000 ps, and exact rational midpoint range no greater than 50,000 ps;
- a pair passes only when both directions pass.

Synthetic short sequences can test the equations and limits but carry
`accepted_policy_sample_count=false` and cannot pass qualification. Complete
streams remain caller-owned qualification artifacts; summary evaluation never
replaces or truncates them.

`CLOCK-OVERHEAD-UNCORRECTED-v1` is explicit in the API. Diagnostic summaries
for read-to-read or exact-boundary duration streams report order statistics
with `correction_applied=false` and `primary_timestamps_unchanged=true`. No
derived timestamp or latency is adjusted.

## Generated-code audit

The release-only `timing-codegen-check` uses GNU Binutils and LLVM 22
disassembly plus source/hash rules. It covers the production reader and all ten
enqueue/dequeue package specializations. The audit requires the selected clock
call and rejects direct `syscall`, `RDTSC/RDTSCP`, `CPUID`, hardware fences,
locked instructions, allocation, exception, logging, and I/O calls. Source
rules bind `p` before release publication, `q` after acquire and before
prefetch/reuse, the complete producer/consumer read sequence, and both compiler
fences. Negative mutants move `p`, move `q`, remove the compiler fences, add a
hardware fence, change the clock ID, and force a syscall; all must be rejected.

The reviewed GCC 16.1 release assembly retains `CLOCK_MONOTONIC_RAW` as clock
ID 4, places the clock call before ring/linked release publication, places it
after successful acquire observation, and places L1's target emission after
`q`. It contains no direct timing-counter, syscall, or hardware-fence
instruction in the audited worker slices. This is correctness evidence about
operation placement only, never a claim about latency quality.

## Evidence boundary

Deterministic fake-clock tests cover exact boundaries, ties, overflow, failure,
cross-thread publication, `FULL`, and all interval equations. A 10,000-read
development-host `CLOCK_MONOTONIC_RAW` smoke verifies only that the reader
works and returns nondecreasing exactly converted values here. It is not the
accepted 10,000,000-read per-core probe, a syscall trace, cross-core
qualification, exact-boundary cost artifact, or experiment-platform evidence.

Q13 selects CPUs `(0,1)` and `(0,26)` as the near/far pair inputs, but it does
not dynamically qualify them. Measurement remains prohibited until the exact
release, stand, pair-specific dynamic/before-block checks, raw storage, controller, and
later readiness gates all pass.
