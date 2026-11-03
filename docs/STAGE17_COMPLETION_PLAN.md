# Stage 17 completion plan

Updated 2026-11-03. Step 2 DONE: successor release `a1ade11`, clock and Q15-R/W qualified.
Step 3: R1 STOPPED at its first warmup; R2 STOPPED at 10:49 UTC on
2026-11-03 with exit 1. Failed R2 raw/control evidence is retained on the stand
under accepted D206 (`m_dur=1`, EXT007 only). PC raw copying is cancelled and
scoped PC cleanup is complete; only small results/provenance go to the PC.
Stand-side capture-9 diagnosis and phase validation are complete: both phases
reconcile, but full-capture validation rejects the mandatory session stop.
Duration selection remains unresolved. Next gate is ACCEPTED ADR0207's
36-capture 1 s/2 s/5 s grid, owner approved; implementation and qualification are complete at `a1ade11`. Both clock pairs and Q15-R/W passed; EXT001–006 are accepted in fresh v5-20. The single D207 family launched at 12:29:53 UTC and is in progress. R1 had no measurement phase or formal calibration, and its
MSR/cgroup restoration was verified. R2 isolation reapplication passed with
the same boot and required controls; exact signature and fresh PC checks passed.
Scientific authority: immutable `protocol/2.0.0-pre.3/` and accepted decisions.
This roadmap is not an execution authorization or a scientific amendment.

## Active owner priority: EXT-007 only

The owner directs fastest completion of EXT-007, with no new optional work,
and requests an update after every step. Defer EXT008–010, pilot execution and
Stage 18 work. Finish only already-started checks and necessary calibration work.

1. **Complete:** finish current verification and freeze the discovery implementation.
2. **Complete:** clean successor release `a1ade11`, both clock pairs and Q15-R/W pass.
   EXT001–006 are admitted at v5-20 journal 000009, six resolutions and three
   transitions, READY_FOR_STAGE17_PHASE_AUTHORIZATION. Q15-W restored hardware.
3. **Stopped, unresolved:** the first 36-capture family stopped during capture 0
   warmup. The consumer reached five million attempts; the independently reconciled
   prefix spans 1,472,506,585 ns. No measurement phase ran. Retain the
   failure and verified restoration; do not retry or extend this family.
4. **R1 failed-prefix validation complete:** all 12 files (1,142,655,488 bytes)
   had SHA-verified two-copy custody at that checkpoint; independent validation reports
   `FAILED_STUDY_PREFIX_RECONCILED`. Full-capture validation is rejected for the
   mandatory session stop; the 36-capture study is not valid and duration
   selection remains unresolved. The owner
   [accepted the working-set amendment and one R2 family](STAGE17_EXT007_WORKING_SET_AMENDMENT_V1_ACCEPTANCE.md).
   The bounded stand helper confirmed capacities 512 / 65,536 / 1,048,576.
   Exact R2 bindings are prepared and live author-request validation passed.
   Exact signature verification and fresh PC capacity/custody checks passed.
   R2 ran from 10:33:27 UTC until its reported stop at 10:49 UTC on 2026-11-03,
   exit 1. Ten controls and 75 files (52,465,834,715 bytes) are retained;
   restoration result reports true. D206 replaces the PC raw-copy gate with
   verified stand-primary custody for EXT007 only. PC copying is cancelled and
   cleanup is complete after stand-original verification. Capture 9's monitoring
   overran its 100 ms measurement window; both retained phases reconcile, but
   full-capture validation rejects `mandatory session stop`. Earlier captures
   remain unassessed and no duration selector ran. Next gate is
   [ACCEPTED ADR0207](decisions/0207-stage17-ext007-discovery-duration-revision.md):
   36 fresh captures across 1 s/2 s/5 s, approved by the owner. Versioned implementation and qualification are complete at `a1ade11`;
   both clock pairs and Q15-R/W passed. EXT001–006 are accepted at v5-20
   journal 000009. The exact signed D207 family launched at 12:29:53 UTC
   on 2026-11-03 and is in progress, with no automatic retry.
5. Complete required formal-calibration fixes, freeze the prospective plans,
   then execute Q16a (708 fresh captures), Q16b (3,540 runs) and Q16c in order.
6. Validate and seal calibration evidence, derive the freeze, and admit EXT-007.

The owner accepted [D206](decisions/0206-stage17-ext007-stand-primary-custody.md)
and its [recorded custody-policy approval](evidence/stage17/STAND-CUSTODY-D206-20261103-01/owner-acceptance.json).
For EXT007 diagnostic and calibration data only, including R1 and R2, retain
one authoritative uncompressed raw/control copy on the stand (`m_dur=1`).
There is no independent raw backup; RAID redundancy is not another custody
domain. This explicitly supersedes D-033's second raw-copy requirement in that
scope, not its scientific validity rules or pilot/Stage 18 custody requirements.
Download small results and provenance to the PC. PC raw copying is cancelled;
scoped cleanup completed at 11:12:37 UTC after stand-original verification:
16 PC files totaling 7,926,030,848 bytes were removed, with no stand raw deletion.
[Cleanup and withdrawal receipts](evidence/stage17/STAND-CUSTODY-D206-20261103-01/README.md)
preserve historical two-copy records. Preserve
failed raw data on the stand. Verify capacity before any future finite plan;
D206 grants no experimental invocation or retry.
Report each completed step or changed blocker against this six-step plan.

## Current position

- Step 3's first warmup stopped with native exit 1; partial warmup/control
  evidence was retained, with no measurement or formal collection. MSR and
  cgroup restoration were verified. All 12 retained files (1,142,655,488 bytes)
  had SHA-verified two-copy custody at that checkpoint. Independent validation reports
  `FAILED_STUDY_PREFIX_RECONCILED`: five million consumer attempts; elapsed
  prefix 1,472,506,585 ns; accepted and consumed both 4,199,692 including one
  drained event; FULL=0. Full-capture validation is rejected for the mandatory
  session stop. This reconciles the failed prefix, not the 36-capture study;
  duration selection remains unresolved and formal runs contributed are zero. The
  [stopped-attempt evidence](evidence/stage17/DISCOVERY-STOPPED-V19-20261103-01/README.md)
  preserves the family and restoration records.
- The owner [accepted the full-footprint amendment and one R2 recovery family](STAGE17_EXT007_WORKING_SET_AMENDMENT_V1_ACCEPTANCE.md).
  The bounded stand footprint helper confirmed capacities 512 / 65,536 /
  1,048,576 under the approved nominal-cache/sharing interpretation. Exact R2
  bindings are prepared; live author-request validation passed. Isolation
  reapplication passed with the same boot and required controls. Fresh stand
  inventory covered 87 paths with zero errors; all 86 monitoring source sizes
  fit their frozen buffers. Exact signature verification passed; fresh PC
  capacity was 392,758,439,936 bytes against the 388,544,851,990-byte requirement,
  and its custody probe passed. R2 started at 10:33:27 UTC on 2026-11-03 under
  the single approved authority (supervisor PID 24845, child PID 24847; fresh
  attempt marker 944 bytes). R2 stopped at 10:49 UTC with exit 1. Ten controls
  and 75 files totaling 52,465,834,715 bytes were retained; restoration result
  reports true. Accepted D206 now governs stand-primary raw custody; PC copying
  is cancelled and scoped cleanup is complete. Failed raw/control evidence
  stays on the stand. The [D206 diagnosis and phase-validation record](evidence/stage17/STAND-CUSTODY-D206-20261103-01/README.md)
  confirms capture 9's required observation started at 25.005774 ms, took
  163.531831 ms and ended at 188.537605 ms, beyond the 100 ms measurement
  window. Both workers had reached their deadlines; the observer correctly
  stopped the session. Warmup accepted/consumed both equal 9,635,880, FULL=4,059,
  with actual reset verified; measurement accepted/consumed both equal 187,535,
  FULL=0. Both phases reconcile. Full-capture validation still rejects
  `mandatory session stop`; no selector ran, captures 0–8 remain unassessed,
  and duration selection is unresolved. No individual slow file or syscall
  was isolated by this diagnosis. Only small reports/provenance returned to the PC.
- Next gate: [ACCEPTED ADR0207](decisions/0207-stage17-ext007-discovery-duration-revision.md),
  36 fresh captures across 1 s/2 s/5 s, with unchanged five-second warmup and
  approved 30-million-attempt buffers for both phases. Owner approval is recorded; clean release `a1ade11` is qualified and the
  exact signed family launched at 12:29:53 UTC. Selection is pending full
  retained-study validation. R2 observations do not select its duration.
- Predecessor release `ac64633` passes seven strict codegen gates and local/stand
  package verification (1,826 files). Both v2 clock pairs pass, and actual
  Q15-R/W passes with verified W restoration. EXT001–006 are admitted at v5-19
  journal 000009 with three transitions. The original EXT005 admission draft
  omitted the catalog-required mixed evidence and authorization summary; it is
  preserved separately, and the corrected admission uses unchanged actual data.
  [Verified qualification copies](evidence/stage17/STAND-QUALIFICATION-V19-20261103-01/README.md)
  retain 133 stand files, including the accepted journal and rejected drafts.
- The owner ran the privileged local D124 search: 98,268 JSON files, zero
  errors and zero matching typed receipts within the declared public scope.
  Fresh stand (33,022 files) and Git-history searches are retained with their
  exact scope and exclusions. The resulting attestation passed admission.
[R2 stopped-attempt and custody record](evidence/stage17/DISCOVERY-RECOVERY-STOPPED-V19-20261103-01/README.md).

## Earlier checkpoints (historical)

No-capture and open-gate statements in this section describe the checkpoints
below, not the current stopped family or completed Step 2.

- Earlier v5-18 passed all six read-only preflight observations. EXT001/002/003/006
  are admitted at journal 000006, PREFLIGHT_ACCEPTED, two transitions.
  The first unisolated clock check failed its tail bound. The owner-approved
  finite isolated requalification then passed near (p99.999 2.284/2.877 us),
  but far failed before complete collection because a legacy software guard
  rejects CPU 8. Both permitted invocations are consumed. The stand was
  restored and independently checked; no Q15 hardware execution followed.
  [Exact retained results](evidence/stage17/STAND-CLOCK-REQUALIFICATION-20261103-01/README.md)
  have verified stand/PC copies. D-205 repairs clock-collector affinity using
  the existing generic owner-binding mechanism, with unchanged CLI pair gates
  and clock rules. Its repaired clean release is verified, and the owner
  approved the new finite v2 family. No discovery or formal calibration has run.
- Preserve v5-17's rejected authoring/admission drafts (fractional authority
  timestamp, then commented known-hosts input); v5-18 uses whole-second
  authority and the exact same host key in the required single-line form.
  A prep-only helper successor supplies all policy-pinned schema bytes;
  qualified release source is unchanged.

A smaller buffer proposal fits modeled storage and active-memory budgets;
full environmental sizing, fresh resources and finite limits remain to freeze.
The proposal does not guarantee the full warmup or sufficient capture counts.
Earlier checkpoints below retain their historical scope.

- Step 1 is complete at local commit `2ff7667`. Its clean release passed all
  seven codegen gates and both local/stand package verification (1,732 files).
  Fresh stand context v5-16 contains only the initialized genesis journal.
- Step 2 found a blocker before qualification: the policy-29 preflight executor
  imports a legacy journal binding and changes semantic policy 55 to 47.
  An independent local reproduction then rejects current schema hashes.
  Preserve that release and genesis; repair only this prerequisite through a
  versioned successor and qualify a fresh context. No qualification attempt,
  discovery capture, or formal calibration followed from this release.
- SSH to `root@94.126.205.83` works through the development PC's persistent
  server-only VPN bypass.
- Last semantically validated stand state: EXT001–006 accepted, two
  transitions, EXT007–010 missing. The latest read-only refresh confirms the
  same boot and journal head; it does not substitute for semantic replay.
- Persistent worker stacks, owner-mapped arena/ring/traces/primary streams,
  bounded drain/reset, exact joins and retained residency-observer components
  are implemented. With D-200, both compiler suites pass 519/519; 107 calibration
  and 44 platform cases pass all four sanitizers. These are software checks.
- No capture from the approved 36-run discovery study has executed.
- D-200 adds caller-owned session coordination/results, full mapped-controller
  software integration and native owner-thread TLS payload observations. Full
  relevant live runtime footprint, actual control monitoring, publication/watchdog and
  exact qualified diagnostic admission remain open. The stand is dedicated to
  these experiments; final primary precision bound `delta_star` is unresolved.
- The prior release/qualification cannot automatically qualify changed source.
  Preserve prospective policy v54 and all earlier records; create a complete
  versioned successor when the integrated source is ready.
- D-201 integrates the mapped runtime and native thread/hardware readback
  components. Both owners remain alive through final control observations;
  timed before/during/after groups enforce explicit per-phase disturbance
  limits and retain independent page results. Both development suites pass
  563/563, with 124 calibration and 71 platform cases passing all four
  sanitizer configurations. Native publication and diagnostic admission are
  being connected next; these checks do not qualify a stand capture.
- D-202 now connects native execution, environmental file snapshots, raw
  publication, diagnostic v5 admission and independent raw/control validation.
  Both full suites pass 631/631; all four sanitizer configurations pass 142
  calibration, 85 platform and 24 targeted runner cases. The production worker
  passes seven codegen gates. D-203 supplies caller-owned linked storage for
  later required service calibration. Source freeze and clean release/stand
  qualification are the immediate next gates. No discovery capture has run.

The D-204 local fix now passes real authoring/admission/executor readiness,
release compatibility, metadata and retained-data regressions. The largest
31,944,212-value metadata test uses about 285 MiB peak RSS. Its clean successor `817c652` is now deployed. The owner completed the
privileged public-evidence search; its scope, exclusions and zero-match result
are retained, together with stand and Git-history searches. Fresh qualification
is now blocked at the far-pair software affinity defect in v5-18 as recorded above.

## Ordered work and acceptance gates

| Step | Work | Evidence required to close it |
|---|---|---|
| 1. Complete the executable runtime | Place and declare provider/backend/clock/controller coordination, worker TLS and other relevant runtime memory; connect actual before/during/after residency, affinity, fault, clock, hardware-state and environmental checks; complete watchdog, independent raw publication, partial-failure retention and restoration. Review formal Q16a, Q16b, Q16c and pilot paths together, including persistent warmup and service counts restricted to the fixed interval. | Integrated success and mandatory-failure tests; no forbidden work in measured intervals; exact complete-worker generated-code checks under both accepted disassemblers; supported compiler/sanitizer/static/schema/canonical checks. |
| 2. Qualify a clean release and current stand | Build a complete source-bound runtime and policy successor; verify archive, binary and dependency identities; repair the missing runtime closure through the new release, not an improvised old wrapper. Replay the real journal and refresh all evidence invalidated by source, boot or platform changes. Reverify CPU pairs, mapping, clocks, atomics, memory, privileges, storage and restoration. | Clean release/custody records and a semantically admitted current predecessor chain. Historical EXT001–006 stay preserved; reuse only evidence whose dependency validity is demonstrated. |
| 3. Freeze and run duration discovery | First family stopped at its first warmup. All 12 R1 files had verified two-copy custody at that checkpoint; independent failed-prefix reconciliation passes, but full-capture validation rejects the mandatory session stop. Duration selection is unresolved. Preserve R1 failure/restoration evidence. The amendment and one R2 family are owner accepted; stand footprints and live author-request validation pass. Exact signature verification and fresh PC checks passed. R2 stopped on 2026-11-03 at 10:49 UTC with exit 1; ten controls and 75 files (52,465,834,715 bytes) are retained, restoration result true. D206 cleanup and capture-9 phase validation are complete. Both phases reconcile; full capture is invalid for mandatory session stop caused by monitoring-window overrun. Captures 0–8 remain unassessed; duration selection is unresolved. Accepted ADR0207 changes the fresh36 grid to 1 s/2 s/5 s and is owner approved; implementation and qualification precede exact admission. | Retained raw/control/failure records and count-only selection of a common duration, or an explicit unresolved result. No diagnostic data enters formal calibration. |
| 4. Close EXT007 | Freeze a new D-037 formal plan using discovery evidence; collect the required 708 fresh Q16a runs, then Q16b service calibration and Q16c feasibility in dependency order. Derive exact distance, service-rate and load outputs using accepted methods. | Phase-bound requests/authorizations, raw evidence, typed results, custody and calibration freeze accepted by the operational verifier. Any feasibility result awaiting final matrix exposure remains explicitly provisional. |
| 5. Close EXT008 and EXT009 | Generate the exact prospective pilot matrix, schedules, IDs, seeds, repetitions, horizons, warmup/recovery, admission tickets and stop rules from accepted calibration. Prove buffers and durable capacity for that exact plan, both custody domains, transfer receipts, partial retention and recovery rehearsal. | Current-stand EXT008 plan and checked EXT009 storage/custody/recovery evidence. Old stand-v2 values are not defaults for stand v5. |
| 6. Close EXT010 and execute the pilot | Bind all nine accepted predecessor resolutions into the exact finite Stage 17 pilot authorization. Execute only its permitted runs, retaining ordered primary streams, control observations, manifests, joins and failures. Produce treatment-blind pilot summaries. | Admitted EXT010, complete controller/worker output lineage, verified restoration, accepted custody and the required pilot output set. Ten catalog resolutions alone do not establish successful pilot completion. |
| 7. Validate Stage 17 exit and hand off Stage 18 readiness | Run the D-115 completion validator against the exact ten resolutions/three transitions, admitted EXT010, matching pilot attempt/result/completion, every planned run, sealed manifest, restoration and process quiescence. Preserve and transfer the pilot artifacts and identify the scientific freezes still needed for Stage 18. | Accepted Stage 17 completion record derived from actual pilot evidence. Stage 18 remains separately blocked until its scientific freezes, independent trust, authority and access chronology pass. |

The prior roadmap combined operational Stage 17 completion with final scientific
readiness. D-115 and `validate_stage17_completion()` distinguish them. Final
settling/warmup, measurement horizon, covariance/precision, role counts, final
matrix/schedules, exposure-based feasibility and stand/storage budgets must be
frozen before Stage 18 admission; they are not additional fields of the Stage 17
operational completion validator. In particular, unresolved application-based
`delta_star` does not block Stage 17 discovery, calibration or pilot collection.

## Discovery controls already approved

The base design below remains approved. The separate
[accepted amendment](STAGE17_EXT007_WORKING_SET_AMENDMENT_V1_ACCEPTANCE.md)
approves the corrected full-footprint interpretation and one R2 family;
R2 consumed its single signed attempt and stopped; independent validation awaits completed custody. No retry or automatic new family is authorized:

- 12 H0/H1 × near/far × working-set contexts, each with 100 ms, 1 s and 5 s:
  36 prospectively enumerated diagnostic captures.
- Planning minimum: 100,000 valid observations in each of the four
  producer/consumer demand/advancing-issue sequences; 100,000 issue intervals
  require at least 100,001 advancing observations.
- Exact five-second pre-freeze warmup under pre.3/D-116, with the accepted
  persistent-worker drain/reset transition and separate measurement origin.
- Select the shortest common candidate passing counts and mandatory validity
  checks across all contexts. Do not select using tails, d2 or treatment gains.
- No passing candidate leaves selection unresolved. No extensions, top-ups,
  hidden retries, favorable reruns or relabeling diagnostic data as formal data.

Finish material formal-calibration source changes before formal collection.
If a separate diagnostic build is necessary, retain its identity and explicitly
establish applicability to the final formal build. A material change invalidates
dependent evidence; it cannot be concealed by keeping the same record label.
The downstream source audit confirms that the current Q16b summary includes
drain in its total consumer count and supplies no separate fixed-interval
completion count. Nonpilot `warmup_reset_verified` is also currently a literal
success rather than execution evidence. Both require actual implementation and
versioned output/admission changes before formal collection; the old summaries
cannot establish those requirements.

## Owner inputs and existing authorization

The owner answered on 2026-11-03:

1. “only to this exps”: the stand is dedicated to these experiments. No additional
   deadline or storage cap was specified. Derive conservative budgets from
   actual resources and bind finite limits before each action; absence of a
   deadline does not authorize an infinite run.
2. “anything”: no positive primary practical latency bound or application
   rationale was selected. Keep `delta_star` unresolved for final precision
   planning. This does not block engineering, qualification or the approved
   duration discovery. The imported freeze checklist reserves `log(1.05)` for
   sensitivity analysis; do not choose the primary bound from observed effects.

Reuse the user's existing authorization for autonomous engineering, SSH/stand
setup and verified local commits without pushing. The accepted pilot owner-role
collapse remains disclosed. Reuse established identities and custody arrangements
where valid; inspect their actual records before requesting replacements.

Prepare complete, reviewable phase records with source hashes, dependencies,
run sets, limits and validity windows before surfacing any genuinely missing
owner-only approval or signature. D-046 requires dependency-ready phase-bound
authority; SSH access and a general intention to finish cannot replace those
records. Do not re-request already established permission. Ask about new
scientific decisions only when existing protocol/approval does not resolve them.

## Working method and completion claim

Step 3 remains unresolved: both R1 and R2 stopped. D207 approves one new family only after its prerequisites.
For R1, the historical two-copy verification and independent failed-prefix reconciliation remain recorded;
full-capture validation rejects the mandatory session stop. No valid-study or
duration-selection result follows from that reconciliation.
The narrow formal-calibration source audit is frozen at its current findings.
Preserve the accepted amendment, exact R2 bindings and failed partial family.
The analysis gate is now accepted D206 plus verified stand-primary evidence:
exact original sizes/SHA-256, manifest bindings, quiescence and restoration.
That gate passed for the completed stand-side capture-9 diagnosis and independent
phase validation. The required monitoring operation overran the 100 ms window;
both phases reconcile, but full capture remains invalid for mandatory session stop.
Captures 0–8 remain unassessed. PC copying is cancelled and cleanup complete;
small reports/provenance and cleanup receipts are retained on the PC, while
failed raw/control data remains on the stand.
The full-36-study wrapper is inapplicable to this partial family and remains
unchanged. Prefix validation cannot establish a valid full study or select a
common duration. No selector ran; selection remains unresolved. Implement and qualify
accepted ADR0207, then obtain exact operational admission before
any new 36-capture 1 s/2 s/5 s family.
Report completed milestones, exact evidence, remaining blockers and the next
gate. Component tests are supporting evidence, not the project completion goal.
Estimate stand time and durable bytes once prospective run counts and durations
are concrete; do not invent an end date from the current software test count.

A failed mandatory gate is retained and reported as infeasible/unresolved under
the protocol, not converted to success. Stage 17 is complete only when its
accepted pilot/exit graph demonstrates it. Stage 18 execution requires all
scientific freezes plus its separate authority and access chronology; no Stage
B/C work is included.

## Governing references

- [Current EXT007 readiness](STAGE17_EXT007_CALIBRATION_READINESS.md)
- [ACCEPTED ADR0207 duration revision — owner approved](decisions/0207-stage17-ext007-discovery-duration-revision.md)
- [Completed D206 cleanup and capture-9 validation](evidence/stage17/STAND-CUSTODY-D206-20261103-01/README.md)
- [D206 accepted EXT007 stand-primary custody](decisions/0206-stage17-ext007-stand-primary-custody.md)
- [D206 original proposal and owner acceptance](evidence/stage17/STAND-CUSTODY-D206-20261103-01/owner-acceptance.json)
- [Accepted working-set amendment](STAGE17_EXT007_WORKING_SET_AMENDMENT_V1_ACCEPTANCE.md)
- [Retained amendment proposal](STAGE17_EXT007_WORKING_SET_AMENDMENT_V1_PROPOSAL.md)
- [Stopped-family evidence](evidence/stage17/DISCOVERY-STOPPED-V19-20261103-01/README.md)
- [Forthcoming R2 preparation and results](evidence/stage17/DISCOVERY-RECOVERY-V19-20261103-01/README.md)
- [D-178 approved discovery design](decisions/0178-stage17-q16a-duration-discovery-proposal.md)
- [D-046 phase-bound authority](decisions/0046-stage17-phase-scoped-execution-authority.md)
- [Operational authorization and EXT007–010 contracts](STAGE17_OPERATIONAL_AUTHORIZATION.md)
- [Immutable freeze checklist](../protocol/2.0.0-pre.3/PROTOCOL_FREEZE_CHECKLIST.md)
- [Calibration invalidation rules](decisions/0038-stage13-calibration-records-arithmetic-and-invalidation.md)
