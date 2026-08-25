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
`check_q15_r_p4_r_collector_release_decision.py` validates proposed D-071,
the exact clean v3 release bytes, immutable P4-R/P4-K predecessors, seven
remaining null P4-R inputs, and six authority/lineage/value negative
mutations. Its optional archive/extraction arguments perform read-only local
release verification and never execute the collector.
`check_q15_r_p4_e_acceptance.py` binds the exact D-071 owner acceptance and
authorized no-authority successor hash. `check_q15_r_p4_r_preparation_v2.py`
enforces one resolved release group, seven null P4-R inputs, unchanged P4-K,
all 25 commands/limits, `NOT_ISSUED`, and eight negative mutations.
`check_q15_r_p4_r_staging_authorization_decision.py` validates proposed D-072
through D-075, exact `f30036e`/v3 lineage and literal candidates, named-role and
1,800-second SSHSIG policy, separate unissued P4-R-I/P4-R-C gates, one-shot
verification/rollback rules, seven unresolved groups, and fifteen negative
mutations. Its optional archive mode reads and hashes the local v3 archive and
rejects unsafe members; it never transfers, extracts, signs, accesses the
stand, or executes the collector.
`check_q15_r_p4_f_acceptance.py` binds the exact accepted statement and
proposal/predecessor hashes, freezes only repository-local template values,
and rejects seven authority/lineage/value mutations.
`check_q15_r_p4_r_successor_templates.py` validates separate still-unissued
P4-R-I and P4-R-C schemas, exact ADR/acceptance/release/path/command/limit/
rollback bindings, six null external-input groups per template, unchanged
P4-R/P4-K predecessors, and twelve negative mutations. Neither checker issues
an authorization or performs filesystem, network, key, stand, or collector
work.
`check_q15_r_p4_k_decision_input.py` validates the proposed D-076 through
D-079 owner-choice bundle, four null selections, eight null P4-K external
inputs, immutable predecessor hashes, three explicit owner questions, split
future gates, all-false authority, and twelve negative mutations. It never
reads, generates, imports, copies, or uses key material and never accesses a
stand, signs, issues, installs, calibrates, pilots, or measures.
`check_q15_r_p4_k_d_acceptance.py` binds the delegated recommended choices,
logical-only custody identifiers, exact predecessor hashes, bounded owner
messages, all-false action authority, and ten negative mutations.
`check_q15_r_p4_k_successor_templates.py` validates separate still-unissued
P4-K-A/P4-K-R schemas, acceptance/ADR hashes, 13/9 null fields, the bootstrap-
signer boundary, one-attempt/zero-retry acquisition, distinct public review,
and fourteen negative mutations. Neither checker discovers, generates,
fingerprints, imports, copies, or uses a key; creates public artifacts or
paths; accesses a stand; signs/issues; installs; or executes any Q15 or
experiment phase.
`check_q15_r_p4_k_a_operational_input_decision.py` validates the proposed
D-080 through D-085 offline-environment, custody, public-export, bootstrap-
trust, fixed-controller, and issuance/review contracts. It binds exact
acceptance/template/ADR hashes, keeps six selections, seven external values,
and five owner answers null, and rejects fifteen authority/evidence/self-
authorization/retry/scope mutations. It does not inspect an offline host,
access a key/trust artifact, collect secrets, create a path/public artifact,
implement or execute a controller, access the stand, sign, issue, or run any
Q15 or experiment phase.

`check_q15_r_p4_k_a_d_acceptance.py` validates the separate policy acceptance,
exact six selections and five responses, seven null external inputs,
ADR-0080..0085 hashes, immutable templates, and the fail-closed absence of a
qualifying bootstrap signer. Nineteen mutations reject controller
implementation authority, external evidence, target-key self-authorization,
premature P4-K-A unblocking, and all operational scopes. It does not implement
or execute a controller or perform any offline, key, trust, path, signature,
stand, Q15, or experiment action.

`check_q15_r_p4_k_a_controller_profile.py` validates ADR-0086's generic
no-authority implementation profile, exact controller/test source hashes, the
fixed ten-step graph, the immutable absent-bootstrap disposition, strict
profile/admission schemas, seven null external inputs, and the lack of any OS
or file backend. It exercises fourteen profile and six admission mutations;
its synthetic complete admission is not an authorization or external-evidence
fixture.

`check_q15_r_bootstrap_governance_root_decision.py` validates the proposed
D-087 through D-092 governance-root decision/input record, exact immutable
lineage, eight null external inputs, six unanswered owner questions, and
fourteen fail-closed mutations. It neither selects a real-world identity or
custody mechanism nor creates, reads, imports, copies, fingerprints, signs, or
uses any key or trust artifact.

D-093 adds `create_d093_bootstrap_root.py`,
`check_d093_bootstrap_authorization.py`,
`verify_d093_bootstrap_evidence.py`, and
`check_d093_bootstrap_evidence.py`. The create tool is fixed to the exact
authorized development-host paths and transaction; its single authorized
execution has completed and must not be repeated. The authorization checker
uses only its no-key self-test by default; `--verify-action-host` additionally
rehashes the exact development-host interpreter and `ssh-keygen` bytes. The
read-only verifier hashes public artifacts and inspects the private file with
`lstat` only. The evidence checker defaults to repository-only validation;
`--verify-external` additionally verifies the development-host public root
without reading or hashing private content. None of these checks activates the
root or authorizes signing, P4-K, stand, Q15, or experiment work.

D-094 adds `check_d094_bootstrap_activation.py`. It validates the exact
activation authorization, append-only active lifecycle state, and v2 P4-K-A
successor. The checker proves that only bootstrap trust moved from null to the
accepted fingerprint, six inputs remain null, no signature or target-key
action occurred, and all stand/Q15/experiment authority remains false. Its
`--verify-external` mode calls only the D-093 read-only public/private-metadata
verifier.

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
