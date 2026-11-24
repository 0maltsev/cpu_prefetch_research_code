"""D281 reviewed Q16c input-ownership bytes; all original handoff gates remain."""
import types
import stage17_q16a_q16c_descriptive_handoff_v1 as previous
import stage17_archive_metadata_fast_v1 as metadata
REVIEWED_COLD_SOURCES = {**previous.REVIEWED_COLD_SOURCES,
    'include/cpu_prefetch/runner/stage17_formal_scheduled_action.hpp': '342fb7e4fc9ecfe5b3faf27a85b0b6fd0d1d603d609dc97652db5c72bd739ff6',
    'src/runner/stage17_formal_scheduled_action.cpp': '3ab55abd8d6f27aa0d0105aa31774beae2c29683c7a5891c5bfe35873d864129'}
_comparison = metadata._clone(previous._comparison, {**previous._comparison.__globals__, 'REVIEWED_COLD_SOURCES': REVIEWED_COLD_SOURCES})
_SCOPE = types.SimpleNamespace(**{**vars(previous), 'REVIEWED_COLD_SOURCES': REVIEWED_COLD_SOURCES, '_comparison': _comparison})
consume = metadata._clone(previous.consume, {**previous.consume.__globals__, **vars(_SCOPE)})
def __getattr__(name): return getattr(_SCOPE, name)
