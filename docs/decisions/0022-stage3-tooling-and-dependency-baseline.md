# ADR-0022: Stage 3 tooling and dependency baseline

- Status: `ACCEPTED`
- Date: 2026-08-17
- Classification: Build, CI, test, and dependency reproducibility
- Decision owners: Build owner; test owner; repository owner
- Protocol version: `2.0.0-pre.1`
- Supersedes: None
- Lifecycle gate: Stage 3

## Context and scientific constraints

ADR-0009 through ADR-0011 selected toolchain families, CMake/Ninja, offline
dependency inputs, and the unit/property-test stack. Stage 3 must constrain
actual versions and make local and CI entry points identical without adding a
scientific control loop.

## Options considered

1. Floating system packages or configure-time downloads.
2. Exact patch versions for every host tool forever.
3. A constrained minor-series baseline, with the exact observed version stored
   in generated build metadata and every dependency recorded by version/source/
   license.
4. Hosted CI that installs dependencies on every run or pre-provisioned
   network-disabled self-hosted runners.

## Decision

Use option 3 with pre-provisioned self-hosted CI:

- CMake 4.3.x, Ninja 1.13.x, Git 2.54.x, and Python 3.14.x;
- GCC 16.1.x with libstdc++ as primary;
- Clang/LLVM 22.1.x with libc++/libc++abi 22.1.x as secondary;
- clang-format and clang-tidy from LLVM 22.1.x;
- GoogleTest 1.17.0 and RapidCheck revision `ff6af6f` (`r1056.ff6af6f`)
  as test-only dependencies;
- Python jsonschema 4.26.x and the recorded transitive packages for Draft
  2020-12 schema checking;
- `actions/checkout` v4.2.2 pinned by full commit in CI.

All dependencies are supplied before configuration. CMake does not fetch or
vendor them. CI commands are the documented local commands. Coverage is not
enabled because no coverage policy was accepted; adding it is a later
engineering decision. No queue implementation or queue dependency is included.

## Evidence

The versions above were available and probed on the development host. Both
accepted C++ compiler/standard-library combinations compiled the smoke target;
GoogleTest, RapidCheck, and the Draft 2020-12 validator were locatable from
pre-provisioned inputs. `config/dependencies.json` records exact sources,
license identifiers, purpose, and constraints.

## Consequences and compatibility

Scientific effect: none; these targets contain no queue, schedule, timing, or
measurement behavior. Compatibility effect: unsupported compiler major/minor
series fail configuration, missing offline inputs fail closed, and every build
records its exact compiler, standard library, Git revision, dirty state, and
protocol version. A measured release will require a later exact release lock and
qualification; this Stage 3 range is a development/CI baseline.

## Verification and acceptance tests

Clean primary and secondary configure/build/test; format and static analysis;
protocol hash and Draft 2020-12 checks; dependency-record checks; ASan/UBSan and
TSan smoke runs where the host runtime supports them; release flag policy;
package generation; generated metadata inspection; and CI syntax review.

## Rollback or supersession

Changing a constrained series, dependency source/license, CI action, sanitizer
policy, or test framework requires a superseding ADR and fresh clean/offline
verification. Patch updates inside a constrained series require an inventory
update and the same Stage 3 checks. Measured binaries remain separately pinned.

## Protocol-amendment assessment

No protocol amendment is required. Any future tool change that changes
protocol-fixed behavior requires scientific-impact review before use.
