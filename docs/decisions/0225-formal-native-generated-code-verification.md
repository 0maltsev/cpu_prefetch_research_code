# ADR-0225: Actual formal native generated-code verification

- Status: ACCEPTED — engineering verification authorized by the owner
- Scientific method change: none
- Execution and qualification authority: none

The historical combined-operation and diagnostic-worker probes do not establish
the generated code of the new persistent formal Q16a/Q16b/Q16c workers. Add a
separate gate over their actual native translation units. A link-only executable
references the three production entrypoints; it does not instantiate replacement
workers or execute captures. With all three formal dispatchers integrated, the
release gate inspects the complete production runner and binds its exact bytes.
The probe remains available for component characterization. Hermetic handoff
reports inspect the substituted test worker in a separate report directory;
they cannot substitute for the production runner reports. Bundle admission
checks both disassemblers, all 42 worker proofs, all negative checks, and exact
binary/checker/source bindings without rerunning disassembly.

Require the exact 42 worker identities: Q16a's two R0 roles, and both roles for
all five packages under each accepted software-prefetch emitter in Q16b and
Q16c. Require machine-code reference paths from the corresponding native entry.
The supported optimized shape is the accepted GCC release. Unsupported compiler
shapes fail closed; Clang sanitizer results are not generated-code qualification.

Worker functions contain legitimate cold mapping, preparation and parked reset
work. Identify active-phase control flow after the unique `service_window` call,
ending at the owner TLS reset. Require the supported unique-reset cut shape. For every TLS cut,
prove that another capture cannot be reached before a fresh start-barrier
arrival. Unclassified escaping transfers reject the cut. Follow all active
operation callees and reject unapproved external calls, indirect transfers,
allocation, blocking I/O, dynamic parsing and forbidden machine instructions.
Require actual primary writers, Q16a's raw demand writer, and dominating
`CLOCK_MONOTONIC_RAW` arguments with no external entry bypassing their definition.

The cold-cut proof includes the TLS observer itself, the observer's loader
callback and every post-cut call before the next barrier. Prove the
`dl_iterate_phdr` callback argument names the bounded native `Walk::visit`
collector and that no external entry bypasses that definition. Recursively
reject captures in this callback and in ordinary called wrappers. The cold TLS
observer's fixed C ABI leaves (`syscall`, `__errno_location`,
`dl_iterate_phdr`) remain qualified-runtime assumptions; they are not allowed
in active capture closures.

Count actual prefetch instruction sites, rather than set membership. Require
the exact registered package/emitter/role vector. Run GNU objdump and accepted
LLVM 22 objdump independently; require agreement on worker entry addresses,
active instruction addresses, cold cuts and prefetch witnesses. Normalize only
LLVM's separate one-byte LOCK prefix representation, retaining its actual
instruction address. Missing tools, malformed input and unsupported shapes fail.

Negative checks mutate decoded instructions from the actual binary to introduce
allocation, an indirect call, a direct syscall, a hidden hot TLS observation,
wrong clock domain, an unregistered atomic operation, a missing worker, wrong
prefetch intent and duplicate prefetch. Both disassemblers must reject all
mutants. Additional actual-code mutants hide captures in a post-cut wrapper,
the TLS observer and its loader callback. Software tests cover prefix truncation,
missing workers, boundary bypass and clock/callback-argument bypass. Reports bind the binary, checker and
relevant source bytes and retain both disassembler versions.

This gate has explicit limits. The active region includes failure-state CAS and
phase-completion OR operations from D210/D219. Their worker-root instruction
forms are retained and checked, but the checker does not prove their memory-object
identity. Operation callees cannot introduce locked instructions. The gate does
not independently prove slot-access/timestamp dataflow or scientific run validity.
Existing queue, workload, timing, software-mapping and diagnostic gates, semantic
tests, sanitizers and independent raw validation remain mandatory. A passing
report alone never qualifies a partial formal release or authorizes collection.
