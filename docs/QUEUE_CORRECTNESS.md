# Stage 5 Queue Correctness Record

Protocol version: **`2.0.0-pre.1`**

Scope: independently authored Stage A queue cores and correctness evidence only.
This record contains no latency, throughput, tuning, package ranking, or
performance recommendation. Software-prefetch package sites, the common event
arena, clocks, schedules, observation storage, and the experiment driver remain
outside Stage 5.

## Shared adapter boundary

`RingQueueAdapter` and `LinkedQueueAdapter` are separate final concrete types.
They have no common virtual base and no runtime family selector. Each exposes
one `noexcept` `try_enqueue(EventPointer)` call and one `noexcept`
`try_dequeue()` call. `EventPointer` cannot be constructed from null. Neither
operation allocates, retries, waits, logs, parses, throws, or invokes a callback.
Private phase observers exist only through the test-access friend and compile
away from the adapter path.

Construction is outside the data plane. It takes a nonzero capacity and an
explicit cache-line byte count; there is no platform default. Invalid sizes,
storage overflow, or invalid node permutations fail before operations begin.
The synthetic test value `64` is a fixture, not a selected or verified platform
fact. Page alignment, page backing, first touch, NUMA placement, and the common
immutable event arena remain later platform/working-set evidence.

## Bounded ring mapping

The implementation maps Torquati, *Single-Producer/Single-Consumer Queues on
Shared Cache Multi-Core Systems*, Section 2 and Figure 3, as fixed by protocol
Section 3.2:

- `C` contiguous pointer-width atomic slots use null as the distinguished empty
  value;
- producer and consumer modulo-`C` cursors occupy two separately aligned cache
  lines and are accessed only by their owning thread;
- an enqueue makes exactly one acquire slot observation. Non-null returns
  `full`; null is followed by one release publication of the event pointer;
- a dequeue makes exactly one acquire slot observation. Null returns `empty`;
  non-null is followed by one release clearing store for slot reuse;
- successful enqueue linearizes at the release pointer store; full linearizes
  at the acquire observation of an occupied slot; successful dequeue linearizes
  at the acquire observation of the event pointer; empty linearizes at the
  acquire observation of null.

The producer publication synchronizes with the consumer acquire before the
consumer uses the pointer. The consumer clearing store synchronizes with the
producer acquire before that slot is reused. Cursor values are not shared and
therefore need no atomic synchronization. They remain in `[0,C)` and do not use
an ever-increasing sequence number, so operation count cannot roll a sequence
field over. Storage-size validation makes `position + 1` representable.

Under the fixed one-producer/one-consumer, non-null-pointer, lock-free-atomic
preconditions, each try operation executes a bounded number of steps without a
loop: the reviewed claim is wait-free completion and linearizable bounded-FIFO
try semantics. It is not a multi-producer/multi-consumer or general queue claim.

Stage 13 adds a calibration-only observer immediately before and after the
same acquire load described above. The observer does not move the
linearization point, add a retry, or change either memory order. Ordinary
operations instantiate an inlined no-op observer; the accepted release probe
still emits the same four queue bodies under both disassemblers. Fake-clock
tests prove that every FULL/empty acquire remains in the demand series while
only accepted/successful operations advance the issue-interval sequence. The
trace is explicitly preallocated and a capacity overrun fails calibration
capture rather than growing storage.

## Linked FIFO plus recycler mapping

The implementation maps Torquati's dSPSC FIFO and bounded SPSC node cache,
Section 3 and Figure 6, with the protocol's declared fixed-arena adaptation:

- construction creates exactly `C+1` cache-line-strided nodes. The supplied
  permutation's first node is the sentinel; the other `C` nodes populate the
  recycler in the supplied FIFO order;
- producer tail, consumer head, recycler producer position, and recycler
  consumer position occupy four separate aligned ownership lines;
- the producer acquire-removes one node from the recycler, release-clears that
  recycler slot, initializes the event and null successor, then release-links
  the node through the prior tail. An empty recycler returns `full` immediately;
- the consumer acquire-loads the current sentinel successor. Null returns
  `empty`. For a successor, it completes its last required reads, advances the
  private head, and release-publishes the old sentinel to the recycler;
- the recycler's release/acquire pairs prevent a consumer-detached node from
  being initialized again before the consumer's last access;
- accepted enqueue linearizes at link publication; full at recycler-null
  observation; successful dequeue at successor observation; empty at null
  successor observation.

`recycler_invariant_failure` is not a third scientific queue outcome. It is a
fail-stop correctness signal for the impossible valid-state case in which the
consumer has a successor but its next FIFO recycler return slot is occupied.
The consumer does not advance the head in that case. A later controller must
classify it as correctness failure, never as `FULL` or `EMPTY`.

### Fixed-arena refinement

Let the abstract state be a bounded FIFO of event pointers with capacity `C`.
The concrete reachable chain contains one current sentinel followed by exactly
the abstract FIFO order. Every other node is in the recycler except for a node
temporarily owned by one in-progress producer or the old sentinel temporarily
owned by one in-progress consumer. SPSC invocation prevents a second operation
by the same owner while such a transient exists.

Initially the abstract FIFO is empty, the chain contains only `pi[0]`, and the
recycler contains `pi[1]..pi[C]`. A successful enqueue removes exactly one
recycler node and release-appends it with the next abstract value. If no node is
available, the abstract FIFO has no capacity available to that producer
operation and immediate `full` refines the bounded result instead of taking the
paper source's allocation fallback. A successful dequeue observes the first
successor, returns its event, makes that successor the new sentinel, and only
then releases the old sentinel to the recycler. Thus no reachable node is
recycled, the chain remains acyclic, tail remains reachable, and FIFO order is
preserved. In zero-loss sequential cycling, obtained node indices repeat
`pi[1]..pi[C],pi[0]` exactly.

The recycler uses modulo-`C` positions and pointer slots, not monotonic sequence
tags. Consequently it has no long-running sequence-number rollover assumption.
This argument covers the fixed Stage A SPSC arena only; it does not cover hazard
pointers, general reclamation, Stage B, or a fallback allocator.

## Atomic and layout boundary

Both implementations use ABI-width `std::atomic<T*>`. Compilation rejects an
atomic pointer wider than the ABI pointer and rejects a target where pointer
atomics are not always lock-free. Every constructed atomic is also checked with
`is_lock_free()` at runtime. The development-host results do not substitute for
the same runtime check on the later eligible stand.

The explicit cache-line input must be a power of two satisfying maximum object
alignment. Allocation bases and every ownership line are runtime-checked. Ring
slots remain contiguous pointer-sized cells; they are not padded into a changed
algorithm. Linked node stride is the smallest integral number of supplied cache
lines containing its header, so every node starts on a supplied-line boundary.

## Correctness evidence

The Stage 5 suite covers:

- empty, full, capacities, FIFO, wrap, repeated record indices, and 200,000
  sequential ring reuse operations;
- exact `C+1` linked node cycling, recycler exhaustion, lapping, sentinel reuse,
  chain acyclicity, tail reachability, and exclusive ownership;
- deterministic 10,000-step reference-model histories and RapidCheck-generated
  histories for both queues;
- one-attempt histories retaining full outcomes separately from accepted rows;
- deterministic suspension before ring publication/reuse and after linked
  recycler obtain/successor observation;
- fixed-seed two-thread stress with slow-producer and slow-consumer scheduling,
  exact first/internal/final pointer order, payload corruption checks, full/empty
  transitions, and repeated recycler transfer;
- explicit duplicate, omission, corruption, and reorder detector negatives;
- compile-time width/lock-free assertions and runtime atomic/layout reports;
- GCC and Clang unit/property/stress plus ASan/UBSan/TSan matrices.

No test records operation duration or rate. A correctness stress loop may retry
outside the adapter to force complete transfer; the separate one-attempt stress
performs exactly one enqueue call per logical arrival and reconciles only the
accepted sequence.

## Generated-code status

GNU Binutils 2.46 and LLVM 22.1.6 objdump on the GCC release probe passed all
four adapter operations: no call, `lock`, `xchg`, or `mfence` instruction class
appeared, and both tools rejected the deliberate call-injection mutant. Human
review of both views confirms direct static code, ordinary acquire/release
x86-64 loads/stores, bounded forward branches, and no allocation, logging,
wait, retry, or dispatch calls. The binary, mutant, rule-set, operation, and
full-disassembly hashes are in the build-local `queue_codegen_report.json` and
bound into both queue provenance records. ADR-0016's Stage 5
dual-disassembler gate passes.

## Residual boundaries

- The later eligible platform must supply and verify its actual cache-line size
  and repeat every runtime lock-free/alignment probe.
- Stage 6 now supplies base-page-aligned, fully first-touched immutable event
  arenas, exact footprint arithmetic, deterministic event/node permutations,
  and content/order/delta integrity inputs. NUMA placement/residency remains a
  Phase 9 platform obligation.
- Stage 6 binds ring `R1/R2` and linked `L1` target sites through a static
  emitter and passes target-order generated-code checks. The platform retaining
  instruction mapping and calibrated context-specific `d2` remain open; no
  default instruction or distance is embedded.
- Termination control, schedule polling, clocks, timestamps, observations, and
  measurement remain unimplemented. The Stage 6 mixer exists only as a tested
  record action pending its final worker/timestamp boundary.
