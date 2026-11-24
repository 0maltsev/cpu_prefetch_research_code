# D249: Q16b cold plan and prospective resource boundaries

- Status: PREPARED engineering plan under owner-accepted D248
- Date: 2026-11-15
- Scope: prospective Q16b; no collection, registration or launch authority

D248 freezes 3540 captures, 59 in each existing cell, with 5-second warmup and
1-second measurement. The plan uses the authenticated D247 Q16a handoff and
its actual six d2=2 results. Both source histories and all Q16a FULL outcomes
remain retained. Common capacities 512/65536/1048576 come from the accepted
working-set amendment; no cache capacity is guessed from this PC.

A separately bound cold caller links only the qualified release42f2ebb package
and managed runtime. It calls the existing service parser/layout API without
constructing a queue, mapping the represented arenas, observing hardware or
running a timed workload. Release and ASan/UBSan caller builds each passed
64 cold checks; original qualified libraries remain unchanged and uninstrumented.
Every actual cell was sized, and a separate check reparsed all 60 actual declared
layouts. Repetition changes only equal-width identities and seeds.

Prospective failure ceilings are requested engineering limits, not observed
rates, selected sample counts or assurances that no limit will be reached:

| Input | Bound |
|---|---:|
| Warmup producer attempts / consumer polls | 100000000 / 100000000 |
| Measurement producer attempts / consumer polls | 30000000 / 30000000 |
| Drain per phase | 30 seconds |
| Setup / publication / cleanup per capture | 120 / 1800 / 120 seconds |
| Cold archival per capture | 1800 seconds |
| Worker address space | 224 GiB |
| Controller / codec / broker address space | 2 / 2 / 2 GiB |

Q16b omits the Q16a demand-observation instrumentation. A larger warmup watchdog
is declared prospectively to avoid assuming the same attempt rate. Actual
measurement duration and the estimator are unchanged. Reaching a bound stops
the family incomplete; it cannot trigger an automatic retry, cap adjustment,
top-up or favorable-result selection.

The exact native maximum mapping is 30709854208 bytes. The retained common
observation/allocation model plus raw publication copy floor gives a maximum
modeled requirement of 58889947616 bytes, below the requested worker ceiling.
This is a declared-component model, not a certification of allocator retention
or observed RSS. Metadata helper, allocation helper, imported helper, symbolic
model and zstd library are bound before/after preparation. The same shared
observation serializer is used by formal service publication; its additional
scalar/phase/layout fields remain covered by the existing 4 MiB allowance.

The largest declared capture is 31227906332 bytes. Archive staging is
31354232832 bytes, conservatively covering both 8192-row transformed raw frames
and 4 MiB bulk frames under the accepted zstd bound. Node-order artifacts,
including empty ring orders, remain covered. The shared D233 quota, 512 GiB
workspace, 256 GiB scratch and 16 GiB reserve are unchanged. Logical family
output is not represented as an archive compression guarantee.

The read-only 08:23 UTC stand accounting verified two existing registered
families, unchanged ledger58848, 460127571968 retained quota bytes, no pending
reservation, and 5539872428032 remaining quota bytes. Actual free bytes were
6446065614848 against 6381686018048 for remaining quota plus workspace,
scratch and reserve. This snapshot is planning evidence; live admission must
check resources again immediately before execution.

The conservative complete-family watchdog is 13827480000000000 ns (161 days
rounded upward). This is a failure ceiling, not an estimated completion time;
warmup and measurement alone total 5h54m. The old 34-day isolation keeper cannot
cover this declared ceiling. A Q16b-specific finite keeper configuration and
its remaining-lifetime admission are required; D243's consumed continuation
setup is not reused as Q16b authority. Historical namespace audit/registration,
the explicit v27 administrative runtime binding, exact signed phase admission,
resource checks, supervision and restoration remain separate requirements.

No new scientific decision, immutable protocol change, native release change,
repeat qualification or repeated Q16a collection/raw validation is introduced.
EXT007/Stage17 and Stage18 admission remain incomplete.
