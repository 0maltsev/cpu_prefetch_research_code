# Read-only topology evidence `STAND-TOPOLOGY-CPU-PREFETCH-V5-20261020-01`

This append-only evidence set was captured as `root` on candidate stand
`94.126.205.83` (`cpu-prefetch-v5`) at `2026-10-20T18:47:55Z`. It contains raw
`lscpu` CPU and cache JSON plus direct read-only sysfs facts for candidate
logical CPUs 0, 1, and 8. Every source file is covered by `SHA256SUMS`; the
manifest SHA-256 is
`d1a1234d9b195a17e7765bfbf6100a3f62a1828ad94440df4ef5b5600da8af4c`.

The evidence proves the following static candidate relationships:

- CPU 0: NUMA 0, package 0, package-local core 1, SMT sibling 16, LLC domain
  `0-7,16-23`;
- CPU 1: NUMA 0, package 0, package-local core 2, SMT sibling 17, the same LLC
  domain as CPU 0; and
- CPU 8: NUMA 1, package 1, package-local core 1, SMT sibling 24, LLC domain
  `8-15,24-31`.

Consequently, producer CPU 0 with consumer CPU 1 is a statically eligible
`NEAR` candidate, and producer CPU 0 with consumer CPU 8 is a statically
eligible `FAR` candidate under the imported definitions. This record does not
select either pair -- that is ADR-0173's own role. It also does not prove
runtime affinity, actual CPU, isolation, interrupt routing, clock
synchronization, page residency, or a verified hardware state. Those remain
independent gates.

No state-changing command, affinity setting, calibration, pilot, or
confirmatory operation occurred.
