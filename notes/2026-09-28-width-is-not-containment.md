# Width is not containment: what an independent observer is, and what it still cannot arbitrate

**2026-09-28.** Pre-registered in
`notes/2026-09-28-independent-observer-preregistration.md`, committed before the
code existed. Implementation:
`examples/phase4_uvm_milestone/uart_uvm_tb.py`
(`UartSerialMonitorIndep`, `UartEdgeRecorder`, `UartIndepObserverTest`). Log:
`examples/phase4_uvm_milestone/uart_uvm_sim_output_2026-09-28.txt`. Plan change:
vplan **v6**.

**Scored: Q1 PASS (more strongly than filed), Q2 FAIL, Q3 FAIL, Q4 PASS, Q5
FAIL.** Five checks pass, three of them after their first form failed. All
three first forms are kept in the source.

---

## 1. What was built

The 09-27 item asked for an observer with its own timebase, because
`UartSerialMonitor` advances with `RisingEdge(dut.clk)` and counts the DUT's own
`BIT_CYCLES`, so under a baud mismatch it drifts *with* the DUT and agrees with
it — 5 disagreements in 1274 checks across ±7% of eps.

Two new components, neither connected to the scoreboard:

- **`UartSerialMonitorIndep`** — waits on `FallingEdge(pin)`, a physical event
  on the wire, then advances with `Timer` in picoseconds using its **own**
  spec-derived nominal bit period. Never `dut.clk`, never the driver's
  `bit_ps`. **The independence is enforced structurally**: check V2 reads the
  class's own source and fails the test if `dut.clk`, `RisingEdge` or
  `BIT_CYCLES` appears in its body. A claim about a timebase that is enforced
  only by intention is not enforced.
- **`UartEdgeRecorder`** — records every transition's *timestamp* and decodes
  offline, reporting a per-frame **margin**: the distance from each sampled
  instant to the nearest transition.

Neither is wired to the scoreboard on purpose. A tolerance sweep drives past
every decoder's limit by design, so an observer whose disagreements count as
errors is an observer that forces the test to fail — the same reason `_limit`
does not go through the scoreboard.

## 2. Four decoders, one sweep

256 frames: a 25 bp wide grid over ±9%, plus a 5 bp fine grid across the
observer's own limit.

| decoder | slow limit | fast limit | width | centre |
|---|---|---|---|---|
| DUT (register readback) | 6.75% | 4.00% | 10.75% | **+1.38%** |
| clock-synchronous monitor | 6.25% | 4.75% | 11.00% | +0.75% |
| **independent monitor** | 5.50% | 5.50% | 11.00% | **+0.00%** |
| edge-timestamp recorder | 5.50% | 5.50% | 11.00% | +0.00% |

On the 5 bp fine grid the independent observer's limits are **±5.55%**, width
**11.10%**, centre **+0.00%**.

## 3. Q1 PASSES, and more strongly than it was filed

The independent observer's window is centred at **exactly +0.00%**, with no
`rx_sync` and no oversampler anywhere in it, while the DUT's sits at **+1.38%**
at `BAUD_DIV=0`. **The whole of the asymmetry belongs to the receiver**, not to
the measurement path. v5 reported the centre offset and declined to assert it
because nothing distinguished a property of the DUT from a property of the
measurement; that half is now settled.

What is *not* settled is the **divisor dependence** of the offset (+0.50%
between `BAUD_DIV=0` and `1`). That remains a two-point observation and the 5 bp
two-divisor experiment is still open.

## 4. Q3 FAILS, and its replacement is the result

The pre-registration predicted the observer's window would be **narrower** than
the DUT's (10.53% vs 10.75%) and that a naive independent observer would
therefore be an under-budgeted oracle. It is **wider**: 11.10%.

And it makes no difference, because:

> **WIDTH IS NOT CONTAINMENT.**

The DUT's window is displaced and the observer's is centred, so neither contains
the other however wide it is. There are **13 baud errors, +5.60% through
+7.75%, at which the DUT receives a clean frame and the independent observer
does not**. A disagreement at any of them is evidence about the observer.

The disqualification generalises, and it is arithmetic rather than empirical,
which is what makes it a sign-off criterion instead of an observation. Any
observer that **locks once on the start edge and then counts a nominal bit
period** has, for 8N1, a budget of exactly

```
1/18 = 5.5556%   either side
```

— the drift accumulated at the **boundary preceding the last sampled bit**
(9 bit periods), not at the sample itself (9.5 bit periods). The DUT's slow
limit is **6.75%**. So that entire class of observer is ruled out at
`BAUD_DIV=0` before anyone measures anything, and making it *better at its own
job* cannot help.

**Q5 FAILS for the same reason.** The edge recorder's window is identical to
the naive monitor's (11.00%, ±5.50%), because it too locks once and counts a
nominal period. Its advantage is **diagnostic**, not a wider budget. What would
satisfy containment — and is not built — is an observer that **re-derives the
bit period per frame from the measured edge spacing**, so its budget comes from
arithmetic on recorded times rather than from drift against a fixed period.
vplan v6 records that as the open requirement.

## 5. Q4 answered as a result, which is what the item asked for

Disagreement with the DUT over the wide sweep:

| observer | disagreements | rate |
|---|---|---|
| clock-synchronous monitor | 13 / 170 | **7.65%** |
| independent monitor | 32 / 170 | **18.82%** |
| edge-timestamp recorder | 31 / 170 | **18.24%** |

09-27 measured **0.39%** for the clock-synchronous monitor on its own sweep. A
genuinely independent observer disagrees roughly **24× more often**, and that
number is the quantitative content of "a clock-synchronous monitor is a second
receiver, not an observer". The prediction of ≥5% holds; the concentration
prediction holds too — every disagreement is at |eps| ≥ 4.75%.

## 6. Three checks that failed in their first form, and what each was wrong about

This is the part worth re-reading in six months.

**V3 — the mutation was too weak, and it failed correctly.** It injected a 2%
error into the observer's own bit period and required the decode to change. It
did not change, and it should not have: 2% over 9 bit periods is 18% of a bit,
comfortably inside the half-bit budget. **A mutant smaller than the thing it is
meant to break is a badly chosen mutant, not evidence of insensitivity** — the
classic mutation-testing failure, and the first time this repository has
committed it since adopting mutation testing on 09-18. Rewritten as a *sweep*
that measures the observer's budget from the inside: clean at 5.50%, breaks
first at **6.00%**, against a derived **5.56%**. The check became a
measurement.

**V4 — the decoder over-segmented, and the aggregate looked healthy.** The
first `decode_frames` treated every falling edge preceded by one bit period of
idle high as a frame start. With 8N1, data `0x01` puts edges exactly one bit
period apart, so single frames segmented into several: **242 driven frames
decoded as 309**, every per-frame verdict came out `False`, and the aggregate
was reassuring — 309 frames, margin 0.5, no error anywhere. **A decoder that
over-segments produces a plausible total and a broken comparison.** The ratio
decoded/driven is now printed with every run and is 1.000. This was caught by
V1, the cheapest check in the file: *all four decoders must agree at eps = 0.*

**V5 — twice wrong, and the second correction produced the best result in the
run.**

- *First form:* "the margin must be positive for every correct decode." Wrong.
  At the limit a sample can land exactly on a transition and still read the
  right bit, when the neighbouring bit happens to carry the same value. So the
  decoder can be **correct by luck**, a zero margin is a legitimate outcome,
  and that is a finding about the instrument rather than a fault. It is now
  printed as one.
- *Second form:* `margin(eps) = max(0, 0.5 − 9.5|eps|)`. Wrong twice over. The
  multiplier is **9**, not 9.5 (see §4), which is why the limit is exactly
  1/18 and the fine grid's 5.55% is the last 5 bp point below it. And the
  margin is **data-dependent**, because a bit boundary with no transition
  across it is not an edge and the recorder records edges. The first predictor
  assumed a transition at every boundary and was out by up to **0.27 bit**.
- *Final form:* the minimum, over every sampled instant, of the distance to the
  nearest **actual** transition, given the frame's bit pattern. Measured
  against that closed form over the whole sweep: worst deviation **0.0000
  bit**.

That data dependence is not a detail. It turns the adjacent-bit
**transition-count** coverpoint — open since 2026-09-26 as a preference — into a
**sign-off dependency**: the margin is a function of the frame's transition
pattern, so an F7 coverage model over byte *values* cannot span it. vplan v6
records it as such.

## 7. What this session concludes

**An oracle needs two properties, and this repository has now spent three
sessions discovering them one at a time.** 09-25 required the *driver* to be
independent. 09-27 required the *observer* to be independent. Today adds that
independence is **necessary and not sufficient**: the observer's own window must
**contain** the window it arbitrates, and that is a different property from
being uncorrelated with the DUT. An observer can be perfectly independent,
measurably wider, and still wrong about the DUT at 13 of the operating points
that matter — which is the interesting failure, because every instinct says a
wider instrument is a safer one.

Stated as the general rule: **an instrument's independence tells you its
disagreements are informative; its coverage tells you whether they are about
the DUT.** The first without the second produces confident evidence about the
instrument.

Second, and now the fourth consecutive session on this theme: today's three
first-form check failures were found by the two cheapest possible checks — an
exact-agreement-at-zero check, and a printed ratio of frames decoded to frames
driven. Neither is clever. The expensive instruments (a 256-probe sweep, a
four-way comparison, a closed-form margin model) were all built on top of a
decoder that a one-line sanity check caught within a second of first running.

---

## Open, created or sharpened today

- **An observer that re-derives the bit period per frame** from measured edge
  spacing — created today, and the only route to a containing oracle. vplan v6
  states it as a requirement.
- **The transition-count coverpoint is now a sign-off dependency**, not a
  preference — created 09-26, promoted today with a quantitative reason.
- **The 5 bp two-divisor experiment** — created 09-27, still open. Today
  removed half of its ambiguity (the offset is the DUT's) and left the other
  half (whether it scales with the divisor) untouched.
- **Whether the DUT's +1.38% displacement is `rx_sync`'s one-clock delay**
  measured directly, now that the measurement path is exonerated. One clock is
  1/16 of a bit at `BAUD_DIV=0` = 6.25%... which is far larger than 1.38%, so
  the naive mechanism does **not** fit and the candidate needs replacing.
  Created today by Q1's success.
- **Audit the other benches' observers for the containment property** — the
  phase6 benches measure F7 too and none of them states its own window.
