# D298 stopped at authorization schema; no new capture, restoration verified

D298 exited1 on19November2026 at23:14:36 Moscow (20:14:36UTC), about5minutes
after launch. Supervisor346747 is gone, MainPID0, and the dedicated service has
no control group. There has been no retry or new execution window.

The attempt passed actual owner/journal/signature/report/deployment admission,
reused all qualification and86 completed reports, prepared fresh isolation and
guarding, registered the94-capture family, and authored its exact unsigned
request. Authorization publication failed before signing. The native executor
never started, no warmup/measurement phase was released, and there are zero new
native checkpoints. All94 captures remain pending.

The exact error is a v6 authorization schema rejection at expires_at_utc:
`2026-11-20T03:06:53.956026Z` does not match the pinned whole-second UTC pattern.
The same producer uses fractional seconds for issued_at_utc. This is a formatting
defect in the administrative authoring code, not a failed CPU measurement or
qualification. The immutable schema correctly rejected it. No authorization
file, signature or prepared formal-execution record was published.

The stopped request is1,979,653bytes, SHA256
`38fc71fd8e6a5dc79c95284999fa51b6b42a41d7cdb6477b4886272af931851c`.
Its94-capture family remains durably registered under plan SHA1212db59. The
physical working directory is empty and matches the recorded FAMILY device/inode.
The registration tip is still the final ledger object; there has been no later
capture transaction. Exact registration and physical facts are retained in
`registered-empty-family.json`. Do not re-register it as an unused new family or
discard this progress. The request has never had native execution authority.

Supervisor and independent StopPost recovery both report verified=true, errors[].
Complete MSR0x1a4 readbacks for CPUs0/1/8 match their zero prestate. Isolation,
root controls and maintenance restoration are verified; the guarded control is
restored to1. The collection owner was reaped; independent recovery needed no
signals. Every passed qualification, all86 Q16c reports, Q16a708/Q16b120 and prior
failed evidence remain preserved.

[D300](../../../decisions/0300-q16c-authorization-utc-seconds.md) fixes prospective
administrative timestamp formatting to whole seconds without changing the
schema, duration ceiling, native release, scientific inputs or deadlines.
Fourteen focused tests pass, including the exact failed precision and boundary
fractions. The separate actual-owner unsigned authoring check passed at23:22:32
Moscow, exercising the saved request and unchanged qualified API in118.655s.
It published only a distinct unsigned draft; no signature, execution, rearm or
retry occurred. Its exact schema/lineage/state result and draft are retained here.
The original300s collection setup allowance remains unverified end-to-end after
this fix; authorization preparation took118.7s alone. A future continuation must
prepare/finalize authority before starting collection, not merely rerun the failed
source with timestamp precision changed.

The running ETA is withdrawn. D298's next-failure stop is consumed: no automatic
retry, new day, extension or further native action is authorized. Any prospective
continuation must explicitly admit the existing empty registered family and saved
request, prove the remaining signing/setup envelope, preserve qualification/data
and obey the original deadline. EXT007/Stage17 remain incomplete; no Stage18
authority exists.

Only small public status, failure, registration and restoration receipts were
copied. No raw data or private operational configuration was transferred. The
startup record remains a historical observation; this stopped checkpoint is the
current state. The accompanying manifest binds the evidence bytes.
