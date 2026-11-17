# D274: pure sizing of retained original Q16c sources

Status: accepted engineering decision, 2026-11-17. Implements D270–D273;
changes no scientific method, native executable, measurement count or deadline.

The standalone native layout query consumes the same sealed original-source
loader as frozen release919c486. Its caller must budget both owned decoded
vectors, the largest simultaneous decode copy and an8192-byte I/O block:
`sum(source_bytes) + max(source_bytes) + 8192`. A declaration of only the sum
correctly fails the native transient-allocation guard. The production D271
worker already includes its decode allowance; this decision fixes only the
new software-sizing caller. The native guard and qualified limits stay fixed.

`prepare_stage17_q16c_resources_v1.py` pins each exact original pair into
distinct sealed, read-only descriptors, checks size/hash and stable file
identity, invokes the pure query with the frozen bundle's runtime libraries,
then assembles all180 actual layouts. Its output grants no execution authority.
Historical requested hardware prestate is explicitly software input; current
hardware verification and authenticated admission remain separate requirements.
The archive-profile hash in the preview remains provisional until the final
accepted optimized profile is bound before signing.

The initial launcher lacked the qualified Python module path. The next caller
omitted the transient decode allowance and was rejected before its first layout
answer. Both failed cold-job receipts stay on the stand. The corrected job
completed all180 layouts in158.956seconds. No native qualification, performance
capture, schedule regeneration or completed Q16a/Q16b validation was repeated.

Real descriptor/hash/failure-cleanup tests and the actual native query regression
pass, including rejection of the old budget, altered layout and incorrect hash.
The same query integration passes ASan/UBSan. Completed source and sizing
bindings, trust-rooted signature verification and remaining gates are retained
in [the evidence report](../evidence/stage17/Q16C-D274-SOURCE-SIZING-20261117-01/REPORT.md).
