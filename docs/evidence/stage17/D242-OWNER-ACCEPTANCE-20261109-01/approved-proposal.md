# D242 proposal: E25 transition-only authority recovery

- Status: **PROPOSED — awaiting explicit owner approval; not execution authority**
- Date: 2026-11-09
- Scope: the E25 administrative transition failure below, only
- Scientific design, capture population, estimators and limits: unchanged

## Observed incident

All 177 preserved captures passed independent validation. E25 release
`42f2ebb96f751319cd55fc1fabdcf7f91ab1c8d0` then passed both clock pairs and one
persistent Q15-R/W session. Q15-W reports restored completion, no quarantine,
and successful process cleanup. EXT001–006 are admitted in journal 000008.

The third readiness transition failed at 2026-11-09T07:17:38Z with
`transition authority is future/expired`. The original EXT001 authorization
was valid from 2026-11-08T13:51:40Z to 14:51:40Z; the independent prefix analysis
lasted more than 13 hours. The driver restored the owned isolation and
maintenance settings, verified at 2026-11-09T07:18:43Z. Q16 has not started.

The guard is functioning as specified: the current graph requires both EXT001
and EXT005 authorities to be current at that transition. The error was scheduling
the short-lived preflight authority before the long analysis, then failing to
check its expiry before qualification. This proposal does not relabel the
failed transition as successful or claim the expired authorization is current.

Exact retained incident bindings (all under the existing E25 evidence root):

| Artifact | SHA256 |
| --- | --- |
| `journal/stage17-state-journal-000008.json` | `c014861b826c4d66c1707570a8b61dfacaaab6976d4eafe7629bca90fe3219c5` |
| Unpublished `journal/stage17-state-journal-000009.json.candidate` | `ebbe3e802c69c094a16f50d35f77e1187de76f94535e1a17d6368885c194062d` |
| Failed `records/transition-003.json` | `4a173f1a14a2ee94911dabb0c78482052948688100722497be889d77e2864d0b` |
| `stage17-q15-w-result-v4.json` | `9cb1632bc8a500879a987dc3603f256518b77f2d57adc6cebc1f940b3419ff67` |
| `stage17-q15_w-completion-v4.json` | `afc31d56ef8e92ef53c70ffff68c4d21a9eebdb4c6af5f05943117de37447077` |
| `clock-qualification-v25-1/restoration.json` | `4d7a5261523d24a3f7ce8429ad63f5d1d1b596770af5d642c2ab27ca9abadd0a` |

The accepted original-prefix manifest remains
`dc0580e84f4bfde9cc7287bd624013c76ba533a500c6e3de3ace49f1d3e3dded`.
The [retained report inventory](../evidence/stage17/Q16A-PREFIX-COMPLETE-E25-20261109-01/qualification/inventory.json)
records the complete paths and byte lengths.

## Proposed owner decision

Authorize one versioned, signed **administrative transition-only** recovery
from this exact journal 000008 to `READY_FOR_STAGE17_PHASE_AUTHORIZATION`, using
the six already admitted resolutions and original successful qualification.
The owner approval permits implementation and verification of that narrow
recovery path; it is not permission to bypass an unimplemented check.

1. Preserve every existing authorization, result, resolution, journal, failed
   transition, unpublished candidate and restoration record byte-for-byte.
   Do not backdate, extend or rewrite an old authorization. Do not replace an
   existing resolution, reset the journal or manufacture a new measurement.
2. Issue a new owner-signed transition-only authorization after software
   verification. Its exact payload binds this decision, journal 000008, all six
   resolution hashes, original qualification/cleanup proofs, failed transition
   and candidate, prefix manifest, stand/boot, qualified source/runtime and
   target edge. Use actual issue time and a finite 1,800-second validity window.
   One consumption, zero automatic retry; expiry stops the action.
3. Version the administrative contract and verifier explicitly. Preserve the
   original historical validation and authorization chronology. The narrowly
   scoped new authorization replaces the requirement that the old EXT001 and
   EXT005 action authorities remain current **for this administrative edge
   only**. Their original executions still must have occurred under valid
   original authority. All other transitions retain the existing rules.
4. Append a new, separately named transition record after full validation;
   retain the failed transition/candidate as incident evidence. Extend the
   authenticated journal from its actual last committed state without changing
   its historical prefix. Reject wrong predecessor, missing original bytes,
   altered qualification, replay, future/expired authority or an invalid
   signature. No direct edit may simply set the state to ready.
5. Keep the measured worker, qualified source `42f2ebb`, original Q15 results
   and archive profile unchanged. Administrative tooling must identify its own
   revision separately and prove it authenticates the original qualification;
   it must not relabel that qualification as belonging to new measured code.
   If this cannot be established, stop instead of rerunning qualification.
6. After the administrative gate succeeds, reapply the existing tested CPU
   isolation mechanism once under a fresh preparation namespace. Verify actual
   boot, topology, effective CPUs/memory nodes, control-file identities,
   daemon-reload stability, current MSR prestate, lifetime and resources against
   the qualified requirements. Preserve the previous restoration. Any mismatch
   stops continuation; it cannot justify another clock/Q15 run automatically.
7. The existing D240 permission still covers only one separately signed
   531-capture continuation after all its gates pass. Do not restart the 177
   captures, their successful validation, the clock checks or Q15-R/W. Keep
   every reconciled FULL observation and failed original capture.

This decision grants no Q16 invocation on its own, no new scientific method,
no additional captures, no further continuation or top-up, no quota reset, and
no pilot/Stage18 authority. The next experimental Q15/Q16 failure still stops
dependent work with retention, reaping and verified restoration.

## Required verification before use

Targeted tests must reject an unrelated incident, changed journal/resolution/
worker/profile/boot, missing original successful result or cleanup, changed
historical bytes, widened target scope, bad signature, future/expired fresh
authority, duplicate consumption and attempted replay of the failed candidate.
Demonstrate unchanged historical behavior and actual original qualification
verification without executing clocks, Q15 or Q16. Retain the exact reviewed
recovery tooling and its evidence before signing the one transition payload.

No runtime guard is relaxed and no recovery is executed while this proposal
remains unapproved. Historical protocol directories remain immutable.
