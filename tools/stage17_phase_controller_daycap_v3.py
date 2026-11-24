"""D272 policy61 qualification controller; Q16c collection admission is separate."""
import stage17_phase_controller_daycap_v2 as previous
import stage17_archive_metadata_fast_v1 as metadata
import stage17_state_journal_v57 as journal

def make_controller():
    return metadata._clone(previous.make_controller,
        {**previous.make_controller.__globals__, 'journal': journal})()

_CONTROLLER = make_controller()

def __getattr__(name): return getattr(_CONTROLLER, name)
def activate(): return _CONTROLLER.activate()
