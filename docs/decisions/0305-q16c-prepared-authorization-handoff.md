# D305: restore the prepared authorization binding at collection handoff

Accepted engineering repair; this grants no retry, rearm, operational signing,
new window or additional manual continuation after the D301/D302 stop.

D301/D302 passed actual source/owner/ledger/time/resource admission, rearmed and
completed authorization readiness successfully. Collection then failed immediately
while constructing execute_formal arguments: the split-out authoring code had
removed the local auth assignment, but the unchanged call still referenced auth.
This was an agent-introduced Python wiring defect, not a failed CPU measurement.
No native attempt or capture occurred. Both recovery paths verified restoration.

The rendered collection prefix now takes auth directly from the actual prepared
handoff's authorization binding, alongside the already loaded request, signature
and plan. It does not recreate, replace or resign anything. The ordinary signed
execution call and all native, observation, custody and scientific functions are
unchanged. Historical packet b7a466f and its signed outputs remain immutable.

The earlier finite root-sequence fixture treated the collection child as a process
boundary, and the body-preservation test did not establish that its removed
prefix still provided every local name. New verification executes the actual
rendered collection function with real common()/file readback and prepared
metadata, substituting only the platform witness and final execution boundary.
It verifies the exact authorization/signature paths and94-capture observation
contract, then exercises publication after the simulated boundary. Before the
repair it reproduces NameError(auth). A separate stdlib symbol-table check catches
the same unresolved name across all rendered scripts. Both pass after the fix.

A separate actual UID1000 verify_formal_signature/prepare_action check may validate
the issued signature and complete qualified preparation API without execute_once,
native arm, control rearm, journal attempt or worker execution. Its result must
be retained and distinguished from a live native run. No changed C/C++ sanitizer
target exists. A prospective continuation must preserve this stopped signed
authority and prepared file, and explicitly arrange distinct fresh output paths
and sufficient authority lifetime; it cannot blindly repeat readiness over files
that already exist or reuse an expired/insufficient-lifetime authority.

The approved first-failure stop remains binding. All qualification,86 reports,
saved request/family and prior raw data remain intact;94 captures remain pending.
No Stage18 authority or research completion claim is added.
