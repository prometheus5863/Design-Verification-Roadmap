# The run axis, and a summary line that parsed as one of the things it summarised

**Date:** 2026-10-06
**Artefacts:** `examples/phase4_uvm_milestone/uart_uvm_tb.py` (witnesses in
`UartCoverage`), `mutation_test_witnesses.py` +
`mutation_report_witnesses_2026-10-06.txt`, `run_axis_audit.py` +
`run_axis_audit_2026-10-06.txt`, `uart_uvm_sim_output_2026-10-06.txt`,
`run_phase4_uvm.sh`
**Closes:** the prerequisite created 2026-10-05 — *make the collector emit
per-sample witnesses* — and, with it, the run axis itself

---

## 1. What was blocked, and precisely why

The 2026-10-05 three-axis audit of the live `UartCoverage` collector measured
two of its three axes and reported the third as follows:

> The logs record counts; counts cannot answer "which frames closed this
> cell", so the run axis is not merely unmeasured but **unmeasurable from the
> committed artefacts**.

That is an unusually clean statement of a blocked item: not "we did not do
this" but "the artefacts do not contain the information". It also names its own
repair, and the repair is small.

## 2. The mechanism

`UartCoverage` now records, per cell, the identity of the samples that hit it:

```
  bin.cp_rx_error.frame              3 sample(s), 3 shown
      #12 t=7040000ps rx frame data=0xc3 corrupt=None parity_ok=True stop_ok=False
      #30 t=26250000ps rx frame data=0xc3 corrupt=None parity_ok=True stop_ok=False
      #48 t=47220000ps rx frame data=0xc3 corrupt=None parity_ok=True stop_ok=False
```

Four design decisions, each with a reason that is not aesthetic:

1. **One path.** Every coverage increment goes through `_hit()` or
   `_hit_cross()`. There is no way to increment a bin without recording a
   witness, and W-c below makes that a regression failure rather than a style
   rule.
2. **A monotonic sample ordinal.** Two samples with the same payload at the
   same simulation time on the same port would otherwise be indistinguishable,
   and the ordinal also lets a reader reconstruct **order**, which is the part
   of the run axis that counts destroy.
3. **Bounded at `WITNESS_KEEP = 4`.** The longest of the five tests takes 2315
   coverage samples. An unbounded witness log grows with simulation length,
   which is how witness logging usually gets abandoned. Four is enough to name
   the sample that *closed* a cell and see whether its immediate successors
   are the same stimulus.
4. **Five runtime assertions, not comments.** A witness log that silently
   disagrees with the counts printed beside it is *worse* than no witness log,
   because the run-axis audit it unblocks would then be auditing a fiction:
   - **W-a** every nonzero cell has ≥ 1 witness;
   - **W-b** every zero cell has none;
   - **W-c** the witness path's own per-cell total **equals** the printed
     count;
   - **W-d** witnesses within a cell are pairwise distinct;
   - **W-e** no cell exceeds `WITNESS_KEEP`, so the bound is a check rather
     than a comment.

All five committed tests pass with `audit verdict PASS over checks W-a to W-e`.

## 3. The finding, which is the 10-05 fault one axis over

`run_axis_audit.py` reads the committed transcript offline — the 2026-10-02
pattern, so it stays checkable without the toolchain and audits the artefact a
reviewer would actually read — and measures stimulus diversity per cell.

**9 of 27 cells are hit more than once and closed by a single repeated
stimulus every time.** The clearest case is the entire payload coverpoint:

| cell | times closed | closing stimulus |
|---|---|---|
| `cp_tx_data.zero` | 3 | `WR addr=0x3 data=0x00` |
| `cp_tx_data.low` | 3 | `WR addr=0x3 data=0x3c` |
| `cp_tx_data.mid` | 3 | `WR addr=0x3 data=0xa5` |
| `cp_tx_data.high` | 3 | `WR addr=0x3 data=0xd2` |
| `cp_tx_data.ones` | 3 | `WR addr=0x3 data=0xff` |
| `cp_rx_error.parity` | 2 | `frame data=0x7e parity_ok=False` |
| `cp_reg_access.wr_baud` | 7 | `WR addr=0x2 data=0x00` |
| `cp_reg_access.wr_int` | 7 | `WR addr=0x5 data=0x03` |
| `cp_parity_mode.none` | 5 | `WR addr=0x0 data=0x01` |

`cp_tx_data`'s bins are **ranges** — `low` is `[0x01, 0x3f]`, `mid` is
`[0x40, 0xbf]`, `high` is `[0xc0, 0xfe]` — and each range is represented by
exactly one value, three times over. The milestone test reports **100.0 %
functional coverage**.

**The collector is not wrong.** Reporting 100 % bin coverage for a directed
suite that closes each bin with one payload is an accurate report of what was
run. The gap is in what the number licenses a reader to believe, and that is
exactly 2026-10-05's fault — *a figure printed beside the thing it does not
measure* — shifted one axis over. 10-05's instance was a denominator; this one
is a figure that measures what it says (**bins touched**) sitting where a
reader will read the answer to a different question (**bins exercised**).

### 3.1 A methodological result that fell out of the same run

The audit reads **all five tests** rather than the milestone alone, and that
turns out to be load-bearing. In the milestone test `cp_rx_error.frame` is
closed three times by `0xc3` and looks like a tenth monotonous cell. The
baud-tolerance tests close it with `0x01` and `0x55`, so across the suite it
has three distinct closers. **A per-test run-axis measurement would have
produced a false finding here**, and nothing in the per-test artefact would
have shown it. The run axis is a property of a *suite*, not of a test.

### 3.2 What the measurement cannot conclude, stated before the numbers

Witnesses are bounded, so diversity is computed over a **prefix**: 7 of the 27
cells are truncated in at least one test. A measured diversity of 1 proves
that *the sample that closed the cell and its first three successors were
identical*; it does not prove the cell is never hit by anything else. Every
number is a **lower bound** and R6 asserts that the truncation is real, so the
labelling is not decorative.

**The repair is named and is this item's successor:** the collector should keep
a bounded **set of distinct payload signatures** per cell alongside its
first-N witnesses. That makes diversity exact at the same log cost, because
the set stops growing once the stimulus stops varying — which is precisely the
case being detected.

No diversity **target** is proposed. Choosing one changes a sign-off criterion
and is a reviewer's decision of the same kind as F7's goal and the
cross-gating decision, both deliberately still open.

## 4. The more useful half of the day: the harness's own detector was wrong

The mutation harness killed 5 of 5 on its first run and **misattributed four
of them.**

`verdict()` matched `(W-[a-e]) FAILED`. The audit's summary line read
`W-a..W-e FAILED`. So the regex matched `"W-e FAILED"` *inside the summary*,
and every mutant came back with `W-e` in its killer column — crediting the one
check that detects a log-growth fault with four detections of correctness
faults it is structurally blind to.

Nothing in the pass/fail result was wrong. All five mutants were genuinely
killed. **The attribution was wrong for four of five rows, and attribution is
precisely the quantity a mutation harness exists to report** — "which check
caught this" is the whole value of the killer column, and a run-axis audit
built on a misattributed detector would inherit the error.

What gave it away was an arithmetic disagreement **inside one row**: N1 showed
three `W-` tags beside `UVM_ERROR=2`. Three detections cannot come from two
errors.

Fixed in two places, and both are needed:

- the regex is anchored on the **colon** the error form always carries
  (`"W-c FAILED: cells where ..."`), which the summary never has;
- the summary line was reworded to `audit verdict PASS over checks W-a to
  W-e`, so it contains no `W-x` token at all.

**The rule, which is new to this repository and is now stated in both files:**

> A summary line must not be parseable as one of the things it summarises.

This belongs beside 2026-10-01's item — name what a check compares against in
a way that cannot drift — but it is a different failure. 10-01 was about a
reference that moved. This is about a *detector that over-reported*, and
over-reporting is the harder direction to notice, because the headline number
(5 of 5) was correct and only the explanation beneath it was false.

## 5. What the mutation harness measures, and one honest limit on W-d

| mutant | fault | killed by | UVM_ERROR |
|---|---|---|---|
| N1 | a bin incremented without `_hit()` | W-a, W-c | 2 |
| N2 | the witness string drops ordinal + time | W-d | 1 |
| N3 | `witness_total` stops accumulating | W-c | 1 |
| N4 | the witness filed under the **wrong cell**, counts still correct | W-a, W-b, W-c | 3 |
| N5 | the `WITNESS_KEEP` bound removed | W-e | 1 |
| B | control: f-string instead of `%`-format | *survived* | 0 |

Each row's `UVM_ERROR` count now equals its number of `W-` tags, which is the
arithmetic the first run failed. N1 and N3 are both W-c deliberately: the same
fault reached from the two sides of the equality W-c asserts, so a harness in
which only one died would mean W-c compares a quantity with itself. N4 is the
one a reader cannot catch by inspection — every count stays correct and only
the witness is misfiled — and it is the fault that would corrupt a run-axis
audit while leaving the coverage report flawless.

**The limit on W-d.** N2 is only caught because several cells in *this*
environment are closed by the same payload every time. Under constrained-random
payloads the item text would differ between samples and N2 would **survive**.
W-d is sound — the ordinal makes duplicates impossible by construction — but
its mutation-detection power is **stimulus-dependent**, which is the
2026-09-28 observer item (a check whose strength depends on what it is run
against) in a new place. Recorded rather than claimed away.

## 6. The toolchain, which had not been exercised for three sessions

2026-10-05 flagged that the previous three sessions were pure python over
committed logs, so `tools/setup_iverilog.sh` and the uvm-python stack had been
untested since 2026-10-03 — "worth noting as a gap rather than as good news".
Both were exercised today and both work, as did both 2026-10-03 gotchas:

- `source tools/setup_iverilog.sh` **without a pipe** (piping runs it in a
  subshell and the `iverilog`/`vvp` shell functions vanish);
- the install recipe of
  `notes/2026-09-06-uvm-python-toolchain-resolution.md` — `python-constraint`
  with `--use-pep517`, then `cocotb<2.0` (resolved to 1.9.2), then
  `uvm-python`.

One new environment fact worth recording: this ran on the device VM at **Python
3.10.12**, which is the right target for `cocotb<2.0`. The graphene repository
in the same automation cannot run there at all — its modules use PEP 701
nested-quote f-strings and need 3.12+ — so the two repositories in this
automation now require **different interpreters**, and this one is the only one
the device VM can execute.

Full regression after all of today's changes: 3 model checks (11 + 24 + 6
checks) and 5 UVM tests, all pass.
