# ADR-0068: Require an independently controlled non-stand custody root

- Status: `ACCEPTED_METHOD_LITERAL_VALUE_UNRESOLVED`
- Decision ID: D-068
- Accepted by: Q15-R-P4-D on 2026-08-25
- Classification: custody and storage engineering
- Owners: custody and audit owners
- Lifecycle gate: before setup or qualification artifact transfer
- Supersedes: no path; constrains the unresolved second-domain input

## Decision

Select an absolute non-stand root controlled independently from the primary
stand custody domain, with append-only receipt handling. The literal root,
controlling principal, access evidence, and receipt mechanism remain null.
A stand-local directory, the primary domain, the development repository by
inference, or a temporary path is rejected.

Evidence is ADR-0056's partial-safe external custody requirement, ADR-0063's
four-role setup, and the unresolved secondary-root input. Scientific effect is
none. Compatibility effect binds root, domain, principal, transfer mechanism,
policy, and receipts as evidence identity.

## Authority and supersession

No directory, transfer, or access test is authorized. A change requires a new
custody ADR and prospective access/receipt verification. Existing artifacts and
receipts remain immutable.
