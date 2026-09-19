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
| F3 RX data path | CRV (loopback) + directed (sampling-margin corners) |
| F4 Parity | CRV (common cases) + 2 directed (mode-switch, corrupted parity) |
| F5 TX FIFO | CRV + 1 directed (write-while-full) |
| F6 RX FIFO/overrun | Directed (overrun sequence) |
| F7 Baud rate | Directed (corner divisor values) |
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
