# Reset-value properties, the mirror-image guard, and a fourth way a property can mean nothing

**Date:** 2026-09-22 · **Phase 5, day 3** · UART CSR formal suite
**Code:** `rtl/uart_controller.v` (`` `ifdef FORMAL_CSR_RESET ``),
`examples/phase5_csr_formal/run_reset_formal.sh`, output
`reset_formal_run_output_2026-09-22.txt` (15/15)

---

## 1. The item, and why it was owed

2026-09-21 proved nine CSR properties and closed with an explicit debt: of
the seven reusable CSR obligations (reset value, write/read-back, reserved
bits, unmapped addresses, status decode, read-to-clear, interrupt masking),
**reset value was the one the suite did not check.** It was named as the
natural next item on three grounds — it is one of seven, it is cheap, and it
needs a guard that is the mirror image of the one everything else uses.

The third ground is the interesting one, and it turned out to be the whole
lesson.

## 2. Why the gap was structural, not an oversight

Every formal property in this repo — the 2026-09-20 FIFO invariants and the
2026-09-21 CSR properties alike — opens with

```verilog
if (f_past_valid && rst_n) begin ... end
```

This is the standard SymbiYosys idiom and it is right: a property about
steady-state behaviour has nothing to say while the design is being forced
to a known state, and without the guard the solver falsifies everything
from a mid-reset start state. But it means **the entire reset window is
excluded from every property in the suite**, and the reset-value obligation
is the one whose whole content lives inside that window.

A gap like this does not show up as a missing test. It shows up as a
uniformly-applied convention with a blind spot, which is harder to see,
because the convention is correct everywhere it was applied.

The fix is the mirror image:

```verilog
if (f_past_valid && !$past(rst_n)) begin ... end
```

### 2.1 Why `$past` is safe here and was not on 2026-09-21

Day 2's bug was a cover that reached **pre-reset state** through `$past()`:
the reset is synchronous, so step 0 precedes the first clock edge and every
register is the solver's free choice; `$past()` then returned a value the
design had already thrown away.

R1–R4 read `$past(rst_n)` — the **reset signal**, not state the reset
discards. `f_past_valid` guarantees an edge has elapsed, so `$past(rst_n)`
returns a value `rst_n` actually held. Reading the reset signal across the
reset boundary is the point of the property; reading *state* across it was
the bug. The two look identical in the source and are opposite in meaning,
which is worth saying out loud in a file a reviewer will read.

### 2.2 Synchronous reset changes the wording of the obligation

Written the obvious way — "whenever `rst_n` is low, the registers read their
reset values" — the property is about an **asynchronous** reset. This design
has a synchronous one, so the registers reach their reset values one edge
*after* `rst_n` is sampled low, and the obvious wording fails on correct RTL.
The guard above encodes the correct wording by construction.

## 3. The properties

| | claim | why it is separate |
|---|---|---|
| **R1** | 28 architectural registers hold their reset values | the internal view; the list was transcribed from the RTL's reset clauses, so a register added later without a property shows up as a diff |
| **R2** | the read port returns the reset values | what *software* sees. `prdata` is a combinational mux over `paddr`, so a decode fault can leave every register correctly reset and still return the wrong value — R1 cannot catch that |
| **R3** | `irq` is low out of reset | implied by R1, but it is the implication with an external consequence: a core asserting `irq` before software enables anything takes a spurious interrupt on every boot |
| **R4** | reset dominates a concurrent bus write | states an intent that is a one-line edit away from being wrong and invisible in a waveform unless a write happens to land in the reset window |

### 3.1 `STATUS` does not reset to zero

```
{1'b0, overrun_err, parity_err, frame_err, rx_avail, rx_full, tx_empty, tx_full}
= {0, 0, 0, 0, 0, 0, 1, 0} = 8'h02
```

because `tx_empty` is a live decode of `tx_cnt == 0`, which reset makes true.
"Registers reset to zero" is the default assumption and it is wrong here.
The constant was derived from the RTL's own concatenation rather than
assumed — day 2's third self-fulfilment shape, avoided by doing the
derivation in the comment where a reviewer can check it.

### 3.2 One register is deliberately out of scope, and the omission is proved

`ADDR_RX_DATA` reads `rx_fifo[rx_rptr]`, and the FIFO array has **no reset
clause**. That is a design decision, not a bug: eight bytes of storage are
unreadable through the protocol while `rx_cnt == 0`, so resetting them costs
area for nothing. Asserting a reset value there would assert something false.

Describing the omission as deliberate is cheap. **Mutant M7 corrupts exactly
that storage at reset and is required to SURVIVE** — so if R2 ever quietly
grows an `ADDR_RX_DATA` assertion, or the FIFO ever grows a reset path, the
suite fails and says which. Same discipline as day 2's N5.

## 4. Mutation: six detected

M1 CTRL not cleared · M2 TX line idles low out of reset · M3 a concurrent bus
write beats reset · M4 `tx_cnt` resets to 1 so `STATUS.tx_empty` is wrong ·
M5 `frame_err` resets *set* · M6 `irq` ignores its enable mask. All six
detected.

Each mutant is `cmp`'d against the original before it is run, and a `sed`
that matched nothing is a **FAIL**, not a silent pass. That guard exists
because of 2026-09-18's green regression that wasn't: a suite reporting
55/55 against deliberately broken RTL.

## 5. THE FINDING — a fourth way a passing property can mean nothing

Day 2's notes generalised to **three** shapes:

1. the antecedent is never satisfiable in the bounded window;
2. a cover is reached from a state the design cannot actually be in;
3. the property is the logic written twice.

**R4 fails none of the three.** Its antecedent is satisfiable — cover `C_R2`
exists for exactly that purpose and is reached at step 4. It is a true
statement about real behaviour. It is not a restatement of any RTL line.

Stage 5 of the runner measures it anyway, by deletion. Build one variant of
the RTL with R4 removed and one with *only* R4 kept, and run M3 — the defect
R4 was written for — against both:

```
noR4:   clean=PASS   with-M3=FAIL
onlyR4: clean=PASS   with-M3=FAIL
```

**Both detect it.** R1 asserts the reset values *unconditionally*, so the
concurrent-write case was already inside R1, and R4 contributes **no
detection power to this suite**. No mutant in the suite distinguishes them,
and no mutant can, unless R1 is narrowed.

### 5.1 Why this is a different shape from the other three

Vacuity is about whether a property is ever *evaluated*. Subsumption is about
whether, having been evaluated, it ever *changes a verdict*. All three
vacuity tests pass on R4 and all three are blind to this. **Only a deletion
experiment finds subsumption**, and a deletion experiment is not part of any
standard flow.

### 5.2 What was done about it

R4 is **kept and annotated in place**, not deleted — repo practice, and there
are two substantive reasons. It states an intent (reset has priority over the
bus) that R1 only implies, and a reader of the property list should be able
to see that the priority was considered rather than inferred. And it would
earn its detection power the moment R1 were narrowed to a quiet bus — which
is how a larger design has to write R1, because enumerating every register
unconditionally does not scale.

### 5.3 The transferable rule

> **A property earns its place by changing a verdict somewhere. If no mutant
> distinguishes it, say so in the file.**

Coverage of *properties* by *mutants* is the property-level analogue of code
coverage, and it costs one extra variant per property. It is also the first
technique in this repo that can tell you a suite is **larger than it needs to
be** — every previous one could only say it was smaller than it looked.

Interview framing, since that is what Phase 5 is for: "how do you know your
assertions are pulling their weight?" has a bad answer (count them), a
standard answer (mutation coverage of the suite as a whole), and a better one
(mutation coverage attributed to *individual* properties, by deletion).

## 6. Scope, stated rather than implied

* R1–R4 are checked by **BMC to depth 12**. Reset properties are shallow by
  construction — every one is decided on the edge after reset — so depth is
  not the binding constraint here that it was on day 2. No k-induction is
  needed and none is claimed.
* The reset window is checked for the **power-on** reset and for a reset that
  **returns** after the design has run (cover `C_R1`, reached at step 3). A
  reset asserted in the middle of an in-flight UART frame is **not** covered:
  reaching a frame takes ≈145 clocks, the same solver-budget boundary day 2
  hit from the register side and day 1 from the datapath side.
* The `` `ifdef FORMAL_CSR_RESET `` block is invisible to Icarus, and that is
  **checked, not asserted** — stage 1 re-runs the Phase 4 bench and requires
  60/60.
* Stage 4 re-runs the 2026-09-20 FIFO jobs and the 2026-09-21 CSR jobs
  unchanged. All four still pass, so the new block disturbed neither.

## 7. Cost

15 sby invocations plus the Icarus regression plus four redundancy variants;
the whole run completes in about 90 seconds on the WASM toolchain.
