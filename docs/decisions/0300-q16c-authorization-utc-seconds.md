# D300: obey the immutable whole-second authorization schema

Accepted engineering repair; this grants no continuation, retry, signing,
qualification or new execution window after the stopped D298 attempt.

D298 passed installed metadata admission, rearmed isolation/guarding and authored
the exact unsigned94 request. Authorization publication then rejected fractional
seconds in expires_at_utc. The immutable v6 authorization schema requires whole
UTC seconds for both time fields. No authorization or signature was published,
no native Q16c attempt started and no new measurement occurred. Both recovery
paths verified complete restoration. All qualification and86 reports remain.

The administrative generator now formats issued_at_utc and expires_at_utc with
`isoformat(timespec='seconds')`. Both are floored from the same actual UTC sample
and the fixed24860-second duration. Their integer-second difference stays24860;
the actual expiry is shortened by less than one second, never extended. The
schema, UTC parser, authority duration ceiling, signed-window deadline, fixed
measurement window, scientific validators and measured native release do not
change. No rounding up, future issue time or permissive regex is introduced.

Tests evaluate the exact original and repaired authoring expressions from the
actual operator AST against the pinned v6 UTC schema. The original recorded
fractional failure is reproduced; repaired fields pass at zero, one,956026 and
999999microseconds and preserve the exact duration without extending expiry.
A separate actual owner-bound unsigned authoring check may exercise the saved
request and unchanged qualified CLI, publishing only a distinct unsigned draft.
It must not sign or execute that draft, rearm controls, or repeat qualification.

The previously launched packet4 stays immutable. This fix affects prospective
administrative source only; D298 remains stopped under its first-failure rule.
Any future continuation must separately account for its already registered empty
family and saved unsigned request, preserve all original evidence and deadlines,
and prove signing/setup budgets before launch. Do not re-register an existing
family or silently retry the consumed D298 authority. No Stage18 authority exists.
