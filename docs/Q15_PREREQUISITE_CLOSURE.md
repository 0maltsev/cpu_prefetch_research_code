# Q15 prerequisite-closure record

Status: **`Q15_P0_ACCEPTED_LOCAL_CLOSURE_COMPLETE; CLEAN_NO_AUTHORITY_CANDIDATE_SEALED`**

Date: 2026-08-24

Protocol: `2.0.0-pre.2`

Authority: repository-local Q15-P0 only. No stand access, dynamic
qualification, account or privilege change, MSR operation, calibration, pilot,
or confirmatory execution is authorized by this record.

## Accepted bundle

The owner accepted the recommended pre-Q15 prerequisite-closure bundle as
`Q15-P0` on 2026-08-24. It accepts D-048 through D-050:

| ID | Accepted local decision | Current result | Still required for Q15 |
|---|---|---|---|
| D-048 | Remove producer-idle, consumer-empty, and drain poll-count expiry; externalize hang containment | Runner/admission v3 and targeted long-gap/backlog tests | Exact two start-barrier values and exact external process wall-clock limit |
| D-049 | Intel 06_55H MSR 0x1A4 H0/H1 mapping for CPUs 0/1/26 | Narrow plan/transaction engine, pure plan command, schema, fake apply/readback/probe/restore tests | Exact candidate prestate, authorized adapter/command hashes, dynamic readback, both probes, restoration evidence |
| D-050 | Four distinct least-privilege roles and two-domain custody proposal | Authorization v2 schema and negative semantic tests | Exact accounts/person bindings, keys/capabilities, negative OS tests, paths/quotas/expiry/signatures and transfer receipt |

## Safe local commands

These commands use synthetic inputs only:

```sh
cmake --preset dev-gcc
cmake --build --preset dev-gcc --target cpu_prefetch_platform_tests \
  cpu_prefetch_lifecycle_tests cpu_prefetch_runner_tests cpu_prefetch_qualification
ctest --preset dev-gcc -R 'HardwarePrefetchMapping|LegitimateLongProducerIdleGap|LegitimateBacklogDrains|RunnerAdmission'
cmake --build --preset dev-gcc --target runner-schema-check qualification-schema-check
cpu_prefetch_qualification --hardware-prefetch-plan H1 \
  123456789abcdef0 fedcba9876543210 0f0f0f0f0f0f0f00
```

The sample values are explicit synthetic test data, not stand prestate.

## Fresh local verification

The accepted Q15-P0 source state passes the following repository-local checks:

- GCC 16/libstdc++ and Clang 22/libc++ development and release builds each
  pass 216/216 tests;
- GCC and Clang ASan/UBSan each pass 216/216 tests with no finding, and GCC
  TSan passes 216/216 tests with no race finding;
- Clang/libc++ TSan passes 214/214 applicable tests with no race finding; only
  the two documented global-allocator-hook tests are excluded because the
  runtime owns conflicting allocation interceptors, and both pass in every
  applicable matrix;
- formatting and Clang-Tidy pass over all 73 C++ translation units; the review
  found and fixed an exception-escape path in the pure qualification CLI;
- immutable protocol integrity passes for both snapshots, all 36 artifacts,
  eight authoritative hashes, 14 imported schemas, and 16 implementation
  Draft 2020-12 schemas;
- the runner v1/v2/v3, qualification, hardware-prefetch, and authorization
  schema suites pass all positive and negative fixtures without issuing
  authority or accessing an MSR; and
- the queue, workload, timing, storage, one-`PAUSE`, and combined-runner
  release generated-code gates pass both accepted disassemblers and all
  registered negative mutants.

These results are synthetic/software evidence only. The owner later authorized
one exact commit and clean no-authority sealing. Revision
`693f00b3878ed027dc09aea7916f149874fb12a1` produced archive SHA-256
`f94bb6922899caba24c26910bd1ba63018425d056fa5fd8282d1098415b8ace1`;
outer/internal hashes, clean extraction, and both nonprivileged self-tests
pass. The manifest grants no dynamic, pilot, confirmatory, or measurement
execution authority.

## Remaining exact Q15 blockers

1. Establish the four distinct principals, credentials/capabilities, negative
   access evidence, validity interval, and detached approval/signature.
2. Bind exact nonprivileged and privileged command argv, inverse, independent
   readback, probes, output artifacts, byte/CPU/wall limits, and stop rules.
3. Supply the exact two barrier bounds and external process-watchdog bound
   prospectively; none may depend on treatment outcomes.
4. Supply fresh exact-model/prestate evidence and complete H0/H1 apply,
   readback, regular/pointer probe, restoration, and quarantine plan.
5. Prove selected-pair clock, runtime atomics/layout, actual CPU/migration,
   address residency, storage capacity, two-domain custody, and transfer/recovery
   prerequisites for the exact candidate.

The
[`Q15 stand-qualification decision/input bundle`](Q15_STAND_QUALIFICATION_DECISION_BUNDLE.md)
now records Q15-S1/ADR-0051 acceptance of a separate qualification-only tool
and split Q15-R/Q15-W authority. The local fixed adapter, schemas, and blocked
preparation records grant neither stand access nor execution authority.

Only after every item exists with immutable hashes can exact Q15-R and later
prestate-bound Q15-W authorizations be prepared for separate owner approval.
They would authorize qualification only, never calibration or pilot work.
