# Q15-R fixed controller

`Q15-R-STATIC-CONTROLLER-v1` is the accepted repository-local implementation
of D-057 through D-060, with the D-062 trust adapter as a distinct admission
layer. It is a qualification controller, not a scientific
runner. It cannot read Stage A schedules, seeds, treatments, outcomes,
calibration inputs, or analysis artifacts.

The fixed graph and every limit are machine-bound by
`config/q15/q15-r-controller-profile-v1.json`. Admission requires an exact
authorization-v2 core hash, a detached OpenSSH SSHSIG artifact, and a distinct
independent verification artifact. The implementation validates the clean
source/release, stand and binding IDs, exact roles, custody policies, limits,
stop conditions, graph, and the absence of prohibited authority before it can
construct an execution ticket. The independently established trust anchor must
match the authorization-core hash, detached-signature ID/hash, verification
receipt ID/hash, signature scheme, and namespace; a receipt for different
bytes cannot admit the controller.

The execution core calls one fakeable operation site for each of the 15 fixed
steps, exactly once and in order. It stops on the first failed or malformed
step, never retries, retains the completed prefix, and never promotes partial
evidence. It checks artifact uniqueness, hashes, completeness, frame size,
wall/session/CPU bounds, artifact count, output size, and arithmetic overflow.
External watchdog and operating-system enforcement remain required independent
evidence; a successful controller return cannot substitute for them.

`Q15-R-TRUST-ANCHOR-ADAPTER-v1` is now implemented as a repository-local,
fakeable inherited-descriptor seam. It accepts exactly authorization-core FD 3
(1 MiB maximum), detached-signature FD 4 (128 KiB), and canonical independent-
receipt FD 5 (128 KiB). Each must be a complete read-only regular-file snapshot
from offset zero. The adapter binds canonical receipt bytes, the auditor-owned
allowed-signers identity, signer fingerprint, SSHSIG scheme/namespace, and the
existing controller admission fields. It exposes no OS path open, shell,
setuid, network, ambient-root, arbitrary selector, or real stand backend.

The current CLI remains intentionally a no-authority build. These commands are
safe and local:

```sh
cpu_prefetch_q15_controller --self-test
cpu_prefetch_q15_controller --describe-scope
```

The production-shaped entry exists as:

```text
cpu_prefetch_q15_controller --execute-q15-r EXACT_AUTHORIZATION EXACT_DETACHED_SIGNATURE
```

In the current build it refuses before opening either path. The clean v2 base
bundle retains that refusal. Q15-R-P2 authorizes and implements only the local
adapter seam; it does not enable this CLI or create an operational release.
Execution still requires an actual trust anchor and role/custody evidence, a
new clean release, an exact signed Q15-R record, and separate explicit approval.

Repository verification:

```sh
cmake --build --preset dev-gcc --target q15-controller-profile-check q15-trust-anchor-adapter-profile-check
ctest --preset dev-gcc -R 'Q15RController|q15.controller_|q15.fixed_controller'
cmake --build --preset release-gcc --target q15-controller-codegen-check
```

The generated-code check uses GNU objdump and accepted LLVM 22
`llvm-objdump`, audits the optimized production core, and rejects a retry
mutant. It is structural evidence only and makes no platform or performance
claim.

Clean commit `a75bcdd0367d79f8ee0496c55edda74311c9ef7d` and v2 archive
SHA-256 `48c460b008790e3b73aefbda94cacddaeb3c842622ca5bac5c763e50515ae035`
now bind this no-authority implementation as base release evidence. The
[`Q15-R operational-prerequisite bundle`](Q15_R_OPERATIONAL_PREREQUISITE_DECISION_BUNDLE.md)
records Q15-R-P2 acceptance and the blocked setup preparation. The existing
refusal remains the only CLI behavior for the production-shaped entry.
