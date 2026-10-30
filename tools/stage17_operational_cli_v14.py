"""Prospective CLI entry point for policy v54 calibration admission."""

from __future__ import annotations

import stage17_operational_cli_v13 as predecessor
import stage17_operational_cli_v11 as base
import stage17_operational_semantics_v8 as authoring
import stage17_operational_semantics_v12 as operational
import stage17_phase_controller_v4 as controller_base
import stage17_phase_controller_v18 as controller_prepare
import stage17_phase_controller_v21 as controller
import stage17_read_only_preflight_semantic_verifier_v29 as preflight
import stage17_semantic_verifier_v39 as preflight_dispatch
import stage17_state_journal_v48 as journal

base.journal_runtime = journal
base.controller = controller
controller_base.journal_runtime = journal
controller_prepare.journal_runtime = journal
preflight_dispatch.preflight = preflight
authoring.ROLE_SCHEMA_v8 = operational.ROLE_SCHEMA_v12
authoring.ROLE_SCHEMA_v6 = operational.ROLE_SCHEMA_v12
main = base.main


if __name__ == "__main__":
    raise SystemExit(main())
