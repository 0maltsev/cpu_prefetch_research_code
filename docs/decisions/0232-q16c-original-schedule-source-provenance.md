# ADR-0232: Q16c original schedule-source provenance

- Status: ACCEPTED — engineering composition of accepted D029/D036/D230
- Date: 2026-11-03
- Scope: Pure offline source validation; no schedule-method or scientific change
- Execution authority: None

## Required source contract

`tools/stage17_q16c_schedule_provenance_v1.py` exposes
`verify_schedule_source` with keyword arguments:

```text
schedule, phase, duration_ns, scale_ordinal, load_level,
calibration_record, artifact_path, artifact_binding,
envelope_utf8_bytes, envelope_binding,
derivation_utf8_bytes, derivation_binding,
expected_parent_namespace_id
```

`schedule` is the prospective native scheduled-input leaf. `phase` is explicitly
`warmup` or `measurement`; duration, scale and load come from the same prospective
capture, with no default scientific values. All three bindings contain exactly
`artifact_id`, `size_bytes` and lowercase SHA256. The native `source_artifact`
binds the original headerless `SCHEDULE-ABS-U64BE-v1` **binary**, not a replacement
JSON vector or a fabricated `frozen-schedule/3` envelope. The other two bindings
independently identify the original generator envelope and derivation bytes.

The controller-facing source receipt can retain
`{artifact_id,binding,envelope_binding,derivation_binding,parent_namespace_id}`,
where `binding` identifies the binary. Controller filesystem bindings may also
carry their established path fields; the controller resolves/authenticates them
and projects the three binding fields for this helper. It passes original UTF-8
bytes, never a reserialized decoded document. `artifact_uri` from the envelope
is retained as provenance and is never opened by this helper.

The explicit expected parent must come from the authenticated phase-schedule
namespace-registry receipt. It is not inferred from an arena namespace, nor
accepted merely because the source itself claims it. The caller still checks
stand/revision consistency, complete-family membership, namespace registration,
sharing/isolation rules, release/analysis provenance, and execution authority.

## Accepted method and exact checks

Protocol 2.0.0-pre.3 sections 5.1–5.5, D029, and D036 already supply the needed
method. D036's exact ladder is `[1,9/10,4/5,7/10,3/5]`; load multipliers are
`[1/4,1/2,3/4]`. After D230 semantic validation of a complete VALIDATED Q16b
record, convert `mu_ref` events/second to the accepted generator's events per
picosecond by exact rational division by `10^12`, after multiplying by the
prospective scale and load. Reduced numerator and denominator must be positive
and representable as uint64. A valid zero `mu_ref` is not silently changed: it
cannot supply a positive-rate D029 source and blocks this check. No achieved
throughput, cell-specific rate or new ladder point is substituted.

Warmup uses the same cell rate and the accepted pre-freeze five-second duration;
its envelope role is WARMUP. Measurement role is CALIBRATION, with the explicitly
supplied duration. The generator envelope's `horizon_ticks` is a **duration**;
the native leaf's `source_horizon_ticks` is the **absolute endpoint**. Verify
`native_end = origin + envelope_duration = origin + duration_ns*1000` using
checked uint64 arithmetic. Nonzero origins therefore remain supported.

Original byte size/SHA checks precede strict duplicate-key UTF-8 JSON parsing.
Reject noninteger numbers, nonfinite values and schema mismatches. Validate the
immutable protocol envelope schema and existing derivation-v2 schema; recompute
their accepted JCS zero-self hashes separately from their original-byte hashes.
Check suite, role, units, rate, IDs, namespaces, derived-key record, immutable
order, half-open boundaries, count, binary size/hash and decoded-deadline hash.
The legacy pre.1 derivation-domain label remains unchanged, as required by D029;
current protocol/schema identity remains pre.3.

Regeneration invokes the unchanged `generate_schedule.py` Philox/key/Decimal80
primitives under its accepted Python 3.14 runtime guard. There is no second RNG,
logarithm implementation, rounding policy or altered transform. Compare each
decoded U64BE binary row with both the existing native vector element and the
accepted generated deadline. Recompute the decoded-hash grammar incrementally.
Generate exactly `offered_count+1` candidates: the final candidate must be at or
beyond the horizon. This rejects a rehashed truncated source that otherwise
contains only valid initial arrivals. Every retained row must be nondecreasing
and within the half-open source interval. The accepted overflow rule also
applies to the first excluded generated candidate.

## Resource and authority boundary

The binary is opened as a nonsymlink regular file and read in fixed eight-byte
rows through bounded buffered I/O. Compare device/inode/size/mtime/ctime before
and after reading, including the original path identity, and verify the whole
original byte hash. No second deadline vector, binary image, generated tuple or
per-row JSON result is allocated. Extra binary-processing storage is constant;
regeneration work is linear in the declared native vector length and may be
substantial for large schedules. Each original JSON metadata document has an
explicit 1 MiB software parsing ceiling. D230 semantic checking uses its existing
finite family structure and associated memory; this helper does not make that
cost disappear or authenticate the report producer from a hash alone.

This change does not widen the native/request vector limit, solve the separate
128 MiB request-vector constraint, modify the controller, or generate/admit/run
a study. The bounded result has schema
`cpu-prefetch-stage17-q16c-schedule-provenance/1`, retains all three source
bindings, internal envelope/derivation/decoded hashes, URI, identities, exact
coordinates/rate and the canonical D230 record hash. Both authority fields are
false. `accepted_generation_verified` means byte agreement with the accepted
algorithm, not historical proof that a particular machine executed the original
generator. Producer, namespace and calibration provenance still require the
caller's authenticated receipts.

## Verification

Software tests consume real original `generate_schedule.py` outputs and the
accepted 104-row binary/decoded-hash golden. They cover all 15 scale/load pairs,
nonzero-origin endpoint conversion, warmup/measurement with identical master
seed bytes and disjoint stream namespaces, and complete synthetic D230 records.
Negatives include missing/unresolved/altered calibration, zero rate, byte/hash
and self-hash mismatches, malformed/duplicate/noninteger JSON, phase/rate/suite/
parent/key mismatches, binary/native mutations, arithmetic overflow, metadata
limits, rehashed forged/truncated sources, symlink/path-identity changes and
bounded-read/no-whole-vector regeneration checks. These are software evidence,
not hardware observations or experiment authority.
