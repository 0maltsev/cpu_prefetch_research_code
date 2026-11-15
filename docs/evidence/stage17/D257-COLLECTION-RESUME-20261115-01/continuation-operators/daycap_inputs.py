"""Pure metadata construction for D254; no collection or qualification."""
import hashlib,json,pathlib,sys,time

def canonical(d):return json.dumps(d,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def bound(p):
 p=pathlib.Path(p);raw=p.read_bytes();return dict(path=str(p),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def write(p,value):
 import os
 p=pathlib.Path(p);raw=value if isinstance(value,bytes) else canonical(value)
 with p.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
 fd=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(fd)
 finally:os.close(fd)
 return bound(p)
def compatibility(c,old_context,current_context,plan_path,platform_current):
 import stage17_q16a_continuation_admission_v1 as admission
 import stage17_q16a_daycap_handoff_v1 as handoff
 old=old_context['resolutions']['S17-EXT-006']['semantic_context'];new=current_context
 roots={'original':pathlib.Path(old['archive_bundle_root']),'current':pathlib.Path(new['archive_bundle_root'])}
 releases={}
 indexes={}
 for side,root in roots.items():
  indexes[side]=admission._inventory(json.loads((root/'BUNDLE_INVENTORY.json').read_bytes()))
  releases[side]=dict(source_revision=old['source_revision'] if side=='original' else new['source_revision'],bundle_root=str(root),worker=bound(root/'release/bin/cpu_prefetch_runner'),bundle_inventory=bound(root/'BUNDLE_INVENTORY.json'),formal_codegen=bound(root/'build-provenance/formal_codegen_report.json'))
 names=admission._source_names(indexes['original']);assert names==admission._source_names(indexes['current'])
 def row(name):return dict(relative_path=name,**{side:bound(root/name) for side,root in roots.items()})
 return dict(schema_version=handoff.SCHEMA,scope=dict(decision='D254',purpose=handoff.PURPOSE,stand_id='CPU-PREFETCH-V5',boot_id=c['boot_id']),original=releases['original'],current=releases['current'],original_plan=c['original_plan'],plan=bound(plan_path),handoff=c['prerequisites']['q16a_validation'],source_comparisons=[row(name) for name in sorted(names)],queue_libraries={side:bound(root/handoff.QUEUE) for side,root in roots.items()},project_headers=[row(name) for name in handoff.HEADERS],native_geometry=c['files']['native_geometry'],platform_manifests=dict(original=bound(pathlib.Path(c['original_evidence_root'])/'ext004-authoring-records-1/platform-manifest.json'),current=bound(platform_current)),execution_authority=False,phase18_authority=False)
