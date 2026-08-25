# Q15-R P5 D-098 stand-setup decision/input bundle

## Current entry state

D-097 completed one public-only P4-K-R review and stopped. Its complete
repository evidence SHA-256 is
`b7c6125d216e01e4207ce54872b2fdb02fd7bf41bb97f99f495006ee28ce4a90`.
The reviewed allowed-signers SHA-256 is
`b08f32720b7987218a5c51f31f822f2ea1d22ff948beb41382518927d815c718`
and target fingerprint is
`SHA256:bOmXmBSxD0rBKid1AKOXQ25jIUjCOrijbM5sN18qLGM`.

This is reviewed public evidence only. It is not installed, activated, or used
for signing, and it grants no stand or P5 authority.

## Inputs still required before P5 can be issued

1. Complete the separately authorized P4-R-I stand-identity gate.
2. Complete the separately authorized one-shot P4-R-C read-only prestate
   collection and independent review.
3. Select an unused absolute content-addressed operational release root from
   that fresh prestate; do not infer it from historical inventory.
4. Select and verify a genuinely independent secondary custody root from fresh
   evidence; do not equate a second directory on the same filesystem with an
   independent domain.
5. Create a versioned successor that binds those three values and proves the
   exact 20 setup commands, 24 access tests, 18 required denials, and 10
   quarantine/rollback commands contain no unresolved token.
6. Prepare an exact named-authority, UTC-bounded, signed P5 authorization and
   obtain separate explicit approval.

## Current machine-readable preparation

`config/q15/q15-r-stand-setup-authorization.preparation-v3.json` resolves only
the two D-097 public-trust groups. It retains exactly three null external input
groups and every execution authority is false. It is not executable.

## Recommended next approval

The next safe external gate is P4-R-I, not P5. A later decision bundle must bind
the immutable collector release, literal staging/capture/custody paths, named
principal, host-key and fresh stand identity evidence, exact UTC/signature
bytes, one attempt, stop conditions, and no automatic continuation to P4-R-C.

No blanket approval, SSH availability, root access, D-097 completion, or this
preparation authorizes P4-R-I, P4-R-C, P5, Q15-R/Q15-W, calibration, pilot,
measurement, or confirmatory execution.
