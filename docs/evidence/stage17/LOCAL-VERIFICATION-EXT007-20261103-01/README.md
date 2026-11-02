# EXT007 owner mapping and controller observation verification

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
