# Stage 17 read-only stand refresh, 2026-11-03 local time

[read-only-inventory.json](read-only-inventory.json) retains the actual remote
timestamp `2026-11-02T23:21:56.300807+00:00`, hostname, boot, selected CPU/cache/
NUMA facts, available resources and existing artifact/journal identities.
The authorized SSH command ran the retained read-only collector and exited 0.
It performed no experiment or MSR read/write and changed no stand controls.
[refresh-evidence.json](refresh-evidence.json) binds the command, retained
collector bytes and inventory digest.

The owner confirms the stand is dedicated to these experiments. This refresh
finds the same boot `4c08cd05-b362-49dd-b37f-629e9c7ad79a` and nine files in the
actual operational journal directory. Head `000008` remains SHA-256
`46e6fa35f7393e136e8169e19e1c3ee7c49a8c2f82acc65322dd813b73e21c84`.
This file-identity comparison is not semantic replay or renewed qualification.

Observed `MemAvailable` is 256,724,420 kB; filesystem available bytes are
7,206,953,512,960. Root-shell soft/hard memory-lock limits are both 8,388,608
bytes. These are observations, not frozen budgets or the future measurement
owner's resource limits. Derive finite run, memory, lock, storage and watchdog
limits from the final runtime/plan and verify them under the actual launch
identity before admission. The boot/source/dependency and hardware-readback
requirements remain in force.
