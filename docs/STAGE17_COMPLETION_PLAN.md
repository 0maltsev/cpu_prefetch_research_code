# Stage 17 completion plan

Updated 2026-11-03. Implementation baseline: `e59c4e0`.
Scientific authority: immutable `protocol/2.0.0-pre.3/` and accepted decisions.
This roadmap is not an execution authorization or a scientific amendment.

## Current position

- SSH to `root@94.126.205.83` works through the development PC's persistent
  server-only VPN bypass.
- Last semantically validated stand state: EXT001–006 accepted, two
  transitions, EXT007–010 missing. The latest read-only refresh confirms the
  same boot and journal head; it does not substitute for semantic replay.
- Persistent worker stacks, owner-mapped arena/ring/traces/primary streams,
  bounded drain/reset, exact joins and retained residency-observer components
  are implemented. Both compiler suites pass 513/513; 104 calibration cases
  pass all four sanitizer configurations. These are software checks.
- No capture from the approved 36-run discovery study has executed.
- The prior release/qualification cannot automatically qualify changed source.
  Preserve prospective policy v54 and all earlier records; create a complete
  versioned successor when the integrated source is ready.

## Ordered work and acceptance gates

| Step | Work | Evidence required to close it |
|---|---|---|
| 1. Complete the executable runtime | Place and declare provider/backend/clock/controller coordination, worker TLS and other relevant runtime memory; connect actual before/during/after residency, affinity, fault, clock, hardware-state and environmental checks; complete watchdog, independent raw publication, partial-failure retention and restoration. Review formal Q16a, Q16b, Q16c and pilot paths together, including persistent warmup and service counts restricted to the fixed interval. | Integrated success and mandatory-failure tests; no forbidden work in measured intervals; exact complete-worker generated-code checks under both accepted disassemblers; supported compiler/sanitizer/static/schema/canonical checks. |
| 2. Qualify a clean release and current stand | Build a complete source-bound runtime and policy successor; verify archive, binary and dependency identities; repair the missing runtime closure through the new release, not an improvised old wrapper. Replay the real journal and refresh all evidence invalidated by source, boot or platform changes. Reverify CPU pairs, mapping, clocks, atomics, memory, privileges, storage and restoration. | Clean release/custody records and a semantically admitted current predecessor chain. Historical EXT001–006 stay preserved; reuse only evidence whose dependency validity is demonstrated. |
| 3. Freeze and run duration discovery | Bind actual capacities/working-set classes, immutable run IDs/seeds, monitoring coverage, buffers, copies, timeout and total stand budgets. Complete the finite diagnostic action record under D-178 before running its 36 captures. | Retained raw/control/failure records and count-only selection of a common duration, or an explicit unresolved result. No diagnostic data enters formal calibration. |
| 4. Close EXT007 | Freeze a new D-037 formal plan using discovery evidence; collect the required 708 fresh Q16a runs, then Q16b service calibration and Q16c feasibility in dependency order. Derive exact distance, service-rate and load outputs using accepted methods. | Phase-bound requests/authorizations, raw evidence, typed results, custody and calibration freeze accepted by the operational verifier. Any feasibility result awaiting final matrix exposure remains explicitly provisional. |
| 5. Close EXT008 and EXT009 | Generate the exact prospective pilot matrix, schedules, IDs, seeds, repetitions, horizons, warmup/recovery, admission tickets and stop rules from accepted calibration. Prove buffers and durable capacity for that exact plan, both custody domains, transfer receipts, partial retention and recovery rehearsal. | Current-stand EXT008 plan and checked EXT009 storage/custody/recovery evidence. Old stand-v2 values are not defaults for stand v5. |
| 6. Close EXT010 and execute the pilot | Bind all nine accepted predecessor resolutions into the exact finite Stage 17 pilot authorization. Execute only its permitted runs, retaining ordered primary streams, control observations, manifests, joins and failures. Produce treatment-blind pilot summaries. | Admitted EXT010, complete controller/worker output lineage, verified restoration, accepted custody and the required pilot output set. Ten catalog resolutions alone do not establish successful pilot completion. |
| 7. Freeze the study and validate Stage 17 exit | Derive settling/warmup, measurement horizon, dependence/block-length diagnostics, covariance and environmental limits from the prescribed blinded evidence. Use the independently justified primary practical bound for precision sizing; derive role counts, final matrix/schedules, replacement/stand/storage budgets and re-evaluate final matrix zero-loss feasibility. Validate all applicable freeze items and the derived Stage 17 completion chain. | Accepted append-only freeze and Stage 17 exit evidence, with no applicable unresolved blocker. Produce a Stage 18 readiness handoff; its independent authority/access/sealing requirements remain separate. |

## Discovery controls already approved

Do not ask the owner to approve this design again:

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

## Owner inputs and existing authorization

Two questions are currently pending:

1. Is the stand dedicated and available exclusively for these runs? What hard
   deadline or storage restriction applies beyond measured resources? Derive
   conservative proposed budgets from actual resources, then bind finite limits
   before each action; absence of a deadline does not authorize an infinite run.
2. What primary practical latency effect and application rationale should define
   `delta_star`, or where is its already-approved record? No approved value was
   found in the reviewed repository/current authoring records. The imported
   freeze checklist explicitly reserves `log(1.05)` for sensitivity analysis.
   Do not choose the primary threshold from observed treatment effects.

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

Keep step 1 as the active integration milestone. Audit downstream plan,
custody and freeze contracts in parallel where they do not depend on new data.
Report completed milestones, exact evidence, remaining blockers and the next
gate. Component tests are supporting evidence, not the project completion goal.
Estimate stand time and durable bytes once prospective run counts and durations
are concrete; do not invent an end date from the current software test count.

A failed mandatory gate is retained and reported as infeasible/unresolved under
the protocol, not converted to success. Stage 17 is complete only when the
accepted pilot/freeze/exit graph demonstrates it. Stage 18 execution requires
its separate authority and access chronology; no Stage B/C work is included.

## Governing references

- [Current EXT007 readiness](STAGE17_EXT007_CALIBRATION_READINESS.md)
- [D-178 approved discovery design](decisions/0178-stage17-q16a-duration-discovery-proposal.md)
- [D-046 phase-bound authority](decisions/0046-stage17-phase-scoped-execution-authority.md)
- [Operational authorization and EXT007–010 contracts](STAGE17_OPERATIONAL_AUTHORIZATION.md)
- [Immutable freeze checklist](../protocol/2.0.0-pre.3/PROTOCOL_FREEZE_CHECKLIST.md)
- [Calibration invalidation rules](decisions/0038-stage13-calibration-records-arithmetic-and-invalidation.md)
