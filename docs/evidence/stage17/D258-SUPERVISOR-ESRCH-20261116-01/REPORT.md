# D258: Supervisor process-exit race repair

The Q16b run remains stopped with16 archived captures and17 checkpoints. Its
primary recorded error is ProcessLookupError(ESRCH), followed by native loss
reported by the archive broker. The original failure record has no traceback,
so the exact historical PID cannot be recovered from that record.

Real Linux procfd tests reproduce the matching defect: open a living task's
/proc/PID/stat, let the task exit and reap it, then read the already opened
file. Linux returns ESRCH. The former supervisor catches only ENOENT at four
observation boundaries and aborts on this ordinary disappearance. The same
final14-test suite fails against the byte-identical baseline (6 errors and1
failure) and passes against the repaired supervisor. This confirms the defect;
the historical causal interpretation remains qualified as described in D258.

The new supervisor catches only FileNotFoundError and ProcessLookupError at
the four existing observation handlers. Other permission/I/O failures,
nonzero owner exits, wrong native identities, native quiescence loss, pidfd
signal checks, deadlines, signature, archive and analysis gates stay enforced.
A bounded phase traceback/exception type/errno is now retained on unexpected
failure, and the exception still propagates through the original cleanup path.

14 targeted tests and22 existing supervision regressions pass locally. Tests
include real kernel exit races, a surviving sibling, genuine native loss,
nonzero exits, permission and I/O faults, wrong executable rejection, diagnostic
publication, expired deadline rejection, and AST comparison proving only the
four intended function bodies changed (three observation functions and phase
diagnostics). Mocked-chain regression fixtures use software-only future time
ceilings because the actual original preparation lease is expired; production
Budget is unchanged and its expired lease is separately tested as rejected.

The fix is Python-only. Qualified native source/worker, measurement code and
archive broker remain unchanged; C++ sanitizers do not exercise these changes.
No Q15/Q16 experiments, raw analysis, repetitions, deadline resets or data
modifications were performed. Old deployed operator bytes and all failed
scientific evidence stay unchanged. Stand verification of the separate immutable fix capsule is now complete.
Collection is still stopped;
no interrupted family or attempt is silently restarted by this correction.


Actual stand verification completed15 November21:59:15 UTC
(16 November00:59:15 Moscow). The baseline reproduced the regression failure;
the fixed14-test suite and22 original regression tests both exited0. All
children were disposable software-only Python processes run as UID1000. The
Q16 service remained failed/MainPID0 before and after;16 archives,17 checkpoints
and the original native failure receipt remained unchanged. No scientific raw
files were read. The old deployed supervisor still has SHA256
d43f9f4235399e3b88b8ce9450ff13b9baab1b8771337f90aacc6b890562730a.

The fixed artifact is installed separately at
E26/d258-supervision-fix-1/run_daycap_study.py, SHA256
47e819dbcd6110d5b356d091e706141131efa5938b0ae0740059efc4d3cb1416.
Its closed capsule manifest is217516422920f953bd04a65057311d4153d3dc65cc80fdb47336cdd3feca70a8,
with administrative source53ac7a5 (full revision in manifest). Every capsule
member was rechecked after tests. Qualified native source A2 and worker305c
remain unchanged. Verified temporary transfer archives were removed from the
PC and stand; all scientific and historical failure evidence remains retained.

The correction is deployed and software-verified; it is not a running collection
or a signed continuation of the consumed family. The expired preparation cutoff
and original overall deadline remain unchanged. A later continuation must
explicitly validate retained evidence and satisfy its own protocol/authority
and remaining time budget; this repair does not silently restart failed runs.
