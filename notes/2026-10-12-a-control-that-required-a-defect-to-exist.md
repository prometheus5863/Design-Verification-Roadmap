# 2026-10-12 — the census found two reads nobody had named, five names it had guessed itself, and then its own control broke when the defect was fixed

**Item taken:** the top-ranked open item, *a DUT-signal census for every
scoreboard*, created 2026-10-11 out of a scoreboard that read the DUT output
it was meant to check (mutant M4 SURVIVED a 5/5 suite).

**Built:** `tools/scoreboard_dut_signal_census.py` — 16 rows over 5 files,
6/6 controls. Output: `tools/scoreboard_dut_signal_census_output.txt`.
**Repaired:** `examples/phase6_crv_uart/uart_crv_cov_tb.v`, with
`mutation_test_report_2026-10-12.txt` (7 mutants, 7/7 as predicted) and
`neutrality_pass_2026-10-12.txt` (8 combinations, exact).

---

## 1. The census, and why its roles are declared rather than inferred

The rule the previous session left behind: **for every DUT signal a checker
reads, ask whether the checker could detect that signal being wrong; if not,
predict it independently in the window where that is possible, or state the
blind spot.**

Four roles: `PREDICTED` (the checker computes the expected value from its own
model, so a defect is observable), `TRUSTED` (the checker uses the DUT's value
as its reference, so a defect corrupts the reference identically and is **not**
observable), `OBSERVED_ONLY` (sampled for coverage; nothing for a defect to
corrupt, and also no check), `SYNC_ONLY` (read to decide *when* to sample, not
*what* to expect — a weaker exposure than PREDICTED, a stronger one than
TRUSTED).

Every role is **declared by a reviewer**. A tool that inferred the role of a
read by static dataflow would be this repository's class (v) failure, a
procedure that certifies itself. What is mechanical is the set of controls
that can **falsify** the declaration:

| | control | what it can catch |
|---|---|---|
| C1 | staleness: every row's `evidence` substring must still appear verbatim in its file | a row whose code has been edited away, i.e. a census that has become decoration |
| C2 | completeness: every mechanically extracted DUT read must be covered by a row | a read nobody has stated the role of — the direction that can grow |
| C3 | allowlist derivation | an allowlist inflated until C2 is vacuous |
| C4 | discriminating power | a census that cannot find anything and reports itself clean |

## 2. C2 failed on the first run, and the ten omissions split three ways

**Two were real.**

* `examples/phase6_crv_uart/uart_crv_cov_tb.v` reads `STATUS.rx_avail`
  (`st[3]`) to decide when to read `RX_DATA`, and no row named it. SYNC_ONLY:
  an `rx_avail` that never asserts trips the per-burst watchdog, one that
  asserts early reads a byte the receiver has not finished and the data
  comparison catches it. The exposure exists but is **indirect**, and no
  mutant has ever been run for it.
* `examples/phase1_milestone/sync_fifo_directed_tb.v` compares `rd_data`
  against `exp_data` taken from its own `ref_model` — the right pattern, also
  unnamed.

**Five were the tool's own defect, and this is the honest one.** The first
draft declared the driven-pin allowlist as a hand-written **name list**,
written from the naming *convention* rather than from the file: it named
`bfm_parity`, `bfm_two_stop`, `bfm_div`, which do not exist, and missed
`bfm_bad_par`, `bfm_bad_stop`, `bfm_bit_ps`, `bfm_mode`, `bfm_par`, which do.

That is the graphene repository's 2026-10-09 rule arriving here: **a list
re-typed from memory measures its own transcription.** The repair is not a
corrected list but a **derived** one — a pin is bench-driven if the file
assigns it (`dut.X.value = …`), which the file itself states. Two names stay
declared (`clk`, `rst_n`) because they are assigned in helpers this extractor
does not follow, and the count of hand-declared names is itself reported.

> **An allowlist that states what the file states cannot be inflated by hand
> to make the control it feeds pass.**

**Three were a vocabulary mismatch.** Rows naming `STATUS error bits [6:4]`
against an extractor naming `frame_err`, `parity_err`, `overrun_err`.

> **A completeness control only works if the declaration and the extraction
> speak the same vocabulary.** The rows now spell the bit names out rather
> than the range — the fix is to make the declaration more specific, not to
> loosen the match.

## 3. The one TRUSTED row, closed the same session, measured in both directions

The Verilog CRV bench read `STATUS.tx_full` and enqueued to its reference
model only when that bit was clear. An early `tx_full` gates the DUT's own
`tx_push` **and** the bench's enqueue identically, so the two agree and
nothing fails. The Verilog twin of the uvm-python hole, deferred on 2026-10-11
because the file owns committed transcripts.

| | seeds 1 / 3 / 5 |
|---|---|
| M7 (`tx_full = tx_cnt >= 7`) **before** | **ESCAPED** — 8203 / 7926 / 7225 checks, all passing |
| M7 **after** | **DETECTED** on all three; first failing check names the occupancy |

The repair makes `tx_full` a checked output. `tx_push` is independent of
`CTRL.en` and the TX engine only pops when enabled, so during the fill phase
occupancy is exactly the number of accepted `TX_DATA` writes, which the bench
counts itself. Three details worth keeping:

1. **The prediction's starting point is checked, not assumed.** The fill phase
   first asserts `tx_empty` set and `tx_full` clear. A predicted occupancy
   that begins from an unverified zero is a second guess, not a prediction.
2. **The prediction is claimed only inside the window where it holds** — once
   the engine is enabled, occupancy is unobservable from the bus, and claiming
   it there would be the 2026-10-05 defect of printing a metric beside
   something it does not measure.
3. **`TX_DEPTH` is named once**, next to the reference model, with the RTL line
   it comes from quoted. A predicted bound written as a bare `8` at three
   sites is 2026-10-11's copied-constant defect waiting to happen.

The repair creates **two** exposures where there were none: the
predicted-occupancy check, and — on two of three seeds — a `burst watchdog:
7 of 8 bytes returned` failure, because the bench now pushes the eighth byte
the DUT drops.

**The output-neutrality pass is exact.** All 8 `(seed, steer)` combinations of
seeds {1,3,5,6} × steer {0,1} are identical outside the two check-count lines:
same transactions, bytes, pushes skipped, constraint rejections, per-bin
coverage, closure transaction. Only the check counts rise (8862 → 8960 at
seed 1, steer 1).

And the reason neutrality is exact is the same fact that hid the defect. On
unmodified RTL both the old condition (`st[0]`) and the new one
(`pushed == TX_DEPTH`) are false at every iteration — the loop samples *before*
each push, so occupancy never exceeds 7 inside it, and `burst_len ≤ 8`. The
baseline's `pushes skipped (tx_full) : 0` is the evidence.

> **An untaken branch is not an unused branch — it is the branch the defect
> takes.** Under M7 the old branch was taken 1–2 times per run.

## 4. And then the repair broke the census

C4 had been written as *"the census must contain at least one TRUSTED row"*,
on the 2026-10-08 argument that a census reporting itself clean has no power
to find anything. Repairing the one TRUSTED row the census had just found made
that control **fail**.

> **A control must not demand that the thing it looks for still be there.**

The right question is not whether a defect is present now but whether the
census has **ever been shown to find one**. C4 now requires at least one row
carrying a **demonstrated escape**: a mutant that was actually run against the
pre-repair code and survived it. That property is permanent.

Two rows qualify — the uvm-python scoreboard's `prdata[0]` with M4
(2026-10-11) and the Verilog driver's `st[0]` with M7 (2026-10-12) — and they
are **the same defect shape found independently in two languages**, which is
why the census is organised around the shape rather than the instance.

The open-TRUSTED count is now **reported** rather than required to be
non-zero, because a clean report and an unexercised control look identical
from outside, and the demonstrated-escape count is what distinguishes them.

This is the inverse of 2026-10-08's rule. A control with no control is
useless; so is one that cannot pass on healthy code.

## 5. The series, with today's two entries

09-17 a suite can pass against broken RTL. 09-18 and print PASS over its own
errors. 09-19/09-20 the subsystem reporting the verdict is not the one doing
the checking. 09-26 a reachability pre-pass answers "did my attempts reach
it". 09-30 a control has to sit where the failure enters. 10-01 an arrival
control that cannot fail is not a control. 10-05 a metric can be printed
beside the thing it does not measure. 10-06 and the detector can misattribute
what it measured. 10-07 an injection guard is a measurement. 10-08 a false
SURVIVED is worse than a missed defect. 10-09 and so is a false DETECTED.
10-10 a control must not read the thing it controls for. 10-11 and neither may
a checker.

**10-12: A CONTROL MUST NOT REQUIRE THE DEFECT IT LOOKS FOR TO STILL EXIST.**

**And: A COMPLETENESS CONTROL ONLY WORKS IF THE DECLARATION AND THE
EXTRACTION SPEAK THE SAME VOCABULARY.**

## 6. Toolchain

The simulator was needed. Both 2026-10-11 gotchas re-confirmed: `source
tools/setup_iverilog.sh` **without a pipe** (Icarus 10.3 came up), and
`iverilog`/`vvp` are shell functions, so wrapping them in `timeout` needs the
real binaries at `/tmp/iverilog_install/usr/bin` with
`-M .../lib/x86_64-linux-gnu/ivl`. No cocotb or uvm-python needed this
session; those recipes were not exercised and are now **one session** from the
two-session staleness threshold.

Device reachable and folder connected at the first firing; nothing crossed the
bridge. Every commit was pushed and verified against the GitHub API, with
`git fetch origin main` immediately before each push per the 10-03 race item.

## 7. What this note does not claim

1. **Not that the census's roles are right.** They are declared; only the
   controls are mechanical. A row declared PREDICTED that is really TRUSTED
   passes every control here, and only running its mutant would catch it. The
   7-of-16 "mutant never run" count is the honest measure of that exposure.
2. **Not that the file list is complete.** Five files are censused; the
   repository has more checkers. C2 is complete only *within* a censused file.
3. **Not that M7 is the only mutant of its shape.** `tx_empty` is now
   predicted too, at one site, and no mutant has been run against it.
4. **Not that the Phase 1 FIFO bench is verified.** Its `full`/`empty`/
   `rd_data` rows are PREDICTED *by construction* from `ref_model`, and the
   "full asserting one entry early" mutant — the exact shape demonstrated
   twice above — has never been run there. That is now the most interesting
   unrun row in the census.
