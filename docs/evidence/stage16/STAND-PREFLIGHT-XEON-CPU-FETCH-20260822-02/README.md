# Clean-release stand preflight `STAND-PREFLIGHT-XEON-CPU-FETCH-20260822-02`

This is an append-only, read-only inventory captured on the candidate stand
`185.184.131.153` on 2026-08-22. It supersedes no earlier inventory. It binds
the observation to clean source revision
`1b0a7f54db7e1ff699331e9ae05a97f409f01ad4` and protocol
`2.0.0-pre.2`.

The transferred archive was
`cpu-prefetch-stand-bundle-2.0.0-1b0a7f5-clean-32ab349ee5e2.tar.gz`
with SHA-256
`e8eb9150d252d38f72b56884b0bcb5026480aee00b969c736fdc124783cb6eac`.
Before collection, the outer sidecar, all 72 internal bundle files, the smoke
binary, and the preflight self-test passed on the stand. The executable ran as
the unprivileged `nobody` account. The root SSH session performed only transfer,
directory creation, extraction, and output redirection.

The inventory document was captured at `2026-08-22T10:56:55Z`. Its SHA-256 is
`f8c6adbac92a9b163c45f71138946f3672eab7391fa27800fd909e028bc73087`;
the returned sidecar verifies that exact file.

Observed count-level facts are two packages, two NUMA nodes, 52 physical
cores, 104 online logical CPUs, a 64-byte cache line, and 4096-byte base pages.
The document deliberately remains
`INVENTORY_ONLY_NOT_QUALIFIED` and lists all seven pre-pilot blockers. It is not
clock, worker-pair, memory-residency, storage, hardware-state, calibration, or
pilot evidence.

No privileged control, MSR write, service change, calibration, pilot, or
confirmatory action occurred.
