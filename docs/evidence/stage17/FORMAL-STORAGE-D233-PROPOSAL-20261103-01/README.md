# Future formal storage proposal evidence

D233 was **ACCEPTED** by the owner; implementation and qualification remain required. The owner reports no additional storage
and asks for a smaller EXT007 budget. [Exact proposal](proposal.md) preserves all
canonical observations and proposes a shared 6 TB physical archive ceiling,
512 GiB workspace, 256 GiB analysis scratch and 16 GiB reserve. It can stop with
an incomplete family; sample ratios do not guarantee full-study fit.

Two read-only stand jobs passed 96 lossless round trips each. Plain Zstandard
sampled 48 files across 12 contexts. The reversible column/delta prototype
sampled 48 blocks from 24 primary files: 45,613,056 original bytes became
6,733,910 bytes at level 3 (6,514,819 at level 9). Every reconstructed sample
matched its original bytes. All original files remained unchanged. Discovery
demand uses a different format from formal D214 demand; its observed compression
ratio is not a formal-demand estimate.

The scripts and original JSONL reports contain only size/hash/provenance data;
no raw observations were transferred to this PC. They establish no archive
custody or scientific performance result. Production codec, crash/recovery,
quota enforcement, dependency provenance and qualified-release integration
remain required after explicit policy acceptance. Historical raw stays intact.

The inventory binds the exact proposed bytes and both sample jobs. No signature,
experimental invocation or historical deletion authority is created by these sample reports.

[Recorded explicit acceptance](owner-acceptance.json) binds the original proposal.
