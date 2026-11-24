# D207 local software verification

D207 approval is recorded separately; this evidence grants no execution authority.
The versioned implementation uses 1 s/2 s/5 s and 30-million-attempt buffers,
with unchanged measurement-loop behavior and explicit stand-primary custody.

The final affected native suite passes 52 checks in development GCC and each
of GCC/Clang ASan+UBSan and TSan (260 checks across five configurations).
Nine actual cold-layout CLI cases pass. Formatting and targeted clang-tidy pass.
The new signed-action and retained-data checks pass, including the synthetic
native fd pipeline and full-family insufficient-count outcome.

The first full GCC suite passed 641/642, exposing disappearing procfs candidates.
D209 reproduces ESRCH at three read sites and verifies the correction with eight
positive and eight negative checks. The next full suite passed 640/642; both
failures were stale supervisor hashes in freshly rendered preflight policies.
The two affected policy checks then passed after refreshing the same declared
operational bindings. Initial failures and deterministic red/green evidence
are retained. This is full-suite coverage with targeted successful reruns,
not a claim that one uninterrupted 642-check run passed.

Protocol/schema/canonical/schedule/provenance gates pass. No stand capture or
qualification is represented here. A clean release and exact stand admission
remain required before using the finite D207 authority.
