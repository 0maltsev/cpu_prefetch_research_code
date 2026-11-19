# D287: D286 guard observations at the cold archive handshake

Accepted engineering implementation under the approved D286 amendment and the
owner's subsequent “continue”. This grants no new scientific method, execution
window or experiment authority. The signed original packet remains immutable.

The root supervisor retains the original D286 Guard and its exclusive lease.
It opens a separate, read-only lease file description and exports an explicitly
bound witness: actual boot, root PID/start identity, lease device/inode/hash,
prestate binding and original finite deadline. The evidence owner can inspect
that FD without permissions to write the control or release the root's lock.
Every verification checks that the separate FD is read-only, the exclusive
root lock still exists, the lease/prestate identities match, the root is alive,
the boot/deadline match and the actual control is0. The witness FD is explicitly
forbidden from the native worker's inherited descriptors.

`stage17_q16c_compaction_integration_v1.py` composes a fresh private Q16c executor,
retaining the original source sealing, native supervision and custody function
bodies. It adds checks outside native measurement:

1. Before the initial native Popen, publish a BEFORE authorization observation.
2. After each authenticated, quiescent native checkpoint, publish AFTER with its
   exact checkpoint binding. Preserve actual observed1 on a control mismatch;
   use null only when no trustworthy actual readback was obtained.
3. If AFTER fails, retain its failure and let the original broker complete the
   archive/custody transaction. Deny the subsequent ACK and propagate the cause
   through the existing native cleanup path. Do not start another capture.
4. Before a valid ACK permits the next capture, recheck the live witness and
   publish the next BEFORE authorization. The ACK's existing credential,
   receipt, native identity and original-deadline checks remain intact. A BEFORE
   receipt describes authorization, not proof that a measurement occurred.
5. After the original runner returns, require all observations. A failure here
   preserves the original conclusive cleanup outcome on the controller error.

The component returns no qualification or scientific-validity credit and has
no experiment launcher. Receipt roots, request/plan bindings, witness FD and
metadata charges must be admitted by a future root operator packet. At94captures,
188 receipts of at most8192bytes require1,540,096bytes; reserve2MiB inside the
existing16MiB family metadata allowance and charge the actual files. The new
descriptor also needs explicit admission. Root guard acquisition/restoration
and independent systemd stop-post recovery must enclose the owned family.
Those live-packet bindings are not implemented or silently added to D285.

Seventeen targeted tests pass locally and on the stand. A bounded stand software
check also passed an actual read-only witness to UID1000 with no capabilities,
verified a synthetic capture's two observations and deliberately SIGKILLed its
root supervisor. Systemd killed the owned child and its independent stop-post
restored the exact original1, with a durable receipt and empty lease. Both PIDs
are gone. This expected injected failure is not a Q15/Q16 experiment.
Fourteen original guard, six D285 and fifteen source-reuse regressions passed.

The existing native worker remains byte-identical to qualified7fb8944. However,
the proposed94-capture continuation cannot use its full180-only declaration:
`src/runner/stage17_formal_family.cpp` and the Python /3 contract require180.
A separately approved continuation format, cold parser/controller work, fresh
release qualification and platform-stratified lineage remain necessary. This
engineering component alone does not make collection ready.

[Fresh evidence and limits](../evidence/stage17/Q16C-D287-GUARD-INTEGRATION-20261119-01/REPORT.md).
