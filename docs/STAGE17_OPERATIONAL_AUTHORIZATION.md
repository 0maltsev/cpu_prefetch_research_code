# Stage 17 operational authorization successor

Current state: **`PREPARED`**  
Pilot execution readiness: **false**  
Stage 17 complete: **false**  
Stage 18 ready: **false**

ADR-0104 replaces the open-ended pilot governance chain with one finite
successor. It does not authorize stand access or a run:

```text
PREPARED
  -> AUTHORIZED_FOR_READ_ONLY_PREFLIGHT
  -> PREFLIGHT_ACCEPTED
  -> READY_FOR_STAGE17_PHASE_AUTHORIZATION
```

Every edge consumes immutable evidence from the single
[`STAGE17-EXTERNAL-INPUTS-v1`](../config/stage17/stage17-external-input-checklist-v1.json)
checklist. Missing, partial, expired, or hash-mismatched evidence retains the
current state and stops without automatic retry. The final state permits
preparation of an exact phase authorization; it is not itself pilot execution
authority. Pilot execution additionally requires all ten checklist entries.

For pilot governance only, `cpu-prefetch-stage17-pilot-owner` is explicitly
the owner, operator, controller, custodian, and auditor. Reviews must disclose
that collapse and may not claim independence. One hashed authorization may
cover one frozen set of read-only preflight observations; no new PKI ceremony
is required for each observation. Privileged controls and each scientific
phase remain separately bounded actions.

This relaxation does not cross the Stage 18 boundary. The imported
`PLANNED -> COLLECTED_SEALED -> TRAINING_OPEN -> SELECTION_FROZEN ->
VALIDATION_UNSEALED -> H3_EVALUATED -> H1H2_RELEASED -> ARCHIVED` chronology,
validation sealing, predecessor hashes, and release authorities remain strict.
No Stage 17 record can unseal or authorize Stage 18.

## Local verification

```sh
cmake --build --preset dev-gcc --target stage17-operational-successor-check
ctest --preset dev-gcc -R 'runner.stage17_operational_successor|q15.p4_r_c_executor_no_network_self_test' --output-on-failure
```

Print the one authoritative unresolved-input list:

```sh
/tmp/cpu-prefetch-stage16-deps/python/bin/python \
  tools/check_stage17_operational_successor.py --print-missing
```

The interpreter path above is the current pre-provisioned development prefix;
another clean environment may use its recorded CMake `Python3_EXECUTABLE`.

## External qualification archive boundary

`execute_d104_p4_r_c.py --self-test` uses synthetic caller-supplied bytes and
never reads the ignored build tree. The exact historical qualification archive
is an external action input governed by
[`Q15-QUALIFICATION-ARCHIVE-EXTERNAL-CONTRACT-v1`](../config/q15/q15-qualification-archive-external-contract-v1.json).
Validate an explicit custody or rebuilt copy separately:

```sh
cmake --preset dev-gcc \
  -DCPU_PREFETCH_Q15_QUALIFICATION_ARCHIVE=/absolute/path/to/exact.tar.gz \
  -DCPU_PREFETCH_Q15_QUALIFICATION_SIDECAR=/absolute/path/to/exact.tar.gz.sha256
cmake --build build/dev-gcc --target q15-qualification-archive-integration-check
```

The contract records the source revision and candidate rebuild commands. A
rebuild is accepted only when both archive and sidecar bytes match the exact
contract; otherwise a byte-identical custody copy is required.

## Preserved predecessors

The machine-checkable
[`STAGE17-D099-D108-PRESERVATION-v1`](../config/stage17/d099-d108-preservation-manifest-v1.json)
binds every decision/evidence artifact. The D-104 preparation continues to
bind its historical executor bytes at Git revision `dc643df...`; ADR-0104 binds
the hermetic successor without rewriting that record. D-105 through D-108
remain unchanged proposed/unaccepted records and are not gates in this
successor.
