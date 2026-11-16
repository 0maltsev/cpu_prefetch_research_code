# D259: Read-only analysis inputs from a completed capture with interrupted custody

- Status: ACCEPTED for the owner's instruction to continue retained Q16b recovery
- Date: 2026-11-16
- Scope: offline evidence inspection; no new measurements or scientific estimator

The E26 Q16b stop retained 17 native-complete checkpoints. Captures 0–15
have complete custody receipts. At ordinal 16, all six archives are already
published: five sources are RELEASED; the control source is PUBLISHED and its
uncompressed original remains. The final custody receipt is absent. Preserve
the original failure and every archive, checkpoint and ledger transition.

Permit a separate read-only inspector to establish which published artifacts
are eligible inputs to independent offline validation. Authenticate the
original signed plan/release outside this boundary. Within it, check original
family device/inode, pending checkpoint, its exact original and retained bytes,
durable CHECKPOINT registration, complete ordered sources, native cleanup,
current PUBLISHED/RELEASED ledger states, original logical bindings, phase/run/
worker/role/header identity and actual physical archive bytes. Missing,
unpublished or corrupted artifacts reject inspection. Existing historical
whole-family and completed-custody admission remain unchanged.

The inspector returns custody_complete=false, family_completion_established=false,
inverse_readback_performed=false and scientific_validity=NOT_ASSESSED. It does
not write the ledger, release originals, synthesize a receipt, reconstruct raw
bytes, or establish experimental validity. The unchanged scientific validator
must independently reconstruct and hash every raw artifact before producing a
capture report. Inspecting a stopped native-complete capture does not turn the
failed family into a successful execution.

No continuation method, additional attempt, deadline extension, selected
replacement, fresh qualification or Stage18 authority is supplied here. Any
reuse/composition and post-exit custody completion require their own explicit
boundaries. Software tests use real small archives and durable interrupted
custody states, including reopening the store with no live worker context.
