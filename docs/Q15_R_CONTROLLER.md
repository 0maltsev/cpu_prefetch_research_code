# Q15-R fixed controller

`Q15-R-STATIC-CONTROLLER-v1` is the accepted repository-local implementation
of D-057 through D-060. It is a qualification controller, not a scientific
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

The current CLI is intentionally a no-authority build. These commands are
safe and local:

```sh
cpu_prefetch_q15_controller --self-test
cpu_prefetch_q15_controller --describe-scope
```

The production-shaped entry exists as:

```text
cpu_prefetch_q15_controller --execute-q15-r EXACT_AUTHORIZATION EXACT_DETACHED_SIGNATURE
```

In the current build it refuses before opening either path. Enabling its
operational adapter requires a later clean controller-bearing bundle, an
actual trust anchor and role/custody evidence, an exact signed Q15-R record,
and separate explicit approval. Q15-R-P1 grants none of those authorities.

Repository verification:

```sh
cmake --build --preset dev-gcc --target q15-controller-profile-check
ctest --preset dev-gcc -R 'Q15RController|q15.controller_|q15.fixed_controller'
cmake --build --preset release-gcc --target q15-controller-codegen-check
```

The generated-code check uses GNU objdump and accepted LLVM 22
`llvm-objdump`, audits the optimized production core, and rejects a retry
mutant. It is structural evidence only and makes no platform or performance
claim.
