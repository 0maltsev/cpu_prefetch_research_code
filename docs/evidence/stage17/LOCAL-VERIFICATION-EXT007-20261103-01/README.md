# EXT007 owner mapping and controller observation verification

ADR-0201: [live-control-composition-checks.json](live-control-composition-checks.json)
records the mapped runtime, final-worker-lifetime regression/fix, native thread
and hardware-prefetch monitors, timed control groups and prospective discovery
contract. Both full development suites pass **563/563**; **124 calibration** and
**71 platform** cases pass all four sanitizer configurations. The subsequently
registered Python contract passes 14 cases. Strict analysis passes the affected
eight translation units after explicit optional guards in the new control test;
its intentionally invalid enum input has a narrowly documented analyzer
annotation. All nine control tests were rebuilt and rerun in all six
configurations after those test-only corrections. Formatting passes. These
checks do not cover the still-developing native publication/dispatcher or
qualify a live experimental run.

ADR-0196, local engineering only. Execution authority: **NONE**. No empirical
performance result, stand control/MSR operation, release qualification,
diagnostic capture or formal calibration is claimed.

[owner-mapping-observer-checks.json](owner-mapping-observer-checks.json) binds
the changed source, accepted isolated runtime, commands, logs and report hashes.
Both full development suites pass **487/487**, exit 0. All **37 platform** and
**83 calibration** cases pass GCC and Clang/libc++ ASan/UBSan and TSan.
Three existing storage allocation-hook cases pass both development suites and
supported sanitizer configurations. The existing Clang TSan allocator-hook
exclusion remains; its functional cases pass without invented counters.
Five affected translation units pass strict analysis. Global format, queue
provenance and all six existing dual-disassembler codegen gates pass.

Mapping tests cover every preparation and cleanup failure, wrong owner facts,
page geometry, one-shot preparation/protection/release and separate actual
residency validation. Local native Linux tests exercise page-size query,
mapping/no-huge/read-only/unmap and a worker's actual singleton affinity/CPU/
thread/fault readbacks. Native mbind request tests check the kernel bitmap
import convention, including node zero/top mask bit and no migration flags.
Successful lock/bind and failure matrices use injected operations; these are
not live stand placement or lock qualification.

Controller tests cover all six rejection and exception boundaries, early stop
and failures reported after actual worker deadlines. A warmup observation
failure cannot reset or release measurement. Measurement observation failure
cannot become success despite complete raw integrity. Real arena/ring/stream
tests retain exact ordinals/checksum and bounded drain independently of control
validity. Software-only sessions explicitly report `not_configured` monitoring;
unreached hooks remain `not_started`.

Initial compile/static checks rejected a copied test observation, incomplete
aggregate initialization, a volatile cast through void, unchecked test optional
accesses and ambiguous observer integer parameters. These were corrected before
the final checks. Native request inspection separately corrected syscall
`maxnode` handling before deployment. No failed check was bypassed.

Full live mapped object/stack composition, retained actual residency/control
snapshots and frozen monitoring/resource budgets, durable publication,
watchdog/admission and clean qualified release remain required before the
approved 36-capture study. Existing codegen checks do not qualify the new exact
combined clock-boundary sequence. No stopped stand attempt was retried.

ADR-0197 adds retained residency observations to those controller hooks.
[retained-residency-observer-checks.json](retained-residency-observer-checks.json)
binds the exact subsequent source, commands, logs and reports. Both full
compiler suites pass **499/499**, exit 0; all **94 calibration** and **37 platform**
cases pass all four sanitizer configurations. Four storage allocation-hook
cases pass both development suites and supported sanitizers, including all six
residency hooks without allocation after preparation. The existing Clang TSan
hook exclusion is unchanged. Two affected translation units pass strict
analysis; global format, provenance and six existing codegen gates pass.

Tests retain independent raw page status, query return/errno, bracketed clock
and completion observations. They reject bad/aliased coverage and reused rows,
wrong nodes, partial writes, failed/regressing clocks, late queries, finite
wait exhaustion and finished workers. A real arena/ring/stream session refuses
initial release on rejected page readback. These page results are injected;
they are not actual stand residency. Partial during queries remain explicit
and do not prove anything about unqueried pages. Full live region coverage,
monitoring/resource admission and the complete owner/stack/control provider
still require integration. No live query, capture or new authority was issued.

The first static pass rejected unchecked member-optionals and implicit
multilevel pointer conversions. Local retained values and explicit casts repair
those diagnostics without suppressions; the final strict pass is clean.

ADR-0198 integrates explicitly mapped worker stacks into the persistent
discovery session. [mapped-worker-stack-checks.json](mapped-worker-stack-checks.json)
binds the source, accepted runtime, commands, logs and existing codegen reports.
Both full development suites pass **506/506**, exit 0. All **41 platform** and
**97 calibration** cases pass GCC and Clang/libc++ ASan/UBSan and TSan. Four
affected translation units pass strict analysis, and global formatting,
provenance and all six existing dual-disassembler codegen gates pass.

Native local tests verify pthread stack geometry and actual worker frames,
singleton affinity, an explicit inaccessible guard, live-byte preservation,
one-shot launch/cleanup, every owner/control failure, refusal to unmap a live
stack, partial launch cancellation, and both persistent phases. Only NUMA
binding is injected in these tests; no actual stand residency is established.
Sanitizer runs verify instrumented software behavior, not physical locking or
platform qualification. Pthread startup may touch metadata from the creator;
the implementation does not claim worker first touch for those bytes.

The initial ASan check rejected using an address-taken local as a physical
stack witness: ASan can relocate it. The corrected assertion checks the
actual frame address and independent pthread stack attributes. Initial static
checks also rejected ambiguous role arguments, unchecked test optionals, an
oversized enum and implicit multiplication widening; all were corrected without
suppressions. An initial label-selected sanitizer run included an unrelated
unbuilt runner executable. Final sanitizer checks explicitly execute the two
affected C++ suites. Review corrected the Threads dependency onto the platform
target, followed by final builds and verification.

Two authorized read-only SSH attempts to `root@94.126.205.83` timed out during
banner exchange with 15- and 20-second connection limits, both exit 255.
Neither reached the requested remote read. There was no stand command,
capture, control change, current operational replay or new resolution.
Complete mapped runtime objects/controller context, retained live controls,
prospective finite budgets, publication/watchdog and qualified diagnostic
admission remain required. Stage 17 is incomplete; Stage 18 has not started.

ADR-0199 integrates owner-prepared runtime objects with the real persistent
backend and mapped pthread stacks.
[mapped-runtime-object-checks.json](mapped-runtime-object-checks.json) binds
the exact source, commands and logs. Both full development suites pass
**513/513**, exit 0. All **104 calibration** cases pass all four sanitizer
configurations. Strict analysis of the affected translation unit and global
format checking pass. Existing queue/timing/storage/runner source is unchanged;
this is not generated-code qualification of the complete discovery worker.

Seven integration/boundary cases cover native mapping preparation, actual
producer/consumer thread identities, object and buffer containment, immutable
records/order, both persistent phases, actual raw streams and exact drained
joins. Failed owner mapping/protection prevents warmup; an already failed peer
prevents new mapping or affinity mutation. Missing peers exhaust a finite
budget. Invalid/overflowing geometry and mismatched owner regions reject;
mutating the caller's original plan cannot change the provider's frozen copy.
Partial construction is destroyed after worker join, before mapping release.
Only NUMA binding is injected, with synthetic clocks; successful local tests
are not stand residency, hardware qualification or experimental evidence.

The first strict analysis rejected ambiguous layout size/alignment arguments.
A typed request repairs the diagnostic without suppression. Final verification
includes the subsequent early-peer-cancellation regression. The restored SSH
refresh retains unchanged boot and operational journal-file identity, excluding
bundled fixture journals; it grants no semantic replay or execution authority.
Complete controller/runtime/TLS coverage, live control monitoring, finite
resource admission, publication/watchdog and exact qualified release remain
open before the approved discovery study. Stage 17 remains incomplete.

ADR-0200 moves shared session barriers, flags and retained results into
caller-owned one-shot storage. Reuse, including reuse after invalid admission,
cannot mutate prior results or launch workers. A native integration test runs
the full existing R0 session with provider/backend/clock/control objects in a
controller-owned mapping, a mapped controller stack and both persistent mapped
worker stacks. Both phases complete and independently retained primary streams
join exactly. Binding remains injected and capture clocks synthetic.

The cold native TLS inventory records actual per-thread payload ranges, FS base,
loader generations and return statuses in finite caller storage. It identifies
real executable TLS and libc `errno`, including on a mapped worker. Short
output retains its prefix and rejects; owner, generation and address changes
reject snapshot equivalence. This is not a complete libc/runtime inventory or
placement qualification; no loader walk belongs in a measured interval.

Both final full development suites pass **519/519**, exit 0. All **107
calibration** and **44 platform** cases pass all four sanitizer configurations.
The first strict analysis rejected four optional-access diagnostics; explicit
checks repair them without suppression. Initial controller test compilation
also required explicit default initialization of the retained result field.
These failures were corrected before the final checks.
[controller-storage-tls-checks.json](controller-storage-tls-checks.json) binds
the exact source, runtime, commands and logs. All four affected translation
units pass final strict analysis. Global format, immutable protocol/schema
integrity, schema fixtures, canonical fixtures and document checks pass.

The [fresh stand inventory](../STAND-AUDIT-CPU-PREFETCH-V5-20261103-01/README.md)
again finds unchanged boot and real operational journal identity. The owner
confirms dedicated use. No new semantic replay, phase authority, qualification
or capture follows. Full live footprint/control monitoring, publication and
watchdog, exact-boundary qualification and diagnostic admission remain open.
