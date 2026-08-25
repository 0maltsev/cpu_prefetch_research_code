# Q15-R controller-closure decision/input bundle

Status: **`ACCEPTED_Q15_R_P1_FOR_REPOSITORY_LOCAL_IMPLEMENTATION_NO_AUTHORITY`**

Prepared: 2026-08-24

Protocol: `2.0.0-pre.2`

Machine-readable record:
`config/q15/q15-r-decision-input-v1.json`

Record SHA-256:
`b99f6d07294c7505fba0cfee79bc425553e398be742280d71e3b467ee80739eb`

Schema: `config/schemas/q15-r-decision-input-v1.schema.json`

Q15-R-P1 accepted D-057 through D-060 on 2026-08-24. This is the complete
decision/input bundle for the work required before an
exact Q15-R authorization can be issued. It is not a Q15-R authorization. It
does not permit stand access, account/key changes, bundle transfer or install,
PMU/MSR/affinity/NUMA operation, dynamic qualification, Q15-W, calibration,
pilot, measurement, or confirmatory execution.

## Why the decision was required

The clean Q15-S3 release contains and hash-binds the accepted same-buffer
state machine, fixed Linux acquisition components, seven collectors, fake
backend tests, sanitizers, and dual-disassembler reports. As deliberately
frozen by ADR-0056, its public command surface has no production command that
starts the phase-spanning session or collectors. The existing split
authorization v1 describes ten logical Q15-R command kinds but does not bind
one executable controller graph and the live same-buffer handoff to Q15-W.

Ad-hoc shell orchestration would leave ordering, peer credentials, partial
failure, frame custody, expiry, and the same mapping's lifetime outside the
verified implementation. D-057 through D-060 close that engineering and
governance decision gap without changing scientific semantics. The local
implementation now passes, but the current sealed release remains Q15-S3 v1
and cannot safely receive Q15-R authority.

## Immutable inputs already available

### Measurement candidate

| Field | Exact value |
|---|---|
| Source revision | `693f00b3878ed027dc09aea7916f149874fb12a1` |
| Bundle profile | `STAGE17-PILOT-CANDIDATE-BUNDLE-v1` |
| Archive SHA-256 | `f94bb6922899caba24c26910bd1ba63018425d056fa5fd8282d1098415b8ace1` |
| Runner SHA-256 | `8bf2577750872a7595e62797e6ef278607f3bd5308820e2c21cc957ff192c2c7` |
| Runner profile | `STAGE17-STATIC-FIVE-PACKAGE-FAIL-CLOSED-v3` |
| CPU pairs | near `0/1`; far `0/26` |
| Relax mapping | `X86-PAUSE-ONE-PER-RELAX-SITE-v1` |
| Software-prefetch mapping | `X86-64-PREFETCHW-PREFETCHT0-v1` |
| Hardware-prefetch mapping | `INTEL-06_55H-MSR-1A4-DISABLE-0_3-v1` |

### Clean Q15-S3 component release

| Field | Exact value |
|---|---|
| Source revision | `7a9262987d4c52df95e9ed2ddc09cfa0d214b198` |
| Archive | `cpu-prefetch-q15-qualification-tool-2.0.0-7a92629-clean-542e64956985.tar.gz` |
| Archive bytes | `4138818` |
| Archive SHA-256 | `20acaded8002c130db725369c67013582dbcfccbd826a033a14658281387f848` |
| Source archive SHA-256 | `542e64956985e8921224cb5ab1130ee5c8e1896687a32f768c920ef6bcd4e8b2` |
| Q15 binary SHA-256 | `0e0e7a9c8fb52c9540fa93bb6a9f83dafe96e26927247ee122c0a5691ef7814a` |
| Manifest SHA-256 | `e6d8da78c5feb5ec3fa76a4526b26bf898826de89556c788cf1c4006df559bed` |
| SBOM SHA-256 | `7b7cb9eec2a5aa1bb9ad22ddb2000092a2ded3d3a43b82e1e90a9e5a0f346717` |
| Probe codegen report | `cb3368f851c5c5ac8e2c5ef5747ecf53f27e586b4b756798daa8386a1266f4aa` |
| Runtime codegen report | `e3c09d4fcbb759b0008c728d563f984d38bdb93e269ac70f3ebd6a1d99ab7014` |
| Repository license | `NO-LICENSE-GRANT` |

The archive's 101-file internal verification and its smoke, preflight,
qualification, and Q15 no-authority self-tests passed from a clean extraction.
Possession of this archive grants no authority.

### Read-only stand evidence

| Artifact | SHA-256 | Scope limit |
|---|---|---|
| `STAND-PREFLIGHT-XEON-CPU-FETCH-20260822-02` | `f8c6adbac92a9b163c45f71138946f3672eab7391fa27800fd909e028bc73087` | Inventory only; not dynamic qualification |
| `STAND-TOPOLOGY-XEON-CPU-FETCH-20260822-01-SHA256SUMS` | `c0c1e727315e17a6e54ef8857e5f4b6ceedbbf97a43f57a3c0659629108ca205` | Static topology only |
| `STAND-STORAGE-XEON-CPU-FETCH-20260822-01-SHA256SUMS` | `9469ad245de27d7211db2a746ae1016dfdebb3a8df07b846fe499ad290617c83` | One candidate stand domain; not custody proof |

The stand identity is `XEON-CPU-FETCH`. These artifacts do not establish
current state, privileges, actual accounts, keys, negative access tests,
dynamic clock/PMU/residency behavior, or Q15 eligibility.

## D-057 — fixed Q15-R controller and authorization v2

Classification: qualification controller and authorization-format
engineering.

Options considered: ad-hoc shell orchestration; arbitrary runtime collector
selectors; one statically fixed fail-closed controller; or declare the stand
ineligible.

Recommendation: implement `cpu_prefetch_q15_controller` profile
`Q15-R-STATIC-CONTROLLER-v1` and
`cpu-prefetch-q15-qualification-authorization/2`. Its only production entry is
`--execute-q15-r` with one exact canonical authorization and detached
signature. It accepts no arbitrary event, CPU, node, path, collector, phase,
schedule, namespace, or treatment selector.

The fixed graph must verify all bindings and roles; create the one private
same-buffer session; acquire the complete MSR prestate through the auditor;
run all Q15-R collectors and H0 regular/pointer probes; seal the immutable
evidence; and either hand the still-live mapping to one separately authorized
Q15-W or expire fail closed. Canonical evidence uses bounded inherited file
descriptors; the authorization handoff uses the accepted versioned local Unix
peer-credential protocol. Partial evidence is retained and no operation is
retried.

Scientific effect: none. Compatibility effect: the controller binary, graph,
transport, CLI, authorization bytes, and output contract become qualification
identity. Owners: controller, platform, security, custody, and audit. Gate:
before a controller-bearing clean release. Supersession: any material change
requires a new ADR, clean release, and requalification; scientific changes
require protocol review.

## D-058 — exact role IDs and custody policy IDs

Classification: least-privilege identity and two-domain custody engineering.

Options considered: one root identity; role labels over shared credentials;
four distinct least-privilege principals and two custody domains; or declare
the stand ineligible.

Recommendation:

| Role/domain | Proposed exact ID |
|---|---|
| Operator | `cpu-prefetch-q15-operator` |
| Controller | `cpu-prefetch-q15-controller` |
| Custodian | `cpu-prefetch-q15-custodian` |
| Auditor | `cpu-prefetch-q15-auditor` |
| Primary domain | `XEON-CPU-FETCH-MD3-Q15-CUSTODY` |
| Secondary domain | `DEVELOPMENT-REPOSITORY-Q15-CUSTODY` |
| Primary output root | `/var/lib/cpu-prefetch/q15-r` |
| Append-only policy | `Q15-PRIMARY-APPEND-ONLY-SEAL-THEN-TRANSFER-v1` |
| Transfer policy | `Q15-HASHED-SEALED-TRANSFER-WITH-RECEIPT-v1` |
| Partial policy | `Q15-RETAIN-PARTIAL-NEVER-PROMOTE-v1` |
| Recovery policy | `Q15-NO-OVERWRITE-NEW-ARTIFACT-ID-v1` |

Approval freezes these names and policies only. It does not create accounts,
keys, directories, groups, capabilities, permissions, or transfer endpoints.
The later Q15-R record must contain actual distinct credentials, fingerprints,
effective group/capability evidence, and negative OS tests for every forbidden
role/action pair.

Scientific effect: none. Compatibility effect: all actual role and custody
facts become authorization identity. Owners: security, platform, custody, and
audit. Gate: before any role/custody setup, then rechecked before Q15-R.
Supersession: any identity, credential, access, domain, path, quota, or policy
change requires fresh prospective authority and evidence.

## D-059 — prospective limits and stop conditions

Classification: resource, validity, and watchdog containment.

Options considered: leave values for execution time; derive them from
qualification/scientific observations; freeze conservative bounds before
execution; or declare the stand ineligible.

Recommendation:

| Limit | Proposed exact value | Rationale/boundary |
|---|---:|---|
| Authorization validity | `14400 s` | Four-hour maximum including separately authorized handoff; expiry fails closed |
| Same-buffer session wall | `14400 s` | Never outlives authorization |
| Active Q15-R collection wall | `1800 s` | Includes the frozen clock workload with margin; not an acceptance threshold |
| External start watchdog | `60 s` | Independent pre-start hang containment |
| Controller start polls | `18446744073709551615` | Exact u64 maximum; external watchdog supplies elapsed-time containment |
| Worker start polls | `18446744073709551615` | Same boundary; no in-measurement poll cap is introduced |
| CPU seconds | `7200 s` | Aggregate process limit |
| Output bytes | `2147483648` | 2 GiB hard authorization cap |
| Artifact count | `128` | Hard append-only count cap |
| Canonical frame payload | `16777216` | 16 MiB per-frame decode cap |
| Primary quota | `4294967296` | 4 GiB scoped custody quota |

Stop on the first authorization/release, role/access, peer/transport,
clock/affinity/NUMA/residency/fault/PMU/MSR, integrity/count/canonical/hash/
custody, expiry, limit, or disconnect failure. Preserve partial evidence,
never promote it, and never retry. These values govern qualification
containment only and may not be tuned from treatment effects or scientific
outcomes.

Scientific effect: none under that boundary. Compatibility effect: every
limit and stop rule becomes authorization identity. Owners: controller,
platform, security, custody, and protocol. Gate: before controller release and
again before final issuance. Supersession: a changed value requires a new
prospective record.

## D-060 — signature, issuance, and approval boundary

Classification: governance and phase authority.

Options considered: let this approval authorize execution; inherit earlier SSH
permission; approve closure work and require a later exact authorization; or
stop.

Decision: canonicalize the final authorization as `JCS-I64-v1` and sign
it using `OPENSSH-SSHSIG-ED25519-SHA512-v1` with namespace
`cpu-prefetch-q15-authorization`. The final record must name the actual signer
and public-key fingerprint and bind the canonical authorization SHA-256,
signature artifact ID/hash, exact UTC issuance/expiry, executable hashes,
literal argv, endpoint, roles, limits, outputs, and prerequisites. Independent
verification must precede execution.

Approval of this bundle authorizes only the repository-local implementation,
fake-backend/schema/sanitizer/codegen verification, and preparation of
non-authorizing role/custody setup artifacts. A later explicit approval of the
final signed Q15-R record is mandatory. Q15-W remains a distinct later phase
which cannot be prepared from guessed prestates.

Scientific effect: none. Compatibility effect: canonical bytes, scheme,
namespace, signer, validity, and hashes become immutable authority identity.
Owners: protocol, platform, security, controller, custody, and audit. Gate:
before repository closure and again before issuance. Supersession: any
signature, canonicalization, issuance, phase, or authority-boundary change
requires a new decision and authorization.

## Evidence still required after approval

Approval closes decisions, not operational evidence. Q15-R remains blocked
until all of the following exist:

1. one separately authorized clean commit and verified no-authority bundle
   containing exact controller source/binary/report/manifest/SBOM/archive
   hashes;
2. separately authorized stand setup of four real credentials and custody
   paths, with positive and complete negative OS access evidence;
3. fresh stand/inventory checks and exact executable paths/hashes, literal
   argv, endpoint, output IDs, quota, and transfer-receipt contract;
4. actual issue/expiry UTC, signer/key identity, canonical authorization hash,
   detached signature/hash, and independent verification record; and
5. separate explicit approval of that final signed Q15-R authorization.

No field above may be replaced by `latest`, a wildcard, root convenience, a
requested value copied as verified state, or an inferred platform value.

## Machine check

After configuring with the recorded dependency prefix:

```sh
cmake --build --preset dev-gcc --target q15-r-decision-check
cmake --build --preset dev-gcc --target qualification-schema-check
ctest --preset dev-gcc -R q15.r_decision_input --output-on-failure
```

The checker validates the Draft 2020-12 schema, local source/profile and stand
evidence hashes, exact decision order, fixed controller graph, distinct role
and custody IDs, numerical containment relationships, signature boundary, and
five negative mutations. It rejects any authority bit in this preparation.

## Exact approval statement

The owner accepted the following exact statement as Q15-R-P1:

> Q15-R-P1 — accept D-057 through D-060, including the exact fixed-controller
> graph, four proposed principal and custody IDs, numerical limits and stop
> conditions, and OpenSSH SSHSIG signature policy in the Q15-R decision/input
> bundle. Authorize repository-local implementation of the fixed Q15-R
> controller and authorization-v2 contract, fake-backend/schema/sanitizer/
> dual-disassembler verification, and preparation of no-authority role/custody
> setup artifacts only. Do not access the stand, create accounts or keys,
> transfer or install bundles, issue/sign/execute Q15-R, prepare or execute
> Q15-W, perform real PMU/MSR/affinity/NUMA operations or dynamic
> qualification, calibrate, pilot, measure, or execute confirmatory work. A
> later exact signed Q15-R authorization requires separate explicit approval.

Any shorter approval is interpreted only within the current no-authority
preparation scope and cannot authorize stand activity.
