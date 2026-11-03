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
