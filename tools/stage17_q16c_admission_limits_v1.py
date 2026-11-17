"""D273 bounded complete-inventory admission for the new Q16c release only.

The frozen 919c486 inventory has4119 entries. Historical4096 limits remain
unchanged. This private namespace admits at most8192 inventory entries while
retaining the original32MiB/file,256MiB total,120s and4096 metadata-read limits.
"""
import types
import stage17_q16a_continuation_admission_v1 as original
import stage17_archive_metadata_fast_v1 as metadata

INVENTORY_ENTRIES = 8192


def make_admission():
    index = metadata._clone(original._inventory,
        {**original._inventory.__globals__, 'MAX_FILES': INVENTORY_ENTRIES})
    return types.SimpleNamespace(**{**vars(original), '_inventory': index})


ADMISSION = make_admission()


def make_handoffs():
    """Keep all original compatibility checks, with the private inventory seam."""
    import stage17_q16a_q16c_descriptive_handoff_v1 as q16a
    import stage17_q16b_q16c_descriptive_handoff_v1 as q16b
    release = metadata._clone(q16a._release,
        {**q16a._release.__globals__, 'admission': ADMISSION})
    a = types.SimpleNamespace(**{**vars(q16a), 'admission': ADMISSION, '_release': release})
    a.consume = metadata._clone(q16a.consume,
        {**q16a.consume.__globals__, **vars(a)})
    b = types.SimpleNamespace(**{**vars(q16b), 'admission': ADMISSION, 'compatibility': a})
    b.consume = metadata._clone(q16b.consume,
        {**q16b.consume.__globals__, **vars(b)})
    return a, b
