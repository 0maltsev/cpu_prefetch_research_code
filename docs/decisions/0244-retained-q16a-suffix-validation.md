# D244: Validate the completed Q16a suffix against retained evidence

- Status: ACCEPTED engineering implementation of the owner's “continue with next steps”, 2026-11-13
- Scope: D240's collected E25 family only
- Scientific method and immutable protocol: unchanged

All 531 continuation captures have native-complete and archive-custody receipts.
The executor completed with exit 0, restored hardware, reaped workers and no
quarantine. The external supervisor's reporting function incorrectly expects
`requested_hex` in completion/6 readbacks. The qualified executor, schema and
CLI18 retention checks use `expected_hex`. Preserve the supervisor's original
failed verdict; validate original completion and restoration through the
qualified signed-lifecycle semantics, producing separate evidence. This neither
repeats the collection nor changes an original receipt.

Use a separately bound offline operator for the exact collected plan
`91c83558b5c5d891cabdd4d875da1292120df5940397298063d55c901a8866c2`.
Verify the original authorization/signature/request/attempt/result/completion,
historical journal 000009 and D242 adapter bytes. Reuse the qualified archival
registry's metadata verification, then reconstruct each capture through the
independent inverse and run the existing Q16a raw validator. Reuse the unchanged
D241 reader capacity derived from each signed capture's residency geometry.

The offline operator uses four workers, 8 GiB address space per capture,
2 GiB each for supervisor/coordinator, 36 GiB aggregate plus 8 GiB admission
reserve, and a finite 72-hour analysis timeout. Per-capture reconstruction uses
the signed analysis workspace bound. Four such workspaces plus 2 GiB metadata
and 256 MiB filesystem allowance must fit the existing 256 GiB scratch ceiling;
the existing D234 supervisor monitors aggregate scratch and a 16 GiB disk
reserve, kills/reaps its own analysis processes on failure and preserves reports.
These are offline software resource limits, not experimental limits.

Fresh analysis outputs are outside the archive program and qualified admission
repository. Archives, ledger, request, failed evidence and original 177 reports
remain unchanged. A suffix manifest requires all 531 ordered raw-validation
reports, original identities and a stable ledger. No calibration evaluator is
called: suffix-only evidence cannot establish family validity or EXT007 credit.

Authenticated 177+531 composition, calibration and formal admission remain
separate work under D240. No fabricated 708-capture native result, relabeling,
new capture, retry, qualification repeat or Stage18 authority follows here.

Verification includes exact collected population and all signed reader bounds,
rejection of changed identity/configuration/authority/resource inputs, complete
historical signed-lifecycle preparation, and actual stand execution of the
bounded offline operator. Software checks do not imply scientific validity.
