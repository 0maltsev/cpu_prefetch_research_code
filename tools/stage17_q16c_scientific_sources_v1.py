"""D288 scientific closure across actual original bundle and signed cold packet.

The original packet is authenticated by its original signed D282 window. No
file is inserted into, or attributed to, a historical qualified bundle.
"""
import ast
from pathlib import Path
import re

import stage17_q16c_admission_limits_v3 as limits
import stage17_q16c_execution_window_v3 as window

admission=limits.ADMISSION
require,same,fields=admission.require,admission.same,admission.fields
WINDOW_SHA='43b83a21677b394194e409fcfe8bb291e404ce2563ccce906d550e7edbafd993'
SIGNATURE_SHA='889b1e2b484c47fb669b9ad946f560669ba023989a668cd9716a0120139ae33f'
ROOTS=('generate_schedule','stage17_q16c_schedule_provenance_v2',
    'stage17_formal_scheduled_capture_validation_v2','stage17_q16c_control_reader_v1')
SCHEMAS=frozenset(('protocol/2.0.0-pre.3/handoff/schemas/schedule.schema.json',
    'config/schemas/schedule-derivation-v2.schema.json','config/schemas/stage17-formal-scheduled-native-input-v2.schema.json'))


def authenticate(proof,validation,reader):
    fields(proof,'execution_window signature manifest','original signed scientific packet')
    same([proof['execution_window']['size_bytes'],proof['execution_window']['sha256']],
        [3462,WINDOW_SHA],'exact original D282 execution window')
    same([proof['signature']['size_bytes'],proof['signature']['sha256']],[322,SIGNATURE_SHA],
        'exact original D282 owner signature')
    root=window.previous.EVIDENCE
    same(proof['execution_window']['path'],str(root/'d282-execution-window-1/window.json'),'original window namespace')
    same(proof['signature']['path'],proof['execution_window']['path']+'.sig','original window signature namespace')
    raw=reader.read(proof['execution_window']);record=admission._json(raw)
    same(record['source_revision'],window.previous.SOURCE,'original scientific source')
    same(record['worker_sha256'],window.previous.WORKER,'original scientific worker')
    same(record['bindings']['administrative_manifest'],proof['manifest'],'actual signed original cold manifest')
    reader.read(proof['signature'])
    import stage17_phase_controller_v2 as owner
    trust=validation.resolutions['S17-EXT-003'].semantic_context['trust']
    require(trust['measurements']['reviewer_role']=='OWNER' and trust['subject_id']==record['stand_id'],'original actual admitted owner')
    owner._verify_signature(raw,Path(proof['signature']['path']),trust)
    return proof['manifest']


def bindings(original_root,current_root,old_index,new_index,packet_binding,reader):
    """Return exact comparison rows; caller authenticates packet_binding first.

    Discovery parses actual pinned bytes. Packet priority matches the original
    cold loader; any overlapping bundled member must also have identical bytes.
    Missing, changed, duplicate or foreign imports fail closed.
    """
    original_root,current_root=Path(original_root),Path(current_root)
    packet=reader.document(packet_binding);folder=Path(packet_binding['path']).parent
    same(packet['schema_version'],'cpu-prefetch-stage17-q16c-cold-packet/1','original scientific packet schema')
    same(packet['qualified_source_revision'],window.previous.SOURCE,'original packet native source')
    same(packet['qualified_worker_sha256'],window.previous.WORKER,'original packet native worker')
    require(packet['execution_authority'] is False and packet['phase18_authority'] is False,'packet authority remains false')
    require(type(packet['files']) is list and 0<len(packet['files'])<=64,'bounded original packet members')
    members={}
    for row in packet['files']:
        fields(row,'name size_bytes sha256','original packet member')
        name=row['name']
        require(type(name) is str and re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]*',name)
            and name not in members,'unique original packet member')
        members[name]=dict(path=str(folder/name),size_bytes=row['size_bytes'],sha256=row['sha256'])

    def bundled(root,index,name):
        require(name in index,'required actual bundled dependency absent: '+name)
        return dict(index[name],path=admission._member(str(root),name))

    found={};pending=list(ROOTS)
    while pending:
        module=pending.pop();relative='tools/'+module+'.py'
        if relative in found:continue
        require(re.fullmatch('[A-Za-z_][A-Za-z0-9_]*',module),'flat scientific import name')
        old=members.get(module+'.py')
        if old is None:old=bundled(original_root,old_index,relative)
        new=bundled(current_root,new_index,relative)
        before=reader.read(old);after=reader.read(new)
        require(before==after,'unchanged actual scientific dependency differs: '+relative)
        if module+'.py' in members and relative in old_index:
            require(before==reader.read(bundled(original_root,old_index,relative)),
                'original packet/bundle scientific overlap differs: '+relative)
        found[relative]=dict(relative_path=relative,original=old,current=new)
        for node in ast.walk(ast.parse(before,filename=relative)):
            imports=([item.name.split('.')[0] for item in node.names] if isinstance(node,ast.Import)
                else [node.module.split('.')[0]] if isinstance(node,ast.ImportFrom) and node.module else [])
            for child in imports:
                name='tools/'+child+'.py'
                if child.startswith('stage17_') or name in old_index or name in new_index or child+'.py' in members:
                    pending.append(child)
    for name in SCHEMAS:
        old=bundled(original_root,old_index,name);new=bundled(current_root,new_index,name)
        require(reader.read(old)==reader.read(new),'unchanged scientific schema differs: '+name)
        found[name]=dict(relative_path=name,original=old,current=new)
    return [found[name] for name in sorted(found)]
