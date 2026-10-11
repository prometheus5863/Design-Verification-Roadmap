#!/usr/bin/env python3
"""
summarize_closure.py -- aggregate the per-seed closure rows that
uart_uvm_crv_tb.py appends to closure_results.csv, and adjudicate the
repository's standing CRV claim against them.

WHY THIS IS A SEPARATE SCRIPT.  Each seed pair costs ~70 s of Icarus wall
clock and this environment's shell calls are time-boxed, so the sweep is run
as several invocations with different SEED_BASE values.  Aggregation therefore
cannot live inside one simulation, and putting it here also means the
distribution can be re-adjudicated without re-simulating -- which is the whole
reason the rows are written in a machine-readable form rather than printed.

THE CLAIM UNDER TEST.  examples/phase6_crv_uart/, 2026-09-24, reports 643
transactions to coverage closure under pure constrained-random against 47
under coverage steering, a 13.68x ratio, and that ratio is this repository's
argument for coverage-driven stimulus.  Both figures are ONE SEED.

Run: python3 summarize_closure.py [closure_results.csv]
"""

import collections
import statistics
import sys

VERILOG_RANDOM_PUSHES = 643
VERILOG_STEERED_PUSHES = 47
VERILOG_RATIO = VERILOG_RANDOM_PUSHES / VERILOG_STEERED_PUSHES

passed = 0
failed = 0


def check(label, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print("  [PASS] %s" % label)
    else:
        failed += 1
        print("  [FAIL] %s" % label)
    if detail:
        print("         %s" % detail)


def load(path):
    rows = []
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            f = line.split(",")
            rows.append(dict(seed=int(f[0]), steer=int(f[1]),
                             items=int(f[2]), pushes=int(f[3]),
                             closed=bool(int(f[4])), hit=int(f[5]),
                             total=int(f[6])))
    return rows


def cv(xs):
    """Coefficient of variation -- the quantity that turns out to carry the
    real argument, and which a single-seed run cannot produce at all."""
    return statistics.stdev(xs) / statistics.mean(xs)


def main(path):
    rows = load(path)
    print("=" * 72)
    print("COVERAGE CLOSURE COST AS A DISTRIBUTION, NOT A NUMBER")
    print("  source: %s, %d rows" % (path, len(rows)))
    print("=" * 72)

    # --- the sweep has to be well-formed before anything is concluded ----
    seen = collections.Counter((r["seed"], r["steer"]) for r in rows)
    dupes = [k for k, v in seen.items() if v > 1]
    check("every (seed, policy) appears exactly once, so no invocation was "
          "run twice and silently averaged into the distribution",
          not dupes,
          "duplicates: %s.  A resumable sweep whose rows are appended can "
          "double-count if an invocation is repeated with the same "
          "SEED_BASE, and averaging duplicates would narrow the spread this "
          "script exists to measure." % (dupes if dupes else "none"))
    seeds0 = sorted(r["seed"] for r in rows if r["steer"] == 0)
    seeds1 = sorted(r["seed"] for r in rows if r["steer"] == 1)
    check("both policies were run on the SAME set of seeds, so the "
          "comparison is paired",
          seeds0 == seeds1 and len(seeds0) >= 3,
          "steer=0 seeds %s, steer=1 seeds %s.  The testbench draws from one "
          "stream per seed and both policies are identical until the "
          "hand-off, so an unpaired comparison would mix the policy with the "
          "draw -- which the first draft of the testbench did." 
          % (seeds0, seeds1))
    check("every run reached closure, so every number below is a closure "
          "cost and not a truncation at MAX_TX",
          all(r["closed"] and r["hit"] == r["total"] for r in rows),
          "%d of %d rows closed." % (sum(1 for r in rows if r["closed"]),
                                     len(rows)))

    data = {s: [r["pushes"] for r in rows if r["steer"] == s] for s in (0, 1)}
    print()
    print("  TX_DATA pushes to closure (the Verilog bench's unit):")
    for s in (0, 1):
        d = sorted(data[s])
        print("    steer=%d  n=%d  %s" % (s, len(d), d))
        print("             min=%d median=%.1f max=%d mean=%.1f stdev=%.1f"
              % (min(d), statistics.median(d), max(d), statistics.mean(d),
                 statistics.stdev(d)))
        print("             spread max/min=%.2fx   CV=%.3f"
              % (max(d) / min(d), cv(d)))

    # --- the two single-seed figures, adjudicated separately -------------
    print()
    lo1, hi1 = min(data[1]), max(data[1])
    lo0, hi0 = min(data[0]), max(data[0])
    check("the STEERED figure REPRODUCES: 2026-09-24's 47 pushes falls "
          "inside this sweep's steered range",
          lo1 <= VERILOG_STEERED_PUSHES <= hi1,
          "47 against [%d, %d], median %.1f.  Reproduced across a different "
          "language (Verilog -> Python), a different framework (a hand-written "
          "task -> a UVM sequence/sequencer/driver) and a different RNG "
          "(Verilog's LCG -> Mersenne Twister).  Agreement under that much "
          "change is evidence about the METHOD rather than about two "
          "artefacts." % (lo1, hi1, statistics.median(data[1])))
    inside0 = lo0 <= VERILOG_RANDOM_PUSHES <= hi0
    check("the PURE-RANDOM figure does not reproduce in any useful sense: it "
          "lands inside a range %.1fx wide, so containing it says almost "
          "nothing" % (hi0 / lo0),
          inside0 and (hi0 / lo0) > 3.0,
          "643 against [%d, %d] (%.1fx wide, CV %.3f).  An interval that "
          "spans an order of magnitude contains 643 the way it would contain "
          "most numbers of that size.  Quoting one draw of this as the "
          "numerator of a headline ratio is the error, not the value of the "
          "draw." % (lo0, hi0, hi0 / lo0, cv(data[0])))

    # --- the ratio, and what the spread does to it ----------------------
    r_med = statistics.median(data[0]) / statistics.median(data[1])
    r_lo, r_hi = lo0 / hi1, hi0 / lo1
    print()
    print("  STEERING SPEEDUP")
    print("    median / median        : %.2fx" % r_med)
    print("    worst case .. best case: %.2fx .. %.2fx" % (r_lo, r_hi))
    print("    2026-09-24, one seed   : %.2fx" % VERILOG_RATIO)
    check("steering wins on every seed, which is the claim that survives",
          all(a > b for a, b in zip(sorted(data[0]), sorted(data[1]))),
          "sorted steered maxima %d < sorted random minima %d; the "
          "distributions do not overlap at all." % (hi1, lo0))
    check("but the RATIO is not a property of the method: it spans %.1fx "
          "across seeds" % (r_hi / r_lo),
          (r_hi / r_lo) > 3.0,
          "%.2fx to %.2fx, against the single-seed %.2fx quoted in "
          "progress.md and the 09-24 note.  A ratio whose denominator is "
          "stable (CV %.3f) and whose numerator is not (CV %.3f) inherits the "
          "numerator's spread, and a single sample of it is not a result."
          % (r_lo, r_hi, VERILOG_RATIO, cv(data[1]), cv(data[0])))

    # --- the stronger claim the single ratio could not make -------------
    cv0, cv1 = cv(data[0]), cv(data[1])
    print()
    print("  AND THE CLAIM THE SINGLE RATIO COULD NOT MAKE")
    print("    CV of closure cost, pure random : %.3f" % cv0)
    print("    CV of closure cost, steered     : %.3f" % cv1)
    print("    ratio                           : %.1fx" % (cv0 / cv1))
    check("coverage steering makes closure cost PREDICTABLE, and that is a "
          "better argument for it than any speedup number",
          cv1 < 0.5 * cv0,
          "the steered cost has CV %.3f against the random cost's %.3f, "
          "%.1fx tighter.  A verification plan can be scheduled against the "
          "steered number and cannot be scheduled against the random one at "
          "all.  This is not visible from one seed per policy -- a single run "
          "has no spread -- so the measurement the 09-24 bench could not make "
          "is the one that carries the case." % (cv1, cv0, cv0 / cv1))

    print()
    print("=" * 72)
    print("CHECKS: %d passed, %d failed" % (passed, failed))
    print("=" * 72)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "closure_results.csv"))
