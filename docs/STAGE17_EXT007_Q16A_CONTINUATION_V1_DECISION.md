# Q16a complete-context continuation v1

Status: **ACCEPTED — the owner's continuation instruction is recorded separately.**
Amendment ID: `AMEND-2.0.0-pre.3-Q16A-CONTINUATION-v1`.
Policy ID: `Q16A-COMPLETE-CONTEXT-CONTINUATION-v1`.
Base: immutable `protocol/2.0.0-pre.3/`; no imported file is changed.
Scope: the one E23 formal Q16a incident identified below. No general retry policy.

## Incident and explicit exception

Original plan SHA256 `a9bef1239ea03d3871e40a0c52a0a3375d1eac7512d299443dd18405e89572f7`, size 12,128,860 bytes, source `dd981b4fdcf953386d4a7514fec381ff9be6e359`.
Original failure receipt SHA256 `a6704159e3dd2adab1598e2959202cfa5a6a0b5c9164a01fab967deeb251c7e4`, size 1,082 bytes (`cpu-prefetch-stage17-phase-action-failure/6`).

The original prospective plan has 12 hardware-state/context combinations, each with 59 repetitions. Captures 0–176 occupy exactly contexts 0–2 (H0/near, all three working sets). Ordinal 177 is the failed 178th attempted capture, the first H0/far context; ordinals 178–707 were not collected. Archive completion is not independent scientific validation.

D037 and D038 prohibit hidden top-up, selective cell rerun and immutable-plan revision. This amendment makes one explicit exception: reuse only the three **complete** original contexts after independent validation, and enumerate one new execution family for the remaining nine complete contexts. It does not reclassify the original failed family as successful, splice a replacement into its immutable plan, or invoke protocol section 10.8's confirmatory 180-cell replacement procedure.

The narrow eligibility condition is an independently proved infrastructure failure before either warmup or measurement was released in original ordinal 177, with zero raw observations, retained failure/control/custody evidence, verified restoration and owned-process cleanup. No measured tail, FULL outcome, insufficient count, timing observation or apparent effect is a reason to select a replacement. If the zero-observation boundary or any required prefix validity/compatibility gate fails, this continuation is ineligible; there is no alternative subset or additional collection allowance.

## Fixed execution population

1. Preserve the entire original plan, authority, attempt, completed raw archives, failed ordinal 177, failure receipt and restoration evidence under their original identities and versions. The original family remains failed.
2. Independently verify all 177 original captures, including exact physical/canonical custody, both phases, every required control, all raw primary/demand joins, clocks, counts and the existing eligibility rules. Require all 59 original captures in each of contexts 0, 1 and 2. No selecting favorable runs or substituting captures from an incomplete context. Correctly reconciled FULL and zero loss remain separate gates.
3. Create a genuine `cpu-prefetch-stage17-formal-ring-plan/3` containing **only 531 captures**. Local ordinal `j=0..530` corresponds to original planned slot `177+j`; context is `3+floor(j/59)`, repetition is `j mod 59`. Run H0/far contexts 3–5, then H1 contexts 6–11, preserving the original order. New local ordinal 0 explicitly replaces the zero-observation failed slot 177; the other 530 slots were unattempted. No 708-row execution projection or fabricated complete-family result is permitted.
4. Use new plan/action/attempt/output/phase identities and namespaces. Preserve **every original prospective numeric `seed_hex`** for the corresponding original slot, including slot 177's explicit zero-observation exception. Bind the arena seed to the new measurement identity with that unchanged numeric value. A continuation-aware namespace audit must distinguish this authorized numeric-seed preservation from prohibited reuse of run IDs, seed IDs or namespace IDs; it must not waive other collisions.
5. Preserve the D212 demand window and method `RING-D2-RUNTAIL-LTL95C95-WINDOW-v2`, five-second warmup, one-second measurement, minimum 100,000 observations in each required series, 59 independent captures per context, geometry, immutable arena, instrumentation, controls, bounds, drain/termination rules, exact quantiles, marginal tolerance construction and distance arithmetic. No duration, capacity or threshold is inferred from the interrupted family's observed values.
6. Keep the complete original finite numeric capture, family and storage ceilings, even though fewer captures execute. Preserve the existing D233 shared program ID, scope and quota accounting. Only exact new qualified source/profile bindings and explicitly declared relocation of the same five cpuset monitoring files may change. Each cpuset source keeps its basename, requested observations, byte/read bounds and other fields; all five paths move together to one owned delegated partition. Actual qualified topology/control values and ownership must be checked separately.
7. Execute this continuation family at most once after its required source qualification, accepted-prefix and compatibility proofs, resource checks, namespace audit and exact signed admission pass. Stop on the next Q15/Q16 failure, retain evidence, reap owned workers and restore hardware/owned isolation. No automatic repair-and-retry cycle, further continuation, top-up or replacement is authorized.

## Compatibility and access chronology

This decision is made **after** the original execution failure and access to its progress, custody and failure records. It is not a pre-original-run amendment or a claim of blinded data access. Preserve the actual access inventory with the acceptance evidence. No statistical guarantee is gained merely by declaring compatibility.

D038's material-change rules continue to apply. A compatibility manifest must bind both original and successor source/worker/qualification identities and prove the unchanged measured kernels, queue/workload/timing primitives, hardware mapping, capacities, geometry, capture boundaries and estimator. Required cold orchestration or infrastructure repairs are disclosed and qualified. New qualification does not relabel old captures as having been collected by the new worker. Any material measurement change or unresolved compatibility blocks reuse under this policy.

## Plan, proof and result boundaries

The `/3` plan's closed `continuation` object contains:

- `policy_id`, `seed_policy`, `future_retries: 0`;
- exact `{path,size_bytes,sha256}` bindings `parent_plan`, `failed_family_receipt`, `accepted_prefix_manifest`, `compatibility_manifest`;
- `reused_contexts: [0,1,2]`, `remaining_contexts: [3,4,5,6,7,8,9,10,11]`;
- `original_first_ordinal: 177`, `failed_original_ordinal: 177`;
- `monitor_path_replacements`, each `{original_path,continuation_path}`, either empty or all five unchanged cpuset basenames.

The parent/failure hashes and sizes are fixed to this incident. Prefix and compatibility bindings are mandatory, but a well-formed reference does not establish the underlying proof. The parent comparison runs at both request authoring and execution; authentication of the original failure/restoration, full accepted prefix, compatibility, qualified release/resources and signed authority is independently mandatory.

The prefix record authenticates the original incomplete family and its 177 eligible captures without assigning that family a successful terminal state. The new family's custody result covers only its 531 captures. A separate versioned composite calibration record must identify both original plans, original report identities, the exact logical 12-by-59 mapping, failure lineage, amendment, prefix proof and compatibility proof. Reuse the unchanged D230 estimator only after all required captures are valid. Never mutate an old report's ordinal, source, run ID, plan hash or version to fit the new family. An incomplete or invalid composite remains unresolved.

D233 stand-primary lossless custody remains in force. Original raw archives stay on the stand; small reports/provenance may be copied. This amendment creates no Q16b/Q16c result, calibration freeze, EXT007 admission, pilot credit or Stage 18 authority. Operational records remain required; this document itself executes nothing.
