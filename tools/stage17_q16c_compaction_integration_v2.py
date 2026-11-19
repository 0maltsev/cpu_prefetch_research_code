"""D288 /4 source pinning through D287's unchanged cold guard boundaries."""
import types
from dataclasses import replace
import stage17_archive_metadata_fast_v1 as metadata
import stage17_q16c_compaction_integration_v1 as previous
import stage17_q16c_source_execution_v2 as source_execution
from stage17_q16c_platform_metadata_v1 import Observations,retaining_store_class

export_witness = previous.export_witness
ReadOnlyWitness = previous.ReadOnlyWitness


def make_executor(observations):
    original_base=source_execution.previous
    def make_base():
        result=original_base.make_executor()
        capacity_check=result.custody.check_capacity
        def guard_capacity(snapshot,space):
            return capacity_check(snapshot,replace(space,
                retained_metadata_bytes=space.retained_metadata_bytes+2*1024**2))
        custody=types.SimpleNamespace(**{**vars(result.custody),
            'ProgramStore':retaining_store_class(result.custody.ProgramStore,observations),
            'check_capacity':guard_capacity})
        result.custody=custody
        result.execute_fixed_action.__globals__['custody']=custody
        return result
    base=types.SimpleNamespace(**{**vars(original_base),'make_executor':make_base})
    source=types.SimpleNamespace(**{**vars(source_execution),'previous':base,
        'make_executor':metadata._clone(source_execution.make_executor,
            {**source_execution.make_executor.__globals__,'previous':base})})
    scope={**previous.make_executor.__globals__,'source_execution':source}
    return metadata._clone(previous.make_executor,scope)(observations)
