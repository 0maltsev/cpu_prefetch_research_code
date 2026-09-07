# Offline analysis boundary

Offline analysis is the separate plane defined by ADR-0001. Stage 15 implements
the synthetic known-answer pipeline in `cpu_prefetch_analysis`; the normative
contract and commands are in [`docs/ANALYSIS.md`](../docs/ANALYSIS.md).

Analysis consumes only immutable checksum-valid artifacts after the applicable
Stage 12 reconciliation and Stage 14 access/block gates. It never runs in the
timed process, controls the scientific measurement loop, or reports synthetic
fixtures as empirical evidence.
