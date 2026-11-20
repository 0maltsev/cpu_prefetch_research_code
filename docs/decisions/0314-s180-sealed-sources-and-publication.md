# D314: S180 sealed source preparation and complete capture publication

Accepted engineering implementation under the exact D310 S180 approval,
D311 prospective blueprint and D312/D313 capture/storage contracts. This adds
cold transport and publication helpers for that approved profile. It does not
activate a worker entry, admit a family, change a scientific count/window,
start an operational window or alter an immutable protocol snapshot.

## Source preparation contract

`prepare_s180_capture_from_sources` consumes the distinct typed native pilot
plan, two exact original source artifact identities, the parent-authenticated
source context and reserved descriptors. It accepts the frozen5-second warmup
and1-second measurement only. Caller-supplied inline vectors are rejected.
It requires the existing prepared persistent-data view, not another event arena.

The helper checks both selected artifacts' exact membership, SHA256 binding,
count/size and finite producer bounds. It rejects duplicate membership, shared
physical identities across phases, descriptors0–2 and aliases of reserved
request/context/output/archive descriptors, including a different descriptor
for the same inode. It then uses the unchanged original sealed-u64BE loader:
read-only immutable memfd seals, full byte hash, source interval/order, exact
extent and unchanged physical identity are mandatory. Reads use pread and do
not mutate or close borrowed descriptors. No generator is substituted and no
new source origin is invented.

Aggregate vector memory includes previously retained phase vectors plus the
loader's current vector and Result success copy: retained +16*N bytes. The
shared memory ceiling and monotonic deadline apply through both loads and
cold native layout/plan validation. This bound covers vectors, not unrelated
metadata, hash state, native maps or all36 common family sources; those remain
separate exact family-budget duties. `PreparedS180Capture` shares immutable
owned vectors across copies/moves and separately owns its MSR prestate. Its
plan() binds spans to that owner; the owner, borrowed family data and environment
paths outlive execution/publication. A moved-from owner rejects plan access.

The parent still must authenticate complete family source membership, accepted
generator/seed provenance, namespace reservation and schedule sharing against
the prospective full plan. This selected-artifact loader is not that authority
boundary and grants no readiness or execution permission.

## S180 output contract

`publish_s180_capture` receives the actual native pilot publication view and
prospective metadata after join, before private cleanup. It publishes exactly
eight bounded artifacts per capture: four independent original primary streams
(warmup/measurement × producer/consumer), original prepared node order, two
prepared source vectors and the complete control document. Source/order word
artifacts retain the existing explicit u64LE format; original source provenance
continues to identify the verified u64BE input bytes. Source coordinates remain
unchanged. Prepared, phase-released and all-arrivals-attempted are distinct.

The new `cpu-prefetch-stage17-s180-capture-control/1` identity and S180 roles
never relabel a Q16c artifact. The control document retains all supplied native
observations (including nine-region monitoring), independent stream status,
actual drain/reconciliation state, exact private layout, persistent mapping
preparation evidence and node-pattern summary. Prospective phase metadata is
retained alongside actual vectors; inline deadline arrays are omitted. Unknown
observations stay absent/null; in particular unavailable shared data has a null
node-pattern summary, not a fabricated zero-valued pattern.

Warmup bytes survive measurement failure; incomplete evidence is published as
incomplete. A sink failure stops publication and leaves the already-written
prefix intact. No archive verification, scientific validity or final family
cleanup is inferred from successful publication. The capture result records
private cleanup only; persistent data remains family-owned. A separate final
family cleanup/restoration record is required. FULL remains retained data,
independent of the zero-loss gate. This helper performs no joined-latency
analysis, rate change, horizon extension or retry.

Shared publication helpers are reused only at the cold serialization seam.
Legacy Q16a/Q16b/Q16c and pilot input/schema/authority semantics are unchanged;
existing Q16c schedule roles and result JSON stay intact. The production fixed
action entry has not changed. A separately scoped full-family session/parser,
artifact/archive integration and EXT008/009/010 admission remain required.

## Verification boundary

The new tests carry real original sealed files through loading, owner-mapped
read-only schedules, real queues/independent raw streams and publication. Their
clock and memory placement/locking observations are explicitly software-only;
no native monitor, MSR, experiment or qualification is invoked. Tests compare
exact original primary bytes and independently transform source BE bytes to
published LE bytes, check all output bindings/hashes, failure retention, memory
and descriptor guards, copied/moved ownership and unknown observations.

Relevant sanitizer/static/format and legacy regression results are retained in
the D314 evidence report. The software result does not establish launch readiness.
The operational24h window remains unused. Exact resources/whole-run ETA,
release codegen, qualified clean native bytes and calibration compatibility
remain mandatory before actual stand execution. EXT007 stays complete in its
signed descriptive scope; full Stage17 and Stage18 status are not promoted.
