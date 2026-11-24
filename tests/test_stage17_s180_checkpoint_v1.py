"""S180 custody contract is independent of scientific validity, software only."""
import copy
from dataclasses import asdict
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import stage17_s180_checkpoint_v1 as c
import stage17_formal_archive_custody_v1 as store
import stage17_formal_checkpoint_v1 as legacy
from test_stage17_formal_checkpoint_v1 import fixture as old_fixture


def fixture():
    old, _, _ = old_fixture()
    native = old["native_result_after_cleanup"]
    native["cleanup_scope"] = "PRIVATE_CAPTURE_ONLY_SHARED_DATA_REMAINS_FAMILY_OWNED"
    for value in [*native["worker_mappings"], *native["worker_stacks"], native["core_mapping"],
                  native["monitor_mapping"], native["controller_stack"]]:
        value["mapping"] = None  # Explicitly synthetic; no native mapping was performed.
    sources = tuple(store.SourceBinding("b"*64+":"+name, store.BoundFile(name, 0, "a"*64),
        store.archive.PhysicalBinding(0, "a"*64), None) for name in c.capture_names(0))
    refs = []
    for s in sources:
        role, schema, media = c.artifact_identity(0, s.expected.file_name)
        refs.append(dict(role=role, schema_identity=schema, media_type=media, **asdict(s.expected)))
    document = dict(schema_version=c.SCHEMA, session_id="software-only-s180", plan_sha256="b"*64,
        program_scope_sha256="c"*64, execution_ordinal=0, native_complete=True,
        native_result_after_private_cleanup=native, artifacts=refs, shared_data_still_family_owned=True,
        scientific_validity="NOT_ASSESSED", execution_authority=False, phase18_authority=False)
    return document, sources


class S180CheckpointTests(unittest.TestCase):
    def validate(self, d, sources):
        return c.validate_checkpoint(d, plan_sha256="b"*64, program_scope_sha256="c"*64,
            session_id="software-only-s180", ordinal=0, sources=sources)

    def test_complete_original_roles_and_private_cleanup_do_not_claim_family_release(self):
        d, sources = fixture()
        self.assertIsNone(self.validate(d, sources))
        self.assertIsNone(c.require_private_cleanup_for_codec(d["native_result_after_private_cleanup"]))
        self.assertEqual(c.original_references(d), [asdict(s.expected) for s in sources])

    def test_legacy_rejects_s180_and_s180_rejects_legacy(self):
        d, sources = fixture()
        with self.assertRaises(c.ArchiveError):
            legacy.validate_checkpoint(d, action="Q16a", plan_sha256="b"*64, capture={}, sources=sources)
        d["schema_version"] = legacy.SCHEMA
        with self.assertRaises(c.ArchiveError): self.validate(d, sources)

    def test_foreign_scope_role_order_authority_and_cleanup_are_rejected(self):
        for mutate in (lambda d: d.update(program_scope_sha256="d"*64),
                       lambda d: d.update(execution_ordinal=True),
                       lambda d: d.update(execution_authority=True),
                       lambda d: d.update(scientific_validity="VALID"),
                       lambda d: d["artifacts"][0].update(role="Q16C_PRIMARY_RAW"),
                       lambda d: d["artifacts"].reverse(),
                       lambda d: d["native_result_after_private_cleanup"]["worker_mappings"][0]["unmap"].update(return_value=-1)):
            d, sources = fixture(); mutate(d)
            with self.assertRaises(c.ArchiveError): self.validate(d, sources)

    def test_failed_prefix_is_retained_and_not_declared_complete(self):
        d, sources = fixture()
        d["artifacts"] = d["artifacts"][:2]
        d["native_complete"] = False
        d["native_result_after_private_cleanup"]["stop"] = 12
        self.validate(d, sources[:2])
        d["native_complete"] = True
        with self.assertRaises(c.ArchiveError): self.validate(d, sources[:2])

    def test_failed_unmapped_memory_can_archive_but_live_private_memory_cannot(self):
        d, _ = fixture(); n = d["native_result_after_private_cleanup"]
        n["stop"] = 12
        m = n["core_mapping"]
        m["mapping"] = dict(address=4096, error_number=0)  # Software-only address token.
        m["unmap"]["return_value"] = -1
        with self.assertRaises(c.ArchiveError): c.require_private_cleanup_for_codec(n)
        m["unmap"]["return_value"] = 0
        self.assertIsNone(c.require_private_cleanup_for_codec(n))


if __name__ == "__main__": unittest.main()
