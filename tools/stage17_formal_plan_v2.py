"""Explicit D233 physical-storage successor; historical v1 remains unchanged.

Shared native validation recomputes the complete canonical bounds. Only a /2
plan can select archival custody. This is a declaration checker, not a runtime
implementation, archive proof, live-resource observation or phase authority.
"""
import stage17_formal_plan_v1 as previous
from stage17_discovery_contract_v2 import ContractError

VERSION = {action: version.replace("/1", "/2") for action, version in previous.VERSION.items()}
SCHEMA = {action: name.replace("-plan-v1", "-plan-v2") for action, name in previous.SCHEMA.items()}


def validate_plan(action, document):
    if action not in VERSION or not isinstance(document, dict):
        raise ContractError("formal plan: unsupported action or document")
    if document.get("schema_version") == previous.VERSION[action]:
        return previous.validate_plan(action, document)
    if document.get("schema_version") != VERSION[action]:
        raise ContractError("formal plan: unsupported schema version")
    return previous._validate_plan(action, document, archived=True)
