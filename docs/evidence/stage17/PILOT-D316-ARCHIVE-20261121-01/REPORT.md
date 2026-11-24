# S180 archive handoff verified in actual synthetic processes

The compiled native checkpoint channel now connects to the parent, sealed archive
broker, real lossless codec children, shared custody store and read-only parent
verifier. Success acknowledges the exact original checkpoint; native failure,
partial publication and source discrepancy retain evidence and stop continuation.
[D316 contract](../../../decisions/0316-s180-lossless-archive-handoff.md).

This completes the archive handoff software step. It does not activate an
authenticated production worker or establish stand qualification/admission.
All data in these tests is synthetic. No stand access, schedule preparation,
qualification, operational window or pilot occurred during this step.

## Observable behavior verified

- The original eight artifacts, role/format/media bindings and original checkpoint
  survive under a distinct S180 contract. Legacy Q16 channels/contracts still pass.
- Real C++/Python sender credentials, held native PIDFD/start identity and original
  request/program/plan/session/order bindings precede bounded synchronous custody.
  A failed exchange latches; final failure publication remains possible.
- Actual bounded broker/encoder/decoder processes archive the complete set and
  reconstruct every original byte/hash. A full checkpoint uses one broker plus24
  codec children. The parked native child remains alive throughout custody;
  broker descendants are reaped before parent verification and acknowledgement.
- Actual failed native captures and source-byte discrepancies receive negative
  acknowledgement; the compiled child exits stopped rather than continuing.
  Partial publication archives only its original successful prefix and leaves
  every unlisted file intact. A still-live private mapping blocks codec execution.
- Parent metadata verification checks extension, original/actual sources, released
  ledger state, physical header/hash, checkpoint copy and receipt registration.
  Corrupted metadata and physical archive bytes fail verification. This reader
  reports `inverse_readback_performed=false`; it never substitutes metadata for
  inverse reconstruction or scientific analysis.
- The original scope bytes remain unchanged. The explicit D310 extension binds
  the accepted owner/blueprint, one family and EXT009 hash inside the same6TB
  program quota. A second family, changed admission, legacy adoption or orphan
  extension cannot silently continue. There is no independent raw backup claim.

## Fresh checks

| Check | Result |
|---|---|
| Registered focused CTest | 39/39 entries passed;30 C++ cases and72 Python cases |
| New/current S180 cases within that set | 23 C++ and19 Python, including9 broker/custody process cases |
| Complete existing runner binary | 139 passed |
| Original sealed-source binary | 5 passed |
| GCC16.1 ASan/UBSan and TSan | 23 S180 cases passed in each |
| Clang22.1/libc++ ASan/UBSan and TSan | 23 S180 cases passed in each |
| Targeted clang-tidy, including native fixture | PASS; no user-code diagnostic |
| Repository format/protocol/schema fixtures/canonical/provenance | PASS |
| Original fixed-action entry | Unchanged; no production CLI activation |

The registered CTest output includes the actual nine S180 broker test results,
not skipped tests. The test-only compiled endpoint publishes no observations and
cannot alter hardware. Sanitizer runs cover the native controller/channel; the
separate actual codec-process tests retain their own finite address-space limits.
Existing preprovisioned dependencies were reused without network downloads or
relaxed toolchain gates. [Commands](COMMANDS.md), [machine-readable result](verification.json)
and retained logs identify the exact verification boundary.

Initial local harness failures are preserved: host procfs denied the user access
to `/proc/1/ns/pid`; the first isolated namespace lacked a visible process group;
the first compiled-fixture cleanup attempted supervision after `communicate()`
had already reaped its child. The fixture now supervises the held child before
reading its bounded output and always releases its lease. Final process tests
run in a real isolated user/PID namespace with a visible session, without host
sudo or any weakened production supervisor check. These were software-test
failures, not failed experimental runs or operational-window resets.

The stalled test process was stopped. Its6,671-byte temporary synthetic directory
was removed after checking the exact test-only program identity; all other test
temporary data cleaned itself up. [PC cleanup receipt](pc-cleanup.json). No
experimental raw data was copied to this PC or deleted from the stand.

## Remaining work

Connect the typed Linux adapter and verified archive handoff through the
authenticated serialized full-family worker entry. Bind its exact runtime profile
and source closure, prospective sources/namespaces/recovery and finite complete
resources, then resolve scoped EXT008/009/010. Complete clean-release codegen,
native qualification and original-producer compatibility. Present the all-inclusive
duration/storage budget before any operational start. Then execute the one
approved S180 family, retain and independently validate results, prove restoration
and assess scoped Stage17 exit.

EXT007 and all708/120/180 accepted descriptive calibration reports remain
preserved. Completed measurements and their raw validation were not repeated.
The approved24h operational window remains unused. Stage17 is incomplete and
Stage18 remains deferred. [Ordered plan](../../../STAGE17_PILOT_PREPARATION.md).
