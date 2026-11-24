# D295 stopped at preparation; qualification passed, restoration verified

Checked19November2026 at19:19:36UTC (22:19 Moscow). The D295 service exited1
at19:07:23UTC (22:07:23 Moscow), about26minutes after launch. MainPID is0
and the service has no control group. There has been no restart.

Progress retained:

- All86 completed original reports passed metadata/hash/lineage admission,
  without repeated raw validation or measurement.
- Near and far clock checks passed. All7 prerequisite operator receipts have
  exit0 and leader_reaped=true. `qualification-family-complete-1.json` records
  full qualification success, including the Q15 sequence.
- Construction stopped before publishing constructed/prepared inputs. The
  output directory is empty and the sign/collect phase log does not exist.
  None of the94 pending Q16c captures started.
- Supervisor recovery and independent ExecStopPost recovery both verified
  restoration, with errors[]. CPUs0/1/8 each match the full zero MSR prestate;
  isolation/maintenance restoration is verified. The actual guarded control
  `/proc/sys/vm/compact_unevictable_allowed` reads1, matching its restored
  prestate. No recovery signalling was required by the independent path.

The exact error is `immutable original restoration differs`, raised by
`stage17_q16c_prefix_reuse_v1.inspect` during the unsigned action-input
validation. Its fixed incident contract requires842bytes and SHA256
`ad2eb45db7d7f8b11ed372a3a76816f551ac7ac0081dcdb6eeacc8d5646dd326`.
The preparation metadata instead supplies849bytes and SHA256
`85721467a378d2dd72cb8d82c6e4c6e03cf21129d804f8aeb104d8d46a87e904`.

The metadata producer `build/stage17-q16c-d295/prepare_d295_metadata.py`
line92 selects the original E29 `clock-qualification-v29-1/restoration.json`.
That is the earlier clock-qualification receipt. The required incident receipt
is E29 `q16c-continuation-recovery-1/restoration.json`. It remains present on the
stand and its size/hash match the fixed contract and the previously preserved
D285 `isolation-restoration.json` exactly. Both documents report successful
restoration, but their distinct historical identities are not interchangeable.
The immutable evidence check correctly rejected the wrong binding; this is a
metadata-production defect, not evidence of a failed clock or Q15 measurement.

The prior software checks exercised prefix reuse and the qualification
constructor, but did not establish the later complete unsigned construction
boundary against this actual incident metadata. The next repair should select
the original incident receipt, require its expected size/hash before launch,
and exercise that complete preparation boundary without native measurement.
Do not weaken the validator, rewrite a historical receipt, or relabel completed
qualification under a different source identity. No production source, packet
or stand configuration was changed during this status check.

All original86 reports and raw data, failed evidence, Q16a708 and Q16b120 remain
preserved. Only small public receipts/logs were transferred. The running ETA is
withdrawn. D295's first-failure stop has consumed this attempt; no retry, clock
reset or additional execution window is authorized by this report. EXT007 and
Stage17 remain incomplete; Stage18 remains prohibited.

`status.json`, exact phase/qualification/recovery receipts, `construct.log` and
`binding-diagnostic.json` substantiate this checkpoint. The accompanying
manifest binds all evidence bytes. This is an evidence/documentation change;
no software behavior changed and no new software-test result is claimed.
