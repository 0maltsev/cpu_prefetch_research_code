# Stage 16 stand-preflight evidence

State: **`INVENTORY_ONLY_NOT_QUALIFIED`**

- Snapshot ID: `STAND-PREFLIGHT-XEON-CPU-FETCH-20260822-01`
- Captured at: `2026-08-22T10:33:20Z`
- Candidate host label: `xeon-cpu-fetch`
- Protocol: `2.0.0-pre.2`
- Source revision in the transferred bundle:
  `b68979d6b38dffe62dcfafc8b8227a85dc713207` with its exact dirty source
  archive retained by the bundle
- Bundle SHA-256:
  `c7b1a84f1fcaa7cde541c107384fe7c89521ba9da8e4b97b792b14662d9fa929`
- Inventory SHA-256:
  `f3bb301c77918c0287c8a287e3915f5d68929684eece660464c69f62770ac94b`

The outer bundle checksum, 72-file internal inventory, smoke executable, and
preflight self-test passed on the candidate stand. The internal verifier, both
executables, and the inventory collector ran as `nobody:nogroup` (UID/GID
65534). Root access was used only to transfer and extract the bundle and to
capture/seal the nonprivileged process output. No platform control,
calibration, pilot, or confirmatory command was run.

The inventory observes two packages, two NUMA nodes, 52 physical cores, and 104
logical CPUs on an Intel Xeon Gold 6230R system. These counts do not select or
qualify a `NEAR` or `FAR` worker pair.

## Preserved sidecar-publication failure

The collector completed once and produced the immutable JSON. The first
sidecar command then ran from the wrong working directory, leaving the empty
`STAND-PREFLIGHT-XEON-CPU-FETCH-20260822-01.json.sha256`. It was not deleted or
overwritten, and the collector was not rerun. `COLLECTION_FAILURE-01.txt`
records the failure. The separately named
`STAND-PREFLIGHT-XEON-CPU-FETCH-20260822-01.json.sha256.recovered-01` is the
verified checksum sidecar; it passed on the stand and after transfer back to
this repository.

All four returned evidence files are read-only. The seven blockers embedded in
the inventory remain authoritative for this preflight snapshot.
