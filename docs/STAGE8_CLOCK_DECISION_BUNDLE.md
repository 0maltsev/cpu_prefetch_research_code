# Stage 8 Clock Decision Bundle

Protocol version: **`2.0.0-pre.1`**

Decision ID: **D-009**

Approval question: **Q7**

State: **`ACCEPTED_BY_Q7`**

The repository owner accepted this exact bundle by answering
`Q7 - accept the bundle` on 2026-08-20. Acceptance freezes D-009 and permits
Stage 8 implementation. It does not qualify the stand, select worker CPUs,
implement timing code, authorize measurement, or report a performance result.

## Decision record

| Field | Accepted value |
|---|---|
| ID | D-009 |
| Classification | Timing/platform mapping with scientific interpretation and measured-path consequences |
| Owners | Repository owner; timing owner; platform owner; queue-correctness owner; code-generation reviewer |
| Deadline / gate | Accept before Stage 8 implementation; pass implementation and selected-core qualification before Stage 8/16 acceptance as applicable |
| Selected clock suite | `LINUX-CLOCK-MONOTONIC-RAW-VDSO-PS-v1` |
| Boundary policy | `TIMESTAMP-BOUNDARIES-BRACKETED-LMRV1` |
| Qualification policy | `CLOCK-QUAL-LMRV1` |
| Overhead policy | `CLOCK-OVERHEAD-UNCORRECTED-v1` |
| Supersession | New suite/policy ID, superseding ADR, and full requalification; old artifacts are never reinterpreted |

## Protocol constraints preserved

The imported protocol fixes every logical timestamp, its order, and every
derived equation. It requires one clock that is monotonic on both worker CPUs,
a documented or calibrated conversion to time, before-block cross-core offset
and drift checks, explicit serialization that does not alter queue memory
order, and calibration of the exact timestamp sequence. The source and
conversion cannot change inside a run or temporal block.

This decision does not alter queue algorithms, release/acquire order, arrival
deadlines, logical rows, additive equations, or the distinction between
producer and consumer observations. It supplies the previously open clock and
linearization-boundary mapping. Any review finding that the mapping changes a
protocol-fixed meaning stops Stage 8 and requires a protocol amendment rather
than an implementation workaround.

## Options considered

| Option | Merits | Material problem | Decision |
|---|---|---|---|
| Direct invariant TSC with `RDTSCP` | Low-level counter, CPU identifier, compact reader | The target is dual-socket; direct cross-socket synchronization is not guaranteed. CPUID leaf `0x15` reports a ratio but no crystal frequency, so an exact stand conversion is not self-describing. Direct serialization also creates a queue-ordering/fence risk. | Reject for v1; retain only as qualification diagnostic evidence |
| `clock_gettime(CLOCK_MONOTONIC_RAW)` through x86-64 vDSO | System-wide non-NTP-adjusted time, documented integer nanoseconds, exact conversion to schedule picoseconds, kernel owns hardware-counter conversion | More reader overhead and a kernel/glibc/vDSO compatibility surface; syscall fallback must be rejected | **Select** |
| `CLOCK_MONOTONIC` | System-wide and monotonic | Incremental time adjustments change the rate and are unnecessary for this experiment | Reject |
| `clock_gettime` syscall fallback | Same logical clock ID | Kernel transition is an unaccepted measured-path mechanism and can materially change read cost | Reject |
| HPET, ACPI PM, PTP, or another source | Possible independent reference | No complete selected-source, access, conversion, skew, or cost evidence exists | Reject for v1 |

The selected source is not a claim that direct TSC is defective on this stand.
It avoids depending on an unproved cross-socket TSC relationship and avoids
inventing the missing crystal-frequency value.

## Evidence

### Imported and accepted repository evidence

- Implementation specification Sections 5.4, 5.5, 8.1, and 8.2; the timestamp
  data dictionary; and the clock-acceptance freeze-checklist row.
- ADR-0003, ADR-0008, ADR-0012, ADR-0014, ADR-0016, ADR-0018, ADR-0024, and
  ADR-0029.
- The published [Stage 8 capability archive](evidence/stage8/20260820T182948Z/README.md),
  whose outer SHA-256 is
  `209aa2ea45b73cfe0ea12a62f0ac060692070d5babe8c60d1095ea9eb2991aca`
  and whose internal manifest passes.

That archive records bare-metal Ubuntu 26.04, Linux `7.0.0-27-generic`, x86-64,
an Intel Xeon Gold 6230R system with 104 online logical CPUs across two sockets,
kernel clocksource `tsc`, `rdtscp`, `constant_tsc`, `nonstop_tsc`, the invariant
TSC CPUID bit, and a one-nanosecond reported resolution for
`CLOCK_MONOTONIC_RAW`. CPUs `0-103` are inventory only, not an accepted worker
placement. The archive contains no dynamic skew, drift, cost, migration, or
generated-code pass and therefore does not qualify the source by itself.

### Primary technical sources

- The [Linux `clock_gettime` contract](https://man7.org/linux/man-pages/man3/clock_gettime.3.html)
  defines `CLOCK_MONOTONIC_RAW` as a nonsettable raw hardware-based clock not
  subject to NTP or `adjtime` rate adjustment.
- The [Linux vDSO contract](https://man7.org/linux/man-pages/man7/vdso.7.html)
  documents the x86-64 `__vdso_clock_gettime` symbol and the userspace path that
  avoids entering the kernel.
- The [Linux timekeeping documentation](https://www.kernel.org/doc/html/latest/timers/timekeeping.html)
  describes clocksource-to-nanosecond conversion.
- The [Linux x86 timekeeping documentation](https://www.kernel.org/doc/html/latest/virt/kvm/x86/timekeeping.html)
  warns that multi-socket TSCs must not be assumed synchronized and documents
  the need for serialization and migration handling.
- The [Intel architecture manuals](https://www.intel.com/content/www/us/en/developer/articles/technical/intel-sdm.html)
  are the source for TSC/RDTSC/RDTSCP and fence semantics used only when
  auditing the kernel/vDSO and diagnostic reader.
- The [C++ fence specification](https://eel.is/c++draft/atomics.fences)
  specifies that `atomic_signal_fence` inhibits compiler reordering without
  emitting the hardware fence of `atomic_thread_fence`.

## Accepted exact clock contract

### Source, path, and identity

- Call `clock_gettime(CLOCK_MONOTONIC_RAW, &timespec)` through the accepted
  glibc ABI.
- The eligible release must resolve this clock through the x86-64 vDSO. Stage 8
  must prove that the qualified call sequence executes no `clock_gettime`
  syscall. A syscall fallback is a clock-qualification failure, not a runtime
  fallback.
- Resolve and prime the function, vDSO data, output pages, and all relocations
  before measurement. No first-use resolution or planned page fault is allowed
  in the timed path.
- Record the suite ID, protocol version, kernel release/config identity, current
  kernel clocksource, glibc identity, vDSO ELF identity/hash and symbol version,
  compiler/build/link identities, reported resolution, qualification-policy ID,
  boundary-policy ID, and acceptance-record hash.
- The clocksource must remain `tsc` for the qualified build and temporal block.
  A source change or unstable-clock message fails closed; no automatic switch
  to TSC, HPET, `CLOCK_MONOTONIC`, or a syscall is allowed.

### Compiler boundary and queue memory order

Every production read is surrounded by
`std::atomic_signal_fence(std::memory_order_seq_cst)` before and after the
`clock_gettime` call. This is the accepted compiler-ordering mechanism only.
The wrapper must add no C++ inter-thread synchronization and no `MFENCE`,
`SFENCE`, `CPUID`, `RDTSC`, or `RDTSCP` instruction. The vDSO's own hashed and
qualified implementation remains part of the selected clock source.

The existing queue release/acquire operations and their order remain byte-for-
byte semantically unchanged. Timing is statically specialized and directly
inlined at the queue boundary: no virtual call, runtime treatment branch,
allocation, exception, retry, log, or blocking wait is introduced. The Stage 5
wait-free/lock-free claims continue to cover the queue algorithm only, not the
external clock implementation.

### Integer conversion and origin

The API returns integer seconds and nanoseconds. Stage 8 validates
`0 <= tv_nsec < 1,000,000,000`, computes checked absolute nanoseconds, subtracts
the immutable run origin in nanoseconds, and multiplies the nonnegative relative
value by exactly `1000` to obtain logical picosecond ticks:

```text
sample_ps = (sample_absolute_ns - run_origin_absolute_ns) * 1000
```

All overflow/underflow bounds are proved before measurement for the complete
horizon and drain. Every observed timestamp is therefore a multiple of 1000 ps;
the picosecond field is an exact common representation, not a claim of
sub-nanosecond clock resolution.

At the two-worker start barrier, the barrier completion step takes the origin
sample before releasing either worker. For a decoded schedule deadline `d` and
schedule origin `o`, the logical `scheduled_arrival` is exactly `d-o`; runtime
comparison is against that value in the same relative picosecond domain. The
complete Stage 7 deadline remains unchanged. No rounding or schedule
regeneration occurs in Stage 8.

### Exact boundary mapping

| Symbol | Operational timestamp point |
|---|---|
| `a_i` | Exact validated Stage 7 deadline minus its declared schedule origin; no clock read |
| `b_i` | A fresh read immediately after the due-deadline poll exits, before event handling |
| `c_i` | First read after deterministic record-index/pointer lookup completes |
| `u_i` | Last read immediately before entering the single `try_enqueue` attempt |
| `p_i` | Last read immediately before the successful ring-slot or linked-successor release publication; accepted rows only |
| `r_i^e` | First read after `try_enqueue` returns `ACCEPTED` or `FULL` |
| `v_i` | Last read immediately before each `try_dequeue`; retained only for the successful attempt |
| `q_i` | First read immediately after the acquire operation observes the successful ring pointer or linked successor, before reuse/prefetch/action work |
| `r_i^d` | First read after the successful `try_dequeue` returns |
| `f_i` | First read after immutable index/payload loads and the fixed private checksum update complete |

The `p_i`-before-publication and `q_i`-after-observation rule brackets the true
queue handoff and prevents response overlap from creating a false negative
residence interval. It prospectively includes the residual publication-side
clock-call cost in the uncorrected residence value. This effect is fixed for
all packages and is reported through the exact-boundary cost calibration; it
is not tuned from queue results.

Empty dequeue polls still take `v` so a successful invocation is observable;
an empty attempt publishes no observation row and executes the protocol's
separate relax instruction. A `FULL` enqueue has no `p_i` or accepted ordinal.

### Overhead policy

Select `CLOCK-OVERHEAD-UNCORRECTED-v1`:

- ordered raw timestamps and raw derived intervals are primary;
- no scalar, median, quantile, per-boundary, or per-run clock-cost subtraction
  is applied;
- no corrected latency field is fabricated;
- the complete read-to-read and exact-boundary calibration distributions are
  retained as diagnostic artifacts;
- negative corrected intervals cannot occur because correction is disabled.

Introducing correction later requires a new policy ID, a superseding ADR, and
prospective requalification. It may not rewrite existing raw artifacts.

### Failure handling

A preparation-time call failure, invalid `timespec`, overflow proof failure,
missing vDSO path, or failed qualification rejects the build/platform/pair
before measurement. An unexpected call failure, regression, timestamp-order
failure, source change, migration/affinity failure, or failed before-block check
invalidates the run and emits only append-only evidence actually available.
The worker path does not throw, log, block, switch source, or fabricate a row.

## Accepted qualification and acceptance limits

These treatment-blind limits are owner choices. They are not inferred from a
queue result and must not be loosened after observing treatment performance.
Every exact worker CPU pair must be supplied explicitly by the later platform
record; this bundle supplies no default placement.

### Static gates

1. Bare-metal Linux x86-64; supported `CLOCK_MONOTONIC_RAW`; current clocksource
   exactly `tsc`; no kernel unstable-clock report or clocksource override.
2. `clock_getres(CLOCK_MONOTONIC_RAW)` succeeds and reports no worse than
   `1,000 ps`.
3. The x86-64 vDSO exports the versioned clock symbol, the glibc call uses it,
   and a `10,000,000`-call probe observes zero clock syscalls and zero failures.
4. Each worker has a singleton affinity mask; the selected CPU stays online;
   pre/post `sched_getcpu` and affinity readback match. Suspend, CPU hotplug, and
   affinity changes are forbidden during qualification and a run.
5. The exact release build and all clock/queue boundary objects pass the dual-
   disassembler and source/hash review below.

### Per-core monotonicity, resolution, and read cost

For each explicitly selected worker CPU, prime `100,000` reads and then retain
`10,000,000` consecutive read-to-read deltas from the exact production reader.
Use the protocol's inverse-ECDF order statistic `X_(ceil(pN))`.

| Gate | Accepted limit |
|---|---|
| Clock call failures or invalid `timespec` | exactly `0` |
| Negative deltas / regressions | exactly `0` |
| Equal adjacent samples | at most `10` in `10,000,000` (`1e-6`) |
| Read-to-read p99.9 | at most `1,000,000 ps` (1 microsecond) |
| Read-to-read p99.999 | at most `10,000,000 ps` (10 microseconds) |

The maximum, all ties, interrupted outliers, CPU identity, and complete ordered
calibration stream remain recorded even though only the declared gates decide
eligibility.

### Cross-core offset and drift

For every explicit producer/consumer CPU pair, run `100,000` four-timestamp
release/acquire exchanges in each direction in three windows whose first and
last starts are at least 60 seconds apart. For an A-to-B exchange, record A
request-send `t1`, B request-receive `t2`, B response-send `t3`, and A
response-receive `t4`. The offset interval is exactly:

```text
[lower, upper] = [t3 - t4, t2 - t1]
```

For a window, take `lower=max(lower_i)` and `upper=min(upper_i)` without
discarding exchanges. Acceptance requires:

- every directional window has `lower <= upper`;
- every complete interval is contained in `[-100,000 ps, +100,000 ps]`;
- interval width is at most `200,000 ps`;
- the range of exact interval midpoints across the three windows is at most
  `50,000 ps`; half-picosecond midpoints are retained as rationals;
- all `600,000` causal handoffs per direction satisfy receive time greater
  than or equal to send time; regressions are exactly zero.

The same full three-window check runs before every temporal block, as required
by the protocol. Failure makes the pair/block ineligible. It never triggers a
different clock or outcome-dependent placement.

### Generated-code and runtime-path gates

For every package specialization and accepted release toolchain:

- prove `b,c,u,p,r^e,v,q,r^d,f` reads remain at the tabled boundaries;
- prove `p` precedes the unchanged release publication and `q` follows the
  unchanged successful acquire observation;
- prove compiler fences surround each read but add no queue synchronization or
  direct counter/fence instruction in the wrapper;
- prove the queue atomic widths, memory orders, and order are unchanged;
- prove absence of syscall instructions, allocation, exception, logging, I/O,
  virtual dispatch, runtime treatment selection, and hidden retry in the
  compiled worker slice;
- bind GNU and LLVM disassembly, source/object/executable/build/vDSO identities,
  rules, and reviewer record by SHA-256;
- require negative mutants that move `p`, move `q`, remove a compiler fence,
  add a hardware fence, change the clock ID, or force a syscall to fail.

Stage 8 must also pass conversion/overflow goldens, boundary-order and exact-
equation tests, clock-regression/skew/drift/cost failures, call-failure partial
artifacts, source-change rejection, dual compiler/library tests, ASan/UBSan,
TSan where technically applicable, and a proof that queue outcomes cannot
select the clock or modify qualification.

## Scientific and compatibility effects

Scientific effect: raw timestamps are quantized to nanosecond clock samples but
represented exactly in the schedule's picosecond domain. The bracketing rule
prospectively fixes instrumentation placement and retains its cost instead of
estimating it away. The same source, boundary map, and no-correction rule apply
to every package and treatment. No queue or performance outcome selected the
decision.

Compatibility effect: Linux x86-64, `CLOCK_MONOTONIC_RAW`, vDSO use, exact
nanosecond-to-picosecond conversion, origin rule, boundary map, limits, and
identity fields are suite-defining. Unknown or mismatched identities fail
closed. Direct TSC readers and syscall fallback are incompatible clock suites,
not transparent optimizations. The physical raw-row encoding remains D-010 and
is not selected here.

## Lifecycle consequences

Q7 is accepted, so Stage 8 implementation may begin. Q7 alone does not close
Stage 8: the implementation, generated code, dynamic qualifier, and explicit
CPU-pair evidence must pass. If Phase 9 has not yet supplied a worker pair,
Stage 8 may finish its software slice but the eligible-stand clock acceptance
record remains pending; no CPU pair may be inferred from the inventory archive.

Measurement, pilot, and confirmatory execution remain prohibited by their
later gates regardless of Q7 or Stage 8 completion.

## Approval record

The repository owner accepted every value, boundary, limit, and failure rule
above on 2026-08-20 by answering exactly:

```text
Q7 - accept the bundle
```

D-009 and ADR-0030 are therefore `ACCEPTED`. Later implementation,
generated-code, dynamic qualification, and explicit CPU-pair gates remain
open and fail closed; no value from static inventory becomes a default.
