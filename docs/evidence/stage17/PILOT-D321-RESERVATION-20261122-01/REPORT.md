# D321: remove the output-inode/resource-admission cycle

The parent can now obtain the real S180 output-directory identity before EXT009
exists. It reserves one exclusive directory and original FAMILY/metadata records
without capture permission. Only after actual scoped admission may the caller
bind EXT009 in a separate immutable receipt and prepare a capture on that inode.
No placeholder digest, orphan adoption, overwritten record or new quota is used.

[D321 decision](../../../decisions/0321-s180-directory-before-resource-admission.md)
describes the new storage-extension/2 route and its preserved boundaries.

The original81c4838 store required EXT009 before directory creation; D319 required
that directory's device/inode in both EXT008 and EXT009. The retained original
constructor reproduction rejects an explicit unknown EXT009. The new order is:

1. Freeze the exact plan and reserve its real directory with no EXT009 value.
2. Admit scoped EXT008/009 using that actual original inode and all other gates.
3. Record the actual EXT009 binding once; keep the reservation byte-identical.
4. Author/verify EXT010 and consume the attempt before the eventual native launch.

Only step1/storage binding mechanisms are implemented here, with a real crypto
integration across this order. The actual scoped semantic producers/journal and
operational launcher are still required. Hashes or synthetic replay views do not
supply their missing proof. No actual EXT008/009/010 was issued by this work.

## Fresh verification

- Eight actual filesystem cases pass: pre-admission inode identity/capture stop,
 exact one-time binding, historical replay, unchanged quota/scope/old ledger,
 no second family/adoption, wrong/partial/missing admission, inode replacement,
 pre-admission data and unsafe directory mode.
- Twelve actual SSHSIG authority/contract cases pass, including reservation,
 EXT009 binding and then signed request construction using the same real inode.
 The replay views and temporary test keys remain explicitly software fixtures.
- Eighteen combined actual sealed broker/codec/native-channel cases pass across
 the existing extension/1 route and new reserved extension/2 route. They retain
 complete inverse byte/hash checks and failed/partial/discrepant evidence stops.
- One additional targeted actual-broker case verifies changed EXT009 admission
 evidence is rejected after archival. It prepares a valid scope before mutation
 and asserts the specific admission-mismatch error from retained custody checks.
- Eleven related registered CTest entries pass. They cover reservation, authority,
 channel/checkpoint and existing custody/runtime/broker/jobs/registry behavior;
 the separately verified18+1 S180 broker cases are not repeated in that run.
- Format, immutable protocol/schema fixtures, canonical bytes, provenance, runner
 and qualification schema gates pass; final Python AST and whitespace checks pass.

The initial fixture attempted to use /tmp's small tmpfs. D233 correctly rejected
its free capacity against the16GiB failure reserve before exercising the new
route. The corrected fixture uses the real workspace filesystem. No capacity
was mocked and no production reserve was lowered. Initial errors remain visible.
The early corrected direct log has7 cases; the final registered/direct suite has8.

The existing D233 base store, ledger kinds, original scope and historical records
are unchanged. Both S180 extension versions remain usable through their explicit
admission paths. New metadata remains charged to the existing shared6TB quota.
Every interrupted/orphan object remains a stop requiring explicit recovery.

## Native/data/authority boundaries

There are no C++ or immutable protocol changes. The clean34247ce native worker
still has SHA256`7460102040fb9685af75131e6810494960b149fcf82d95d776347e4379d8f0fc`
and6151832bytes; D320 codegen and prior native sanitizer evidence remain preserved.
No native rebuild, qualification, calibration, empirical measurement or completed
raw validation was repeated for these Python-only changes.

A fresh qualified administrative source closure must explicitly include the new
module/updated S180 store before real use. Existing sealed profiles are not
silently updated. This step performs no stand access, directory reservation,
schedule preparation, experimental run or operational-window start on the stand.
No raw data was transferred to this PC. Temporary fixtures and test keys are gone.

Step3 remains incomplete: connect qualified scoped semantic/journal admission,
parent/profile and durable attempt/sealed dispatch/archive orchestration. Then
bind actual original sources/namespaces and the complete time/storage/recovery
budget, admit EXT008–010, qualify the frozen native release once, and conditionally
run/validate the single180-capture family with restoration and scoped exit.
Stage17 is incomplete; Stage18 remains deferred.
