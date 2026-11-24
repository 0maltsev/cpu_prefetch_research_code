# D322: scoped journal mechanism verified; actual fact producers remain

Ordered signed S180 EXT008–010 can now be persisted and independently replayed
without changing the original seven resolutions or granting generic readiness.
The journal requires a caller-qualified semantic provider for actual EXT008/009
facts. Those production providers, the executable parent and qualified profile
are still pending. This report does not record actual pilot input admission.

[D322](../../../decisions/0322-s180-signed-scoped-input-journal.md) defines the
trust boundary, durable publication and historical/current verification split.

## Verified behavior

- Fifteen tests pass against the unchanged clean34247ce worker's real cold
  layout interface. They use actual temporary SSH keys, SSHSIG verification,
  filesystem writes, advisory locks and injected publication interruptions.
- The tests preserve the original seven resolutions, reject boolean or
  self-asserted semantic results, wrong signer/namespace/bytes, wrong order,
  foreign anchor/policy, fixture promotion, future/regressed timestamps and
  context substitution. They detect modified records/signatures/snapshots,
  in-flight mutation, changed inventory, lock/directory inode replacement,
  metadata deadline/read-limit violations and non-object payloads.
- An interrupted publication retains its exact partial record and blocks
  subsequent replay, append and adoption. No failed evidence is deleted.
- Historical signature replay works after expiry but returns no native request
  or launch permission. Current replay rejects expiry. All journal views retain
  `pilot_ready=false`, `execution_authority=false`, `phase18_authority=false`.
- The actual legacy policy65 verifier still rejects descriptive EXT007 as a
  basis for legacy pilot EXT008, EXT009 and EXT010, even after the separate
  scoped test journal contains all three signed records.
- The authenticated-base adapter's closed-locator/actual-UTC/non-synthetic
  argument contract passes. Its original replay call is mocked in that test;
  this is not fresh replay/admission of actual stand evidence.
- Five related registered CTest suites pass, covering 45 cases: journal15,
  authority12, reservation8, checkpoint5 and archive-channel5. They run with
  authorized local IPC outside the managed boundary. The separate original
  twelve-case authority regression also passes.
- Format, immutable protocol integrity, schema fixtures, canonical encoding,
  queue provenance, runner schemas and qualification schemas all pass.

Semantic facts and base replay views are explicitly synthetic in these tests.
The library's required callback is not a substitute for implementing and
qualifying the real source/platform/qualification/resource verifiers. There is
no permissive default, input-selected verifier or production fixture selector.
The semantic-policy fingerprint binds an identity; it cannot prove correctness.

## Observed failures and corrections

The first ten cases passed. Later adapter negative coverage rejected forbidden
arguments as intended, but expected `JournalError` instead of the actual
`AuthorityError`; the expectation now matches that boundary. The fourteen-case
suite then passed. Review added a held-lock inode check and a fifteenth case.
Its non-object payload initially hit the canonical parser's `ArchiveError`
before the intended explicit input guard; the guard now precedes parsing. The
initial direct and registered failures remain retained, followed by passing
final direct/registered results. No experiment failed or was retried.

## Preserved release and research state

No C++ or immutable protocol source changed. The6151832-byte worker still has
SHA256 `7460102040fb9685af75131e6810494960b149fcf82d95d776347e4379d8f0fc`,
with clean source34247ce. D320's native codegen and previous sanitizer evidence
remain applicable to those exact native bytes; native checks were not repeated
for Python-only metadata changes. `native-preservation.json` records the fresh
byte/source check. No empirical claim follows from these software tests.

No stand access, directory reservation, schedule preparation, qualification,
capture, raw transfer or operational window occurred. Completed Q16a708,
Q16b120 and Q16c180 remain preserved. There is no new whole-pilot ETA.
Temporary fixture keys/files were cleaned by their test owners; only bounded
reports/manifests are retained on this PC, with no new research raw data.

Step3 remains in progress: actual semantic fact producers, parent attempt/
archive lifecycle and qualified S180 profile are required. Then bind actual
inputs and the complete recovery/resource/time budget, provide the total ETA,
qualify and conditionally execute the single approved S180 family. Stage17 is
not complete and Stage18 execution remains outside scope.

`manifest.json` binds the changed implementation, decision and evidence files.
Copied logs strip trailing horizontal whitespace/surplus EOF newlines; original
byte counts/digests for altered copies are in `log-normalization.json`.
