# Repository tools

Stage 3 tools verify the build foundation, protocol snapshot, documentation,
dependency inventory, and release flags. `cpu_prefetch_smoke` reports build
identity only. `generate_schedule.py` is the accepted standalone Stage 7
preparation tool; it generates a complete immutable schedule and envelopes
before measurement and cannot observe a queue, clock, or outcome. No tool in
this directory is a benchmark or produces scientific results.

`cpu_prefetch_qualification --hardware-prefetch-plan` is a Q15-P0 pure mapping
check over three caller-supplied complete hexadecimal prestates. It accepts
only H0/H1 and the fixed CPUs-0/1/26 Intel 06_55H MSR-0x1A4 mapping. It has no
MSR reader/writer, does not collect stand facts, and cannot apply or authorize
a control. `check_hardware_prefetch_schema.py` validates only synthetic or
already-collected immutable evidence.

## Stage 8 clock-decision evidence collector

`collect_stage8_clock_evidence.sh` gathers read-only host, topology, clocksource,
firmware, toolchain, repository, and imported-protocol evidence for preparing
D-009. It requires the operator to supply the intended CPU list; it never
selects CPUs or fills in a platform value. It does not install tools, use the
network or `sudo`, access MSRs, change machine state, qualify a clock, or run a
performance experiment.

From the repository root, set the CPU list from the approved stand placement
record and choose a new output name:

```bash
./tools/collect_stage8_clock_evidence.sh \
  --cpus "$CLOCK_CORE_LIST" \
  --output "$PWD/stage8-clock-evidence-$(date -u +%Y%m%dT%H%M%SZ).tar.gz"
```

The output file must not already exist. The command prints its SHA-256. Inside
the archive, `SHA256SUMS` protects every collected file and
`collection_issues.tsv` records unavailable tools, permission failures, and any
critical protocol-integrity failure. Preserve the original archive and printed
hash. Because it contains hostname, firmware product, kernel, affinity, and
repository-state data, review it before sharing; redact only a separately named
copy and hash that copy independently. The collector never invokes
`hostnamectl`, because its default output contains machine and boot IDs. It
records a SHA-256 of `/proc/cmdline` but redacts identity-bearing boot, storage,
and network values while retaining timing-relevant kernel flags.

This archive is capability/configuration input to the D-009 decision bundle. It
does not replace the Stage 8 implementation's accepted skew, drift, resolution,
read-cost, conversion, boundary, and generated-code qualification evidence.
