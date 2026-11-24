"""D277/D278 explicit cold Q16c/3 administration over the qualified919c486 release.

The caller authenticates this administrative packet and its historical exports.
Original v25 signed authority, journal, hardware, discovery, namespace, UTC and
one-use rules execute unchanged. No qualification or experiment occurs on import.
"""
from pathlib import Path
import time
import types

import stage17_phase_controller_daycap_v1 as graph
import stage17_phase_controller_daycap_v4 as qualification
import stage17_operational_cli_daycap_v4 as qualified_cli
import stage17_archive_metadata_fast_v1 as metadata
import stage17_archive_q16c_descriptive_overlay_v1 as overlay_module
import stage17_formal_scheduled_descriptive_v1 as descriptive
import stage17_q16c_source_execution_v1 as execution
import stage17_q16c_empty_reuse_v1 as receipts
import stage17_q16c_admission_limits_v2 as limits
import stage17_daycap_administration_v1 as association
import stage17_state_journal_v59 as journal
import stage17_q16c_execution_window_v2 as execution_window

SCHEMA = 'cpu-prefetch-stage17-q16c-descriptive-historical-inputs/1'
CONTEXT_SCHEMA = graph.CONTEXT_SCHEMA
admission = limits.ADMISSION
ANALYSIS_RESERVE_NS = 5_400_000_000_000
RESTORATION_RESERVE_NS = 2_400_000_000_000


def _read_history(raw, packet_root, handoffs):
    document = admission._json(raw)
    admission.fields(document, 'schema_version q16a q16b boot_id execution_authority phase18_authority', 'Q16c history')
    admission.same(document['schema_version'], SCHEMA, 'Q16c history schema')
    graph._uuid(document['boot_id'])
    for flag in ('execution_authority', 'phase18_authority'):
        admission.same(document[flag], False, 'history authority')
    reader = admission.BoundReader(); results = {}
    for phase, handoff in zip(('q16a','q16b'), handoffs, strict=True):
        row = document[phase]
        admission.fields(row, 'historical_context original_plan compatibility' if phase=='q16a'
                         else 'historical_context compatibility', 'historical '+phase)
        for key in ('historical_context','compatibility'):
            admission.require(Path(row[key]['path']).parent == packet_root, 'bound history packet namespace')
        context = reader.document(row['historical_context'])
        admission.fields(context, 'schema_version boot_id resolutions execution_authority phase18_authority', 'old qualification export')
        admission.same(context['schema_version'], CONTEXT_SCHEMA, 'old qualification export schema')
        admission.same(context['boot_id'], document['boot_id'], 'actual old/current boot')
        for flag in ('execution_authority','phase18_authority'):
            admission.same(context[flag], False, 'old export authority')
        admission.fields(context['resolutions'], 'S17-EXT-004 S17-EXT-006', 'actual old qualification contexts')
        resolutions = {}
        for key, value in context['resolutions'].items():
            admission.fields(value, 'semantic_context', 'actual old semantic export')
            admission.require(type(value['semantic_context']) is dict, 'old semantic context required')
            resolutions[key] = types.SimpleNamespace(semantic_context=value['semantic_context'])
        old = types.SimpleNamespace(resolutions=resolutions)
        release = resolutions['S17-EXT-006'].semantic_context
        admission.same(release['source_revision'], handoff.original.SOURCE, 'actual historical '+phase+' source')
        admission.same(release['inventory_sha256'], handoff.original.INVENTORY, 'actual historical '+phase+' inventory')
        admission.same(release['release_artifact_sha256'], handoff.OLD_WORKER if phase=='q16a'
                       else handoff.original.WORKER, 'actual historical '+phase+' worker')
        proof = reader.document(row['compatibility'])
        admission.same(proof['schema_version'], handoff.SCHEMA, 'historical compatibility schema')
        admission.same(proof['scope'], dict(decision='D270', purpose=handoff.PURPOSE,
            stand_id=resolutions['S17-EXT-004'].semantic_context['stand_id'],boot_id=document['boot_id']), 'bound reuse purpose')
        for flag in ('execution_authority','phase18_authority'):
            admission.same(proof[flag], False, 'compatibility authority')
        original_plan = reader.document(row['original_plan']) if phase=='q16a' else None
        if original_plan is not None:
            admission.same(proof['original_plan'], row['original_plan'], 'actual retained original plan')
            admission.same(original_plan['source_revision'], release['source_revision'], 'actual old plan source')
        results[phase] = row, old, original_plan, proof
    reader.finish()
    return document, results


def make_controller():
    handoffs = limits.make_handoffs()
    history = []; admitted = {}; windows = []; reuse_proofs = []
    overlay = graph._clone_module(overlay_module, {'_CONFIG':None})
    plans = execution.make_contract()
    registry = execution.previous.make_output_registry(plans)
    controller = graph._clone_module(graph, {'journal_runtime':journal,
        'overlay':overlay, 'registry':registry, 'contract':plans, '_HISTORICAL':None})
    scope = controller.prepare_action.__globals__

    def selected(request):
        return (request.get('action_id')=='Q16c' and isinstance(request.get('action_inputs',{}).get('plan'),dict)
                and request['action_inputs']['plan'].get('schema_version')==descriptive.VERSION)

    def configure_historical_inputs(document, packet_root):
        root = Path(str(packet_root))
        admission.require(root.is_absolute() and root.is_dir() and root.resolve(strict=True)==root, 'canonical history packet root')
        raw = admission.canonical(document)
        admission.require(len(raw)<=131072, 'finite history packet configuration')
        _read_history(raw, root, handoffs)
        value = raw, root
        admission.require(not history or history[0]==value, 'history packet already pinned')
        if not history: history.append(value)

    def configure_execution_window(proof):
        raw=admission.canonical(proof)
        admission.fields(proof,'manifest signature','separate execution window proof')
        execution_window.read(proof['manifest']);execution_window.read(proof['signature'])
        admission.require(not windows or windows[0]==raw,'execution window already pinned')
        if not windows:windows.append(raw)

    def configure_source_reuse(proof):
        raw=admission.canonical(proof)
        admission.require(not reuse_proofs or reuse_proofs[0]==raw,'source reuse proof already pinned')
        if not reuse_proofs:reuse_proofs.append(raw)

    def historical_inputs():
        if not history: raise controller.ControllerError('Q16c history packet is not configured')
        return _read_history(*history[0], handoffs)

    def validate_inputs(request, validation):
        if not selected(request): raise controller.ControllerError('descriptive administration requires explicit Q16c/3')
        config, historical = historical_inputs(); checked = {}; source_result = []
        admission.require(len(windows)==len(reuse_proofs)==1,'signed window/source reuse are not configured')
        window=execution_window.authenticate(admission._json(windows[0]),validation=validation,
            plan=request['action_inputs']['plan'],now=time.monotonic_ns())
        admission.same(Path('/proc/sys/kernel/random/boot_id').read_text().strip(),config['boot_id'],'actual current boot')

        def prior(result, phase, plan, selected_duration_ns):
            key = phase.lower(); row, old, old_plan, proof = historical[key]
            admission.same(proof['handoff'], request['action_inputs']['prerequisite_bindings'][key+'_validation'], 'actual signed '+phase+' handoff')
            current = association.associated_validation(validation,plan['stand_id'])
            old = association.associated_validation(old,plan['stand_id'])
            arguments = dict(validation=current,original_validation=old,plan=plan,selected_duration_ns=selected_duration_ns,
                             original_boot_id=config['boot_id'],boot_id=config['boot_id'])
            if phase=='Q16a':
                checked[phase] = handoffs[0].consume(result,original_plan=old_plan,compatibility=row['compatibility'],**arguments)
            elif phase=='Q16b':
                checked[phase] = handoffs[1].consume(result,compatibility_binding=row['compatibility'],**arguments)
            else: raise controller.ControllerError('unexpected prior calibration')

        def ring(plan, result, binding):
            return v25.validate_ring_reuse(plan,checked.get('Q16a',result),binding)

        def sources(plan, bindings, registrations, result):
            admission.require(type(bindings) is list and len(bindings)==360,'complete360-source prospective family')
            record, originals = receipts.validate(plan,bindings,registrations,bindings[0]['source_preparation'],
                validation=validation,boot_id=config['boot_id'],deadline_ns=time.monotonic_ns()+120*10**9,reuse=admission._json(reuse_proofs[0]))
            # Verify the exact basis actually came from the retained Q16b result.
            minimum = checked['Q16b']['derived_result']['min_mu_ref']
            admission.same(minimum,dict(numerator=1670571,denominator=1),'exact retained descriptive service minimum')
            source_result.append((record,originals))

        extent = v25._with_globals(v25.validate_action_inputs,dict(contract=plans,
            validate_prior_calibration=prior,validate_ring_reuse=ring,validate_schedule_sources=sources,
            registry=types.SimpleNamespace(**{**vars(registry),'canonical':registry.archive.canonical})),
            dict(request=request,validation=validation))
        if len(source_result)!=1: raise controller.ControllerError('source job must be authenticated exactly once')
        # This is only a return channel within this synchronous preparation,
        # never a cache that skips validation. Every call repeats all gates.
        admitted.clear(); admitted.update(request_sha256=registry.sha256(registry.canonical(request)),
                                          source_record=source_result[0][0],source_bindings=source_result[0][1],execution_window=window)
        return extent

    v25 = graph._clone_module(graph.original_v25, {'journal_runtime':journal,
        'activate':controller.activate,'registry':registry})
    scope.update(_v25=v25,_is_daycap=selected,_validate_inputs=validate_inputs,
        configure_historical_inputs=configure_historical_inputs,_historical_inputs=historical_inputs,
        configure_execution_window=configure_execution_window,configure_source_reuse=configure_source_reuse,
        configure_verified_descriptor=overlay.configure_verified_descriptor,is_archived=registry.is_archived,
        runtime_from_context=v25.runtime_from_context,_runtime_from_context=v25._runtime_from_context,
        _validate_action_inputs=v25._validate_action_inputs,make_executor=execution.make_executor)
    v26 = graph._clone_module(graph.original_v26, {'previous':v25,'activate':controller.activate,
        'contract':plans,'_contract':plans,'is_archived':registry.is_archived,'_validate_inputs':validate_inputs,
        'qualified_archive_profile':controller.qualified_archive_profile,'_prepare_action':controller._prepare_archive})
    scope['_v26']=v26

    def execute_once(**arguments):
        admitted.clear()
        prepared = controller.prepare_action(**arguments)
        admission.same(admitted['request_sha256'],registry.sha256(prepared.request_bytes),'actually prepared request bytes')
        record=admitted['execution_window'];extent=plans.validate_plan('Q16c',prepared.request['action_inputs']['plan'])
        admission.require(time.monotonic_ns()+extent.declared.watchdog_ns+ANALYSIS_RESERVE_NS+RESTORATION_RESERVE_NS
            < record['global_deadline_ns'],'complete remaining Q16c envelope cannot fit separately approved execution window')
        executor=execution.make_executor()
        try:
            return executor.execute_fixed_action(repository_root=prepared.root,authorization=prepared.authorization,
                authorization_bytes=prepared.authorization_bytes,request=prepared.request,request_bytes=prepared.request_bytes,
                worker_binding=prepared.runtime,worker_path=prepared.worker_path,release_binding=prepared.release,
                output_root=Path(prepared.request['evidence_root_binding']['absolute_path']),
                archive_runtime_profile=prepared.archive_runtime_profile,q16c_source_bindings=admitted['source_bindings'],
                synthetic_test_only=arguments.get('synthetic_test_only',False))
        finally:controller.activate()

    scope['execute_once']=execute_once
    # Namespace attributes and original function globals share these aliases.
    return types.SimpleNamespace(**scope)


def make_cli():
    controller=make_controller()
    # The qualified CLI already has isolated inherited/local function globals.
    # Clone its actual view and private base rather than only module attributes.
    base=graph._clone_module(qualified_cli._base,{'journal_runtime':journal})
    view=graph._clone_module(qualified_cli._VIEW,dict(controller=controller,base=base,
        registry=controller.registry,daycap_execution=execution,journal=journal))
    scope=view.main.__globals__
    scope['author_ext001_daycap_v1']=qualified_cli.author_ext001_daycap_v4
    base.main.__globals__.update(author_ext001=qualified_cli.author_ext001_daycap_v4)
    return view
