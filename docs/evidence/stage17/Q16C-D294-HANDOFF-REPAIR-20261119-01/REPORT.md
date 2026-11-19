# Qualification handoff repaired and verified;86 reports preserved

D294 fixes the software producer that stopped D292 after all86 original Q16c
reports passed. The qualification handoff now copies boot_id from the validated
signed execution-window record. The consumer's boot comparison and unchanged
7200s ceiling remain enforced. No default platform value, permission relaxation,
experimental input change, new window or retry is introduced.

The repaired producer SHA256 is
`5c91b3284940e69b03cb6dc8ed3906c1b52f526270e37f48c39c63f943bbeeee`.
The exact deployed qualification consumer source has SHA256
`58845d94dbe52c3d69dd1a5c984611aea2f8667b2cb621028717d19368122025`.
Its fixture/provenance is retained under
`tests/fixtures/stage17/d292-qualification-handoff/` and matches the original
qualification packet inventory72663c92892ae80d0e833cc1b9433c5e3d62435fc7169064b94e582d82e58b10.

Verification:

- The new integration test runs the actual deployed Packet constructor body
  against the supervisor's actual published handoff. Before the repair it
  reproduces KeyError('boot_id'). The foreign-boot test initially also exposed
  the missing field rather than reaching the intended boot-mismatch rejection.
- After the repair all10 supervisor sequence tests pass, including the real
  constructor, foreign-boot stop/restoration, original failed-handoff reproduction,
  ordering and first-failure cleanup. Only native action methods use software
  collaborators; the metadata reader/comparison/deadline logic is real.
- All43 affected operator, execution-window and policy tests pass with no skips.
  Changed Python compiles, policy63 rendering and `git diff --check` pass. No
  native source changed; native sanitizers are not claimed as new evidence.
- A UID1000 metadata-only stand probe evaluated the exact repaired producer
  expression with the actual historical signed-window boot. It used the real
  deployed constructor in an isolated temporary metadata directory: original
  error reproduced, repaired handoff accepted, foreign boot rejected and7200s
  budget unchanged. Its temporary constructor exposed no qualification methods.
  The failed service and compaction state were unchanged. No raw decode, guard
  acquisition, native action or new execution window occurred. The original
  stopped handoff/packet/bundle were not modified.

The86 completed reports, completion and accepted-prefix manifests remain as
verified in Q16C-D292-PREFIX-VALIDATED-STOP-20261119-01. No completed raw validation
was repeated. This repair has not been deployed into an experimental attempt.

D295 is the concrete continuation proposal, SHA256
`49bc337f79bd5593d9d934a4c6aa1638c260c5654822d5dd046a3e705d650e8b`:
120s report/lineage admission, one7200s qualification,1200s preparation,24860s94
collection/archive,2400s restoration and3600s94 validation/composition. Total
39380s=10h56m20s; estimate5–8h after launch. All86 reports are reused without
another raw analysis. Exact authority implementation/clean release/packets and
all prelaunch gates follow owner acceptance; no immediate launch is claimed.

D292's explicit first-failure/no-retry/no-another-window condition requires a
new owner decision before that additional attempt. D295 remains PROPOSED; no
approval is inferred from software repair instructions. EXT007/Stage17 remain
incomplete and no EXT008–010 or Stage18 authority is introduced.
