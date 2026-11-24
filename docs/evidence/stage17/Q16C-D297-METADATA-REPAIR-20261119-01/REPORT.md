# D297 repaired metadata; full frozen unsigned construction passed

At19November2026 19:40:51UTC (22:40 Moscow), the stand verification confirmed
`FULL_FROZEN_UNSIGNED_CONSTRUCTION_PASS`. The actual existing7b7c263 unsigned
constructor reached `UNSIGNED_INPUTS_VALIDATED` after all original gates. It used
the already passed D295 qualification and a corrected incident-restoration input.
No clock/Q15 qualification, raw validation or measurement was repeated. No
experimental family was registered and no new execution window was started.

The repair selects E29 `q16c-continuation-recovery-1/restoration.json`,842bytes,
SHAad2eb45d, matching the unchanged runtime's fixed original-incident contract.
The earlier clock-restoration receipt remains untouched. Only the restoration
binding changes within the incident seed. Four configuration fields differ:
incident_reuse_inputs, packet_root, output_root and overlay. The latter rebinds
all7 byte-identical archive-source copies to the new packet's required namespace.
All other fields remain equal, including the native source, worker, candidate
inventory and original scientific inputs. The stopped launch configuration
remains SHA3359f966. The qualified candidate and scientific validators are not
modified.

The first software rehearsal exposed an error in the new workspace setup: the
archive descriptor still referred to sources in the old packet directory.
The original namespace check correctly rejected it. Its log and helper snapshot
are preserved. The next isolated rehearsal copied the exact source bytes and
rebound only their packet-local paths; full construction passed. These were
bounded software checks on CPU3 as UID1000, without signing, native execution,
hardware changes or experimental retries. This software failure did not consume
another experimental attempt.

The passed construction artifact is572bytes, SHA256
`5867405f24bb920ef684c9fbff296375d48f338f814137f0cb6ba2aa41719838`.
Its94-setting plan is1,732,630bytes, SHA256
`1212db59b9c12dd50837ca4b79897ddcd76a06fc4c3ea99b1fabd9b2b23b36a6`;
action inputs are1,977,503bytes, SHA256
`3d48b21c6b4204006a4975965d8ac64585577e64d9569484685fbd5a102c6fcb`.
Exact paths, actual configuration binding, unchanged worker hash, source-copy
checks and absence of family registration are in `stand-verification.json`.

Six focused tests and17 affected existing tests pass. They use the actual D285
incident receipt and D295 wrong-binding diagnostic, preserve historical inputs,
reject missing/changed/symlinked receipts, verify returned metadata bytes and
exercise exclusive output publication and all four configuration changes.
The CMake Python test list includes the new focused test module. No C/C++ behavior
changed, so no affected native sanitizer target or fresh native sanitizer result
is claimed. The final helper's single-read digest verification is covered by
the focused tests; the exact deployed helper snapshots used for both stand
rehearsals are preserved separately.

D295 remains stopped with no process/control group; its verified recovery and
passed qualification remain under their original identities. The guarded
compact_unevictable_allowed value is1. All86 original validated reports and all
Q16a708/Q16b120 remain preserved. The94 pending captures have not begun, and the
software-rehearsal artifact itself grants no execution authority.

[D298](../../../decisions/0298-q16c-qualified-same-window-continuation-proposal.md)
is a prospective one-continuation proposal. It would reuse qualification, rearm
isolation/guarding and collect94 within the original20November08:37:50 Moscow
deadline, with no new day. Its4–7h estimate and full8h44m20s remaining envelope
require launch before19November23:53:30 Moscow. It remains unapproved; no
administrative continuation or experiment has launched. The repository's
first-failure rule requires an explicit prospective exception before that step.
EXT007/Stage17 remain incomplete; Stage18 remains prohibited.

Only small public evidence was transferred. Source helpers, both software logs,
service lifecycle, test outputs and exact bindings are retained here. The
manifest binds these bytes. No private operational configuration or raw archive
was copied to the PC.
