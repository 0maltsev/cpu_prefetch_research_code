"""D288 actual7fb8944/new-candidate measured and scientific dependency identity.

Caller authenticates both qualification exports and this owner-bound manifest.
No compilation, source generation, raw validation or experiment is performed.
Old and new compaction regimes remain distinct in the final scientific report.
"""
from pathlib import Path

import stage17_q16c_admission_limits_v3 as limits
import stage17_formal_scheduled_continuation_v1 as contract
import stage17_q16c_execution_window_v3 as window
import stage17_q16c_scientific_sources_v1 as science

admission=limits.ADMISSION
require,same,fields=admission.require,admission.same,admission.fields
SCHEMA='cpu-prefetch-stage17-q16c-prefix86-compatibility/2'
LIBRARIES=frozenset('release/lib/libcpu_prefetch_'+name+'.a' for name in (
    'queue','calibration','storage','timing','workload','lifecycle','platform','protocol','reconciliation'))
SCIENTIFIC_ROOTS=science.ROOTS


def consume(plan,binding,*,validation,original_validation,boot_id):
    contract.validate_plan(plan)
    reader=admission.BoundReader();proof=reader.document(binding)
    fields(proof,'schema_version decision stand_id boot_id parent_plan_sha256 original current libraries source_comparisons '
        'scientific_dependencies original_scientific_packet platform_manifests execution_authority phase18_authority','prefix compatibility')
    for key,value in dict(schema_version=SCHEMA,decision='D288',stand_id=plan['stand_id'],boot_id=boot_id,
            parent_plan_sha256=contract.PARENT_SHA256,execution_authority=False,phase18_authority=False).items():
        same(proof[key],value,'exact incident compatibility '+key)
    same(boot_id,window.previous.BOOT,'same original verified boot')
    old=original_validation.resolutions['S17-EXT-006'].semantic_context
    current=validation.resolutions['S17-EXT-006'].semantic_context
    for key,value in dict(source_revision=contract.PARENT_SOURCE,release_artifact_sha256=window.previous.WORKER,
            inventory_sha256='8cfad0e13f95e896f1824ead7beba8dad6b44a5c7327a928e35f7a46b5746444').items():same(old[key],value,'actual original '+key)
    same(plan['source_revision'],current['source_revision'],'actual qualified successor source')
    for key in ('source_revision','release_artifact_sha256','inventory_sha256','archive_bundle_root'):
        require(current[key]!=old[key],'original qualification must not be relabeled '+key)
    for context in (original_validation,validation):
        same(context.resolutions['S17-EXT-004'].semantic_context['stand_id'],plan['stand_id'],'actual physical stand')
    compatibility=limits.make_handoffs()[0]
    releases={side:compatibility._release(proof[side],context,reader,source) for side,context,source in (
        ('original',old,contract.PARENT_SOURCE),('current',current,plan['source_revision']))}
    compatibility._platforms(proof['platform_manifests'],original_validation,validation,reader)
    # Actual file bytes, not claimed identical flags or a source-only analogy.
    compatibility._comparison(proof['libraries'],LIBRARIES,releases,reader,identical=True)
    names=admission._source_names(releases['original'][1])
    same(sorted(names),sorted(admission._source_names(releases['current'][1])),'complete measured native source dependency closure')
    compatibility._comparison(proof['source_comparisons'],names,releases,reader,identical=False)
    packet=science.authenticate(proof['original_scientific_packet'],original_validation,reader)
    actual=science.bindings(releases['original'][0],releases['current'][0],
        releases['original'][1],releases['current'][1],packet,reader)
    same(proof['scientific_dependencies'],actual,'complete actual bundled and signed-packet scientific dependency closure')
    for side,(root,_,report) in releases.items():
        compatibility.codegen.validate_report_bindings(report,binary=Path(proof[side]['worker']['path']),source_root=Path(root))
    reader.finish()
    return dict(schema_version=SCHEMA,parent_plan_sha256=contract.PARENT_SHA256,
        current_source_revision=plan['source_revision'],identical_measured_libraries=sorted(LIBRARIES),
        original_platform_regime='UNRECORDED',current_platform_regime='VERIFIED_ZERO_REQUIRED',
        scientific_dependencies_verified=True,execution_authority=False,phase18_authority=False)
