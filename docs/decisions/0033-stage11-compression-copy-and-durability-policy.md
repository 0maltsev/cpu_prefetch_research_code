# ADR-0033: Stage 11 compression, copy, and durability policy

- Status: `ACCEPTED`
- Date: 2026-08-21
- Classification: Artifact durability / compression / recovery / custody
- Decision owners: Repository owner; storage owner; data custodian; recovery owner
- Protocol version: `2.0.0-pre.1`
- Supersedes: None; selects the policy left open by D-020
- Lifecycle gate: Accepted before Stage 11 implementation; operational storage-domain evidence by Stage 16 and before pilot

## Context and scientific constraints

The protocol permits only frozen lossless post-measurement compression, gives
compression no hot-capacity credit, and requires immutable ordered sources,
partial-failure retention, stable hashes, and append-only correction. It leaves
the concrete compression and copy counts open. The repository has no approved
compression dependency and no named production storage domains, quotas, paths,
or custodians.

## Options considered

1. No compression and one durable instance.
2. No compression and two byte-identical durable instances in distinct
   verified domains.
3. Post-run zstd or another frozen lossless codec with two instances.
4. One raw and one compressed instance.

## Decision

Select option 2 and policy `RAW-OBS-NONE-TMP1-DUR2-v1` exactly as specified in
the accepted
[`STAGE11_STORAGE_DECISION_BUNDLE.md`](../STAGE11_STORAGE_DECISION_BUNDLE.md):

- `compression=NONE` for canonical producer, consumer, and joined artifacts;
- `m_tmp=1`, reserving at most one complete temporary producer/consumer raw
  work image in addition to durable instances, with sequential publication;
- `m_dur=2`, requiring exactly two byte-identical, independently reread and
  SHA-256-verified durable instances, including the primary, in two explicitly
  distinct `storage_domain_id` values;
- a staging object that becomes the verified primary counts within `m_dur`,
  not again as a simultaneous temporary copy;
- joined rows stream after a passed audit into a unique no-replace primary and
  are then replicated, without a complete temporary joined artifact;
- all writing, hashing, syncing, publication, replication, ledger updates, and
  recovery occur after measurement and are unreachable from worker code;
- unique create/no-overwrite staging, complete checked writes, data and
  directory sync, independent size/hash reread, and atomic no-replace
  publication, or a backend with proved equivalent semantics;
- an append-only copy ledger records policy, artifact ID/hash/size, distinct
  domain IDs/URIs, verification results/timestamps, and complete/incomplete
  state without extending the imported envelope;
- no automatic raw-source deletion; copy, capacity, crash, sync, readback, or
  recovery failure retains every verified instance and records incomplete
  evidence without retrying measurement or fabricating a copy;
- recovery may promote a unique staging candidate only after exact expected
  size and SHA verification and never mutates or reuses a published identity.

With D-010 row sizes, the accepted planning minimum is:

```text
B_total >= sum_r [3 * (N_sched,r*b_P(L_r) + N_acc,r*b_C(L_r))
                  + 2 * N_acc,r*b_J(L_r)]
```

The proof separately adds exact envelopes, integrity records, ledgers,
schedules, manifests, filesystem overhead, and an explicit operator reserve.
It receives no compression credit.

## Evidence

- Imported specification Section 8.3, data dictionary, freeze checklist, and
  append-only lifecycle rules.
- ADR-0004, ADR-0005, ADR-0015, ADR-0017, ADR-0020, ADR-0021, and ADR-0022.
- The accepted D-010 sizes and the bundle's corruption, capacity, publication,
  and recovery contract.
- The repository owner answered `Q9 - accept the bundle` on 2026-08-21. No
  storage ratio or performance outcome was used.

## Consequences and compatibility

Scientific effect: none to logical observations or measured operations because
all storage publication/copy work is post-measurement and compression is
disabled. The conservative footprint must be funded prospectively.

Compatibility effect: policy ID, `compression=NONE`, `m_tmp=1`, `m_dur=2`,
byte-identical copies, domain distinction, ledger fields, no-overwrite
publication, and recovery behavior are policy identity. One copy, compressed
v1 bytes, inferred domain identity, automatic deletion, or destructive repair
fails closed.

## Verification and acceptance tests

Stage 11 must pass immutable publication/no-overwrite, partial-write, staged
crash, disk exhaustion, partial-replica, sync/readback mismatch, recovery,
append-only correction, exact copy-ledger, checked-capacity, and worker-call-
graph tests. Fake/local backends are software correctness evidence only.

Stage 16 must bind two real independent durability domains, exact permissions
and custody, available bytes plus explicit reserve, filesystem/backend
capabilities, and a successful crash/recovery/readback exercise. Until then,
pilot eligibility remains blocked. Q9 does not invent those facts.

## Rollback or supersession

A new compression codec, copy count, durability boundary, ledger, deletion, or
recovery rule requires a new policy ID, superseding ADR, dependency/license
review where applicable, capacity update, and full prospective requalification.
Existing v1 raw sources and verified copies remain immutable.

## Protocol-amendment assessment

No amendment is required because this policy implements the protocol's
post-measurement, lossless, append-only storage boundary. Any proposal to
compress, copy, aggregate, overwrite, or perform I/O in the measured path, or
to discard required raw/partial evidence, conflicts with protocol-fixed
behavior and requires protocol review rather than an engineering override.
