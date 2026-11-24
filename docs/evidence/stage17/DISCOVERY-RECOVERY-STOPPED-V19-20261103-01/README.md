# R2 discovery stopped — 2026-11-03

The [approved recovery family](../DISCOVERY-RECOVERY-V19-20261103-01/README.md)
started at 10:33:27 UTC and stopped with exit 1 at **10:49:00 UTC**.
It retained 75 output files totaling **52,465,834,715 bytes**, including ten
capture-control documents through ordinal 9. No completion record exists.
The finite one-attempt authority is consumed; no retry is authorized.

The original failure record reports `WORKER_NONZERO`, retained partial
evidence, a reaped worker leader and absent process group. MSR restoration
readbacks match all three CPU prestates, with no quarantine. The supervisor
also verified removal of the CPU partition and restoration of its root
prestate. The subsequent source audit confirmed the recorded supervisor and
controller processes were gone before hashing the output inventory.

`r2-output-inventory.json` contains the original stand-side sizes/hashes and
small public metadata encodings. `r2-output-inventory-audit.json` binds the
complete post-quiescence inventory and restoration result. `originals/`
preserves verified original failure, hardware, signed-authority and operator
bytes. The large raw/control data remain on the stand and are being copied
to the existing PC using four bounded, uncompressed SCP transfers, followed
by independent readback/hash verification and no-overwrite publication.

- Stand: `/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-19/discovery-output-r2-1`
- PC destination: `/home/omaltsev/research/cpu_prefetch_research_code/build/stage17-discovery-v19-copy1/discovery-output-r2-1`

At this checkpoint the second copy is **in progress**. No independent raw or
capture-control analysis has begun. The failure cause and individual capture
validity remain unassessed; duration selection is unresolved and this partial
family contributes zero formal runs. Once complete custody is verified,
diagnose the failed capture using the existing independent routines. Do not
fabricate a full-study retention report or select a duration from this prefix.

The monitoring SSH connection dropped during collection. A PC route readback
showed the stand IP using the VPN tunnel. The previously requested server-only
bypass was restored with a temporary active-device rule; direct SSH then
confirmed the same stand boot and continued original attempt. No experiment
was restarted. The exact scoped command and rollback are retained in
`r2-connectivity-recovery.json`.
