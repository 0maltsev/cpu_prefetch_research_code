# D243: One additional isolation setup after administrative prelaunch timeout

- Status: PROPOSED — owner approval required before additional isolation setup
- Date: 2026-11-09
- Scope: the already registered and signed E25 Q16a continuation only
- Scientific design, source, capture population and measurement limits: unchanged

## Completed work and observed stop

D242 transition-only recovery succeeded; journal 000009 is committed. All 177
original captures, their successful independent validation, both successful
clock pairs, Q15-R/W and six qualified resolutions remain preserved. The exact
531-capture continuation passed source compatibility, both namespace audits,
full input admission, registration in the original shared program and signing.

D242's one permitted isolation reapplication passed at 09:51 UTC, including
boot, topology, MSR prestate, daemon-reload stability and remaining lifetime.
The subsequent launcher `--check` timed out in its owner subprocess after 180
seconds. It created no launch root, experimental attempt, capture or raw output.
The cleanup path restored the owned isolation and maintenance settings at
09:55:53 UTC; all restoration checks passed. The registered family is empty.

The launcher performs repeated plan/lineage validation around signed admission.
An independent read-only invocation of that signed admission passed in
103.327 seconds under the same UID1000, capability set, CPU3 and 2 GiB address
space limit. This does not claim that the complete live launch check has passed.
The observed failure is an insufficient administrative check allowance; no new
Q15/Q16 experimental failure occurred.

Exact retained bindings:

| Artifact | SHA256 |
| --- | --- |
| Plan / registered family | `91c83558b5c5d891cabdd4d875da1292120df5940397298063d55c901a8866c2` |
| Signed request | `aa780db91ceaaedca11fe3b4036c3506e9de80b5a25c6189c69c7a065ed8026a` |
| Phase authorization | `c84caa002b522e1228500474ac2f514e6db5e0f5214bfac332acc592d499d4bf` |
| Phase signature | `f2b00a01489e921212cf74f20254dce9c4a3174cb7765f5cb3e428acaaa94b06` |
| Failed prelaunch check record | `bc84e5a85de567cbe1678cec62a0e87fbdf999d9d99adea56388d5c1a1251f2d` |
| Verified restoration record | `6164321e36b417a95a606fc2d354d45e064b80654ff792a66eb6cdc0e7b0ce6a` |
| Successful signed-admission diagnostic | `7bb84558487122f0269372937e67d5d4fa8089c8dfeabf38579430c65ef82621` |

All paths and lengths are in the [prelaunch inventory](../evidence/stage17/Q16A-CONTINUATION-E25-20261109-01/prelaunch-inventory.json).

## Proposed approval

1. Use the separately retained launcher v2 with a fixed **600-second** owner
   admission allowance. Preserve the UID, capabilities, CPU, 2 GiB check memory
   ceiling, kill/reap cleanup and every existing admission gate. This allowance
   applies only to external administrative verification, before native execution.
2. Permit **one additional** use of the unchanged, cold-tested isolation core
   under fresh `isolation-preparation-v25-resume-2`. Keep the same qualified
   source `42f2ebb`, boot, CPU placement, control paths, 34-day finite lifecycle
   and all required readbacks. The new helper requires an explicit D243 owner
   acceptance record and verifies exact existing request/authorization/signature
   hashes, an empty registered family and an absent launch namespace.
3. Bind the new actual prestate/handoff in `launch-config-2.json`. Preserve the
   original clock/Q15 evidence and every prior failure/restoration byte. Run
   the complete live launcher `--check`, then launch the already authorized
   family once only if it passes. The launcher rechecks before native execution.
4. Reuse the existing registered family and signed request. Do not re-register,
   reset quota, rewrite the request, redo D242 transition, repeat prefix analysis,
   rerun clocks/Q15, repeat the 177 captures or change any measurement budget.
5. Stop and restore on any failed preparation/launch gate. The first new
   experimental Q15/Q16 failure still stops dependent work. This grants no
   further isolation retry, additional capture family or Stage18 authority.

The [reviewable operator packet and verification](../evidence/stage17/D243-LAUNCH-PREPARATION-20261109-01/verification.json)
contains exact source hashes and nine passing software tests. Launcher v2
changes only its import/entrypoint locations and the administrative 180→600
second allowance. It still invokes the original D242 CLI19 and qualified
CLI18/controller26/worker; the signed D242 administrative packet is unchanged.
No native source, archive profile, native setup/cleanup/watchdog, sample minimum,
duration, seed, quota or scientific interpretation changes.

D242 explicitly permitted isolation reapplication once. That setup was used
and restored, so this additional setup requires a new owner approval. Approval
of this proposal authorizes only the concrete sequence above; it does not
declare the live launch check or the experiment successful in advance.
