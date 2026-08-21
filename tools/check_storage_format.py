#!/usr/bin/env python3
"""Independent standard-library audit of RAW-OBS-U64LE-LP-RUNID-v1 fixtures."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import struct
import subprocess
import tempfile


FORMAT_ID = "RAW-OBS-U64LE-LP-RUNID-v1"
ENCODING = "FIXED_U64_LE_LENGTH_PREFIXED_UTF8_RUN_ID"
EXPECTED = {
    "producer": (
        2,
        120,
        "c6b47e3a4e73fa26e913ccd9101bd68e72bc3de4a488c3e3332fc65c7c61787c",
        (
            (0, 7, 500, 101, 1000, 102, 2000, 103, 3000, 104, 4000, 105, 5000, 0, 15),
            (1, 8, 1500, 102, 2000, 103, 3000, 104, 4000, 0, 0, 105, 5000, 0, 1),
        ),
    ),
    "consumer": (
        1,
        80,
        "0ed5a56f76a293b344eca47c684558d7fe6e46cebffd06981a446fd2c667a888",
        ((0, 7, 105, 5000, 106, 6000, 107, 7000, 108, 8000),),
    ),
    "joined": (
        1,
        192,
        "f02f4b2bc4a035dba7b9d5e91bb38a20aa2d309c19d81f49b9054aad9bc28f2a",
        ((0, 0, 7, 0, 0, 500, 1000, 2000, 3000, 4000, 5000, 5000,
          6000, 7000, 8000, 500, 1000, 2000, 3500, 2000, 2000, 2000,
          1000, 7500),),
    ),
}


def decode_rows(data: bytes, row_count: int, body_bytes: int) -> tuple[tuple[int, ...], ...]:
    run_id = b"r"
    prefix_bytes = 8
    stride = prefix_bytes + body_bytes
    if len(data) != row_count * stride:
        raise ValueError("exact row/byte count mismatch")
    rows: list[tuple[int, ...]] = []
    for offset in range(0, len(data), stride):
        length = struct.unpack_from("<I", data, offset)[0]
        if length != len(run_id) or data[offset + 4:offset + 5] != run_id:
            raise ValueError("literal row run_id mismatch")
        if data[offset + 5:offset + prefix_bytes] != bytes(prefix_bytes - 5):
            raise ValueError("nonzero prefix padding")
        rows.append(struct.unpack_from(f"<{body_bytes // 8}Q", data, offset + prefix_bytes))
    return tuple(rows)


def verify_envelope(path: pathlib.Path, kind: str, rows: int, byte_count: int,
                    sha256: str) -> None:
    raw = path.read_bytes()
    if raw.endswith(b"\n") or raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError("envelope has a BOM or trailing newline")
    document = json.loads(raw)
    expected_kind = {"producer": "PRODUCER", "consumer": "CONSUMER",
                     "joined": "JOINED_DERIVED"}[kind]
    exact = {
        "schema_version": "2.0.0-pre.2",
        "protocol_version": "2.0.0-pre.2",
        "stream_kind": expected_kind,
        "logical_row_schema_version": "2.0.0-pre.2",
        "physical_format_record_id": FORMAT_ID,
        "encoding": ENCODING,
        "time_unit": "PICOSECONDS",
        "endianness": "LITTLE_ENDIAN",
        "compression": "NONE",
        "row_count": rows,
        "byte_count": byte_count,
        "immutable_ordering": True,
        "artifact_sha256": sha256,
    }
    for field, value in exact.items():
        if document.get(field) != value:
            raise ValueError(f"envelope {field} mismatch")
    if document["run_id"] != "r":
        raise ValueError("envelope run_id mismatch")
    if document["storage"]["mode"] != "EXTERNAL_IMMUTABLE_ARTIFACT":
        raise ValueError("envelope storage mode mismatch")
    if kind == "joined" and len(document.get("source_artifacts", [])) != 2:
        raise ValueError("joined source references missing")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture-generator", type=pathlib.Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="cpu-prefetch-stage11-format-") as directory:
        root = pathlib.Path(directory)
        subprocess.run([args.fixture_generator, root], check=True)
        for kind, (row_count, body_bytes, expected_hash, expected_rows) in EXPECTED.items():
            data = (root / f"{kind}.raw").read_bytes()
            observed_hash = hashlib.sha256(data).hexdigest()
            if observed_hash != expected_hash:
                raise ValueError(f"{kind} SHA-256 mismatch: {observed_hash}")
            if decode_rows(data, row_count, body_bytes) != expected_rows:
                raise ValueError(f"{kind} decoded words mismatch")
            verify_envelope(root / f"{kind}.json", kind, row_count, len(data),
                            expected_hash)
        if (root / "empty.raw").read_bytes() != b"":
            raise ValueError("empty stream is not empty")
        if hashlib.sha256(b"").hexdigest() != (
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        ):
            raise ValueError("standard SHA-256 empty vector mismatch")
        for document_name in ("integrity.json", "copy-ledger.json"):
            document_bytes = (root / document_name).read_bytes()
            if document_bytes.endswith(b"\n") or document_bytes.startswith(b"\xef\xbb\xbf"):
                raise ValueError(f"{document_name} has a BOM or trailing newline")
            json.loads(document_bytes)
    print("storage-format-check: PASS (C++ encoder/Python decoder, 4 streams, 3 envelopes, 2 canonical records)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
