# D316: S180 lossless archive handoff under the shared program quota

Accepted engineering implementation, 2026-11-21, under the owner's exact D310
S180 acceptance. This completes the archive contract needed by D315's typed
adapter. It changes no scientific setting, count, window, estimator or immutable
protocol and activates no authenticated CLI entry or stand execution.

## Original S180 evidence and separate transport

S180 uses its own checkpoint, custody, broker request/result and channel
request/acknowledgement schemas. Its original eight-artifact publication order
and six-field role/format/media bindings remain intact. The shared custody engine
receives the three-field expected byte bindings extracted from those references;
the original checkpoint is retained byte for byte, never rewritten as a Q16
checkpoint. Legacy entry points retain their original closed schemas and names.

The checkpoint records `scientific_validity=NOT_ASSESSED` and explicit false
execution/Stage18 authority, alongside the actual native result after private
cleanup. These complete the unused S180/1 contract before its first collection.
Successful native completion requires the full original publication and returned
mapping/stack cleanup and joins. A failed capture may retain only its successful
publication prefix; unlisted partial files remain on disk.

The C++ `S180ChannelSink` parks the native process at the cold checkpoint. Its
fixed channel binds parent credentials, original request/program hashes, exact
execution ordinal and checkpoint hash. Each archive interval is finite and
cannot reset the original absolute deadline. Receipt size is bounded. A failed
exchange latches the sink; final failure evidence can still be published. This
is transport, not independent proof of storage custody or execution authority.

The Python parent checks actual packet sender credentials against its held
PIDFD/start identity, verifies the exact original checkpoint and enforces frozen
session/plan/order. A normal acknowledgement is possible only for a complete
native capture and successful custody. A verified failed-evidence receipt permits
a negative acknowledgement that releases the parked native process to stop and
restore; it never permits the next capture. The first channel error stops the
channel, without retry. Broker/ledger/child-cleanup verification must precede ACK.

## Fixed broker and unchanged codec

The new fixed sealed broker entry binds the exact approved blueprint/acceptance,
all180 prospective capture identities, original plan hash, program storage scope,
EXT009 resolution binding, pinned native process and qualified source closure.
The qualified parent must authenticate actual admission: this low-level broker
does not turn arbitrary supplied hashes into an admitted experiment.

The existing D233 encoder, zstd settings, archive header policy and inverse
decoder remain unchanged. Each artifact uses bounded encoding, complete inverse
byte/hash verification, durable publication, another complete inverse check and
ledgered working-copy release. The broker owns sequential codec processes;
the parent retains its actual native child identity while supervising broker
cleanup. A complete eight-artifact checkpoint uses one broker and24 codec
children. The process/resource budget must count all25, not just the broker.

The six persistent family data contexts intentionally remain mapped. Before
spawning any codec, and again during custody transitions, all actually present
private capture mappings must show successful unmap. Unknown or unreleased
private mapping evidence rejects archival and preserves working files. Native
failure and source-byte discrepancy produce `ARCHIVED_FAILED_EVIDENCE`, with
expected/actual/discrepancy bindings preserved. Correctly retained failures never
become normal continuation or scientific validity.

## Explicit extension inside the original quota

The original `scope.json` is unchanged. A durable immutable S180 extension in
the existing program's metadata records exact D310 acceptance/blueprint, original
program/domain, the family and scoped EXT009 binding. The FAMILY ledger record
binds this file. All existing formal archives and this one S180 family share the
same6,000,000,000,000-byte quota,512GiB workspace,256GiB analysis scratch and16GiB
reserve; no second6TB allocation or independent raw backup is claimed.

Extension files, checkpoints, custody and ledger metadata count in physical
accounting. Reopening requires the identical extension/admission and family
identity. Another S180 family, legacy adoption, changed admission or an orphan
extension is rejected; there is no automatic recovery or retry. Existing formal
families and their stored scope/receipts remain readable under their contracts.

## Independent parent metadata checks

The S180 read-only registry verifies original checkpoint/custody bytes, extension,
original expected versus actual logical sources, retained discrepancy evidence,
all RELEASED transitions/current states, exact archive paths/header roles/phase
run identities, physical hashes, original retained checkpoint and the receipt's
immediately following authenticated ledger registration. It supports retained
failed prefixes but reports continuation false. It explicitly reports no new
inverse readback and no scientific validity; broker inverse checks and later
independent scientific validation remain separate evidence.

## Verification and remaining boundary

Real local process tests connect the compiled C++ sink to the credential-bearing
parent, sealed broker, actual encoder/decoder children, durable shared store and
read-only registry before acknowledgement. Tests cover success, failed native
capture, partial publication and changed source bytes; exact inverse readback of
all eight synthetic artifacts, metadata/physical corruption rejection, extension
scope and first-failure stop are also checked. These are synthetic software
verification, not stand performance or qualification.

The test-only native endpoint cannot capture data or alter hardware and is not
installed as a production worker. GCC and Clang/libc++ ASan/UBSan and TSan cover
the native controller/transport; actual codec-process tests run separately under
their existing address-space limits. Procfs supervisor checks run in a real local
user/PID namespace with a visible session, without host sudo or relaxed guards.

The authenticated serialized full-family worker entry, current runtime profile,
scoped EXT008/009/010, exact source/admission/namespace/recovery plan, release
codegen and clean native qualification/compatibility remain required. No stand
schedule preparation, operational window, qualification or pilot was started.
Completed calibration is unchanged. Stage17 exit and Stage18 remain pending.
