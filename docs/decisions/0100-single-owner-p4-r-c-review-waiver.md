# ADR-0100: Accept a single-owner P4-R-C review waiver

- Status: `ACCEPTED_REPOSITORY_LOCAL_IMPLEMENTATION_ONLY_NO_ACTION_AUTHORITY`
- Date: 2026-08-26
- Decision ID: D-100
- Accepted by: owner response immediately following the exact D-100 through
  D-103 statement, bound to decision-input SHA-256 `faa4c377...`
- Owners: protocol, security, custody, and audit owner acting as one owner
- Protocol version: `2.0.0-pre.2`
- Lifecycle gate: executor implementation before any P4-R-C authorization

## Context and options

ADR-0074 requires a distinct auditor. No distinct person is available. The
options are to remain blocked or accept one owner acting as operator, custodian,
and reviewer for exactly one P4-R-C transaction.

## Decision and effects

Accept the single-owner option and its explicit lack of independent misuse or
tamper detection, development-host/account compromise exposure, unencrypted
signer/transport-key impact, and permanent-loss risk. A resulting review must
be labelled single-owner, never independent.

Scientific effect is none. Principal identities, waiver, risks, and review
label become compatibility inputs. This ADR authorizes only repository-local
implementation and still-unissued records. Key use, signing, stand access,
P4-R-C, and every later phase require separate exact authorization.

## Verification and supersession

Schema and semantic tests reject a distinct-review claim, missing waiver,
authority widening, or automatic continuation. Any reviewer, role, risk, or
scope change requires prospective supersession; prior evidence remains.
