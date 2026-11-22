"""D310 pilot extension inside the existing D233 store and shared quota.

The qualified parent authenticates current scoped admission. This file records
its exact binding and the already accepted owner approval; it grants no run.
"""
from dataclasses import asdict
import re
import stat

import stage17_formal_archive_custody_v1 as base
import stage17_formal_archive_v1 as archive
import stage17_s180_checkpoint_v1 as contract
import stage17_s180_archive_reservation_v1 as reservation

EXTENSION_SCHEMA = "cpu-prefetch-stage17-s180-storage-extension/1"


class ProgramStore(base.ProgramStore):
    def physical_accounting(self):
        """Charge original S180 native administrative metadata too.

        The base raw-working exemption predates these names. Their retained
        entry/result/per-capture attempt records are metadata, not raw buffers.
        Historical programmes/families and the base accounting are unchanged.
        """
        usage=super().physical_accounting()
        logical,allocated=usage.logical_size_bytes,usage.allocated_bytes
        quota,objects=usage.quota_bytes,usage.unique_objects
        for family,record in self._families.items():
            if record.get('storage_extension') is None:continue
            directory=self.root/'working'/family;before=directory.stat(follow_symlinks=False)
            if (not stat.S_ISDIR(before.st_mode) or (before.st_dev,before.st_ino)!=(record['device'],record['inode'])):
                raise base.CustodyError('S180 native metadata family identity differs')
            names=['s180-session-entry.json','s180-session-result.json',*(f's180-e{i}-attempt.json' for i in range(180))]
            for name in names:
                try:st=(directory/name).stat(follow_symlinks=False)
                except FileNotFoundError:continue
                if (not stat.S_ISREG(st.st_mode) or st.st_nlink!=1 or st.st_dev!=before.st_dev
                        or st.st_uid!=before.st_uid or st.st_mode&0o022):
                    raise base.CustodyError('unsafe retained S180 native metadata')
                disk=archive.checked_product(st.st_blocks,512)
                logical=archive.checked_sum(logical,st.st_size);allocated=archive.checked_sum(allocated,disk)
                quota=archive.checked_sum(quota,max(st.st_size,disk));objects=archive.checked_sum(objects,1)
            after=directory.stat(follow_symlinks=False)
            if (before.st_dev,before.st_ino)!=(after.st_dev,after.st_ino):
                raise base.CustodyError('S180 native metadata directory changed')
        self._check()
        return base.PhysicalUsage(logical,allocated,quota,objects)

    def __init__(self, *args, ext009_resolution_sha256, **kwargs):
        super().__init__(*args, **kwargs)
        self.ext009_resolution_sha256 = (None if ext009_resolution_sha256 is None else
            archive.sha(ext009_resolution_sha256, "S180 EXT009 binding"))
        self._extension_binding = None
        self._reserving_directory = False

    def reserve_family(self):
        return reservation.reserve_family(self)

    def inspect_reservation(self):
        return reservation.inspect_reservation(self)

    def bind_admission(self):
        return reservation.bind_admission(self)

    def prepare_family(self, family_id):
        self._check()
        if archive.sha(family_id, "S180 family") != self.family_id:
            raise base.CustodyError("S180 family differs before extension publication")
        if reservation.is_reserved_family(self):
            return reservation.prepare_reserved_family(self, family_id)
        if self.ext009_resolution_sha256 is None:
            raise base.CustodyError("S180 EXT009 is absent; only directory reservation is permitted")
        if any(key != self.family_id and value.get("storage_extension") is not None
               for key, value in self._families.items()):
            raise base.CustodyError("D310 permits only one S180 family in the shared program")
        document = dict(schema_version=EXTENSION_SCHEMA, approval_sha256=contract.APPROVAL_SHA256,
            blueprint_sha256=contract.BLUEPRINT_SHA256, program_scope_sha256=self.scope_sha256,
            family_id=self.family_id, ext009_resolution_sha256=self.ext009_resolution_sha256,
            program_id=self.scope["program_id"], storage_domain_id=self.scope["storage_domain_id"],
            shared_program_quota_bytes=base.PROGRAM_QUOTA, workspace_bytes=base.WORKSPACE,
            analysis_scratch_bytes=base.SCRATCH, reserve_bytes=base.RESERVE,
            independent_raw_backup=False, execution_authority=False,
            policy_id="D310-S180-LOSSLESS-STAND-PRIMARY-v1")
        raw = archive.canonical(document)
        name = "s180-extension-" + self.family_id + ".json"
        path = self.root / "metadata" / name
        if self.family_id in self._families:
            bound = self._families[self.family_id].get("storage_extension")
            if type(bound) is not dict:
                raise base.CustodyError("existing family lacks the explicit S180 extension")
            binding = base.BoundFile(**bound)
            if binding.file_name != name or self._read_bound(path, binding.binding(), self.limits.max_record_bytes) != raw:
                raise base.CustodyError("S180 extension changed or belongs to another admission")
        else:
            # An orphan extension from an interrupted attempt is retained; no
            # automatic adoption, repair, overwrite or retry is performed.
            if path.exists() or path.is_symlink():
                raise base.CustodyError("orphan S180 extension requires explicit recovery")
            binding = self.retain_metadata(name, raw)
        self._extension_binding = binding
        return super().prepare_family(family_id)

    def _family_scope_fields(self):
        if self._extension_binding is None:
            raise base.CustodyError("S180 storage extension is not bound")
        self._read_bound(self.root / "metadata" / self._extension_binding.file_name,
                         self._extension_binding.binding(), self.limits.max_record_bytes)
        if not self._reserving_directory:
            if reservation.is_reserved_family(self):
                reservation.verify_admission(self)
            elif self.ext009_resolution_sha256 is None:
                raise base.CustodyError("S180 capture has no EXT009 admission")
        return dict(storage_extension=asdict(self._extension_binding))

    def _checkpoint_contract(self, document):
        self._family_scope_fields()
        if (document.get("schema_version") != contract.SCHEMA
                or document.get("plan_sha256") != self.family_id
                or document.get("program_scope_sha256") != self.scope_sha256
                or document.get("scientific_validity") != "NOT_ASSESSED"
                or document.get("execution_authority") is not False):
            raise base.CustodyError("S180 checkpoint scope differs")
        return contract.original_references(document)

    def capture_archive_status(self, sources):
        if self._checkpoint[2]["native_complete"] is not True:
            return "ARCHIVED_FAILED_EVIDENCE"
        return super().capture_archive_status(sources)

    def capture_archive_receipt(self, checkpoint, artifacts, status):
        ordinal = self._checkpoint[2]["execution_ordinal"]
        document = dict(schema_version=contract.CUSTODY_SCHEMA,
            program_scope_sha256=self.scope_sha256, plan_sha256=self.family_id, execution_ordinal=ordinal,
            checkpoint=asdict(checkpoint), ledger_tip=asdict(self.ledger_binding()), artifacts=artifacts,
            status=status, storage_extension=asdict(self._extension_binding),
            scientific_validity="NOT_ASSESSED", execution_authority=False, phase18_authority=False)
        return f"s180-e{ordinal}-archive-custody.json", document

    def _custody_filename(self, name):
        return re.fullmatch(r"s180-e[0-9]+-archive-custody\.json", name) is not None

    def _custody_contract(self, document):
        checkpoint = self._checkpoint[2]
        expected_status = self.capture_archive_status(tuple(self._sources.values()))
        if (set(document) != contract.CUSTODY_FIELDS or document["schema_version"] != contract.CUSTODY_SCHEMA
                or document["program_scope_sha256"] != self.scope_sha256 or document["plan_sha256"] != self.family_id
                or document["execution_ordinal"] != checkpoint["execution_ordinal"]
                or document["checkpoint"] != asdict(self._checkpoint[0])
                or document["storage_extension"] != self._family_scope_fields()["storage_extension"]
                or document["status"] != expected_status or document["scientific_validity"] != "NOT_ASSESSED"
                or document["execution_authority"] is not False or document["phase18_authority"] is not False):
            raise base.CustodyError("S180 custody receipt differs from original checkpoint/extension")
