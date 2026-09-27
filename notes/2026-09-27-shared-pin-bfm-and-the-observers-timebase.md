# 2026-09-27 — One shared pin BFM, an independent timebase for the UVM environment, and the day the regression runner turned out not to be reading its own log

Study note for the session that closed the 2026-09-26 top item. Four things
worth keeping, in rough order of how portable they are.

---

## 1. A regression runner that greps a fixed path in /tmp is a gate that can pass without looking

This was found by accident and it is the most transferable thing here.

Establishing a pre-refactor baseline meant running both phase6 benches and
**diffing today's output against the committed output**, rather than reading
the runner's verdict. The diff showed, buried in 500 lines of bench output,
two lines on stderr:

```
tee: /tmp/baudcov_seed_1.log: Permission denied
```

and the runner still printed `ALL 3 SEEDS PASS`.

The mechanism, once seen, is obvious. The runner did:

```bash
timeout 170 vvp ... | tee /tmp/baudcov_seed_$s.log
grep -q "RESULT: PASS" /tmp/baudcov_seed_$s.log || FAILED=1
```

The automation sandbox reuses `/tmp` across sessions with **different uid
mappings**. `/tmp/baudcov_seed_{1,2,3}.log` existed, owned by `nobody:nogroup`,
dated **2026-09-26**. `tee` could not open them, said so on stderr, and passed
stdin through to stdout as it always does — so the console output was correct
and complete. Then `grep` read **yesterday's file**, which said `RESULT: PASS`.

**Demonstrated rather than reasoned about.** The bench was edited to force
`errors > 0` so it printed `RESULT: FAIL`. The unchanged runner printed
`ALL 1 SEEDS PASS` and exited **0**. With the fix, the same broken bench gives
exit code 1.

Both failure directions are live, which is what makes this worth a paragraph
rather than a one-line fix:

- with a stale PASS log present → **false pass**;
- with nothing writable and no stale file → `grep` fails → **false failure**.

A gate that cannot write its evidence should not be able to reach a verdict in
either direction.

**The general rule.** *A pass/fail gate must consume the artefact it just
produced, and must be unable to consume anything else.* Three defences, each
counting as FAILURE rather than as success:

1. a private `mktemp` log per seed — no stale file is reachable at all;
2. an empty log means `tee` failed, which is a failure, not a pass;
3. **exactly one** `^RESULT:` line is required, so a concatenated, partial or
   doubled log cannot satisfy the gate either.

**Where this sits in the repository's standing pattern.** The
verdict-versus-checking class has now been found at every layer of a
testbench: in checkers (six occurrences, 09-17 to 09-23), in a measurement
(09-24), in stimulus and thresholds (09-25), in the reachability pre-pass that
decides what may be *asserted* (09-26), and now in **the thing that decides
whether the regression passed at all**. For two days `ALL 3 SEEDS PASS` was a
sentence about a file rather than about the DUT.

Nothing published moved — both benches reproduce their committed outputs byte
for byte, which is how the bug was caught rather than a lucky escape from it.

And the fix validated itself within the hour: the *new* Phase 4 runner, written
with the same three defences, reported FAILURE for three tests that had all
passed, because its `grep -cE '^\*\* TESTS='` was anchored at `^` and cocotb
pads that line with leading spaces. A gate whose first bug is a false failure
is a gate built the right way round.

---

## 2. Proving a refactor instead of asserting it: zero tolerance, picosecond resolution

The pin driver was a `task drive_frame` duplicated **verbatim** in
`examples/phase6_rx_pin_driver/uart_rx_pin_tb.v` and
`examples/phase6_baud_error_coverage/uart_baud_cov_tb.v`. The duplication was
deliberate — two benches that must agree about a measured tolerance limit are
more convincing when a disagreement between them cannot be a disagreement
between their drivers — and it stopped being defensible the moment the Phase 4
UVM environment needed a third copy.

The extraction is to `bfm/uart_rx_pin_bfm.v`, whose only timebase is `bit_ps`:
no clock port, no cycles counted.

**The interesting half of the equivalence question is not the one that looks
interesting.** Whether two identical `#(drv_bit_ns)` statements agree is
trivial. What is not trivial is that the old path computed a **`real`
nanosecond** bit period and let `#(real)` quantise it to the 1 ps precision of
a `timescale 1ns/1ps` module, while the BFM path **rounds that same real to an
integer number of picoseconds in the caller** and delays by the integer. Two
different roundings of one product.

So `bfm/uart_rx_pin_legacy_ref.v` keeps the old task character for character
and **re-derives** `drv_bit_ns` internally from the baud error in basis points,
exactly as the phase6 benches did. `examples/phase6_bfm_equivalence/` runs both
off **one** stimulus stream and compares every `rx` transition timestamp:

| test | what | result |
|---|---|---|
| T1 | 3072 structured: 24 frame configs × 8 data × 16 **awkward** eps | 0 errors |
| T1b | 400 random, including a random initial edge phase | 0 errors |
| T1c | glitch and idle modes | 0 errors |
| T2 | exact clock-grid alignment at eps = 0 (V2) | every boundary exactly 32 cycles |
| T3 | negative control: eps ≠ 0 must **disagree** (V4) | exactly 9·`bit_ps`, 16 eps values |

3534 trials, 7126 checks, **0 errors**, tolerance zero. The eps table is
deliberately unlovely — 1 bp, 7 bp, 37 bp, 1234 bp, 4751 bp — because if the
two roundings ever differ they differ on products that do not land on a
picosecond boundary, and a table of multiples of 100 bp would miss exactly
those.

**T3 exists because T1 cannot catch the failure that matters most.** A BFM that
passed T1 and T2 while *also* agreeing with a cycle-counted driver at every eps
would have a decorative "independent" timebase. T1 proves sameness; T3 proves
difference; neither alone is the claim.

### The check that was wrong, and why the constant was not simply corrected

T2's first version hardcoded *"0xAA in 8N1 gives 10 transitions, every span 32
cycles"*. It failed: 8 transitions, one span wrong. The **BFM was right**. The
start bit is 0 and 0xAA's LSB is 0, so the first boundary has no transition and
the first span is 64 cycles, not 32.

The fix is not `10 → 8`. A hand-written expected value is a second
implementation with no tests of its own, so T2 now **derives** the expected
transition list from the frame's level sequence and checks 40 configurations
instead of one. That is 09-26 item 2's lesson — a pre-pass answers *did my
attempt reach it*, not *is it reachable* — at the scale of a single constant.

### Mutation test: 7 detected, 0 escaped, 1 deliberate void

Worth reading against **2026-09-26**, where a mutation test of the baud-error
coverage model detected **0 of 5** and every detection came from an anchored
cross-check instead.

The headline row here is `bit_ps_off_by_one_ps`: **one picosecond per bit**,
3×10⁻⁶ of a bit period, detected with 7077 errors and a first failure of
"delta 9 ps at transition 1". That defect is four orders of magnitude below the
5 bp sweep grid and could never move a measured tolerance limit — **no
DUT-level check in this repository can see it.** A zero-tolerance timestamp
comparison sees nothing else.

The void mutant is kept in the suite on purpose: its `sed` pattern spans two
lines and matches nothing, and it is a **live check that the harness scores an
unmatched pattern as void rather than as a pass**. A mutation harness whose
silently-unmatched patterns count as detections is the same failure mode as a
testbench that passes against broken RTL.

### The end-to-end form, which is the one that matters for the numbers

Both benches reproduce their committed outputs **byte for byte** — every
measured limit, every coverage count, every closure frame count — with every
task *signature* preserved so that not one of the ~2000 lines of tests in those
files was touched. Q2 predicted "not by one basis point". Correct.

One deliberate non-tidy-up: `idle_gap` keeps `#(n_bits * drv_bit_ns)` instead
of being rewritten in integer ps, because converting it would have moved
inter-frame spacing by up to a picosecond and broken byte-for-byte reproduction
**for a reason unrelated to the change under test**. An incidental edit inside
a refactor whose whole claim is "nothing moved" is not free.

---

## 3. The item: an independent timebase inside the UVM environment

`UartSerialDriver` used to advance one bit with

```python
for _ in range(BIT_CYCLES):
    await RisingEdge(dut.clk)
```

Its timebase **was** the DUT's clock. Two consequences, and the second is the
one that mattered: a baud mismatch was inexpressible, and **every frame this
environment had ever driven had its bit edges exactly on DUT clock edges with
zero edge-phase variation** — under a 69-check regression at 100% functional
coverage. The receiver's oversampling had never been exercised off-grid here at
all, which is 09-26 item 8 in one line: coverage records what the stimulus
reached.

`uart_uvm_top.v` now instantiates the DUT beside the BFM and the driver
*programs* it. Deliberately **not** a Python reimplementation of the timebase:
that would be a third pin driver, and the item existed because two verbatim
copies were already one too many. Phase 4 and both phase6 benches now drive the
same module from two languages.

**One small piece of mechanism worth remembering.** The handshake watches
`done_cnt` (monotonic) rather than `busy`'s rising edge. Polling for a rising
`busy` from Python means polling on clock edges, and an action shorter than one
clock period can start and finish between two polls — the driver would then
wait forever for a transition it already missed. A full frame holds `busy` for
~160 clock periods and would have been safe either way, **which is exactly why
the unsafe version would have survived review**.

### The third measurement, and the thing nobody predicted

phase6 runs `BAUD_DIV=1` (32-cycle bit); this environment runs `BAUD_DIV=0`
(16-cycle bit). The oversampling *ratio* is 16 in both, so the **fractional**
limit must agree if tolerance is a property of the oversampling structure
rather than of the divisor.

| | fast | slow | **width** | centre |
|---|---|---|---|---|
| `phase6_rx_pin_driver`, 09-25, `BAUD_DIV=1` | −4.50% | +6.25% | **10.75%** | +0.875% |
| `phase4_uvm_milestone`, 09-27, `BAUD_DIV=0` | −4.00% | +6.75% | **10.75%** | +1.375% |

Both limits land **inside** the derived ±1.00% band (09-25's measured
0.69%-of-eps phase sensitivity plus this test's 25 bp grid), which is Q7's
prediction: inside the band, not on the number.

Unpredicted, and sharper than the prediction: **the width is identical to the
basis point and the entire window is displaced by +0.50%.** A displacement at
constant width is a **sampling-point offset**, not a change in tolerance.

Candidate mechanism, recorded as a hypothesis because the grid cannot confirm
it: `rx_sync`'s one-clock delay is 1/32 of a bit at `BAUD_DIV=1` and 1/16 at
`BAUD_DIV=0`, and 0.03125 bit spread over the ~9.5-bit last checked sample
predicts ≈0.33% against a measured 0.50% — **inside one 25 bp grid step**, so
the two cannot be told apart here. Not asserted as the explanation; left as an
open item with a stated experiment (finer grid, both divisors, in one bench).

This is what drove the vplan v5 correction to sign-off criterion 5: a
per-limit criterion is divisor-dependent and would **fail this same RTL** at
`BAUD_DIV=0` while its tolerance width had not moved at all.

---

## 4. Q4: the reference model does encode the driver's timebase — and the smallness of the effect is the real finding

`cfg.predictable = False` makes the scoreboard **count** rx traffic as OPEN
instead of checking it: observed, not predicted, not asserted. Explicitly not a
loosened tolerance — one wide enough to accept a corrupted byte would also
accept a real bug. Same three verdicts as 09-26's coverage model
(REACHED / EXCLUDED-by-argument / OPEN), arriving in a scoreboard.

`test_uart_scoreboard_timebase_assumption` runs the identical sweep with that
path **disabled** and asserts the model mispredicts. Turning a finding into a
test that fails if the finding ever stops being true is cheap here and worth
more than a paragraph: if some future change makes the model genuinely
timebase-independent, someone has to explain why, instead of a stale assumption
rotting unobserved.

It does mispredict. **5 times in 1274 checks, over 182 probes spanning ±7% of
baud error** — far less than the prediction implied. And the reason is the
better result:

- **4 of the 5** are `STATUS.frame_err: expected 1, got 0` — the **monitor**
  decoded a low stop bit and the DUT did not flag one.
- 1 is a byte disagreement (`expected 0x01, got 0x81`) at the extreme.

The monitor samples `rx` on the DUT's clock using the DUT's own algorithm
(`BIT_CYCLES/2` to mid-start-bit, then `BIT_CYCLES` per bit). Under a mismatch
it therefore **drifts with the DUT and agrees with it**. So:

> **A clock-synchronous monitor on an asynchronous line is not an independent
> observer. It is a second receiver carrying the same assumption, and its
> agreement with the DUT is not evidence the DUT was right.**

This is the loopback fallacy — which this very environment's driver docstring
has warned about since 09-18, in the words *"a loopback test cannot distinguish
a receiver that works from a receiver that happens to agree with the
transmitter's own idea of the frame format"* — **relocated from the
transmitter to the observer**. The same sentence, one noun changed, and nobody
noticed it applied.

The 5 disagreements cluster at the tolerance limits, where the two samplers'
drift finally differs enough to land on different bits. So the count is a
measure of **the difference between two sampling implementations**, not of the
DUT's correctness, and a bigger number would not have meant a worse DUT.

Hence v5's requirement that F7's oracle be register-side — driven byte against
the `RX_DATA` read — with monitor decodes allowed for coverage and debug but
never as the pass/fail basis.

---

## 5. Toolchain, for the next session

- **uvm-python's `run_test()` can be called at most ONCE per simulator
  process.** A second call is `UVM_FATAL [TTINST] An uvm_test_top already
  exists via a previous call to run_test`. Three `@cocotb.test()` coroutines
  each calling it in one run gives `TESTS=3 PASS=1 FAIL=2` where **neither
  failure is about the DUT**. `run_phase4_uvm.sh` runs each test in its own
  invocation via cocotb's `TESTCASE`. This is the third uvm-python constraint
  for `notes/2026-09-06-uvm-python-toolchain-resolution.md`, after the
  run-phase timing constraint and the `cocotb<2.0` pin.
- The **install recipe needed four `--no-deps` packages** today, not the three
  in the 09-06 note: `python-constraint --use-pep517`, `cocotb<2.0`, then
  `--no-deps` for `uvm-python`, `cocotb-coverage`, `cocotb-bus` and `regex`.
  Installing `uvm-python` with dependencies drags in `cocotb-coverage`, which
  demands `cocotb>=2.0` and breaks the pin. Four sequential `ModuleNotFoundError`s
  is the expected path, not a sign anything is wrong.
- Both **2026-09-17 Icarus gotchas still apply**: source
  `tools/setup_iverilog.sh` **without a pipe**, and wrap the real `vvp` binary
  in `timeout` rather than the shell function.
- `cocotb`'s `make` needs `$HOME/.local/bin` on `PATH` for `cocotb-config`;
  without it the failure is `Makefile:20: /Makefile.sim: No such file or
  directory`, which does not name the cause.
- Coverage enforcement in the Phase 4 environment is now **opt-out per test
  with a stated reason**, not a lowered global target. The two new tests sweep
  one frame format and cannot reach the parity and stop-bit bins; lowering
  `TARGET` so they appear to would have been the dishonest fix.
