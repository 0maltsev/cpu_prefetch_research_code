# Q15-R stand-setup authorization preparation

Status: **`BLOCKED_INPUTS_REQUIRED_NO_AUTHORITY`**

The machine-readable
[`q15-r-stand-setup-authorization.preparation.json`](../config/q15/q15-r-stand-setup-authorization.preparation.json)
binds the accepted D-061 through D-064 decision set, the verified clean v2 base
release, `Q15-R-TRUST-ANCHOR-ADAPTER-v1`, and the exact 20 setup, 24 access,
and ten quarantine command IDs in the byte-preserved proposal. Its SHA-256 is
`a671fad5b45823a617140d9ee1f684235812daede0048fb67e1255ce74ecb057`.

This is an exact preparation contract, not an issued or executable
authorization. Every authority flag is false. It contains no executor or shell
script, does not resolve inputs from the environment, and cannot validate as a
Q15-R or Q15-W authorization.

Before an executable stand-setup authorization can be prepared, all six input
groups must be supplied prospectively and hash-bound:

1. a clean operational adapter release and complete archive/manifest/SBOM/
   binary/report hashes;
2. exact allowed-signers bytes, artifact ID/hash, Ed25519 fingerprint, and
   offline key custodian;
3. exact operational release root;
4. exact separate secondary custody root and host/mount/owner/mode/quota facts;
5. fresh current stand prestate for all referenced names, paths, executables,
   devices, mounts, and quotas;
6. a named authority, issue/expiry UTC, evidence destinations and IDs,
   signature, and independent-review receipt.

The future authorization must contain only literal argv; no `@...@` token may
remain. It must preserve setup order, stop on the first mismatch, require all
24 access results including 18 denials, retain partial evidence, and apply only
applicable non-deleting quarantine actions. Stand setup and each later phase
require separate explicit approval.

Repository-local check:

```sh
cmake --build --preset dev-gcc --target q15-r-stand-setup-preparation-check
```
