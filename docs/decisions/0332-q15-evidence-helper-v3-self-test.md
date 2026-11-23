# D332: align the qualification evidence helper self-test with schema3

Accepted engineering correction within the existing S180 preparation. The
helper's actual evidence builder already emits qualification-evidence/3 under
D175. Its self-test still compared that accepted constant to /2 and therefore
failed before its synthetic JSON/builder round trip. Reproduce the failure on
the unchanged clean34247ce helper; preserve it as software evidence.

Change only that self-test comparison to the already accepted /3. Register the
actual helper --self-test in CTest, requiring its PASS and explicit no-device,
no-stand, no-clock output. Real --kind handling, raw/schema interpretation,
eligibility, sampling, scientific methods and hardware behavior are unchanged.
The ordinary qualification tool's separate self-test already expects /3 and is
unchanged. Do not edit or rebuild the frozen measurement worker to repair an
auxiliary diagnostic.

Use the provisioned compiler/runtime to build the missing helpers from frozen
source, then verify their software-only self-tests. The corrected helper is
first checked in the development build and GCC ASan/UBSan. A separately clean
release helper must be built before qualification; record its source revision
and binary independently from the unchanged34247ce measurement worker. The
original broken helper is not silently replaced in that frozen source tree.

The generic fixed Q15 tool declares family06/model55 and CPUs0/1/26. It is not
this stand's hardware route. The current stand requests the registered06_3E
mapping on CPUs0/1/8; its Q15 path is the model-aware persistent runner session.
Record the fixed tool's actual metadata and exclude its hardware actions from
the future stand profile. Clock-pair helper bytes match the existing v32 helper;
byte equality establishes software identity, not a new or reused stand
qualification. No qualification sample count or existing limit changes.

All six helper software diagnostics pass with the corrected development helper;
the registered regression and the GCC ASan/UBSan JSON/builder round trip pass.
Format, protocol/schema/canonical/provenance and whitespace checks remain required.
There is no stand execution, raw generation, source bank, operational window,
pilot authority or completed qualification from these checks. The full qualified
outer operator/EXT008 producer and scientific validator remain pending; Stage17
is incomplete and Stage18 deferred.
