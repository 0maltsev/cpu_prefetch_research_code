"""Bounded software diagnostic, not a Q15/Q16 or performance experiment.

Only this process's private 64 MiB mapping is migrated. No sysctl changes,
archive mutations, qualification or native research invocation.
"""
import collections
import ctypes
import errno
import json
import mmap
import os
import threading
import time

libc = ctypes.CDLL(None, use_errno=True)
libc.syscall.restype = ctypes.c_long
libc.mlock.argtypes = (ctypes.c_void_p, ctypes.c_size_t)
libc.mprotect.argtypes = (ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int)
libc.munlock.argtypes = (ctypes.c_void_p, ctypes.c_size_t)
size = 64 * 1024**2
page = os.sysconf('SC_PAGESIZE')
assert page == 4096 and os.uname().machine == 'x86_64'
os.sched_setaffinity(0, {3})
region = mmap.mmap(-1, size, flags=mmap.MAP_PRIVATE | mmap.MAP_ANONYMOUS,
                   prot=mmap.PROT_READ | mmap.PROT_WRITE)
address = ctypes.addressof(ctypes.c_char.from_buffer(region))
assert libc.madvise(ctypes.c_void_p(address), ctypes.c_size_t(size), 15) == 0
mask = ctypes.c_ulong(1)
assert libc.syscall(237, ctypes.c_void_p(address), ctypes.c_ulong(size),
                    ctypes.c_int(2), ctypes.byref(mask), ctypes.c_ulong(65), ctypes.c_uint(0)) == 0
for i in range(0, size, page):
    region[i] = 90
assert libc.mlock(address, size) == 0
assert libc.mprotect(address, size, mmap.PROT_READ) == 0
pages = (ctypes.c_void_p * (size // page))(*(address+i for i in range(0, size, page)))
statuses = (ctypes.c_int * len(pages))()
def query(addresses, output):
    result = libc.syscall(279, ctypes.c_int(0), ctypes.c_ulong(len(addresses)),
                          addresses, ctypes.c_void_p(0), output, ctypes.c_int(0))
    assert result == 0, (result, ctypes.get_errno())
query(pages, statuses)
assert set(statuses) == {0}
selected = (ctypes.c_void_p * 1)(address + 1916 * page)
observed = (ctypes.c_int * 1)()
end = time.monotonic() + 10
counts = collections.Counter()
migration = collections.Counter()
errors = []
def migrate():
    try:
        os.sched_setaffinity(0, {4})
        target, moved = (ctypes.c_int * 1)(), (ctypes.c_int * 1)()
        while time.monotonic() < end:
            for node in (1, 0):
                target[0] = node
                result = libc.syscall(279, ctypes.c_int(0), ctypes.c_ulong(1),
                                      selected, target, moved, ctypes.c_int(2))
                if result != 0:
                    raise RuntimeError((result, ctypes.get_errno(), moved[0]))
                migration[str(moved[0])] += 1
    except BaseException as error:
        errors.append(repr(error))
thread = threading.Thread(target=migrate)
started = time.monotonic()
try:
    thread.start()
    while time.monotonic() < end:
        query(selected, observed)
        counts[str(observed[0])] += 1
    thread.join(timeout=5)
    assert not thread.is_alive() and not errors, errors
    query(pages, statuses)
    intact = all(region[i] == 90 for i in range(0, size, page))
    report = dict(schema_version='cpu-prefetch-d286-migration-query-reproduction/1',
                  scope='SOFTWARE_DIAGNOSTIC_ONLY', boot_id=open('/proc/sys/kernel/random/boot_id').read().strip(),
                  kernel=os.uname().release, mapping_bytes=size, page_bytes=page,
                  private_mapping=True, mbind_node=0, mlock_succeeded=True, read_only=True,
                  migration_explicit=True, migrated_page_index=1916, global_controls_changed=False,
                  query_status_counts=dict(counts), migration_status_counts=dict(migration),
                  final_all_page_status_counts=dict(collections.Counter(map(str, statuses))),
                  contents_intact=intact, elapsed_seconds=time.monotonic()-started,
                  reproduced_missing_status=counts[str(-errno.ENOENT)] > 0,
                  historical_failure_root_cause_proven=False, experiment_authority=False)
    print(json.dumps(report, sort_keys=True), flush=True)
    assert intact and report['reproduced_missing_status']
finally:
    thread.join(timeout=5)
    assert libc.munlock(address, size) == 0
    region.close()
