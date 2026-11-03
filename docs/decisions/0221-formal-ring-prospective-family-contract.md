# ADR-0221: Prospective D212 family and finite resource accounting

- Status: `ACCEPTED` — engineering implementation of accepted D037/D206/D212
- Date: 2026-11-03
- Scope: prospective Q16a plan validation; no numerical plan selected
- Execution authority: none

Introduce `cpu-prefetch-stage17-formal-ring-plan/1`, with explicit native
capture/resource/monitoring inputs under D217. It prospectively enumerates
every repetition in the twelve hardware/placement/working-set contexts,
with at least 59 runs per context, one common positive measurement duration,
and one explicit minimum observation count per eligible series. Contexts are
ordered H0 then H1, NEAR then FAR, and L2/LLC/beyond-LLC; repetitions remain in
their frozen order. No omitted, repeated or appended run can repair a failed
formal family. This contract selects no duration, count or empirical limit.

Warmup and measurement use distinct reserved namespaces, globally unique run
IDs, seed IDs and seed values. The existing persistent-arena seed rule applies.
The twelve context factor labels must match the actual input geometry; near/far
worker numbers come from explicit qualified input rather than a hardcoded CPU.
Geometry remains identical across H0/H1 for each placement/working-set class;
each context's resource and monitoring bounds remain identical across its
prospective repetitions. These are independent calibration runs. They preserve
the same workers and mappings across each warmup/reset/measurement sequence,
without claiming persistent mappings across a paired temporal block.

Compute the exact maximum of all eight retained raw stream extents from their
prospective row capacities and original codecs: the eight-byte-rounded
four-byte length plus UTF-8 run ID prefix, followed by 15 producer, 10 consumer
or 9 demand u64 words. This includes warmup and drain evidence. The largest
single raw file is a necessary lower bound on cold publication-copy memory.
The native binary still recomputes its actual object and mapping layout.

Each capture declares setup, publication, cleanup, watchdog, publication memory,
other process memory, total process memory, metadata output and total output
ceilings. Its watchdog covers setup, the five-second warmup, measurement, both
bounded drains, publication and cleanup. Its process ceiling covers declared
native mappings plus publication and other runtime memory. Its output ceiling
covers all possible original raw bytes plus metadata. Checked u64 arithmetic
rejects overflow rather than wrapping. A family watchdog covers family setup,
every capture watchdog and cleanup; sequential peak memory adds controller
memory to the largest capture ceiling. Required disk space adds complete-family
output, analysis scratch and a separately declared reserve under D206's one
authoritative uncompressed stand-copy policy.

These checks establish consistency of declarations, not that arbitrary heap,
metadata, analysis-scratch or watchdog estimates are adequate. The concrete
resource proof must additionally bound actual native/publication/runtime
extents, JSON storage and qualification overhead, check fresh free resources,
and apply independently verified process limits. The admission layer must bind
the clean qualified release, valid discovery selection, seed reservation,
resource and monitoring proofs, all prerequisite resolutions, current stand
identity and explicit phase authority. No synthetic plan establishes them.

Verification uses a full 708-capture software fixture, exact independent raw
byte arithmetic, coverage/order and identity mutants, forbidden outcome-based
inputs, duration/bound changes, missing raw-copy memory, omitted drain or
publication time, insufficient disk reserve, bool/integer confusion and u64
overflow. Tests use software-only values and cannot supply a formal parameter.
