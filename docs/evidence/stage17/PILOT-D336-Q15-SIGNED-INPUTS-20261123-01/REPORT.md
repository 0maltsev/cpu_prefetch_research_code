# S180 Q15 signed-input checkpoint

The separately scoped Q15-R/W signed-input boundary is implemented under
[D336](../../../decisions/0336-s180-scoped-q15-signed-inputs.md). It preserves the
original EXT003 runtime and all seven resolutions while binding the current
frozen worker to a separately qualified S180 profile leaf. **No stand access,
qualification, source generation, measurement or operational window started in
this step.** Completed calibration and native34247ce remain unchanged.

Actual SSHSIG verification uses only admitted original EXT002/003 owner trust.
Each authorization must match independently supplied qualification context,
original stand/seven-input ancestry and descriptive scope. R binds observed
probe geometry; W requires its own signature over R lineage, the same session
and all original CPU0/1/8 prestate values. Original qualification start/deadline,
boot/window, protected output identity and current native/profile bindings cannot
be selected or reset by the signed document. No command/backend/trust-root or
pilot/Stage18 permission is accepted.

Verified immutable bytes produce the existing native request/4 and context/4.
The native request retains the original JSON-plus-LF carrier while the new
authorization remains exact JCS-I64. Both actual byte hashes are bound in the
context, avoiding a hash cycle. The new schema and compiled schemas are validated
independently. The source-profile leaf in the native release carrier is explicitly
separate from the original EXT003 resolution and is not itself a new journal
admission. Profile/platform/raw evidence still require independent qualification.

All43 cases in3 registered suites pass in16.53 seconds:12 existing pilot-authority,
15 signed-journal and16 new Q15 cases. All16 new cases also pass Python development
and debug allocation in0.947 seconds. Temporary keys/signatures are real; base
journal/platform/root/profile data are explicitly synthetic software fixtures.
The tests neither establish live facts nor produce hardware eligibility. They
also prove legacy runtime selection still returns its original executable after
the new verifier runs, and that R signatures cannot cross to W.

Retained regressions identify and correct missing owner/mode fields required by
the compiled request schema, an omitted local schema reference and the native
request newline mismatch with the original result validator. Before the last
fix, that validator would reject an otherwise valid native result hash. Original
schemas and serializers are preserved; neither failure consumed a stand attempt.

Format, protocol/schema fixtures, canonical/provenance and runner/qualification
checks pass. The new authorization schema is the only added config schema;
immutable protocol and production C++ are unchanged. AST and whitespace checks
pass. Existing native sanitizer/codegen evidence is not rerun or relabeled for
this Python/schema-only change. `verification.json` records fresh results and
exact unchanged native/core/legacy-file identities. The CTest snapshot preserves
content with only final blank lines normalized.

This closes the signed-input prerequisite, not persistent Q15 execution or
EXT008. The qualified parent must derive live facts, authenticate the profile,
pin actual filesystem/runtime identities, reverify signatures before use,
consume durable attempts, own one persistent process/buffer, validate raw output,
enforce deadlines and prove restoration. Actual R/W collection, complete EXT008,
outer operator/profile, scientific pilot validator and actual admission/ETA remain
pending. Stage17 remains incomplete; Stage18 execution stays deferred.
