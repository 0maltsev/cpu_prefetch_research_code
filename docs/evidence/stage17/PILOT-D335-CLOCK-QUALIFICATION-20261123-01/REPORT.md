# S180 owned clock-qualification checkpoint

The near/far clock portion of the pending S180 qualification producer is
implemented under [D335](../../../decisions/0335-s180-owned-clock-qualification.md).
**No actual stand control, qualification, source generation, measurement or
operational window started.** This is local software verification. Full Q15
qualification, actual EXT008, outer operator/profile and scientific validation
remain required. Completed EXT007 and frozen native34247ce stay preserved.

The library requires the actual prepared environment and approved D333 guard.
It pins the unchanged478632-byte clock helper, consumes a durable fresh attempt,
uses ordered single-use near/far entries into the original reserved partition,
and retains actual worker PID/start/image witnesses for existing supervised
recovery. The child verifies requested limits, placement and controller affinity.
Near must pass before far starts. Every actual failure latches the environment
for restoration only; no namespace adoption or automatic retry exists.

The existing100000 prime/10000000 delta counts per role, three cross-core
windows in each direction,100000 exchanges per window, CPU0/1/8 mapping and
unchanged helper evaluator are required. Read exact canonical raw summary
fields/types; the helper's aggregate is not relabeled as a full timestamp trace.
Clock-pair proof explicitly has full_qualification=false and grants no admission,
Q15 or execution authority. Its immutable bindings preserve the original stage
start/deadline/completion, and later proof failures cannot be revived by replacing
changed bytes. The subsequent Q15 producer must preserve that original deadline.

Actual held-leader/pidfd/subreaper supervision bounds console delivery and
terminates/reaps children on error or interruption, including escaped owned
descendants. Require independent original empty-partition and platform readbacks
before accepting each pair. Preserve failed/partial raw and terminal evidence.
Explicit child umask0077 and per-pair ownership checks remove reliance on the
parent shell's defaults. The complete bounded metadata fits512KiB/16 inodes
inside D334's existing headroom; quotas, counts and stage caps are unchanged.

Fresh combined regression passes105 cases in6 suites in140.97 seconds, including
the then19 clock cases and86 environment/compaction/parent/launcher/resource
cases. After the last clock-only permission refinement, its registered20-case
suite passes in75.45 seconds; all20 pass Python development/debug allocation
in98.73 seconds. The final test logs distinguish these checkpoints. A separate
synthetic endpoint passes GCC ASan/UBSan for both pairs, and targeted clang-tidy
passes. Production C++ is unchanged; native sanitizer evidence is for that
endpoint only. AST, whitespace, format, schema/canonical/provenance and runner/
qualification checks pass. The original protocol check initially picked an
ambient rpds-py2026.9.1 because the provisioned PYTHONPATH was omitted; rerunning
with the existing pinned2026.5.1 prefix passes without installing dependencies.

Tests use real sealed ELF execution, executable hashes, pidfds, child limit
readbacks, signals, pipe bounds, durable files and supervisor cleanup. Explicit
temporary-file/platform doubles represent MSRs, cgroups, membership, sysctl and
CPU selection; the separate ELF emits software summaries and never qualifies
hardware. It has no production linkage or artifact-selectable runtime switch.

Initial failures are retained: the endpoint initially emitted noncanonical JSON;
the proof reader initially received a list despite requiring a top-level object;
entry verification was excluded from the stage cap; and inherited umask0002
made raw summaries fail the protected-evidence gate. All are corrected. The
initial short timeout test could expire during setup under debug allocation;
it now injects expiry at the post-registration clock boundary to verify actual
live-child cleanup deterministically, without changing production timing limits.
Two initial test assertions also used the wrong exception/cleanup field and
were corrected. This is software diagnosis, not experimental retry or new data.

Frozen worker/helper images, original guard/core, source worktree, production
C++, protocol and config invariants pass. `invariants.json` and `verification.json`
record their scope. CTest log content is retained with only trailing blank lines
normalized in the two last-test text snapshots. Evidence inventory hashes all
retained files. Verified duplicate PC staging may be removed after comparison;
stand raw data is untouched.

Next: persistent Q15 qualification and complete scoped EXT008 producer, qualified
outer operator/profile and historical proof replay, independent scientific pilot
validator, actual inputs/admissions and full ETA, then fresh qualification and
the single conditional pilot. No whole-run ETA or launch readiness is claimed.
Stage17 remains incomplete; Stage18 execution remains deferred.
