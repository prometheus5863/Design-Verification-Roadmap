# CSR formal verification, and the two ways a bounded proof can mean nothing

**Date:** 2026-09-21 · **Phase 5, day 2** · DUT: `rtl/uart_controller.v`
**Companion artefacts:** `examples/phase5_csr_formal/` (suite, runner, recorded
output), `notes/2026-09-20-sva-and-formal-bounded-vs-unbounded.md` (day 1).

---

## 1. Why the register map is the right second formal target

Day 1 proved FIFO invariants by **k-induction** — unbounded claims about traces
of any length. The register map is the opposite shape and that is the point of
doing it second rather than more of the same:

| | FIFO invariants (day 1) | CSR properties (day 2) |
|---|---|---|
| claim | holds on every trace of **any** length | decided within **two** cycles |
| engine that suits it | `prove` (temporal induction) | `bmc` |
| what makes it hard | finding a strengthening invariant | nothing — it is cheap |
| what makes it **valuable** | depth | **cross-coupling** |
| failure mode to fear | not k-inductive → UNKNOWN | **vacuity** |

The last row is the substance of this session. A shallow property is easy to
prove and easy to prove *for the wrong reason*, and both of this session's
findings are instances of that.

CSR checking is also the single most reusable thing in this phase for
interviews: every SoC has a register map, every register map has the same seven
obligations (reset value, read-back, reserved bits, RO/WO protection, decode
isolation, side-effect-on-access, and clear semantics), and the same seven
properties transfer verbatim to the next block.

## 2. The seven obligations, and how each becomes a property

Written as they apply to this DUT's six registers (CTRL, STATUS, BAUD_DIV,
TX_DATA, RX_DATA, INT_EN at 0x0–0x5, with 0x6–0xF unmapped).

**(a) Read-back.** After a write to a RW register, a read returns what was
written — *masked to the implemented width*. This DUT is a good example of why
the width matters: CTRL takes `pwdata[4:0]`, INT_EN takes `pwdata[2:0]`,
BAUD_DIV takes all eight. A property that checks `ctrl == $past(pwdata)` would
be wrong, and one that checks only `ctrl[0]` would miss a truncation bug.

**(b) Reserved bits read as zero.** The complement of (a): the bits the design
does *not* implement must not read back as anything else. CTRL reads
`{3'b000, ctrl}`, INT_EN reads `{5'b00000, int_en}`, STATUS bit 7 is reserved.

**(c) Write-only and unmapped reads are defined.** TX_DATA is write-only;
0x6–0xF are unmapped. The verification plan's Section 2.1 requires such a read
to return a defined value and not hang. Both return 0x00.

**(d) Decode isolation — the important one.** Writing address A must change
register A *and nothing else*. The naive form enumerates address pairs and is
O(n²). The **contrapositive** form is O(n) and stronger:

```verilog
if (ctrl != $past(ctrl))
    assert($past(wr_en) && $past(paddr) == ADDR_CTRL);
```

*A register that changed must have been addressed.* One line per register covers
every "a write to STATUS / to RX_DATA / to any unmapped address must not disturb
anything" requirement at once, and it keeps covering them if someone adds a
seventh register tomorrow. This is the shape worth memorising.

**(e) Live fields track their source.** STATUS[3:0] are combinational views of
the FIFO occupancy. The property relates the read mux to the FIFO counters —
two different parts of the design — so it cannot be satisfied by construction.

**(f) Access side effects.** Reading RX_DATA pops the FIFO; reading STATUS
clears the sticky error bits. These are the properties that catch the classic
bugs, and both halves matter: *reading when non-empty must pop* and *reading
when empty must not*. The second is the underflow bug.

**(g) Masking.** `int_en == 0` implies `!irq`. Note the phrasing: asserting the
full boolean expression for `irq` would be the RTL's `assign` written twice and
would prove nothing. Asserting that a fully masked controller is *silent* is a
claim about behaviour.

## 3. Finding 1 — `$past()` reaches back across a synchronous reset

The vacuity cover for the read-to-clear property was

```verilog
always @(posedge clk)
    if (f_past_valid && rst_n)
        cover(f_csr_rd && paddr == ADDR_STATUS && $past(overrun_err));
```

and sby reported it **reached at the earliest possible step**. Setting
`overrun_err` requires a complete serial frame, so that was not credible, and
the witness trace was dumped and read:

```
step 0   f_past_valid=0   rst_n=0   overrun_err=1     <- solver's free choice
step 1   f_past_valid=1   rst_n=1   overrun_err=0     <- reset has taken effect
                          paddr=0x1, psel=1, pwrite=0  (a STATUS read)
```

**The mechanism.** The design has a *synchronous* reset. Step 0 is before the
first clock edge, so the solver may choose any value for any register; the
standard `assume(!rst_n)` while `!f_past_valid` correctly forces the design into
reset at the first edge, but it cannot un-choose step 0's values. `$past()` is a
register holding the previous cycle's value — and at step 1 that previous cycle
is the pre-reset one. The cover fired on a value the design had already thrown
away.

**Why it is worse than a mis-scored cover.** That cover existed to prove the
read-to-clear property was not vacuous. It passed without the design ever
setting an error bit. A check whose only job is to detect a false sense of
security, providing a false sense of security, is a strictly worse outcome than
not having written it.

**Scope, checked rather than assumed.** Assertions C1–C9 are unaffected: every
one using `$past` is guarded by `$past(rst_n)`, which disables it across the
boundary. Only the covers lacked the guard — and that asymmetry is the
transferable lesson. *A cover feels like a query and an assertion feels like an
obligation, so the reset guard gets written on assertions and forgotten on
covers.* It is the same guard and it is needed for the same reason.

**The fix, plus a check that it stays fixed.** All covers now carry
`&& $past(rst_n)`, and the runner parses sby's per-cover "Reached cover statement
in step N" lines and **fails the run if any cover is reached before step 2**,
because a cover reached that early is reading pre-reset state by definition.

**Defect class, fifth occurrence.** 09-17 checks that never ran; 09-18 a PASS
line that ignored UVM_ERRORs; 09-19 `make`'s exit code ignoring cocotb's FAIL;
09-20 `prove` mode's third outcome; today, a cover reached for the wrong reason.
Second one caught before it produced a wrong number. The new sub-lesson: **a
PASS whose *step number* is implausible is a finding.** sby told the truth — the
cover genuinely was reachable — and the conclusion drawn from it was wrong
anyway. The tool was not the problem; the reading of it was.

## 4. Finding 2 — two of the nine properties are vacuously true, and it is measured

`bmc` runs to depth 20. After reset the three sticky error bits are 0, and the
only path that sets one runs through the RX engine completing a serial frame:
start bit + eight data bits + stop bit at sixteen oversample ticks each,
**≈145 clocks even at `baud_div = 0`**, the fastest legal baud. So the antecedent
of the read-to-clear property (C6) and of the error-rise property (C7) is never
satisfiable inside the bounded window. Both are **vacuously true**.

The temptation is to leave the green line alone. Instead, stage 3b **asserts the
vacuity**: mutant N5 disables the STATUS read-to-clear path entirely — exactly
the defect C6 exists to catch — and the runner *requires it to survive*. It does.

This is what turns a suspicion into a measurement, and it is worth the trouble
because the two statements sound identical in a report and are not:

* "C6 is proved." — implies the read-to-clear path is verified.
* "C6 is proved over traces reachable in 20 cycles, and it is measured that
  those traces never set an error bit, so deleting the clear path does not break
  it." — implies the read-to-clear path is **not** verified here, and says where
  it must be verified instead.

The second is the true one, and the Phase 4 simulation regression is where that
path actually gets exercised: it drives real frames and sets all three bits
every run.

**The attempt to close it honestly.** `uart_csr_deep_cover.sby` assumes
`baud_div == 0` and covers `rx_state == RX_STOP1`, `frame_err`, and a STATUS
read following a set `frame_err`, at depth 170. Measured on this toolchain: the
WASM z3 build reached **step 61 of 170 in 2 min 39 s** and did not finish inside
the session budget; a second run with one assumption removed was slower still,
stalling around step 18. The job is committed for reproducibility and is not
part of the default run.

**The resulting scope statement** matches day 1's from the other side. Day 1 put
the serial datapath out of formal scope because its properties span many bit
periods. Day 2 reaches the same boundary from the register side: **any property
whose antecedent requires a complete UART frame is out of reach for bounded
model checking on this toolchain and belongs to simulation.** Knowing precisely
where that line falls — and which of one's own properties are on the wrong side
of it — is the useful output, and it is not something a PASS/FAIL summary says.

## 5. Vacuity, generalised — the part that transfers

Three distinct ways a passing property can mean nothing, all seen in this repo:

1. **Antecedent never satisfied** (today, C6/C7). `A |-> B` where `A` is
   unreachable in the bounded window. *Detection:* cover `A` — and check the
   cover is reached for the right reason and at a credible step.
2. **Cover reached from unreachable state** (today, finding 1). The cover fires,
   but on a state the design cannot actually be in — pre-reset garbage,
   or an induction start state. *Detection:* read the witness trace. There is no
   substitute; no summary line contains this information.
3. **Property is the logic written twice** (C3, C4 here, labelled as such). It
   passes because it is a copy of the implementation, and fails only when that
   implementation is mutated — which proves the copy is faithful, not that
   either is correct. *Detection:* ask which *other* part of the design the
   property constrains. If the answer is "none", it is a restatement.

A fourth, not applicable here but worth carrying: **over-constrained
assumptions**. `assume()` that excludes real behaviour makes everything pass.
The deep-cover job's `assume(baud_div == 0)` is exactly this shape, which is why
it lives in its own job and its own `ifdef` rather than in the main suite.

## 6. What Phase 5 still owes

* **A property needing a strengthening invariant.** Day 1's stage 4 found P2
  inductive alone; today's properties are all shallow, so the technique remains
  studied and unexercised. Still the phase's clearest gap.
* **The SVA sequence layer** (`##`, `[*]`, `|->`, local variables) — runnable on
  neither Icarus 10.3 nor Yosys 0.69. Today's properties are again in the
  immediate-assertion-on-a-clock-edge style.
* **`abc pdr` as a second engine** — would give a solver-independent check, and
  is the obvious candidate for the deep-cover job that smtbmc cannot finish.
* **Reset-value properties.** The seven obligations in §2 include "reset value",
  and this suite does not check it: the `f_past_valid` idiom disables everything
  during reset, so the reset values themselves go unasserted. A separate job
  with the opposite guard would close it — noted for the next session.
