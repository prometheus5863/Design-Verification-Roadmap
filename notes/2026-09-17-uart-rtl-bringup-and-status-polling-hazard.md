# 2026-09-17 -- UART controller RTL bring-up, and a real verification
# hazard: read-to-clear status bits vs. polling wait loops

## 0. What this session did and why

Phase 4's milestone has been gated since 2026-09-05 on a DUT that does
not exist: `verification_plans/uart_controller_verification_plan.md` was
written spec-first (deliberately, per the planning methodology in
`notes/2026-09-05-*.md`) and its own Section 7 flags that "the DUT RTL
itself will need to be written (or sourced) for the first time" as a
Phase 4 dependency. The 8-bit ALU used for Phases 1-3 is too small to
carry the plan's 9 features (no registers, no FIFOs, no serial framing,
no interrupt).

So this session wrote the DUT: `rtl/uart_controller.v`, plus a directed
self-checking bring-up regression,
`examples/phase4_rtl_bringup/uart_controller_tb.v`.

Deliberate scoping decision: **this is not the UVM testbench.** Bringing
up a new DUT inside a brand-new UVM environment means that when a test
fails you cannot tell whether the DUT or your UVM code is wrong. The
bring-up suite here is plain Verilog-2001 on the pinned Icarus 10.3
build, so it is subject to none of the class-support limitations logged
since 2026-08-25 (those apply to class-based *testbenches*; synthesizable
RTL and procedural testbenches compile fine). Once this regression is
green, the UVM environment gets built against a DUT already known good.

## 1. The RTL

394 lines, Verilog-2001, implementing plan Section 1 exactly:

- APB-lite register interface (`paddr[3:0]`, `pwdata`, `prdata`,
  `pwrite`, `psel`, `penable`, `pready` tied high -- v1 has no wait
  states per Section 1.2).
- All six registers of the Section 1 map: CTRL, STATUS, BAUD_DIV,
  TX_DATA (WO, push), RX_DATA (RO, pop), INT_EN.
- 8-entry x 8-bit TX and RX FIFOs, single clock domain (CDC explicitly
  out of scope, Section 1.2).
- 16x-oversample baud generator: one oversample tick every
  `(BAUD_DIV+1)` clocks, so one bit period is `16*(BAUD_DIV+1)` clocks
  and the bit rate is `clk/(16*(div+1))` -- the plan's documented
  relationship, verified by measurement in T8 below.
- TX FSM: start / 8 data LSB-first / optional parity / 1-2 stop, idle
  high. RX FSM: start-bit confirmation at mid-bit (a high sample at
  mid-start-bit is treated as a glitch and abandoned, not a frame),
  then mid-bit sampling of each data bit, parity check, stop-bit check.
- `CTRL.loopback_en` routes the internal `tx` back into the receiver,
  ignoring the `rx` pin.
- `irq` = OR of unmasked live conditions, per plan Section 2.8.

### 1.1 One deliberate deviation from the plan, and why

The plan (Section 1) calls all seven STATUS bits "live status". The four
occupancy bits (`tx_full`, `tx_empty`, `rx_full`, `rx_avail`) are indeed
implemented combinationally. The three error bits (`frame_err`,
`parity_err`, `overrun_err`) are **not**: they are sticky, set by the
event and cleared by a STATUS read (the classic 16550 LSR read-to-clear
behaviour) or by reset.

This is a correction to the plan, not an implementation shortcut. A
genuinely combinational error bit would be asserted for the single clock
cycle in which the error is detected, and no register read could
reliably observe it -- which would make the plan's own F4 and F6 checks
("`STATUS.parity_err` is set exactly when ...", "`overrun_err` is set
when ...") untestable through the register interface. The plan's Section
7 explicitly anticipates revisions of this kind once real RTL exists.
Recorded here and in the RTL header comment rather than silently
applied; `verification_plans/` needs a v2 revision to match (listed in
"not yet covered" below).

## 2. The bring-up regression: 60 checks, T1-T12

Every check is a runtime comparison that prints expected vs. actual and
increments a failure counter; the run ends with `$fatal` on any failure,
so a broken DUT cannot pass quietly. There is also a global watchdog so a
hung DUT fails loudly instead of running forever. Feature mapping:

| Test | What it checks | Plan feature |
|---|---|---|
| T1 | reset values of all registers, `irq` low | F1 |
| T2 | R/W readback, bit masking, RO STATUS write ignored, WO TX_DATA read defined, undefined address does not hang | F1, F1.1 |
| T3 | TX->RX loopback, parity none, 1 stop | F2, F3, F9 |
| T4 | even and odd parity over loopback | F2, F3, F4 |
| T5 | two stop bits | F2, F3 |
| T6 | TX FIFO fill, `tx_full`, write-while-full is a safe no-op, in-order drain of all 8 bytes | F5 |
| T7 | RX FIFO overrun: 9th byte dropped, `overrun_err` set, existing 8 entries intact | F6 |
| T8 | measured TX bit period vs. `16*(div+1)*clk` | F7 |
| T9 | `irq` masking/unmasking without disturbing STATUS | F8 |
| T10 | corrupted parity bit driven at bit level -- negative test | F4 |
| T11 | bad stop bit -> `frame_err` | F3 |
| T12 | sticky error bits are read-to-clear (pins the Section 1.1 deviation) | -- |

T10 required the standalone bit-level RX driver the plan's Section 2.4
already predicted would be needed ("not reachable via TX-loopback, since
a correctly-functioning TX never sends bad parity"). That prediction held
exactly.

Result: **60 passed, 0 failed**
(`examples/phase4_rtl_bringup/uart_controller_tb_sim_output_2026-09-17.txt`).

## 3. The real finding: a testbench that passed against broken RTL

The first complete version of this regression reported 55 passed, 0
failed. That number was not trustworthy, and mutation testing is what
exposed it.

Method: inject one deliberate defect into a *copy* of the RTL, re-run the
regression, and require it to fail. A mutation that survives is a hole in
the testbench.

The first round (`m1`: TX odd-parity generation computing even parity
instead) **passed all 55 checks against knowingly broken RTL.**

Root cause, and it is worth stating precisely because it generalises:

- `parity_err` is read-to-clear (Section 1.1).
- The testbench's wait helper was `wait_rx_avail()`, which **polled
  STATUS in a loop** until `rx_avail` came up.
- So by the time the test read STATUS to check `parity_err`, its own
  polling loop had already read STATUS several times and cleared the bit.

The testbench was destroying the evidence it was about to check. The
check was not weak, and the RTL bug was not subtle -- the *measurement
apparatus* had a side effect on the thing being measured.

The general lesson, which applies to any register interface with
read-to-clear or read-destructive fields (RX FIFO pops, W1C interrupt
flags, clear-on-read counters): **a polling wait loop is not a passive
observer.** In a UVM environment this same hazard reappears as a monitor
or a `wait_for_status()` utility task issuing real bus reads; the fix
there is the same as here -- either wait on something other than the
destructive register, or capture the whole register in one read and check
all its fields from that single snapshot.

Fix applied: `wait_rx_avail()` replaced with `wait_bits(n)`, a counted
wait of `n * 16 * (div+1)` clocks. Frame timing is fully deterministic
(the divisor is known to the testbench), so a counted wait is both safe
and sufficient. The error-bit tests now take a single STATUS read and
check `rx_avail` and the error bits from that one snapshot.

After the fix: 60 checks, and all five mutations are detected.

| Mutation | Injected defect | Result |
|---|---|---|
| m1 | TX odd parity computes even parity | 59/60, FAILED (was: undetected) |
| m2 | RX overrun overwrites FIFO instead of dropping | 56/60, FAILED |
| m3 | `irq` ignores the `INT_EN` mask | 57/60, FAILED |
| m4 | RX samples at the bit edge, not mid-bit | 36/60, FAILED |
| m5 | baud reload off by one | 25/60, FAILED |

Full report:
`examples/phase4_rtl_bringup/mutation_test_report_2026-09-17.txt`.

Note what m1's "59 passed, 1 failed" says about coverage quality: a
single-bit parity defect is caught by exactly one check. That is thin,
and it is thin *legitimately* -- the loopback path is the only TX-parity
observation point in this suite. A `tx`-line monitor with an independent
reference bit-stream generator (plan Section 2.2's actual specified
check) would catch it in many more places. That belongs in the UVM
environment, and is now a concrete argument for building it rather than
a checklist item.

## 4. Toolchain note (small, but it cost time)

`source tools/setup_iverilog.sh | tail -5` does **not** work. Piping
`source` runs it in a subshell, so the `iverilog`/`vvp` shell functions
it defines vanish when the subshell exits, and the next command fails
with `iverilog: command not found` even though the setup script reported
success. Source it without a pipe.

Related: because `iverilog`/`vvp` are shell *functions*, not binaries,
`timeout 150 vvp sim` fails with `timeout: failed to run command 'vvp':
No such file or directory`. To wrap them in `timeout` (worth doing in a
mutation loop, where a mutant can hang), invoke the real binary with its
`-M` plugin path directly:
`timeout 150 $IVL/usr/bin/vvp -M $IVL/usr/lib/x86_64-linux-gnu/ivl sim`.

Both are recorded here because both produced confusing failures that
looked like broken tooling rather than shell semantics.

## 5. Web search availability

Not needed this session -- this was RTL design against an
already-researched in-repo specification plus hands-on debugging, not a
literature review. No fetches attempted, so no access failures to record.
