# Stage 17 stand handoff

Status: **D-120, D-121 and D-122 terminal evidence retained; D-123
replacement handoff unexecuted**. These are executable command contracts, not
authority.
The repository supplies fixed schemas, validators and actions; the owner must
supply every uppercase path, identity, timestamp and detached signature. Never
substitute a synthetic fixture or edit a validated JSON document by hand.

## Local hermetic rehearsal

From a clean extracted `STAGE17-HERMETIC-DRY-RUN-BUNDLE-v2` root, this single
command performs the full temporary 10-resolution/3-transition/pilot/seal/exit
workflow through the production validators and compiled test-linked dispatcher:

```sh
python3 -B tools/run_stage17_hermetic_handoff.py \
  --bundle-root "$PWD" \
  --bundle-directory /absolute/path/containing/exact-hermetic-bundle-and-sidecar
```

It creates no checked-in record and grants no stand or Phase 18 authority.

## Operational roots and canonical CLI

Use the verified extracted production bundle as the immutable repository root
and a different, create-exclusive owner directory as mutable evidence:

```sh
export S17_REPOSITORY=/absolute/path/to/verified/extracted/pilot-candidate-bundle
export S17_EVIDENCE=/absolute/path/to/new/stage17-operational-evidence
export S17_PYTHON=/absolute/offline/python-prefix/bin/python3
test -f "$S17_REPOSITORY/BUNDLE_MANIFEST.json"
"$S17_PYTHON" -B "$S17_REPOSITORY/validators/verify_stand_bundle.py" \
  --root "$S17_REPOSITORY"
test ! -e "$S17_EVIDENCE"
install -d -m 0700 "$S17_EVIDENCE"
"$S17_PYTHON" -B "$S17_REPOSITORY/tools/stage17_operational_cli_v11.py" \
  --repository-root "$S17_REPOSITORY" --evidence-root "$S17_EVIDENCE" \
  init --materialize-admission-root
export S17_RELEASE_BUNDLE_ROOT="$S17_REPOSITORY"
export S17_REPOSITORY="$S17_EVIDENCE/admission-root"
test -f "$S17_EVIDENCE/manifests/stage17-admission-root-binding-v1.json"
"$S17_PYTHON" -B "$S17_REPOSITORY/tools/stage17_operational_cli_v11.py" \
  --repository-root "$S17_REPOSITORY" --evidence-root "$S17_EVIDENCE" status
S17_JOURNAL=$("$S17_PYTHON" -B \
  "$S17_REPOSITORY/tools/stage17_operational_cli_v11.py" \
  --repository-root "$S17_REPOSITORY" --evidence-root "$S17_EVIDENCE" \
  journal-path)
test -f "$S17_JOURNAL"
```

Expected initial result is `PREPARED`, zero resolutions, zero transitions and
ten missing inputs. `stage17_operational_cli_v11.py` writes canonical JSON with
`O_EXCL`, fsyncs file and parent, verifies supplied detached signatures, and
validates a candidate journal before accepting its immutable successor. It
never signs, invents owner facts, or enables a fake backend.

For each externally produced typed artifact family, build its manifest without
manual JSON editing:

```sh
"$S17_PYTHON" -B "$S17_REPOSITORY/tools/stage17_operational_cli_v11.py" \
  --repository-root "$S17_REPOSITORY" --evidence-root "$S17_EVIDENCE" \
  --pilot-archive "$S17_PILOT_ARCHIVE" --pilot-sidecar "$S17_PILOT_SIDECAR" \
  author-manifest --input-id S17-EXT-NNN --manifest-id OWNER_MANIFEST_ID \
  --stand-id OWNER_STAND_ID \
  --artifact ROLE:ARTIFACT_ID=/absolute/path/to/existing/typed-artifact \
  --output /absolute/new/path/manifest-v4.json
```

The repeated `--artifact` values must name the complete closed role family for
that input. The command validates actual bytes against the registered schema.

## Ordered real workflow

0. Preserve the three terminal implementation-defect transactions. D-120 stopped
   before marker; its existing typed receipt remains immutable. D-121 created
   attempt v8 but stopped before `Popen`, and its output root must still contain
   exactly that marker. D-122 reached T1 but stopped before marker/transport
   during action-time terminal-schema revalidation, and its output root must
   remain empty. Create the D-121 and D-123 typed receipts once; they deny retry
   and require a new transaction:

   ```sh
   "$S17_PYTHON" -B \
     "$S17_REPOSITORY/tools/author_stage17_post_marker_blocker_v1.py" \
     --blocker-id "$D121_BLOCKER_ID" --actor "$OWNER_ACTOR" \
     --journal "$D121_STOPPED_JOURNAL" \
     --authorization "$D121_STOPPED_AUTHORIZATION" \
     --resolution "$D121_STOPPED_RESOLUTION" \
     --transition "$D121_STOPPED_TRANSITION" \
     --output-root "$D121_MARKER_ONLY_PREFLIGHT_OUTPUT_ROOT" \
     --output "$D121_BLOCKER_RECEIPT"
   "$S17_PYTHON" -B \
     "$S17_REPOSITORY/tools/author_stage17_action_revalidation_blocker_v1.py" \
     --blocker-id "$D123_BLOCKER_ID" --actor "$OWNER_ACTOR" \
     --journal "$D122_STOPPED_JOURNAL" \
     --authorization "$D122_STOPPED_AUTHORIZATION" \
     --resolution "$D122_STOPPED_RESOLUTION" \
     --transition "$D122_STOPPED_TRANSITION" \
     --output-root "$D122_EMPTY_PREFLIGHT_OUTPUT_ROOT" \
     --failure-category CURRENT_RECEIPT_SCHEMA_BINDING_KEY_MISMATCH \
     --error-code ACTION_REVALIDATION_SCHEMA_BINDING_MISMATCH \
     --output "$D123_BLOCKER_RECEIPT"
   ```

1. Create the fixed EXT001 authorization/supporting-contract/envelope without
   editing JSON. All uppercase values are owner inputs; the command validates
   the exact Ed25519 host-key bytes, known-hosts line, transport identity,
   bundle locators, finite UTC window and fixed read-only policy. Supply
   predecessor evidence for D-120/D-121/D-123 exactly one of two mutually
   exclusive ways (ADR-0124, accepted): the three `--*-blocker` flags shown
   below when real blocker-receipt evidence exists, or
   `--no-predecessor-attestation "$D124_NO_PREDECESSOR_ATTESTATION"` in their
   place when an exhaustive real search -- never assumed -- found none to
   bind. Author that attestation record with `tools/author_stage17_no_
   predecessor_attestation_v1.py` first if using it.

   ```sh
   "$S17_PYTHON" -B "$S17_REPOSITORY/tools/stage17_operational_cli_v11.py" \
     --repository-root "$S17_REPOSITORY" --evidence-root "$S17_EVIDENCE" \
     --pilot-archive "$S17_PILOT_ARCHIVE" \
     --pilot-sidecar "$S17_PILOT_SIDECAR" author-ext001 \
     --stand-id "$OWNER_STAND_ID" --ssh-target "$OWNER_SSH_TARGET" \
     --known-hosts-host "$OWNER_KNOWN_HOSTS_HOST" \
     --pinned-host-public-key "$OWNER_PINNED_HOST_PUBLIC_KEY" \
     --pinned-known-hosts "$OWNER_PINNED_KNOWN_HOSTS" \
     --transport-identity "$OWNER_TRANSPORT_IDENTITY" \
     --bundle-root-locator "$S17_RELEASE_BUNDLE_ROOT" \
     --capture-id "$EXT001_CAPTURE_ID" \
     --captured-at-utc "$EXT001_CAPTURED_AT_UTC" \
     --preflight-evidence-root "$EXT001_PREFLIGHT_OUTPUT_ROOT" \
     --pre-marker-blocker "$D120_BLOCKER_RECEIPT" \
     --post-marker-blocker "$D121_BLOCKER_RECEIPT" \
     --action-revalidation-blocker "$D123_BLOCKER_RECEIPT" \
     --actor "$OWNER_ACTOR" --issued-at-utc "$EXT001_ISSUED_AT_UTC" \
     --expires-at-utc "$EXT001_EXPIRES_AT_UTC" \
     --authorization-id "$EXT001_AUTHORIZATION_ID" \
     --attempt-id "$EXT001_ATTEMPT_ID" --contract-id "$EXT001_CONTRACT_ID" \
     --envelope-id "$EXT001_ENVELOPE_ID" \
     --output-directory "$S17_REPOSITORY/evidence/ext001-v14"
   "$S17_PYTHON" -B "$S17_REPOSITORY/tools/stage17_operational_cli_v11.py" \
     --repository-root "$S17_REPOSITORY" --evidence-root "$S17_EVIDENCE" \
     --pilot-archive "$S17_PILOT_ARCHIVE" \
     --pilot-sidecar "$S17_PILOT_SIDECAR" admit-resolution \
     --input-id S17-EXT-001 --actor "$OWNER_ACTOR" \
     --recorded-at-utc "$EXT001_RECORDED_AT_UTC" \
     --repository-evidence "$S17_REPOSITORY/evidence/ext001-v14/envelope-v14.json" \
     --authorization-file "$S17_REPOSITORY/evidence/ext001-v14/authorization-v11.json"
   "$S17_PYTHON" -B "$S17_REPOSITORY/tools/stage17_operational_cli_v11.py" \
     --repository-root "$S17_REPOSITORY" --evidence-root "$S17_EVIDENCE" \
     --pilot-archive "$S17_PILOT_ARCHIVE" \
     --pilot-sidecar "$S17_PILOT_SIDECAR" append-transition \
     --actor "$OWNER_ACTOR" --timestamp-utc "$EXT001_TRANSITION_UTC"
   ```

   Expected journal states: resolution `000001`, T1 `000002`, state
   `AUTHORIZED_FOR_READ_ONLY_PREFLIGHT`. The v1 journal evidence policy is
   satisfied inside the private admission snapshot; the release bundle root
   remains byte-identical and independently verifiable. The
   `--no-predecessor-attestation` substitution (ADR-0124, accepted) is
   mutually exclusive with the three `--*-blocker` flags, enforced before
   any file I/O; use exactly one of the two, never both, never neither.

2. Execute the six fixed read-only observations with the current preflight
   executor. Author and admit the complete EXT002 manifest (attempt, six
   stdout, six stderr, six receipts, completion, observed trust/runtime and
   inventory records). No Q15 action is permitted before this succeeds.

   ```sh
   S17_JOURNAL=$("$S17_PYTHON" -B \
     "$S17_REPOSITORY/tools/stage17_operational_cli_v11.py" \
     --repository-root "$S17_REPOSITORY" --evidence-root "$S17_EVIDENCE" \
     journal-path)
   "$S17_PYTHON" -B \
     "$S17_REPOSITORY/tools/stage17_read_only_preflight_executor_v13.py" \
     --execute --repository-root "$S17_REPOSITORY" \
     --journal "$S17_JOURNAL" \
     --journal-directory "$S17_EVIDENCE/journal"
   ```

   Policy v21 binds this policy-v15/executor-v13 preflight and journal
   v17/controller v9 for later actions. Predecessor controllers are immutable
   and must not be substituted. A failed or partial preflight remains terminal;
   retain its evidence and issue no automatic retry.

3. Author EXT002 from the complete retained observation family, then author
   EXT003 owner acceptance from the admitted EXT002 hashes, explicitly
   preserving `distinct_auditor=false` and `independent_review=false`. Admit
   EXT002/003 through CLI v11 and append T2. Expected state:
   `PREFLIGHT_ACCEPTED`. Revalidate the resulting journal with policy v21
   before preparing Q15.

4. Canonically author the Q15-R request and unsigned authorization:

   ```sh
   "$S17_PYTHON" -B "$S17_REPOSITORY/tools/stage17_operational_cli_v11.py" \
     --repository-root "$S17_REPOSITORY" --evidence-root "$S17_EVIDENCE" \
     author-request --action Q15-R --action-inputs "$Q15_R_TYPED_INPUTS" \
     --request-id "$Q15_R_REQUEST_ID" --session-id "$Q15_SESSION_ID" \
     --authorization-id "$Q15_R_AUTH_ID" \
     --attempt-id "$Q15_R_ATTEMPT_ID" --output-root "$Q15_SESSION_ROOT" \
     --output "$Q15_R_REQUEST"
   "$S17_PYTHON" -B "$S17_REPOSITORY/tools/stage17_operational_cli_v11.py" \
     --repository-root "$S17_REPOSITORY" --evidence-root "$S17_EVIDENCE" \
     author-authorization --request "$Q15_R_REQUEST" --actor "$Q15_ACTOR" \
     --reviewer "$Q15_REVIEWER" --issued-at-utc "$Q15_R_ISSUED_UTC" \
     --expires-at-utc "$Q15_R_EXPIRES_UTC" --output "$Q15_R_AUTHORIZATION"
   ```

   The owner signs those exact bytes externally and verifies the detached
   signature through `verify-signature`. Start the phase-spanning Q15 session;
   it waits in `H0_SEALED_WAITING_FOR_Q15_W` without releasing its private
   mapping:

   ```sh
   S17_JOURNAL=$("$S17_PYTHON" -B \
     "$S17_REPOSITORY/tools/stage17_operational_cli_v11.py" \
     --repository-root "$S17_REPOSITORY" --evidence-root "$S17_EVIDENCE" \
     journal-path)
   "$S17_PYTHON" -B \
     "$S17_REPOSITORY/tools/stage17_q15_session_controller_v6.py" --start \
     --repository-root "$S17_REPOSITORY" --journal "$S17_JOURNAL" \
     --journal-directory "$S17_EVIDENCE/journal" \
     --operational-evidence-root "$S17_EVIDENCE" \
     --authorization "$Q15_R_AUTHORIZATION" --signature "$Q15_R_SIGNATURE" \
     --pilot-archive "$S17_PILOT_ARCHIVE" \
     --pilot-sidecar "$S17_PILOT_SIDECAR"
   ```

5. While Q15-R is waiting, collect, author and admit EXT004's exact
   qualification source/derived records. Canonically author and externally
   sign Q15-W. Continue the same session with
   the following command, using the exact control ID printed by the waiting
   start process. Q15-W re-reads live prestate, applies/readbacks,
   runs both probes, restores/readbacks, and retains failure/quarantine evidence
   if recovery cannot be proven. Admit EXT005 only from its typed outputs.

   ```sh
   "$S17_PYTHON" -B \
     "$S17_REPOSITORY/tools/stage17_q15_session_controller_v6.py" \
     --continue-q15-w --control-id "$Q15_CONTROL_ID" \
     --journal "$S17_JOURNAL" \
     --journal-directory "$S17_EVIDENCE/journal" \
     --operational-evidence-root "$S17_EVIDENCE" \
     --authorization "$Q15_W_AUTHORIZATION" --signature "$Q15_W_SIGNATURE" \
     --pilot-archive "$S17_PILOT_ARCHIVE" \
     --pilot-sidecar "$S17_PILOT_SIDECAR"
   ```

6. Verify the actual archive/sidecar and author EXT006 without manual JSON:

   ```sh
   "$S17_PYTHON" -B "$S17_REPOSITORY/tools/stage17_operational_cli_v11.py" \
     --repository-root "$S17_REPOSITORY" --evidence-root "$S17_EVIDENCE" \
     --pilot-archive "$S17_PILOT_ARCHIVE" --pilot-sidecar "$S17_PILOT_SIDECAR" \
     author-ext006-contract --primary-custody-domain "$CUSTODY_DOMAIN_A" \
     --secondary-custody-domain "$CUSTODY_DOMAIN_B" \
     --contract-id "$EXT006_CONTRACT_ID" \
     --output "$S17_EVIDENCE/manifests/ext006-contract-v4.json"
   ```

   Create both custody receipts, admit EXT006, then append T3 only after
   EXT004/005/006 are valid. Expected state:
   `READY_FOR_STAGE17_PHASE_AUTHORIZATION`.

7. For Q16a, Q16b and Q16c in that order, use `author-request`,
   `author-authorization`, external detached signing, `verify-signature`, then:

   ```sh
   "$S17_PYTHON" -B "$S17_REPOSITORY/tools/stage17_operational_cli_v11.py" \
     --repository-root "$S17_REPOSITORY" --evidence-root "$S17_EVIDENCE" \
     --pilot-archive "$S17_PILOT_ARCHIVE" --pilot-sidecar "$S17_PILOT_SIDECAR" \
     execute-action --authorization "$ACTION_AUTHORIZATION" \
     --signature "$ACTION_SIGNATURE"
   ```

   Admit EXT007 only after the three complete result families and calibration
   freeze validate.

8. Freeze and admit EXT008's complete 180-cell plan and registered repetitions,
   exact schedules/seeds/run IDs/limits/admissions and predecessor hashes.
   Admit EXT009 only after storage budget, two custody domains, copy ledger and
   recovery evidence validate.

9. Canonically author and externally sign EXT010 only after EXT001..009 are
   admitted. Execute `STAGE17-BLINDED-PILOT` with the same controller command.
   The worker accepts only the fixed full plan and produces the complete raw,
   joined, integrity, residency, hardware-state and sealed-manifest family.

10. Validate controller attempt/result/completion and sealed pilot bytes, then
    create the Stage 17 exit chain. Completion is derived from admitted EXT010
    and those exact hashes; a handwritten readiness boolean is rejected.

    ```sh
    "$S17_PYTHON" -B "$S17_REPOSITORY/tools/stage17_operational_cli_v11.py" \
      --repository-root "$S17_REPOSITORY" --evidence-root "$S17_EVIDENCE" \
      --pilot-archive "$S17_PILOT_ARCHIVE" \
      --pilot-sidecar "$S17_PILOT_SIDECAR" \
      derive-stage17-completion --pilot-output-root "$PILOT_OUTPUT_ROOT" \
      --output "$S17_EVIDENCE/stage17-completion-v4.json"
    ```

11. Prepare only unissued Phase 18 readiness, independent trust enrollment,
    authorization draft and empty access journal. No Stage 17 authority can
    advance Phase 18 from `PLANNED`.

    ```sh
    "$S17_PYTHON" -B "$S17_REPOSITORY/tools/stage17_operational_cli_v11.py" \
      --repository-root "$S17_REPOSITORY" --evidence-root "$S17_EVIDENCE" \
      prepare-phase18-readiness \
      --stage17-completion "$S17_EVIDENCE/stage17-completion-v4.json" \
      --created-at-utc "$ACTUAL_PHASE18_READINESS_UTC" \
      --output "$S17_EVIDENCE/phase18-readiness-v4.json"
    ```

    Without a separately pre-admitted independent Phase 18 trust anchor this
    command must emit `BLOCKED_EXTERNAL_PHASE18_TRUST_REQUIRED`; it never
    creates Phase 18 authorization.

At each admission use:

```sh
"$S17_PYTHON" -B "$S17_REPOSITORY/tools/stage17_operational_cli_v11.py" \
  --repository-root "$S17_REPOSITORY" --evidence-root "$S17_EVIDENCE" \
  --pilot-archive "$S17_PILOT_ARCHIVE" --pilot-sidecar "$S17_PILOT_SIDECAR" \
  admit-resolution --input-id S17-EXT-NNN --actor "$OWNER_ACTOR" \
  --recorded-at-utc "$ACTUAL_RECORDED_UTC" \
  --receipt-evidence /absolute/path/to/verified-custody-receipt
```

Stop on the first missing hash, signature, state, capability, restoration,
quiescence, custody or storage failure. Preserve partial evidence; never retry
an attempted one-shot action.
