# The lowest set bit: an instrument whose competence is a function of the stimulus

**2026-09-29.** Design/functional verification study note. Continues the
instrument-quality thread that runs 09-24 (anchored comparison) → 09-25
(independent driver) → 09-26 (a freshly produced anchor) → 09-27 (independent
observer) → 09-28 (independence is necessary and **not sufficient**: the
observer's window must *contain* the window it arbitrates).

This session closes 09-28's top item — an observer that re-derives the bit
period per frame — and then does the thing 09-28's result made necessary:
measures the new instrument's window over the **whole** input space instead of
sampling it.

---

## 1. What was built, in one paragraph

`UartAdaptiveEdgeObserver` locks on the start edge at `t₀`, assigns each
consecutive inter-edge gap an integer bit-index increment
`Δn = round(Δt / T_ref)`, and after each assignment replaces `T_ref` with the
running least-squares estimate through the origin, `T̂ = Σ n·t / Σ n²`. It then
samples at `t₀ + (i + 1.5)·T̂`. The period it uses comes from the frame, not
from the observer. That is the whole idea, and it is the only route 09-28 left
open: a fixed-period observer accumulates `9·ε` of drift by the boundary
preceding the last sampled bit, giving an arithmetic budget of exactly
`1/18 = 5.5556%`, which is **smaller than the DUT's measured 6.75% slow limit**,
so that entire class is disqualified from arbitrating F7 by arithmetic rather
than by measurement.

---

## 2. The pre-registered law was wrong, and the correction is sharper than it

Pre-registration (`notes/2026-09-29-adaptive-observer-preregistration.md`, P1,
committed before the code existed) predicted

```
|ε| < 1 / (2·g_max)       g_max = the LARGEST inter-edge gap, in bit periods
```

reasoning that the integer assignment is the only step that can fail, and it
can fail on any gap. **It cannot.** After the *first* assignment the running
least-squares update has already replaced the nominal reference with an
estimate of the transmitter's own period, so every later gap is assigned
against a reference that is already right. Only the first assignment is made
against a period the observer brought with it. So

```
|ε| < 1 / (2·g_first)     g_first = the FIRST gap, start edge → next transition
```

and for 8N1 LSB-first the first transition after the start edge is the **lowest
set data bit**:

```
g_first = 1 + ctz(data)      (9 for data == 0)
```

**The observer's baud tolerance is set by the position of the lowest set bit in
the payload and by nothing else in the byte.** `0x01`, `0x03`, `0x7F`, `0xFF`
and 124 other odd bytes all get 50%; `0x80` gets 6.25%; `0x00` gets 5.56%. Two
bytes that differ in seven of eight bits have identical budgets if they agree on
where their lowest 1 sits, and two bytes differing in one bit can differ by a
factor of nine.

This is the third time this month a pre-registered number has failed in a way
that produced the session's result, and the pattern is worth naming: **P1 was
wrong because it mislocated the failure in the algorithm, not because it
mis-estimated a quantity.** A prediction with a mechanism attached fails
informatively; one with only a number attached fails uninformatively.

---

## 3. Nine frames is not a measurement of 256 bytes

The simulation measured five bytes, one per budget class, and every measured
limit was the last clean step below its bound: `0xAA` 25.00% vs 25.00%, `0x08`
12.50% vs 12.50%, `0x04` 16.60% vs 16.67%, `0x80` 6.20% vs 6.25%, `0x00` 5.50%
vs 5.56%. On that basis it concluded the observer **contains** the DUT's window
for 254 of 256 bytes and fails for exactly `0x00` and `0x80`.

That conclusion is an extrapolation from five points, and it was about to
become a **sign-off criterion naming two bytes**. So `budget_law_exhaustive.py`
measures the other 251. It lifts the decode out of `uart_uvm_tb.py` by source
extraction (`ast.get_source_segment`) and execs it against a stub base class, so
the algorithm measured is byte-identical to the algorithm the UVM regression
runs — re-typing it would have made any disagreement between the two
uninterpretable, which is 09-24's rule. Stimulus is synthesised as edges at
`t₀ + n·bit_ps` with the BFM's own integer-ps rounding. 512 limits at 1 bp
resolution, 6.9 s, **no simulator required**, which is why it sits in
`run_phase4_uvm.sh` ahead of the five UVM tests rather than in a notes file.

| `g_first` | bytes | predicted | measured slow limit |
|---|---|---|---|
| 1 | 128 | 50.000% | 4999 bp |
| 2 | 64 | 25.000% | 2500 bp |
| 3 | 32 | 16.667% | 1666 bp |
| 4 | 16 | 12.500% | 1250 bp |
| 5 | 8 | 10.000% | 999 bp |
| 6 | 4 | 8.333% | 833 bp |
| 7 | 2 | 7.143% | 714 bp |
| 8 | 1 | 6.250% | 625 bp |
| 9 | 1 | 5.556% | 555 bp |

256/256. The **negative control fires**: the pre-registered `g_max` law matches
only 90 of 256, so 166 bytes refute it and the comparison demonstrably can
reject a wrong law. The tolerance region is contiguous for every byte —
checked, because a discontiguous one would invalidate the word *budget*. And
the non-containing set is measured to be **exactly** `{0x00, 0x80}`, equal to
the predicted set.

---

## 4. The law is one-sided for half the input space, and a defensive guard is why

This is the finding the exhaustive scan produced that the nine-frame
measurement could not have. All 128 bytes with `g_first = 1` have their slow
limit at the predicted 4999 bp and **do not fail anywhere on the fast side
within ±60%**.

The mechanism is one line of the decode, and it is not arithmetic:

```python
dn = int(round((tj - t_prev) / t_ref))
if dn < 1:
    dn = 1                    # <- this
```

For `g_first = 1` a fast frame's first gap rounds *down*, and the only wrong
value it can reach is **0** — which the clamp turns back into the correct 1. For
`g_first ≥ 2` the wrong value is ≥ 1 and the clamp cannot help, which is why
those 128 bytes are symmetric to within 1 bp. The raw assignment is printed as
0 at −60% for four such bytes, so the mechanism is demonstrated rather than
asserted.

**A guard whose job is to prevent a nonsensical index also prevented a failure
that was bounding the instrument.** It makes the instrument better, and it makes
the stated law wrong in the conservative direction — which is the direction one
wants to be wrong in, and is still worth knowing, because a budget quoted
symmetrically under-claims the fast side of half the input space. Recorded with
its limit: *unbounded* here means *did not fail in the scanned ±60%*, and a
frame beyond −100% is not physical.

The mutation report makes the same point from the other side: removing that
clamp moves this result **and leaves V3's law, V4's containment set and V6's
anchored threshold bit-identical**. The line is load-bearing for one claim and
irrelevant to the claim sign-off rests on.

---

## 5. One number, three independent routes

The law says the observer's tolerance is about the *first assignment*. If that
is true it must also govern a corruption of the observer's **own** starting
reference, which is a different experiment: `round(g·(1+ε)/(1+s))` fails when
`g·|1/(1+s) − 1| > ½`, i.e.

```
s* = 1/(1 − 1/(2·g_first)) − 1
```

For the binding byte of this morning's A4 sweep (`0xAA`, `g_first = 2`) that is
**33.33%**, so the first sweep point above it is 4000 bp. This morning's
*simulation* broke at 4000 bp. The model, run this afternoon, breaks at
4000 bp. Derivation, simulation, and an independent model implementation of the
same algorithm agree on one number — and the derivation came from a law that was
fitted to neither of them.

---

## 6. What this is for: stimulus selection IS oracle selection

Two consequences, and the second is the transferable one.

**(i) F7 evidence may not be carried by `0x00` or `0x80`.** This is now a
measured fact over the whole input space rather than an inference, and it goes
into vplan v7 as a sign-off criterion. A constrained-random F7 test that draws
payload bytes uniformly will draw one of those two bytes in **0.78%** of frames,
and at those frames the observer's window is narrower than the DUT's, so a
disagreement is evidence about the observer. It will not announce itself: the
disagreement looks exactly like a DUT failure.

**(ii) The instrument's competence is a function of the stimulus.** Every
observer this repository built before today had *a* window — a property of the
observer, quotable once. This one does not. It has 256 windows, and choosing the
payload byte chooses how competent the oracle is, over a 9× range. That inverts
the usual reading of the stimulus/checker split: stimulus is normally thought of
as what *reaches* the DUT and the checker as what *judges* it, independently. Here
the stimulus silently reconfigures the judge.

Combined with 09-28's finding that the per-frame *margin* is an exact function of
the frame's **adjacent-bit transition count**, there are now **two orthogonal
per-byte quantities** that determine what an F7 result means: `1 + ctz(data)`
sets the budget, and the transition count sets the margin. Neither is a
function of the byte's *value* in any way a value-based or range-based coverage
model can span — `0x01` and `0xFF` are adjacent in neither. That is the concrete
argument, now twice over, for the transition-count coverpoint promoted to a
sign-off dependency on 09-28, and a new one for a `ctz` coverpoint beside it.

The general shape, stated for the interview answer it will eventually be: *when
an instrument derives its own reference from the signal it is measuring, the
signal's content becomes part of the instrument's specification.* Adaptive
instruments buy accuracy by giving up a fixed, quotable error bar. You get the
accuracy; you owe a coverage model over whatever the adaptation depends on.

---

## 7. Honest limits of today's measurement

- `budget_law_exhaustive.py` is a **model check**, not a simulation. It measures
  the instrument, which is pure arithmetic on recorded timestamps and therefore
  the half of the containment comparison that *can* be settled exhaustively
  without a simulator. It says nothing about the DUT, whose window remains a
  simulation result (slow 6.75%, fast 4.00%, `BAUD_DIV=0`).
- Its stimulus generator is rebuilt rather than reused, so a defect there is
  covered only by V6's anchor to the committed simulation log. No mutant was run
  on it; recorded in the mutation report as not done.
- The 254/256 containment claim inherits the DUT window's own uncertainty. The
  measured margin at `0x40` (`g_first = 7`, 714 bp vs 675) is **39 bp**, and
  09-25 measured one oversample tick of initial edge phase moving a limit by
  0.69% of ε. 39 bp is inside that. **So the third-tightest byte is not
  comfortably contained, and `0x40` and `0xC0` should be treated as borderline
  rather than passing** — a two-divisor measurement of the DUT's window is the
  open item that would settle it.
