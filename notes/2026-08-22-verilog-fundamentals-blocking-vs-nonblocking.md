# Phase 1 Study Notes: Verilog-2001 Fundamentals & Blocking vs. Non-Blocking Assignment

**Date:** 2026-08-22
**Roadmap item:** Phase 1 — Digital Logic & HDL Fundamentals
**Covers checklist item:** "Verilog-2001 fundamentals (modules, always
blocks, blocking vs. non-blocking assignment)"

**Note on tooling:** this session's sandbox does not have Icarus Verilog
(`iverilog`) installed and has no package-manager write access to install
it, so the example code below was **not simulated in this session** — the
expected outputs stated are derived from careful manual application of the
IEEE 1364 simulation event-scheduling semantics (the standard reference
semantics summarized in Section 3), which is unambiguous for the examples
chosen. The code is written to be run and checked with `iverilog -o sim
shift_register_blocking_vs_nonblocking.v && vvp sim` on a machine with
Icarus Verilog available — flagged here rather than silently presented as
simulated.

## 1. Module basics (Verilog-2001 style)

```verilog
module and_gate (
    input  logic a,
    input  logic b,
    output logic y
);
    assign y = a & b;   // continuous assignment: purely combinational
endmodule
```

Verilog-2001 (as opposed to Verilog-95) added ANSI-style port declarations
(direction + type in the port list itself, as above) instead of requiring
separate `input`/`output` declarations in the module body — this is the
style used throughout this roadmap and in industry RTL today. Module
instantiation uses named port connections almost universally in real
codebases (positional connection is error-prone and considered bad
practice once a module has more than 2-3 ports):

```verilog
and_gate u_and (
    .a (sig_a),
    .b (sig_b),
    .y (sig_y)
);
```

## 2. `always` blocks: combinational vs. sequential

Two `always` block *shapes* cover the overwhelming majority of RTL:

```verilog
// Combinational: sensitivity list covers every signal read inside the block.
// Verilog-2001 allows always @(*) to auto-infer the sensitivity list --
// always prefer this over manually listing signals, since a missing
// signal in a manual list creates a simulation/synthesis mismatch bug
// (simulation shows stale values; synthesis, which always treats this as
// combinational regardless of the list, does not).
always @(*) begin
    y = a & b;
end

// Sequential: sensitivity list is exactly the clock edge (and
// asynchronous reset edge, if used).
always @(posedge clk) begin
    q <= d;
end
```

The single most important rule connecting `always` block *shape* to
assignment *type* (Section 3) is:

> **Combinational `always @(*)` blocks should use blocking (`=`)
> assignments. Sequential `always @(posedge clk)` blocks should use
> non-blocking (`<=`) assignments.** Mixing these within the same variable
> is a well-known source of simulation/synthesis mismatches and race
> conditions, and is flagged by essentially every lint tool used in
> industry (Verilog lint rulesets like those built into VCS/Questa/Verible
> all check this).

## 3. Blocking (`=`) vs. non-blocking (`<=`) assignment semantics

This is the most commonly misunderstood topic for engineers new to
Verilog, and it's foundational enough that it deserves the precise
simulation-semantics explanation, not just the "rule of thumb" above.

- **Blocking assignment (`=`):** executes immediately, in program order,
  *within* the current simulation time step — the assigned variable's new
  value is visible to subsequent statements in the same `always` block
  (and to other blocks scheduled in the same evaluation region) right
  away, as if it were a normal sequential-programming-language assignment.
- **Non-blocking assignment (`<=`):** the right-hand side is evaluated
  immediately (using the *current* values of all variables involved), but
  the actual *update* to the left-hand-side variable is deferred to the
  end of the current time step (the NBA — non-blocking assign — update
  region of the IEEE 1364 stratified event queue, which runs after all
  blocking assignments and all "active" region evaluation for that time
  step have completed).

### 3.1 Why this makes non-blocking correct for sequential logic

Consider a 2-stage shift register meant to model two flip-flops both
sampling on the same clock edge:

```verilog
// CORRECT: non-blocking -- both flops sample the OLD value of the
// signal upstream of them, exactly like real parallel hardware flip-flops
// clocked by the same edge.
always @(posedge clk) begin
    q1 <= d;
    q2 <= q1;
end
```

At a given `posedge clk`, both right-hand sides (`d` and `q1`) are
evaluated using their values *from before this edge*, and both updates are
committed together at the end of the time step. This correctly models two
real flip-flops that both sample their D input at the same physical clock
edge — `q2` gets the *old* `q1`, i.e. the value that was present *before*
this clock edge, which is exactly the one-cycle-delayed shift-register
behavior intended.

```verilog
// BUG: blocking assignment used for what should be sequential logic.
always @(posedge clk) begin
    q1 = d;
    q2 = q1;   // reads the value q1 was JUST assigned above, in the
               // same clock edge -- collapses two flip-flops of delay
               // into one.
end
```

Because blocking assignment updates `q1` immediately, the second line's
read of `q1` sees the *new* value from this same edge, not the old one.
The simulated (and, for most synthesis tools, the synthesized) behavior
becomes a single-cycle shift instead of a two-cycle shift: `q2` tracks
`d` with only *one* cycle of delay instead of two. This is a functional
bug, not just a style violation, and it is exactly the class of bug that
a directed testbench (checking `q2` against a delayed-by-two-cycles
reference model) or, later in the roadmap, an SVA property like
`assert property (@(posedge clk) q2 == $past(d, 2));` is designed to
catch.

### 3.2 Why blocking is correct (and non-blocking is needlessly confusing)
### for combinational logic

```verilog
// CORRECT: blocking, values propagate immediately within the block,
// matching the "instantaneous" semantics wanted for combinational logic.
always @(*) begin
    sum  = a + b;
    total = sum + c;   // sees the just-computed 'sum', as intended
end
```

If non-blocking were used here (`sum <= a + b; total <= sum + c;`), both
right-hand sides would be evaluated using the values from *before* this
block ran (since neither update commits until the NBA region), so `total`
would use the *previous* evaluation's `sum`, not the one just computed —
a one-evaluation-cycle-stale bug that is hard to spot because it may
happen to produce the right answer once values stabilize into a steady
state, and only shows up as a subtle bug when inputs are actually
changing every cycle. This is exactly the kind of latent bug that
simulation alone (without a self-checking testbench comparing against a
reference model every cycle, not just at steady state) can miss.

### 3.3 The classic swap example (why simultaneity matters)

```verilog
// Register swap -- classic textbook example of why NBA semantics exist.
always @(posedge clk) begin
    a <= b;
    b <= a;
end
```

With non-blocking assignment, both right-hand sides (`b` and `a`) are
evaluated using their pre-edge values, so this correctly swaps `a` and
`b` every clock edge — exactly matching what two cross-coupled flip-flops
built from discrete gates would physically do. The blocking-assignment
version (`a = b; b = a;`) does *not* swap; it makes both `a` and `b` end
up equal to the original `b` (since the second statement reads the just-
overwritten `a`), which is obviously wrong and is a favorite interview/
exam question for exactly this reason.

## 4. Companion code

See `examples/phase1/shift_register_blocking_vs_nonblocking.v` for a
self-contained module pair (correct non-blocking version and buggy
blocking version of the same 2-stage shift register) plus a directed
testbench that drives a known input sequence and checks `q2` against a
`$past`-style software reference model, to make the bug and its detection
concrete rather than purely conceptual. As noted above, this was written
and hand-verified against IEEE 1364 semantics but not run through a
simulator in this sandboxed session (no iverilog available) — running it
locally with Icarus Verilog is a natural follow-up rather than something
this session could self-verify end-to-end.

## References / resources used

Semantics summarized here follow the IEEE 1364-2005 Verilog LRM's
stratified event queue model (active/inactive/NBA/postponed regions),
which is the standard reference for blocking vs. non-blocking assignment
timing, and is covered in essentially every industry Verilog/SystemVerilog
methodology guide (e.g. Sutherland & Mills, "Standard Gotchas: Subtleties
of the Verilog and SystemVerilog Standards That Every Engineer Should
Know" — the canonical paper specifically about this topic and the
`always @(*)`-with-blocking / `always @(posedge clk)`-with-non-blocking
coding guideline). Live WebSearch was available this session but was not
used for this note, since IEEE 1364 event-scheduling semantics are fixed,
stable standard content rather than time-sensitive information.
