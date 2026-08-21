# Phase 1 Study Notes: Combinational & Sequential Logic Review

**Date:** 2026-08-22
**Roadmap item:** Phase 1 — Digital Logic & HDL Fundamentals
**Covers checklist items:** "Combinational logic review (Boolean algebra,
muxes, encoders, ALUs)" and "Sequential logic review (latches vs.
flip-flops, FSMs, timing basics)"

This is a from-fundamentals review, written as verification-engineer-
oriented study notes rather than a full designer's treatment — the
emphasis throughout is on *what a verification engineer needs to reason
about correctly* (functional behavior, corner cases, and the properties
that get checked/covered), not on gate-level implementation detail.

## 1. Boolean algebra essentials

The identities that come up constantly when reasoning about RTL and
writing checkers/assertions:

- **De Morgan's laws:** `!(a & b) == (!a | !b)` and `!(a | b) == (!a & !b)`.
  Used constantly when simplifying or sanity-checking a condition written
  as a negation of an AND/OR chain (e.g. turning `!(valid && ready)` into
  `!valid || !ready` when writing a coverage or assertion condition).
- **Absorption:** `a | (a & b) == a`, `a & (a | b) == a`. Useful for
  spotting redundant terms in an RTL condition that a synthesis tool would
  optimize away anyway — if you see this pattern in a testbench check, it
  usually means the check is more complex than the actual logic requires.
- **Consensus theorem:** `(a&b) | (!a&c) | (b&c) == (a&b) | (!a&c)` — the
  `b&c` term is redundant given the other two. Relevant to hazard analysis
  (a redundant term like this is exactly the kind of term that, if
  physically removed, can introduce a static hazard/glitch in an async
  circuit — not usually a concern for synchronous RTL but shows up in
  clock-gating and reset-tree analysis).
- **XOR/XNOR identities:** `a^b == (a&!b)|(!a&b)`, and `a^b^c` is
  associative/commutative — this matters directly for verification because
  parity checkers, ECC logic, and LFSRs (common in verification
  infrastructure, e.g. randomization seeds) are built from XOR trees, and
  proving two XOR expressions equivalent is a common formal/assertion task.

## 2. Multiplexers, encoders, decoders

- **Mux (multiplexer):** an N:1 mux selects one of N data inputs using
  ceil(log2(N)) select bits. The verification-relevant property: for every
  legal select value, the output must equal the corresponding input,
  *and* for a well-formed design there should be no output change for any
  other input transition (mux isolation) — this is exactly the kind of
  property that gets written as an SVA property later in Phase 5, and is a
  natural first target for `assert property` once we get there. A mux is
  also the canonical multiplexed-bus-arbitration building block: most
  arbiters in real designs are "priority/round-robin select logic driving
  a mux," so understanding mux behavior precisely (including behavior on
  illegal/multi-hot select) is foundational for verifying arbiters later.
- **Demultiplexer:** the dual of a mux — one input routed to one of N
  outputs based on select. Common in dispatch logic (e.g. routing a
  decoded instruction to one of several functional-unit issue queues).
- **Encoder / priority encoder:** an encoder converts a one-hot input
  vector into a binary index; a *priority* encoder additionally resolves
  the case where more than one input bit is set, by defining a fixed
  priority order (typically highest-index or lowest-index wins). This
  matters for verification because priority encoders are almost always
  under-specified in English design docs ("grants the highest-priority
  request") — the exact tie-breaking rule and behavior when *no* request
  is asserted (does it output a valid bit, or a don't-care encoded value?)
  are exactly the kind of ambiguity a verification plan (Phase 3) needs to
  pin down before writing checks.
- **Decoder:** the dual of an encoder — binary index to one-hot output.
  Used everywhere: memory address decode, opcode decode, one-hot state
  encoding for FSMs (see Section 4).

## 3. ALU (arithmetic logic unit) structure

A basic ALU is a mux-selected bank of parallel combinational operations
(adder, subtractor typically via two's-complement adder with an invert +
carry-in trick, logical AND/OR/XOR, shifter) selected by an opcode field,
plus status/flag outputs (zero, carry-out, overflow, sign). Verification-
relevant points:

- **Overflow vs. carry-out are different signals with different
  definitions** — carry-out is the raw carry out of the MSB adder stage;
  signed overflow is `carry_into_msb XOR carry_out_of_msb` (equivalently:
  overflow occurs when adding two same-sign operands produces a
  result of the opposite sign). Confusing these two is one of the most
  common ALU-checker bugs — a scoreboard/reference-model implementation
  needs to get the overflow formula exactly right, not just "close enough
  most of the time," because it is only exercised at operand-magnitude
  corner cases that constrained-random testing may under-sample without
  explicit boundary-value directed tests or coverage bins for it.
- **Boundary/corner values that deserve explicit coverage bins:** all-
  zeros, all-ones, the two's-complement most-negative value (`0x80...0`,
  which has no positive counterpart — negating it overflows), and
  operand-equal-to-zero cases for shift/divide-adjacent operations. This
  is a concrete preview of the "features -> checks -> coverage" thinking
  that Phase 3 (verification planning) will formalize.

## 4. Latches vs. flip-flops

- **Latch:** level-sensitive — transparent (output follows input) while
  the enable/clock is asserted, and holds its last value once the
  enable/clock deasserts. A D-latch is the minimal 1-bit storage element;
  building an edge-triggered flip-flop out of two latches (master-slave)
  is the standard way to explain *why* flip-flops behave the way they do.
- **Flip-flop:** edge-triggered — samples input only at a clock edge
  (posedge or negedge) and is opaque otherwise. Essentially all
  synchronous digital design (and everything in Phases 2-6 of this
  roadmap) is built from edge-triggered flip-flops specifically *because*
  they give a single, well-defined sampling instant per cycle, which is
  what makes static timing analysis and synchronous verification
  tractable. Latches are still used in real designs (e.g. clock-gating
  cells, some pipeline-balancing tricks, memory-macro internals) but
  inferring a latch *unintentionally* from incomplete combinational logic
  (a classic missing-else-branch bug) is one of the most common and most
  dangerous RTL coding mistakes — Section 6 below connects this directly
  to blocking-vs-non-blocking assignment semantics, which is where this
  bug actually originates in practice.

## 5. Finite state machines (FSMs)

- **Moore machine:** outputs are a function of state only (`output =
  f(state)`). Outputs change only on a clock edge (when state changes),
  which makes Moore outputs glitch-free and generally easier to verify
  (an output is stable for the entire cycle it's valid), at the cost of
  sometimes needing an extra state/cycle of latency compared to an
  equivalent Mealy design.
- **Mealy machine:** outputs are a function of state *and* current inputs
  (`output = f(state, input)`). Can react within the same cycle an input
  changes (useful for protocols with tight combinational response
  requirements), but outputs can glitch combinationally if inputs glitch,
  and are more work to verify correctly because the output depends on two
  things changing together rather than one.
- **State encoding choices:** binary (minimum flip-flops, denser but
  decode logic can be a critical-path/glitch concern), one-hot (one
  flip-flop per state, larger but very tolerant of decode-logic timing and
  a very common encoding style in verification-friendly RTL because
  illegal states can be checked trivially with a "more than one hot bit"
  or "all zero" assertion), and gray-code (adjacent legal states differ by
  one bit — mainly used for state machines that cross clock domains, since
  it minimizes the chance of a CDC synchronizer catching an intermediate,
  illegal multi-bit-changed value; this previews the CDC topic in Phase 6).
- **Illegal-state recovery:** a real FSM verification concern that a purely
  functional description glosses over — what does the FSM do if it somehow
  lands in an encoded state that has no defined transition (due to a
  reset glitch, a soft error, or a design bug)? A well-specified FSM
  either defines a `default` transition back to a safe/reset state for
  every unused encoding, and/or has that property checked with an SVA
  "no illegal state reachable" / "illegal state always recovers within N
  cycles" property in Phase 5.

## 6. Timing basics: setup, hold, and why this matters for RTL/verification

- **Setup time (t_su):** data at a flip-flop's D input must be stable for
  at least t_su *before* the active clock edge.
- **Hold time (t_h):** data must remain stable for at least t_h *after*
  the active clock edge.
- **Setup violation** happens when combinational logic between two
  flip-flops is too slow relative to the clock period (a *max-delay*
  problem, fixed by reducing logic depth, pipelining, or slowing the
  clock). **Hold violation** happens when a launched signal arrives at the
  next flop *too fast* — before the previous cycle's capture has
  "settled" relative to clock skew (a *min-delay* problem, generally
  independent of clock frequency, and fixed by adding delay, not by
  slowing the clock).
- Why a verification engineer needs this even though STA (static timing
  analysis) is a separate discipline: (1) functional RTL simulation is
  a zero-delay / unit-delay abstraction that is *blind* to setup/hold
  violations by construction — a design can pass 100% of functional
  simulation and still fail in silicon from a timing violation, which is
  exactly why gate-level simulation with back-annotated timing and formal
  CDC/timing-exception checking exist as separate verification steps; and
  (2) multi-clock-domain designs (Phase 6, CDC verification) are
  fundamentally about *systematically avoiding* metastability that setup/
  hold violations cause when a signal crosses between unrelated clock
  domains — synchronizer flop chains, gray-coded pointers for async
  FIFOs, and CDC-specific lint/formal tools all exist to manage this one
  underlying physical problem.

## References / resources used

This session's material is drawn from standard, well-established digital
design fundamentals (De Morgan/Boolean algebra, mux/encoder/decoder/ALU
structure, latch vs. flip-flop, Moore/Mealy FSMs, setup/hold timing) as
covered in Harris & Harris, *Digital Design and Computer Architecture*
(the primary Phase 1 textbook reference in this roadmap's README), and
standard industry treatments of FSM encoding and CDC fundamentals. Live
WebSearch was available this session but was not needed for this pass,
since this material is stable, foundational content rather than anything
time-sensitive; it was applied here specifically framed around what a
verification engineer needs to reason about (checkable properties, corner
cases, ambiguity in spec language) rather than as a pure design reference.
