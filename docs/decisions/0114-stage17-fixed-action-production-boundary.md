# ADR-0114: Stage 17 fixed-action production boundary

- Status: Accepted for repository implementation; operational authority remains unissued
- Decision ID: D-114
- Classification: implementation/governance boundary; no scientific semantic change
- Date: 2026-08-27
- Owner: repository owner and Stage 17 implementation owner
- Gate: Stage 17 stand handoff
- Supersedes: the production claims of ADR-0113 only; immutable evidence and protocol records remain preserved

## Context

The policy-v9 phase controller allowed an authorization to select its own
allowed-signers file, principal, namespace, and executable.  It accepted a
zero process exit without reading an action-specific typed result and invoked
an entry point that the runner did not implement.  The resulting boundary was
self-authorizing and fail-open.  Commit `ca8ea3844212fbd57eaac9945589d6e0f9a87545`
is therefore a `REJECTED_FAIL_OPEN_PREDECESSOR`, not production authority.

## Options considered

1. Patch controller v1 and retain policy v9.
2. Permit authorizations to carry a pinned trust root and executable.
3. Add a versioned successor whose trust and runtime identities come only
   from admitted external-input contexts, execute a closed compiled worker,
   and require a fully validated typed result.

Option 3 is selected.  Options 1 and 2 cannot establish an independent trust
root or preserve immutable predecessor reviewability.

## Decision

Policy v10 uses a closed verifier registry for all ten `S17-EXT` inputs.
Controller v1 refuses every execution before opening a worker, marker, or
output root.  Controller v2 obtains allowed-signers bytes, signer principal,
SSHSIG namespace, and role declarations solely from the EXT002 observation
context accepted by EXT003.  An authorization can only hash-reference those
two resolutions.  The controller rejects a self-rooted signature before the
one-shot marker.  EXT002 must also bind its stand ID, preflight-attempt
authorization digest, and observed stand-anchor digest to the already
admitted EXT001 target and pinned-host-key evidence; a free-standing trust
claim cannot become the controller trust root.

Controller v2 reads the admitted allowed-signers file and the supplied
signature once through nonsymlink regular-file descriptors, copies those exact
bytes into sealed parent-procfd snapshots, and gives only the snapshot
locators to `ssh-keygen -Y verify`.  The signature check therefore cannot
reconsume a replaced owner pathname after the trust context was admitted.

Q15-R and Q15-W use the exact runner path, size, SHA-256, role, action surface,
and runtime profile observed in EXT002 and accepted in EXT003.  EXT006 v2 later
verifies the actual candidate archive, sidecar, manifest member, and worker
member bytes, and requires the worker member to equal that admitted runtime.
Q16a, Q16b, Q16c, and the blinded pilot use only the resulting EXT006 release
context.  No checked-in commit predicts a future archive hash.

The production `cpu_prefetch_runner` exposes exactly six fd-only actions:
`Q15-R`, `Q15-W`, `Q16a`, `Q16b`, `Q16c`, and
`STAGE17-BLINDED-PILOT`.  There is no arbitrary command, argv, stdin, plugin,
output-name, or production fake-backend surface.  A distinct test-linked
binary supplies synthetic operations only to the hermetic integration suite.
The production operations are not placeholders: Q15-R reads the fixed
prefetch-control prestate and qualification facts; Q15-W applies the fixed
transaction, independently reads back, probes, restores, verifies restoration,
and quarantines on failure. Q16a captures separate producer/consumer ring
demand and issue tick series. Q16b runs the admitted continuously-ready
service-rate capture. Q16c and the blinded pilot consume only admitted frozen
open-loop deadlines through the static five-package runner. The Q16 paths
require a sealed controller admission ticket and emit bounded producer- and
consumer-private raw observations where the protocol requires them.

Before its durable marker, controller v2 opens nonsymlink regular worker and
request inputs, verifies owner/mode/size/hash, and copies them into sealed
memfd snapshots.  Together with the sealed trust/signature verification above,
this closes every pathname consumed by the controller's child processes. It
executes the verified worker snapshot through its
parent-procfd locator and passes the sealed request and already-open output
directory descriptors.  Source pathname replacement or in-place mutation
therefore cannot change consumed bytes.  The action definition and every
JSON Schema validator needed after the marker are loaded and checked before
the marker as part of the policy-bound runtime closure; terminal validation
does not reopen mutable repository paths.  The Stage 17A.7 subreaper and
PID-namespace-safe group-quiescence boundary remains mandatory.

A process exit status never establishes completion.  After leader and process
group quiescence, the controller reads a create-exclusive result, validates
its action-specific schema and full authorization/request/runtime/release/
predecessor lineage, rehashes every declared output, and applies the Q15-W
restoration/quarantine gate.  Only then may it write controller completion.
Q16a additionally retains the raw ring-demand series; Q16b reports its actual
attempted event count separately from the prospectively bounded attempt
capacity. Qualification records cannot be admitted from an outcome word
alone: each reported qualification digest must name and hash-bind the exact
source artifact bytes re-read by the closed manifest verifier.

Stage 17 exit is computed from admitted pilot attempt/result/completion and a
sealed manifest.  Phase 18 uses a separate signed authorization and access
journal; Stage 17 authority cannot advance its chronology.

The policy-v10 runtime-key set is exact and binds every Python admission,
controller, executor, exit, snapshot, and process-supervisor module plus the
actual C++ worker, runner core, header, and entrypoint bytes. A clean release
created after this ADR supplies the future archive/member identity. Its v2
bundle carries the exact policy bindings and transitive controller runtime at
their repository-relative paths and verifies every byte before use; the ADR
does not predict or self-authorize that release.

## Scientific effect

None.  This ADR implements authority, integrity, and execution boundaries for
already registered actions.  Calibration quantities, pilot factors,
schedules, seeds, platform values, and acceptance thresholds remain external
admitted inputs and are not invented here.

## Compatibility and risks

Policy-v9 authorizations, requests, markers, and results cannot be replayed as
v10 records.  Existing v1-v9 definitions remain readable.  A prior one-shot
marker blocks a v2 attempt.  The fixed production worker is Linux-specific and
requires procfs, memfd sealing, inherited descriptors, and the accepted
process-group supervisor.  Absence or drift fails before action or is retained
as typed failure after the marker.

## Supersession rule

Any successor must be prospective, preserve predecessor bytes and evidence,
bind a strictly narrower or equivalent independent trust root, retain the
closed six-action surface, and demonstrate exact-byte consumption plus typed
result validation with an unmocked compiled-worker integration test.  A
scientific change requires a protocol amendment, not an implementation ADR.
