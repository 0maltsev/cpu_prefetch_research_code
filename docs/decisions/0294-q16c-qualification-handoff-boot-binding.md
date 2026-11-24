# D294: carry the verified boot into the qualification handoff

Accepted engineering repair within the existing CPU research software scope.
This decision grants no retry, new clock or experimental authority.

D292 independently validated and published all86 retained Q16c reports, then
stopped before any qualification action. The supervisor wrote the finite
qualification handoff without boot_id. The deployed packet constructor requires
that field to equal its release boot, so it correctly failed with KeyError.
The guard and complete MSR prestate were restored. Original failure, handoff,
window, reports and recovery remain immutable.

The producer now copies boot_id directly from the already validated signed
execution-window record. No default, inferred boot, permission change, consumer
relaxation or deadline extension is introduced. The7200s qualification ceiling,
original absolute start/end fields and one-attempt behavior are unchanged.
No native measurement source or independent scientific validator changes.

The earlier supervisor sequence tests substituted the packet constructor. New
integration tests run the actual deployed constructor body, preserved byte-for-
byte as a source-bound fixture with its original packet provenance. Only native
action methods remain software collaborators. The actual old handoff reproduces
KeyError; the full supervisor's repaired handoff is accepted; a foreign release
boot is rejected before qualification and the guard is restored. The original
regression fails before the repair and passes afterward.

Completed86 validation is final retained evidence. Its reports must be reused;
this repair does not authorize repeating their raw decode, measurements or
changing their original source identities/platform stratum. A subsequent
continuation needs its own explicit decision under D292's stop rule and must
exercise its actual installed packet constructor with the prospective handoff
before consuming a new experimental clock. Python-only metadata changes have
no modified C/C++ sanitizer target; existing native evidence is not described
as fresh verification of this repair.
