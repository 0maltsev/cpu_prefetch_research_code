D284 repairs both exact-comparison defects in the administrative source-reuse
guard. Local commit97b8c7451c14ccd7d7380524677d7fd1cc9daad4. Dependency
sets and raw file bytes now use direct exact equality through the existing
AdmissionError boundary. The shared JSON canonicalization helper is unchanged.
No scientific input or accepted comparison requirement changed.

Verification completed:

- Seven new qualified-context regressions expose the original set failure.
  They cover matching inputs, added/removed transitive dependencies, changed
  Python bytes, all three schemas, missing files and incorrectly relabelled
  current qualification. Existing source/plan/window protections stay in place.
- Restoring only the old byte comparison makes the matching-case test fail with
  the expected bytes TypeError, independently detecting the second defect.
- All41 targeted source-reuse/integration/policy62/qualification tests PASS,
 21.301s. `git diff --check` PASS. Python-only repair: native/sanitizer/codegen
  builds were not repeated; frozen qualified7fb8944 executable is unchanged.
- A complete35-member administrative packet was staged separately on the stand.
  Its manifest SHA256 is34d5c84227e6386c19f10a47b439b73560fbb95971cc201ed0d326e8d56cb34f.
  The original failed packet and all of its bindings remain unchanged.
- Actual completed qualification and original empty-attempt/signature checks,
  generator/schema closure and all360 original source hashes passed in60.726s.
  Original source extent7216896152bytes and producer919c486 remain unchanged.
- The exact failed constructor validation call was then reconstructed from its
  retained inputs, including Q16a/Q16b histories, existing compatibility proofs,
  original signed D282 window, namespaces and Q15 hardware metadata. It passed
  at2026-11-18T10:52:57UTC in97.903s under the actual UID1000, current six admitted
  resolutions and repaired complete17-module packet. Its unit exited0, reaped.
  No signed-document or signature mocks were used in either stand check.

The first standalone software-check setup omitted a retained helper and stopped
at import, before qualification validation. Its failure log is preserved.
The complete hash-verified cold packet supplied the correct dependency closure.
These were software checks, not attempts to qualify or collect another experiment.

The full validation call is verified; constructor output publication, signing,
registration and live collection were not performed by this check. No experiment,
source generation, qualification, isolation or new window was started. Original
ledger66472 is unchanged, source bank remains immutable, and the passed clocks/
Q15 plus Q16a708/Q16b120 are preserved. Q16c remains0/180 and the D282 campaign is
stopped/restored. The old completion ETA stays withdrawn and the signed deadline
is unchanged. This software repair grants no automatic retry or Stage18 authority.
