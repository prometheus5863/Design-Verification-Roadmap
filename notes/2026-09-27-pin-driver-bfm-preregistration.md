# 2026-09-27 — Pre-registration: extracting the RX pin driver into one shared BFM and giving the Phase 4 UVM environment an independent timebase

Written and committed **before any of the code it describes exists**, continuing
the practice this repository adopted on 2026-09-21 and the graphene repo adopted
the same week. The point is that a prediction which can be quietly edited after
the measurement is not a prediction. Everything below is scored in
`AUTOMATION_LOG.md` at the end of the session, including — especially — the
items that turn out wrong.

## The item being closed

From the 2026-09-26 "Not yet covered" list, verbatim:

> **Fold the independent-timebase driver into the Phase 4 UVM environment as a
> real `uvm_driver`** — open since 09-25 and now the clear top item. Today
> promotes it from nice-to-have to **prerequisite**: the pin driver is
> duplicated **verbatim** in two directories, deliberately (so a difference in
> results cannot be a difference in the driver), and that reasoning does not
> survive a third copy.

Two things are therefore in scope, in this order:

1. **The prerequisite.** One shared pin-driver BFM, used by every bench that
   drives the `rx` pin, replacing the duplicated in-file `drive_frame` task.
2. **The item.** The Phase 4 UVM `UartSerialDriver` reworked to program that
   BFM, so the UVM environment gains a timebase independent of the DUT's.

## Why the Phase 4 driver needs this at all

`examples/phase4_uvm_milestone/uart_uvm_tb.py`'s `UartSerialDriver` advances one
bit by `for _ in range(BIT_CYCLES): await RisingEdge(dut.clk)`. Its timebase
**is** the DUT's clock. Two consequences, and the second is the one that
matters:

- It cannot express a baud mismatch, so the UVM environment structurally cannot
  do the tolerance work `phase6_rx_pin_driver` and `phase6_baud_error_coverage`
  do.
- Every frame the UVM environment has **ever** driven has had its bit edges
  exactly on DUT clock edges, with zero edge-phase variation. The receiver's
  oversampling and mid-bit re-check logic has never been exercised off-grid by
  this environment. A clean 69-check regression at 100% functional coverage says
  nothing about that, which is itself an instance of 09-26 item 8: coverage
  records what the stimulus reached.

## Design under test of *this* session

`bfm/uart_rx_pin_bfm.v` — one module, controlled entirely through ports so that
Verilog and cocotb/Python can drive the same source:

- `bit_ps` (32-bit integer): the bit period in picoseconds, and the BFM's
  **only** timebase. Deliberately an integer in ps, not a `real` in ns: a `real`
  module port is a portability hazard in Icarus and is not reliably writable
  from cocotb, and under `` `timescale 1ns/1ps `` a `#(real_ns)` delay is
  already quantised to ps — so integer ps should be the *same* number, which
  Q1 below turns into a measurement rather than an assumption.
- `phase_ps`: delay inserted before the start bit, the initial edge phase.
- `data`, `par`, `two_stop`, `bad_stop`, `bad_par`, and a runt-pulse mode.
- `go` / `busy` handshake, so any language can drive it.

## Questions

- **Q1 — Is the extraction a pure refactor at picosecond resolution?**
  Prediction: **yes, exactly** — every `rx` transition timestamp identical
  between the BFM and a verbatim copy of the old task, over every trial, with
  zero tolerance allowed. Reason: both round the same product `BIT_NS_NOM *
  (1+eps)` to ps. Risk I am naming in advance: the old code rounds *once per
  bit* from a `real`, and if I compute `bit_ps` by rounding first and then
  delaying, ten bits accumulate ten identically-rounded delays either way — but
  if the old path happens to accumulate in `real` time rather than per-bit, the
  two diverge by up to 10 ps over a frame. I predict per-bit rounding and exact
  agreement; a 1–10 ps divergence would falsify this and would be a real
  finding about refactoring a timebase.

- **Q2 — Do the 09-25 measured tolerance limits move when the two phase6
  benches switch to the shared BFM?** Prediction: **no, not by one basis
  point.** A pure refactor that moves a measured number has not been a pure
  refactor. This is the strongest available check on Q1 because it is an
  end-to-end consequence rather than a waveform comparison.

- **Q3 — Does the existing Phase 4 regression survive the driver swap at
  eps = 0?** Prediction: **yes, unchanged** — 69 scoreboard checks, 0 errors,
  100% functional coverage, and I additionally predict the **total simulated
  time is identical** (60830.0 ns), because at eps = 0 and phase = 0 the BFM's
  bit period is exactly `16*(BAUD_DIV+1)` clock cycles. An unchanged pass with a
  *changed* end time would mean the timebase moved somewhere I did not look.

- **Q4 — Does the UVM reference-model scoreboard survive baud-error
  stimulus?** Prediction: **no, and it should not.** The scoreboard predicts the
  received byte from the driven byte; a frame driven past the receiver's
  tolerance legitimately yields a different byte or an error bit, and the
  scoreboard has no way to know that was expected. If this is right, the finding
  is structural and worth more than the code: **a reference model written
  against a synchronous driver silently encodes that driver's timebase as an
  assumption**, and the assumption is invisible until someone changes the
  driver. I predict the failure appears as scoreboard mismatches rather than as
  a crash, and that the fix is a per-item "outcome is not predictable" mode
  rather than a loosened check — 09-26 item 3's three-valued verdict arriving in
  a scoreboard instead of a coverage model.

- **Q5 — How many copies of the pin driver are there?** Prediction: **exactly
  2** (`phase6_rx_pin_driver`, `phase6_baud_error_coverage`), with the Phase 4
  Python driver as a third *reimplementation* rather than a copy. Stated so that
  a miscount is on the record; a census that reads signatures instead of call
  sites was 09-26 item 6's mistake in the graphene repo.

- **Q6 — Does the equivalence bench detect defects injected into the BFM?**
  Prediction: **all of them**, because an exact timestamp comparison has no
  slack to hide in — unlike a coverage model, which 09-26 item 11 measured
  detecting **none** of five mutants. I expect the contrast to be sharp: this is
  the same mutation test against a checker whose tolerance is zero.

- **Q7 — Will the UVM environment's independently-measured 8N1 tolerance limit
  agree with 09-25's?** Prediction: it lands **within** the derived band rather
  than on the number, the same outcome 09-26 item 7 got from its cross-check,
  because the two benches differ in edge phase and sweep grid. A landing exactly
  on the number would be more suspicious than a landing near it.

## Validations (each must produce an EXACTLY known value, not a plausible one)

The 2026-09-17 graphene lesson, applied here: a plausible-range check passes
things an exact check catches.

- **V1 — Exact waveform equivalence.** BFM vs. a verbatim copy of the old task,
  both instantiated in one bench, every `rx` transition timestamped at ps
  resolution. Required: **identical transition counts and identical
  timestamps**, exactly, on every trial. Tolerance: zero.
- **V2 — Exact grid alignment.** At `bit_ps = BIT_PS_NOM` and `phase_ps = 0`,
  the number of DUT clock cycles between consecutive `rx` transitions must be
  **exactly** `16*(BAUD_DIV+1)`, with zero variance over the frame. This is the
  known-value check that ties the BFM to the cycle-counted driver it replaces.
- **V3 — Regression invariance.** The committed Phase 4 result (69 checks, 0
  errors, 100% coverage) reproduced, and the end time compared to 60830.0 ns.
- **V4 — NEGATIVE control.** At eps ≠ 0 the BFM must **disagree** with a
  cycle-counted driver, by a predicted amount: over a 10-bit 8N1 frame at
  eps = +1%, the last transition must sit `0.01 * 10 * BIT_PS_NOM` later,
  exactly. A refactor that passed V1–V3 while *also* agreeing here would mean
  the independent timebase is decorative. V1 alone cannot catch that; V4 is
  the reason both exist.
- **V5 — Zero regressions in the two phase6 benches.** Both committed outputs
  reproduced check-for-check, which is Q2 in executable form.

## What would make this session a failure rather than a result

If V1 passes and nothing else is learned, the session has done a refactor and
should say so plainly rather than dress it up. The findings this session is
actually hunting are Q4 (a scoreboard's hidden timebase assumption) and Q7 (a
third independent measurement of a number measured twice already). Q1–Q3 and V5
are the price of admission, not the result.
