# D288 stopped before raw validation; metadata reader defect confirmed

Checked19November2026 at14:41:38UTC (17:41:38Moscow). The stand service is failed,
MainPID0, exit1. It stopped at **13:50:18UTC (16:50:18Moscow)** after124.538s from
its13:48:13UTC start. The prior running report was the startup observation.
The6–9h ETA is withdrawn. No automatic retry, new window or clock reset occurred.

Progress and restoration:

- 0/86 independent reports; the raw-analysis output root was never created.
- 0/94 new captures; no qualification, platform-guard acquisition or new-family
 registration/construction started.
- All87 original checkpoint/custody sets remain:86 native-complete plus failed86.
 The failed86 checkpoint and original failure hashes still match the fixed
 incident anchors57dc6ede/17540e9e. All708 Q16a and120 Q16b reports remain retained.
- Both supervisor and independent recovery report verified=true, errors=[].
 Actual MSR readbacks match the recorded complete zero values on CPUs0/1/8.
 Compaction remains1; no experiment restart was performed during diagnosis.

Confirmed cause: `stage17_q16c_retained_prefix_v1.collect_metadata` passes the
public registry's binding objects to a ProgramStore loaded from the original
sealed private archive namespace. The metadata adapter compares dataclass
objects directly. Python dataclass equality requires the same class identity,
so identical fields from two module instances compare unequal.

The read-only stand reproduction used the actual original runtime/profile and
capture0 checkpoint/receipt. Both bindings contain exactly14343 bytes and SHA256
28258ceebf63913da41da3d7f35118bd9c2dbc090a0d8e0a4505472e3a8125d6.
The caller class is `stage17_formal_archive_v1.PhysicalBinding`; the reader class
is `_d273_archive_333567_stage17_formal_archive_v1.PhysicalBinding`. Their fields
are equal; their objects compare false. The original caller reproduces
`CustodyError: metadata binding differs`; the same reader accepts the binding
constructed in its own namespace. No ProgramStore transaction, raw decode,
measurement, source modification or scientific validation retry was performed
by this probe. This confirms an integration defect; it does not establish full
scientific/raw-data validity.

The existing tests did not exercise this actual cross-namespace registry/store
boundary. The smallest repair direction is a private registry view using the
store's exact archive/custody types throughout checkpoint, receipt and ledger
verification, with real mixed-namespace metadata regression coverage. Preserve
all byte/hash/inode/ledger/scientific gates and the historical runtime unchanged.
No production fix was made under this status-check request.

Plan status: source/package preparation completed; prefix metadata admission
FAILED; all downstream qualification/collection/analysis steps blocked. Under
the approved D288 first-failure/no-retry rule, the job remains stopped. A verified
repair and an explicit continuation decision are needed before another attempt;
this report does not authorize one or change the original deadlines. EXT007 and
Stage17 remain incomplete; Stage18 remains prohibited.
