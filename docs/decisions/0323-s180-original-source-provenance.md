# D323: independently verify the S180 original source bank

Accepted engineering implementation under approved D310. Add the read-only
source-generation/membership verifier required by scoped pilot admission. This
does not admit EXT008/009, change the frozen plan or generator, reserve a
namespace, authorize an experiment or start an operational window.

## Confirmed gap and exact expectations

The Q16c provenance verifier deliberately requires measurement envelopes with
`schedule_kind=CALIBRATION` and native identifiers without slash separators.
The S180 blueprint instead fixes slash-separated namespaces and needs `PILOT`
measurement envelopes. Reusing Q16c's checker, relabeling its calibration
sources or weakening its historical rules would be incorrect.

`stage17_s180_source_provenance_v1` derives exactly36 expectations from a concrete
collection-plan candidate and the original frozen blueprint: eighteen shared
placement/working-set/load groups, each with warmup and measurement. Reuse the
existing exact180-entry order/pairing/group checks. Every paired treatment must
bind the same original schedule identity, count, horizon, artifact and hash.
Ceiling-based sizing and unknown sources cannot pass. Original blueprint hash,
initial exact rates, master seed and every slash-separated namespace stay fixed.
Warmup remains WARMUP/five seconds; measurement is PILOT/one second. Source
origins and exact counts come from the prospective plan, not guessed values.

The caller supplies the seed identity from its separately authenticated
prospective registry. That identity is checked against both original metadata
records; this library does not establish its freshness or consumption history.
The blueprint supplies the actual master seed and namespace. Input metadata
cannot choose a different rate, generator, phase or parent namespace.

## Original bytes and accepted generation

Each source record has closed coordinates and three distinct original artifact
bindings: binary, envelope and derivation. Require all36 coordinates and108
distinct artifact identities, canonical absolute nonsymlink paths, safe regular
files, independent physical inodes and exact byte extents/hashes. Metadata uses
the original protocol schedule and D029 derivation schemas, strict integer
parsing and both existing zero-self hash checks. Integral floating-point control
values are rejected before canonicalization can normalize them.

Independently verify phase/coordinates/rate, half-open inclusion and immutable
order, seed/namespace ancestry, external original binary binding and accepted
derived key. Distinct source namespaces need distinct derivation record IDs.
Regenerate every expected deadline using the unchanged accepted Philox and
Decimal80 primitives, comparing each original big-endian u64 in place. Check
the original binary hash and domain-separated decoded-deadline hash. Test one
additional generated candidate after the declared count: a self-consistently
truncated source cannot hide a further in-window arrival. Inline placeholders,
Q16c calibration envelopes and foreign namespaces cannot substitute for pilot
sources.

This is streaming verification, with no full arrival vector, source rewrite,
publication or deletion. A caller-frozen source-byte ceiling and monotonic
deadline are mandatory. Check the deadline before I/O, at most256 draws apart
during regeneration and before final return. Bound plan/control metadata to
16MiB/1MiB and original envelope/derivation files to1MiB each. Retain original
path/inode/mode/owner/size/time stamps and recheck the complete bank at the end.
Returned bindings do not alias caller-owned inputs.

## Scope and integration

The resulting generation/membership proof explicitly leaves namespace freshness,
resource admission, execution and Stage18 authority false. An input-provided
`accepted_generation_verified` assertion never bypasses verification. The
qualified parent must authenticate this code and its dependencies, the exact
prospective seed/namespace registry and original files, and own the actual
bounded preparation/proof publication. Source path locators are not instructions
to execute commands. There is no production fixture/backend selector.

Full original generation replay is potentially expensive. It belongs in the
prospectively budgeted preparation/provenance operation within the single
24-hour operational envelope. It must not be silently run inside every D322
120-second metadata replay. The qualified producer receipt and its independent
scoped semantic replay remain to be implemented and bound; a self-asserted
receipt is insufficient. This decision does not change D322's lease or claim
that the missing integration is complete. No actual source preparation may
start before the all-inclusive estimate/budget is presented and passes.

Tests use real accepted generator output in a disjoint SOFTWARE bank with tiny
rates and a patched fixture blueprint fingerprint; the production function has
no such selector. The original unpatched S180 blueprint's exact rates,
namespaces,36-source coverage and hash rejection are separately checked without
generating prospective research schedules. Software evidence is not actual
source admission or a stand timing estimate. Native34247ce, protocol versions,
accepted generator/Q16c verifier and completed calibration remain unchanged.
