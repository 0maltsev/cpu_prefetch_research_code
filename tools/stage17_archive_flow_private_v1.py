"""Compose cold archive optimizations in a fresh private executor namespace.

No signature, scientific input, filesystem or measured worker changes occur
here. Callers still require the normal separately admitted phase authority.
"""
from __future__ import annotations

import types

import stage17_archive_inventory_native_v1 as inventory
import stage17_archive_metadata_fast_v1 as metadata
import stage17_fixed_action_executor_v12 as original


def make_executor():
    result = metadata.make_executor(original)
    scope = result.execute_fixed_action.__globals__
    scoped_custody = types.SimpleNamespace(**{
        **vars(original.custody),
        'ProgramStore': inventory.make_store_class(base=original.custody.ProgramStore)})
    scope['custody'] = scoped_custody
    result.custody = scoped_custody
    return result
