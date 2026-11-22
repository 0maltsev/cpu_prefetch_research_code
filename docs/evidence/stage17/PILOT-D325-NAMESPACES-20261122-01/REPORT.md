# D325: prospective namespace manifest and actual public-history previews

Bounded read-only previews found no S180 identity collision in91,723 stand and
36,812 local public metadata files. The prospective manifest fixes360 phase run
IDs,36 shared source declarations,52 namespaces including the root and one
original master seed. No namespace was registered, pilot source generated,
stand qualification started or research capture executed.

[D325](../../../decisions/0325-s180-prospective-identities-and-public-history.md)
defines exact identity conventions, scope, bounds and historical-format handling.

## Actual preview results

| Observation | Result |
|---|---|
| Stand selected public history | PASS;91,723 files,907,966,097 bytes, zero collisions/errors;219.668s |
| Stand coverage | All32 retained contexts and all11 observed registered archive families have their full canonical plan history |
| Initial local history | FAIL; zero collisions, but one legacy stdout wrapper and one missing full historical plan |
| Final local selected history | PASS;36,812 files,2,161,291,532 bytes, zero collisions/errors;172.991s |
| Namespace registration | Not performed |
| Qualified operational admission | Not issued; previews are not a launch decision |

Both retain the existing finite public JSON/JSONL scope and raw-payload tree
exclusions. They are not whole-disk no-collision proofs. Original file/directory
snapshots, mandatory historical plans and every observed archive FAMILY are
checked; partial history, mutation, malformed metadata and exhausted bounds fail.
The one-master/shared-namespace design is checked directly rather than forcing
Q16c's different identity counts or regex. No caller exclusion or unused flag
can bypass matching.

The stand preview executed tested code over SSH stdin with no installation or
stand writes. It used the version before the exact local stdout-format addition;
that source is retained verbatim and its digest matches the report's transported
source binding. The subsequent change is tested locally and its exact diff is
retained. This distinction is explicit: the preview is not qualified production
admission by the final administrative profile. Required launch admission must
bind its qualified producer and current reservation/window.

## Preserved local diagnostic and metadata-only recovery

The489-byte local prequalification export is a valid JSON object followed by
`scratch_roots 10`. Its original bytes and locator remain unchanged. The final
reader recognizes only its exact full SHA256 and exact framing, inspects both
the object and trailer, and reports the complete binding. Changed or unknown
wrappers still fail. `legacy-prequalification-stdout.txt` preserves those bytes.

The missing plan was the actual completed-Q16c1212db59 plan bound by D297/D306
constructed records. Exactly1,732,630 bytes of plan metadata were copied from
the retained stand locator and verified against its original SHA256 at both
ends. The copy stays in the selected local history. No raw observations were
copied, decoded again, edited or deleted. Transfer details are retained.

## Current resource observations and timing component

At22November18:34UTC the stand retained its previous boot,6,276,437,540,864 bytes
available on the root filesystem and262,027,116,544 MemAvailable bytes. No
`cpu_prefetch` comm-name match was observed. This limited process-name check is
not a complete quiescence, restoration, isolation or EXT009 proof.

A read-only100,300-entry extent inventory found the active program's archive
files occupy579,186,851,840 allocated bytes (579,167,629,194 logical bytes).
Metadata/ledger/working extents and empty older programs are retained in the
separate report. Raw contents were not read. This is a point observation, not
locked quota replay or complete resource admission; existing source/scratch,
whole-job limits and actual worst-case pilot/archive bounds still need checking.

Under the user's earlier timing-test authorization, the unchanged accepted
Philox/Decimal80 transform kernel ran three5000-transform synthetic batches on
the stand's Python3.14.4. It used a disjoint software-only seed/namespace, no
affinity/hardware changes, schedule files or actual pilot identities. Wall
times were0.772/0.659/0.659s. Original source hash and observed affinity are bound
in the timing report. This is engineering timing, not empirical research data.

The full36-source bank has90,210,834 expected shared arrivals at the frozen
rates/windows. Applying the measured per-load kernel costs to two passes gives
about6.79h for serial generation plus independent regeneration alone. The
previous collection/archive/validation analogy is6.39h, making about13.2h before
additional overhead. Actual counts remain ungenerated, and the extrapolation
excludes file/vector construction, metadata, qualification, native/codec/custody
work not represented by the analogy, summaries, recovery and restoration.
There is no verified whole-pilot ETA or permission to launch from this estimate.

## Software verification and remaining gates

Fourteen new namespace cases pass. Two final registered suites pass21 cases
(new14, existing continuation7); the original three Q16c matcher cases also
pass,24 distinct relevant cases total. Coverage includes escaped/serialized
identities, numeric encodings, all contexts, raw-tree non-entry, complete family
history, no exclusions, malformed/symlink input, hard bounds, snapshot mutation
and exact-only stdout framing. An initial test syntax typo was corrected before
the first13-case pass; its failed log remains preserved. No experiment failed.

Format, immutable protocol integrity, schema fixtures, canonical bytes, queue
provenance, runner and qualification schemas pass. Original public/Q16c auditors,
D322–324, accepted generator, native source and the frozen6151832-byte34247ce
worker remain unchanged. The worker SHA is
`7460102040fb9685af75131e6810494960b149fcf82d95d776347e4379d8f0fc`.
No native rebuild, sanitizer/codegen rerun, calibration, raw validation or
qualification was repeated for these Python-only changes.

Next: qualified production semantic checks and actual namespace reservation,
complete source/platform/resource/recovery/time admission, the parent owning
one durable attempt and archive/cleanup/restoration, and the S180 administrative
profile. Actual total ETA/budget must pass before first stand preparation or
qualification. Stage17 is incomplete and Stage18 remains deferred.

Only reports/manifests and the required historical plan metadata are on the PC.
Owned software fixtures were cleaned. Verified duplicate large build reports
are removed only after their exact evidence copies are checked; cleanup is
recorded separately. All completed Q16a708/Q16b120/Q16c180 evidence remains intact.
`manifest.json` binds implementation, decision, observations and evidence.
