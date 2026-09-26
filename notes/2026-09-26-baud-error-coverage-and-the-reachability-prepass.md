# A coverage model on the driven baud error, and the pre-pass that fired against correct RTL

**Date:** 2026-09-26
**Code:** `examples/phase6_baud_error_coverage/` — `uart_baud_cov_tb.v`,
`run_baud_cov.sh`, `uart_baud_cov_sim_output_2026-09-26.txt` (3 seeds, 11
checks each, 0 errors), `run_mutation_tests.sh`,
`mutation_test_report_2026-09-26.txt` (5 detected, 1 expected escape, 0
unexpected, 0 voided)
**Plan:** vplan **v4** — two annotations in Section 2.7, one Section 3 row
**Predictions:** C2, C3, C5, C6 PASS; C1 and C4 FAIL, both informatively

---

## 1. The item, and why it was the top one

2026-09-25's vplan v3 revision created it:

> `cp_baud_div`'s corner bins measure the divisor *register*, not the
> tolerance; F7 needs bins on {0, within ±2%, within ±4%, beyond the limit}
> and a closure criterion over them. The stimulus now exists; the coverage
> model does not, and 09-24's finding 9 is the warning attached — check a new
> bin is reachable *before* putting it in a closure criterion.

Both halves turned out to be wrong in instructive ways: the bins are not the
right bins, and the warning is not sufficient as stated.

T1 disposes of the premise in one measurement first. Sweeping eps from −8% to
+8% at 2% steps — taking the receiver from perfect through broken and back —
`cp_baud_div` reports **1 of 4 bins hit, unchanged throughout**, because it
samples a register nobody wrote. A coverage report built on it reads
"covered" across the entire range of the behaviour it is nominally about.

## 2. The headline: the pre-pass fired against correct RTL

The first version of the bench had two verdicts. A cross cell was *reachable*
if the pre-pass produced it and *unreachable* otherwise, and every unreachable
cell became an illegal bin — an assertion that the cell must never occur.

Twenty-one frames into the random closure run, one of them fired. Band 3
(4% < |eps| ≤ the measured limit) × *byte lost*, from eps = −4.71% on 8O1
with a data pattern and edge phase the pre-pass had not tried. Correct RTL,
legal stimulus, a bench reporting a failure.

**A pre-pass answers "did my attempts reach it". That is not "is it
reachable", and collapsing the two manufactures false failures.** This is the
verdict-vs-checking class landing on the *reachability analysis* — after
checkers (six occurrences 09-17 to 09-23), measurement (09-24), and stimulus
and thresholds (09-25). Every layer of the testbench has now supplied an
instance, and so has the layer that decides what the testbench is allowed to
assert.

The fix is three verdicts:

| verdict | basis | goes into |
|---|---|---|
| `CLS_REACHED` | the pre-pass produced it | the closure criterion |
| `CLS_EXCLUDED` | an **argument** about the mechanism | an illegal bin |
| `CLS_OPEN` | not reached, not ruled out | neither |

Only two of fifteen cells are `CLS_EXCLUDED`, and the argument is stated in
the source rather than inferred from the attempts: at eps = 0 the driver's bit
period equals the DUT's nominal period exactly, so no drift accumulates over a
frame, and the only free variable is the initial edge phase, which moves every
sample point by less than one oversample tick (1/16 bit) against a half-bit
margin. The pre-pass's attempts are a *check* on that argument — it fails the
run if the pre-pass ever produces a cell the argument excluded — not its
basis.

`CLS_OPEN` is the load-bearing addition. It is an honest "don't know", which is
what a coverage report owes a bin it can neither hit nor rule out, and it is
what the two-verdict scheme had no way to express. Seed 2 of the committed
output shows the same refutation happening safely under the new scheme:
band 3 × lost, reached at frame 127, **reported as a result**.

**And "unreachable" is never a property of a bin.** It is a property of a bin
*and a stimulus space*. T4b makes that concrete: `eps == 0 × frame error` is
excluded for well-formed frames and trivially reachable the moment the stop
bit may be driven low, which the bench does deliberately and excludes from
`cls[]`. A coverage report that does not name its stimulus space cannot say
what an unhit bin means.

## 3. The specified bins are the wrong bins, three ways

**(a) They do not partition the domain.** 8N1's slow limit is +6.25%, so
eps = +5% is outside "within ±4%" and inside the limit — it belongs to none of
the four bands. Four bins that do not partition their domain silently drop
stimulus, and a closure criterion over them reports 4/4 hit while never
sampling the dropped region. A fifth band exists in this model to hold it, and
it took **19 of the 28 frames** of the steered closure run.

**(b) An absolute bin edge on a tolerance is a scale assumption.** Of twelve
probe rows across the four configurations, **seven** are classified
differently by the 4.00% edge and by the per-configuration measured limit.
This is the same fault the graphene repo has spent five sessions on — *a
numeric default is a claim about scale* — arriving in Verilog as a **coverage
bin** rather than a threshold.

**(c) A measured bin edge is a claim about the measuring stimulus.** The
anchored cross-check against 09-25's limits FAILED on the first run of this
bench. Same DUT, same sweep, same trial-set *size*: two of six bytes swapped,
`0x3C`/`0x81` for `0x01`/`0x80`, moved 8O1's fast limit by **0.50% of eps, in
the optimistic direction**. `0x01` and `0x80` put a lone 1 adjacent to the
start and stop bits — exactly where a drifting sample lands on a *differing*
neighbour. The BEYOND band's edge is derived from this number, so the bin
inherits the optimism. Kept as a standing experiment (T0b) rather than a
paragraph, because it is cheap and it is the reason the cross-check exists.

The cross-check's own tolerance is **derived, not chosen**: 09-25's measured
0.69%-of-eps phase sensitivity plus the 25 bp sweep grid. An independent bench
landing *inside that window* rather than on the number (8N1 fast +25 bp, 8E1
fast −5 bp) turns 09-25's "quote it as a band, not a number" from an inference
about sampling geometry into a **second measurement**.

## 4. What must not be written into sign-off

The tempting closure criterion is "beyond the limit ⇒ an error". It is false,
and 09-25 already contained the counterexample: at eps = +6.80%, past every
measured limit, frame_err appeared on 8/8 bytes with `data[7]=0` and 0/8 with
`data[7]=1`. Beyond the tolerance limit, survival depends on **the data** — a
bit that drifts into its neighbour's window is only corrupted if the neighbour
differs. C3 confirms the cell (beyond × clean) is reachable.

So it is neither a coverage bin nor an assertion. **A coverage bin records
that stimulus reached a region; it licenses no implication about what happens
there.**

## 5. Reachable is not reached

T5 runs the same closure criterion twice. Pure random stimulus, drawing the
fifth band uniformly over 4.05%–5.55% — the natural first choice — **did not
close in 250 frames** on seed 1: the *error* outcome in that band lives in the
last few basis points below the limit and a uniform draw almost never lands
there. The same criterion closes in **28 frames** once the generator aims its
band at the first unhit cell, which is the steering
`examples/phase6_crv_uart` already uses.

A measured argument for coverage-driven stimulus rather than an assertion that
it helps — and the sharper statement is the pair: **a cell can be reachable,
correctly judged reachable, and still out of a uniform generator's reach.**
That is 09-24's finding 9 arising from a *correct* reachability judgement
rather than from an unreachable bin.

## 6. Predictions, including two useful failures

- **C1 FAIL.** 8E1 at eps = −3.90%, inside the absolute ±4% bin, lost **0 of
  24** frames with the edge phase randomised across one oversample tick. The
  predicted mechanism is real but shows up one band further out: at −4.30%,
  past the measured limit, **12 of 24** frames were clean. The limit is a band
  *in the phase variable*, confirmed — but the ±4% bin is not unsafe by that
  route, and the reason it is still the wrong bin is (a) and (b) above, not
  this.
- **C4 FAIL badly, and the failure is better than the prediction.** Predicted
  2 non-reachable cells; measured **7 of 15**, because every
  inside-the-limit band is clean *by construction*. **A cross whose axes are
  causally linked is mostly illegal bins, not coverage.** Writing the naive
  15-cell cross into a closure criterion makes closure unachievable, and the
  useful half of the model is the outcome axis, not the band axis.
- C2, C3, C5, C6 PASS.

## 7. Mutation test: the coverage model detects nothing, and that is the point

5 detected, 1 expected escape, 0 unexpected, 0 voided. In **every** detected
row the first failure is the anchored cross-check of the measured tolerance
against 09-25's values — `BAUD_DIV` ignored (the 09-24 loopback escape),
sample position moved to tick 7 and to tick 12, the stop-bit check removed,
parity polarity swapped. Every one of those mutants **fills exactly the same
coverage bins**.

The glitch-filter mutant escapes, and the row says so with its reason: no
check in this bench observes a runt start pulse. An expected escape reported
as one is cheaper than rediscovering that it was.

**Coverage records what the stimulus reached. Only a check can say the DUT was
right.** A bench whose coverage closes and whose checks are thin is a bench
that measures its own stimulus.

## 8. Not yet covered (candidates for future runs)

- **Fold the independent-timebase driver into the Phase 4 UVM environment as a
  real `uvm_driver`** — open since 09-25 and now the clear top item: two
  benches (09-25's and today's) duplicate the driver verbatim, which today's
  header calls out as a real cost. Factoring it is the prerequisite.
- **Factor the APB and pin-driver tasks into an included fragment** — created
  today. They are copied verbatim between `phase6_rx_pin_driver` and
  `phase6_baud_error_coverage` so that a difference in results cannot be a
  difference in the driver; that reasoning does not survive a third copy.
- **A three-valued outcome axis for the OTHER coverage models** — created
  today. `phase6_crv_uart`'s 30 bins are all stimulus-side; today's cross
  shows the outcome axis is where the reachability structure lives, and the
  same cross applied to the CRV bench's crosses would say how many of its
  cells are illegal bins in disguise.
- **A coverpoint on the DATA pattern's adjacent-bit transitions** — created
  today by T0b. The tolerance depends on whether adjacent bits differ, so the
  right data coverpoint for F7 is not the byte value but its transition count;
  `cp_data`'s one-hot / AA-55 / popcount bins do not measure it.
- **Two transmitters at once** — created 09-25, untouched. A link's tolerance
  is the intersection of two one-sided budgets, which is how a real
  clock-accuracy spec is written.
- **`abc pdr` as a second engine** — unchanged since 09-23, still the best
  single experiment available.
- **Per-property coverage of the PHASE 4 UVM environment** — open since 09-23.
- **A less greedy steering policy** — created 09-24, and today gives it a
  concrete test case: the steering here aims at the *highest* unhit band
  first, which closed in 28 frames; nothing establishes that ordering is good.
- **A mutation script for `examples/phase4_uvm_milestone/`** — open since
  09-19. Today's script is a second adaptable template.
- **Mutants not yet attempted**: interrupt *enable* combinations, the loopback
  mux itself, reset asserted mid-frame.
- **A property that actually needs a strengthening invariant** — blocked on
  the same bound.
- **The SVA sequence layer** — runnable on neither tool here; open since
  09-20.
- **Code coverage measurement** — Icarus has none; open since 09-18.
- Phase 6: lint, regression infra, coverage merge, CDC basics, interview prep.
