# No mutant moves between modes; M7 has never run; and the 2026-10-21 result survives its control

**2026-10-22.** Ranked-first item from 2026-10-21: *do the other
coverage-steered bins suppress detection too?* — i.e. re-run every mutant in
`phase6_crv_uart` under `steer=0` as well as `steer=1`, since all twelve
committed reports were produced in **one mode** and have been read as
statements about the suite.

Artifacts: `examples/phase6_crv_uart/run_mutation_tests_bimodal.sh` with
`bimodal_mutation_report_2026-10-22.txt`;
`examples/phase6_crv_uart/run_equal_budget_control.sh` with
`equal_budget_control_2026-10-22.txt`. `phase6_uvm_crv_uart` was **not** run —
it needs cocotb and remains blocked, so this session covers one of the two
suites the item named and says so.

---

## 1. The question as asked: nothing moves

| mutant | A `steer=0` | B `steer=1` | E equal-budget |
|---|---|---|---|
| M1 TX parity polarity swapped | 5/5 | 5/5 | 5/5 |
| M2 RX data bit inverted | 5/5 | 5/5 | 5/5 |
| M3 stop_bits ignored by TX | 5/5 | 5/5 | 5/5 |
| M4 TX FIFO count never increments | 5/5 | 5/5 | 5/5 |
| M5 BAUD_DIV ignored | 0/5 | 0/5 | 0/5 |
| M6 STATUS read no longer clears | 0/5 | 0/5 | 0/5 |
| M7 tx_full one entry early | 5/5 | 5/5 | 5/5 |

**No mutant moves.** The committed one-mode scores for M1–M7 are not
mode-conditional, and `tx_empty`'s T3 remains the only known
mode-conditional row in the repository. That is the answer, and it is the
least interesting of the three results.

## 2. THE MODE COMPARISON HAS A CONFOUND, AND IT IS LARGE

The bench's run loop is

```verilog
while (total_tx < max_tx && bins_hit() < N_BINS && errors == 0)
```

It stops **at closure**, and steering exists to reach closure sooner. So the
two modes do not drive the same stimulus — by design, since
`TRANSACTIONS TO CLOSURE` is the figure this bench was built to report:

| seed | `steer=0` tx | `steer=1` tx | ratio |
|---|---|---|---|
| 1 | 648 | 54 | 12.0× |
| 3 | 258 | 49 | 5.3× |
| 5 | 110 | 53 | 2.1× |
| 7 | 360 | 52 | 6.9× |
| 9 | 457 | 40 | 11.4× |

A mutant needing a rare event is then more likely to be caught under
`steer=0` **for volume alone**, with nothing implied about the coverage model.
2026-10-21 gave a specific mechanism for T3's escape and that mechanism is
still in the code — but the experiment as run had two explanations and could
not separate them.

**The control is `+maxtx`:** run `steer=0` truncated to `steer=1`'s own
transaction count. It cannot reach closure, so scoring it `RESULT: FAIL`
would mark every row detected, including unmutated RTL. Every run is
therefore classified by **which check failed** — `PASS` / `CLOSURE_ONLY` /
`DATA` / `DIED` — with a positive control (G2) requiring unmutated truncated
RTL to come out `CLOSURE_ONLY`.

### Applied to T3, where the movement actually was

| seed | budget | A `steer=0` | B `steer=1` | E equal-budget |
|---|---|---|---|---|
| 1 | 54 | DATA | **PASS** | **DATA** |
| 3 | 49 | DATA | DATA | DATA |
| 5 | 53 | DATA | **PASS** | **DATA** |
| 7 | 52 | DATA | DATA | CLOSURE_ONLY |

On **both** seeds where steering escaped, pure random still detects T3 within
steer=1's own budget, caught by *"post-push tx_empty agrees with occupancy"*.
**Volume does not explain the escapes.** The 2026-10-21 conclusion survives
the control that could have overturned it.

**What is not claimed:** that the aggregate gap is entirely the coverage
model. At equal budget pure random scores 3/4 rather than 4/4 — seed 7 shows
the budget alone can cost a detection on a seed where steering did **not**
escape. The per-seed reading is load-bearing; the aggregate is not. Running a
control that could have falsified the result and finding it does not is worth
more than the original measurement.

## 3. M7 HAS NEVER RUN

`run_mutation_tests.sh` injects M7 with

```
s/wire tx_full  = (tx_cnt == 4.d8);/wire tx_full  = (tx_cnt >= 4\\x27d7);/
```

One backslash too many. GNU sed reads `\x27` in a replacement as a hex escape
and emits `'`; it reads `\\x27` as an escaped backslash followed by `x27` and
emits:

```verilog
wire tx_full  = (tx_cnt >= 4\x27d7);
```

which is a syntax error. And that runner scores a compile error as a
detection:

```bash
if [ "$V" = "FAIL" ] || [ "$V" = "COMPILE_ERROR" ]; then GOT="DETECT"
```

So the M7 row has read **"predicted DETECT, got DETECT (as predicted)"** in
every committed report since 2026-10-12, and its stated reason names a
specific check — *"Now DETECTED by the predicted-occupancy check, which names
the occupancy"* — that this mutant has never reached.

Injected by anchor instead, M7 **is** detected 5/5 in both modes, first-failing
check *"tx_full agrees with predicted occupancy"* / *"post-push tx_full agrees
with occupancy"*. **The conclusion was right and the evidence for it did not
exist.** That is the worse of the two possibilities: a wrong conclusion gets
corrected the next time someone looks, and a right conclusion with no evidence
behind it never gets looked at again.

### The claims are true, and the repository has never held their evidence

`git log -S` dates the malformed sed to the commit that **introduced** the M7
row (`0a6c9bb`, 2026-10-12). So the committed runner has never done anything
with M7 but fail to compile it. That commit's message, and the Phase 6
checklist entry in `progress.md`, both claim M7 "escaped three seeds before,
is detected by all three now" — a before/after comparison that a compile error
cannot produce in either direction.

Reproduced today with a correct injection, against the **pre-repair** bench
(`0a6c9bb~1`):

```
seed=1 : PASS (escaped)
seed=3 : PASS (escaped)
seed=5 : PASS (escaped)
```

and against the current bench, 5/5 detected in both modes. **Both halves of
the claim are true.** Neither was ever produced by anything in the repository:
whatever measured the before/after was not committed, and what was committed
has only ever emitted a syntax error.

That is the exact failure mode worth naming. A *wrong* claim gets corrected
the next time someone looks. A *right* claim with absent evidence is stable —
it survives every review, because every review finds the verdict it expected
and the reason it expected, and the two were never connected.

### The guard, and why the existing one is incomplete

`run_mutation_tests.sh` already guards injection — it refuses a sed that
matched **nothing**, with a comment saying such a row "would otherwise have
scored as an escape against UNMODIFIED RTL". That guard covers exactly one of
the two ways an injection fails. The other is a sed that matches and emits
something that is not the language, and scoring `COMPILE_ERROR` as `DETECT`
turns it into a reported **success**. The complete guard is both:

> **the file must change, AND the result must still compile.**

This is the 2026-10-20 *naming is not invoking* lesson one level down: the
mutant was named in a table, the table was believed, and nothing asked whether
it had ever been a program.

## 4. M4's STATED REASON IS FALSE

The committed why-string for M4 says it is

> "caught by the coverage criterion, not by any data check"

M4 is the repository's only worked example of a mutant caught by coverage
closure, and it is the justification for the bench's design decision that
"coverage closure is a PASS CRITERION, not a report line". Classifying by
first failing check:

```
  FAIL post-push tx_empty agrees with occupancy: got 0x1, expected 0x0
  FAIL burst watchdog: 0 of 4 bytes returned
  FAIL reference queue drained: got 0x4, expected 0x0
  FAIL coverage closure: 9 of 30 bins
```

Three data checks fail first. The closure check does fail too, but it is not
the catching mechanism, so the claim is false as written.

**Consequence worth stating plainly: no mutant in this suite is detected by
the coverage criterion alone.** The decision to make closure a pass criterion
is not thereby wrong — it may still be the only thing that would catch some
mutant nobody has written — but it currently has **no mutation evidence behind
it**, and it has been cited as though it had.

Same shape as §3 and as M7: a claim about *which check does the work* was
recorded next to a verdict that did not depend on it, and nothing in the flow
ever compared the two. 2026-10-21 built per-check adjudication for exactly
this reason in the `tx_empty` runner; the older runner never got it, and both
of today's defects are in rows that predate it.

## 5. What this session did not do

- `phase6_uvm_crv_uart` is untouched — it needs cocotb.
- `run_mutation_tests.sh` is left **unedited**, so its twelve committed
  reports stay comparable; the repairs live in a second runner. Whether the
  old runner should be retired or corrected in place is a decision, not a
  build, and is listed rather than taken.
- The three other runners that treat `COMPILE_ERROR` as a detection were not
  audited. `phase1_mutation/run_mutation_tests.py` reports it as its own
  verdict class, which may already be correct; `run_tx_empty_mutation_tests.sh`
  returns `COMPILE_ERROR||` and does not obviously score it as a hit. Neither
  was checked today and neither should be assumed clean.
