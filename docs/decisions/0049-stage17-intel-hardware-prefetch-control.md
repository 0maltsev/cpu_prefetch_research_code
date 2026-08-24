# ADR-0049: Intel 06_55H hardware-prefetch control mapping

- Status: `ACCEPTED_AND_IMPLEMENTED_SOFTWARE_ONLY`
- Date: 2026-08-24
- Decision ID: D-049
- Classification: platform-dependent treatment mapping
- Decision owners: protocol, platform, security, and validation owners
- Protocol version: `2.0.0-pre.2`
- Supersedes: the unresolved D-018 hardware-prefetch mapping only
- Lifecycle gate: software mapping at Q15-P0; dynamic evidence at Q15

## Context and options

The accepted candidate is Intel family 06 model 55H. H0 is the unmodified
observed default. H1 must disable the four documented core-scope prefetch
engines without modifying unknown/reserved state. Options considered were an
unverified utility command, a broad arbitrary-MSR helper, a model-restricted
complete-value transaction, or leaving the platform ineligible.

## Decision

Select the narrow mapping
`INTEL-06_55H-MSR-1A4-DISABLE-0_3-v1`:

- exact CPUID gate: family `06`, model `55H`;
- exact core-scope MSR: `IA32_MISC_FEATURE_CONTROL` / `0x1A4`;
- CPUs: exactly `0`, `1`, and `26` for the accepted near/far owner set;
- H0: read and preserve each complete 64-bit prestate without writing;
- H1: request `prestate | 0x0f`, covering documented L2 hardware, adjacent
  cache-line, DCU L1, and DCU IP disable bits;
- preserve bits 63:4 exactly and expose no arbitrary address/mask interface;
- independently read back the complete requested value, run both regular-
  stream and pointer-stream probes, restore the complete prestate in reverse
  order, and independently verify restoration; and
- reject family/model/CPU drift, missing/duplicate prestates, H0/H1 collapse,
  partial readback, failed probes, and uncertain restoration. Restoration
  uncertainty quarantines the stand.

The repository implements the plan/transaction logic, fake backends, evidence
schema/semantic validator, and a pure plan command. It deliberately implements
no Linux MSR reader/writer and executed no MSR operation under Q15-P0.

## Evidence and effects

- Owner acceptance of Q15-P0 on 2026-08-24.
- Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 4,
  model 06_55H MSR table:
  <https://cdrdv2-public.intel.com/874253/335592-090-sdm-vol-4.pdf>.
- Existing hashed candidate inventory and CPUID evidence; these identify the
  candidate but do not replace a fresh Q15 readback.
- Positive/negative fake transaction and schema tests.

Scientific effect: maps the already registered H0/H1 factor without changing
its levels. Compatibility effect: model, MSR, mask, CPU set, prestate,
readback, probes, restoration, tool hash, and evidence schema are qualification
identity. Owner: platform/protocol. Deadline: before any calibration or pilot.
Any mapping/model/scope/bit/probe change needs a superseding ADR and full
requalification; treatment changes require a protocol amendment.

## Authority boundary

Q15-P0 approves the mapping and local implementation only. Actual prestate,
privileged reads/writes, probes, and restoration require an exact hash-bound
Q15 authorization and distinct operational authorities.
