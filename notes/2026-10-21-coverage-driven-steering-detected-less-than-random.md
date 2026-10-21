# 2026-10-21 — The `tx_empty` prediction holds, and coverage-driven steering detected *less* than pure random

**Ranked-first item worked:** *a mutant for the `tx_empty` prediction*, ranked
first on 2026-10-18 deliberately — it is **content**, and the three sessions
before it had all spent their ranked-first item in the instrument layer.

---

## 1. The setup, and why attributability is the whole design

Two `tx_empty` predictions are live in `examples/phase6_crv_uart/uart_crv_cov_tb.v`:

```
"fill phase starts with tx_empty set"        st[1] == 1 before any push
"post-push tx_empty agrees with occupancy"   st[1] == (pushed == 0)
```

Neither had ever been mutation-tested. An untested prediction has an
**unmeasured** verdict — the 2026-09-17 lesson that started mutation testing
in this repository, when a bench passed 55/55 against deliberately broken RTL.

The trap here is specific. `tx_empty` is read in **three** places in
`rtl/uart_controller.v`: the TX engine's pop condition (`if (!tx_empty)`), the
IRQ decode, and the STATUS decode. So mutating the **wire** changes what the
DUT *does*, the RX data comparison catches it, and the report says DETECTED —
**while saying nothing whatever about whether the prediction works.**

> "Detected" and "detected by the prediction under test" are different
> verdicts, and a report that conflates them answers a weaker question than
> the one it was written to ask.

So the mutants are split:

| | what is mutated | who can see it |
|---|---|---|
| **T1** `tx_empty` stuck CLEAR | STATUS decode only | only a STATUS reader |
| **T2** `tx_empty` stuck SET | STATUS decode only | only a STATUS reader |
| **T3** `tx_empty` one entry early | STATUS decode only | only a STATUS reader |
| **T4** `tx_empty` one entry early | **the wire** | the data path |

T4 is not a fourth test of the prediction. **It is the control for the
distinction**, and the harness adjudicates every row by *which check failed
first*, so a detection by the wrong check is reported as what it is.

One confound checked and stated rather than assumed: the RTL carries
`assert(prdata[1] == tx_empty)` (property C5), which would detect T1–T3 on its
own. It sits inside `ifdef FORMAL` from line 395, and the Icarus flow compiles
without `-DFORMAL`, so it is inert here.

## 2. The matrix

Four seeds (1, 3, 5, 7), both stimulus modes.

| ID | mutant | `steer=0` random | `steer=1` coverage-driven |
|---|---|---|---|
| T1 | STATUS decode: stuck CLEAR | **4/4** | **4/4** |
| T2 | STATUS decode: stuck SET | **4/4** | **4/4** |
| T3 | STATUS decode: one entry EARLY | **4/4** | **2/4** (escapes on 1, 5) |
| T4 | WIRE: one entry early | 4/4 | 4/4 |

T1 and T2 are caught by **different** checks, and that settles a question the
census left open: the fill-phase check can only ever see `tx_empty` wrongly
**clear**, and the post-push check only ever wrongly **set** (C4 constrains
`burst_len` to [1, 8], so the post-push occupancy is never zero). **Neither
prediction subsumes the other and neither is redundant.**

T4 is detected in both modes **by the burst watchdog** — a data-path check.
Reported as NOT ATTRIBUTABLE, which is the intended outcome for the control.

## 3. The result: coverage-driven steering detected less

T3 is wrong only at occupancy 1, so it needs a burst that pushed **exactly one
byte**. The coverage-driven mode misses it on half the seeds that pure random
catches.

The mechanism, read out of `pick_config_steered` rather than guessed:

1. `burst_len` is drawn randomly from [1, 8] at the **top** of the task.
2. The coverage loops then **overwrite** it with `8`, `3` or `1` to chase the
   first unhit `cov_txq` bin.
3. The `burst_len = 1` branch fires only while `cov_txq[0]` is unhit — and
   `cov_txq[0]` is "TX FIFO seen empty", which the fill phase observes on the
   **first burst**, long before `STEER_AFTER = 24`.

So steering can only ever **remove** length-1 bursts here. It never adds one.

**The lesson is not about this mutant.** Coverage closure and defect detection
are different objectives. A generator aimed at the first unhit bin spends
stimulus it was otherwise spending on states that no bin happens to name, and
occupancy 1 is exactly such a state: `cov_txq` bins *empty / partial / full*,
and "partial" is satisfied by a burst of 2–7 just as well as by a burst of 1.

> **The coverage model cannot see the distinction the prediction depends on,
> so steering toward 100 % closure is free to walk away from it.**

This is worth carrying into the roadmap generally. A coverage-driven flow
reports progress in the one currency it can measure, and nothing in that
currency is denominated in *detection*. A 100 % closure figure and a mutation
score are not two views of the same quantity, and when they disagree the
closure figure is the one that will be believed, because it is the one on the
dashboard.

## 4. Two defects in this session's own work

- **The first draft asserted the opposite result.** It claimed steering reached
  `burst_len = 1` "by construction", because `pick_config_steered` *contains* a
  branch setting `burst_len = 1`. Reading the branch rather than the task: the
  branch is guarded by a bin that is hit immediately. **The presence of a line
  is not the firing of it** — the same shape as 2026-10-20's *naming is not
  invoking*, one level down.
- **The harness was first-failure-wins.** It took the first seed that failed,
  reported `DETECTED`, and ran `steer=1` only — so it would have printed T3
  **DETECTED** and hidden a 50 % escape rate. That is this repository's
  recorded dominant failure mode, committed **inside the harness written to
  measure a prediction's reach**. It was caught by running T3 by hand across
  both modes, not by any control in the file. `run_matrix` now reports per
  seed and per mode and names the escaping seeds.

**Both defects would have produced a green, confident, wrong report**, and
neither would have been visible in it.

## 5. Environment

Icarus Verilog 10.3 from the cached `tools/setup_iverilog.sh`; the 2026-09-17
gotchas both still apply and were both respected (do not pipe the `source`;
call the real `vvp` binary under `timeout`, since `vvp` is a shell function).
`yosys` / `sby` / `cocotb` remain absent. No live web search was used and none
was needed. The bridge was stable; every commit was pushed immediately after
commit, which is the pattern 2026-10-20 recommended after a near miss.
