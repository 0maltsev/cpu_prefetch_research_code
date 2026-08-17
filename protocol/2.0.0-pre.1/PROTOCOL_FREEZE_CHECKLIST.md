# Protocol Freeze Checklist

Protocol version: **`2.0.0-pre.1`**. The paper and implementation specification are an implementation-ready structural protocol, but they are not pilot- or execution-ready. Version `2.0.0-pre.1` is an incompatible logical primary-data-model revision; `1.0.0-pre.1` lineage and hashes remain preserved. Confirmatory execution is prohibited until every applicable mandatory item is frozen in a dated, treatment-blind, append-only record. `FIXED` means the semantics are normative; it does not imply that a platform mapping or numerical output already exists.

| Item | Required record | Status | Gate while unresolved |
|---|---|---|---|
| Protocol version | semantic version and amendment lineage | **FIXED:** `2.0.0-pre.1` | schema/manifests must name it; `1.x` instances are incompatible |
| Primary practical bound `delta_star` | log-ratio bound, application budget, rationale, reviewers, date | **BLOCKED:** `log(1.05)` is sensitivity-only | no confirmatory execution or final precision counts |
| Queue-full policy | retained drop; no repeat; strict `N_full=0` estimability gate | **FIXED** | required full-outcome cell blocks dependent confirmation |
| Optional nonzero full-rate threshold | only by pre-result amendment with rationale | **NOT USED** | cannot be introduced post-outcome |
| Stage A record ownership | preinitialized immutable one-line records | **FIXED** | mutable lifecycle remains Stage C |
| Consumer action | read immutable index and aligned 64-bit payload, update private rolling checksum, then record `f_i` | **FIXED** | implementation must preserve exact hot-path structure |
| Integer-mixing operation | identity, constants, generated-code signature, fixed instruction structure | **BLOCKED BEFORE PILOT** | no pilot until selected and recorded |
| Producer waiting | tight clock poll plus non-sleeping relax; no sleep/yield/scheduler API | **FIXED** | platform relax mapping required before pilot |
| Consumer polling | repeated `try_dequeue`; same relax after empty; no adaptive backoff | **FIXED** | platform relax mapping required before pilot |
| Termination/drain | release `arrivals_finished`, acquire observe, empty queue, drain exit; control line isolated | **FIXED** | memory-order/code review pending implementation |
| Primary quantile | non-interpolated `X_(ceil(pN))`; exact inclusion/drain boundary | **FIXED** | changes require amendment |
| Logical timestamp rows | every row has `run_id`; exact handling/lookup/invocation/linearization/response/action boundaries and equations | **FIXED** | implementation must preserve all logical fields |
| Ordered raw data | producer and consumer ordered rows; external immutable stream envelope; inline rows test-only; histograms derived only | **FIXED** | physical format/version still required before pilot |
| Physical raw format/version | physical-format record ID, encoding, integer time unit, row sizes, endianness, compression, alignment, copy policy | **BLOCKED BEFORE PILOT** | no primary latency pilot or storage acceptance |
| Buffer/storage budget | symbolic formulas resolved with scheduled/accepted rows, row sizes, `N_eff`, copies, `180*Rtotal`; compression post-measurement only | **FIXED RULE; OUTPUT BLOCKED** | no pilot until capacity proof passes |
| Producer/consumer join | `(run_id, accepted_ordinal)`; repeating record index validates only; failed audit distinct from joined data | **FIXED** | implementation evidence required before pilot |
| Phase/integrity evidence | final rolling checksum, pre/post content, ordered-index and address-delta checksums with algorithm/version IDs | **FIXED FIELDS; ALGORITHMS OPEN** | completed valid latency run cannot omit it |
| Run lifecycle | planned/early failures/measurement/drain/completed plus independent join status and conditional artifacts | **FIXED** | semantic-validator implementation required |
| Warm-up seed namespace | disjoint namespace and generator mapping | **OPEN BEFORE PILOT** | no reproducible warm-up |
| Warm-up duration | `max(5 s, 10*tau_corr)`, `tau_corr=h_max/rho_min` | **FIXED RULE; BLOCKED OUTPUT** | pilot must supply `h_max` and `rho_min` |
| Deterministic reset/origin | drained barrier; ring empty/cursors zero; sentinel `pi[0]`; recycler `pi[1..C]`; event/counter/sample positions zero | **FIXED** | phase checks pending implementation |
| Start barrier and `t0` | both workers synchronize; clock-derived `t0` | **FIXED RULE; PLATFORM MAPPING OPEN** | clock protocol required |
| Recovery interval | one treatment-blind duration and acceptance rule | **BLOCKED PENDING PILOT/BUDGET** | whole-plot chronology incomplete |
| Cache-history interpretation | controlled warm-start; no explicit cache/HW-prefetch clearing | **FIXED** | must not be described as cold start |
| Stage A block roles | `H3_TRAIN`, `H3_VALIDATION`, `H1H2_SUPPLEMENTAL` assigned before execution | **FIXED** | final role counts blocked by precision |
| Common block namespace | common Stage A namespace with role-specific subspaces; no separate H1-H2 namespace | **FIXED** | RNG namespace mapping open |
| Validation sealing/unsealing | authority, timestamps, input hashes, selection checksum/signature, unseal record | **BLOCKED BEFORE CONFIRMATION** | validation and H1/H2 outcomes inaccessible |
| H3 candidate order/tie break | `(R0,H0)` through `(L1,H1)` in fixed package-first order | **FIXED** | no adaptive ordering |
| H3 training rule | mean `log(Qhat_0.999)` independently in six contexts | **FIXED** | no validation/counter influence |
| H3 training count | `Rtrain>=12`; all 45 unordered candidate pairs in six contexts (270) have prospective SE no greater than `delta_star/2` | **FIXED RULE; OUTPUT BLOCKED:** bound, covariance, budget | H3 unresolved |
| H3 validation count | `Rval>=8`; pre-selection one-sided max-T family has `6*10*9=540` ordered comparisons and largest half-width no greater than `delta_star/2`; report 54 after selection | **FIXED RULE; OUTPUT BLOCKED** | no outcome-based resizing or validation access |
| H1/H2 count | separate seven-member H1 and twenty-member H2 max-T sizing gives `R_H1`, `R_H2`; `R12=max(R_H1,R_H2)` | **FIXED RULE; OUTPUT BLOCKED** | no combined 27-member family or final schedule |
| Final Stage A count | `Rtotal=max(R12,Rtrain+Rval)`; `Nruns=180*Rtotal` | **FIXED FORMULA; BLOCKED OUTPUT** | no final run count |
| Complete-block replacement | invalid run makes original block incomplete; only a new complete role-compatible block may replace | **FIXED** | budget/authority still open |
| `R_replacement_max` | maximum replacement blocks per platform | **BLOCKED BEFORE CONFIRMATION** | no confirmatory collection |
| Replacement authority | named role and append-only authorization record | **BLOCKED BEFORE CONFIRMATION** | no replacement may be scheduled |
| Effective-tail handling | genuine `N_eff<200000` retained, not extended/repeated; dependent confirmation blocked | **FIXED** | horizon still pilot-dependent |
| Measurement horizon | common applicable horizon chosen from treatment-blind pilot | **BLOCKED PENDING PILOT** | p99.9 gate unresolved |
| Moving-event-block diagnostic | correlation estimator, selected length, half/double sensitivity | **BLOCKED PENDING PILOT** | stability/effective count unresolved |
| Service-rate calibration estimator | fixed-duration independent throughput runs; one-sided 95% run-level LCB per cell; minimum valid LCB | **FIXED CONTRACT; ESTIMATOR/DURATION/COUNT OPEN** | `mu_ref` unavailable |
| Matrix zero-loss feasibility | simultaneous per-cell full-probability upper bounds; exposure over `Rtotal`, `180*Rtotal` runs, and scheduled events; union-bound whole-matrix lower probability; frozen confidence, `pi_matrix`, estimator, and global reduction | **FIXED CONTRACT; OUTPUT BLOCKED** | loads cannot be frozen; strict confirmatory zero loss unchanged |
| Common capacities and loads | near/far `C`, residency evidence, `mu_ref`, final 0.25/0.50/0.75 rates | **BLOCKED PENDING PLATFORM/CALIBRATION** | Stage A matrix unavailable |
| `d2` calibration contexts | ring-off; separate P/C latency and issue interval; platform/placement/capacity-specific | **FIXED CONTRACT; OUTPUT BLOCKED** | `R2` unavailable |
| RNG algorithm/version | algorithm, version, master seed, derivation function | **OPEN BEFORE PILOT** | no reproducible randomization |
| Seed namespaces | common Stage A plus warm-up/train/validation/supplemental/calibration/pilot/diagnostic/B/C subspaces | **FIXED STRUCTURE; VALUES OPEN** | schedules/permutations unavailable |
| Schedule contract | kind/family, namespace derivation, integer unit, absolute/delta encoding, origin, horizon, half-open boundary, exact rational rate, count, overflow, checksum | **FIXED LOGICAL FIELDS; PHYSICAL ENCODING OPEN** | semantic validation and concrete encoding required before pilot |
| Permutation algorithm | exact algorithm/version and rejection-stream behavior | **OPEN BEFORE PILOT** | node/event orders not reproducible |
| Checksum algorithms | artifact SHA-256 plus frozen rolling/data checksum algorithms and serialization | **PARTLY FIXED:** artifact SHA-256; data algorithms open | manifests/data cannot be sealed |
| Manifest/schema versions | Draft 2020-12 schema IDs, compatibility matrix, positive/negative conformance suite, semantic-validator contract | **FIXED STRUCTURE:** handoff schemas at `2.0.0-pre.1` | implementation must reject `1.x` data or migrate by explicit amendment |
| Queue provenance/license | algorithm version, artifact, license, reuse/adaptation mode | **BLOCKED BEFORE IMPLEMENTATION ARCHITECTURE** | no source reuse decision |
| Language/toolchain/atomics | standard, compiler/library, flags, atomic width/alignment/lock freedom | **BLOCKED BEFORE PILOT** | correctness mapping unavailable |
| Generated-code acceptance | package-specific review of queue boundaries, waits, record loads/checksum, dispatch absence | **FIXED GATE; EVIDENCE BLOCKED** | no performance pilot |
| Sanitizer/correctness acceptance | unit/property/stress/sanitizer matrix and refinement argument | **FIXED GATE; EVIDENCE BLOCKED** | no performance pilot |
| Platform/topology | CPU/microcode/cache/NUMA inventory and eligible cores | **BLOCKED BEFORE PILOT** | placement/classes unavailable |
| Hardware-prefetch states | requested and independently verified state records | **BLOCKED BEFORE PILOT** | HW-prefetch contrast unavailable |
| Privileged-control authority | named operator/authorization and readback method | **BLOCKED BEFORE PILOT** | no privileged state change |
| Clock acceptance | source, conversion, serialization, skew/drift/resolution/read-cost limits | **BLOCKED PENDING PLATFORM/PILOT** | timestamps invalid |
| Environmental acceptance | frequency, thermal, migration, interrupt, switch, residency limits | **BLOCKED PENDING BLINDED PILOT** | run-validity rules incomplete |
| Performance counters | events, encodings, domains, privilege, grouping, attribution limits | **OPEN, PLATFORM-DEPENDENT** | diagnostic coverage may shrink |
| Wall-clock stand budget | calibration, pilot, Stage A, replacements, counters, B/C, authority | **BLOCKED** | no collection authorization |
| Author/anonymity | explicit anonymous decision or repository-supported identities | **SUBMISSION ONLY; OPEN** | PDF author remains empty |
| Submission format | venue/template/page limit/style/accessibility | **SUBMISSION ONLY; OPEN** | generic article layout remains |

## Freeze and amendment rule

No blocked or open item may be resolved using confirmatory treatment outcomes. Every freeze/unseal/amendment record names the protocol version, authority, timestamp, input hashes, affected estimands, and superseded record without overwriting it. Queue-full and genuine effective-tail insufficiency never authorize repetition. An invalid run permits only complete-block replacement within `R_replacement_max`; exceeding that limit stops collection and leaves the study unresolved.
