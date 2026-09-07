# Stage 8 Clock-Decision Capability Evidence — 2026-08-20

Status: **capability/configuration evidence only**. This publication does not
accept D-009, qualify a clock, select producer/consumer placement, authorize
Stage 8 implementation, or report a performance experiment.

## Collection identity and scope

- Protocol: `2.0.0-pre.1`.
- Collection UTC: `2026-08-20T18:29:48Z`.
- Platform observed after collector-package provisioning: bare-metal Ubuntu
  26.04, Linux `7.0.0-27-generic`, `amd64`.
- Inventory scope: every CPU reported online and available to the collector,
  `0-103` (104 logical CPUs). This is an inventory scope, not a frozen worker
  placement.
- Repository base revision recorded by the collector:
  `fe2a49db32c07663a22a24fb79b8000fd58d6a30` on `f/phase-7`.
- The recorded checkout was intentionally dirty only for the transferred
  collector and its documentation; the exact collector is embedded in the
  archive and is published in this commit.
- Collection ran under the explicitly authorized root platform account. It was
  read-only with respect to platform controls and performed no measurement.
  This does not satisfy the later requirement to prove an unprivileged measured
  process.

## Published artifacts

- [Evidence archive](stage8-clock-evidence-20260820T182948Z.tar.gz)
- [Archive SHA-256](stage8-clock-evidence-20260820T182948Z.tar.gz.sha256)
- [Collector run log](stage8-clock-evidence-20260820T182948Z.run.txt)

Archive SHA-256:
`209aa2ea45b73cfe0ea12a62f0ac060692070d5babe8c60d1095ea9eb2991aca`.
The archive contains its own `SHA256SUMS` covering all 480 internal files.

## Verification and limitations

- Independent local and stand-side archive checks passed.
- All 18 imported artifact sizes, hashes, and inventory entries matched; all
  four current authoritative protocol hashes matched.
- Publication checks found no machine/boot ID file, UUID-shaped identifier,
  credential signature, private key, GitHub token, serial-number path, or
  internal checksum failure.
- `/proc/cmdline` identity-bearing boot, storage, and network values are
  redacted. Its original bytes are bound only by SHA-256; timing-relevant flags
  remain visible.
- The collection reports zero critical issues, 318 warnings, and nine
  informational gaps. Of the warnings, 316 are denied reads of sysfs control
  files (`autosuspend_delay_ms`, `unbind_clocksource`, and `unbind_device`), one
  is the expected nonzero `systemd-detect-virt` result for bare metal, and one is
  the repository's full Python protocol check rejecting Ubuntu's
  `jsonschema 4.19.2` instead of the accepted `4.26.0`. The independent
  standard-library hash/inventory verifier passed.
- `adjtimex`, GCC/G++, Clang/Clang++, CMake, Ninja, and `llvm-objdump` were not
  installed. This archive therefore cannot establish the accepted build or
  dual-disassembler generated-code gates.
- Installing the named collector dependencies updated their security/tool
  packages and restarted affected services before collection; the running
  kernel was not upgraded. The archive represents the resulting post-install
  state.

## Privacy and custody note

An earlier raw archive was retained on the stand but rejected for public
publication because it included `hostnamectl` machine/boot identifiers and an
unredacted root-filesystem UUID. It was never transferred into this repository.
Its server-side SHA-256 is
`c9c44af044b8760168a5be9b975e773260e27ec6e04099a3802e0c1856eb06f7`.
The collector was corrected and retested before producing the published
archive. The owner explicitly authorized publication of the corrected archive,
checksum, and run log to this public branch on 2026-08-20.

## D-009 consequence

This evidence can inform the D-009 proposal's platform capability section. It
does not provide accepted clock source/conversion/serialization choices,
scientific acceptance limits, cross-core skew and drift qualification,
read-cost distributions, migration behavior, boundary generated code, or the
final selected-core qualification. D-009 and Stage 8 remain blocked until those
decision and implementation gates are completed.
