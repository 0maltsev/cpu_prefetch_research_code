# D256: Renew E26 transition authority without repeating qualification

- Status: ACCEPTED within the owner's instruction to fix the admission failure
- Date: 2026-11-15
- Scope: one administrative transition in E26; no scientific-method change

The fresh A2 release passed near/far clock qualification and completed Q15-R
and Q15-W with verified restoration. EXT005 admission succeeded, but transition
3 failed. EXT001's read-only authorization expired at 18:23:47 UTC; Q15-W's
authorization started at 18:24:50 UTC. These original intervals do not overlap.
Changing the transition timestamp cannot legitimately repair this incident.

Following the failure report, the owner instructed "fix it". Existing owner
authority permits signing administrative records for these experiments. Use a
new owner-signed, 1,800-second, one-use authority for this transition only. This
is a recorded application of the D242 administrative recovery pattern to E26,
with its own policy, source, worker, boot, incident hashes and fresh signature.
It does not represent approval of this ADR's exact bytes by the owner.

Keep the six admitted resolutions, both historical transitions, failed draft
transition and candidate journal, original authorization windows, successful
qualification evidence and cleanup records unchanged. The new version-2 third
transition preserves the graph edge, evidence population, original authority
references and all graph/catalog/schema hashes. It adds the explicit renewal
authorization and signature. Its timestamp is current and must follow all six
resolutions. The renewal signs the full administrative closure and every
incident binding. Reject altered evidence, changed source/worker/boot, failed
qualification, incomplete restoration, expired renewal and repeated use.

The new private journal runtime retains every policy59 semantic, lineage and
fork check, changing only validation of that exact third edge. The original
policy59 modules are not patched. D255's actual platform association and all
v6 signature, execution, storage and one-attempt gates remain in force.

This repair grants no experiment execution, retry, scientific inference or
Stage18 authority. Completed Q16a is retained. Any Q16b execution still needs
its own signed request, resource/isolation checks and prospective duration
estimate. The original absolute 24-hour study deadline is not reset or extended
by administrative recovery. If remaining finite budgets cannot fit, stop
incomplete and report that separately from the repaired journal transition.
