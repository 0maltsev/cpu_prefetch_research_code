"""Explicit software platform boundary for D333 tests; never a runtime backend."""
from contextlib import ExitStack
import hashlib
from pathlib import Path
from unittest import mock
import stage17_s180_compaction_v1 as compaction


def attach(test,environment_owner,root,*,initial=1):
    root=Path(root)
    stack=ExitStack();test.addCleanup(stack.close)
    control=root/'software-compaction-control';control.write_text(str(initial)+'\n')
    script=root/'software-stop-post.py';script.write_bytes(compaction.stop_post_script());script.chmod(0o444)
    stack.enter_context(mock.patch.object(compaction,'ROOT',root/'compaction'))
    stack.enter_context(mock.patch.object(compaction.original,'CONTROL',control))
    stack.enter_context(mock.patch.object(compaction.original,'LEASE',root/'software-lease'))
    image=compaction.runtime.ImageBinding(script,script.stat().st_size,hashlib.sha256(script.read_bytes()).hexdigest())
    supervision=compaction._Supervision(token=compaction._TOKEN,script=image,properties={})
    owned=compaction.prepare(environment_owner=environment_owner,supervision=supervision)
    def cleanup():
        if owned.guard.fd is not None:
            try:owned.guard.restore()
            finally:owned.guard.unlock()
    test.addCleanup(cleanup)
    return owned,control,supervision
