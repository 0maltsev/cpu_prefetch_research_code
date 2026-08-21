# ADR-0036: Stage 13 matrix zero-loss feasibility and global action

- Status: `ACCEPTED`
- Date: 2026-08-21
- Classification: Scientific feasibility inference / matrix-level load policy
- Decision owners: Protocol owner; statistical owner; block-planning owner; repository owner
- Protocol version: `2.0.0-pre.2`
- Supersedes: None; resolves D-036
- Lifecycle gate: Accepted before Stage 13 implementation; final evaluation requires immutable Stage 14/15 exposures and schedules

## Context and scientific constraints

Protocol Section 5.3 requires a separate open-loop, exactly-one-attempt
feasibility probe using the actual schedule family and retaining every `FULL`.
It requires simultaneous per-cell upper confidence bounds on per-offered-event
full probability and fixes the matrix lower bound
`max(0,1-sum_c E_c*p_U,c)`. It leaves confidence, dependence treatment,
estimator, `pi_matrix`, and global load-reduction action open.

Events within a run are not justified as independent experimental units. Zero
observed `FULL` events cannot imply zero probability. No decision may tune an
individual favorable cell, relax confirmatory strict zero loss, or use
confirmatory outcomes.

## Options considered

1. Event-level Clopper-Pearson/binomial limits.
2. Ordinary event bootstrap or a zero-observed-is-zero rule.
3. Whole-run cluster bootstrap or GEE.
4. A weighted Hoeffding upper bound over independent bounded run-cluster full
   fractions with prospective Bonferroni allocation.

Options 1 and 2 silently assume event independence or can emit an invalid zero
bound. Option 3 leaves resampling and small-sample behavior open. Option 4
requires independence only between runs, allows arbitrary within-run
dependence, and has a positive finite-input margin.

## Decision

Select D-036 suite
`MATRIX-FULL-RUNCLUSTER-WHOEFFDING-BONFERRONI-v1` as specified by the accepted
[`STAGE13_CALIBRATION_DECISION_BUNDLE.md`](../STAGE13_CALIBRATION_DECISION_BUNDLE.md).

For feasibility run `r`, cell `c`, and global scale `g_j`, define

```text
Y_cjr     = N_full,cjr / N_offered,cjr
w_cjr     = N_offered,cjr / sum_r N_offered,cjr
p_hat,cj  = sum_r w_cjr * Y_cjr
alpha_cj  = (1/20) / (180 * 5) = 1/18000
p_U,cj    = min(1,
                p_hat,cj
                + sqrt(log(1/alpha_cj) * sum_r(w_cjr^2) / 2))
```

with these constraints:

- runs, not offered events, are independent units; arbitrary within-run event
  dependence is permitted;
- exact counts and weights remain rational; a zero-offered run is invalid for
  the estimator and cannot be silently repaired;
- the plan and schedule family must support the prospective common-marginal
  interpretation needed to apply a run-cluster bound to the planned matrix;
- the familywise one-sided confidence is `19/20` over all 180 cells and all five
  candidates, including candidates not reached after prospective stopping;
- the transcendental margin uses only the accepted D-038 outward-rounded,
  versioned offline arithmetic profile; and
- every finite all-zero observation set retains a strictly positive upper
  margin before clamping.

Freeze `pi_matrix=19/20`. For immutable `Rtotal` and schedules, calculate

```text
E_cj = Rtotal * N_sched,cj
P_L,j = max(0, 1 - sum_c E_cj*p_U,cj)
```

and evaluate this exact descending common rational scale ladder:

```text
g = [1/1, 9/10, 4/5, 7/10, 3/5]
rates(g) = g * [1/4, 1/2, 3/4] * mu_ref
```

Each scale has a disjoint predeclared namespace and a complete 180-cell probe
plan. Select the first descending candidate with `P_L>=19/20`. If none passes,
the design is infeasible or unresolved. No new ladder point, cell-specific
rate, capacity revision, confidence reduction, threshold relaxation, achieved-
throughput substitution, or confirmatory tuning is implicit.

Q12 does not provide probe counts, horizons, schedules, seeds, `mu_ref`,
`Rtotal`, `N_sched`, stand evidence, or a final load result.

## Evidence

- The protocol and statistical owners answered
  `Q12 - accept the bundle` on 2026-08-21.
- Imported implementation specification Sections 5.2 and 5.3 and the
  matrix-feasibility freeze-checklist row.
- Hoeffding's bounded-independent-variable inequality, applied to independent
  run-cluster fractions rather than events.
- No pilot, confirmatory, full-rate, throughput, or latency outcome was used to
  select confidence, threshold, or ladder.

## Consequences and compatibility

Scientific effect: the bound may be very conservative and may show that the
planned matrix is infeasible. This is preferred to an unsupported event-
independence claim. The 0.95 simultaneous confidence and `pi_matrix=0.95` are
distinct owner choices.

Compatibility effect: cluster unit, common-marginal prerequisite, weights,
confidence allocation, five-candidate family, threshold, scale ladder,
exposure equation, arithmetic profile, and first-pass global action are suite
identity.

## Verification and acceptance tests

Stage 13 must test direct golden vectors, unequal offered counts, all-zero
positive bounds, `p_U=1` clamping, `180*5` allocation, exact exposure and union
arithmetic, overflow, all five candidates, first-pass selection, no-pass state,
missing cells, zero-offered runs, namespace separation, and rejection of a
cell-specific adjustment. Inputs and outputs must remain synthetic.

Final feasibility must remain `NOT_EVALUATED` until exact `Rtotal`,
`Nruns=180*Rtotal`, and every planned schedule count are frozen.

## Rollback or supersession

Changing the cluster unit, dependence assumption, weighting, confidence,
multiplicity family, `pi_matrix`, ladder, exposure, arithmetic profile, or
selection action requires a new policy ID, prospective superseding ADR, and a
complete feasibility recalculation. Existing evidence remains immutable.

## Protocol-amendment assessment

No amendment is required because the protocol leaves these feasibility choices
open while fixing strict confirmatory zero loss and the union-bound equation.
Any nonzero acceptable confirmatory full threshold, cell-specific favorable
adjustment, outcome-driven tuning, or altered matrix equation conflicts with
protocol-fixed behavior and requires protocol review.
