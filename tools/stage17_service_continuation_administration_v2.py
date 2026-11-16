"""Private D265 diagnostic reader route; original qualification stays intact."""
import stage17_service_continuation_administration_v1 as previous
import stage17_service_prefix_admission_v2 as prefix


def make_controller():
    return previous.metadata._clone(previous.make_controller,
        {**previous.make_controller.__globals__, 'prefix': prefix})()


def make_cli():
    return previous.metadata._clone(previous.make_cli,
        {**previous.make_cli.__globals__, 'make_controller': make_controller})()
