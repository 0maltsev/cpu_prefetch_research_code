# Stage 17 stand handoff

Status: **unexecuted**. This is an ordered command contract, not authority.
Every uppercase value is an external input that must be supplied by the named
owner/custodian and recorded before the command may run. Never substitute
`latest`, a wildcard, an inferred stand value, or a synthetic fixture.

Use one create-exclusive append root, outside the source checkout:

```sh
export S17_REPOSITORY=/absolute/path/to/verified/extracted/pilot-candidate-bundle
export S17_EVIDENCE=/absolute/path/to/create-exclusive/stage17-evidence
export S17_JOURNAL_DIR="$S17_EVIDENCE/journal"
export S17_LATEST_JOURNAL="$S17_JOURNAL_DIR/stage17-state-journal-000000.json"
test -f "$S17_REPOSITORY/BUNDLE_MANIFEST.json"
python3 "$S17_REPOSITORY/validators/verify_stand_bundle.py" --root "$S17_REPOSITORY"
test ! -e "$S17_EVIDENCE"
install -d -m 0700 "$S17_EVIDENCE" "$S17_JOURNAL_DIR"
install -m 0600 "$S17_REPOSITORY/config/stage17/journal/stage17-state-journal-000000.json" "$S17_LATEST_JOURNAL"
```

The create step requires separate operational authority because it mutates the
stand filesystem. The repository does not grant it. Every record below is
canonical JSON, create-exclusive, and referenced by repository-independent
path, byte count and SHA-256 from the next journal snapshot. Validate each
snapshot before making it latest:

```sh
PYTHONPATH=/absolute/offline/python-prefix/lib/python3.14/site-packages \
python3 "$S17_REPOSITORY/tools/stage17_state_journal_v7.py" \
  --print-status --repository-root "$S17_REPOSITORY" \
  --journal "$S17_LATEST_JOURNAL" --journal-directory "$S17_JOURNAL_DIR"
```

The production CLI never admits synthetic evidence. Do not edit a validated
snapshot in place.

## Ordered workflow

1. Issue the exact bounded S17-EXT-001 read-only preflight authorization and
   detached signature. Expected paths:
   `$S17_EVIDENCE/ext001/authorization.json`, `authorization.json.sig`,
   `supporting-contract.json`, `semantic-envelope.json`, and the first
   resolution/journal successor. Validate it; append transition T1 only after
   the resolution is admitted.

2. Execute the six fixed read-only preflight observations through the current
   preflight executor. Expected root: `$S17_EVIDENCE/ext002/preflight/` with
   attempt, six stdout, six stderr, six receipts, runtime/trust identities,
   completion, and aggregate manifest. No Q15/Q16 action is permitted here.

3. Create the owner acceptance at
   `$S17_EVIDENCE/ext003/owner-acceptance.json`, explicitly recording
   `distinct_auditor=false`, `independent_review=false`, and the exact admitted
   EXT002 runtime/trust hashes. Admit EXT002 and EXT003, then append T2.

4. Collect EXT004 qualification source artifacts and nine typed records under
   `$S17_EVIDENCE/ext004/`. Every `*_sha256` in a qualification record must
   equal a source artifact hash. Admit the aggregate manifest only after all
   source bytes rehash.

5. Issue and execute Q15-R, then separately issue and execute Q15-W. Controller
   v2 uses the worker observed in EXT002/003 and refuses self-selected trust:

   ```sh
   PYTHONPATH=/absolute/offline/python-prefix/lib/python3.14/site-packages \
   python3 "$S17_REPOSITORY/tools/stage17_phase_controller_v2.py" --execute \
     --repository-root "$S17_REPOSITORY" \
     --journal "$S17_LATEST_JOURNAL" --journal-directory "$S17_JOURNAL_DIR" \
     --authorization "$S17_EVIDENCE/ext005/ACTION/authorization.json" \
     --signature "$S17_EVIDENCE/ext005/ACTION/authorization.json.sig"
   ```

   Replace `ACTION` first with `q15-r` and then with `q15-w`; the signed action
   and request must already name that exact fixed action. Q15-W must prove
   restoration or quarantine and cannot become EXT005 completion otherwise.

6. Build the clean pilot-candidate release after the Stage 17B commit, transfer
   it under separately approved custody, and verify its real archive/sidecar
   bytes. Expected EXT006 records:
   `$S17_EVIDENCE/ext006/archive.tar.gz`, `archive.tar.gz.sha256`,
   `custody-receipt.json`, and `resolution.json`. The archive worker member
   must be byte-identical to the EXT002/003 observed runner.

7. Admit EXT004, the final Q15-W EXT005 family, and EXT006. Append T3 only after
   all three resolutions are valid. The computed graph state must be
   `READY_FOR_STAGE17_PHASE_AUTHORIZATION`.

8. Separately issue and execute Q16a, Q16b and Q16c with controller v2 using the
   command in step 5 and authorization roots `$S17_EVIDENCE/ext007/q16a`,
   `q16b`, and `q16c`. Q16a must retain `q16a-trace-v2.json`; Q16b/Q16c must
   retain producer/consumer raw streams. Admit EXT007 only after all three
   signed families and `calibration-freeze.json` pass.

9. Freeze EXT008 under `$S17_EVIDENCE/ext008/`: exact pilot plan, schedule,
   runner admission, run IDs, seeds, horizons, capacities, packages, D2,
   stop/resource limits, and artifact names. It must reference admitted
   EXT001..007 and may not read outcomes.

10. Admit EXT009 under `$S17_EVIDENCE/ext009/`: storage budget, two independent
    custody-domain records, copy ledger, and recovery test with exact paths,
    ownership, permissions, byte counts and hashes.

11. Issue EXT010 only after EXT001..009 are admitted. Expected files:
    `$S17_EVIDENCE/ext010/authorization.json`, `authorization.json.sig`, and
    `request.json`. They bind the exact nine resolution hashes and frozen pilot
    run set and grant no Phase 18 authority.

12. Execute the blinded pilot exactly once using controller v2:

    ```sh
    PYTHONPATH=/absolute/offline/python-prefix/lib/python3.14/site-packages \
    python3 "$S17_REPOSITORY/tools/stage17_phase_controller_v2.py" --execute \
      --repository-root "$S17_REPOSITORY" \
      --journal "$S17_LATEST_JOURNAL" --journal-directory "$S17_JOURNAL_DIR" \
      --authorization "$S17_EVIDENCE/ext010/authorization.json" \
      --signature "$S17_EVIDENCE/ext010/authorization.json.sig" \
      --pilot-archive "$S17_EVIDENCE/ext006/archive.tar.gz" \
      --pilot-sidecar "$S17_EVIDENCE/ext006/archive.tar.gz.sha256"
    ```

13. Seal the pilot attempt, result, completion, raw artifacts and manifest under
    `$S17_EVIDENCE/pilot/`. A process exit code is never completion; the typed
    result, fixed output set, hashes, lineage and quiescence proofs must pass.

14. Append the Stage 17 exit journal in order:
    `PILOT_AUTHORIZED -> PILOT_EXECUTED -> PILOT_EVIDENCE_SEALED ->
    STAGE17_COMPLETE -> PHASE18_HANDOFF_PREPARED`. Expected root:
    `$S17_EVIDENCE/stage17-exit/`. Each transition binds admitted real records.

15. Create the Stage 17 completion statement and treatment-blind freeze only
    from those admitted pilot records. Synthetic or caller-supplied readiness
    booleans are forbidden.

16. Prepare, but do not execute, separate Phase 18 readiness, independent trust
    context, authorization draft and empty access journal under
    `$S17_EVIDENCE/phase18/`. Phase 18 requires a separately signed authority
    before the strict chronology can leave `PLANNED`.

Stop at the first missing hash, failed semantic verifier, expired/future
authorization, state mismatch, restoration/quarantine failure, custody loss,
typed-result failure, live process group, or storage failure. Retain partial
evidence and never retry an attempted one-shot action.
