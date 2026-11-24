# Q16c first native stop — 18 November 2026 Moscow

Q16c has **zero successful measurements**. At 22:18:27 UTC on 17 November,
the first capture stopped with native `exception` (13), before mappings,
session creation or raw publication. Its one final checkpoint and one durable
custody receipt contain **no raw artifacts**. They are retained failure evidence,
not a completed capture or an independently valid calibration.

The family and supervisor stopped without retry. Hardware readbacks match all
three original prestate values; the native worker was reaped and its process
group is gone. Isolation and maintenance restoration passed. At 22:29 UTC no
active owned unit or reserved partition remained. A read-only 22:38 UTC check
again found the supervisor failed/exited, MainPID0 and no isolated CPUs.

The corrected D279 cold constructor had passed in99.432s before rearm. Source,
source custody/history, signatures, owner inventory, retained qualification and
live resource checks passed; the native919c486 worker actually started. Those
facts do not turn the subsequent native failure into a successful observation.

The [original export](failure-export.json) contains exact source paths, sizes,
hashes and bytes. Separate verified copies include [native failure](native_failure.json),
[checkpoint](checkpoint.json), [custody](custody.json), [supervisor completion](study_complete.json),
[collection traceback](collect_log.log) and [partition restoration](partition_restoration.json).
The program ledger's terminal record was66471; original data/history is retained.

Software diagnosis found a deferred-use lifetime error: the sealed-source parser
callback copies the hardware-state array, but its returned native plan borrows
that temporary array. The pure regression reproduces expired CPU/value storage
and the native layout exception before mappings. The actual stand catch-all
discarded `what()`, so the exact original exception text cannot be recovered.
[D280](../../../decisions/0280-q16c-owned-hardware-prestate.md) repairs ownership;
[verification logs](../Q16C-D280-NATIVE-REPAIR-20261118-01/dev-runner-tests.log)
contain136 passing runner tests and the neighboring ASan/UBSan log contains23
passing checks. No empirical performance claim follows from these tests.

The owner subsequently instructed “continue”. Software repair and corrected
release preparation proceed; no replacement capture has started. Q16a708 and
Q16b120 remain preserved. The existing D277 end18November19:52:53UTC is unchanged.
EXT007 and Stage17 remain incomplete; Stage18 remains prohibited.
