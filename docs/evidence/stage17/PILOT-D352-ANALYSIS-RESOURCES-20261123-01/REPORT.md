# D352 retained analysis resource accounting verified

The live resource gate now reserves all retained joined streams, bounded
metadata/allocation allowance and their objects within the unchanged512GiB
workspace. It also requires explicit authenticated commitments for other
workspace and scratch usage, including old failed evidence. There is no zero
default, compression/loss credit, policy expansion or actual usage claim.
The evidence contract is version2; old declarations cannot silently omit these
obligations. [Decision and equations](../../../decisions/0352-s180-retained-analysis-resource-accounting.md).

All17 resource cases pass Python development/debug execution using the actual
unchanged frozen worker's cold descriptions. Five affected registered suites
pass72 distinct cases. Protocol/schema/canonical checks and changed Python AST
and whitespace checks pass. No native code changed or new native sanitizer path
exists. The original omission test fails before implementation; its log is
retained. The first full direct run has five protected-root fixture ownership
errors; all other12 cases pass. Running the unchanged ownership checks in an
isolated user/PID namespace passes all17; no protection was weakened.

The independent row-width equation and boundary tests cover the previously
omitted retained output, old workspace/scratch overflows, source order, object
budgets, explicit declarations, live resource replay and failure latching.
All platform/state fixtures remain software evidence only.

Unchanged D334 conservative offered ceilings give433012032000 joined logical
bytes. Output with metadata/allocation allowances is433389519360 bytes.
The complete planned workspace comparison uses447990954726 bytes, leaving
101764859162 for other commitments. The scratch comparison leaves237363220020
bytes for other commitments. These calculations explicitly use zero other
commitments as a hypothetical arithmetic case, not an authenticated census or
actual admission. Actual allocated charges remain mandatory at runtime.

No raw was copied to the PC or reanalyzed, and no stand action or operational
window started. Historical raw and the required original namespace audit remain
preserved. Stage17 remains incomplete. Next: supervised inverse/analysis timing,
the qualified outer operator/profile, actual census and full ETA/admission;
the single pilot remains conditional, and Stage18 execution remains deferred.
