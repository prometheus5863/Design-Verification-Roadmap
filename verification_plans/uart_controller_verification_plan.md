# Verification Plan: UART Controller with Register Interface

**Status:** **v2, revised 2026-09-19.** Originally a Phase 3 milestone
deliverable (2026-09-05, v1), written spec-first before any RTL existed.
Phase 4 has since produced the RTL, a UVM environment and a register
model, and this revision folds back what they found. Written as the spec
this repo's Phase 4 UVM testbench is built against, and as an early
draft of the Phase 6 capstone's verification plan sub-item (the README
already names "a UART or SPI controller wrapped with a register interface"
as the concrete capstone DUT). No RTL exists for this DUT yet in this repo
-- this plan is deliberately written spec-first, per the planning
methodology in `notes/2026-09-05-verification-planning-and-stimulus-
strategy-tradeoffs.md`, Section 1, before any testbench (or DUT) code.

## Revision history

| Version | Date | Change |
|---|---|---|
| v1 | 2026-09-05 | Initial spec-first plan, Phase 3 milestone |
| **v2** | **2026-09-19** | **STATUS re-specified.** v1's blanket "Live status" wording is **wrong for the three error bits** and could not have been implemented as written. Three independent Phase 4 findings forced it: (a) the RTL bring-up (2026-09-17) could not make a live-status error bit observable through a register read at all, since the condition is gone by the time software reads it; (b) the UVM environment's read-to-clear check (2026-09-18) showed that checking such a bit *sets* is not checking it, because one read per run cannot distinguish "never clears" from "correctly re-set"; (c) the register model (2026-09-19) cannot express the two halves of STATUS in one `uvm_reg` access policy — the live bits are RO+volatile, the error bits are RC. Also adds the RX_DATA read-side-effect note and its consequence for generic register sequences. **v1's text is annotated in place below, not deleted.** |
| **v3** | **2026-09-25** | **F7 re-specified, and four further corrections absorbed.** v1 assigned F7 to *directed* testing of the TX bit period, and that plan is not wrong so much as **unable to reach the thing F7 is about**: every bench in this repo until today ran in loopback, where the TX and RX engines share one baud generator, so a wrong divisor desynchronises nothing and the baud tolerance is infinite. F7's tolerance number, flagged open since v1 ("to be finalized once RTL exists"), could not be produced by any bench the plan described. It is now **measured** — see 2.7 below — and the strategy changes to a driven-pin receiver on an **independent timebase**. Also absorbed: (i) v2's STATUS correction, already in place; (ii) **reset values were unspecified** (2026-09-22); (iii) **C6/C7's behaviour was assigned to formal where formal provably cannot reach it** (2026-09-23); (iv) **Section 3's CRV assignment is satisfiable for the register interface and the loopback datapath but NOT for F7**, for the structural reason above (2026-09-24). **No v1 or v2 text is deleted; every change is annotated in place.** |
| **v4** | **2026-09-26** | **The F7 coverage bins v3 specified are the wrong bins, and the pre-pass v3 demanded is not sufficient on its own.** v3's coverage consequence asked for bins on {0, within ±2%, within ±4%, beyond the measured limit}. Built and measured (`examples/phase6_baud_error_coverage/`), those four bands **do not partition the baud error** — for 8N1 the slow limit is +6.25%, so +5% is outside "within ±4%" and inside the limit and belongs to no band; a **fifth band** is required. The absolute edges also **disagree with the DUT** (7 of 12 probe rows classify differently under 4.00% than under the per-configuration measured limit), and **"beyond the limit ⇒ an error" is false and data-dependent**, so it is neither a bin nor an assertion. Separately, v3 inherited 09-24's rule "check a bin is reachable before putting it in a closure criterion" — and a reachability pre-pass turned into illegal bins **fired against correct RTL** 21 frames into a random run. Sign-off therefore distinguishes **excluded by argument** from **not reached**, and only the former is asserted. **No v1–v3 text is deleted; every change is annotated in place.** |

Template structure and the features -> checks -> coverage -> tests
philosophy follow ChipVerify's seven-section vplan template and the
OpenHW Group CORE-V-VERIF project's planning guide (both cited in the
notes file above); the strategy assigned to each feature below (directed /
constrained-random / coverage-driven, or a mix) follows the trade-off
discussion in that same notes file, Section 2.

---

## 1. Design overview and scope

**DUT:** a memory-mapped UART (Universal Asynchronous Receiver/
Transmitter) controller: one 8-bit-data serial transceiver, TX and RX
FIFOs, and a synchronous register interface (APB-lite style: address,
write-data, read-data, write-enable, read-enable, ready -- consistent with
this roadmap's Phase 6 note that the capstone is "an APB-lite peripheral").

**Block-level interfaces:**
- Register bus: `paddr[3:0]`, `pwdata[7:0]`, `prdata[7:0]`, `pwrite`,
  `psel`, `penable`, `pready` (APB-lite subset; no wait states in v1 scope
  -- `pready` tied high, see Section 1.2).
- Serial lines: `tx` (output), `rx` (input).
- `irq` (output, level, active-high).
- Clock/reset: `clk`, `rst_n` (synchronous, active-low).

**Register map** (byte-addressed, 4-bit address space is intentionally
generous for v1's 6 registers):

| Addr | Name | R/W | Bits | Description |
|---|---|---|---|---|
| 0x0 | CTRL | R/W | `[0]` en, `[2:1]` parity_mode (00=none,01=even,10=odd), `[3]` stop_bits (0=1,1=2), `[4]` loopback_en | Enable/config |
| 0x1 | STATUS | RO | **live (RO, volatile):** `[0]` tx_full, `[1]` tx_empty, `[2]` rx_full, `[3]` rx_avail &nbsp;&nbsp; **sticky (read-to-clear):** `[4]` frame_err, `[5]` parity_err, `[6]` overrun_err | **v2:** two halves, not one. ~~Live status (Section 2.3)~~ — see Section 1.1 |
| 0x2 | BAUD_DIV | R/W | `[7:0]` divisor | Baud-rate divisor (clk/(16*(div+1)), standard 16x-oversample UART convention) |
| 0x3 | TX_DATA | WO | `[7:0]` | Write pushes one byte into the TX FIFO (no-op + `overrun_err`-style drop if full -- Section 2.5) |
| 0x4 | RX_DATA | RO | `[7:0]` | Read pops one byte from the RX FIFO (returns stale/undefined data if empty, per `rx_avail` in STATUS -- feature 2.6). **v2:** this read has a side effect on state outside the register, which no `uvm_reg` access policy can express — see Section 1.2 |
| 0x5 | INT_EN | R/W | `[0]` tx_empty_en, `[1]` rx_avail_en, `[2]` err_en | Interrupt mask |

### 1.1 STATUS is two registers wearing one address (v2, 2026-09-19)

v1 described all seven STATUS bits as "live status". For bits `[3:0]`
that is right: tx_full, tx_empty, rx_full and rx_avail are combinational
functions of FIFO occupancy, and reading them twice in a row legitimately
gives different answers.

**For bits `[6:4]` it is not implementable.** frame_err, parity_err and
overrun_err report *events*, not conditions. A framing error exists for
the duration of one stop bit. If the bit were live, it would be clear
again long before any software or testbench could read it, and the plan's
own checks — "`STATUS.parity_err` is set exactly when a received frame's
parity bit disagrees…" (Section 2.4), "`STATUS.overrun_err` is set when a
new fully-received byte arrives while the RX FIFO is already full"
(Section 2.6) — would be unobservable through a register read. They are
therefore **sticky: set by the event, cleared by a STATUS read** (the
classic 16550 LSR behaviour), which is what `rtl/uart_controller.v`
implements.

Consequences that are now requirements, not notes:

- **Any check on an error bit must account for the read that clears it.**
  Reading STATUS is destructive. A check that reads STATUS to see whether
  frame_err is set has, by doing so, cleared it for every later check in
  the same run.
- **Checking that an error bit SETS is not checking it.** A single read
  per run cannot distinguish a bit that never clears from one correctly
  re-set by the next event. The check must read STATUS **twice**: the
  first read verifies the bit is set, the second verifies the first read
  cleared it. (Mutation testing found this: a mutant deleting the
  read-to-clear logic survived a suite that only checked the set.)
- **The two halves need different modelling.** In a UVM register model
  the live bits are `RO` + volatile and the error bits are `RC`. UVM does
  not *compare* volatile fields, so a generic `uvm_reg_hw_reset_seq`
  sweep over STATUS silently checks nothing — STATUS's reset value
  (0x02: tx_empty set, all else clear) must be checked explicitly.

### 1.2 RX_DATA's read has a side effect the register layer cannot express (v2)

Reading RX_DATA pops the RX FIFO. No `uvm_reg` access policy describes
"this read mutates a queue elsewhere in the design". A register model can
describe the byte-wide read port and nothing more.

Requirement: **RX_DATA must be excluded from generic register sequences**
(`NO_REG_TESTS`), because a hw-reset sweep or a bit-bash over it is
silently consuming received bytes that another check is waiting for. The
FIFO behaviour belongs to F6's checks, not to the register layer. TX_DATA
is excluded for the milder reason that it is write-only, so a generic
read-compare is meaningless.

**FIFOs:** TX and RX FIFOs are each 8 entries deep, 8 bits wide
(synchronous, same clock domain as the register bus and the UART core --
v1 scope has no clock-domain-crossing; CDC is explicitly out of scope,
Section 1.2, and deferred to the Phase 6 roadmap topic of the same name).

**Frame format:** 1 start bit, 8 data bits (LSB first), optional parity
bit (per CTRL.parity_mode), 1 or 2 stop bits (per CTRL.stop_bits) -- a
fixed 8-data-bit width is an explicit scope reduction (Section 1.2).

### 1.2 Explicit scope reductions (out of scope for v1)

Stated up front, per ChipVerify's template guidance that a vplan should
say what is *not* verified as clearly as what is:

- Configurable data-bit width (5/6/7/9 bits) -- fixed at 8 for v1.
- `pready`-based APB wait states / back-pressure on the register bus.
- Clock-domain crossing between the register-bus clock and a
  UART-line clock -- single clock domain assumed for v1 (CDC is its own
  named Phase 6 README topic, deliberately deferred rather than folded in
  here).
- Hardware flow control (RTS/CTS).
- Break/idle-line detection.

These are candidates for a v2 plan revision once the Phase 4 UVM
environment for v1 exists (see Section 7).

---

## 2. Features to be verified

Each feature gets an ID (`F<n>`), a priority (P0 = must-work-for-any-
regression-to-mean-anything, P1 = important, P2 = edge case/nice-to-have),
and a strategy assignment per the Section 2 trade-off notes.

### 2.1 Register access (F1) -- P0

Every register in Section 1's map is readable/writable per its R/W column;
writes to read-only bits/registers are ignored without side effects;
reads from write-only `TX_DATA` return an implementation-defined value
(not a hang or protocol error).

- **Checks:** a register-access scoreboard comparing every observed
  `(addr, pwrite, data)` transaction against an internal reference-model
  copy of each register's expected value/access-type.
- **Coverage:** a `cp_addr` coverpoint (all 6 defined addresses + at least
  one undefined address, to confirm graceful non-hang behavior) crossed
  with `cp_rw` (read/write).
- **Strategy:** constrained-random (address x read/write is a small,
  fully enumerable space -- CRV with a coverage-driven stop closes this
  fast, no directed tests needed for the happy path). One directed test
  for the "write to read-only STATUS bits" corner (F1.1 below), since
  that specific illegal-write scenario is unlikely to be hit reliably by
  uniform random addressing alone within a reasonable transaction count.

### 2.2 TX data path (F2) -- P0

A byte written to `TX_DATA` is serialized onto `tx` as: start bit (0),
8 data bits LSB-first, parity bit if enabled (Section 2.4), 1 or 2 stop
bits (1), at the programmed baud rate (Section 2.7), with `tx` idle-high
between frames.

- **Checks:** a reference bit-stream generator (independent of the DUT,
  built from CTRL/BAUD_DIV register values) compared bit-for-bit against
  a `tx`-line monitor's sampled sequence.
- **Coverage:** `cp_parity_mode` (none/even/odd) x `cp_stop_bits` (1/2) x
  `cp_data_pattern` (all-zeros, all-ones, alternating, one specific
  "typical ASCII" value -- corner-value bins, not exhaustive 256-value
  enumeration, per the CORE-V ADDI example's "minimal sufficient
  coverage" philosophy in the notes file).
- **Strategy:** constrained-random data bytes (uniform + weighted toward
  the corner bins above) with a coverage-driven stop on the
  parity/stop-bits/data-pattern cross; loopback mode (CTRL.loopback_en,
  F2.1) reused as the easiest path to close this without needing a
  separate RX-side reference model yet.

### 2.3 RX data path (F3) -- P0

A serial byte received on `rx` (start bit, 8 data bits LSB-first, parity
if enabled, stop bit(s)) is correctly deserialized into the RX FIFO,
sampled at the mid-bit point per the 16x-oversample baud convention
(BAUD_DIV, Section 1), with `STATUS.rx_avail` set once a byte is queued.

- **Checks:** scoreboard comparing FIFO-popped bytes (via `RX_DATA` reads)
  against the known-good bytes that were serially driven onto `rx` by the
  testbench's RX-side bit driver.
- **Coverage:** same `cp_parity_mode` x `cp_stop_bits` x `cp_data_pattern`
  cross as F2, on the receive side; an additional `cp_rx_timing`
  coverpoint for mid-bit vs. near-edge sampling-margin stress (drive
  transitions slightly early/late relative to the nominal bit period, to
  exercise the oversample sampling logic's timing margin, not just its
  nominal-timing correctness).
- **Strategy:** constrained-random serial byte streams via loopback
  (F2.1) once TX is trusted (F2 closes first, since loopback makes RX
  testing depend on a working TX path); a small number of directed tests
  for the sampling-margin corners in `cp_rx_timing`, since precisely-timed
  near-edge transitions are exactly the kind of exact scenario random
  stimulus rarely produces on its own (Section 2's directed-testing
  strength, per the notes file).

### 2.4 Parity generation and checking (F4) -- P0

TX-side: correct even/odd parity bit computed and appended when enabled;
no parity bit sent when `parity_mode=00`. RX-side: `STATUS.parity_err` is
set exactly when a received frame's parity bit disagrees with the
even/odd parity of the received data bits, and is *not* set when
`parity_mode=00` regardless of the incoming bit stream.

> **v2 amendment (2026-09-19).** `STATUS.parity_err` is **sticky,
> read-to-clear** (Section 1.1), so "is set" must be read as "is set, and
> is cleared by the read that observed it". The check below must read
> STATUS **twice** per provoked error: once to see the bit set, once to
> see it cleared. A check that only reads once passes against RTL whose
> read-to-clear logic has been deleted.

- **Checks:** an independent parity-reference function (even/odd parity
  of the transmitted/received data byte) compared against both the
  transmitted parity bit (TX) and `STATUS.parity_err` (RX).
- **Coverage:** this is ChipVerify's own worked UART-parity coverage
  example, reused directly (Source 2 in the notes file): a `cp_parity`
  coverpoint with even/odd/none bins, plus a specific "mid-stream mode
  switch" bin (change `CTRL.parity_mode` between consecutive frames) --
  reproduced here because it is exactly this DUT's own parity feature,
  not adapted from a different protocol.
- **Strategy:** constrained-random for the even/odd/none bins (reached
  quickly via F2/F3's own random data); one directed test specifically
  for the mid-stream mode-switch bin and one directed negative test that
  deliberately corrupts a parity bit at the RX-side bit-driver level (not
  reachable via TX-loopback, since a correctly-functioning TX never sends
  bad parity -- this is the plan's first feature that *requires* a
  standalone RX bit-driver independent of loopback, flagged as a
  testbench-architecture dependency for Phase 4).

### 2.5 TX FIFO management (F5) -- P1

`STATUS.tx_full`/`tx_empty` accurately reflect FIFO occupancy; a write to
`TX_DATA` while `tx_full` does not corrupt the FIFO (defined behavior:
drop the incoming byte, optionally flaggable via a future overrun-style
bit -- v1 scope: silently dropped, explicitly not silently *corrupting*
existing entries, which is the actual safety property being checked).

- **Checks:** a FIFO reference model (a simple queue) mirrored against
  every push/pop, checked for entry-for-entry agreement plus the
  full-write-is-a-safe-no-op property above.
- **Coverage:** `cp_tx_fifo_level` (empty, 1 entry, full-minus-one, full)
  crossed with `cp_tx_write_while_full` (boolean).
- **Strategy:** constrained-random for general fill/drain patterns
  (burst-write-then-drain, single-byte trickle) with a coverage-driven
  stop on the level coverpoint; one directed test for the exact
  write-while-full boundary condition (P1, not P0, since it's a safety/
  no-corruption property rather than a core data-path feature, but still
  concrete enough to specify precisely rather than hope random hits it).

### 2.6 RX FIFO management and overrun (F6) -- P1

Same FIFO-level coverage as F5, plus: `STATUS.overrun_err` is set when a
new fully-received byte arrives while the RX FIFO is already full (the
incoming byte is dropped, not silently overwriting the oldest entry)
— **v2: sticky and read-to-clear, so the same two-read rule as F4
applies (Section 1.1)**;
`RX_DATA` reads while `rx_avail=0` do not crash/hang the register
interface (returns an implementation-defined value, per Section 1's
register map note).

- **Checks:** FIFO reference model as F5; a dedicated overrun check that
  a byte fully received while `rx_full` is asserted results in
  `overrun_err` set and the FIFO's *existing* contents unchanged (an
  ordering/no-corruption property, same shape as F5's write-while-full
  check).
- **Coverage:** `cp_rx_fifo_level` (as F5) x `cp_overrun_event` (boolean).
- **Strategy:** overrun is a genuine corner case unlikely to occur under
  generic random traffic (requires sustained RX faster than the testbench
  drains `RX_DATA`) -- assigned **directed test**, deliberately
  constructing the fill-then-overrun sequence, per the notes file's
  guidance that directed tests are the right tool for a small number of
  known-important exact scenarios rather than hoping CRV stumbles into
  them.

### 2.7 Baud-rate generation (F7) -- P1

The internal bit-rate clock derived from `BAUD_DIV` matches the
documented `clk/(16*(div+1))` relationship (Section 1) across the full
8-bit divisor range, including the `div=0` (fastest) boundary.

- **Checks:** measured TX bit period (from the `tx`-line monitor's
  edge timestamps) compared against the expected period computed from
  `BAUD_DIV` and the testbench's known `clk` period, within a stated
  tolerance (to be finalized once RTL exists and any internal rounding
  behavior is known -- flagged as an open item, Section 6).
- **Coverage:** `cp_baud_div` with corner bins (0, 1, mid-range, 255) --
  not all 256 values, per the same "minimal sufficient coverage"
  reasoning as F2's data-pattern coverpoint.
- **Strategy:** directed (a handful of specific divisor values, since the
  feature is a simple, fully-deterministic arithmetic relationship best
  checked exactly at chosen corners rather than swept randomly).

#### 2.7 annotated (v3, 2026-09-25): F7 as written could not be reached, and the number is now measured

**What was wrong with the plan, not with the RTL.** The check above measures
the **TX** bit period against arithmetic. That is a check on the baud
*generator*, and it is worth having, but F7's engineering content is the
**receiver's tolerance to a transmitter running at a different rate** — the
number a system integrator actually needs. v1 flagged that number as "to be
finalized once RTL exists"; it stayed open for twenty days because **no bench
the plan described could produce it.** Every UART bench in this repo ran in
loopback, where `CTRL.loopback_en` routes `tx` internally back to the receiver
and both engines share one baud generator. A wrong divisor moves both sides
together, so the data is perfect and the tolerance is infinite. The 2026-09-24
mutation test demonstrated this rather than argued it: the mutant *"BAUD_DIV
ignored by the baud generator"* **escaped** a 60-check self-checking suite, and
escaped it for a structural reason.

**Revised strategy (supersedes "directed (corner divisor values)"):** F7 needs
a **driven-pin receiver test with an independent timebase** — a driver holding
its own bit period, reading nothing from the DUT's clock, baud counter or
oversample tick. The v1 TX-period check is retained as a separate, weaker
check; it is necessary and it is not sufficient.

**The measured number** (`examples/phase6_rx_pin_driver/`, 2026-09-25):

| config | fast transmitter | slow transmitter | binding sample |
|---|---|---|---|
| 8N1 | −4.50% | +6.25% | data bit 7 / stop 1 |
| 8N2 | −4.50% | +6.25% | data bit 7 / stop 2 |
| 8E1 | −4.05% | +5.60% | parity bit / stop 1 |
| 8O1 | −4.05% | +5.60% | parity bit / stop 1 |

**Three things about that table the plan must now say, because each one changes
how a sign-off criterion should be written:**

1. **The tolerance is ASYMMETRIC, and not by accident.** Drifting *late* off a
   stop bit is harmless, because the line idles high and a late sample of idle
   still reads 1; drifting *early* off the final stop bit lands in a data bit
   that may be 0. So the fast limit is set by the last sample carrying a
   *value* and the slow limit by the last *stop* bit. A criterion of the form
   "±X%" mis-states the design by assuming a symmetry it does not have.
2. **Parity costs tolerance.** Adding a parity bit pushes the last checked
   sample one bit further from the resync point, tightening the limit from
   6.25%/4.50% to 5.60%/4.05%. So F7's acceptance number is **per frame
   format**, not one number for the block. A second stop bit, by contrast,
   costs nothing measurable.
3. **The limit is a BAND, not a number.** The arrival edge's phase against the
   DUT's free-running 16× oversample counter is uncontrolled and quantises the
   effective sample point in 1/16-bit steps, one of which is 0.69% of the baud
   error. Quoting F7 to two decimal places would be spurious precision. **The
   defensible sign-off statement is: better than ±4.0% in every configuration
   measured, asymmetric, tighter with parity than without.**

**Coverage consequence.** `cp_baud_div`'s corner bins check the divisor
*register*, not the tolerance. F7 needs a coverpoint on the **baud error** of
the driven stimulus — at minimum bins for {0, within ±2%, within ±4%, beyond
the measured limit} — and that coverpoint is unreachable without the
independent-timebase driver, which is the same structural point as above
appearing in Section 5.

> **v4 annotation (2026-09-26): the bins above are the wrong bins, and this
> is measured rather than argued.** The coverpoint was built
> (`examples/phase6_baud_error_coverage/uart_baud_cov_tb.v`, 3 seeds, 11
> checks, 0 errors) and the specified band set fails three ways.
>
> 1. **It does not partition the baud error.** 8N1's slow limit is +6.25%, so
>    eps = +5% is outside "within ±4%" and inside the limit — it belongs to
>    none of the four bands. A closure criterion over a non-partition reports
>    every bin hit while never sampling that region. A **fifth band,
>    4% < |eps| ≤ the measured limit**, is required, and it took 19 of the 28
>    frames of the steered closure run.
> 2. **The absolute edges are a claim the DUT does not honour.** Of twelve
>    probe rows across the four configurations, **seven** are classified
>    differently by the 4.00% edge and by the per-configuration measured
>    limit. An absolute bin edge on a tolerance is a scale assumption.
> 3. **A measured bin edge is a claim about the measuring stimulus.** Swapping
>    two of the six trial bytes — `0x3C`/`0x81` for `0x01`/`0x80`, same
>    trial-set size, same DUT, same sweep — moved 8O1's fast limit by
>    **0.50% of eps, in the optimistic direction**, because `0x01` and `0x80`
>    put a lone 1 adjacent to the start and stop bits, exactly where a
>    drifting sample lands on a differing neighbour. The BEYOND band's edge
>    inherits that optimism.
>
> **The outcome axis matters more than the band axis.** The cross of five
> bands with three outcomes (clean / error bit set / byte lost or wrong) has
> **15 cells, of which only 8 are reachable** by well-formed frames: every
> inside-the-limit band is clean by construction. A cross whose axes are
> causally linked is mostly illegal bins rather than coverage.
>
> **What must NOT be written into sign-off:** "beyond the measured limit ⇒ an
> error". It is false and data-dependent — past every measured limit, a frame
> whose drifting bit lands on an *identical* neighbour is received cleanly,
> which 09-25's own T1b staircase already showed (8/8 frames failed with
> `data[7]=0`, 0/8 with `data[7]=1`). It is not a bin and not an assertion.
>
> **The corrected coverage requirement for F7** is therefore: five bands over
> the driven baud error (zero / |eps| ≤ 2% / 2% < |eps| ≤ 4% / 4% < |eps| ≤
> the per-configuration measured limit / beyond it), crossed with the
> three-valued outcome, with **the closure criterion over the reachable cells
> only** and the two cells excluded *by argument* (an exactly-nominal
> well-formed frame cannot lose a bit or miss its stop bit) carried as illegal
> bins. Closure requires **coverage-driven steering**: pure random stimulus
> did not close in 250 frames, because the error outcome in the fifth band
> lives in the last few basis points below the limit.

> **v4 annotation (2026-09-26): "check a bin is reachable first" is not
> sufficient as stated, and this cost a false failure.** 09-24's finding 9,
> which v3 inherited, says to establish a bin is reachable before putting it
> in a closure criterion. Implemented as a directed pre-pass with two verdicts
> — reachable if the pre-pass produced the cell, unreachable otherwise, and
> every unreachable cell an illegal bin — **an illegal bin fired against
> correct RTL 21 frames into the random run** (band 3 × byte-lost, from an eps
> of −4.71% on 8O1 with a data pattern and edge phase the pre-pass had not
> tried). A pre-pass answers *"did my attempts reach it"*, which is not *"is
> it reachable"*.
>
> Sign-off therefore uses **three** verdicts, and only the second is asserted:
>
> | verdict | basis | goes into |
> |---|---|---|
> | REACHED | the pre-pass produced it | the closure criterion |
> | EXCLUDED | an **argument** about the mechanism, checked but not based on the attempts | an illegal bin / assertion |
> | OPEN | not reached, not ruled out | neither — recorded as unknown |
>
> "Unreachable" is also never a property of a bin alone but of a bin *and a
> stimulus space*: `eps == 0 × frame error` is excluded for well-formed frames
> and trivially reachable once the stop bit may be corrupted, which the bench
> demonstrates deliberately. **A coverage report that does not name its
> stimulus space cannot say what an unhit bin means.**

**Also now reachable, and therefore now assignable in Section 3:** framing
errors, parity errors, and the start-bit glitch filter are all driven at the
pin in that bench. In loopback the DUT's own transmitter never emits a bad stop
bit, wrong parity, or a runt pulse, so F4's corrupted-parity check and F3's
sampling-margin corners were being asserted against stimulus that could not
produce them.

### 2.8 Interrupt generation (F8) -- P0

`irq` asserts if and only if at least one unmasked (`INT_EN`) condition
among {tx_empty, rx_avail, any of frame/parity/overrun err} is currently
true; masking a condition via `INT_EN` deasserts its contribution to
`irq` without affecting the underlying `STATUS` bit.

- **Checks:** a combinational reference model of `irq` as a function of
  live `STATUS` and `INT_EN` register values, compared every cycle
  against the DUT's actual `irq` output.
- **Coverage:** `cp_int_source` (tx_empty/rx_avail/frame_err/parity_err/
  overrun_err, one bin per source) crossed with `cp_int_masked`
  (enabled/masked), confirming every source has been observed both
  driving and *not* driving `irq` (the masked case).
- **Strategy:** largely free/automatic once F2-F7's stimulus is running
  (the `irq` reference-model check runs continuously in the background as
  a scoreboard on every other feature's traffic -- a coverage-driven
  regression closes the `cp_int_source x cp_int_masked` cross without
  dedicated interrupt-only tests, except one directed test that
  deliberately masks every source simultaneously to confirm `irq` is held
  deasserted even while multiple underlying `STATUS` conditions are true).

### 2.9 Loopback mode (F9) -- P1

`CTRL.loopback_en=1` internally routes `tx` to `rx` (external `rx` pin
ignored while enabled), with no other feature's behavior otherwise
changed -- verified as a foundational *testbench-enabling* feature
(Section 2.2-2.3 depend on it) as well as a feature in its own right.

- **Checks:** confirm F2 (TX)/F3 (RX) checks all pass identically whether
  driven via loopback or via an independent bit-level RX driver, for a
  representative stimulus subset -- loopback is not trusted blindly just
  because it's convenient for other features' tests.
- **Coverage:** `cp_loopback` (enabled/disabled) crossed with a subset of
  F2's `cp_parity_mode`/`cp_stop_bits` bins (not the full cross again --
  reusing F2/F3's already-planned coverage, per Section 1's "minimal
  sufficient" philosophy, rather than doubling the whole matrix).
- **Strategy:** constrained-random (reuses F2/F3's stimulus generation
  with `loopback_en` as an additional randomized field).

---

## 3. Verification methodology summary

Per-feature strategy assignments (Section 2) are summarized here for a
quick regression-planning view:

| Feature | Strategy |
|---|---|
| F1 Register access | CRV + 1 directed (illegal write) |
| F2 TX data path | CRV (loopback-based) |
| F3 RX data path | CRV (loopback) + directed (sampling-margin corners) — **v3: the sampling-margin corners are only reachable at the pin; in loopback the DUT's own transmitter cannot produce them** |
| F4 Parity | CRV (common cases) + 2 directed (mode-switch, corrupted parity) — **v3: "corrupted parity" is unreachable in loopback; now driven at the pin** |
| F5 TX FIFO | CRV + 1 directed (write-while-full) |
| F6 RX FIFO/overrun | Directed (overrun sequence) |
| F7 Baud rate | ~~Directed (corner divisor values)~~ → **driven-pin receiver on an independent timebase** (v3, 2026-09-25; the directed TX-period check is retained as a necessary but insufficient companion — see 2.7 annotated) |
| F7 Baud rate — coverage | ~~`cp_baud_div` corner bins~~ → ~~{0, ±2%, ±4%, beyond the limit}~~ → **five bands over the driven baud error × three-valued outcome, closure over the reachable cells only, coverage-driven steering required** (v4, 2026-09-26 — the four-band set does not partition the domain and its absolute edges disagree with the measured limit; see 2.7 v4 annotations) |
| F8 Interrupt | CDV (background scoreboard) + 1 directed (all-masked) |
| F9 Loopback | CRV |

This mirrors the hybrid approach recommended in the trade-off notes
(Section 2 there): the bulk of state-space exploration (F1-F3, F5, F8,
F9) is assigned to constrained-random/coverage-driven stimulus, while a
deliberately small number of directed tests (F3's timing margin, F4's two
corners, F6 in full, F7 in full, F8's all-masked case -- 7 directed tests
total across the whole plan) target scenarios that are either exact
corner conditions or require sequencing unlikely to occur under generic
random traffic within a practical simulation budget.

Architecturally, this plan assumes the layered testbench structure
already covered conceptually in Phase 3 (`notes/2026-08-31-layered-
testbench-architecture-and-tlm-basics.md`): a register-bus driver/monitor,
a serial-line driver/monitor (for the standalone RX bit-driver F4
requires), a reference-model scoreboard per Section 2's per-feature
checks, and a functional-coverage collector subscribing to the same
monitors -- to be implemented as an actual UVM environment in Phase 4,
per this repo's already-logged conclusion (2026-08-25, reconfirmed
2026-08-31) that a real UVM environment needs a different simulator than
the pinned Icarus 10.3 build used for Phases 1-3's hand-workaround
examples.

---

## 4. Test list

| Test name | Feature(s) | Type | Priority |
|---|---|---|---|
| `test_reg_access_crv` | F1 | Random | P0 |
| `test_reg_illegal_write` | F1.1 | Directed | P0 |
| `test_tx_loopback_crv` | F2, F9 | Random | P0 |
| `test_rx_loopback_crv` | F3, F9 | Random | P0 |
| `test_rx_sampling_margin` | F3 | Directed | P1 |
| `test_parity_crv` | F4 | Random | P0 |
| `test_parity_mode_switch` | F4 | Directed | P1 |
| `test_parity_corrupted_rx` | F4 | Directed | P0 |
| `test_tx_fifo_crv` | F5 | Random | P1 |
| `test_tx_fifo_write_while_full` | F5 | Directed | P1 |
| `test_rx_fifo_overrun` | F6 | Directed | P1 |
| `test_baud_div_corners` | F7 | Directed | P1 |
| `test_interrupt_all_masked` | F8 | Directed | P0 |
| `test_full_regression_cdv` | F1-F3, F5, F8, F9 | Coverage-driven random | P0 |

`test_full_regression_cdv` is the long-running background regression that
closes most of Section 2's coverage crosses; the other CRV-typed tests
above are shorter, feature-focused seeds used for bring-up and fast
iteration before the full regression is trusted to run unattended.

---

## 5. Coverage plan

**Functional coverage** (the `cp_*` coverpoints/crosses defined per-feature
in Section 2) is the primary closure metric, tied directly to Section 2's
feature list per this plan's stated philosophy (a feature without mapped
coverage is not actually verified). Target: 100% of all defined bins
across F1-F9's coverpoints/crosses before Phase 4 sign-off (Section 6).

**Code coverage** (line/branch/toggle/FSM-state, once RTL exists): target
95%, consistent with ChipVerify's cited typical range -- deliberately not
100%, since some structural code (defensive/unreachable error-handling
branches) is expected and should be reviewed by inspection rather than
forced into a contrived coverage-hitting test.

---

## 6. Sign-off criteria

1. All P0 tests in Section 4 pass with zero scoreboard/checker errors.
2. All P1 tests pass, or any failure is triaged and explicitly waived
   with a written reason (not silently skipped).
3. 100% functional coverage on all Section 2 coverpoints/crosses (or an
   explicitly justified/waived exception, e.g. a bin later found to be
   unreachable given the actual RTL's implementation).
4. Zero known open P0/P1 bugs.
5. Baud-rate tolerance (F7) finalized against actual RTL behavior --
   currently an open item (Section 2.7) since no RTL exists yet to
   measure real rounding/timing behavior against.

---

## 7. Resource and status notes

> **v2 status (2026-09-19).** Most of what follows is now history. The
> RTL exists (`rtl/uart_controller.v`, 2026-09-17), the toolchain question
> was resolved (uvm-python/cocotb on Icarus 10.3, 2026-09-06), the Phase 4
> UVM milestone environment is built and mutation-tested
> (`examples/phase4_uvm_milestone/`, 2026-09-18), and a register model with
> the built-in hw-reset and bit-bash sequences exists
> (`examples/phase4_ral/`, 2026-09-19). Still not built from this plan:
> constrained-random and coverage-driven stimulus (Section 3 assigns most
> features to CRV; today's tests are directed), code coverage (Section 5
> targets 95%; Icarus has no native support), and F7's baud-tolerance
> number. The paragraph below is kept as written because its last sentence
> — that the plan would need revising once bring-up surfaced details the
> spec-first pass could not anticipate — is exactly what happened, twice.

This plan is a Phase 3 deliverable, written before any UART RTL or
testbench code exists in this repo. Phase 4 (UVM, not yet started) is
where this plan's per-feature strategy assignments (Section 3) and test
list (Section 4) become actual UVM sequences/tests, and where the DUT
RTL itself will need to be written (or sourced) for the first time --
both flagged as Phase 4 dependencies, not oversights in this plan. Given
this repo's already-documented Icarus-10.3-cannot-host-real-UVM finding,
Phase 4 bring-up will also need to resolve that toolchain question before
any of this plan's tests can actually be coded and run.

This plan is expected to be revised once real RTL/bring-up experience
surfaces details this spec-first pass could not anticipate (exact
`overrun_err`/FIFO-full corner behavior, the F7 baud-tolerance number,
possibly new features/registers) -- consistent with CORE-V-VERIF's own
guidance (notes file, Source 1) that a vplan is a living, reviewed
document tracked alongside the project's actual status, not a one-time
artifact.
