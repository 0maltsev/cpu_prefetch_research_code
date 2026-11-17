# D273: Count-sized Q16c traces and authenticated original-source receipts

- Status: ACCEPTED engineering implementation under approved D270; verification and launch admission pending
- Date: 2026-11-17
- Scope: cold source preparation, exact trace/resource sizing and explicit descriptive admission

Retain the approved180 settings, one capture per setting,1-second measurement,
5-second scheduled warmup, scale1 and every actual observation. Retain original
30-second maximum drains, monitoring/counter acceptance rules and independent
producer/consumer reconciliation. All completed Q16a/Q16b data remains fixed.

The Q16b plan reserves100million warmup and30million measurement primary rows
per owner. Q16c already knows its exact prospective original arrival counts.
Reserve producer and consumer primary capacity equal to each actual scheduled
count: every producer attempts once and each accepted arrival yields at most
one consumer row. EMPTY polls yield no primary row. This omits no observation,
performs no within-run resizing and changes no measurement duration or method.
The producer attempt watchdog is that exact count; prospectively declare a
finite1billion consumer-poll ceiling for each Q16c phase. These are new Q16c
engineering bounds, not changes to a completed Q16b run or its measured counts.
Maintain the prior12-byte phase run-ID width. Native layout and every retained
source/publication/metadata allocation must be recomputed before arm. No
compression credit applies to memory and no actual hardware value is inferred.

The accepted original D029 generator and independent v2 provenance verifier
remain unchanged. A software-only stand arithmetic timing measured131072
operations in1.619seconds with16workers and262144 in1.993seconds with32workers.
For the planning expectation902108340 deadlines, two arithmetic passes imply
about6.19/3.81hours respectively, before tail/coordination costs. This is a
software timing model, not an actual prospective count or empirical queue
performance evidence. It created zero schedules and zero experimental actions.
Use32 bounded workers only with observed CPU/memory/FD admission. Generation
and independent verification are each performed on every original source once;
all actual output bytes, algorithms, namespace/seed and rounding rules remain.

Subsequent authoring/execution/retention must not repeatedly regenerate those
hundreds of millions of original values. D270 explicitly permits reuse of
previously authenticated exact results. Introduce a purpose-specific source-job
record with complete360-source provenance, actual generator/validator source
closure, qualified-software inventory, original byte bindings, fixed D269 load
basis, unchanged boot, owned-worker completion/reaping and the original source
and24-hour deadlines. Its owner signature is verified using independently
admitted EXT003 trust, not a self-selected allowed-signers file. This is data
provenance only, never a phase authorization or performance-validity claim.

Every reuse rehashes all original binaries/envelopes/derivations, compares every
receipt and registered source coordinate/rate/phase and rejects any missing,
extra, rebound, changed or foreign input. The signed complete execution record
and exact source closure are mandatory; an arbitrary cached success flag is
insufficient. Keep all original failed source evidence, with no regeneration,
retry, top-up, rate selection or clock reset after a failure.

Bind the complete original prospective setup in the signed job, including every
master seed, artifact URI and derivation-record identity. A repeated seed ID
alone cannot prove the actual seed. Check all360 independent physical source
objects and current envelope/derivation identities on reuse. Publish reaping
facts only after joining the actual pool, including the error/deadline path.

The frozen919c486 bundle has4119 inventory entries, above the historical4096
bound. A private Q16c namespace raises only the inventory-entry maximum to8192;
it preserves complete inventory coverage and all duplicate/field/path checks.
Historical readers retain4096. Actual metadata file reads keep their existing
4096-file,32MiB individual,256MiB aggregate and120-second bounds. This is cold
engineering capacity only; no scientific acceptance or release identity changes.

The single D270 operational window remains unstarted by software development,
packaging, runtime-identity checks and synthetic arithmetic timing. Its first
actual stand prospective-source preparation or qualification anchors one
absolute24-hour monotonic deadline. A source preparation cap of6h15m is a
prospective resource limit, not a promise of completion. Before experimental
launch, use actual sources/layouts and measured preparation/archive/validation
costs to freeze the remaining finite envelope and give the updated ETA. Do not
launch if the complete envelope cannot fit. Keep D233 storage and stop/reap/
restore on the first new experimental, validity, custody, resource or time
failure. No automatic retry or window extension; Stage18 remains unauthorized.
