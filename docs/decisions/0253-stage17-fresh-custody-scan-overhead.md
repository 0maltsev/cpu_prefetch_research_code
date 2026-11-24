# D253: Reduce fresh custody-check overhead before another experiment

- Status: ACCEPTED engineering scope by the owner; implementation and timing verification in progress
- Date: 2026-11-15
- Scope: cold archive metadata I/O and complete physical inventory only
- Scientific methods, captured observations and qualified native measurement code: unchanged
- Execution authority: software timing tests only; no new experimental launch

The owner requested stopping current Q16b, reducing archive overhead, presenting
an approximate runtime before another experimental run, and permitted timing
tests on the stand. Stop at a fully archived boundary and preserve the actual
interruption, owned-worker cleanup and restoration evidence. Do not treat this
stop as successful family completion or silently restart it.

The stopped attempt retained three completed captures. Its first archive interval
was239.03seconds, while whole capture cycles were about347seconds. Source analysis
shows four full historical ledger replays per successful capture and70complete
pre-write inventory scans for six artifacts. A full3540-capture family adds198240
ledger records. An estimate based only on the first cycle ignores this growth.

Keep complete fresh ledger replay, exact canonical/schema/chain/transition
checks, file hashing, before/after stable-identity checks, every inventory stat,
hardlink deduplication, checked arithmetic, physical quota and live filesystem
limits. Keep both full archive reconstruction readbacks, durable publication,
working-copy release checks and all failure behavior. No filesystem observation,
content, decoded semantic state or physical total may be accepted from a cache.

Optimize metadata reads by reusing only normalized ancestor path strings while
freshly checking every ancestor on each read. Allocate reads from the observed
file size plus one rather than the potentially gigabyte metadata ceiling; still
reject growth, truncation, excessive size, changed identities or byte bindings.
Historical methods remain readable unchanged; introduce a private v2 adapter.

A guarded ASCII JSON parser was tested as an additional candidate. Although
acceptance/error tests passed, actual stand replay took13.5seconds versus10.6
without it. Reject this slower candidate and preserve its prototype/timing as
engineering evidence. Keep the existing parser and canonicalizer in the selected
implementation; the extra prototype supplies no execution authority.

Implement a separate cold native inventory helper for the same complete fresh
scan and first-observed inode accounting. It has finite memory/time/input bounds,
rejects invalid names/types/overflow and returns only numeric usage. Authenticate
and seal its exact image before use, with no library search or fallback after a
native failure. Compare every usage field with the existing Python scan on real
files, hardlinks, sparse files, symlinks, malformed namespaces and exhausted
limits. Run native sanitizer checks and actual stand inventory timing.

Time software against retained data after shutdown. Benchmarks add no queue
observations or scientific credit and do not revalidate completed Q16a. Preserve
historical profiles and source; prospective production use needs a separately
bound profile and normal phase admission. Present an approximate family budget
that includes growth and disclose which contexts were actually measured.
Leave collection stopped at this engineering handoff.

## Remove redundant ledger openings within one cold transaction

The v11 pre-broker store opening only derives root, scope and family attributes.
Derive those from the same validated constructor without entering/replaying;
the broker still performs the complete fresh locked replay and original family,
checkpoint and source admission before any archive write.

After proven broker cleanup, open one fresh locked store for original receipt
authentication and the immediately following original resource check. Execute
their unchanged bodies with a private context factory returning that held store
only for the identical request object and exact deadline. Reject use after the
transaction, mismatched requests or deadlines; release on every failure. No
broker or other cooperating writer can intervene between the two checks while
the exclusive lock is held. No state is reused across store transactions.

This reduces four full cold replays to two per capture while retaining the
actual broker replay, independent controller replay, durable receipt binding,
fresh quota/resource checks, failure cleanup and acknowledgement ordering.
Preserve v11 unchanged and introduce v12 plus a private composition factory.
