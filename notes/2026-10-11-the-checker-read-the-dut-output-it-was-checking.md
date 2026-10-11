# 2026-10-11 — The checker read the DUT output it was checking, and the headline ratio had a stable denominator

Phase 6 capstone box **(a)** is closed: the constrained-random,
coverage-driven UART stimulus of `examples/phase6_crv_uart/` now runs from a
real UVM sequence. It had been deferred for four consecutive sessions, each of
which chose measurement infrastructure instead and each of which closed a real
item — but the roadmap's own next milestone had not moved, and 10-10 recorded
that the next session should do this one unless a defect forced otherwise.

New: `examples/phase6_uvm_crv_uart/` — `uart_uvm_crv_tb.py`,
`summarize_closure.py`, `run_mutation_tests.sh`, a parameterised `Makefile`,
and the dated sim/summary/mutation transcripts.

---

## 1. What was ported, and the one thing deliberately changed

Same DUT (`rtl/uart_controller.v`, unmodified), same four constraints, same
rejection budget of 200, same 30-bin model over 5 coverpoints and 2 crosses,
same bin-to-stimulus steering map. Real UVM rather than a Python generator
wearing the name: `UartCfgItem(UVMSequenceItem)`,
`UartCrvSequence(UVMSequence)` through a `UVMSequencer`, `UartRegDriver`
(`UVMDriver`) on the APB-lite register interface, `UartBusMonitor`
(`UVMMonitor`) broadcasting on a `UVMAnalysisPort`, and **two independent
subscribers on it** — `UartScoreboard` and `UartCoverage` — inside
`UartAgent`/`UartEnv`/`UartCrvTest` with the standard phases, objection-based
termination, factory creation and `UVMConfigDb`.

The deliberate change: in the Verilog bench the driver enqueued each byte to
the reference model *itself*, after reading `tx_full`. The checker's notion of
what the DUT accepted came from the thing driving the DUT — this repository's
09-19/09-20 shape. Here the scoreboard is fed **only** by the monitor and
derives acceptance from observed bus traffic, so driver and checker share no
variable. That change is also what produced §4, which is the session's main
result.

## 2. The measurement the port made possible

A UVM sequence is an object that can be started again, so N seeds × 2 policies
run inside one elaboration; a Verilog bench needs a separate `vvp` per seed.
Each seed pair costs ~70 s of Icarus wall clock and this environment's shell
calls are time-boxed, so the sweep is **resumable**: every run appends one
machine-readable row and `summarize_closure.py` adjudicates whatever rows
exist. It checks the sweep is well-formed before concluding anything — no
duplicate `(seed, policy)` rows, both policies on the same seed set, every run
actually closed — because an appended-row sweep can double-count if an
invocation is repeated, and averaging duplicates would narrow the very spread
the script exists to measure.

In the Verilog bench's own unit, TX_DATA pushes:

| policy | pushes to closure | median | spread | CV |
|---|---|---|---|---|
| pure random | 131, 228, 272, 279, 364, 1745 | 275.5 | **13.32×** | **1.218** |
| steered | 41, 42, 44, 48, 53, 58 | 46.0 | 1.41× | 0.141 |

**09-24's steered 47 reproduces.** It lands inside [41, 58] across a different
language, a different framework and a different RNG (Verilog's LCG → Mersenne
Twister). Agreement under that much change is evidence about the *method*, not
the two-artefacts coincidence the graphene repository's 10-02 rule warns about.

**09-24's pure-random 643 does not reproduce in any useful sense.** It lands
inside a range 13.3× wide. An interval spanning an order of magnitude contains
643 the way it would contain most numbers of that size.

So the 13.68× ratio has a **stable denominator and an unstable numerator**, and
across seeds it spans **2.26× to 42.56×** — an 18.8× range around the one
sample `progress.md` quoted as the argument for coverage-driven stimulus.

**What survives is stronger than what is lost.** Steering wins on every seed
and the distributions do not overlap at all (steered max 58 < random min 131).
And the steered cost is **8.7× tighter in CV**:

> Coverage steering does not mainly make closure *faster*. It makes closure
> cost **predictable**. A verification plan can be scheduled against 46 ± 7
> pushes; it cannot be scheduled against 131…1745 at all.

That claim is invisible from one seed per policy, because a single run has no
spread. The measurement the 09-24 bench could not make is the one that carries
the case.

## 3. Three defects in the new bench, found by the disagreement

The port first reported 2.1×, not 13.68×. Chasing that gap found three things,
all in the new bench and all recorded in place:

**(a) A constant ported without its unit.** The Verilog bench steers after
`STEER_AFTER = 24` "transactions", and its `total_tx` increments once per
TX_DATA *push*. The first draft carried the 24 across and applied it to
*sequence items*. A burst configuration carries 1–8 pushes, so "24" silently
became ~110 pushes of pure-random head start — **4.5× the Verilog bench's** —
and the measured speedup was dominated by the length of the prefix rather than
by the policy.

**(b) An off-by-one that made steering look like it never ran.** `cov.items`
was set *after* `finish_item`, so a closure latched mid-burst read the count of
*completed* items and reported **exactly 24 for every seed** — the hand-off
point — for a closure that happened during the 25th item, the first steered
burst. Three identical numbers across three seeds is what made it visible; a
noisier quantity would have hidden it.

**(c) An unpaired comparison.** `random.Random(seed*7919 + steer)` gave the two
policies *different* streams, so the difference between them mixed the policy
with the draw. Same seed for both now: the runs are identical until the
hand-off and the only difference after it is the policy.

And one hypothesis is recorded as **refuted** rather than deleted. The
unlabelled unit looked like the explanation for the whole discrepancy. It is
not: the per-item and per-push speedups agree to **1.01×**, because the mean
burst length is the same under both policies and divides out. The labelling fix
stands on its own; where the unit *did* matter was the hand-off constant.

## 4. The checker read the DUT output it was checking

Mutation testing, 4 mutants + an unmutated control, applied to copies of the
RTL with the testbench unmodified. On the first run:

| mutant | outcome |
|---|---|
| control (unmutated) | PASS, as required |
| M1 loopback mux removed | FAIL — burst watchdog |
| M2 TX even-parity bit inverted | FAIL — status error bits |
| M3 RX_DATA reads the wrong FIFO slot | FAIL — loopback mismatch |
| **M4 `tx_full` asserts one entry early** | **SURVIVED** |

M4 survived because of §1's improvement. The scoreboard derives push
acceptance from observed traffic rather than being told by the driver — but it
derived it from the DUT's own `STATUS.tx_full`. A mutant that corrupts
`tx_full` corrupts the reference model in exactly the same way, the two agree,
and nothing fires.

> **A checker that reads a DUT output as ground truth cannot detect a defect
> in that output.**

This is 10-10's rule — *a control must not read the thing it controls for* —
one layer down, in the scoreboard rather than in an arrival control. And it was
introduced by this session's own structural improvement and caught by mutation
testing in the same session, which is the first time that has happened here
rather than a session finding the previous session's hole.

**The repair makes `tx_full` a checked output rather than an input.** The burst
is filled with the UART disabled — the TX engine only pops in `TX_IDLE` when
enabled, which is also the only reason the `cp_txq.full` bin is reachable at
all — so during the fill phase occupancy is *exactly* the number of accepted
`TX_DATA` writes since the last `en=0` CTRL write. The scoreboard predicts
`tx_full` from that with no help from the DUT, uses its own model to decide
acceptance, and compares predicted against reported on every STATUS read of
the fill phase. M4 is now killed twice over, with the exact diagnostic
`tx_full reported 1, model says 0 at occupancy 7 of 8`.

The prediction is claimed **only** inside the fill window. Outside it the
engine is popping and occupancy is not derivable from the bus, so the check is
not attempted — claiming it there would be the 10-05 defect, a quantity printed
beside the thing it does not measure. Nothing is given up, because the fill
window is the only window in which this bench observes `tx_full`.

**And the Verilog bench still has the hole**, for the same reason: its driver
reads `tx_full` and enqueues to `expq` on that basis. Recorded as an open item
rather than repaired here, because that file owns a committed transcript.

Closure counts are unchanged by the repair (seed 1, steer=1: 11 items / 48
pushes before and after), so the distribution in §2 still describes this bench.

**Provenance, 10-09's rule.** All four detections are a *failing check*; none
is a crash or a timeout, against 3 of 6 by crash in
`mutation_test_reachable_cross.py`. Printed per mutant, measured rather than
assumed.

**M2 earns its own line.** An inverted TX parity bit is caught by the STATUS
error-bit check and by **no data comparison at all** — the byte still arrives
correctly in loopback, because both the TX parity generator and the RX checker
read `cfg_parity` and only the generator was mutated. That check was carried
over from the Verilog bench on the argument that a spurious framing/parity/
overrun error must fail the run even though no data check would notice. This is
the first time it has been shown to be the only thing standing between a real
defect and a green run.

**Injection guard, 10-07's rule.** Every mutant declares `EXPECTED_SITES` and
the run aborts with `GUARD_FAIL` if `grep` finds a different count. `cmp -s`
is kept only as a second, weaker gate, because it answers "did the file
change" and not "did the change I specified land" — a sed expression matching
two sites when one was intended, or zero because the source was reformatted,
both pass `cmp`.

## 5. Methodological note

09-17 a suite can pass against broken RTL. 09-18 and print PASS over its own
errors. 09-19/09-20 the subsystem reporting the verdict is not the one doing
the checking. 09-26 a reachability pre-pass answers "did my attempts reach
it". 09-30 a control has to sit where the failure enters. 10-01 an arrival
control that cannot fail is not a control. 10-05 a metric can be printed
beside the thing it does not measure. 10-06 and the detector can misattribute
what it measured. 10-07 an injection guard is a measurement. 10-08 a false
SURVIVED is worse than a missed defect. 10-09 and so is a false DETECTED — a
verdict must name the mechanism that produced it. 10-10 a control must not read
the thing it controls for.

**10-11: AND NEITHER MAY A CHECKER. A SCOREBOARD THAT TAKES ITS REFERENCE FROM
A DUT OUTPUT IS BLIND TO EXACTLY THAT OUTPUT'S DEFECTS.**

Checkable rule: **for every DUT signal a checker reads, ask whether the
checker could detect that signal being wrong. If not, either predict it
independently in the window where that is possible, or state the blind spot.**
The mechanisable form is a census: list every DUT signal each scoreboard
reads, and for each one name the mutant that would prove it is checked rather
than trusted.

Second rule, from §3: **a constant carried from one bench to another carries
its unit, and the unit is usually not in its name.** `STEER_AFTER = 24` is
correct in both benches and means two things 4.5× apart. Mechanisable: any
constant copied across harnesses must have its unit in its identifier —
`STEER_AFTER_PUSHES`, not `STEER_AFTER`.

Third, from §2: **a single-seed figure is not a property of a method.** Where a
quantity is a random variable, the spread is part of the result, and quoting
one draw of a ratio can understate *and* overstate the case at once — here it
overstated the speedup and entirely missed the predictability, which is the
better argument.

## 6. Toolchain and automation health

**The simulator was needed this session, after two sessions without it**, and
10-10 recorded that two sessions without exercising the gotchas is the point at
which they stop being verified knowledge. All three are now **re-confirmed on
this environment**:

* `source tools/setup_iverilog.sh` **without a pipe** — piping runs it in a
  subshell and the `iverilog`/`vvp` shell functions vanish. Confirmed: Icarus
  10.3 came up and reported its version.
* `export PATH="$HOME/.local/bin:$PATH"` or `cocotb-config` is missing and the
  Makefile fails with `No rule to make target '/Makefile.sim'`. Confirmed —
  pip warned about exactly that directory not being on PATH.
* The install recipe of `notes/2026-09-06-uvm-python-toolchain-resolution.md`
  still works: `pip install python-constraint --use-pep517`, then
  `"cocotb<2.0"` (1.9.2 here), then `uvm-python` (0.4.0).

Two new environment facts worth recording:

* **`print()` inside a cocotb test is buffered to the end of the run**, so a
  long sweep shows nothing until it finishes. A background `nohup` run does
  not survive this environment's shell call either. Both are why the sweep is
  resumable across invocations rather than one long run.
* **uvm-python's `UVMConfigDb.get` writes into a list argument** and raises
  `value must be a list-like with append` if given `None` — unlike the SV
  `uvm_config_db#(T)::get` output-argument form. The existing
  `examples/phase4_uvm_python/alu_uvm_tb.py` already had the right idiom.
* `cocotb`'s `BinaryValue.__int__` raises on `x`/`z` rather than resolving, so
  a monitor sampling from time 0 — before any reset sequence has driven the
  bus — crashes on its first sample. Handled by returning `None` and skipping,
  and **counting** the skips: an access the monitor cannot resolve is one it
  must not report, and a monitor that guessed 0 there would silently fabricate
  a quiet bus.

Device reachable and folder connected at the first firing; nothing crossed the
bridge. Every commit was pushed and verified against the GitHub API before the
next was written, with `git fetch origin main` immediately before each push per
the 10-03 race item.
