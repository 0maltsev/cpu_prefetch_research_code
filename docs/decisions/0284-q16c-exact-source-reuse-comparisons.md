# D284: exact comparisons in the Q16c source-reuse guard

Engineering repair of the D282 constructor failure. Scientific inputs, native
release7fb8944, original signatures/source bank and all acceptance criteria stay
unchanged. This decision grants no experiment, retry or additional window.

The guard passed dependency sets and raw file bytes to `admission.same`, which
accepts JSON values only. Identical closures raised TypeError before comparison;
identical source bytes would raise the same error after that first defect.

Use exact set equality for the complete discovered Python dependency closure,
and exact byte equality for each member plus all three required schemas. Route
inequality through the existing AdmissionError boundary. Keep the shared JSON
comparison helper unchanged. Do not stringify values, compare only lengths,
ignore extra dependencies or skip a file. Existing producer/current release,
empty-attempt, signature and retained-file checks remain in force.

Seven new qualified-context regression tests execute `inspect` with real bundle
files and real transitive discovery. Only the stand-specific signed-document
reader and signature boundary use test doubles. Check matching inputs, added or
removed dependency membership, changed Python bytes, every schema, absent files
and incorrectly relabelled current qualification. These tests expose the original
set defect; reverting only the byte fix independently exposes the second defect.
All41 affected source-reuse/integration/policy62/qualification tests pass locally.

Complete verification also requires a bounded, read-only check using the actual
completed stand qualification, real original signatures and hashes for all360
original sources. Stage repaired administrative bytes separately; never overwrite
the frozen failed packet or qualified native bundle. Preserve any software-check
failure evidence. No sanitizer/native rebuild is needed for this Python-only
comparison repair; previously qualified C++ bytes remain frozen.

A repaired guard alone does not resume the stopped D282 campaign. Preserve passed
clocks/Q15 and all708 Q16a/120 Q16b results. Original absolute deadlines remain
unchanged, Q16c remains0/180, and Stage18 is prohibited.
