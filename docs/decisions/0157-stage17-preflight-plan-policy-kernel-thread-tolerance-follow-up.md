# ADR-0157: Stage 17 preflight-plan-policy follow-up for ADR-0156

- **Status:** `ACCEPTED`
- **Decision ID:** D-157
- **Classification:** implementation correctness, latent defect in
  already-accepted production code, action-time reachability gap
- **Owner:** repository/platform/security/pilot owner
- **Gate:** before any real `S17-EXT-001` authored after ADR-0156 can
  reach a working real preflight/fixed-action execution

## Context

The real, live standv2-21 journal was the first ever to author `S17-
EXT-001` against an admission root pre-patched with ADR-0156's fix
(`stage17_fixed_action_executor_v5.py`/`stage17_phase_controller_v15.py`,
plus the corresponding `tools/stage17_operational_cli_v11.py` edit). Its
real preflight capture (`S17-EXT-002`) failed twice in succession:

1. First: `stage17-read-only-preflight-v12: FAIL: bindings tools__
   stage17_operational_cli_v11_py bytes drifted`. Root-caused directly:
   `stage17_read_only_preflight_executor_v25.py` hardcodes `import
   stage17_state_journal_v35 as current_journal`, whose own `semantic`
   binding is `stage17_semantic_verifier_v41` -- so `execute_once`'s own
   `_prospective_validation` re-checks the admission root's files
   against policy-v41's stale `cli_v11.py` hash even though the
   admission root had already been patched to ADR-0156's policy-v42
   shape. Fixed live, mid-journal (safe: this check runs before
   `_prepare_action`'s marker-creation check, so no one-shot marker had
   been written), by adding `stage17_read_only_preflight_executor_v26.py`
   -- an additive successor monkey-patching `current_journal` to `v36`,
   the same technique `v36` itself already uses for its own `semantic`
   binding.

2. Second, after applying that fix: `stage17-read-only-preflight-v12:
   FAIL: S17-EXT-001 is not prospectively action-ready`, with the real
   underlying exception silently swallowed to `None` by production code
   (`evaluate_s17_ext_001_action_readiness_v20`'s own broad `except
   (KeyError, SemanticAdmissionError, OSError, ValueError): return
   None`). Root-caused by reproducing the same call directly, read-only,
   with the exception printed instead of swallowed: `SemanticAdmission
   Error: actual state_journal source path does not match policy role`,
   raised from `stage17_semantic_verifier_v4.py`'s `_verify_loaded_
   runtime`. `S17-EXT-001`'s own `semantic_context` embeds a frozen
   snapshot of `implementations.executor`/`implementations.state_
   journal` from `config/stage17/stage17-read-only-preflight-evidence-
   admission-policy-v27.json` (`stage17_operational_cli_v11.py`'s
   `author-ext001` hardcodes this exact path) -- a policy generation
   authored before ADR-0156 existed, still pinning `executor` = `tools/
   stage17_read_only_preflight_executor_v25.py` and `state_journal` =
   `tools/stage17_state_journal_v35.py`. Once the admission root's
   *actually loaded* executor/journal moved to `_v26.py`/`_v36.py` (fix
   #1 above), the basenames no longer matched what `S17-EXT-001`'s own
   frozen resolution recorded, and `_verify_loaded_runtime` correctly
   rejected the mismatch.

This second failure is unrecoverable for standv2-21's own journal: its
`S17-EXT-001` is already admitted, permanently freezing the stale `v27`-
shaped `implementations` snapshot into that resolution's own `semantic_
context`. No patch can satisfy both "match what `S17-EXT-001` already
recorded" and "match the admission root's actually-patched files" at
once for that one resolution. This mirrors exactly the precedent ADR-
0131 itself recorded for `pid_namespace_supervisor = v2`, and ADR-0156's
own Context section recorded for `standv2-20`: a fresh journal, authored
*after* the complete fix exists, is required.

This is a distinct, real, first-time-observed gap, not a mistake in
ADR-0156's own fix: no journal before standv2-21 had ever authored a
fresh `S17-EXT-001` against an admission root carrying ADR-0156's
executor/phase-controller change, so this specific reachability path
(the preflight-plan-policy's own frozen executor/state-journal snapshot)
had never been exercised against it before.

## Decision

Add, as additive successors, exactly mirroring the `v26`->`v27` pattern
this same policy chain already used for ADR-0146:

- `tools/stage17_read_only_preflight_semantic_verifier_v28.py`: re-
  exports every `v27` name unchanged except `IMPLEMENTATION_PATHS`
  (`executor` -> `_v26.py`, `state_journal` -> `_v36.py`) and `verify_
  policy_v28` (a copy of `verify_policy_v27`'s body, not an alias, for
  the exact reason that file's own docstring already gives: a function's
  free variables resolve against the module that defines it).
- `config/schemas/stage17-read-only-preflight-evidence-admission-policy-
  v28.schema.json`: mechanical successor to `_v27`'s schema, changing
  only the version-numbered `const`s and the `predecessor` object's
  required-key names (`policy_v26`/`adr_0146` -> `policy_v27`/`adr_0156`),
  matching exactly the diff shape `_v26` -> `_v27` already established.
- `tools/author_stage17_read_only_preflight_policy_v28.py`: renders
  `config/stage17/stage17-read-only-preflight-evidence-admission-policy-
  v28.json`, verified for real via `verify_policy_v28` against the
  actual rendered document.
- `tools/stage17_operational_cli_v11.py`'s `author-ext001` command is
  edited in place a second time this session (its own established,
  already-27-times-repeated convention) to reference `...policy-v28.json`
  instead of `...policy-v27.json`.
- A new outer operational-policy generation (`v43`, superseding `v42`)
  re-pins `cli_v11.py`'s latest hash and adds `_v26.py`/`_v28.json`-
  adjacent files to its own closure, following exactly ADR-0156's own
  `v41` -> `v42` pattern. `v42.json` stays byte-for-byte frozen (it was
  used, however briefly, by standv2-21's own admitted `S17-EXT-001`);
  ADR-0156's own text is not edited, since it too is already embedded
  by hash into that same admitted resolution.

## Effects

Fixes the specific, real, reproduced deadlock that stopped standv2-21's
own preflight capture from ever succeeding once ADR-0156's executor fix
was applied mid-journal. No scientific design, hardware-safety
mechanism, credential handling, transport mechanics, or admission
semantics for any `S17-EXT-00N` input changes -- only which preflight-
plan-policy generation a fresh journal's own `author-ext001` embeds, and
which executor/state-journal source files that generation expects to be
loaded at real preflight/action time. This does not make standv2-21's
existing chain executable (see Context above); a fresh `S17-EXT-001`
admission against policy-v43/preflight-policy-v28 is required before any
real Q16a/Q16b/Q16c retry.

## Verification and supersession

Acceptance requires, all confirmed for real this session: (1) a real,
live reproduction of both failures against standv2-21's actual admission
root, with the second failure's real (normally-swallowed) exception
printed via a read-only diagnostic reproducing `evaluate_s17_ext_001_
action_readiness_v20`'s own logic; (2) `verify_policy_v28` run for real
against the actual rendered `...policy-v28.json`, confirmed `PASS`; (3)
a full pre-patch rehearsal (materializing a fresh admission root from
the sealed bundle, applying every fix committed since, including this
one) confirmed zero drift against the current repo's own `v43` policy;
(4) `git diff` confirming no previously-accepted file's bytes changed
except `stage17_operational_cli_v11.py` (its own established, repeatedly
in-place-edited convention) and `stage17-operational-evidence-admission-
policy-v42.json`/ADR-0156 staying byte-for-byte untouched. Any later
change to which executor/state-journal generation a fresh `S17-EXT-001`
expects needs another prospective successor under the same standard
applied since ADR-0108.
