# Repository Status

Protocol snapshot: **`2.0.0-pre.1`**

Repository state: **`STAGE_3_BUILD_AND_CI_FOUNDATION_COMPLETE`**

Readiness verdict: **`READY_FOR_STAGE_4_NOT_READY_FOR_MEASUREMENT`**

## Readiness by area

| Area | State | Evidence or blocker |
|---|---|---|
| Stage 1 import/traceability | `COMPLETE_REVERIFIED` | The Stage 3 check freshly passed all 18 manifest sizes/SHA-256 values, exact inventory, four current authoritative hashes, JSON parsing, and Draft 2020-12 meta-schema validation for all seven schemas. |
| Stage 2 implementation-decision freeze | `COMPLETE` | ADR-0001 through ADR-0021 are accepted. Q4 selected no license grant; later scientific/platform decisions remain open only at their recorded gates. |
| Stage 3 build/CI foundation | `COMPLETE_LOCAL` | ADR-0022, constrained offline inputs, CMake/Ninja presets, smoke targets, tests, lint, schema/document/dependency/CI checks, sanitizer presets, generated metadata, install/package rules, and pinned self-hosted CI are implemented. |
| Queue implementation | `NOT_STARTED` | Correctly deferred to Phase 5 after Phase 4 contracts. No queue source or third-party queue code exists. Atomic representation/refinement evidence remains a Phase 5 gate. |
| Measurement system | `NOT_STARTED_BLOCKED_LATER_DECISIONS` | No clock, schedule, queue, timed loop, raw codec, controller, or platform-control implementation exists. Their recorded scientific/platform decisions remain unresolved at later gates. |
| Pre-pilot validation | `NOT_STARTED` | Requires Phases 4–15 and fresh eligible-platform/custody evidence. |
| Pilot | `PROHIBITED` | Phase 16 and explicit pilot authorization are absent; this one-NUMA-node development host is ineligible for near/far evidence. |
| Confirmatory execution | `PROHIBITED` | Pilot outputs and all later protocol freeze records, budgets, authorities, and sealing proof are absent. |

## Stage 3 products

- C++20 `cpu_prefetch_foundation` and `cpu_prefetch_smoke` build-identity targets;
- GoogleTest identity test and fixed-seed RapidCheck framework smoke test;
- GCC 16.1.x/libstdc++ and Clang 22.1.x/libc++ development presets;
- GCC release/package preset and four ASan/UBSan/TSan presets;
- clang-format 22.1.x and clang-tidy 22.1.x checks;
- offline protocol/hash/schema, documentation, dependency/license, CI, and
  release-flag checks;
- Git/protocol/compiler/stdlib/version metadata and a no-license stand-foundation
  package;
- self-hosted GitHub Actions jobs using a full-commit-pinned checkout action.

No product implements or simulates benchmark behavior and no placeholder result
is emitted.

## Fresh local verification

| Check | Result |
|---|---|
| Clean GCC 16.1.1/libstdc++ configure, build, 3 CTest tests | `PASS` |
| Clang 22.1.6/libc++ 22.1.6 configure, build, 3 CTest tests | `PASS` |
| GCC and Clang ASan+UBSan smoke matrices | `PASS`; zero findings |
| GCC and Clang TSan smoke matrices | `PASS`; zero findings |
| clang-format and clang-tidy | `PASS` |
| Protocol/import hashes and seven Draft 2020-12 schemas | `PASS` |
| Documentation links and 17-record dependency/license inventory | `PASS` |
| Release unsafe/native flag rejection | `PASS` |
| Release tests and CPack TGZ generation | `PASS` |
| Generated metadata and package contents inspection | `PASS` |

LeakSanitizer is explicitly disabled in the ASan presets because it cannot run
under the managed ptrace boundary. This does not disable AddressSanitizer or
UndefinedBehaviorSanitizer. The external self-hosted CI workflow was inspected
but cannot be executed from this local workspace; runner provisioning and an
actual hosted run remain external platform evidence. Coverage remains
unconfigured because no coverage gate was accepted.

## License and dependency state

ADR-0021 records no repository license grant. There is no `LICENSE` file. The
package carries `docs/NO_LICENSE_GRANT.md`; third-party licenses remain listed
separately in `config/dependencies.json`. GoogleTest and RapidCheck are test-only
and no third-party queue source was downloaded or vendored.

## Immediate gate

The exact next safe activity is **Stage 4 / Phase 4: implement the imported
logical contracts and structural/semantic validators**. Do not begin queue or
measurement behavior, pilot activity, or confirmatory execution.
