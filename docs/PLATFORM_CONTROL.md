# Stage 9 Platform Inventory and Control Contract

## Scope

`cpu_prefetch_platform` implements the non-measuring Stage 9 software boundary
for Linux x86-64 under ADR-0018 and ADR-0019. It does not identify this
development host as the experiment stand, choose a core pair, change host
state, or qualify a platform for measurement. Stage B/C page and placement
treatments remain excluded.

The layer has seven separate operations:

1. `LinuxInventoryProvider::collect` reads inventory without changing state.
2. `detect_capabilities` records read-only, external-authority-required,
   unavailable, or mapping-unresolved status.
3. `validate_requested_state` binds an explicit request to one inventory
   snapshot and rejects impossible or non-Stage-A placement.
4. `apply_requested_state` either produces a dry-run plan or calls an injected,
   explicitly identified actuator.
5. `verify_requested_state` obtains fresh observations through a separate
   verifier interface and compares exact values.
6. `restore_platform_state` restores recorded pre-state in reverse application
   order and retains every failure.
7. `emit_manifest` emits a deterministic rich evidence record, while
   `emit_protocol_platform_record` emits the exact imported
   `platform.schema.json` logical shape.

No operation is reachable from the timed producer or consumer API.

## Inventory

The Linux provider reads procfs, sysfs, `uname`, `sysconf`, and process-local
atomic facts only. It records:

- online logical CPUs and their core, package, SMT-sibling, NUMA, and cache
  memberships;
- deduplicated data/unified cache domains, size, line size, sharing masks, and
  last-level status;
- NUMA-node CPU membership;
- PCI address/vendor/device/class, NUMA node, and local CPU mask when readable;
- CPU vendor/model/stepping/microcode, pointer-atomic width/alignment/runtime
  lock freedom, base page size, kernel, compiler, standard library, and language
  standard;
- read-only observations for firmware/DMI, memory population and huge pages,
  cpufreq/governor, turbo, cpuidle, SMT, IRQ affinity, CPU isolation/nohz, and
  clocksource.

Missing mandatory topology or identity input is an error; a NUMA node is never
invented from CPU numbering. Optional observations retain an explicit absent
value. The caller supplies snapshot ID and capture time, so neither is inferred
from a path or local clock.

Inventory is capability evidence, not verification of a requested run state.
PCI and uncore observations do not imply that a device affects this experiment;
that relationship needs stand evidence.

## Placement and memory policy

The request names producer and consumer logical CPUs, placement, memory-node
sets, and page size. Validation enforces the imported Stage A rules:

- both CPUs are online, distinct physical cores, and not SMT siblings;
- `NEAR` is one NUMA node with a shared last-level cache domain;
- `FAR` is different NUMA nodes;
- shared queue/node/event/schedule storage is bound to the producer node;
- producer-private and consumer-private buffers are bound to their worker
  nodes;
- the requested page size exactly matches inventoried base pages.

Interleaved, consumer-local, replicated, migrated, explicit-huge-page, and THP
treatments are rejected as Stage C choices. The library does not select a
near/far pair or page size.

Actual affinity, allocation policy, page residency, and migration observations
are separate typed controls. A later run controller must collect their
before/during/after evidence for the exact thread IDs and address extents.

## Controls, authority, and verification

Typed control kinds cover producer/consumer affinity and actual CPU, shared and
private memory policy/residency, base/huge-page state, governor/frequency,
turbo, C-state, SMT, interrupt routing, isolation, hardware prefetch,
clocksource, microcode, firmware, compiler, binary, and libraries.

Each control records target, exact requested value, mandatory flag, mutation
flag, authority ID, actuation mechanism, and independent verification
mechanism. Mutations fail validation without authority. An actuation mechanism
cannot also be declared its own verification mechanism.

The repository provides:

- a real Linux read-only inventory provider;
- deterministic parsing, validation, capability detection, dry-run, evidence,
  and manifest code;
- injected actuator/verifier interfaces and scripted fake implementations in
  tests.

It intentionally provides no production state-changing Linux actuator in this
stage. Exact affinity/NUMA/page/frequency/turbo/C-state/IRQ/isolation mappings
still need the selected stand, approved authority, target-specific readback,
and rollback evidence. Hardware-prefetch capability is always
`MAPPING_UNRESOLVED` until the exact CPU manual, fields, engines, authority,
readback, regular/pointer probes, and rollback are accepted. A generic MSR or
“disable all prefetchers” implementation is forbidden.

`AUTHORIZED_APPLY` therefore becomes usable only with an injected approved
adapter. `DRY_RUN` never calls an actuator. An applied step is not verified.
Verification rejects missing evidence, value disagreement, mismatched
verification mechanism, empty evidence ID, different inventory snapshot, or
different state epoch. Mandatory unreadable state fails closed.

Before mutation, each control needs independently recorded pre-state. On a
partial apply failure, successfully changed controls are restored in reverse
order. A missing pre-state or failed restore is retained as a restoration
failure and keeps the platform ineligible; there is no best-effort success
label.

## Manifests and compatibility

The rich evidence manifest uses `LINUX-PLATFORM-EVIDENCE-v1` and JCS-I64-v1
canonical JSON. It keeps inventory, capabilities, requested state, apply/plan
steps, independent observations, restoration steps, errors, build/binary and
library provenance, and a zero-field self-hash. Partial and dry-run manifests
are valid artifacts but have `eligible=false`.

The imported platform schema remains the normative logical summary. Its emitter
requires explicit eligible near/far pairs, memory-population and residency
records, compiler flags/link mode, accepted clock evidence IDs, and separate H0
and H1 readback/probe/authority IDs. It validates pair topology, emits no richer
extra fields, and uses the imported version and enums. Rich facts are retained
in separately hashed evidence artifacts rather than squeezed into or added to
the immutable imported schema.

Changing an enum, placement rule, evidence version, imported projection, or
verification/eligibility semantics requires a superseding engineering ADR and
full requalification. A change to scientific placement or hardware-state
meaning requires a protocol amendment.

## Correctness evidence and limits

The platform-labelled tests cover CPU-list/topology parsing, cache/NUMA/PCI
inventory, exact near/far acceptance, missing/offline CPUs, SMT sibling
confusion, NUMA and Stage C policy rejection, unresolved/unsupported controls,
missing authority, dry-run non-mutation, partial apply, reverse restoration,
restoration failure, apply/readback disagreement, stale/non-independent
readback, complete and partial canonical manifests, imported-schema loading,
and a read-only development-host smoke inventory.

Run them with:

```sh
ctest --preset dev-gcc -L platform --output-on-failure
```

These tests establish software behavior only. Before any measurement, the
selected stand still needs an approved actuator/authority, complete readback
and restoration exercise, exact core/address evidence, runtime lock-free facts,
full Stage 8 clock qualification on both selected pairs, and before-block
rechecks.
