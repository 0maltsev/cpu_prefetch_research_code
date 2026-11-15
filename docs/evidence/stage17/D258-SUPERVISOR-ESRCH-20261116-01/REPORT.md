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
scientific evidence stay unchanged. This source checkpoint precedes stand
verification of a separate immutable fix capsule. Collection is still stopped;
no interrupted family or attempt is silently restarted by this correction.
