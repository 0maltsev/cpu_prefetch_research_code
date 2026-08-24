# Q15-S3 dynamic probe and collector implementation bundle

Status: **`ACCEPTED_AND_IMPLEMENTED_REPOSITORY_LOCAL; NO_AUTHORITY`**

Protocol: `2.0.0-pre.2`

Accepted decisions: D-054 through D-056

This bundle resolves implementation mechanisms that are frozen before the
remaining D-052 dynamic probe and seven collectors can be implemented. It does
not authorize stand access, `perf_event_open`, affinity or NUMA changes, MSR
reads or writes, dynamic qualification, Q15-R, Q15-W, calibration, pilot, or
confirmatory execution.

Repository result: the exact profile is
`config/q15/q15-dynamic-implementation-profile-v1.json`. The phase-spanning
state machine, fixed Linux/fake backends, bounded local frame, seven distinct
collector components, no-allocation counted region, and traversal/caller
dual-disassembler gates are implemented. Only safe description/self-test
commands are exposed without authority. The separately authorized clean Q15-S3
commit and bundle grant no execution authority, and no dynamic operation has
been executed.

## Why another decision is required

D-052 requires an H0/H1 pair to use the same binary, CPU, buffer, layout,
order, and counter configuration. ADR-0051 separately requires Q15-R evidence
to be sealed before a prestate-bound Q15-W authorization can be created, and
requires distinct operator and auditor roles around every mutation.

The current authorization model places the H0 regular/pointer probes in Q15-R
and the H1 probes in Q15-W. Two ordinary one-shot process invocations would
allocate different anonymous buffers. Treating reproducible bytes as the
"same buffer" would silently weaken a scientific qualification constraint.
The implementation therefore needs an explicit phase-spanning ownership and
control mechanism.

## D-054 — Phase-spanning same-buffer probe session

- Classification: qualification orchestration and treatment-state verification
- Owner: protocol, platform, security, custody, and audit owners
- Deadline/gate: before implementing the dynamic probe command and before Q15-R

### Options considered

1. Run independent H0 and H1 processes and interpret identical bytes as the
   same buffer.
2. Persist the buffer in a file or shared-memory object and remap it later.
3. Keep one non-mutating probe-session process alive across Q15-R sealing and
   Q15-W authorization, retaining one private anonymous mapping.
4. Supersede D-052 so that only byte identity, not buffer identity, is
   required.

### Recommended option

Select option 3.

The fixed qualification executable gains a long-lived probe-session mode. One
session:

- is bound to one exact authorization binding, stand, selected CPU, NUMA node,
  verified LLC size, verified base-page size, H0 complete value, H1 complete
  value, binary hash, contract hash, and implementation-profile hash;
- creates one `MAP_PRIVATE|MAP_ANONYMOUS` mapping, binds it to the authorized
  node, disables transparent huge pages for that mapping, first-touches it on
  the selected CPU, and retains the mapping until restoration readback;
- uses the same mapping and deterministic bytes for the regular and pointer
  traversals and for both H0 and H1;
- emits the H0 regular/pointer evidence through a Q15-R client, then enters an
  explicit `H0_SEALED_WAITING_FOR_Q15_W` state without changing or remapping the
  buffer;
- accepts H1 continuation only from the exact Q15-W controller identity after
  the controller presents the authorization hash and the independent H1
  readback artifact ID/hash and complete value;
- emits H1 evidence through a separate Q15-W client, then accepts completion
  only after the exact independent restoration-readback artifact ID/hash and
  complete H0 value are presented; and
- fails closed on disconnect, wrong peer, wrong state/value/hash, expired
  authorization, buffer-integrity change, migration, residency change,
  multiplexing, page fault, or any illegal transition.

The process does not read or write an MSR, validate a detached signature,
grant authority, or decide that an operator/auditor role is authorized. The
external Q15 controller and OS policy retain those responsibilities. The
session checks only the exact execution binding and evidence handoff supplied
by an already authorized controller.

Communication uses a fixed versioned local protocol over an inherited or
Unix-domain endpoint. Peer credentials, session ID, state sequence, complete
message framing, artifact hashes, and disconnects are recorded. The eventual
Q15-R/Q15-W record must bind the exact endpoint, peer identities, argv, limits,
and output artifacts. There is no network listener and no wildcard endpoint.

No duration is selected here. The session requires an explicit nonzero
authorization expiry and external watchdog limit and has no built-in default.
If Q15-W cannot be issued before that bound, the H0 evidence and session
failure are retained, the mapping is destroyed, and a later attempt requires
new authorization; it is never silently resumed with a new buffer.

### Effects

Scientific effect: preserves literal same-buffer H0/H1 qualification and the
registered order without changing the binary counter criteria. It does not
turn qualification observations into experiment outcomes.

Compatibility effect: session protocol/version, state sequence, mapping
identity, process start identity, peer identities, H0/Q15-R handoff, Q15-W
authorization and readback hashes, buffer hashes, and restoration handoff
become qualification identity.

### Supersession rule

A different phase boundary, buffer-lifetime interpretation, or control
protocol requires a new ADR and full requalification. Changing "same buffer"
to "same bytes" changes an accepted scientific qualification constraint and
requires explicit protocol-owner review plus a superseding D-052 contract;
it cannot be an implementation fallback.

## D-055 — Fixed Linux acquisition and probe mechanisms

- Classification: platform implementation and raw-observation acquisition
- Owner: platform, timing, compiler, security, and audit owners
- Deadline/gate: before dynamic probe implementation and generated-code audit

### Options considered

1. Use `perf stat`, `numactl`, and shell parsing around the probe.
2. Use libpfm/libnuma or another new runtime dependency.
3. Use narrow direct Linux interfaces behind injected system-call seams.
4. Leave mechanisms selectable at runtime.

### Recommended option

Select option 3 with no new runtime dependency.

- Raw PMU: direct `perf_event_open` with `PERF_TYPE_RAW`, config `0xf824`,
  user-only, pinned, non-inherited, per-thread scope, and read format
  `TOTAL_TIME_ENABLED|TOTAL_TIME_RUNNING`. Reset/enable/disable/read occurs once
  per counted pass. Short reads, nonzero event-open group/CPU fields,
  multiplexing, unsupported event, permission failure, or counter lifecycle
  error fail closed. No retry or fallback event exists.
- CPU: `sched_setaffinity`, `sched_getaffinity`, and `sched_getcpu` through a
  fixed singleton-CPU interface. Entry/exit CPU and migration observations are
  raw evidence; requested affinity is never copied into verified state.
- Memory: overflow-checked
  `ROUND_UP(2*VERIFIED_LOCAL_LLC_BYTES,VERIFIED_BASE_PAGE_BYTES)`, then fixed
  private anonymous `mmap`, `mbind(MPOL_BIND)`, `madvise(MADV_NOHUGEPAGE)`, and
  target-CPU first touch. No guessed cache/page/node value and no fallback to
  another node, THP, or interleave policy is permitted.
- Residency: direct `move_pages` query over every page before priming, between
  priming and the counted traversal, and after the traversal. Page arrays are
  preallocated outside the counted pass. Unavailable status, wrong node,
  migration, unequal/zero counts, or query failure fails closed.
- Faults: `getrusage(RUSAGE_THREAD)` snapshots conservatively bracket counter
  enable/traversal/disable. Any positive minor- or major-fault delta fails the
  pass. The fault call itself is outside the counted traversal and the PMU is
  user-only.
- Timing: the accepted `CLOCK_MONOTONIC_RAW` reader records raw diagnostic
  boundaries. Nothing is subtracted from the PMU count and no timing threshold
  affects acceptance.
- Integrity: D-053 complete pre/post SHA-256 and exact pointer-cycle closure
  run outside the counted traversal. The regular traversal uses the same
  immutable deterministic buffer and performs exactly one volatile `uint64_t`
  load per ascending line.

Production backends expose no arbitrary PMU type/config, CPU set, NUMA policy,
page policy, event group, MSR, path, probe seed, or traversal selector. Tests
use injected fake system calls and cannot reach a real PMU, affinity, NUMA, or
MSR operation. Release code must pass the accepted GNU/LLVM dual-disassembler
gate and deliberate forbidden-work mutants.

### Effects

Scientific effect: implements D-052's exact observation model and failure
boundary without performance thresholds or correction.

Compatibility effect: system-call request fields, buffer formula/mapping,
counter lifecycle, page enumeration, fault boundary, timestamp boundary,
failure categories, and generated instructions become qualification identity.

### Supersession rule

Any event, scope, memory policy, fault boundary, traversal, timing correction,
or fallback change requires a new ADR and clean no-authority release. A change
to D-052 semantics also requires its formal supersession.

## D-056 — Collector packaging and append-only evidence boundary

- Classification: qualification tooling, evidence, and least-privilege packaging
- Owner: platform, timing, queue, compiler, security, custody, and audit owners
- Deadline/gate: before clean Q15 qualification-tool release and Q15-R

### Options considered

1. Seven unrelated helper executables and ad-hoc text output.
2. One general-purpose collector accepting arbitrary probes, paths, and event
   definitions.
3. Fixed subcommands/components in the separate Q15 qualification executable,
   each emitting one versioned canonical evidence kind.
4. Reuse the measurement runner as the qualification collector.

### Recommended option

Select option 3.

`cpu_prefetch_q15_tool` remains separate from the sealed measurement candidate.
It gains fixed, non-wildcard commands/components for exactly:

1. `Q15-CLOCK-COLLECTOR-v1`;
2. `Q15-ATOMIC-LAYOUT-COLLECTOR-v1`;
3. `Q15-ACTUAL-CPU-MIGRATION-COLLECTOR-v1`;
4. `Q15-ADDRESS-RESIDENCY-COLLECTOR-v1`;
5. `Q15-SOFTWARE-PREFETCH-COLLECTOR-v1`;
6. `Q15-MSR-PRESTATE-COLLECTOR-v1`; and
7. `Q15-MSR-READBACK-COLLECTOR-v1`.

Each collector keeps its own ID, evidence kind, version, raw inputs, eligibility
decision, failure state, source IDs/hashes, executable hash, authorization
hash, actor/peer identity, timestamps, and canonical output hash. Sharing one
release binary does not merge evidence kinds or acceptance rules. The atomic
and software-prefetch collectors inspect the actual linked queue/layout and
code-generation profiles; they cannot accept caller-supplied `passed=true`
claims. CPU and residency observations are captured by the same concrete
qualification operations they qualify. MSR readback remains a distinct
auditor invocation and never reuses the writer's returned value.

Dynamic components produce `Q15-CANONICAL-U32BE-LENGTH-PREFIXED-FRAME-v1`
records (one unsigned 32-bit big-endian byte length followed by exactly that
many JCS-I64-v1 bytes) to an
authorization-bound output descriptor or endpoint. Filesystem creation,
`O_EXCL`, synchronization, append-only custody, quotas, two-domain transfer,
and final sealing remain the external custodian's responsibility. No
collector writes into a sealed Q15-R artifact; Q15-W evidence is a new artifact
that references the sealed Q15-R hashes. Partial frames and failures are
retained and cannot be represented as complete eligible evidence.

The tool contains no scientific schedule, namespace, queue outcome, analysis,
calibration, pilot, or confirmatory command. Its no-authority bundle continues
to set every dynamic/MSR/pilot/measurement authority flag to false. Exact
executable hashes and argv become prospective Q15-R/Q15-W inputs only after a
clean build and clean-bundle verification.

### Effects

Scientific effect: none; it makes the seven already frozen qualification
contracts executable without combining their gates or accessing outcomes.

Compatibility effect: binary/profile hash, command grammar, evidence schema,
collector IDs, linked layout/codegen report hashes, frame protocol, and partial
failure representation become qualification identity.

### Supersession rule

Changing executable partitioning, accepting caller assertions in place of
observations, merging evidence kinds, changing canonicalization, or changing
partial-failure semantics requires a new ADR, clean bundle, and full
requalification. Scientific rule changes require protocol review.

## Repository-local verification after acceptance

Acceptance authorized only implementation, tests, sanitizers, and
generated-code auditing in this repository. The implementation gate was:

- positive and negative state-machine tests for every D-054 transition;
- disconnect, stale authorization, wrong peer/value/hash, expiry, and partial
  evidence fault injection;
- exact fake-backend assertions for every D-055 system-call field and order;
- PMU open/ioctl/read/close failure tests with no fallback or retry;
- affinity/migration, NUMA/residency, page-fault, overflow, and base-page
  negative tests;
- collector evidence-schema and cross-record tests for all seven IDs;
- proof that booleans supplied by a caller cannot manufacture clock, atomic,
  CPU, residency, software-prefetch, or MSR eligibility;
- GCC and Clang unit/integration suites, ASan/UBSan and applicable TSan;
- formatting/static analysis; and
- strict GNU Binutils plus accepted LLVM disassembly and mutants around both
  counted traversals and counter boundaries.

No test may open a real PMU, change affinity/NUMA policy, access an MSR, or use
the stand. A later separately authorized clean commit and no-authority bundle
would be required before Q15-R can be prepared.

The implemented slice passes 37/37 focused Q15 tests under both development
compiler/library presets. Final post-review ASan/UBSan runs pass 36/36 under
both compilers, GCC TSan passes 36/36, and Clang/libc++ TSan passes its 35/35
applicable tests. These shortened final sanitizer runs omit only the unchanged
long-running clock collector case; it had already passed every sanitizer
matrix before the final strong-type API cleanup. Clang TSan also omits the
global-allocation-override no-allocation executable because that override
conflicts at link time with Clang TSan's allocator interceptors; GCC TSan and
both ASan/UBSan presets pass that test.

Targeted static analysis of all ten changed Q15 translation units, tests, and
codegen probes passes with no user-code diagnostics. Formatting, both immutable
protocol snapshots, 14 imported plus 22 implementation schemas, canonical
fixtures, and 127 documents/256 local links pass. Both release compilers pass
the strict Q15 traversal and counter-boundary audits under GNU Binutils 2.46
and LLVM 22.1.6, including registered extra-work mutants. The dynamic profile
checker proves seven distinct collectors and rejects four semantic mutations;
the future bundle profile passes one synthetic positive and 33 negative cases
without sealing a bundle.

## Acceptance record

The protocol/platform/security/custody owner stated on 2026-08-24:

> Q15-S3 - accept D-054 through D-056: use one phase-spanning, non-mutating
> probe session to preserve the same private anonymous buffer across sealed
> Q15-R H0 evidence and later Q15-W H1/restoration evidence; use the fixed
> direct Linux PMU, affinity, NUMA, residency, fault, and diagnostic-clock
> mechanisms in D-055; and implement the seven distinct evidence collectors as
> fixed components of the separate Q15 qualification executable under D-056.
> Authorize repository-local implementation, fake-backend tests, sanitizers,
> and dual-disassembler auditing only. Do not authorize stand access, real PMU
> or affinity/NUMA execution, MSR access, dynamic qualification, Q15-R/Q15-W,
> calibration, pilot, measurement, or confirmatory work.

Rejecting D-054 leaves the dynamic implementation blocked. Selecting option 1
or 2 would not satisfy the accepted same-buffer contract. Selecting option 4
requires an explicit superseding scientific decision rather than an
engineering default.
