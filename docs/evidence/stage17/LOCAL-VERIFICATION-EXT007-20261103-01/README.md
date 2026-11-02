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
