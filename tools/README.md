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

Q15-S1/ADR-0051 adds `cpu_prefetch_q15_tool` as a separate qualification-only
executable. Its pure self-test/scope commands never open a device. Its dynamic
surface is fixed to CPUID family 06/model 55H, MSR 0x1A4, CPUs 0/1/26, and
complete H1/H0 values derived from the accepted 0x0f mask; it has no arbitrary
path/address/mask/CPU-list or scientific-run option. Presence of the executable
grants no authority. Dynamic options require a later exact signed Q15-R or
Q15-W record and effective OS role controls. Repository tests exercise only a
fake file-operation boundary and never open `/dev/cpu/*/msr`. See
`docs/Q15_QUALIFICATION_TOOL.md`.

D-052 adds `check_q15_probe_collector_contract.py`. It validates the frozen
raw-PMU probe/seven-collector contract and negative mutations without opening a
counter, device, or stand connection. It is a definition check, not a probe or
collector implementation and not authority.

`check_q15_r_external_input_acquisition.py` preserves the hash-bound proposal.
`check_q15_r_p4_d_implementation.py` validates Q15-R-P4-D acceptance,
ADR-0066 through ADR-0070, the exact 25-command collector contract, schemas,
complete/partial synthetic artifacts, and blocked unissued P4-R/P4-K
preparations. `cpu_prefetch_q15_prestate_collector --self-test` and
`--describe-contract` are no-execution checks; its `--collect` entry requires a
separate exact Q15-R-P4-R and is not run by repository verification.
`validate_q15_r_prestate.py` is the offline artifact validator: it enforces
unique/canonical JSON, Draft 2020-12, the exact contract prefix and process
state, finite bounds, stop-first failure, and zero-self SHA-256.

D-053 adds `check_q15_probe_implementation.py` and
`check_q15_probe_codegen.py`. The first validates the exact master-seed,
namespace/purpose, derived-key, buffer-integrity, and no-authority profile with
negative mutations. The second requires GNU and LLVM disassembly to show one
static demand-load instruction in each counted traversal, no call/prefetch/
fence/system instruction, and expected rejection of extra-load/prefetch
mutants. Neither tool accesses a stand or PMU.

Q15-S3 adds `check_q15_dynamic_implementation.py` and
`check_q15_runtime_codegen.py`. The first binds D-054 through D-056, their
no-authority profile, the phase-spanning state machine, exact Linux seams, and
the seven-component registry. The second requires GNU and LLVM disassembly to
show indirect enable, exactly one accepted traversal call, and indirect
disable in each counted region; it rejects duplicate-traversal and software-
prefetch mutants. Repository tests use fake operations and an allocation hook.
Neither checker starts a Q15 session, opens a counter/device, changes affinity
or NUMA policy, or accesses a stand.

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
