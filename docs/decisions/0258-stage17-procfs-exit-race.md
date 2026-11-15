# D258: Tolerate disappeared process observations without weakening failure gates

- Status: ACCEPTED for the owner's instruction to fix the Q16b problem
- Date: 2026-11-16
- Scope: cold supervisor observation and diagnostics; no scientific-method change

The Q16b supervisor stopped after16 archived captures. Its primary recorded
exception is ProcessLookupError(ESRCH); cleanup then retained an archive failure
reporting lost native quiescence. The historical supervisor recorded only the
exception representation, so the precise failing lookup and PID are unknown.

Disposable-process software reproduction demonstrates that Linux returns
ESRCH when a /proc/PID/stat file is opened while a task exists and read after
that task exits and is reaped. This reaches the same supervisor code path as
ordinary archive helpers exiting during monitoring. The previous observer
catches ENOENT/FileNotFoundError but lets ESRCH/ProcessLookupError abort the
whole study. This is a confirmed defect consistent with the historical primary
error. Cleanup initiating native termination and producing the broker's later
worker-loss error is the leading causal interpretation, not a claim that the
missing historical traceback has been recovered.

Treat only FileNotFoundError and ProcessLookupError as a disappeared task at
the four existing observation catches: reading a parent's children list,
reading a child's start time, observing the owner and checking tracked child
liveness. Continue observing surviving owned processes. Do not catch arbitrary
OSError, permission or I/O failures. Do not relax PID start-time checks, pidfd
signalling, executable identity checks, native quiescence, nonzero owner exits,
ownership, deadlines, hardware restoration or scientific admission.

Add bounded failure_type, failure_errno and failure_traceback fields to the
existing cold phase-result record. Record at most20 traceback frames and32768
characters without local-variable capture. Reraise the exception and retain
the original cleanup path. Diagnostics confer no success or retry authority.

Publish the repaired supervisor as a new separately bound artifact. Keep the
deployed failed supervisor, its signatures, one-use attempt and all qualified
native/archive bytes unchanged. Native source A2 and worker305c need no rebuild
or new clock/Q15 qualification for this Python-only correction. Tests exercise
real kernel procfd races, preserved error/identity/native-loss gates, unchanged
source bodies and existing cleanup/receipt/analysis contracts. These establish
software correctness only; no performance claim or new observations result.

This fix does not restart an experiment, consume another attempt, reset an
expired preparation lease, extend the original24-hour deadline, alter the
120-capture matrix, or declare the16 archives scientifically validated.
Collection remains stopped. Reusing retained data and any future continuation
must satisfy its own explicit protocol, validity, signature and budget gates.
