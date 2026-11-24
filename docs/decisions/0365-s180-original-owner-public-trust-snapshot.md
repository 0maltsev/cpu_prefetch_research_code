# D365: Preserve original-owner public trust in the root S180 controller

Status: engineering correction; no new scientific decision or run authority.

D364's actual stand preflight170ad22 reached its final offline signer check and
stopped. The unchanged legacy SSHSIG verifier requires allowed-signers to belong
to its effective UNIX user. The admitted original106-byte trust file belongs to
UID1000, while the qualified S180 hardware controller correctly runs as root.
Disposable single-UID software tests did not expose this ownership difference.
No actual S180 root, source, qualification, scoped admission or24h window existed.

The original journal continues to use D361's full original-owner replay. Do not
chown/chmod the original trust, alter original signed semantic contexts, weaken
the legacy verifier or run the hardware controller as the unprivileged user.

Add an S180-only public-trust snapshot adapter. The root caller opens the exact
admitted original canonical file, verifies its recognized owner (root for ordinary
same-owner inputs, or the established original UID1000), protected single-link
regular type, bound size/hash and unchanged file epoch. For the actual UID1000
case only, create an exclusive root-owned temporary copy of those same public
bytes under `/run`. Invoke the unchanged legacy verifier using a private copy of
the trust context whose only changed field is that temporary public-file locator.
Principal, namespace, hash, size, original persisted context and signed payload
remain identical. Recheck the held original and named file after verification;
remove the temporary public copy after either success or failure. No private-key
bytes are copied or logged. Unknown owners and any drift fail.

S180 authority/journal and their existing Q15 consumers use this adapter. Legacy
original readers stay unchanged. The qualified service profile adds the three
exact authority/journal/adapter overlays and verifies they actually loaded.
The fixed29-module archive component excludes these modules and remains byte
identical; D362 sizing, runtime profile and quota/experiment limits do not change.

An actual stand software check signs one non-JSON, non-authorizing challenge
using the already authorized offline signer. The UID1000 adapter verifies it and
rejects a changed message. The original trust bytes, epoch, owner and mode remain
unchanged. All temporary test files are removed. This proves the real ownership
boundary without collecting research data or consuming the operational window.

Retain the failed19-file D364 service package and preflight diagnostic. Replace
only its unstarted active software location with a new clean22-file source
package, then repeat the read-only release preflight. No experiment is retried,
no deadline reset and no completed measurement or raw inverse rerun is authorized.

Evidence: [actual trust test and affected regressions](../evidence/stage17/PILOT-D365-PUBLIC-TRUST-20261124-01/REPORT.md).
