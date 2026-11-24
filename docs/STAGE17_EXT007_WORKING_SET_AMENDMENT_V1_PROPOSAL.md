# EXT007 working-set reconciliation amendment v1 — proposed

Status: **PROPOSED; NOT ACCEPTED; NO EXECUTION AUTHORITY**.
Amendment ID: `AMEND-2.0.0-pre.3-EXT007-WORKING-SET-v1`.
Base scientific source: immutable `protocol/2.0.0-pre.3/`.

[Prepared plan, resource checks and helper source](evidence/stage17/DISCOVERY-RECOVERY-PROPOSAL-V19-20261103-01/README.md)
are retained for review. They grant no execution authority.

This versioned amendment proposal resolves the conflict between that source's
section 4.1 and legacy D-162. No immutable snapshot, historical decision,
attempt or evidence is edited. Approval must be recorded separately before
this proposal governs another experiment. It changes no schema version,
estimand, contrast, timestamp boundary or raw-data format.

## Conflict and proposed disposition

The immutable specification requires power-of-two logical capacities common
to both queue packages. It defines the footprint as the common event arena
plus the complete queue storage, including sentinel, recycler, control lines
and padding. Select the largest qualifying capacity for L2/LLC residency and
the smallest qualifying capacity for beyond-LLC. D-162 instead permits
non-power-of-two capacities and uses per-item queue bytes, omitting the event
arena and other required storage. That legacy interpretation must not govern
new EXT007 or downstream plans.

The proposed disposition is to enforce the original full-footprint rules.
Retain D-162 and all affected historical artifacts as history; do not migrate
or relabel their observations. The first v19 diagnostic attempt remains a
stopped, invalid study and contributes no formal run or duration selection.

For this stand, use the observed 256 KiB private L2 and 25 MiB producer-home LLC
as the nominal capacity inputs to the original conservative thresholds.
Record sharing explicitly: the near workers and controller share the home
LLC; far uses the producer-home LLC only. Never add the remote LLC. The stand
is dedicated to these experiments; SMT siblings remain reserved and unused.
The read-only cache-control observation found no resctrl mount or CAT feature
advertised. Nominal capacity is not a measurement of instantaneous cache
occupancy, a cache-way reservation or guaranteed effective residency.

Using those explicit inputs, the existing compiled storage APIs imply:

| Class | Proposed C | Full ring bytes | Full linked bytes | Adjacent boundary |
|---|---:|---:|---:|---|
| L2 |512|36,992|69,952|C1024 linked139,584 exceeds131,072|
| LLC |65,536|4,718,720|8,913,216|C131072 linked17,826,112 exceeds13,107,200|
| Beyond LLC |1,048,576|75,497,600|142,606,656|C524288 ring37,748,864 is below52,428,800|

These source/compiled-ABI results must be confirmed with the prepared bounded
storage-construction check before adopting the new table. That check calls
existing constructors and footprint APIs, performs no enqueue/dequeue or
timing experiment, runs as UID 1000 with capabilities removed, and is limited
to 1 GiB address space, 60 CPU seconds and 120 wall seconds. Its source and
executable are prepared locally. Stand execution was rejected by automatic
approval review and remains pending explicit owner permission.

## One proposed recovery study

After approval and a matching footprint check, prospectively freeze a new
36-capture D178 family with the table above, new `D178W26B03xx`/
`D178M26B03xx` identities and separate R2 namespaces. Preserve all old IDs.
Keep five-second warmup, the 100 ms/1 s/5 s measurement grid, all 12 contexts,
100,000-per-sequence criterion, count-only selection and stop rules unchanged.
Increase the predeclared warmup attempt capacity to 30,000,000; measurement
capacities remain 1,000,000/4,000,000/5,000,000. No success or rate guarantee
follows from these buffer limits.

The prepared proposal uses the same ac64633 worker and 86 monitoring sources.
Its modeled native peak is 10,239,557,632 bytes and active allocation model is
57,622,774,016 bytes. Keep the existing finite 224 GiB AS and 12 GiB memlock
launcher limits. Fresh memory and disk checks must pass before starting.

Reserve 388,544,851,990 bytes per custody filesystem: 374,321,963,800 bytes of
study output, 3,485,469,950 bytes of validation spool and 10 GiB reserve. The
existing PC remains the second uncompressed copy. Retain the stopped first
attempt; no deletion or compression makes room for the new plan.

Reapply only the previously qualified CPU isolation configuration and verify
unchanged boot, runtime, topology and control readbacks. Preserve the accepted
clock evidence under its original identity; this proposal authorizes no new
clock capture. Obtain a fresh exact signed diagnostic action authorization.
Run the new family once, stop on the first mandatory failure, retain partial
data and restore or quarantine. No automatic retry, extension, formal Q16a,
pilot or Stage 18 execution is authorized by this proposal.

The prepared unapproved plan hash is
`d0de060cfcb6e80dbfec6193faad2b2d714bfd218b5223ab020002c90ebfd22f`.
Final operational bindings must include this amendment and the actual
footprint-check result before signing. A mismatch requires review, not a
silent substitution.

Approval is needed because AGENTS.md requires a versioned amendment for a
scientific contradiction, D178 requires a new prospective plan after a stopped
study, and automatic approval review rejected the new stand footprint helper.
