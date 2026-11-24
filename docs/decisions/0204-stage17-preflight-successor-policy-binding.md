# ADR-0204: Bind the current preflight entry point to its qualified policy

- Status: `IMPLEMENTED_VERIFIED_LOCAL_NO_EXECUTION_AUTHORITY`
- Decision ID: D-204
- Scope: required EXT007 release/preflight compatibility; no scientific change
- Predecessor: clean source `2ff7667`, operational policy 55, preflight policy 29

The clean D-202/D-203 release passes its seven generated-code gates and package
verification locally and on the stand. Its fresh v5-16 journal contains only
genesis. Before authoring or executing qualification, an independent local
reproduction found that importing preflight executor 29 changes the shared
journal implementation's semantic verifier from policy 55 to policy 47.
Genesis replay then rejects current hardware-prefetch schema bindings. The
executor's older import chain installs its historical semantic module after
the current CLI has installed the current one. A passing current CLI status
therefore does not establish that the separately invoked executor is usable.

Preserve the deployed release, policy 55, preflight policy 29 and earlier
records. Add versioned preflight and operational successors that explicitly
bind the actual execution body, journal, semantic verifier and source identity
to the same current policy. Bind the full entry-point import closure in the
new release. Preserve the old entry points for their historical fixtures.
Do not replace old hashes, relax byte checks or patch a deployed wrapper.

The regression must exercise the actual CLI/executor import boundary in fresh
processes and verify current policy bindings, including a rejection when an
obsolete semantic binding is substituted. Check the new package's isolated
runtime and its current qualification/diagnostic entry points before deployment.
The full local regression now passes CLI authoring, journal admission and
transition into prospective executor readiness in fresh process orders,
including historical executor and Q15-session imports. Expiry and changed-source
mutants reject, with zero transport calls and no attempt marker.

Native measurement code is unchanged; preserve its existing verification and
repeat the clean-release generated-code gates for the new source identity.

The successor changes no experiment, duration, count requirement, treatment,
queue, timing boundary, retention policy or accepted authority. A fresh stand
qualification and exact finite phase authority remain necessary. No capture
or empirical result follows from this compatibility repair.

The same readiness review found that valid full-footprint residency records
can exceed the independent validator's generic resident JSON node/text limits.
Keep the existing JSON artifact format and every recorded page address/status.
Parse those two numeric arrays into explicitly bounded packed storage, reject
noninteger or out-of-range entries, and preserve exact order/count/value checks.
Do not raise unrelated JSON limits or omit observations. Verify the largest
planned geometry within measured local memory before admitting the study.
This fixes an implementation limit; it changes no control validity criterion.

Verification: the full CLI/admission/executor regression passes, with five
release compatibility cases and the old-path failure reproduced separately.
Six focused packed-metadata cases, twelve retained-study cases and five C++
publisher/validator bridge cases pass. An explicit largest-geometry test parses
and checks all 31,944,212 numeric values: packed capacity 260,308,992 bytes,
peak RSS 298,307,584 bytes, with unchanged generic metadata limits. Formatting,
protocol/schema integrity, schema fixtures and canonical fixtures pass.

The reproduced preflight failure is retained in
`build/ext007-runtime-20261101/preflight-policy55-regression.log`; final checks
are in `d204-preflight-successor.log`, `d204-integrated-checks.log` and
`discovery-metadata-validation.log` in the same directory. These software checks
are distinct from the clean replacement release and stand qualification.
No live attempt or capture was performed.
