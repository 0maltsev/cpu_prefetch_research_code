# D308: chronological qualification records at descriptive admission

Accepted engineering correction within the authorized EXT007 finalization.
No scientific method, data, signed freeze, native qualification or experiment changes.

The first D307 admission job verified the original six qualifications and signed
descriptive record, then rejected a positional comparison. The actual journal
stores EXT001/002/003/006/004/005 in chronological admission order. The fixed
action predecessor vector uses categorical EXT001 through EXT006 order. Their
record hashes must have identical complete membership, without rewriting either
order. The original journal000009 is3710bytes, SHA256
2fab0d69e3350dea0106a1fd5a0aa0ddd04dab8bae1956815e66ad47a378f5aa.

The regression fixture now preserves this observed ordering and reproduces the
same failure. Semantics19 changes exactly that comparison to sorted membership;
the complete journal replay still validates original sequence, record identity,
hashes, signatures, predecessors and temporal order. Preserve semantics18,
policy64, journal61, the original admission entry and failed job unchanged.
Use policy65/journal62 and a source-bound successor entry. Reuse only the exact
already published manifest after byte equality checks. Use a fresh metadata-job
output/receipt/preview namespace, then ordinary canonical append and full replay.
The prior failure happened before custody receipt, preview or canonical resolution
publication; journal000009 remains the actual head and EXT007 remains unresolved.

This authorizes necessary metadata software repair under the existing user
instruction to continue EXT007; it grants no new Q15/Q16 run, qualification,
raw decoding, experimental retry, day, pilot or Stage18 action. The signed D307
data freeze and all completed/failed scientific evidence remain unchanged.
