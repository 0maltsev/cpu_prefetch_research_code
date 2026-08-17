# Configuration

This directory contains versioned, non-local configuration inputs. Stage 3 adds
the dependency/license inventory. Stage 4 uses the unmodified imported schemas
directly and therefore adds no compatibility schemas here. Stage 5 adds exactly
two machine-checked `queue-provenance/` records; they bind independently
authored implementation files by SHA-256 and explicitly retain the missing
LLVM-disassembler blocker. Future
implementation-owned schemas may enter `config/schemas/` only with a documented
relationship to the imported logical contract and an accepted compatibility
decision.

The typed loader has no implicit platform values or missing-field fallback.
Experiment plans and stand-specific values do not belong here until their
lifecycle decisions and evidence exist.

`local/` is ignored for operator-specific configuration. A local file is never
evidence of requested or verified stand state.
