# Approved isolated clock requalification, 2026-11-03

Outcome: **NEAR_PASS_FAR_SETUP_FAILURE_RESTORATION_VERIFIED**.
The owner approved the finite plan before any stand mutation. Exact approved
text, operator script, prospective command/limit records and invocation logs
are retained here. The qualified release remained source `817c652`, clock
binary SHA-256 `0ccefc493c48de378f4611570e6839dabbb0a7589d2c09caad3e63e734961f8d`.

The isolated partition reserved CPUs 0/1/2/8/16/17/18/24 and memory nodes
0/1. Effective and exclusive sets matched; ordinary root/slice CPU sets
excluded the reserved set. The supervisor used CPU 3, and the launcher
entered the partition before dropping to UID/GID 1000, binding its initial
thread to CPU 2 and verifying its 8 GiB address-space and preserved 8 MiB
memlock limits. Native clock threads bound the requested pair. No concurrent
operator preparation or admission ran on the stand during these captures.

The near capture ran 08:04:55Z–08:06:56Z and passed at the prescribed counts.
Its producer/consumer p99.999 deltas were **2.284/2.877 us**, below the
unchanged 10 us limit; both p99.9 values were 0.314 us, below 1 us.
Both CPUs had zero regressions and ties. Affinity, read status and
cross-core evaluation passed. This supports the near pair in the recorded
configuration; it does not establish the cause of the earlier tail failure.

The far invocation ran 08:06:56Z–08:06:57Z and exited 1 before completing
collection: `producer_pinned=1 consumer_pinned=0 complete=0`. It produced
no raw clock JSON. The actual stderr, empty stdout, process limits and
before/after control observations are retained. No far clock quantile or
complete distribution exists and none is inferred.

Source inspection and the exact binary's disassembly identify a stale
legacy 0/1/26 affinity guard in `LinuxQ15PlatformOperations`. The clock CLI
correctly selects V5 CPU 8, but that helper rejects it before the Linux
affinity call. CPU 8 was present in the effective isolated set throughout
the invocation. [ADR-0205](../../../decisions/0205-stage17-clock-affinity-selected-pair.md)
records the narrow software repair; it grants no further capture attempt.

The family stopped immediately. At 08:06:57Z the created partition was
empty and removed, added cpuset delegation was removed, and the exact root
prestate was read back: CPUs 0–31 effective, isolated set empty, subtree
controllers `cpu memory pids`. An independent read-only check subsequently
confirmed the restored state, unchanged boot, and no Q15 execution artifacts.
No Q15 hardware action, discovery capture or formal calibration followed.

All stand artifacts were copied uncompressed to the PC and verified against
stand-side sizes and SHA-256 hashes in `inventory.json`. The originals remain
on the stand. The approved maximum of two invocations is consumed; no retry
or threshold change is authorized by this record.
