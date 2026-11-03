"""Independent, pure validation of retained discovery environmental evidence.

No filesystem/hardware access, collection, retries, thresholds or authority.
The caller admits raw artifact bytes and binds source plans, declared ranges and
base-page geometry first. Syscall records establish internally consistent bounded
delivery, not authenticity or an atomic snapshot. Only smaps page/lock facts are
interpreted; all other source contents retain UNFROZEN_LIMITS status.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from typing import Any

SCHEMA_VERSION = "cpu-prefetch-discovery-environment-validation/1"
CONTROL_VERSION = "cpu-prefetch-stage17-discovery-control/1"
GROUP_ORDER = (
    "WARMUP_BEFORE", "WARMUP_DURING", "WARMUP_AFTER",
    "MEASUREMENT_BEFORE", "MEASUREMENT_DURING", "MEASUREMENT_AFTER",
)
SMAPS_PATH = b"/proc/self/smaps"
MAX_U64 = (1 << 64) - 1
MAX_I64 = (1 << 63) - 1
PREPARATION_READY = 4
SAMPLE_NOT_STARTED = 0
SAMPLE_NOT_REQUESTED = 5
SAMPLE_COMPLETE = 11
VMA_HEADER = re.compile(
    rb"([0-9a-fA-F]+)-([0-9a-fA-F]+)[ \t]+([r-][w-][x-][ps])"
    rb"[ \t]+([0-9a-fA-F]+)[ \t]+([0-9a-fA-F]+):([0-9a-fA-F]+)"
    rb"[ \t]+([0-9]+)(?:[ \t]+(.*))?"
)
FIELD_LINE = re.compile(rb"([A-Za-z][A-Za-z0-9_]*):[ \t]*(.*)")
KB_VALUE = re.compile(rb"([0-9]+)[ \t]+kB")
PAGE_FIELDS = (b"Size", b"KernelPageSize", b"MMUPageSize", b"AnonHugePages", b"Locked")
OTHER_HUGE_FIELDS = (b"ShmemPmdMapped", b"FilePmdMapped", b"Shared_Hugetlb", b"Private_Hugetlb")


class EnvironmentEvidenceError(ValueError):
    """Path-specific missing, contradictory or unsupported evidence."""


def _fail(path: str, reason: str) -> None:
    raise EnvironmentEvidenceError(f"{path}: {reason}")


def _object(value: Any, fields: str, path: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != set(fields.split()):
        _fail(path, "unexpected or missing fields")
    return value


def _uint(value: Any, path: str, minimum: int = 0, maximum: int = MAX_U64) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        _fail(path, f"requires integer in [{minimum}, {maximum}]")
    return value


def _equal(value: Any, expected: Any, path: str) -> None:
    if type(value) is not type(expected) or value != expected:
        _fail(path, f"requires {expected!r}")


def _bytes(value: Any, path: str) -> bytes:
    if not isinstance(value, list) or any(type(byte) is not int or not 0 <= byte <= 255 for byte in value):
        _fail(path, "requires exact raw byte array")
    return bytes(value)


def _call(value: Any, path: str) -> int:
    obj = _object(value, "return_value error_number", path)
    result = obj["return_value"]
    if type(result) is not int or not -MAX_I64 - 1 <= result <= MAX_I64:
        _fail(path, "invalid signed syscall result")
    _equal(obj["error_number"], 0, path + ".error_number")
    if result < 0:
        _fail(path, "failed syscall")
    return result


def _source_plan(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail(path, "requires frozen source plan")
    path_key = "path_bytes" if "path_bytes" in value else "path"
    obj = _object(value, f"{path_key} byte_capacity chunk_bytes max_data_reads requested", path)
    if path_key == "path_bytes":
        raw_path = _bytes(obj[path_key], path + ".path_bytes")
    else:
        if not isinstance(obj[path_key], str):
            _fail(path, "frozen path must be a string or explicit raw byte array")
        try:
            raw_path = obj[path_key].encode("utf-8", errors="strict")
        except UnicodeError as error:
            raise EnvironmentEvidenceError(f"{path}: invalid frozen UTF-8 path") from error
    if not raw_path.startswith(b"/") or b"\x00" in raw_path:
        _fail(path, "source path must be absolute and NUL-free")
    capacity = _uint(obj["byte_capacity"], path + ".byte_capacity", 1, MAX_I64 - 1)
    chunk = _uint(obj["chunk_bytes"], path + ".chunk_bytes", 1, capacity)
    reads = _uint(obj["max_data_reads"], path + ".max_data_reads", 1, MAX_I64)
    requested = obj["requested"]
    if not isinstance(requested, list) or len(requested) != 6 or any(type(flag) is not bool for flag in requested) or not any(requested):
        _fail(path, "requires six explicit requests and at least one observation")
    return {"path_bytes": list(raw_path), "byte_capacity": capacity, "chunk_bytes": chunk,
            "max_data_reads": reads, "requested": requested.copy()}


def _read(value: Any, offset: int, requested: int, path: str) -> int:
    obj = _object(value, "offset requested_bytes observed", path)
    _equal(obj["offset"], offset, path + ".offset")
    _equal(obj["requested_bytes"], requested, path + ".requested_bytes")
    result = _call(obj["observed"], path + ".observed")
    if result > requested:
        _fail(path, "read result exceeds requested bytes")
    return result


def _no_probe(sample: dict[str, Any], path: str) -> None:
    probe = _object(sample["eof_probe"], "offset requested_bytes observed", path + ".eof_probe")
    _equal(probe["offset"], 0, path + ".eof_probe.offset")
    _equal(probe["requested_bytes"], 0, path + ".eof_probe.requested_bytes")
    _equal(probe["observed"], None, path + ".eof_probe.observed")
    _equal(sample["probe_byte"], None, path + ".probe_byte")


def _sample(value: Any, plan: dict[str, Any], source: int, group: int) -> bytes | None:
    path = f"$.environment_samples[{source * 6 + group}]"
    obj = _object(value, "source_index group_index attempted stop captured_bytes byte_capacity data_reads read_capacity raw_bytes reads eof_probe probe_byte", path)
    _equal(obj["source_index"], source, path + ".source_index")
    _equal(obj["group_index"], group, path + ".group_index")
    _equal(obj["byte_capacity"], plan["byte_capacity"], path + ".byte_capacity")
    _equal(obj["read_capacity"], plan["max_data_reads"], path + ".read_capacity")
    captured = _uint(obj["captured_bytes"], path + ".captured_bytes", maximum=plan["byte_capacity"])
    count = _uint(obj["data_reads"], path + ".data_reads", maximum=plan["max_data_reads"])
    if not isinstance(obj["reads"], list) or len(obj["reads"]) != count:
        _fail(path, "read count differs from retained read records")
    if not plan["requested"][group]:
        if type(obj["attempted"]) is not bool:
            _fail(path, "attempted must be a boolean")
        _equal(obj["stop"], SAMPLE_NOT_REQUESTED if obj["attempted"] else SAMPLE_NOT_STARTED, path + ".stop")
        _equal(captured, 0, path + ".captured_bytes")
        _equal(count, 0, path + ".data_reads")
        _equal(obj["raw_bytes"], [] if obj["attempted"] else None, path + ".raw_bytes")
        _no_probe(obj, path)
        return None
    _equal(obj["attempted"], True, path + ".attempted")
    _equal(obj["stop"], SAMPLE_COMPLETE, path + ".stop")
    raw = _bytes(obj["raw_bytes"], path + ".raw_bytes")
    if len(raw) != captured or count == 0:
        _fail(path, "captured prefix or read count is inconsistent")
    offset = 0
    ended = False
    for index, read in enumerate(obj["reads"]):
        remaining = plan["byte_capacity"] - offset
        if remaining == 0 or ended:
            _fail(path, "unplanned read after capacity/EOF")
        actual = _read(read, offset, min(remaining, plan["chunk_bytes"]), path + f".reads[{index}]")
        offset += actual
        ended = actual == 0
    if offset != captured:
        _fail(path, "read returns do not explain captured prefix")
    if ended:
        _no_probe(obj, path)
    else:
        if offset != plan["byte_capacity"] and count != plan["max_data_reads"]:
            _fail(path, "premature EOF probe before finite budget boundary")
        _equal(_read(obj["eof_probe"], offset, 1, path + ".eof_probe"), 0, path + ".eof_probe.return_value")
        _equal(obj["probe_byte"], None, path + ".probe_byte")
    return raw


@dataclass(frozen=True)
class SmapsVma:
    begin: int
    end: int
    fields: dict[bytes, bytes]


def _kilobytes(fields: dict[bytes, bytes], key: bytes, path: str) -> int:
    match = KB_VALUE.fullmatch(fields.get(key, b""))
    if match is None:
        _fail(path, f"missing/malformed {key.decode('ascii')} kB field")
    # Bound conversion independently of Python's configurable decimal digit
    # limit. Leading zeros do not change the retained number's meaning.
    digits = match[1].lstrip(b"0") or b"0"
    if len(digits) > 20:
        _fail(path, "kB value exceeds unsigned 64-bit byte extent")
    return _uint(int(digits) * 1024, path + "." + key.decode("ascii"))


def parse_smaps(raw: bytes) -> tuple[SmapsVma, ...]:
    """Parse complete byte-oriented smaps blocks; no pathname decoding."""
    if not isinstance(raw, bytes) or not raw or not raw.endswith(b"\n") or b"\x00" in raw:
        _fail("smaps", "requires nonempty complete newline-terminated bytes")
    output: list[SmapsVma] = []
    current: SmapsVma | None = None
    for line_number, line in enumerate(raw.split(b"\n")[:-1], 1):
        header = VMA_HEADER.fullmatch(line)
        if header:
            if any(len(part.lstrip(b"0")) > 16 for part in (header[1], header[2])):
                _fail(f"smaps.line[{line_number}]", "VMA address exceeds unsigned 64-bit range")
            begin, end = int(header[1], 16), int(header[2], 16)
            if not 0 <= begin < end <= MAX_U64 or (current is not None and begin < current.end):
                _fail(f"smaps.line[{line_number}]", "overlapping, unsorted or invalid VMA range")
            current = SmapsVma(begin, end, {})
            output.append(current)
            continue
        field = FIELD_LINE.fullmatch(line)
        if current is None or field is None or field[1] in current.fields:
            _fail(f"smaps.line[{line_number}]", "malformed or duplicate smaps field")
        current.fields[field[1]] = field[2].strip(b" \t")
    for index, vma in enumerate(output):
        path = f"smaps.vma[{index}]"
        for key in PAGE_FIELDS:
            _kilobytes(vma.fields, key, path)
        if _kilobytes(vma.fields, b"Size", path) != vma.end - vma.begin:
            _fail(path, "Size does not match VMA extent")
        if b"VmFlags" not in vma.fields or any(re.fullmatch(rb"[a-z]{2}", token) is None for token in vma.fields[b"VmFlags"].split()):
            _fail(path, "missing/malformed VmFlags terminator")
    if not output:
        _fail("smaps", "no VMA blocks")
    return tuple(output)


def _regions(value: Any, base_page_bytes: int, path: str) -> list[dict[str, int]]:
    if not isinstance(value, list) or len(value) != 7:
        _fail(path, "requires exactly seven declared regions")
    result = []
    for index, item in enumerate(value):
        row = _object(item, "address bytes expected_node", f"{path}[{index}]")
        start = _uint(row["address"], path + ".address", 1)
        size = _uint(row["bytes"], path + ".bytes", 1)
        node = _uint(row["expected_node"], path + ".expected_node")
        if start % base_page_bytes or size % base_page_bytes or start + size > MAX_U64:
            _fail(path, "region is unaligned or overflows")
        if any(start < prior["address"] + prior["bytes"] and prior["address"] < start + size for prior in result):
            _fail(path, "declared regions overlap")
        result.append({"address": start, "bytes": size, "expected_node": node})
    return result


def _page_policy(vmas: tuple[SmapsVma, ...], regions: list[dict[str, int]], page: int) -> list[dict[str, Any]]:
    evidence = []
    for index, region in enumerate(regions):
        cursor, end = region["address"], region["address"] + region["bytes"]
        covering = []
        for vma in vmas:
            if vma.end <= cursor or vma.begin >= end:
                continue
            path = f"smaps.region[{index}]"
            if vma.begin % page or vma.end % page:
                _fail(path, "VMA boundaries are unaligned to prospective base page")
            if vma.begin > cursor:
                _fail(path, "VMA gap in declared region")
            for key in (b"KernelPageSize", b"MMUPageSize"):
                if _kilobytes(vma.fields, key, path) != page:
                    _fail(path, "observed page size differs from prospective base page")
            if _kilobytes(vma.fields, b"AnonHugePages", path) != 0:
                _fail(path, "anonymous huge pages observed")
            for key in OTHER_HUGE_FIELDS:
                if key in vma.fields and _kilobytes(vma.fields, key, path) != 0:
                    _fail(path, "huge-page mapping observed")
            size = _kilobytes(vma.fields, b"Size", path)
            if _kilobytes(vma.fields, b"Locked", path) != size:
                _fail(path, "Locked does not establish full VMA coverage of region")
            covering.append({"vma_begin": vma.begin, "vma_end": vma.end,
                             "covered_begin": cursor, "covered_end": min(end, vma.end),
                             "locked_bytes": size, "kernel_page_bytes": page, "mmu_page_bytes": page})
            cursor = min(end, vma.end)
            if cursor == end:
                break
        if cursor != end:
            _fail(f"smaps.region[{index}]", "missing full VMA coverage")
        evidence.append({"region_index": index, "coverage": covering})
    return evidence


def validate_environment(control: dict[str, Any], source_plans: list[dict[str, Any]],
                         expected_regions: list[dict[str, int]], *,
                         base_page_bytes: int) -> dict[str, Any]:
    """Verify delivery/page policy; raise EnvironmentEvidenceError on any gap.

    Accept the publisher's decoded native control, frozen monitoring source
    plans (``path`` UTF-8 text or explicit ``path_bytes``), and seven independently
    bound ``{address, bytes, expected_node}`` ranges. The caller supplies verified
    base-page geometry and admits the JSON artifact, including duplicate-key
    rejection and custody/binding checks. This function neither reads a host
    page size nor discovers a source set.

    Publisher inputs are ``regions``, ``environment_group_order``,
    ``environment_preparations`` (raw path/plan, attempted/released, stop and
    open/close results), and source-major ``environment_samples`` (six each).
    A sample retains actual ``raw_bytes``, ``captured_bytes``, finite ``reads``
    with offset/request/result triples, and ``eof_probe``/``probe_byte`` facts.
    Missing/failed requested evidence never becomes an empty successful sample.
    Other native-control admission and session checks remain the caller's job.
    """
    page = _uint(base_page_bytes, "expected.base_page_bytes", 1)
    if page & (page - 1):
        _fail("expected.base_page_bytes", "requires power-of-two verified geometry")
    if not isinstance(control, dict):
        _fail("$", "requires native control object")
    _equal(control.get("schema_version"), CONTROL_VERSION, "$.schema_version")
    _equal(control.get("environment_group_order"), list(GROUP_ORDER), "$.environment_group_order")
    regions = _regions(expected_regions, page, "expected.regions")
    observed_regions = _regions(control.get("regions"), page, "$.regions")
    if observed_regions != regions:
        _fail("$.regions", "declared regions differ from independently bound geometry")
    if not isinstance(source_plans, list) or not source_plans:
        _fail("expected.sources", "requires explicit nonempty frozen source plans")
    plans = [_source_plan(value, f"expected.sources[{index}]") for index, value in enumerate(source_plans)]
    paths = [bytes(plan["path_bytes"]) for plan in plans]
    if len(set(paths)) != len(paths) or SMAPS_PATH not in paths:
        _fail("expected.sources", "requires unique sources including /proc/self/smaps")
    smaps_index = paths.index(SMAPS_PATH)
    if plans[smaps_index]["requested"] != [True] * 6:
        _fail("expected.sources", "smaps is mandatory in every observation group")
    preparations, samples = control.get("environment_preparations"), control.get("environment_samples")
    if not isinstance(preparations, list) or len(preparations) != len(plans) or not isinstance(samples, list) or len(samples) != len(plans) * 6:
        _fail("$", "missing/extra environment preparations or six-group samples")
    sources = []
    smaps_groups = []
    for source, plan in enumerate(plans):
        path = f"$.environment_preparations[{source}]"
        prep = _object(preparations[source], "attempted released stop open close plan", path)
        _equal(prep["attempted"], True, path + ".attempted")
        _equal(prep["released"], True, path + ".released")
        _equal(prep["stop"], PREPARATION_READY, path + ".stop")
        retained = _object(prep["plan"], "path_bytes byte_capacity chunk_bytes max_data_reads requested", path + ".plan")
        retained_plan = _source_plan(retained, path + ".plan")
        if retained_plan != plan:
            _fail(path + ".plan", "observed source plan differs from frozen plan")
        _call(prep["open"], path + ".open")
        _equal(_call(prep["close"], path + ".close"), 0, path + ".close.return_value")
        groups = []
        for group in range(6):
            raw = _sample(samples[source * 6 + group], plan, source, group)
            groups.append({"group_index": group, "requested": plan["requested"][group],
                           "captured_bytes": None if raw is None else len(raw),
                           "sha256": None if raw is None else hashlib.sha256(raw).hexdigest()})
            if source == smaps_index:
                smaps_groups.append({"group_index": group,
                                     "regions": _page_policy(parse_smaps(raw), regions, page)})
        sources.append({"source_index": source, "path_bytes": plan["path_bytes"], "groups": groups})
    return {"schema_version": SCHEMA_VERSION, "status": "VERIFIED_DELIVERY_AND_PAGE_POLICY",
            "environmental_limits": "UNFROZEN_LIMITS", "scientific_validity": "NOT_ASSESSED",
            "execution_authority": False, "base_page_bytes": page,
            "sources": sources, "smaps_groups": smaps_groups,
            "scope": "Non-atomic retained snapshots; no madvise, NUMA, sensor threshold or continuous-state inference"}
