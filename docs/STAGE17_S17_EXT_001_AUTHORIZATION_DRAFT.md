# S17-EXT-001 read-only preflight authorization draft

The machine-readable
[`STAGE17-S17-EXT-001-READ-ONLY-PREFLIGHT-AUTHORIZATION-DRAFT-v1`](../config/stage17/stage17-s17-ext-001-read-only-preflight-authorization-draft-v1.json)
is the only current authorization draft. It is deliberately invalid as issued
evidence: every owner-supplied value is `null`, `status` is
`DRAFT_NOT_ISSUED_OWNER_INPUT_REQUIRED`, and it grants no authority.

The owner must provide all of these real values in one prospective action:

- a unique authorization ID and the acting owner identity;
- exact issue and expiry UTC timestamps;
- the exact target-scope ID;
- finite `max_commands` and `max_wall_seconds` limits;
- the stand ID, SSH target, and SHA-256 of the pinned host-key evidence;
- absolute locators for the exact pilot-candidate archive and sidecar bytes;
- for each of the six frozen read-only observations, the executable path and
  SHA-256, exact argv, and create-exclusive output locator.

The fixed portions cannot be broadened: one attempt per observation, zero
retries, stop on the first mismatch or nonzero exit, retain every partial
artifact, no stand mutation, no privileged control, no calibration, no pilot
execution, and no Stage 18 authority. The pilot owner explicitly also acts as
operator, custodian, and auditor; independent review is not claimed.

After the values exist, the supporting observation contract must be written as
a new repository file and hashed. The nested `authorization_payload` is then
written separately, validated against
`stage17-operational-authorization-evidence-v1.schema.json`, and referenced by
one new append-only `S17-EXT-001` resolution. Only after the validator reads
those real files and the next journal snapshot from disk may the first state
transition be constructed. The draft itself can never be referenced as
evidence.
