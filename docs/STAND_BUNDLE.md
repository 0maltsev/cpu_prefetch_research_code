# Stage 16 stand-preflight bundle

Bundle profile: **`STAGE16-STAND-BUNDLE-v1`**

This bundle transfers immutable software-verification inputs to an authorized
Linux x86-64 stand. It is intentionally a **stand-preflight bundle**, not a
measurement bundle: it contains no production measurement executable, frozen
platform values, pilot plan, calibration output, or confirmatory authority.

## Content contract

Every bundle contains:

- `BUNDLE_MANIFEST.json` with protocol, source, release, readiness, and blocker
  identities;
- `SHA256SUMS`, plus an external SHA-256 sidecar for the outer archive;
- a deterministic source archive of the exact tracked and implementation-owned
  working-tree files used for the release;
- release `cpu_prefetch_smoke` and read-only `cpu_prefetch_preflight`
  executables and all repository static libraries;
- build metadata, exact release compile commands, and runtime dependency
  resolution with nondeterministic per-process loader addresses removed;
- both the complete current protocol snapshot and imported/implementation-owned
  schemas;
- the no-license notice, exact dependency inventory, and an SPDX 2.3 SBOM;
- implementation artifact/schema validators and the bundle verifier;
- a nonauthoritative configuration-shape example whose unresolved values are
  all JSON `null`; and
- this document, the readiness report, and the exact stand runbook.

The deterministic outer filename binds project version, Git revision, source
state, and the first twelve hexadecimal digits of the source-archive SHA-256.
Existing bundle paths are never overwritten.

## Debug-symbol strategy

Stage 16 does not alter release flags or post-link strip binaries. The bundled
preflight/foundation executables are the unstripped outputs of the accepted
`release-gcc` preset, and their exact source archive and compile commands are
retained. They are not measurement executables and carry no empirical timing
role. A future production measurement executable, its optimization/debug-info
policy, build ID, symbols, and custody must be frozen and requalified together;
Stage 16 does not silently add `-g`, strip symbols, or declare a future binary.

## Creation and verification

After a clean release build and all release code-generation checks:

```sh
cmake --build --preset release-gcc --target stand-bundle
sha256sum -c build/release-gcc/stand-bundle/*.tar.gz.sha256
```

For the reproducibility check, invoke the same generator with two new distinct
output directories and require the two `.tar.gz` SHA-256 values to be equal:

```sh
python3 tools/create_stand_bundle.py \
  --source-root . --build-dir build/release-gcc \
  --output-dir build/stage16-bundle-repro-a
python3 tools/create_stand_bundle.py \
  --source-root . --build-dir build/release-gcc \
  --output-dir build/stage16-bundle-repro-b
sha256sum build/stage16-bundle-repro-a/*.tar.gz \
  build/stage16-bundle-repro-b/*.tar.gz
```

On the stand, replace the uppercase tokens, verify the sidecar, extract into a
new empty directory, change into the single extracted top-level directory, and
run:

```sh
sha256sum -c ARCHIVE.tar.gz.sha256
mkdir -p EMPTY_EXTRACTION_DIRECTORY
tar -xzf ARCHIVE.tar.gz -C EMPTY_EXTRACTION_DIRECTORY
cd EMPTY_EXTRACTION_DIRECTORY/EXTRACTED_TOP_LEVEL_DIRECTORY
python3 validators/verify_stand_bundle.py --root .
release/bin/cpu_prefetch_smoke
release/bin/cpu_prefetch_preflight --self-test
```

These checks verify bytes and nonprivileged executable startup only. They do
not qualify a clock, CPU pair, NUMA placement, storage domain, hardware state,
or stand.

## Supersession

A changed source, compiler, flag, dependency, protocol snapshot, validator,
bundle layout, or release artifact produces a new archive and checksum. An old
bundle remains immutable. A profile change requires a superseding engineering
ADR and complete clean verification; a scientific change additionally follows
the protocol amendment rule.

## Q14 pilot-candidate profile

`STAGE17-PILOT-CANDIDATE-BUNDLE-v1` is a separate append-only profile and does
not modify this Stage 16 bundle. Its target is:

```sh
cmake --build --preset release-gcc --target pilot-candidate-bundle
```

The target first requires strict `PASS` reports for queue, workload, timing,
storage, one-`PAUSE`, and all ten combined runner operation shapes. It then
requires a clean exact Git revision. The archive adds the non-executing runner,
qualification-only tool, v2 admission and future authorization schemas,
codegen reports, and production-runner documentation. Release binaries remain
unstripped and are bound to exact compile/build provenance.

The manifest explicitly records no dynamic qualification authority, no
measurement command, and `pilot_authorized=false` and
`confirmatory_authorized=false`. A valid archive is only an input to a future
exact Q15 request. It cannot authorize transfer, stand access, qualification,
control, calibration, or pilot work.

D-047 fixes the physical mapping as `X86-64-PREFETCHW-PREFETCHT0-v1`; both
accepted compilers pass the strict two-disassembler combined audit. The
manifest and combined report must carry that exact identity. The creator still
rejects dirty source trees, non-`PASS` or drifted reports, overwrite, and any
authority-bearing output.
