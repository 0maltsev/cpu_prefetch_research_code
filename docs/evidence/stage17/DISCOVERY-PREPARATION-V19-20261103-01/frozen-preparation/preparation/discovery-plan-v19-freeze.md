# Prospective EXT007 diagnostic study, v19

This operational freeze implements the already approved D-178 study and the
owner's instruction to complete EXT007 autonomously. It does not change the
scientific grid or grant pilot/Stage18 authority. The exact signed request is
still required before execution.

Plan SHA-256: e841c5f00b90db7871423133e1842e6441cdf585633978833239693881ba0967.
Clean release: ac64633662c4e61c8dd98e332dc70f77085e2e48.
Worker SHA-256: cffe204c0af3bffaa46912a52dfa3d79c2114ba1b87e74f71573dd2a14071268.
Qualification: actual v19 journal 000009, EXT001–006, restored Q15-W and both
clock pairs passing under the retained isolated partition.

Exactly 36 captures: H0/H1 x near/far x three working sets x 100ms/1s/5s,
in the contract's fixed order, each preceded by five seconds of persistent
warmup and verified drain/reset. No retry, extension, replacement or top-up.
Run identities, SHA256-derived seeds, exact mappings, namespaces and original
predecessor bytes are enumerated in plan/action-inputs/namespace documents.
The count-only selector requires 100,000 valid observations in each of four
sequences in every context; diagnostic data never count toward formal Q16a.

Prospective engineering controls: five million warmup attempts; one/four/five
million measurement attempts for the three durations; drain capacity C+1;
30-second drain limit; two-MiB owner stacks; finite polling limits 10^12.
Major-fault limit zero; minor faults and context switches remain recorded
without invented acceptance thresholds. During observations are scheduled at
2.5s of warmup and one quarter of measurement, with one page per mapped region;
before/after observations cover all mapped pages. All 86 enumerated public
environment sources are requested in all six observation groups. Their
numeric pilot acceptance thresholds remain unfrozen.

The finite per-capture watchdog sums allowances for setup120s, warmup5s,
measurement, two drains30s, publication1800s and cleanup120s. Total study
watchdog is 76,093.2 seconds including study setup/cleanup. These are explicit
upper controls, not measured completion times or an expected 21-hour runtime.
The requested warmup/measurement intervals themselves total 253.2 seconds.

Storage: output budget258,733,870,648 bytes; maximum validation drain spool
16,620,003,326 bytes; additional10GiB reserve. Required space per custody
filesystem is286,091,292,214 bytes. Use one uncompressed retained copy on the
stand and one on the existing PC. Transfer and verify original sizes/hashes
after collection; perform independent count/control validation only after
both copies exist. Retain partial/failure evidence. No archive duplicate or
compression is budgeted. The PC write/fsync/readback probe is retained.

Memory: worker AS cap224GiB; controller planning allowance2GiB; separate
stand reserve16GiB. Prepare finite per-process memlock12GiB and retain actual
UID/GID, capability, affinity and limit readbacks. Check fresh MemAvailable
against242GiB and storage against the complete allowance before launch.
The active-allocation model includes native mappings, full monitoring and
publication trees; it must retain at least16GiB headroom below the AS cap.
This is not a guarantee about allocator retention, publication success,
warmup attempt sufficiency or eventual observation counts.

Warmup capacity exhaustion or mandatory hardware/integrity/placement/clock/
cleanup failure stops the study. Measurement capacity exhaustion remains
INSUFFICIENT subject to all mandatory gates. Restore the recorded MSR
prestate on failure/completion; otherwise quarantine. Preserve the approved
CPU partition while dependent work continues, and restore its recorded
prestate when the work stops. No automatic second attempt is authorized.
