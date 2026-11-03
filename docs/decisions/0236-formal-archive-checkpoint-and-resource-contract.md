# ADR-0236: Formal archive checkpoints and prospective resource contracts

- Status: ACCEPTED engineering implementation of owner-accepted D233
- Date: 2026-11-03
- Scope: Future formal EXT007 storage integration only
- Execution authority: None

## Contract

D233 requires a durable original final-result receipt after each native capture
returns from cleanup, before encoding or starting another capture. The previous
family dispatcher retained these facts only in memory until family completion.
It also reserved cumulative canonical output as uncompressed retained disk.

Add `cpu-prefetch-stage17-formal-capture-checkpoint/1`, containing the exact
encoded native final result, original artifact bindings in publication order,
plan hash, action, ordinal and both phase run identities. It records native
completion separately from scientific validity, which remains `NOT_ASSESSED`.
Failed and empty prefixes also receive their original final facts. The original
control documents are unchanged. Durable publication failure prevents the
archive hook and further captures. The receipt alone is not live-quiescence or
archive proof; the qualified broker must check both independently.

The cold hook is synchronous and receives a prospective finite watchdog. It
must finish or fail before collection can advance. A mandatory native failure
still stops the family even if archival custody succeeds. A missing broker is
rejected before whole-plot hardware access. Existing sinks have no archive
capability by default. The initial checkpoint implementation therefore does
not activate archival execution.

Formal family plan versions `/2` explicitly select D233 and add a storage plan.
Version `/1` continues to require its original uncompressed policy. The shared
validators recompute the same native coverage, layouts, canonical row/output
bounds, phase durations and publication memory. No row cap or logical output
bound is reduced to satisfy physical admission.

The storage declaration fixes the approved shared program quota at 6 TB,
workspace at 512 GiB, analysis scratch at 256 GiB and reserve at 16 GiB. It binds
one program identity, exact immutable program-scope hash and implementation
profile, a separately bounded broker process and one codec process with a
2 GiB address-space ceiling, finite per-capture cold time, staging ceiling,
publication extent overhead, checkpoint limit and analysis workspace. These
are prospective bounds, not observed resource availability. The actual codec
must enforce staging/write limits and admission must verify fresh filesystem
allocation, inode, memory and shared-ledger facts separately.

Initial free-space admission requires Q+W+S+R. Later runtime admission subtracts
only physically retained program usage from the remaining quota; neither a
new family nor a failed capture resets Q. Workspace must contain the largest
complete canonical capture, declared archive staging and publication overhead.
Analysis scratch must contain the declared one-capture spool/workspace.
The family watchdog includes every declared archive checkpoint. Memory adds
the codec and declared broker ceilings conservatively to native/controller memory; allocator
retention and source vectors receive no compression credit.

The archive ceiling is enforced as a stop condition, not a beneficial-ratio
guarantee. Any quota, deadline, publication, verification or cleanup failure
retains evidence and stops incomplete without selecting a subset or retrying.

## Verification and remaining integration

Targeted checks cover exact approved constants, complete-family canonical
parity, cold time/memory, overflow, shared remaining quota, historical version
strictness, final-result preservation and publication failure. Native tests and
relevant sanitizers are required. The broker, archive-aware retention resolver,
qualified release, live admission and phase authority remain separate gates.
No test, declaration or checkpoint grants an experimental invocation.

## Bound synchronous channel

The native output sink accepts an archive channel only for an explicit `/2`
storage plan. Its sealed context binds the inherited descriptor, actual parent
PID and program-scope hash. Before hardware access, the sink verifies a local
`SOCK_SEQPACKET` endpoint and kernel parent credentials. Every bounded packet
binds the original request, program scope, capture ordinal and original final
receipt hash. The parent uses kernel per-message worker credentials plus a
pinned PID/start identity and verifies that capture/controller threads and
native child processes are gone while the worker waits for acknowledgement.

A successful acknowledgement requires `ARCHIVED_AND_RELEASED` and the exact
durable custody receipt. The native sink rereads its bounded original bytes and
checks size/hash before advancing, and charges receipt metadata against the
prospective capture/family budgets. Failed-evidence archival cannot acknowledge
success. The parent driver must independently verify the actual dedicated broker
process, archive/ledger result and child cleanup; transport checks alone provide
no custody or scientific credit. Fixed packet bounds and finite monotonic
deadlines apply without extension. An absent or mismatched channel fails closed.

The one shared program uses `working/<plan-sha256>/` family directories so
original publisher filenames remain unchanged without colliding between
Q16a/Q16b/Q16c families. Ledger and archive identity remain whole-program scoped.

The native cold deadline starts before durable checkpoint publication. A
`CLOCK_MONOTONIC` kernel timer sends SIGKILL at that same absolute deadline,
without creating another thread in the parked native process. The parent owns
reaping and hardware recovery. The request carries the deadline to the broker;
neither receipt verification nor acknowledgement restarts the interval. A
previous threaded watchdog would have contradicted the required single-thread
quiescence check and is not used for this cold interval.

For `/2` plans, family identity is SHA256 of the native JCS-I64-v1 plan bytes,
without a trailing newline. The historical signed request transport retains its
existing newline convention. These are different objects and their encodings
must not be conflated. New namespace, checkpoint, archive, calibration and
retention paths use the native plan identity; historical `/1` Python paths remain
unchanged. No row values, run membership or scientific estimator changes.

Each successful publication binding is captured at the sink boundary, even if
the enclosing publisher later returns failure or throws. A failed checkpoint
therefore preserves its actual successful prefix. Unlisted partial files remain
in the failed working directory and cannot authorize continuation. The cold job
builder hashes actual bounded sources. Source discrepancies receive a durable
expected/observed receipt; incomplete row bytes use lossless byte fallback and
the result remains failed evidence. Neither archival success nor a fallback
turns a native or integrity failure into a completed family.
