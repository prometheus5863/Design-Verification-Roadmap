# Phase 5 milestone — formal property suite on the UART FIFO control path

Run it:

```sh
source tools/setup_formal.sh          # source, do not pipe
bash examples/phase5_formal_uart/run_formal.sh
```

Recorded output: `formal_run_output_2026-09-20.txt` (10 passed, 0 failed).

## What is proved

Properties live in `rtl/uart_controller.v` under `` `ifdef FORMAL ``, the
SymbiYosys idiom. They cover the **TX/RX FIFO control path**, chosen because
its correctness is an *unbounded* claim — "the count never exceeds 8, on any
trace of any length" — which is exactly what simulation cannot establish.

| | property |
|---|---|
| P1 | `tx_cnt <= 8`, `rx_cnt <= 8` |
| P2 | `(wptr − rptr) == cnt[2:0]` — pointer/count consistency, not implied by P1 |
| P3 | `!(full && empty)`, and `rx_avail` agrees with `rx_cnt` |
| P4 | the count changes by at most 1 per cycle, and only in the direction the strobes call for |
| C1 | cover: a *full* TX FIFO, and a wrapped read pointer |

Results on the real RTL: **bmc depth 24 PASS, prove (k-induction) PASS —
an unbounded proof — cover PASS**, both cover statements reached (step 10
and step 6), so the suite is not vacuous.

## The finding worth carrying into Phase 6

`prove` mode has **three** outcomes, not two. On mutant M1 (TX push no longer
guarded by `~tx_full`) sby reports `DONE (UNKNOWN, rc=4)`: the basecase
passes and *induction* fails. That is **not a counterexample** — the
induction trace starts from a possibly-unreachable state, so it says only
that the property is not k-inductive for that design. The same mutant under
`bmc` gives `DONE (FAIL, rc=2)` with a genuine reachable trace.

So a mutation harness for formal must score **bmc FAIL**, not "prove did not
pass". `run_formal.sh` does exactly that and prints the prove verdict
alongside as commentary. This is the 2026-09-17/18/19 verdict-vs-checking
defect class in its formal-tool form, caught this time *before* it produced
a wrong number — the first of the four to be caught in advance.

Unlike `make`, sby's exit code is actually informative (0 pass / 2 fail /
4 unknown) and agreed with its status line in all 13 runs. The script still
parses the status line, and now *measures* the agreement rather than
assuming it either way.

## Stage 1 is a guard, not a formality

The `` `ifdef FORMAL `` block must be invisible to Icarus. `run_formal.sh`
re-runs the Phase 4 60-check regression and requires **60/60** before it
does any formal work. Claimed-and-checked.

## Measured, not assumed: P2 is inductive on its own

Stage 4 deletes P1 and re-runs the proof to find out whether P2 needs P1 as
a strengthening invariant. It does not — P2 alone is k-inductive here. The
stage is kept because the negative result is the interesting one and the
next property added may well need it.

## Not covered

The serial datapath (start-bit detect, oversampling, parity, stop-bit
framing). Its properties need sequences spanning many bit periods —
16·(BAUD_DIV+1) clocks each — which the WASM solver budget does not reach at
any useful depth. That is a scope statement, not a claim that the datapath
is correct.
