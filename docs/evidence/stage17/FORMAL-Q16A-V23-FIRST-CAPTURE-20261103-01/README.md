# E23 qualification and first formal Q16a capture

This is an archival progress checkpoint, not scientific acceptance or family completion.
Source release remains `dd981b4fdcf953386d4a7514fec381ff9be6e359`; documentation updates do not rebuild or replace it.
The [inventory](inventory.json) records exact copies of the small original stand reports and fresh qualification snapshot. All eight supplied first-capture bindings and all 48 snapshot checksums (46 metadata files plus index/manifest) were rechecked before copying. No raw data, archive payloads, or 12 MB formal plan were copied.

Both E23 clock pairs and Q15-R/W passed. EXT001–006 have six admitted resolutions at journal 000009. The [isolation handoff](formal-isolation-handoff-1.json) retains actual zero MSR readbacks on CPUs 0, 1, and 8, worker reaping, process-group disappearance, and an empty retained isolation partition before formal execution. These are Q15 restoration observations, not claims that the ongoing Q16 family has finished or restored.

The formal attempt marker records its native action start at 2026-11-03T21:43:17.262729Z. Capture ordinal 0 completed native collection and publication. Its custody receipt records nine artifacts as `ARCHIVED_AND_RELEASED`, with `scientific_validity: NOT_ASSESSED`. Ledger sequence 83 durably binds that receipt at **2026-11-03T21:53:24.450007809Z**. This snapshot therefore establishes **1/708 captures fully archived**. Later live progress is outside this checkpoint.

The nine canonical artifacts total **7,132,420,155 bytes**; their physical archives total **693,674,798 bytes**. The checkpoint's original logical bindings equal all nine custody logical/expected bindings; there are no failure receipts. The linked receipt and ledger hashes were checked locally. The complete raw archives and ledger stay on the stand under D233; this small packet does not independently decode them or grant scientific credit.

Plan SHA256: `a9bef1239ea03d3871e40a0c52a0a3375d1eac7512d299443dd18405e89572f7`.
Program scope SHA256: `4d0ddac91ec96bb7038f2903b965a2f1a785b63b108b5b05e645742ac8dcc0c2`.
Qualified worker SHA256: `2e54f9ab7752e8e0f8be02df76970cb94849c93e923cf625d38550a658963c4f`.
Launcher configuration SHA256: `7d06a7229f511c22de722a7bd4b7dacccf6fc09ae42e93f14cea3b32ee8cf68e`.
The launcher read-only check, actual launch readback, one-attempt marker, checkpoint, custody receipt and ledger record are retained under `first-capture/`.

Q16a independent validation and family custody admission remain pending. Q16b/Q16c, calibration freeze and EXT007 admission remain incomplete. Stage 17 is not complete and this packet grants no Stage 18 authority. Scientific durations, required counts and thresholds are unchanged; D234 diagnostic captures contribute zero formal runs.

The [owner stop instruction](first-capture/owner-stop-on-q15-q16-failure-1.json) remains active: stop dependent work after any Q15/Q16 failure, preserve evidence, reap owned workers, restore hardware/owned isolation, and report. No automatic repair/retry cycle is authorized.

Two auxiliary local bookkeeping checks were mistaken: a snapshot binder expected 48 manifest artifacts although there are 46 plus index/manifest; a post-build check compared pure-sizing input placeholders against computed output layouts. Neither was a Q15/Q16 phase failure. The actual snapshot checksums and final 12 layouts passed; original formal outputs were unchanged and the final plan was built once. Earlier d452/c962 failures and original records remain preserved in their existing evidence packets.
