# ADR-0047: Stage 17 physical software-prefetch mapping

- Status: `ACCEPTED_AND_IMPLEMENTED_SOFTWARE`
- Date: 2026-08-22
- Decision owners: protocol, platform, workload, compiler, and code-generation
  owners
- Protocol version: `2.0.0-pre.2`
- Supersedes: the unresolved physical-emitter state retained by ADR-0028 and
  ADR-0044; their site, target, distance, and static-binding rules remain
  unchanged
- Lifecycle gate: D-044 clean pilot-candidate release before Q15

## Context and scientific constraints

The imported Stage A treatment requires a retaining write-intent hint at each
registered R1/R2 producer slot-line site, a retaining read hint at each matched
R1/R2 consumer slot-line site, and a retaining read hint for the immediate L1
successor header. R0/L0, the L1 producer, event records, and the linked recycler
must receive no Stage A software prefetch.

The accepted candidate stand is an Intel Xeon Gold 6230R Linux x86-64 system.
The immutable Stage 8 CPUID archive records
`CPUID.80000001H:ECX=0x00000121` on selected CPUs 0, 1, and 26, including the
PRFCHW bit. Intel documents `PREFETCHW` as an anticipatory write hint and
`PREFETCHT0` as the T0 temporal read form. A fresh isolated compiler probe also
showed that unconstrained `__builtin_prefetch(address,1,3)` lowers to
`PREFETCHT0`, not `PREFETCHW`, under both accepted release compilers. A generic
builtin therefore cannot silently implement the producer site.

No queue outcome, calibration result, treatment comparison, or performance
observation selected the mapping.

## Options considered

1. Use the compiler builtin without constraining or auditing its physical
   lowering.
2. Use `PREFETCHT0` as the explicitly named producer read fallback and as the
   retaining read form.
3. Use `PREFETCHW` for the ring producer and `PREFETCHT0` for the ring consumer
   and linked successor, with exact compiler/disassembler and runtime CPUID
   gates.
4. Use `PREFETCHWT1` or another locality form.
5. Keep D-044 blocked.

## Decision

Select option 3 as `X86-64-PREFETCHW-PREFETCHT0-v1`:

- R1/R2 producer: exactly one `PREFETCHW` for the registered future ring-slot
  cache line;
- R1/R2 consumer: exactly one `PREFETCHT0` for the registered same-distance
  ring-slot cache line;
- L1 consumer: exactly one `PREFETCHT0` after acquiring the immediate successor
  and before demanding its event pointer/header;
- L1 producer and R0/L0: no software-prefetch instruction; and
- no event-record or recycler target, runtime fallback, alternative-locality
  form, compiler memory fence, hidden retry, or dynamic dispatch.

The emitter uses explicit GNU-style x86 instruction templates so the physical
mnemonic does not depend on the builtin default. The source form is accepted
only when GCC 16.1.1 and Clang 22.1.6 produce the exact mapping and both GNU
Binutils 2.46 and LLVM 22.1.6 independently pass the complete ten-operation
audit. Source, compiler, flags, binary, rule, disassembler, report, and mapping
IDs are compatibility identity.

Each owner thread must bind and independently read back its accepted CPU, then
observe `CPUID.80000001H:ECX[8]`. A missing leaf or bit is a zero-attempt
pre-run preparation failure before private-stream first touch and the start
barrier. Static inventory evidence does not replace this per-release dynamic
qualification.

## Evidence

- Owner acceptance of the D-047 confirmation and repository-local application
  statement on 2026-08-22.
- Protocol implementation specification Sections 3.2, 3.3, and 4.2.
- ADR-0016, ADR-0028, ADR-0043, and ADR-0044.
- Immutable Stage 8 CPUID evidence for CPUs 0, 1, and 26.
- Intel instruction-set documentation and the pinned GCC/Clang compiler
  contracts.
- Fresh GCC and Clang strict dual-disassembler combined-operation audits,
  including wrong-write, wrong-read, duplicate-read, and forbidden-work
  mutants.

## Scientific and compatibility effects

The decision realizes the already registered write/read intents and sites. It
does not change a queue, target address, distance rule, schedule, timestamp,
row, lifecycle, estimator, or treatment family. The physical mapping is a
platform form and cannot be generalized to another CPU architecture, compiler
lowering, or locality instruction.

Changing any mnemonic, intent, site, target, count, fallback, compiler form, or
capability gate requires a superseding ADR, a new mapping/profile identity,
complete generated-code requalification, and protocol review if treatment
semantics would change. Existing releases and artifacts remain immutable.

## Verification and acceptance tests

- Positive and negative fake capability tests prove that both owner threads
  check PRFCHW after affinity and before first touch.
- The typed qualification artifact is eligible only for the exact mapping,
  both per-worker capability observations, both compilers, and both
  disassemblers.
- Schema tests reject an alternative producer instruction.
- The complete generated producer/consumer call graph requires exact per-
  specialization instruction vectors and rejects four independent mutants.
- The full supported build, sanitizer, schema, formatting, static-analysis,
  release, and bundle matrix remains mandatory for D-044 closure.

## Rollback or supersession

Unsupported capability, compiler drift, codegen mismatch, or evidence mismatch
fails before measurement and produces no fallback. A future replacement needs
a new prospective mapping ID and ADR; it cannot be selected from calibration,
pilot, or confirmatory outcomes.

## Protocol-amendment assessment

The selected mapping implements the protocol's documented write-intent and
retaining-read alternatives without changing their semantics. No protocol
amendment is required.
