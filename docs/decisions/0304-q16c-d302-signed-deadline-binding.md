# D304: bind approved D302 separately from historical D301 timing

Engineering implementation of the owner's explicit D302 acceptance. No method,
count, duration, additional continuation or new24-hour window is introduced.

The default D301 deadline remains its historical1589604784571258ns endpoint.
Without a closed D302 proof, the expired gate still rejects launch. The supplement
requires the exact29f5dfcf proposal, actual “continue” acceptance, no new windows,
no extra manual continuations, unchanged31460s envelope and exact original signed
day endpoint1636624784571258ns. All fields/types and current-owner signature are
checked in actual UID1000 admission before control rearm or operational signing.
The full envelope must fit strictly before that endpoint, including all reserves.

D301's original approval/cutoff fields and original signed D295 window remain
unchanged. Historical comparisons use the original total endpoint separately
from the admitted runtime endpoint. Root enforces min(actual start+31460s,
admitted day endpoint). Whole-second authorization expiry is derived from the
original signed window's actual UTC/monotonic start and that admitted endpoint,
with unchanged24860s duration and no non-temporal template changes.

The supplement never admits merely because a JSON field claims approval: the
signature is verified against current admitted owner trust alongside D301 and
the original window. A software-only child result remains non-authorizing. Each
installed configuration has distinct software/runtime ownership-audit receipts;
no prior proof is overwritten or substituted for a fresh audit.

Tests retain the expired default, validate exact actual acceptance, reject extra
days/attempts/counts/time, exercise strict final-start boundaries and derive the
UTC endpoint from the unchanged signed window. A rejected/missing signature cannot
be ignored. Existing readiness, source-preservation, native-body, first-failure
recovery and restore-before-analysis sequence checks remain required. Actual
installed signed-provenance, ledger, owner, hardware and resource gates precede
the single conditional launch. No C/C++ source or scientific validator changes;
there is no affected native sanitizer target or new empirical claim.
