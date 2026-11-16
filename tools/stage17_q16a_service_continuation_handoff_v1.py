"""D260 private handoff of the completed Q16a result to an explicit /4 family.

The original D254 scientific compatibility scope remains identified as D254.
The new schema/purpose, reviewed cold-source hash and /4 plan validator identify
this D260 engineering route. Every other source, platform, qualification,
geometry, report and original arithmetic check runs its original function body.
No old module globals or actual historical qualification are modified.
"""
import types

import stage17_q16a_daycap_handoff_v1 as previous
import stage17_formal_service_continuation_v2 as continuation
import stage17_archive_metadata_fast_v1 as metadata
import stage17_daycap_administration_v1 as association

SCHEMA = 'cpu-prefetch-stage17-q16a-service-continuation-compatibility/1'
PURPOSE = 'RETAINED-Q16A-FOR-D260-Q16B-CONTINUATION'
COLD_SHA256 = '5423c5347763f42192fa1c84c97956f090875fff3065c8886690e3aec132104f'


def make_handoff():
    scope = {**vars(previous), 'SCHEMA': SCHEMA, 'PURPOSE': PURPOSE,
             'COLD_SHA256': COLD_SHA256, 'daycap': continuation}
    for name, function in vars(previous).items():
        if isinstance(function, types.FunctionType) and function.__module__ == previous.__name__:
            scope[name] = metadata._clone(function, scope)
    return types.SimpleNamespace(**scope)


def consume(document, *, validation, plan, selected_duration_ns, original_validation,
            original_plan, compatibility, original_boot_id, boot_id):
    return make_handoff().consume(document,
        validation=association.associated_validation(validation, plan['stand_id']), plan=plan,
        selected_duration_ns=selected_duration_ns,
        original_validation=association.associated_validation(original_validation, original_plan['stand_id']),
        original_plan=original_plan, compatibility=compatibility,
        original_boot_id=original_boot_id, boot_id=boot_id)
