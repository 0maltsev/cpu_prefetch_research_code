# Q15 probe and collector contract

Status: **`FROZEN_CONTRACT; IMPLEMENTATION_REQUIRED; NO_AUTHORITY`**

Protocol: `2.0.0-pre.2`

Decision: D-052 / ADR-0052

Normative implementation contract:
`config/q15/q15-probe-collector-contract-v1.json`

Contract ID: `Q15-PROBE-COLLECTOR-CONTRACT-v1`

## Boundary

This contract fixes what a future qualification implementation must collect
and how its probe result is classified. It does not provide probe/collector
executables, authorize stand access, open a performance counter, read or write
an MSR, apply a hardware state, run calibration, or execute pilot or
confirmatory work. The machine-readable `unimplemented_boundary` records each
of those absent authority/implementation facts fail-closed.

## Counter and probe contract

The counter is the raw Skylake-X event `L2_RQSTS.ALL_PF`: EventSel `0x24`,
UMask `0xf8`, config `0x000000000000f824`. A future collector must use
`perf_event_open` per thread after singleton affinity; count user activity only;
exclude kernel, hypervisor, and guest; disable inheritance; pin the event; and
retain `time_enabled` and `time_running`. Any multiplexing or unequal enabled/
running time fails the probe.

Both probes use private target-node memory sized by the exact formula
`ROUND_UP(2*VERIFIED_LOCAL_LLC_BYTES,VERIFIED_BASE_PAGE_BYTES)`. The future
implementation must derive the verified local LLC size and base-page size from
Q15-R evidence; it may not replace the formula with a guessed byte count.
Allocation, target-CPU first touch, and one priming pass occur before the one
counted pass. The counted traversal admits no allocation, filesystem I/O,
software prefetch, major fault, or minor fault. H0 and H1 use the same binary,
CPU, buffer, layout, order, and counter configuration.

The regular probe makes one volatile 64-bit demand load from every cache line
in ascending address order. It passes only if integrity passes, the H0 count is
strictly positive, and the H1 count is exactly zero.

The pointer-dependent probe makes one dependent volatile 32-bit next-index
load per line over one cycle containing every line. Its permutation is
`FISHER-YATES-PHILOX4X32-10-v1`, derived from SHA-256 of the UTF-8 literal
`Q15-POINTER-PROBE-PERMUTATION-v1`; the resulting seed is frozen in the JSON
contract. Integrity and H1 zero are mandatory. H0 positive is
`DISTINGUISHED`; H0 zero is
`NOT_DISTINGUISHABLE_WHERE_NOT_POSSIBLE`. The latter does not qualify the
pointer probe as distinguished and does not invalidate an otherwise valid
regular-stream result.

Timing values are raw diagnostics only. No time is subtracted from a PMU count
and no elapsed-time or effect-size threshold participates in acceptance.

## Collector matrix

| ID | Phase | Exact acceptance boundary |
|---|---|---|
| `Q15-CLOCK-COLLECTOR-v1` | Q15-R | Accepted clock qualification evaluators and frozen repetition counts; raw evidence retained; no correction |
| `Q15-ATOMIC-LAYOUT-COLLECTOR-v1` | Q15-R | Exact pointer and termination widths/alignments, runtime lock-free results, and required cache-line separation |
| `Q15-ACTUAL-CPU-MIGRATION-COLLECTOR-v1` | Q15-R/Q15-W | Singleton affinity readback and `sched_getcpu` at operation entry/exit equal the authorized CPU; zero migrations |
| `Q15-ADDRESS-RESIDENCY-COLLECTOR-v1` | Q15-R/Q15-W | `move_pages` covers every page before, between priming/counted passes, and after; equal nonzero page counts, zero unavailable/wrong-node/migrated pages |
| `Q15-SOFTWARE-PREFETCH-COLLECTOR-v1` | Q15-R | PRFCHW on CPUs 0/1/26 and accepted GCC/Clang plus GNU/LLVM codegen reports all pass |
| `Q15-MSR-PRESTATE-COLLECTOR-v1` | Q15-R | One fixed complete-value read for each CPU 0/1/26; requested state is never copied into verified state |
| `Q15-MSR-READBACK-COLLECTOR-v1` | Q15-W | Independent complete-value readback after every one-CPU apply and restore, with distinct writer and auditor identities |

## Transaction and artifacts

The future Q15-W controller must bind an H0 baseline to exactly one CPU's H1
apply, independent complete-value readback, both H1 probes, exact complete-value
restore, and independent restoration readback before proceeding. It must retain
raw counter values, raw timestamps, integrity fields, page/CPU observations,
commands, exit statuses, partial failures, and artifact hashes append-only.
Successful command return is never verified state.

## Repository-local validation

With the recorded Python dependency environment:

```sh
python3 tools/check_q15_probe_collector_contract.py
cmake --build --preset dev-gcc --target q15-probe-collector-contract-check
ctest --preset dev-gcc -L q15 --output-on-failure
```

These checks validate only contract bytes and negative mutations. They do not
execute a probe or collector. Before Q15-R, the future implementation still
needs exact source/binary hashes, generated-code evidence, commands, roles,
limits, storage/custody, signatures, and a clean no-authority release binding.
