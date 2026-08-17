# ADR-0015: SHA/HMAC dependency and exact-integer canonicalization

- Status: `ACCEPTED`
- Date: 2026-08-17
- Classification: Artifact identity / deterministic derivation
- Decision owners: Repository owner; data-integrity owner; build owner
- Protocol version: `2.0.0-pre.1`
- Supersedes: None
- Lifecycle gate: Stage 2 policy; exact suite specification/fixtures due before Phase 4 consumers

## Context and scientific constraints

The protocol fixes SHA-256 artifact identities and requires stable canonical bytes and deterministic seed derivation. Plain RFC 8785/I-JSON number handling cannot be allowed to coerce exact protocol integers through binary floating point.

## Options considered

1. Custom cryptography.
2. OpenSSL 3 EVP SHA-256/HMAC-SHA-256.
3. Plain RFC 8785 JSON canonicalization.
4. A versioned RFC-8785-derived exact-integer suite or a deterministic binary form.

## Decision

Use OpenSSL 3 EVP for SHA-256 and HMAC-SHA-256. Define algorithm suite `JCS-I64-v1`: RFC 8785 property ordering, string, escaping, and whitespace rules, while every schema `integer` is encoded as its exact shortest base-10 lexical value and is never coerced through an IEEE-754 double. Use HMAC-SHA-256 for domain-separated seed derivation under a later fully specified label/field encoding.

## Evidence

The repository owner accepted Q2 on 2026-08-17. OpenSSL supplies a vetted API; the imported data model includes exact integers for which lossy I-JSON conversion is incompatible.

## Consequences and compatibility

Scientific effect: preserves logical values and stable identities; seed values remain later prospective inputs. Compatibility effect: every producer/consumer records the suite ID and passes cross-tool boundary fixtures; unknown suite IDs fail closed.

## Verification and acceptance tests

Known-answer SHA/HMAC vectors, cross-language canonical fixtures below/at/above `2^53`, ordering/escaping/negative-zero and rejection fixtures, dependency hash/license records, and immutable artifact-ID tests are required.

## Rollback or supersession

A new identity suite uses a new version and converters that emit new derived artifacts. Existing bytes/IDs are immutable and never reinterpreted.

## Protocol-amendment assessment

No amendment is required because logical values and fixed SHA-256 semantics are preserved.
