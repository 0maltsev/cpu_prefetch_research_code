"""D273 raw-validator/composer control-source identity integration.

Preserve frozen v1 bytes and every count/coverage/claim rule. The raw validator
actually returns its control-schema source identity; the new private report
consumer requires that exact field as well as every existing source binding.
"""
import types
import stage17_q16c_descriptive_calibration_v1 as previous
import stage17_archive_metadata_fast_v1 as metadata

archive,contract,admission=previous.archive,previous.contract,previous.admission
Error,require,same,fields,uint=previous.Error,previous.require,previous.same,previous.fields,previous.uint
SCHEMA=previous.SCHEMA
raw_validator=types.SimpleNamespace(**{**vars(previous.raw_validator),
    'SOURCE_VERSIONS':dict(previous.raw_validator.SOURCE_VERSIONS,control=previous.raw_validator.CONTROL_IDS['Q16c'])})
_report=metadata._clone(previous._report,{**previous._report.__globals__,'raw_validator':raw_validator})
evaluate=metadata._clone(previous.evaluate,{**previous.evaluate.__globals__,'_report':_report})
