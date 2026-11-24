# ADR-0186: Separate D-100 proposal self-test from external archive integration

- Status: `ACCEPTED`
- Date: 2026-11-02
- Decision ID: D-186
- Protocol version: `2.0.0-pre.3`, unchanged
- Scope: local verification; no scientific or action authority

The D-100 proposal checker is registered as a synthetic CTest but reads an
external historical build archive and sidecar implicitly. The existing
`Q15-QUALIFICATION-ARCHIVE-EXTERNAL-CONTRACT-v1` already states that external
bytes are required for integration/actions and must never be read by a
self-test. Its exact hash remains authoritative; the local reconstruction
does not match it and must not be accepted.

Add an explicit `--self-test` mode to the proposal checker and use it only
for that synthetic CTest. It validates the unchanged proposal schema,
decisions, bounds, authority, six tracked predecessor inputs, D-099 evidence,
and exact archive/sidecar/collector identity metadata against the schema-checked
external contract. It reads no external archive or sidecar bytes and reports
`external_archive=NOT_ACCESSED`. Retain all twelve existing negative cases
and add seven external-identity mutants. Test that the hermetic mode cannot
call the external validator or sidecar hash reader.

The default checker and its existing CMake integration target still require
the actual exact archive and sidecar and must fail when they are missing or
different. Keep the independent explicit-path archive integration validator
unchanged. Verify this failure remains observable. No required integration
test or action-input gate may be replaced by a self-test PASS.

The D099–D108 preserved inputs, accepted contracts, historical archive hash,
and reconstruction bytes remain unchanged. A passing full synthetic CTest
suite does not qualify a current policy/release, repair stand access, or admit
an external input. The missing historical archive remains unresolved for
its separate legacy integration/action boundary.

Verification: nineteen proposal mutants and both boundary cases pass. The
default checker still returns exit 1 for the missing exact archive/sidecar.
After integration, all 410 Clang/libc++ CTest entries pass in the isolated
accepted glibc 2.43 runtime. No external archive validation or action occurred.
