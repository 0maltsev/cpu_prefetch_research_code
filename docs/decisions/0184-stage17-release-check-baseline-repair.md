# ADR-0184: Repair baseline release-check failures

- Status: `ACCEPTED`
- Date: 2026-11-01
- Decision ID: D-184
- Protocol version: `2.0.0-pre.3`, unchanged
- Scope: required release prerequisites for the EXT007 continuation
- Lifecycle gate: local engineering; fresh source policy and release still required

## Decision

Fresh checks with the restored accepted tools reproduce three baseline
format failures and three focused runner static-analysis diagnostics. Repair
these prerequisites within their existing behavior, rather than relaxing the
checks or changing experiment semantics.

Apply LLVM 22 formatting to `src/platform/platform.cpp`,
`tests/platform_model_test.cpp`, and
`tools/q15_qualification_evidence_tool_main.cpp`. Their changes consist of
layout and equivalent adjacent string-literal formatting.

In the existing best-effort Q15 transition-delay helper, use the existing
nonthrowing `Result::value_if` accessor and an explicit null check instead of
checked `value()` calls inside the `noexcept` function. Preserve zero-delay
behavior, the same clock reads, early exit on a failed clock result, unsigned
elapsed-time arithmetic, and the same requested duration. This does not change
the helper's existing virtual-backend exception contract, add a timing
estimator, or alter counted probe or measurement boundaries.

Make the two mapping tests' optional checks visible through ordinary C++
branches. A missing registered mapping still fails fatally, and both exact
mapping identifiers remain asserted. Do not suppress optional-access
diagnostics, disable assertions, or weaken the compiler policy.

The subsequent full static check exposes 27 further baseline diagnostics:
checked optional access in platform/clock/timing tests and same-width
sequence/spin-count parameters in the spin-only clock-exchange overload.
Use ordinary checked test-value helpers (including the timing test's existing
helper), preserving every expected observation and failure assertion. Give
the spin-only overload a `CrossCoreExchangeSpinLimit` parameter and update
all callers with the same counts. Its default remains exactly two billion
iterations; the clock-backed overload retains the same spin and wall-clock
fallback controls. No exchange, polling, sleep, timeout, or memory-order
behavior changes. This is an internal source API tightening, requiring caller
recompilation and the same fresh qualification as the other source changes.

## Verification and provenance

These are behavior-preserving repairs. Use the existing runner, Q15, and
platform tests plus strict formatting/static analysis; no tests that merely
mirror the new accessor syntax are needed. Rebuild affected sanitizer targets
as appropriate and record actual outcomes after execution.

The repaired platform (20), timing (18), and clock-pair (2) tests pass in
the isolated accepted glibc 2.43 runtime. All 20 timing/clock-pair cases pass
under GCC and Clang/libc++ ASan/UBSan and TSan. The earlier focused runner
and Q15 checks pass 29 + 12 cases under both compiler sanitizer matrices.
Global formatting and the focused strict clang-tidy checks pass; full static
analysis remains in progress. The
[2026-11-02 evidence](../evidence/stage17/LOCAL-VERIFICATION-EXT007-20261102-01/README.md)
records the restored runtime and remaining full-suite prerequisites.

`src/runner/stage17_fixed_action.cpp` is source-bound by prospective policy
v54. Keep that committed policy and every predecessor unchanged. Its author
check must now detect source drift until a successor policy binds the repaired
source and the completed diagnostic implementation. Do not regenerate v54 in
place or use it as execution authority. No external journal, qualification,
scientific result, or hardware state is migrated by this repair.
