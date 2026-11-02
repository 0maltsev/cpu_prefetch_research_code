# cpu-prefetch-v5 read-only refresh, 2026-11-02

The owner restored SSH. This audit records current observations and retained
artifact identities; it authorizes no experiment and resolves no external input.

[inventory.json](inventory.json) contains nine observed journal-file hashes,
six retained-artifact hashes, boot identity, selected CPU topology/cache facts,
NUMA links, memory/disk availability, base-page size, root-shell memlock limits,
and MSR **device metadata only**. The latest journal (000008) and all six
retained artifacts exactly match their hashes in the 2026-10-30 audit. Earlier
journal hashes are recorded here without claiming an independent prior
comparison. No MSR value was read or written. No capture ran.

The observed CPUs 0 and 1 share node 0's LLC; CPU 8 is on node 1 with a separate
LLC. Sysfs reports 256 KiB L2, 25 MiB LLC, and 64-byte cache lines. These are
hardware observations, not a frozen usable-cache budget, actual worker-affinity
proof, or page-residency verification. The root-shell resource limits do not
verify a future measurement owner's limits. No resource budget is frozen.

The stand reboot removed the prior `/tmp/operational_cli_v11_local_patch_v4.py`
wrapper. Using the retained CLI directly as UID/GID 1000 with the exact pilot
archive/sidecar returns exit 1: the hardware-prefetch schema binding differs
from that older CLI's policy expectation. Selecting the retained versioned v47
journal runtime also fails before replay: its `stage17_state_journal_v46`
dependency is missing. Neither failure was bypassed; no binding, source, or
record on the stand was changed. The old temporary wrapper's bytes have not
been recovered, so its behavior is not inferred from its previously recorded
hash or recreated by suppressing checks.

Consequently no fresh validated operational state is claimed. The last
validated checkpoint remains 2026-10-30's v5-12 `PREFLIGHT_ACCEPTED`, six
resolutions, two transitions, EXT007–010 missing, and `pilot_ready=false`.
Retain the old context and stopped attempts. A complete, source-qualified new
runtime/release and fresh dependent qualification remain required for the
changed discovery implementation; do not treat a reboot or new wrapper as
qualification continuity.

[audit.json](audit.json) records the checks and rejection outcomes.
[collect-read-only.py](collect-read-only.py) is the exact inventory program;
its hash is recorded in the audit. It ran via SSH stdin with `python3 -B -`.
It neither installs files on the stand nor changes its hardware configuration.

A supplemental [runtime check](runtime-versions-20261102T202604Z.json) at
20:26 UTC confirms working SSH and reports native glibc 2.43, Python 3.14.4
and OpenSSL 3.5.5. `g++`, `clang++` and CMake were absent from the queried
process's normal PATH. It only invoked version commands with Python bytecode
writes disabled; no configuration, MSR or capture action occurred. These
version facts do not qualify the new binary or its loaded dependency closure.

A further [resource snapshot](resources-20261102T211554Z.json) at 21:15:54 UTC
(November 3 locally) also used SSH stdin with `python3 -B -`. It read uname,
boot ID, `/proc/loadavg`, selected `/proc/meminfo` entries, evidence-filesystem
`statvfs`, process `comm` names, and the latest retained journal bytes. The
latest journal SHA-256 remains unchanged, with nine journal files present.
No process `comm` matched `prefetch` or `discovery` at that instant; this is not
a proof of global machine quiescence. Resource availability is not a frozen
budget. The JSON records actual remote values without asserting fresh replay,
qualification, MSR state or execution authority. No stand files, controls or
captures were changed.

[Connectivity restoration](connectivity-restored-20261102.json) records a
subsequent successful SSH read after adding a persistent server-only VPN bypass
to the development PC's NetworkManager Wi-Fi profile. The stand boot ID is
unchanged. The operational `journal/` directory still contains nine records;
`stage17-state-journal-000008.json` retains SHA-256
`46e6fa35f7393e136e8169e19e1c3ee7c49a8c2f82acc65322dd813b73e21c84`.
An initial recursive listing also included bundled fixture journals; it was
not used to identify operational head. The retained refresh explicitly scopes
the real journal directory. This is file identity, not semantic replay or
current qualification. No stand file, control or experiment was changed.
