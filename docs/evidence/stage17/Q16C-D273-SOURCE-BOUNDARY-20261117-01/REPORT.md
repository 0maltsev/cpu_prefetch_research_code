# Q16c original-source boundary software checks

[D273](../../../decisions/0273-q16c-prospective-resource-and-source-receipt-boundary.md)
implements a once-only32-worker software preparation job, complete signed360-source
receipts and a private8192-entry inventory reader. The unchanged original generator
and independent provenance verifier are loaded from the frozen919c486 bundle.
This adds no native change or execution authority and does not start D270’s clock.

Five pool/ownership tests pass: actual child completion/reaping before final
publication, cleanup after first failure and timeout, exclusive publication and
strict JSON, plus finite inventory admission without changing historical limits.
Five receipt tests use actual SSH signatures with an independent temporary test
trust root. They exercise complete ordered current-byte custody and reject changed
seeds, originals, code, incomplete signed families, false reaping, foreign signature
principals and changed global deadlines. Their provenance fixtures are explicitly
synthetic software data; they are not accepted research evidence.

A separate PC-only integration ran the actual frozen accepted generator and actual
independent verifier for one synthetic1-second L025 source:417694 originals, hash
39a6cfeaf13df24cd221bb8a49148645b242b340f9f227ed08ec6e0b0bb21a12.
The temporary source was removed. It performed zero native measurements and is
software verification only. Adjacent original logs retain all results.

The first receipt test exposed a set passed to the strict JSON equality helper;
it now compares sorted complete lists. A pool test was corrected to inject its
failure in a first scheduled job, rather than after a30-second fixture delay.
All affected checks were rerun successfully. No stand run failed or started.

Next is integration into signed Q16c admission, complete finite budgeting and
whole-study supervision. The stand release remains unqualified, all completed
Q16a/Q16b reports remain fixed, and Stage17 remains incomplete.
