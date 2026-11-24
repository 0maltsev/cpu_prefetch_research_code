# Q15-R stand-setup authorization preparation

Status: **`SUCCESSOR_V2_BLOCKED_FIVE_EXTERNAL_INPUTS_NO_AUTHORITY`**

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

This predecessor was sealed before an adapter-bearing release existed, so it
correctly retains all six input groups. It is not overwritten after release
construction. Before an executable stand-setup authorization can be prepared,
all six predecessor groups must be supplied prospectively and hash-bound:

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

Clean commit `c8b69abf0c6aec7b740efe78d998a93545302a94` now supplies a
verified no-authority release candidate. The
[`Q15-R-P3 decision/input bundle`](Q15_R_OPERATIONAL_RELEASE_DECISION_BUNDLE.md)
records accepted D-065. Versioned successor
[`q15-r-stand-setup-authorization.preparation-v2.json`](../config/q15/q15-r-stand-setup-authorization.preparation-v2.json)
has SHA-256
`25ab86661f2a0ea1c92237aea06585e585bea9303f9309678e110978c7bd5338`
and resolves only item 1. The five external path, custody, prestate, and
signer/trust inputs remain blocked, and every future authorization field is
still null.

The accepted-method
[`Q15-R-P4 external-input acquisition decision bundle`](Q15_R_EXTERNAL_INPUT_ACQUISITION_DECISION_BUNDLE.md)
defines how those five inputs must be collected and verified. ADR-0066 through
ADR-0070 accept the methods, and the fixed no-authority collector is implemented
locally. All five literal values remain null; Q15-R-P4-R and Q15-R-P4-K are
blocked preparations, not issued authority. Stand setup cannot proceed from
method acceptance, collector bytes, or generic acceptance.

The future authorization must contain only literal argv; no `@...@` token may
remain. It must preserve setup order, stop on the first mismatch, require all
24 access results including 18 denials, retain partial evidence, and apply only
applicable non-deleting quarantine actions. Stand setup and each later phase
require separate explicit approval.

Repository-local check:

```sh
cmake --build --preset dev-gcc --target q15-r-stand-setup-preparation-check
cmake --build --preset dev-gcc --target q15-r-stand-setup-preparation-v2-check
cmake --build --preset dev-gcc --target q15-r-external-input-acquisition-check
cmake --build --preset dev-gcc --target q15-r-p4-d-implementation-check
```
