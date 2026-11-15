# D247: Reuse the verified D246 composition at downstream admission

- Status: ACCEPTED engineering integration under D240/D245/D246
- Date: 2026-11-15
- Scope: the exact completed 177+531 Q16a composition; no new experiment
- Scientific estimator, observation minimum and immutable protocol: unchanged

Controller26 requires one source revision in a legacy Q16a record. The accepted
D240 continuation necessarily has two revisions and two source plans. Projecting
that composition into the legacy schema would erase its actual history.

`stage17_q16a_handoff_v1` accepts a new explicit handoff schema containing exact
physical bindings for D246's completed composition, native geometry proof and
completion record. Their independently authenticated and reviewed originals are
retained in `Q16A-COMPOSITION-ACTUAL-20261115-01`. This gate pins their exact sizes
and hashes in code; plan-supplied hashes or success flags cannot substitute for
the already completed D246 producer, signature, custody and geometry checks.
It supports this completed incident only, not arbitrary future attestations.

The composition is 629535 bytes, SHA256
`3c84e5436cedf2e513b28be3f7dc44fa6f44afc3632a728eb3b82d66be89192f`.
Geometry is 4329 bytes, SHA256
`9076992ec8d993a314fd7d8b8134b7642e1127b1bfe730001bf1c663e7d76e87`.
Completion is 1030 bytes, SHA256
`954c13f435573b33ddb9ec144e0111c4a29a7e0da62e2df622f5ad2fe419f906`.
Exact durable copies may have different physical locators; their original
internal locators remain unchanged. Bounded regular-file, symlink, hash and race
checks apply to every read.

The consumer checks the current authenticated EXT006 source/inventory/bundle
and EXT004 platform against the accepted geometry provenance. It checks stand,
discovery duration and minimum, all 708 valid summaries and 1416 unique original
run identities, and recomputes the unchanged exact estimator. The return value
is the original composite calibration with both source histories, FULL outcomes,
and all conservative authority/authentication flags preserved.

Controller27 uses private function-global rebinding, following controller26's
existing pattern. Only an explicit handoff used as the Q16a prerequisite takes
the new path. Later ring geometry and R2 distances must match its exact result;
R2 evidence identity binds the whole handoff in the prospective signed request.
Legacy calibration validation remains strict. Existing plan, discovery,
hardware, namespace, signature, journal, UTC deadline and qualified archive
profile gates remain required. The qualified worker and native source are
unchanged; deployment must use a separately bound administrative packet rather
than modifying the qualified bundle or claiming that packet was qualified.

This closes the Q16a prerequisite representation gap only. It does not satisfy
Q16b/Q16c collection, their independent validation, calibration freeze, EXT007
exit admission, pilot readiness, or Stage18 access. No raw decoding, capture,
qualification, isolation reapplication or prior experimental retry follows
from evaluating this handoff.
