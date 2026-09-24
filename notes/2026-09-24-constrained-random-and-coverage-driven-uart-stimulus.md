# Constrained-random and coverage-driven UART stimulus: what the two mechanisms actually are, and a measured closure ratio

**Date:** 2026-09-24
**Repo:** Design-Verification-Roadmap
**Open item addressed:** *"Constrained-random and coverage-driven UART
stimulus — all stimulus in all benches is still directed while the vplan
assigns most features to CRV. Now the top item and the longest-standing one"*
— carried since Phase 2 and named top on 2026-09-23.
**Code:** `examples/phase6_crv_uart/uart_crv_cov_tb.v`,
`run_crv_cov.sh`, `run_mutation_tests.sh`; recorded output in
`uart_crv_cov_sim_output_2026-09-24.txt`, `closure_sweep_2026-09-24.txt`,
`mutation_test_report_2026-09-24.txt`.

---

## 1. Why this had to be built by hand, and why that is worth the trouble

Icarus 10.3 has no `rand`, no `constraint` blocks, no `covergroup`, no
`solve … before`. The tempting move is to write a SystemVerilog bench that
cannot run here and log it as done, which would be the repo's
verdict-vs-checking class again, in its purest form.

So both mechanisms are written out in Verilog-2001, and the exercise turns out
to be the most useful part:

| language feature | what it is, once written by hand |
|---|---|
| a constraint solver | rejection sampling over a bounded attempt budget |
| a covergroup | counter arrays, a sampling point per coverpoint, a closure predicate |
| coverage-driven stimulus | a mapping from *unhit bin* back to *stimulus that hits it* |

The third row is the one an interview actually probes, and writing it by hand
makes the answer concrete: a coverage-driven flow is nothing but that mapping,
applied automatically. A commercial tool does not invent stimulus; it searches
the constraint space with the coverage database as its objective. Everything
else — the bins, the sampling points, the closure criterion — the engineer
writes either way.

The rejection-sampling budget deserves its own note. `pick_config_random`
counts rejected candidates and **fails the run** if a single draw needs more
than 200. That is deliberately the hand-built equivalent of a solver reporting
an unsatisfiable constraint set: without it, an over-constrained draw is an
infinite loop, and *an infinite loop is the one failure mode a regression
cannot report*. Measured on a random run: 309 rejections in total, worst
single draw 11, against a budget of 200.

## 2. The constraint set, and which constraint does the work

```
C1  parity_mode != 2'b11          illegal encoding, never drive it
C2  baud_div <= 3                 drawn from 0..7, so C2 genuinely rejects
C3  (parity, stop) != previous    forces configuration variety
C4  burst_len in [1, 8]
```

C3 is the interesting one. Without it, a random walk can sit on the same
`(parity, stop)` pair for long stretches and the *cross* coverpoint barely
moves while the individual coverpoints look healthy. This is the standard
argument for crosses, and C3 is the standard answer: constrain against the
previous value rather than widening the distribution. C2 is drawn from a
wider range than it permits **on purpose**, so that the rejection count in
the report is a real number rather than a constant zero — a constraint that
never rejects is untested machinery.

## 3. RESULT — the measured cost of not steering

30 bins; closure is a pass criterion. Both modes, same constraints, same
seeds:

| seed | pure random | steered | ratio |
|---|---|---|---|
| 1 | 643 | 47 | 13.7x |
| 2 | 335 | 48 | 7.0x |
| 3 | 252 | 41 | 6.1x |
| 4 | 511 | 36 | 14.2x |
| 5 | 105 | 50 | 2.1x |
| 6 | 121 | 60 | 2.0x |
| 7 | 354 | 51 | 6.9x |
| 8 | 405 | 42 | 9.6x |

|  | random | steered | ratio |
|---|---|---|---|
| mean | 340.8 | 46.9 | **7.3x** |
| worst seed | 643 | 60 | **10.7x** |
| best seed | 105 | 36 | 2.9x |
| spread (max/min) | **6.1x** | **1.7x** | — |

**Read the spread, not only the mean.** Steering improves the worst case
10.7x and the best case 2.9x, collapsing a 6.1x seed-to-seed spread to 1.7x.
The honest statement is therefore not "coverage-driven stimulus is 7x faster"
but **"coverage-driven stimulus makes closure predictable"** — and on a real
project predictability is the more valuable of the two, because a regression
budget is set by the worst case rather than the mean.

Seeds 5 and 6 are the reason this needed a sweep. On those two the ratio is
2.0–2.1x, and a session that had run one seed and got seed 5 would have
written down a true number that misrepresents the mechanism by a factor of
five. This is the same lesson the other repo logged on 2026-09-20 about
unrepresentative samples, arriving from a different direction.

## 4. FINDING — a coverage hole can be a sampling-point defect, and it looks identical to a stimulus gap

The first working version of this bench closed 29/30. The missing bin was
`cp_txq.full`, and the natural reading — the stimulus never fills the TX FIFO
— was wrong.

The push loop samples STATUS *before* each push. With `burst_len = 8` the
last sample it takes is at occupancy 7, and the FIFO reaches 8 only after that
push. **The stimulus created the state and the covergroup never looked at
it.** One extra sample after the push loop closed the bin.

Two things follow, and the second is the more general:

1. A report saying `full = 0` cannot distinguish "never happened" from "never
   sampled", and the fix for the two is completely different.
2. It was caught because **closure is a pass criterion**. As a report line,
   29/30 with a PASS verdict is exactly the sort of thing that gets read as
   "nearly closed" and carried forward for weeks.

## 5. FINDING — the closure counter and the closure criterion were reading different databases

Sixth occurrence of the verdict-vs-checking class (09-17, 09-18, 09-19,
09-20, 09-21), and the first one produced by *two outputs of the same run
disagreeing*.

`seed=6, steer=1` printed both of these:

```
TRANSACTIONS TO CLOSURE  : NOT REACHED in 60  (steer=1)
RESULT: PASS  (11460/11460 checks)
```

Both statements came from the same run, and only one was true. The criterion
called `bins_hit()` at the end of the run; the counter was updated only at
*push* sites. Seed 6's last bin was filled by a STATUS sample rather than by a
push, so `closure_tx` stayed at its sentinel while `bins_hit()` reached 30.
The bench had closed and reported that it had not.

Two repairs, and the second is the one worth keeping. Every coverage update
now goes through one `note_closure` task, so there is a single definition of
closure. And the bench now **asserts that its two statements about closure
agree**:

```verilog
if ((bins_hit() == N_BINS) != (closure_tx >= 0)) begin ... errors++ ... end
```

Two lines. **An inconsistency between two outputs of one run is the cheapest
bug detector available, and it needs no reference model, no golden file and no
second tool.** Worth looking for wherever a bench reports the same fact twice.

## 6. RESULT — mutation testing: 4 detected, 2 escapes predicted in advance, 6/6 verdicts as predicted

`run_mutation_tests.sh` injects each defect into a **copy** of the RTL under
`/tmp`; the repo's RTL is never modified. G1 requires the baseline to PASS
first and aborts otherwise. Each verdict was predicted with a reason before
the run, and the script scores **prediction against outcome** rather than a
detection count — following 2026-09-19's rule that a detection count is a
number and an understood reach is a statement.

| mutant | verdict | why |
|---|---|---|
| M1 TX parity polarity swapped | DETECT | the RX parity check disagrees and sets `STATUS.parity_err`, which every status read asserts is clear |
| M2 RX data bit inverted at mid-bit | DETECT | every byte mismatches the reference model |
| M3 `CTRL.stop_bits` ignored by TX | DETECT | a two-stop frame runs one bit short, so the next start bit lands inside the previous frame's stop window |
| M4 TX FIFO count never increments | DETECT | `tx_full` can never assert, `cp_txq.full` is unreachable, **closure fails** |
| M5 `BAUD_DIV` ignored by the baud generator | ESCAPE, predicted | see below |
| M6 STATUS read no longer clears the sticky bits | ESCAPE, predicted | a clean loopback burst never injects an error, so a bit that fails to *clear* is never observed *set* |

**M4 is caught by the coverage criterion and by no data check whatever.**
Every byte still arrives correctly; the only thing that breaks is a bin's
reachability. This is the strongest available argument for the design decision
in Section 4 — closure as a pass criterion catches a class of RTL defect that
no amount of self-checking stimulus reaches.

**M5 is the most useful line in the table.** In loopback, TX and RX share one
baud generator, so a wrong divisor desynchronises nothing: both sides are
wrong together and the data is perfect. **No loopback bench, at any level of
sophistication, can detect a baud-rate error.** That is structural rather than
a gap in this suite's stimulus, and it converts an item that looked like
"write more stimulus" into a specific argument for the **standalone RX
bit-driver** the Phase 4 milestone still has open — a driver that generates
serial frames from its own timebase is the only thing that can check F7's
baud tolerance at all. The vplan's F7 has never been measured in any bench,
and now there is a reason on record why the existing bench shape cannot
measure it.

The script also fails the run if an injection matched nothing. A `sed` that
silently misses leaves the RTL unmodified, and the row then scores as an
escape against *correct* RTL — the same class of false verdict the mutation
test exists to prevent, one level up.

## 7. What this settles, and what it does not

Settled: the vplan's CRV assignment now has a running implementation with a
closure criterion, a measured steering benefit with its variance reported, and
a mutation report whose escapes are explained.

Not settled:
- **F7 baud tolerance** remains unmeasurable in this bench shape (Section 6),
  and now has a stated reason.
- The suite drives the **register interface** and the **loopback datapath**.
  It never drives the RX pin independently, so framing errors, parity errors
  and overrun are all reachable only by the directed bring-up bench.
- 30 bins is a small model. It has no bins for interrupt combinations, none
  for the loopback mux itself, and none for reset asserted mid-frame.
- Steering here is **greedy first-unhit**, the simplest possible policy. A
  real tool biases the constraint distribution rather than overriding it, and
  the difference shows up when constraints interact — which C1–C4 barely do.
