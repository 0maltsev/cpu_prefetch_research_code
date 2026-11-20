"""D308 fresh metadata entry, unchanged append/replay and signed freeze."""
import hashlib
import inspect
from pathlib import Path
import admit_stage17_descriptive_freeze_v1 as previous
import stage17_state_journal_v62 as journal
import stage17_semantic_verifier_v65 as semantic
import stage17_operational_semantics_v19 as scoped

PARENT_SHA = 'cec8958a9d12202d2a030abbdb3f112967acdad4b696bc1c52ca7912cc851b86'
cloning,original_cli = previous.cloning,previous.original_cli


def retained_manifest(io,data,manifest):
    path = data/'ext007-manifest-v5.json'
    if not path.exists(): return io.save(path,manifest)
    binding = io.binding(path)
    scoped.require(io.read(binding) == scoped.freeze.canonical(manifest),'exact retained signed-data manifest')
    return binding


def main():
    scoped.require(hashlib.sha256(Path(previous.__file__).read_bytes()).hexdigest() == PARENT_SHA,'exact preserved admission entry1')
    text = inspect.getsource(previous.main)
    replacements = [
        ('tools/admit_stage17_descriptive_freeze_v1.py','tools/admit_stage17_descriptive_freeze_v2.py'),
        ("manifest_binding = io.save(data/'ext007-manifest-v5.json',manifest)", 'manifest_binding = retained_manifest(io,data,manifest)'),
        ('d307-ext007-descriptive-freeze-1.json','d308-ext007-descriptive-freeze-1.json'),
        ('S17-EXT-007-D307-DESCRIPTIVE-CUSTODY-1','S17-EXT-007-D308-DESCRIPTIVE-CUSTODY-1'),
        ('d307-preview-resolution-007.json','d308-preview-resolution-007.json'),
        ('d307-scoped-admission-preview.json','d308-scoped-admission-preview.json')]
    for old,new in replacements:
        scoped.require(text.count(old) == 1,'exact retained entry seam '+old); text = text.replace(old,new,1)
    namespace = {**vars(previous),'__file__':__file__,'journal':journal,'semantic':semantic,'scoped':scoped,
                 'retained_manifest':retained_manifest}
    exec(compile(text,__file__+':preserved-admission','exec'),namespace)
    return namespace['main']()


if __name__ == '__main__': main()
