# ADR-0192: Query live page residency with preallocated scratch

- Status: `ACCEPTED`
- Date: 2026-11-02
- Decision ID: D-192
- Protocol version: `2.0.0-pre.3`, unchanged
- Scope: Linux residency observations for the live discovery backend

The existing Q15 residency helper allocates address and status vectors on
every query. Keep that preparation/post-run API unchanged. Add a Linux query
path whose page addresses and status elements are caller-owned live typed
storage, prepared before capture. Validate whole aligned pages, exact lengths,
checked address ranges, and disjoint scratch/mapping before writing scratch.

Sampling makes one `move_pages` query with null destination nodes and zero
flags. It neither migrates pages nor changes memory policy. It allocates,
logs, retries, and formats nothing. Return the actual syscall result and
failure errno independently of each actual page status. Clear status to an
invalid sentinel before each query; a failed or partial observation must not
inherit any previous successful page placement. Eligibility requires syscall
success and every status matching the prospectively requested node.

The backend must prepare the scratch on its documented monitoring owner,
freeze the observation schedule and finite capacity before execution, and
retain each required status snapshot and clock observation before reusing
scratch. Query scratch alone is not durable evidence. One owner samples or
reads a query at a time. Placement remains an observed fact, distinct from
requested binding. This decision sets no cache size, CPU/node, sample cadence,
duration, resource budget, or execution authority.

Verify exact page enumeration and raw results, invalid/overlapping geometry
without writes, failed/partial observations after a prior success, wrong-node
and negative statuses, and zero allocations for repeated prepared queries.
Run supported compiler/sanitizer checks. Synthetic injected query results are
software verification only; live placement still requires actual stand
observations through the qualified backend.
The next source policy must bind both new query files and the final backend;
the existing prospective policy is preserved and supplies no current authority.
