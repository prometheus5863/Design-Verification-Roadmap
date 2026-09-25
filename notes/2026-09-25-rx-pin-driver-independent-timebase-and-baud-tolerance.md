# Driving the RX pin from an independent timebase: F7 measured, and what a loopback bench structurally cannot see

**2026-09-25.** Closes the top item of the 2026-09-24 list — *"constrained-random
stimulus driven at the RX PIN, from an independent timebase"* — and with it the
standalone RX bit-driver item open since the Phase 4 milestone, and the
long-open *"F7's baud-tolerance number, never measured in any bench"*.

Code: `examples/phase6_rx_pin_driver/uart_rx_pin_tb.v` (888 lines),
`run_rx_pin.sh`, `run_mutation_tests.sh`. Recorded output:
`uart_rx_pin_sim_output_2026-09-25.txt` (3 seeds, 93 checks, 0 errors),
`mutation_test_report_2026-09-25.txt` (7 injected, 7 detected). Plan revision:
`verification_plans/uart_controller_verification_plan.md` v3.

---

## 1. The structural argument, which is the reason this directory exists

Every UART bench in this repo — the Phase 4 bring-up, the UVM environment, the
RAL work, the formal properties, the Phase 6 CRV suite — has driven the DUT in
**loopback**, where `CTRL.loopback_en` routes `tx` internally back to the
receiver. That was a reasonable choice: loopback gives a closed self-checking
path with no external model.

It also makes one whole class of defect **unreachable in principle**. In
loopback the TX and RX engines share one baud generator, so a wrong `BAUD_DIV`
moves both sides together: the transmitter is wrong, the receiver is wrong in
exactly the same way, and the data is perfect. On 2026-09-24 the mutation test
injected precisely that defect and it **escaped a 60-check self-checking
suite** — not because the suite was weak, but because no amount of stimulus
sophistication reaches a fault the harness topology cancels.

That is worth stating as a general principle, because it is easy to mistake for
a coverage gap: **a shared resource between stimulus and checker cancels exactly
the faults that live in it.** The loopback mux shares the baud generator, so
baud faults cancel. More constraints, more coverage bins, more seeds — none of
them help. The only fix is a second, independent timebase.

## 2. What "independent" means concretely

The driver holds its own bit period as a real, `drv_bit_ns`, and toggles the
`rx` pin on its own schedule. It reads nothing from the DUT: not its clock, not
`baud_cnt`, not `os_tick`. `drv_bit_ns` is the DUT's nominal bit period scaled
by `(1 + eps)`, and `eps` is swept. Loopback is **off** for every test in the
file.

## 3. F7, measured

| config | fast transmitter (`eps<0`) | slow transmitter (`eps>0`) | binding sample |
|---|---|---|---|
| 8N1 | −4.50% | +6.25% | data bit 7 / stop 1 |
| 8N2 | −4.50% | +6.25% | data bit 7 / stop 2 |
| 8E1 | −4.05% | +5.60% | parity bit / stop 1 |
| 8O1 | −4.05% | +5.60% | parity bit / stop 1 |

Three properties of that table matter more than the numbers.

**It is asymmetric, and not by accident.** Drifting *late* off a stop bit is
harmless, because the line idles high and a late sample of idle still reads 1.
Drifting *early* off the final stop bit lands in a data bit, which may be 0. So
the fast limit is set by the last sample carrying a **value** and the slow limit
by the last **stop** bit. A specification of the form "±X%" asserts a symmetry
this design does not have.

**Parity costs tolerance.** A parity bit pushes the last checked sample one bit
further from the resync point: 6.25/4.50 becomes 5.60/4.05. F7's acceptance
number is therefore **per frame format**. A second stop bit, by contrast, costs
nothing measurable — predicted as a null result (P3) and held.

**It is a band, not a number.** The arrival edge's phase against the DUT's
free-running 16× oversample counter is uncontrolled, and quantises the effective
sample point in 1/16-bit steps, one of which is 0.69% of the baud error —
fourteen steps of the 0.05% sweep grid. **The sweep resolution is finer than the
phenomenon it measures.** The defensible statement is *better than ±4.0% in every
configuration measured, asymmetric, tighter with parity than without*.

## 4. The RTL comment was the spec I predicted from, and it is wrong

Predictions P1–P5 were pre-registered in the testbench header, derived from the
RTL's own comment: *"16x oversample, sample at mid-bit (os position 8)"*, i.e.
0.5000 of a bit period. A four-line hierarchical probe on `dut.rx_mid` measures
where the samples actually land:

```
8N1   n=10  first sample at 0.6250 bit, last at 9.6250 bit, spacing exactly 1 bit
8E1   n=11  first sample at 0.5938 bit, last at 10.5938 bit
```

Late by up to **two oversample ticks**, because `rx_os` starts counting at the
first `os_tick` *after* edge detection and `rx_sync` adds a clock. So **P1 and P4
fail**, and they fail because the comment is not the design. Both are left in the
file and scored FAIL; the interesting content is not that a prediction was wrong
but *what it was derived from*. This is this repo's standing verdict-vs-checking
finding one level up: **a comment is an unverified assertion, and predicting from
one is predicting from documentation.**

P3 is worth a line too. It **failed on the first run and passed on the second**,
and nothing about the DUT changed: at the 0.2% sweep grid the first run used, 8N2
read 0.2% tighter than 8N1 — one grid step — and the null prediction scored a
spurious FAIL. At 0.05% the two are identical. **A measurement grid coarser than
the effect under test manufactures differences**, which is the same lesson the
graphene repo recorded on the same day about a finite-difference step, arrived at
from the opposite direction.

## 5. Two independent routes to the same number

With the sample point measured, the tolerance follows from arithmetic with no
free parameters: sample `i` sits at `(i + off)` bit periods and driver bit `i`
spans `[i, i+1]·(1+eps)`, so early drift out of bit `i` needs `eps ≤ off/i` and
late drift into bit `i+1` needs `eps ≥ −(1 − off)/(i+1)`. Three corrections earn
their place, each measured rather than assumed:

1. **`off` is the offset of the line VALUE, not of the sample.** `rx_sync` delays
   it one clk = 1/32 bit here = **0.35% of eps** at `i = 9`. Without that term the
   derived slow limit is 6.60% against a swept 6.25%; with it they agree.
2. **The binding `i` differs by direction** — Section 3's asymmetry, in the
   arithmetic.
3. **`off` is quantised by edge phase** — Section 3's band.

The bench checks the swept result against the derived band and it passes. Two
routes to one number, one empirical and one structural, is a stronger statement
than either alone; and it is what makes the mutation results in Section 7 sharp,
because a mutant that moves the sample point breaks the agreement.

One more thing that bound derivation taught, and it is the same lesson as the
graphene repo's that day: the lower edge of the band was first written as the
literal `0.5625`. Under the mutant that moves the sample point, the band
**inverted** (lo > hi) and the failure message became nonsense. A hardcoded
bound is a claim about this RTL. It is now derived as one oversample tick below
the measured value.

## 6. Two exact results, one of them unpredicted

**T1b — past the slow limit the failure is exactly "data bit 7 is 0".** The stop
sample lands in driver bit 8, which carries data bit 7, so at `eps = +6.80%`:
`frame_err` on **8 of 8** bytes with `data[7] = 0` and **0 of 8** with
`data[7] = 1`, data intact in both. An exactly known outcome, not a plausible
range.

**T1c — the degradation staircase, unpredicted, and found by T1b's first version
failing.** T1b first used `eps = +7.50%`, which is past `off/8` as well as
`off/9`, so data bit 7 was mis-sampled too and every byte came back with bit 7
replaced by bit 6 — the test failed while its headline prediction passed. The
frame does not "stop working" at a threshold; it **fails one sample at a time,
from the last backwards**, at `off/9`, `off/8`, `off/7`, …, each failed sample
reading its predecessor's value:

| eps | received | corrupt data bits | predicted |
|---|---|---|---|
| 6.80% | `aa` | 0 | 0 |
| 7.70% | `2a` | 1 | 1 |
| 8.70% | `6a` | 2 | 2 |
| 10.50% | `4a` | 3 | 3 |
| 12.50% | `5a` | 4 | 4 |

Exact at all five points, with the thresholds coming from T0's measured offset
and nothing else. This is the clearest example so far in this repo of a *failure
mode* specified as precisely as a pass criterion, and it exists only because a
test that failed was read rather than adjusted.

## 7. Mutation test: 7 injected, 7 detected, 0 escaped

| mutant | verdict | first failure |
|---|---|---|
| M1 `BAUD_DIV` ignored — **the 2026-09-24 loopback escape** | **detected** | 59 errors; T0 sample count 12, expected 10 |
| M2 RX samples at os position 7 | detected | T1b data corrupt past the slow limit |
| M3 stop-bit check removed | detected | swept slow tolerance outside the derived band |
| M4 parity polarity swapped | detected | CRV frame lost at `eps = 0` |
| M5 glitch filter removed | detected | runt pulse queues a byte |
| M6 overrun overwrites instead of dropping | detected | `rx_full` not set with 8 queued |
| M7 `rx_sync` bypassed | detected | swept slow tolerance outside the derived band |

**M1 is the row this directory exists for**, and it is caught loudly. M3 and M7
are worth noting because they are caught by the **derived-band cross-check** and
by nothing else in the suite: a stop-bit check that never fires widens the
measured tolerance beyond what the measured sample point permits, and removing
the synchroniser shifts the sample point without shifting the tolerance with it.
**A cross-check between two independent routes catches the class of defect that
moves one route and not the other** — which no single-route suite, however
thorough, can do.

The harness voids any row whose `sed` matched nothing, since unmodified RTL
scoring as an escape is the same false verdict the mutation test exists to
prevent, one level up — 2026-09-24's guard, carried forward.

## 8. Two bugs in this bench, recorded rather than fixed quietly

Both are this repo's standing failure classes appearing on the **stimulus** side,
which is new: the six previous occurrences were about checkers, and 2026-09-24's
pair were about measurement.

**(a) `$random` is signed.** The CRV generator computed
`($random % (2m+1)) - m`, and `$random`'s result is *signed*, so the remainder
can be negative and `eps` reached **−7.2% under a 2.4% constraint**. Seven of
twenty frames failed and the bench blamed the DUT. A generator that silently
exceeds its own constraint is verdict-vs-checking in the stimulus: the constraint
was documented, asserted nowhere, and wrong. The fix is `{$random(seed)}`, one
brace pair — and the general form is that **a constraint worth writing in a
comment is worth a runtime check.**

**(b) A stimulus value that cannot show the effect being counted.** T1c first
used `0x2A` as the probe byte, whose bits 7 and 6 are both 0 — so the
`bit7 ← bit6` substitution changed nothing and the staircase read one step low at
every point. This is the exact twin of 2026-09-24's *unreachable coverage bin*,
on the other side of the testbench: there, a covergroup could not observe a real
behaviour; here, a stimulus value could not exhibit one. `0xAA` is the only
usable shape, because every adjacent bit pair must differ.

## 9. What is newly reachable

All of these were unreachable in loopback, because the DUT's own transmitter
never emits a bad stop bit, wrong parity, or a runt pulse:

* **framing errors** (T3), including the read-to-clear behaviour of the sticky
  bit;
* **parity errors, both polarities** (T4), with the correct-parity case checked
  alongside so the test cannot pass by flagging everything;
* **RX overrun deterministically** (T5), with the eight queued bytes verified
  *intact* — the RTL drops the new byte rather than overwriting, and M6 shows the
  check discriminates;
* **the start-bit glitch filter** (T6), plus a check that the receiver is still
  alive afterwards.

The plan had assigned F3's "sampling-margin corners" and F4's "corrupted parity"
to loopback stimulus all along. That is corrected in v3.

## 10. Left open

* **A coverpoint on the driven baud ERROR** — created today by the v3 revision.
  `cp_baud_div`'s corner bins measure the divisor *register*, not the tolerance;
  F7 needs bins on `{0, within ±2%, within ±4%, beyond the limit}` and a closure
  criterion over them. The stimulus now exists; the coverage model does not.
* **Fold this driver into the Phase 4 UVM environment as a real `uvm_driver`** —
  the serial agent there has an RX bit-driver that runs at the DUT's rate. An
  independent-timebase driver is a different component, and it would make the UVM
  environment able to reach what this bench reaches.
* **Two transmitters at once** — the asymmetry in Section 3 means a link's
  tolerance is the *intersection* of two one-sided budgets, which is how a real
  clock-accuracy specification is written (±2% at each end, not ±4% total).
  Nothing here measures a link, only a receiver.
* **`abc pdr` as a second engine** — unchanged since 09-23 and still the best
  single experiment available.
* **Per-property coverage of the Phase 4 UVM environment** — open since 09-23.
* **A mutation script for `examples/phase4_uvm_milestone/`** — open since 09-19;
  today's script is a template that could be adapted directly.
* **Widen the Phase 6 coverage model** and **a less greedy steering policy** —
  both created 09-24, untouched.
* **Mutants not yet attempted**: interrupt *enable* combinations, the loopback
  mux itself, reset asserted mid-frame.
* **Code coverage measurement** — Icarus has none; open since 09-18.
* **The SVA sequence layer** — runnable on neither tool here; open since 09-20.
