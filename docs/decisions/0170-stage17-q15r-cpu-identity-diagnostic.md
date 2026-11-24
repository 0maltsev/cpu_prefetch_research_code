# ADR-0170: Stage 17 Q15-R CPU-identity diagnostic instrumentation

- Status: `ACCEPTED`
- Date: 2026-10-08
- Classification: Diagnostic instrumentation, no behavior change
- Decision owners: Protocol owner; repository owner
- Protocol version: `2.0.0-pre.3`
- Supersedes: None

## Context

The first-ever real Q15-R attempt on a new stand (`cpu-prefetch-v3`,
185.184.128.107, Intel Xeon Gold 6230R) failed at the CPU-identity check
in `run_q15_phase_session_worker`'s session preparation
(`src/runner/stage17_fixed_action.cpp`, `S17-Q15R-CPU`:
"Q15-R requires the accepted 06_55H CPU") -- even though every
independent, real signal confirms this stand's CPU genuinely is family
6 / model 0x55: `/proc/cpuinfo` reports `cpu family: 6`, `model: 85`
(0x55) uniformly across all 104 logical CPUs (no heterogeneity, no
hypervisor CPUID masking -- `systemd-detect-virt` reports `none`), and
a standalone static binary executing the exact same raw `__get_cpuid`
leaf-1 decode this session's codebase uses independently confirmed
`family=6 model=0x55` on the real stand.

This rules out a genuine CPU-identity mismatch. The remaining
possibility is a bug specific to the compiled worker process's own
invocation context (its restricted environment, `setpriv`-dropped
privileges, or something else in `run_q15_phase_session_worker`'s own
code path) that a standalone diagnostic binary run outside that
context cannot reproduce.

## Decision

Add one `std::fprintf(stderr, ...)` line immediately after
`platform::read_x86_family_model()` is called in the Q15-R
CPU-identity check, printing whether `identity` is present and its
decoded `family`/`model` (or showing zeros if absent), alongside the
expected values. This is a pure diagnostic addition: no control flow,
no stored evidence, no change to the pass/fail decision the existing
check already makes. The next real, signed Q15-R attempt against this
stand will capture this line in the worker's real stderr tail
(`worker_stderr_tail` in the session failure record, or stdout on
success), giving a definitive, real answer to why the check is
failing in-process without requiring further guessing.

This edit changes `src/runner/stage17_fixed_action.cpp`'s bytes, which
are individually pinned by `config/stage17/stage17-operational-
evidence-admission-policy-v47.json`'s own `bindings` entry (the same
file ADR-0159/ADR-0166/ADR-0168 already re-pinned three times for real
functional changes to this exact file). A new policy generation (v48)
re-pins it again, and a matching `stage17_state_journal_v42.py`
successor propagates the new semantic-verifier generation through the
admission journal's ancestor-walk mechanism, exactly mirroring the
ADR-0168/v41 pattern.

## Consequences

Scientific effect: none -- this changes only which bytes a stderr
diagnostic line emits; no measured or frozen quantity is affected, and
no admission-time semantic check's logic changes.

Compatibility effect: any pilot-candidate bundle built from a commit
at or after this one needs a fresh `S17-EXT-001` through `S17-EXT-003`
admission (worker/binary identity changes), exactly as every prior
re-pin of this same file required.

## Rollback or supersession

This diagnostic line is intentionally left in place rather than
reverted immediately after use -- it is inert on the success path
(prints the matching values and continues) and provides a permanent,
cheap breadcrumb if this exact check ever fails again on a future
stand. A future ADR may remove it once the underlying question this
ADR exists to answer is resolved and documented.
