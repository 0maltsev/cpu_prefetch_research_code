# Stage 17 stand handoff

Status: **unexecuted**. These are executable command contracts, not authority.
The repository supplies fixed schemas, validators and actions; the owner must
supply every uppercase path, identity, timestamp and detached signature. Never
substitute a synthetic fixture or edit a validated JSON document by hand.

## Local hermetic rehearsal

From a clean extracted `STAGE17-HERMETIC-DRY-RUN-BUNDLE-v1` root, this single
command performs the full temporary 10-resolution/3-transition/pilot/seal/exit
workflow through the production validators and compiled test-linked dispatcher:

```sh
python3 -B tools/run_stage17_hermetic_handoff.py \
  --bundle-root "$PWD" \
  --pilot-archive /absolute/path/to/exact-hermetic-bundle.tar.gz \
  --pilot-sidecar /absolute/path/to/exact-hermetic-bundle.tar.gz.sha256
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
"$S17_PYTHON" -B "$S17_REPOSITORY/tools/stage17_operational_cli.py" \
  --repository-root "$S17_REPOSITORY" --evidence-root "$S17_EVIDENCE" init
"$S17_PYTHON" -B "$S17_REPOSITORY/tools/stage17_operational_cli.py" \
  --repository-root "$S17_REPOSITORY" --evidence-root "$S17_EVIDENCE" status
```

Expected initial result is `PREPARED`, zero resolutions, zero transitions and
ten missing inputs. `stage17_operational_cli.py` writes canonical JSON with
`O_EXCL`, fsyncs file and parent, verifies supplied detached signatures, and
validates a candidate journal before accepting its immutable successor. It
never signs, invents owner facts, or enables a fake backend.

For each externally produced typed artifact family, build its manifest without
manual JSON editing:

```sh
"$S17_PYTHON" -B "$S17_REPOSITORY/tools/stage17_operational_cli.py" \
  --repository-root "$S17_REPOSITORY" --evidence-root "$S17_EVIDENCE" \
  --pilot-archive "$S17_PILOT_ARCHIVE" --pilot-sidecar "$S17_PILOT_SIDECAR" \
  author-manifest --input-id S17-EXT-NNN --manifest-id OWNER_MANIFEST_ID \
  --stand-id OWNER_STAND_ID \
  --artifact ROLE:ARTIFACT_ID=/absolute/path/to/existing/typed-artifact \
  --output /absolute/new/path/manifest-v3.json
```

The repeated `--artifact` values must name the complete closed role family for
that input. The command validates actual bytes against the registered schema.

## Ordered real workflow

1. Use the fixed EXT001 authoring contract and the owner's signing system to
   produce canonical unsigned authorization/supporting-contract/envelope bytes
   plus a detached SSHSIG. Admit them with `admit-resolution`; then run
   `append-transition`. Expected journal states: resolution `000001`, T1
   `000002`, state `AUTHORIZED_FOR_READ_ONLY_PREFLIGHT`.

2. Execute the six fixed read-only observations with the current preflight
   executor. Author and admit the complete EXT002 manifest (attempt, six
   stdout, six stderr, six receipts, completion, observed trust/runtime and
   inventory records). No Q15 action is permitted before this succeeds.

3. Author EXT003 owner acceptance from the admitted EXT002 hashes, explicitly
   preserving `distinct_auditor=false` and `independent_review=false`. Admit
   EXT002/003 and append T2. Expected state: `PREFLIGHT_ACCEPTED`.

4. Canonically author the Q15-R request and unsigned authorization:

   ```sh
   "$S17_PYTHON" -B "$S17_REPOSITORY/tools/stage17_operational_cli.py" \
     --repository-root "$S17_REPOSITORY" --evidence-root "$S17_EVIDENCE" \
     author-request --action Q15-R --action-inputs "$Q15_R_TYPED_INPUTS" \
     --request-id "$Q15_R_REQUEST_ID" --authorization-id "$Q15_R_AUTH_ID" \
     --attempt-id "$Q15_R_ATTEMPT_ID" --output-root "$Q15_SESSION_ROOT" \
     --output "$Q15_R_REQUEST"
   "$S17_PYTHON" -B "$S17_REPOSITORY/tools/stage17_operational_cli.py" \
     --repository-root "$S17_REPOSITORY" --evidence-root "$S17_EVIDENCE" \
     author-authorization --request "$Q15_R_REQUEST" --actor "$Q15_ACTOR" \
     --reviewer "$Q15_REVIEWER" --issued-at-utc "$Q15_R_ISSUED_UTC" \
     --expires-at-utc "$Q15_R_EXPIRES_UTC" --output "$Q15_R_AUTHORIZATION"
   ```

   The owner signs those exact bytes externally. Start the phase-spanning Q15
   session with `stage17_q15_session_controller_v1.py --start`; it waits in
   `H0_SEALED_WAITING_FOR_Q15_W` without releasing its private mapping.

5. While Q15-R is waiting, collect, author and admit EXT004's exact
   qualification source/derived records. Canonically author and externally
   sign Q15-W. Continue the same session with
   `stage17_q15_session_controller_v1.py --continue-q15-w --control-id
   OWNER_CAPTURED_CONTROL_ID`. Q15-W re-reads live prestate, applies/readbacks,
   runs both probes, restores/readbacks, and retains failure/quarantine evidence
   if recovery cannot be proven. Admit EXT005 only from its typed outputs.

6. Verify the actual archive/sidecar and author EXT006 without manual JSON:

   ```sh
   "$S17_PYTHON" -B "$S17_REPOSITORY/tools/stage17_operational_cli.py" \
     --repository-root "$S17_REPOSITORY" --evidence-root "$S17_EVIDENCE" \
     --pilot-archive "$S17_PILOT_ARCHIVE" --pilot-sidecar "$S17_PILOT_SIDECAR" \
     author-ext006-contract --primary-custody-domain "$CUSTODY_DOMAIN_A" \
     --secondary-custody-domain "$CUSTODY_DOMAIN_B" \
     --output "$S17_EVIDENCE/manifests/ext006-contract-v3.json"
   ```

   Create both custody receipts, admit EXT006, then append T3 only after
   EXT004/005/006 are valid. Expected state:
   `READY_FOR_STAGE17_PHASE_AUTHORIZATION`.

7. For Q16a, Q16b and Q16c in that order, use `author-request`,
   `author-authorization`, external detached signing, `verify-signature`, then:

   ```sh
   "$S17_PYTHON" -B "$S17_REPOSITORY/tools/stage17_phase_controller_v3.py" \
     --execute --repository-root "$S17_REPOSITORY" \
     --operational-evidence-root "$S17_EVIDENCE" \
     --journal "$S17_EVIDENCE/journal/stage17-state-journal-000009.json" \
     --journal-directory "$S17_EVIDENCE/journal" \
     --authorization "$ACTION_AUTHORIZATION" --signature "$ACTION_SIGNATURE" \
     --pilot-archive "$S17_PILOT_ARCHIVE" --pilot-sidecar "$S17_PILOT_SIDECAR"
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

11. Prepare only unissued Phase 18 readiness, independent trust enrollment,
    authorization draft and empty access journal. No Stage 17 authority can
    advance Phase 18 from `PLANNED`.

At each admission use:

```sh
"$S17_PYTHON" -B "$S17_REPOSITORY/tools/stage17_operational_cli.py" \
  --repository-root "$S17_REPOSITORY" --evidence-root "$S17_EVIDENCE" \
  --pilot-archive "$S17_PILOT_ARCHIVE" --pilot-sidecar "$S17_PILOT_SIDECAR" \
  admit-resolution --input-id S17-EXT-NNN --actor "$OWNER_ACTOR" \
  --recorded-at-utc "$ACTUAL_RECORDED_UTC" \
  --receipt-evidence /absolute/path/to/verified-custody-receipt
```

Stop on the first missing hash, signature, state, capability, restoration,
quiescence, custody or storage failure. Preserve partial evidence; never retry
an attempted one-shot action.
