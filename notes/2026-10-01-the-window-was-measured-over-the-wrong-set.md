# The window was measured over the wrong set

**2026-10-01.** The top open item since 2026-09-27 was "the two-divisor 5 bp
window measurement". It is closed. The answer is negative, and it is bigger
than the question: the hoped-for F7 admissible set of 254/256 is unreachable
at any divisor, **and the committed 252/256 is itself an overcount — the
right figure is 247/256.**

The instrument is `examples/phase6_divisor_window/uart_divisor_window_tb.v`:
16 checks, 18483 frames, plain Verilog on Icarus, no cocotb and no
uvm-python. It reads the DUT through its own APB register interface with the
pass criterion `uart_uvm_tb.py`'s `_probe` uses, and it takes the limit
definition from `_window` verbatim, so the two benches are comparable by
construction rather than by resemblance. The pin is driven only by
`bfm/uart_rx_pin_bfm.v`, per the 2026-09-27 single-driver rule.

## 1. What was pre-registered, and how it came out

Five predictions were written into the file's header from reading
`rtl/uart_controller.v`, before it was first run. The RX engine enters
`RX_START` on the clk edge at which the registered `rx_sync` is low and
zeroes `rx_os` there; `rx_os` advances only on `os_tick`; and
`rx_mid = os_tick & (rx_os == 8)`, so the start bit is sampled on the
**ninth** oversample tick after detection, not the eighth. Write the total
sampling lateness, in bit periods, as

```
p = 1/16  +  rho / (16 * (div+1))
    ^^^^     ^^^^^^^^^^^^^^^^^^^^
 structural    detection latency,
 ninth tick    rho in clk cycles
```

and sampling of framed bit *k* happens at `k + 1.5 + p` nominal bit periods
after the true falling edge.

| | prediction | outcome |
|---|---|---|
| **P1** | width is exactly 1/9 = 1111.1 bp at every divisor | **CONFIRMED** |
| **P2** | centre = p/9 | framework, not separately testable |
| **P3** | rho is one small positive integer at all divisors | **FALSIFIED** |
| **P4** | the centre has a floor of (1/16)/9 = 69.4 bp | **not supported** |
| **P5** | so the slow limit has a 625 bp floor and no divisor admits either byte | **conclusion survives, argument FALSIFIED** |
| **A2a** | the committed 675/400 reproduces at zero edge phase | **FALSIFIED** |

The three that fail are **left in the suite as failing checks**. The file's
purpose is to decide them, and a prediction deleted once it is refuted cannot
be audited later. `run_divisor_window.sh` therefore gates on the exact
expected tally (`13/16 ... 3 failed`) rather than on zero failures — a suite
whose failures are part of its result needs its result pinned, or the next
change to it is invisible.

## 2. P1 holds exactly, and it collapses a 09-28 approximation

Width is 1105–1110 bp in **all 24** divisor-phase cases, bracketing 1111.1 bp
in every one. It does not move with the divisor and it does not move with the
edge phase. The reason it cannot: the slow limit is `(1/2 + p)/9` and the
fast limit is `(1/2 - p)/9`, so `p` cancels out of the sum entirely. The
window has a **size that is a property of the frame format** and a **position
that is a property of the implementation**, and nothing about the
implementation touches the size.

And the size is one we already had. A lock-once-and-count observer has a
budget of `1/18` each way (2026-09-28, §4), hence a total width of `1/9`.
**The same number.** 09-28 measured 11.00% against 11.10% and wrote that the
observer's window is "wider"; they are **equal**, and the entire containment
failure is displacement. The claim "width is not containment" was right and
was weaker than the truth: here width is not even a *difference*.

## 3. P3 fails, and the centre's variable is not the divisor

Recovering `rho` in clk cycles from the measured centre gives
0.48, −0.49, −1.49, −0.40, −4.54, −4.48 at divisors 0, 1, 2, 3, 7, 15. A
negative detection latency is a detection that happens before the edge, so
the model is wrong, not merely imprecise. The centre is also not monotone in
the divisor: 102, 52, 35, 62, 30, 50 bp at edge phase 0.

The diagnosis is in A6. **The centre moves 50–53 bp with the edge phase, at
every divisor** — and that is the same magnitude as the entire divisor-driven
variation across the whole range measured (phase-averaged centre 112 bp at
div 0 falling to 41 bp at div 15). So a two-point comparison between div 0
and div 1 at an uncontrolled phase cannot separate a divisor effect from a
phase effect; the two confounds are the same size. The 2026-09-28 "+0.50%
centre shift between BAUD_DIV 0 and 1" is numerically indistinguishable from
the phase spread **at a single divisor**, which is why it was right to file it
as unsettled and why one more divisor would not have settled it either.

This also lands on the committed anchor. At div 0 on the 25 bp grid the four
edge phases give (650,450), (625,450), (675,400), (675,425). The committed
pair is reproduced **exactly at half an oversample tick and at no other
phase.** So slow 675 / fast 400 is not a property of the DUT; it is one
sample of a phase-dependent quantity, taken at a value of a variable nobody
was controlling. The anchor is recovered — but only by naming the variable.

## 4. The result: the pair window answered a per-byte question

F7 admissibility asks of **one byte**: can the adaptive observer arbitrate a
frame carrying this payload? So the window that has to be contained is the
DUT's window **for that byte**. The 2026-09-29 V4 check compared every byte's
observer limit against one pair-derived DUT window (slow 675 bp) instead.

A pair window is an **intersection** over its bytes. It is therefore never
wider than any member, so substituting it understates the DUT — and an
understated DUT window makes the observer look adequate when it is not. The
error is **fail-unsafe**, not merely imprecise, and it fires: in **16 of 24**
divisor-phase cases the pair window says 0x80 is contained and 0x80's own
window says it is not.

Asked per byte the arithmetic closes:

```
observer limit  = (1/2) / g_first      g_first = 1 + ctz(b)
                                       = position of the FIRST transition
DUT slow limit  = (1/2 + p) / span     span    = position of the LAST
                                         transition in [0, d0..d7, 1]

containment  <=>  span / g_first  >=  1 + 2p
```

The framed stream begins at 0 (start) and ends at 1 (stop), so **span >=
g_first always**, with equality **exactly** when the stream has a single
transition — and there containment requires `p <= 0`, which no receiver that
samples after an edge can deliver. There are nine such bytes:

| byte | g_first | span | observer | DUT slow (div 0) | ratio |
|---|---|---|---|---|---|
| 0x00 | 9 | 9 | 555 | 650 | 1.171 |
| 0x80 | 8 | 8 | 625 | 725 | 1.160 |
| 0xC0 | 7 | 7 | 714 | 825 | 1.155 |
| 0xE0 | 6 | 6 | 833 | 975 | 1.170 |
| 0xF0 | 5 | 5 | 1000 | 1175 | 1.175 |
| 0xF8 | 4 | 4 | 1250 | 1475 | 1.180 |
| 0xFC | 3 | 3 | 1666 | 1975 | 1.185 |
| 0xFE | 2 | 2 | 2500 | 2950 | 1.180 |
| 0xFF | 1 | 1 | 5000 | 5925 | 1.185 |

Every one is **INADMISSIBLE**, and the ratio is `1 + 2p` — constant to
within the 25 bp grid across a **tenfold** range of limits, which is the
single-parameter law tested nine times rather than asserted once. The four
multi-transition controls (0x40, 0x55, 0xAA, 0x01) all stay admissible.

**So the F7 admissible set is 247/256.** The 09-29 measurement is not
withdrawn: it is exactly right about the two bytes whose own DUT limit
happens to coincide with the pair window, which is why those two and no
others showed up. It was the comparison that was wrong, not the numbers.

**And 0x40 is next.** It is the multi-transition byte with the largest
`g_first` (7, with span 9), so it needs `p <= 1/7 = 0.1429`. The largest `p`
measured anywhere here is 0.1233, at div 0, phase 2 — **14% of margin.** A
receiver with slightly more sampling lateness than this one loses 0x40 too,
and then the ten-byte boundary is no longer a property of the frame format.

## 5. Mutation testing, and the harness becoming its own bug

Six mutants into a copy of the RTL: 4 detected, 2 escaped.

**M2 escapes and it is correct that it does.** Moving the `rx_edge` strobe
from 15 ticks to 14 changes **nothing** — 0 of 37 golden entries. Moving the
`rx_os` wrap from 15 to 14 (M6) changes **everything** — 37 of 37, including
the eps=0 exactness check. So the sample cadence is set by the counter's own
wrap and the `rx_edge` threshold is **redundant** with it for sampling: the
state machine's bit boundary can move two ticks without moving one sampling
instant. A mutation of one of two redundant encodings of the same constant is
invisible by construction, and the pair is the only way to find out which one
is load-bearing. **M4** escapes by design, stated in advance: no glitch
stimulus exists here.

**The finding is about the harness.** M3 was meant to bypass the RX
synchroniser. Its first build appended a marker comment and rerouted only the
read sites matching `rx_mid && rx_sync` — which does not include the
start-**detection** read `if (!rx_sync)`, the one place it was aimed. The
09-30 positive control read **PRESENT**, because the text had arrived. The
suite reported the baseline tally with 0 of 37 entries moved, and it was
filed as a weakness of the suite. **It was an inert mutant.**

So a second control was added: the text the mutation **replaces** must be
**absent** from the mutated source. It fails on the old M3 instantly — the
flop assignment was still there. Rebuilt as a real combinational bypass, M3
is detected and moves 20 of 37 entries, which also settles the physics: the
synchroniser is a genuine contributor to `p` and is **not** the whole of it,
the same verdict the unmutated P3 reaches from the other side.

## 6. The methodological note

- **09-24** the anchored comparison; **09-25** the independent driver;
  **09-26** a freshly produced anchor; **09-27** the independent observer;
  **09-28** independence is not sufficient — the observer's window must
  contain the one it arbitrates; **09-29** the qualifying observer's window
  is a function of the stimulus; **09-30** so the coverage model and the
  admissibility constraint can be unsatisfiable together.

- **10-01: A CONTAINMENT CLAIM IS A CLAIM ABOUT TWO SETS, AND AN AGGREGATE
  STANDS IN FOR NEITHER.** Every entry in this series has been about making
  the observer's window honest. None of them noticed that the *other* window
  in the comparison — the DUT's — was an aggregate: one pair-derived number
  used for all 256 bytes, while the observer's side was computed per byte.
  The two sides of a containment test were measured over different sets, and
  the mismatch is silent, because an aggregate window is a perfectly ordinary
  number that is simply the wrong one. It errs in one direction only:
  intersecting over bytes shrinks the DUT's window, which makes the observer
  look adequate. **An aggregate on the contained side of a containment claim
  is fail-unsafe by construction**, and no amount of care on the containing
  side can detect it.

  The interview form: *when you check that A contains B, say what B was
  measured over — and if it was measured over a set rather than the item
  you are adjudicating, you have checked a different claim, and the error
  has a known sign.*

- **The corollary, which is 09-30's inverted.** 09-30: the check most likely
  to be vacuous is the one whose passing you find reassuring. Today the three
  worst findings came from a check that **failed** — A2a, the anchor — and
  was, on first reading, obviously the new bench's fault. A failing anchor
  against a committed number is the easiest failure in the world to attribute
  to the new instrument. It was the old measurement that was underspecified.
