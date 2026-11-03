# D205 local clock-affinity verification

The CPU 0/8 regression reproduced the stale legacy affinity guard before
the production edit: consumer pinning failed. After the repair, the near,
V5 far and out-of-range CPU cases passed, three tests in each configuration:

- GCC/libstdc++ development, ASan/UBSan and TSan;
- Clang/libc++ development, ASan/UBSan and TSan.

These run at reduced software-test counts on the PC; they cannot qualify
the stand or meet the accepted clock sample-count gate. Both phases of the
V5 pair are exercised. The invalid CPU still fails closed. The production
tool self-test also passed without clock reads, thread pinning or hardware
access. Formatting and targeted clang-tidy passed; suppressed diagnostics
were in non-user code.

The exact policy-56 and preflight-policy-30 authoring checks passed without
changing their hashes. Only the clock collector implementation and its tests
changed. CLI registration/pair selection, public headers, accepted limits,
legacy Q15 probe behavior and measured clock-read loops remain unchanged.

Commands/results and exact hashes are retained in the listed logs and
`inventory.json`. A fresh clean release, explicit clock-tool rebuild,
package verification and stand qualification remain separate gates.

Clean release `ac64633662c4e61c8dd98e332dc70f77085e2e48` is now built and
deployed. All seven required code-generation gates pass, and the clock and
qualification-envelope executables were explicitly linked before packaging.
Both local and stand package verification pass for 1,826 files, and the
actual release-admission verifier accepts the extracted package.

Archive SHA-256:
`428b69b160429bca9c6ba0690e1136e4c2e131d6a1ba7d53377c69fc088ef5e7`.
Clock executable SHA-256:
`1e6bde398d7188e97c05b2293a596c64612b39f54a0c81aec430faa152f784ba`.
Both GNU and LLVM disassembly show three owner-binding calls, two actual
thread observations and no legacy Q15 binding call. Archived clock source
matches the repair; CLI pair-selection source remains byte-identical.
The packaged clock tool's self-test passes without measurement.

Qualification prefetch/combined checks also pass for both GCC and Clang
under both disassemblers at this new source revision. Fresh v5-19 is
initialized on the stand. These release/software checks grant no additional
clock capture authority; the preceding finite family remains consumed.
