# Phase 5, second milestone — formal properties on the UART register map

**Date:** 2026-09-21
**Target named by:** the 2026-09-20 session ("CSR properties on the six-register
map — the named next target. Short, shallow, exactly what BMC is good at").

Run it:

```bash
source tools/setup_formal.sh       # do NOT pipe this -- see tools/setup_formal.sh
source tools/setup_iverilog.sh     # stage 1 needs Icarus
bash examples/phase5_csr_formal/run_csr_formal.sh
```

Recorded output: `csr_formal_run_output_2026-09-21.txt` — **15 passed, 0 failed**.

---

## 1. Why CSR properties, and why they are a different exercise from 2026-09-20's

The FIFO invariants proved on 2026-09-20 are *unbounded* claims — "the count
never exceeds 8, on any trace of any length" — and needed k-induction. The CSR
properties are the opposite: every one is decided within two cycles. That makes
them the natural fit for BMC, and it makes them a different skill. What they
buy is not depth but **cross-coupling**: each one relates a part of the design
to a *different* part, so no single line of RTL can make one true by
construction.

The nine properties, classified honestly by how much they are worth:

| | property | class |
|---|---|---|
| C1 | write / read-back on CTRL, BAUD_DIV, INT_EN (5, 8 and 3 bits respectively) | cross-check |
| C2 | decode isolation — a register that *changed* must have been addressed | cross-check, **strongest here** |
| C3 | read mux and reserved bits | structural restatement |
| C4 | write-only (TX_DATA) and unmapped (0x6–0xF) reads return 0x00 | structural restatement |
| C5 | STATUS[3:0] track the FIFO flags exactly | cross-check |
| C6 | the three sticky error bits are read-to-clear | cross-check — **but see §4** |
| C7 | the error bits can only *rise* in a stop state | cross-check — **but see §4** |
| C8 | RX_DATA pop-on-read, and no pop when empty | cross-check |
| C9 | interrupt masking: `int_en == 0` implies `!irq` | cross-check |

C3 and C4 are labelled *structural restatement* because they say the same thing
the read mux says. A mutation of that mux is detected trivially — the property
and the logic are one sentence written twice. They are kept because they are the
register map's spec and because they fire on an address-decode change that
breaks several things at once, but they are the weakest class and are not
counted as evidence the design is right.

C2 is the one to point at. Stated in the contrapositive — *a register that
changed must have been addressed* — it covers "a write to STATUS must not
disturb anything", "a write to RX_DATA must not disturb anything" and "a write
to any of the ten unmapped addresses must not disturb anything" in one line
each, without enumerating sixteen addresses.

## 2. Separate define, so 2026-09-20 stays reproducible

The block is nested `` `ifdef FORMAL_CSR `` inside the existing `` `ifdef FORMAL ``.
The 2026-09-20 FIFO jobs pass `-DFORMAL` only and therefore see exactly the
source they saw then; **stage 4 re-runs all three of them and requires PASS**,
so that is checked rather than asserted. Stage 1 re-runs the Phase 4 60-check
Icarus regression for the same reason, one level down: the new block must be
invisible to simulation. It reported 60/60.

## 3. The bug this suite shipped with for exactly one run

The first version of the vacuity cover was

```verilog
always @(posedge clk)
    if (f_past_valid && rst_n)
        cover(f_csr_rd && paddr == ADDR_STATUS && $past(overrun_err));
```

and sby reported it **reached, at the earliest possible step**. That was too
fast to be true — setting `overrun_err` requires a complete serial frame — so
the witness trace was dumped and read instead of being believed:

```
t=0   f_past_valid=0  rst_n=0  overrun_err=1   <-- solver's free choice
t=10  f_past_valid=1  rst_n=1  overrun_err=0   <-- reset has now taken effect
                                paddr=0x1 psel=1 pwrite=0   (a STATUS read)
```

The design has a **synchronous** reset, so at step 0 — before the first clock
edge — the solver is free to pick `overrun_err = 1`. One cycle later the design
is properly reset and the bit is 0, but `$past()` **reaches back across the
reset boundary** and returns the value the design had already thrown away. The
cover fired on garbage.

This is worse than a mis-scored cover. The cover's entire job was to show that
C6 is not vacuous. It passed without the design ever setting an error bit, so it
certified its own uselessness — a green light that meant nothing.

**Scope of the bug:** assertions C1–C9 were *not* affected. Every one of them
that uses `$past` is already guarded by `$past(rst_n)`, so none can read across
the boundary. The covers were the only place the guard was missing, which is
exactly where it is easy to forget — a cover feels like a query, not an
obligation.

**The fix, and the guard against a repeat.** All covers are now guarded by
`f_past_valid && $past(f_past_valid) && rst_n && $past(rst_n)`, and the runner
parses the per-cover *"Reached cover statement in step N"* lines and **fails the
run if any cover is reached before step 2**. A cover reached that early is
reading pre-reset state by definition. The earliest now is step 3.

This is the **fifth** occurrence of the verdict-vs-checking defect class in this
repo (2026-09-17 checks that never ran; 09-18 a PASS line that ignored
UVM_ERRORs; 09-19 `make`'s exit code ignoring cocotb's FAIL; 09-20 `prove` mode's
third outcome) and the **second** caught before it produced a wrong number. The
specific lesson this one adds: *a PASS whose step number is implausible is a
finding*. sby told the truth — the cover really was reachable — and the
conclusion drawn from it was still wrong.

## 4. What is NOT established, measured rather than assumed

**C6 and C7 are vacuously true at the depth this runs at.** After reset the
three sticky error bits are 0, and the only path that sets one runs through the
RX engine completing a serial frame: a start bit plus eight data bits plus a
stop bit at sixteen oversample ticks each, ≈145 clocks even at the fastest legal
baud. `bmc` runs to depth 20. C6's antecedent is never satisfiable in that
window.

Rather than leave that as a suspicion, **stage 3b asserts it**. Mutant N5
disables the STATUS read-to-clear path entirely — precisely the defect C6 exists
to catch — and is *required to survive*. It does. A property suite that cannot
be broken by deleting the logic it is about is not testing that logic, and
saying so is worth more than a green line that implies otherwise.

`uart_csr_deep_cover.sby` is the attempt to reach the interesting state anyway:
it assumes the fastest legal baud (`baud_div == 0`) and covers `rx_state ==
RX_STOP1`, `frame_err`, and a STATUS read that follows a set `frame_err`, at
depth 170. **Measured cost on this toolchain: the WASM z3 build reached step 61
of 170 in 2 min 39 s before the session budget ran out.** That is a statement
about the solver budget, not about the design — the Phase 4 simulation
regression drives real frames and sets all three error bits every run. The job
is committed so the experiment is reproducible; it is not part of the default
run.

This is the same scope boundary 2026-09-20 drew around the serial datapath,
arrived at from the register side: **anything whose antecedent needs a complete
UART frame is out of reach for bounded model checking on this toolchain, and
belongs to simulation.** Knowing exactly where that line falls is the useful
output.

## 5. Mutation results

Seven defects, each injected into a *copy* of the RTL. Detection means `bmc`
returns FAIL with a reachable counterexample — never an exit code.

| mutant | defect | target | result |
|---|---|---|---|
| N1 | write decode aliases CTRL onto the STATUS address | C2 | detected |
| N2 | CTRL reserved bits read as 1 | C3 | detected |
| N3 | unmapped / write-only reads return 0xFF | C4 | detected |
| N4 | STATUS `tx_full`/`tx_empty` bits swapped | C5 | detected |
| N5 | STATUS read-to-clear disabled | C6 | **survives — by design, see §4** |
| N6 | RX_DATA read pops an empty FIFO | C8 | detected (and the FIFO suite's P1/P4) |
| N7 | TX-empty interrupt ignores its mask bit | C9 | detected |

N6 is worth a second look: it fails at line 433 (the 2026-09-20 FIFO property
P4) *and* line 608 (C8). Two independent suites catching the same defect from
different directions is the cheapest available evidence that neither is
self-fulfilling.

---

## Day 3 (2026-09-22): reset-value properties, and a property that does nothing

`run_reset_formal.sh`, `uart_reset_bmc.sby`, `uart_reset_cover.sby`, and the
`` `ifdef FORMAL_CSR_RESET `` block at the end of `rtl/uart_controller.v`.
Recorded output: `reset_formal_run_output_2026-09-22.txt` (15/15).

### The guard is the whole point

Day 2 (2026-09-21) proved nine CSR properties and then recorded an owed item:
of the seven reusable CSR obligations, "reads its reset value after reset"
was the one the suite did not check. The reason was structural rather than an
oversight. Every property in this repo is guarded by

```verilog
if (f_past_valid && rst_n)          // disabled DURING reset
```

which is correct for a steady-state property and is exactly what makes the
reset window unreachable. This obligation is the one whose entire content
lives inside the window every other property excludes, so it needs the
**mirror image**:

```verilog
if (f_past_valid && !$past(rst_n))  // sample the edge AFTER reset
```

`$past()` is safe here for the reason it was *not* safe on day 2. Day 2's bug
was reading **state** across a reset boundary — state the reset had since
discarded. Reading the **reset signal** across that boundary is the point of
the property. `f_past_valid` guarantees an edge has elapsed, so `$past()`
returns a value the design actually held.

The reset is **synchronous**, so the obligation is "one edge after `rst_n`
was sampled low, the register reads its reset value" — not "whenever `rst_n`
is low". The second form describes an asynchronous reset this design does not
have and would fail on correct RTL.

### The properties

| | what it says | scope |
|---|---|---|
| R1 | 28 architectural registers are at their reset values | internal |
| R2 | the read port returns the reset values (CTRL, STATUS, BAUD_DIV, INT_EN, TX_DATA) | observable |
| R3 | `irq` is low out of reset | external |
| R4 | reset dominates a concurrent bus write | intent |

**`STATUS` resets to `8'h02`, not `8'h00`.** Its bit 1 is `tx_empty`, a live
decode of `tx_cnt == 0`, which reset makes true. A reader who assumed
"registers reset to zero" would write `8'h00` and the property would be wrong
while the design was right. The constant was derived from the RTL's own
concatenation, not assumed — the third self-fulfilment shape from day 2.

**`ADDR_RX_DATA` is deliberately absent from R2.** It reads
`rx_fifo[rx_rptr]`, and the FIFO array has no reset clause: resetting eight
bytes of storage costs area for no benefit when `rx_cnt == 0` makes them
unreadable through the protocol. Asserting a value there would assert
something false. **Mutant M7 corrupts exactly that storage at reset and is
REQUIRED TO SURVIVE**, so the omission is demonstrated to be deliberate
rather than described as deliberate.

### Mutation: six detected, one required to survive

M1 CTRL not cleared · M2 TX line idles low · M3 a concurrent write beats
reset · M4 `tx_cnt` resets to 1 (so `STATUS.tx_empty` is wrong) · M5
`frame_err` resets set · M6 `irq` ignores its enable mask. All six detected.
Every mutant is checked with `cmp` against the original first, so a `sed`
that matches nothing is a FAIL rather than a silent pass — the shape of the
2026-09-18 green-regression-that-wasn't.

### The finding: R4 is redundant, and that is a fourth failure mode

Day 2's notes list **three** ways a passing property can mean nothing:
antecedent never satisfied, cover reached from an unreachable state, and
property = the logic written twice. R4 fails none of those three. Its
antecedent is satisfiable (cover `C_R2`, reached at step 4), it is a true
statement about real behaviour, and it is not a restatement of the RTL.

Stage 5 measures it anyway, by deletion: build one variant with R4 removed
and one with *only* R4 kept, and run M3 — the defect R4 was written for —
against both.

```
noR4:   clean=PASS  with-M3=FAIL
onlyR4: clean=PASS  with-M3=FAIL
```

**Both detect it.** R1 asserts the reset values unconditionally, so the
concurrent-write case was already inside it, and R4 contributes no detection
power to this suite.

This is **subsumption**, a fourth failure mode, and the three vacuity tests
are all blind to it. Only a deletion experiment finds it. R4 is kept and
annotated in place rather than deleted: it states an intent — that reset has
priority over the bus — that R1 only implies, and it would earn its power the
moment R1 were narrowed to a quiet bus, which is how a larger design would
have to write R1.

The transferable rule: **a property earns its place by changing a verdict
somewhere. If no mutant distinguishes it, say so in the file.** Coverage of
properties by mutants is the property-level analogue of code coverage, and it
is cheap: one extra variant per property.
