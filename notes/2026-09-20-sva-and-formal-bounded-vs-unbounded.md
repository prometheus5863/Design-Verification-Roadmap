# Phase 5, day 1: SVA, bounded vs unbounded, and why "not proved" is not "broken"

**Date:** 2026-09-20
**Phase:** 5 (Assertions & Formal Verification) — started
**Artefacts:** `tools/setup_formal.sh`, `examples/phase5_formal_uart/`

---

## 1. Why this phase is not more simulation

Phase 4 ended with a 60-check regression and a UVM environment, all of which
answer the same shape of question: *on the traces I generated, did the DUT
misbehave?* Every one of those checks is existential over a finite set of
stimuli I chose. The FIFO count claim "`tx_cnt` never exceeds 8" is
universal over *all* traces of *all* lengths, and no number of simulations
establishes it. That gap is the entire reason formal exists, and it is why
this phase's first target was deliberately a FIFO invariant rather than the
serial datapath, which is the more interesting-looking but less formal-shaped
problem.

## 2. SVA: the pieces, and which of them this repo can actually run

SystemVerilog assertions come in two kinds.

**Immediate assertions** — `assert (expr) else $error(...)` inside procedural
code — are just conditional statements. Icarus 10.3 supports them, and they
are what the Phase 4 testbenches have effectively been doing by hand.

**Concurrent assertions** — `assert property (@(posedge clk) a |=> b);` — are
temporal: they describe behaviour over *sequences* of clock ticks, and they
are the real subject of this phase. The vocabulary:

- **Sequences.** `a ##1 b` (b one cycle after a), `a ##[1:5] b` (between 1
  and 5), `a[*3]` (three consecutive), `a[->2]` (goto: second occurrence,
  not necessarily consecutive). `throughout`, `within` and `intersect`
  compose them.
- **Implication.** `|->` is overlapping (consequent starts on the cycle the
  antecedent ends), `|=>` is non-overlapping (starts the next cycle).
  Without an implication, `assert property (b)` demands `b` on *every*
  cycle, which is almost never what is meant.
- **Local variables.** `int v; (start, v = data) |=> ##[1:8] (out == v)` —
  how a property captures a value at one moment and checks it later. This is
  the feature that makes data-transport properties expressible at all, and
  it is also the first thing a limited tool drops.
- **`assume` vs `assert` vs `cover`.** `assume` constrains the environment
  (the solver may not produce traces violating it), `assert` is the
  obligation, `cover` demands the tool *exhibit* a trace reaching a
  condition. In simulation `assume` is roughly a check on the testbench; in
  formal it is load-bearing, and an over-strong `assume` is the standard way
  to prove something vacuously.
- **Clocking and reset.** `disable iff (!rst_n)` is the idiomatic guard.
  The SymbiYosys equivalent used in this repo is an explicit `f_past_valid`
  register plus `if (f_past_valid && rst_n)`, because the property block
  must also stay inside the Verilog-2001-ish subset Yosys reads.

**What is actually runnable here.** Icarus 10.3 has essentially no
concurrent-assertion support, so the SVA above cannot be simulated in this
repo. Yosys 0.69's `read_verilog -formal` accepts `assert`, `assume`,
`cover` and `$past`, but not the full sequence/property layer. So Phase 5's
properties are written in the **immediate-assertion-on-a-clock-edge** style —
`always @(posedge clk) if (...) assert(...)` — which is expressively weaker
than SVA but is what both available tools accept, and is the style the
SymbiYosys literature uses throughout. The sequence vocabulary above is
therefore studied here and not yet exercised; that is a limitation to state
plainly rather than paper over.

## 3. Bounded vs unbounded, which is the whole point

**BMC (bounded model checking)** unrolls the design `k` cycles and asks the
SAT/SMT solver for a trace reaching a property violation within `k`. If it
finds one, the trace is a real, reachable counterexample. If it does not,
the only conclusion is *no bug within k cycles*. BMC is a **bug finder**, and
a complete one up to its depth.

**Temporal (k-)induction** is the unbounded argument:

1. *Base case*: the property holds on the first `k` states, from reset.
2. *Induction step*: if the property held on `k` consecutive arbitrary
   states, it holds on the next.

If both discharge, the property holds **forever, on every trace**. The catch
is step 2's "arbitrary": the solver starts from any state satisfying the
property, including states the design can never actually reach. A design can
be perfectly correct and still fail induction, because a bogus start state
has a successor that violates the property.

**That asymmetry produces three outcomes, and it bit this session.** On
mutant M1 (the TX push guard removed) SymbiYosys returned:

```
engine_0.basecase:  Status: passed
engine_0.induction: Status: failed
DONE (UNKNOWN, rc=4)
```

`UNKNOWN`, not `FAIL`. The tool is saying "I could not prove it and I did
not disprove it." The same mutant under `bmc`:

```
Assert failed in uart_controller: uart_controller.v:432  (P1, tx_cnt <= 8)
Assert failed in uart_controller: uart_controller.v:464  (P4)
DONE (FAIL, rc=2)
```

— a genuine reachable counterexample. **A mutation harness must score `bmc
FAIL`.** Scoring "prove did not return PASS" would have counted M1 as
detected for the wrong reason, and would count a *correct* but
non-k-inductive design as buggy. This is the same defect class as 2026-09-17,
09-18 and 09-19 — the subsystem reporting the verdict not being the
subsystem doing the checking — in its formal-tool form. It is the first of
the four caught **before** it produced a wrong number, which is only because
the previous three made the shape recognisable.

**Fixing an induction failure** (not needed this session, but this is the
standard toolbox): strengthen the invariant. Add assertions describing
*reachable* states so tightly that the solver can no longer pick a bogus
start state. Increase `k`. Or use an engine that computes the invariant
itself — `abc pdr` (IC3/PDR) rather than `smtbmc`, which does not need a
human-supplied strengthening. Stage 4 of `run_formal.sh` tests the
strengthening question directly by deleting P1 and re-proving P2: **P2 is
inductive on its own here**, so no strengthening was needed. Recorded as
measured, including that the answer was the boring one.

## 4. Vacuity, and why `cover` is not optional

A property suite that passes on a design which can never reach the
interesting states proves nothing. The classic vacuity is an implication
whose antecedent is never true; the classic *self-inflicted* one is an
`assume` strong enough to rule out the behaviour under test.

This suite guards against it with two cover statements: a **full** TX FIFO
(`tx_cnt == 8`) and a **wrapped** read pointer (`tx_rptr != 0 && tx_cnt ==
0`). Both were reached, at step 10 and step 6. Without them, P1 and P2 would
pass identically on a FIFO whose push guard was permanently false.

The one `assume` in the suite — `if (!f_past_valid) assume(!rst_n)` — forces
the trace to begin in reset rather than mid-flight, and is the minimum
needed. Every `assume` is a promise about the environment that somebody else
has to keep; the honest position is that this one is kept by any real system
that asserts reset at power-on.

## 5. Practical formal use cases (the Phase 5 checklist item), and which fit here

- **Connectivity / SoC integration.** Prove port A reaches port B through
  the mux tree. Trivially unbounded, huge state space, no simulation
  equivalent. Not applicable to a single peripheral.
- **X-propagation.** Prove no X reaches an output. Needs X-aware semantics
  Yosys's `-formal` flow does not model.
- **CSR / register-map properties.** Every RW register reads back what was
  written; RO registers ignore writes; reserved bits read zero. **This is
  the obvious next target here** — the UART has six registers and a RAL
  model from 2026-09-19 already describing them, and these properties are
  short, shallow, and exactly what BMC is good at. It also overlaps the
  vplan's F1/F1.1 features, which are currently covered only by directed
  simulation.
- **Deadlock / liveness.** "A request is eventually granted." Needs fairness
  constraints and an engine for unbounded liveness; `prove` mode handles
  safety only. Out of scope for this toolchain.
- **Arithmetic / datapath equivalence.** Not relevant to a UART.

## 6. What Phase 5 still owes

1. **CSR properties on the register map** — the natural next session, per
   Section 5.
2. **A property needing a strengthening invariant.** Stage 4 found P2
   inductive on its own, so the invariant-strengthening technique has been
   studied but never *exercised*. The serial datapath's "a started frame
   always completes" is the likely candidate.
3. **The sequence layer.** Section 2's `##`, `[*]`, `|->`, local variables:
   studied, not runnable on either tool here. Worth one session establishing
   whether any accessible tool (Verilator's partial SVA?) closes the gap,
   since interview questions assume fluency with it.
4. **`abc pdr` as a second engine**, which computes invariants itself and
   would give an independent check on the smtbmc result.
5. The Phase 5 checklist's "documented result" is done for one property set;
   the SVA-suite half of the milestone is not, for the tooling reason in
   Section 2.

## 7. Toolchain record

`tools/setup_formal.sh`. No root, no apt: `pip install --user yowasp-yosys
z3-solver` gives the real Yosys 0.69, SymbiYosys, `yosys-smtbmc` and
`yosys-witness` as WebAssembly builds, plus a native `z3`. sby calls its
helpers as plain `yosys`/`yosys-smtbmc`, so the script installs shims.
Source it, do not pipe it — the same subshell trap documented for
`setup_iverilog.sh` on 2026-09-18.

Cost: the WASM builds print "Preparing to run … This might take a while" on
every invocation and are noticeably slower to start than native binaries.
The full four-stage run — Icarus regression, three proofs, ten mutant runs,
one invariant experiment — still completes in well under two minutes.
