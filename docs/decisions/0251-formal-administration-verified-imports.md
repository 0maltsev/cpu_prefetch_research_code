# D251: Execute verified administrative source rather than cached imports

- Status: ACCEPTED engineering correction before new Q16b authority
- Date: 2026-11-15
- Scope: administrative source authentication only; no scientific/native change

Independent review reproduced D250's loader accepting cached project modules
whose `__file__` matched a verified source locator while their callbacks differed.
The actual preceding stand check used a fresh interpreter and remains retained
as read-only evidence. No Q16b authority, registration or measurement was created
through that path. Preserve the deployed v1 packet and all original receipts.

The successor `stage17_formal_admin_v2` and packet schema `/2` reject foreign
cached bootstrap/project modules before first activation. The original bootstrap
and three new administrative modules execute by compiling their already
hash-verified bytes. They are not reopened through import/bytecode-cache lookup.
The original qualified source/policy closure and D242 admission remain intact.

Repeated signature checks in one admitted interpreter reuse only its own
authenticated module objects. Reentry checks packet identity, module identity,
function/code identity and imported-module bindings. Another module claiming
the same locator, a replaced function or a replaced import cannot stand in for
that record. This permits the preserved activation behavior without repeating
the original bootstrap import or weakening the phase signature gate.

Outer registration and launch callers also compile the exact packet-bound
entrypoint bytes and reject unverified cached entrypoints. The launch caller
retains its own verified entrypoint for the required second check. Actual
execution starts the fixed v2 entrypoint in a fresh interpreter. These checks
address wrong/stale/cached project imports; they do not claim isolation from
arbitrary code already running with the same process privileges.

The new packet is stored separately at `q16b-admission-operators-2`; no qualified
bundle or legacy deployed packet is modified. CLI20/controller27, the exact
Q16b plan, estimator, duration, counts, seeds and native worker are unchanged.
New source authentication does not substitute for fresh journal, namespace,
profile, hardware, resource, signature, deadline or isolation admission.

Focused regression tests cover matching-path cached callbacks, compilation of
authenticated bytes despite different path contents, module replacement,
function/code replacement and import replacement. Original packet, signature
dispatch and legacy admission tests remain required. No experiment is rerun.
