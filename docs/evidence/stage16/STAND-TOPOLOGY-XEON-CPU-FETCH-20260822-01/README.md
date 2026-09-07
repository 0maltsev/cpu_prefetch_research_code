# Read-only topology evidence `STAND-TOPOLOGY-XEON-CPU-FETCH-20260822-01`

This append-only evidence set was captured as the unprivileged `nobody`
account on candidate stand `185.184.131.153` at
`2026-08-22T10:58:46Z`. It contains raw `lscpu` CPU and cache JSON plus direct
read-only sysfs facts for candidate logical CPUs 0, 1, and 26. Every source
file is covered by `SHA256SUMS`; the manifest SHA-256 is
`c0c1e727315e17a6e54ef8857e5f4b6ceedbbf97a43f57a3c0659629108ca205`.

The evidence proves the following static candidate relationships:

- CPU 0: NUMA 0, package 0, package-local core 0, SMT sibling 52, LLC domain
  `0-25,52-77`;
- CPU 1: NUMA 0, package 0, package-local core 1, SMT sibling 53, the same LLC
  domain as CPU 0; and
- CPU 26: NUMA 1, package 1, package-local core 0, SMT sibling 78, LLC domain
  `26-51,78-103`.

Consequently, producer CPU 0 with consumer CPU 1 is a statically eligible
`NEAR` candidate, and producer CPU 0 with consumer CPU 26 is a statically
eligible `FAR` candidate under the imported definitions. This record does not
select either pair. It also does not prove runtime affinity, actual CPU,
isolation, interrupt routing, clock synchronization, page residency, or a
verified hardware state. Those remain independent gates.

No state-changing command, affinity setting, calibration, pilot, or
confirmatory operation occurred.
