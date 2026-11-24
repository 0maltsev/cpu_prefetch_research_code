"""Actual pinned C++ FD encoder -> independent Python inverse, software only."""
from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import io
import json
import os
from pathlib import Path
import resource
import struct
import subprocess
import sys
import tempfile
import time
import unittest

from test_stage17_formal_archive_v1 import ArchiveFixture, codec_limit, digest
import stage17_formal_archive_v1 as a


class NativeArchiveBridge(unittest.TestCase):
    encoder: Path | None = None
    fixture: Path | None = None

    def setUp(self):
        if self.encoder is None:
            self.skipTest("requires explicit --encoder native binary")
        self.temp = tempfile.TemporaryDirectory(prefix="d233-native-bridge-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.f = ArchiveFixture(self.root)
        self.f.profile = replace(self.f.profile, encoder_sha256=digest(self.encoder.read_bytes()))
        self.counter = 0

    def native_encode(self, data, header, *, plan_mutant=None, result_limit=65536):
        self.counter += 1
        directory = self.root / str(self.counter)
        directory.mkdir()
        source, plan_path, target, result = (directory/n for n in ("source", "plan", "archive", "result"))
        source.write_bytes(data)
        keys = ("artifact_id artifact_role canonical_format run_id phase worker canonical_size_bytes canonical_sha256 "
                "codec_id row_bytes fallback_reason implementation_profile_sha256 encoder_sha256 zstd_library_sha256").split()
        plan = dict(identity={k: header[k] for k in keys}, limits=dict(window_log=self.f.profile.window_log,
            maximum_header_bytes=self.f.limits.max_header_bytes,
            maximum_decoded_block_bytes=self.f.limits.max_decoded_block_bytes,
            maximum_encoded_block_bytes=self.f.limits.max_frame_bytes,
            maximum_archive_bytes=self.f.limits.max_archive_bytes,
            maximum_observed_context_bytes=64*1024**2, io_chunk_bytes=1024*1024,
            maximum_io_calls=100000, deadline_monotonic_ns=self.f.limits.deadline_ns))
        if plan_mutant:
            plan_mutant(plan)
        plan_path.write_bytes(a.canonical(plan))
        def constrain():
            resource.setrlimit(resource.RLIMIT_AS, (2*1024**3, 2*1024**3))
        with source.open("rb") as src, plan_path.open("rb") as request, target.open("xb") as out, result.open("xb") as report:
            fds = (src.fileno(), out.fileno(), request.fileno(), report.fileno())
            command = [str(self.encoder), "--encode-stage17-archive-v1"]
            for name, fd in zip(("--source-fd", "--archive-fd", "--plan-fd", "--result-fd"), fds):
                command.extend((name, str(fd)))
            command.extend(("--plan-byte-limit", "16384"))
            command.extend(("--result-byte-limit", str(result_limit)))
            process = subprocess.run(command, pass_fds=fds, capture_output=True, timeout=30, preexec_fn=constrain)
        self.assertEqual(source.read_bytes(), data)
        report = json.loads(result.read_bytes()) if result.stat().st_size else None
        return process, report, target

    def roundtrip(self, data, header, role):
        process, report, path = self.native_encode(data, header)
        self.assertEqual(process.returncode, 0, process.stderr.decode(errors="replace"))
        self.assertEqual(report["stop"], "COMPLETE_STAGING_SYNCED")
        physical = a.PhysicalBinding(path.stat().st_size, digest(path.read_bytes()))
        self.assertEqual(report["observed_archive_sha256"], physical.sha256)
        self.assertEqual(report["observed_canonical_sha256"], digest(data))
        sink = io.BytesIO()
        with codec_limit():
            proof = a.verify_archive(path, expected_header=header, role=role, physical=physical,
                profile=self.f.profile, limits=self.f.limits, sink=sink)
        self.assertEqual(sink.getvalue(), data)
        self.assertEqual(proof.canonical.sha256, digest(data))
        # An independently constructed golden also agrees on all physical bytes.
        self.assertEqual(path.read_bytes(), self.f.encode(data, header))
        return path

    def test_native_empty_row_boundaries_wraps_and_determinism(self):
        for rows in (0, 1, 8191, 8192, 8193):
            data = b"".join(struct.pack("<Q", ((1<<64)-1-i if i%2 else i)) for i in range(rows))
            h,r = self.f.header(data)
            with self.subTest(rows=rows):
                self.roundtrip(data,h,r)

    def test_native_byte_blocks_and_wholefile_tail_fallback(self):
        for n in (0, 1, a.BYTE_BLOCK, a.BYTE_BLOCK+7):
            data = (bytes(range(256))*((n+255)//256))[:n]
            h,r = self.f.header(data,"bytes")
            with self.subTest(bytes=n):
                self.roundtrip(data,h,r)
        data = b"incomplete-native-prefix\xff"
        h,r = self.f.header(data,"producer",fallback="incomplete-row-prefix")
        self.roundtrip(data,h,r)

    def test_native_exact_lp_rows_all_three_canonical_geometries(self):
        for layout in ("producer","consumer","demand"):
            h,r = self.f.header(b"",layout)
            encoded = h["run_id"].encode()
            prefix = struct.pack("<I",len(encoded))+encoded
            prefix += bytes((-len(prefix))%8)
            body = bytes((i%256 for i in range(h["row_bytes"]-len(prefix))))
            data = (prefix+body)*8193
            h,r = self.f.header(data,layout)
            with self.subTest(layout=layout):
                self.roundtrip(data,h,r)

    def test_native_bound_failures_preserve_source_and_never_emit_valid_archive(self):
        data = bytes(8193*8)
        h,r = self.f.header(data)
        mutants = (
            lambda p:p["identity"].update(encoder_sha256="0"*64),
            lambda p:p["identity"].update(zstd_library_sha256="0"*64),
            lambda p:p["identity"].update(canonical_sha256="0"*64),
            lambda p:p["limits"].update(deadline_monotonic_ns=time.monotonic_ns()-1),
            lambda p:p["limits"].update(maximum_archive_bytes=1),
            lambda p:p["limits"].update(maximum_observed_context_bytes=1),
        )
        for index, mutate in enumerate(mutants):
            process, report, path = self.native_encode(data,h,plan_mutant=mutate)
            with self.subTest(mutant=index):
                self.assertNotEqual(process.returncode,0)
                if report is not None:
                    self.assertNotEqual(report["stop"],"COMPLETE_STAGING_SYNCED")
                with codec_limit(), self.assertRaises(a.ArchiveError):
                    a.verify_archive(path,expected_header=h,role=r,
                        physical=a.PhysicalBinding(path.stat().st_size,digest(path.read_bytes())),
                        profile=self.f.profile,limits=self.f.limits)
        process,report,path = self.native_encode(data,h,result_limit=1)
        self.assertNotEqual(process.returncode,0)
        self.assertIsNone(report)  # source-qualified check occurs before result write
        # A valid staging object alone never supplies a successful result/custody.
        self.assertTrue(path.exists())

    def test_actual_publishers_raw_and_untouched_control_roundtrip(self):
        if self.fixture is None:
            self.skipTest("requires explicit --fixture publisher binary")
        from test_stage17_q16a_capture_validation_v1 import Fixture as RingFixture
        from test_stage17_formal_service_capture_validation_v1 import Fixture as ServiceFixture
        for mode in ("ring", "service", "scheduled"):
            seed = self.root/(mode+"-seed")
            seed.mkdir()
            f = RingFixture(seed) if mode=="ring" else ServiceFixture(seed,scheduled=mode=="scheduled")
            if mode!="ring":
                f.capture.update(package="L1", cell_ordinal=144 if mode=="scheduled" else 48,
                    linked_order=dict(seed_id="node-seed",seed_hex="c"*64,namespace_id="node-namespace",arena_alignment_bytes=4096))
            config = self.root/(mode+"-input.json")
            config.write_text(json.dumps(dict(capture=f.capture,resources=f.resources,monitoring=f.monitoring,hardware_control=f.hardware)))
            output = self.root/(mode+"-original")
            command = [str(self.fixture)] + ([] if mode=="ring" else ["--mode",mode]) + [str(config),str(output)]
            result = subprocess.run(command,capture_output=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stderr.decode(errors="replace"))
            original = {p.name:digest(p.read_bytes()) for p in output.iterdir()}
            for path in output.iterdir():
                data = path.read_bytes()
                phase = "warmup" if "warmup" in path.name else "measurement" if "measurement" in path.name else None
                if path.name.endswith("-demand.bin"):
                    layout = "demand"
                elif path.name.endswith("-producer.bin"):
                    layout = "producer"
                elif path.name.endswith("-consumer.bin"):
                    layout = "consumer"
                elif path.suffix==".bin":
                    layout = "u64"
                else:
                    layout = "bytes"
                h,r = self.f.header(b"",layout)
                h.update(artifact_id=path.name,phase=phase,canonical_size_bytes=len(data),canonical_sha256=digest(data))
                if layout in ("producer","consumer","demand"):
                    h["run_id"] = f.capture[phase]["run_id"]
                    h["worker"] = "consumer" if "consumer" in path.name else "producer"
                    h["row_bytes"] = r.row_bytes(h["run_id"])
                    h["block_size_bytes"] = 8192*h["row_bytes"]
                h["row_count"] = len(data)//h["row_bytes"] if h["row_bytes"] else None
                h["block_count"] = (len(data)+h["block_size_bytes"]-1)//h["block_size_bytes"]
                with self.subTest(mode=mode,file=path.name):
                    self.roundtrip(data,h,r)
            self.assertEqual(original,{p.name:digest(p.read_bytes()) for p in output.iterdir()})


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--encoder",type=Path,required=True)
    parser.add_argument("--fixture",type=Path)
    args,rest=parser.parse_known_args()
    NativeArchiveBridge.encoder=args.encoder.resolve()
    NativeArchiveBridge.fixture=args.fixture.resolve() if args.fixture else None
    unittest.main(argv=[sys.argv[0],*rest])
