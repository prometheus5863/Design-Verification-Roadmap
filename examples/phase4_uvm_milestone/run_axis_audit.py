"""
run_axis_audit.py

THE RUN AXIS, measured for the first time.

The 2026-10-05 three-axis audit of the live `UartCoverage` collector could
measure its AXIS coverage (which dimensions the metric spans) and its
EVIDENCE soundness (whether a closed cell was closed by sound evidence), and
reported the RUN axis -- *which samples actually closed each cell* -- as not
merely unmeasured but UNMEASURABLE, because the committed logs recorded only
counts.  Per-sample witnesses were added 2026-10-06 and this module is the
first measurement they make possible.

It is OFFLINE and reads only the COMMITTED simulator transcript
`uart_uvm_sim_output_2026-10-08.txt`, which is the pattern this repository
has used since 2026-10-02 for anything that must still be checkable when the
toolchain is not installed.  It therefore measures the artefact a reviewer
would read, not a fresh run that might differ from it.

WHAT THE RUN AXIS ASKS, in this repository's terms.  A coverage report that
says `cp_rx_error.frame = 3` makes two claims a reader will conflate: that
the framing-error bin is reachable, and that it has been exercised.  The
first needs one sample.  The second needs several DIFFERENT ones.  Counts
cannot tell them apart; witnesses can.

RESULT, stated up front.  Across the five committed tests, **9 of the 27
cells are hit more than once and closed by a single repeated stimulus every
time.**  The clearest case is the whole payload coverpoint: `cp_tx_data`
reports 5/5 bins hit, and *each of its five bins was closed three times by
one byte* -- `zero` by 0x00, `low` by 0x3c, `mid` by 0xa5, `high` by 0xd2,
`ones` by 0xff.  Those bins are RANGES and each range is represented by a
single value, three times over.  `cp_rx_error.parity` is likewise closed
twice by 0x7e and nothing else; `cp_reg_access.wr_baud` and `.wr_int` seven
times each by one write.

The milestone test reports **100.0 % functional coverage** and the stimulus
diversity behind a third of its cells is **one**.  That is not a defect in
the collector -- reporting 100 % for a directed suite that closes each bin
with one payload is an accurate report of what was run -- and it is
invisible in every artefact this repository committed before today.

One thing the aggregate view corrects, and it is the reason this audit reads
all five tests rather than the milestone alone: in the milestone test
`cp_rx_error.frame` is closed three times by 0xc3 and looks like another
diversity-1 cell, but the baud-tolerance tests close it with 0x01 and 0x55,
so across the suite it has three distinct closers.  A single test's witness
block would have reported that cell as monotonous and the suite's would not.

THE LIMIT THIS AUDIT DECLARED ON 2026-10-06, AND ITS REMOVAL ON 2026-10-08.
Witnesses are bounded at `WITNESS_KEEP = 4` per cell, so the diversity in
Section 2 is over the first four samples of each cell.  A prefix diversity of
1 proved that *the closing sample and its first three successors were
identical*, not that the cell is never hit by anything else -- a LOWER bound.
This audit recorded the repair as its own top open item: have the collector
keep a bounded set of DISTINCT signatures per cell beside the first-N
witnesses.

**The collector implements it as of 2026-10-08 and SECTION 2b reads it.**
Section 2's prefix numbers are retained, because the gap between prefix and
exact is itself the measurement of what the repair bought:

  * **all 9 of the prefix-diversity-1 cells are CONFIRMED exactly 1.**  The
    2026-10-06 finding survives becoming a measurement, which is the
    outcome that was not guaranteed and the reason the repair was worth
    doing rather than arguing about.
  * **7 of 27 cells had their diversity understated by the prefix**, the
    largest gap being `cp_rx_error.frame` at 7 -> 19.  So the prefix was
    not merely conservative in principle; it was wrong about a quarter of
    the cells in practice, and none of those were the cells the finding
    rested on.
  * **5 of 27 cells are still BOUNDED** -- the signature set is capped at
    `SIGNATURE_KEEP = 16` -- and the difference from the witness prefix is
    that the cap REPORTS hitting itself, per cell, with a count of the
    distinct signatures it refused.  That is the whole improvement: not an
    unbounded log, but a bound that cannot be mistaken for a measurement.

Nothing about the SUITE changed on 2026-10-08.  Only the measurement did.

Run:    python3 run_axis_audit.py
Writes: run_axis_audit_<date>.txt
"""

import collections
import datetime
import os
import re
import sys

LOG = "uart_uvm_sim_output_2026-10-08.txt"
# 2026-10-06's transcript is kept beside it and is still
# parseable by this module: the signature block is optional
# everywhere below, so this audit degrades to its original
# prefix-only form on a log that predates the collector change
# rather than failing on it.
LOG_PREFIX_ONLY = "uart_uvm_sim_output_2026-10-06.txt"

_FAIL = []
_LINES = []


def say(s=""):
    _LINES.append(s)
    print(s)


def check(tag, ok, label, detail=""):
    say("  [%s] %-5s%s%s" % ("PASS" if ok else "FAIL", tag, label,
                             ("  -- " + detail) if detail else ""))
    if not ok:
        _FAIL.append(tag)
    return ok


TEST_RE = re.compile(r"^#{4,}\s+(\S+)\s+#{4,}\s*$")
HDR_RE = re.compile(r"^\s{2}(\S+)\s+(\d+) sample\(s\), (\d+) shown\s*$")
WIT_RE = re.compile(r"^\s{6}#(\d+) t=(\d+)ps (\w+) (.*)$")
SUM_RE = re.compile(r"audit verdict (\w+) over checks W-a to W-e")
# ---- the distinct-signature block, added to the collector 2026-10-08 ----
SIG_HDR_RE = re.compile(
    r"^\s{2}(\S+)\s+(\d+) distinct, (\d+) sample\(s\), "
    r"(EXACT|BOUNDED \(\+(\d+) refused\))\s*$")
SIG_RE = re.compile(r"^\s{6}= (.*)$")
SIGSUM_RE = re.compile(r"audit verdict (\w+) over checks S-a to S-e")
COVPCT_RE = re.compile(r"TOTAL bin coverage: ([\d.]+)%")


def parse(path):
    """-> {test: {"cells": {name: {"total": n, "witnesses": [...]}} ,
                  "verdict": str, "coverage": float}}"""
    tests = {}
    cur = None
    cell = None
    sig_cell = None
    for raw in open(path, encoding="utf-8", errors="replace"):
        line = raw.rstrip("\n")
        m = TEST_RE.match(line)
        if m:
            cur = m.group(1)
            tests[cur] = {"cells": {}, "verdict": None, "coverage": None,
                          "sig_verdict": None, "sigcells": {}}
            cell = None
            sig_cell = None
            continue
        if cur is None:
            continue
        m = SUM_RE.search(line)
        if m:
            tests[cur]["verdict"] = m.group(1)
            cell = None
            sig_cell = None
            continue
        m = SIGSUM_RE.search(line)
        if m:
            tests[cur]["sig_verdict"] = m.group(1)
            cell = None
            sig_cell = None
            continue
        m = COVPCT_RE.search(line)
        if m:
            tests[cur]["coverage"] = float(m.group(1))
            continue
        m = HDR_RE.match(line)
        if m and (m.group(1).startswith("bin.")
                  or m.group(1).startswith("cross.")):
            cell = m.group(1)
            tests[cur]["cells"][cell] = {"total": int(m.group(2)),
                                         "shown": int(m.group(3)),
                                         "witnesses": []}
            continue
        m = SIG_HDR_RE.match(line)
        if m and (m.group(1).startswith("bin.")
                  or m.group(1).startswith("cross.")):
            sig_cell = m.group(1)
            tests[cur]["sigcells"][sig_cell] = {
                "n": int(m.group(2)), "total": int(m.group(3)),
                "exact": m.group(4) == "EXACT",
                "refused": int(m.group(5)) if m.group(5) else 0,
                "sigs": []}
            cell = None
            continue
        m = SIG_RE.match(line)
        if m and sig_cell:
            tests[cur]["sigcells"][sig_cell]["sigs"].append(m.group(1).strip())
            continue
        m = WIT_RE.match(line)
        if m and cell:
            tests[cur]["cells"][cell]["witnesses"].append(
                {"ord": int(m.group(1)), "t_ps": int(m.group(2)),
                 "port": m.group(3), "sig": m.group(4).strip()})
            continue
        if line.strip() == "" or line.startswith("UVM_"):
            cell = None
            sig_cell = None
    return tests


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, LOG)
    today = datetime.date.today().isoformat()

    say("run-axis audit of the LIVE UartCoverage collector")
    say("source: %s (committed transcript, read offline)" % LOG)
    say("=" * 78)

    if not os.path.exists(path):
        say("  the committed transcript is missing; nothing to audit.")
        return 1
    tests = parse(path)

    say("SECTION 1.  The transcript parses, and it is the artefact claimed")
    say("=" * 78)
    say("    %-46s %8s %7s %9s"
        % ("test", "cells", "cov %", "W verdict"))
    for t, d in tests.items():
        say("    %-46s %8d %7s %9s"
            % (t, len(d["cells"]),
               "%.1f" % d["coverage"] if d["coverage"] is not None else "-",
               d["verdict"] or "-"))
    check("R1", len(tests) == 5,
          "all five committed tests are present in the transcript",
          "found %d: %s" % (len(tests), ", ".join(tests)))
    check("R2", all(d["verdict"] == "PASS" for d in tests.values()),
          "every test's own witness audit (W-a to W-e) passed, so the "
          "witness data this module reads is internally consistent with the "
          "counts printed beside it",
          "verdicts: " + ", ".join("%s=%s" % (t, d["verdict"])
                                   for t, d in tests.items()))
    check("R3", all(d["cells"] for d in tests.values()),
          "every test emitted a non-empty witness block -- the 2026-09-27 "
          "rule, never grep a file for the absence of something without "
          "first proving the something could appear",
          "cells per test: " + ", ".join("%d" % len(d["cells"])
                                         for d in tests.values()))
    say()

    say("=" * 78)
    say("SECTION 2.  Stimulus diversity per cell (PREFIX measurement, "
        "first %s samples)" % "WITNESS_KEEP")
    say("=" * 78)
    say("  diversity = number of DISTINCT item signatures among the shown")
    say("  witnesses.  A cell with total > 1 and diversity 1 was hit")
    say("  repeatedly by the SAME stimulus: reachable, and exercised once.")
    say()

    agg = collections.OrderedDict()
    for t, d in tests.items():
        for cell, c in d["cells"].items():
            e = agg.setdefault(cell, {"total": 0, "sigs": collections.Counter(),
                                      "closers": set(), "tests": set()})
            e["total"] += c["total"]
            for w in c["witnesses"]:
                e["sigs"][w["sig"]] += 1
            if c["witnesses"]:
                e["closers"].add(c["witnesses"][0]["sig"])
            e["tests"].add(t)

    say("    %-30s %7s %5s %9s %s"
        % ("cell", "total", "div", "tests", "closing signature(s)"))
    mono = []
    for cell in sorted(agg):
        e = agg[cell]
        div = len(e["sigs"])
        if e["total"] > 1 and div == 1:
            mono.append(cell)
        closers = sorted(e["closers"])
        say("    %-30s %7d %5d %9d %s"
            % (cell, e["total"], div, len(e["tests"]),
               closers[0] if len(closers) == 1
               else "%d distinct: %s" % (len(closers), "; ".join(closers))))
    say()
    say("  cells with total > 1 and PREFIX diversity 1: %d of %d"
        % (len(mono), len(agg)))
    for c in mono:
        say("      %s  (closed %d times by: %s)"
            % (c, agg[c]["total"], next(iter(agg[c]["sigs"]))))
    check("R4", len(mono) > 0,
          "MAGNITUDE: the run axis is NON-TRIVIAL -- cells exist that the "
          "counts report as heavily hit and that one stimulus closed every "
          "time",
          "%d of %d cells (%.1f %%), aggregating %d samples -- and the "
          "collector reports 100.0 %% functional coverage in the milestone "
          "test"
          % (len(mono), len(agg), 100.0 * len(mono) / len(agg),
             sum(agg[c]["total"] for c in mono)))
    say()

    say("=" * 78)
    say("SECTION 2b.  EXACT diversity -- this audit's own top open item, closed")
    say("=" * 78)
    say("  2026-10-06 ended by naming the repair: a BOUNDED SET OF DISTINCT")
    say("  signatures per cell, kept alongside the first-N witnesses, which")
    say("  makes diversity exact at the same log cost because the set stops")
    say("  growing once the stimulus stops varying.  The collector implements")
    say("  it as of 2026-10-08 and this section reads it.")
    say()
    say("  A cell is EXACT when the bound refused no distinct signature.")
    say("  A BOUNDED cell is still a lower bound and is still labelled one --")
    say("  2026-10-03: a bound that cannot report hitting itself is not a")
    say("  bound, it is a silent truncation.")
    say()

    sigagg = collections.OrderedDict()
    for t, d in tests.items():
        for cell, c in d.get("sigcells", {}).items():
            e = sigagg.setdefault(cell, {"sigs": set(), "refused": 0,
                                         "total": 0, "tests": set()})
            e["sigs"] |= set(c["sigs"])
            e["refused"] += c["refused"]
            e["total"] += c["total"]
            e["tests"].add(t)

    if not sigagg:
        check("R7", False,
              "the transcript carries a distinct-signature block",
              "NONE FOUND.  %s predates the 2026-10-08 collector change, so "
              "this audit has degraded to its prefix-only form and Sections "
              "2b and 4 report nothing." % LOG)
    else:
        say("    %-30s %7s %7s %7s %s"
            % ("cell", "total", "prefix", "exact", "status"))
        understated, confirmed_mono, bounded = [], [], []
        for cell in sorted(sigagg):
            e = sigagg[cell]
            exact_n = len(e["sigs"])
            pref_n = len(agg[cell]["sigs"]) if cell in agg else 0
            is_exact = e["refused"] == 0
            if not is_exact:
                bounded.append(cell)
            if exact_n > pref_n:
                understated.append((cell, pref_n, exact_n))
            if cell in mono and exact_n == 1 and is_exact:
                confirmed_mono.append(cell)
            say("    %-30s %7d %7d %7d %s"
                % (cell, e["total"], pref_n, exact_n,
                   "EXACT" if is_exact else "BOUNDED (+%d refused)" % e["refused"]))
        say()

        # The cross-check between the two bookkeeping paths, at the AUDIT
        # level rather than inside the collector.  The collector's own S-d
        # checks this too; doing it again here means a transcript that was
        # edited, truncated or assembled by hand cannot pass.
        orphans = []
        for t, d in tests.items():
            for cell, c in d["cells"].items():
                sc = d.get("sigcells", {}).get(cell)
                if sc is None:
                    continue
                have = set(sc["sigs"])
                for w in c["witnesses"]:
                    full = "%s %s" % (w["port"], w["sig"])
                    if full not in have:
                        orphans.append((t, cell, full))
        check("R7", not orphans,
              "EVERY witness's stimulus appears in its cell's signature set, "
              "so the two bookkeepings agree in the committed artefact and "
              "not only inside the running collector",
              "%d witness/signature mismatch(es)%s"
              % (len(orphans),
                 "" if not orphans else ": " + "; ".join(
                     "%s %s %s" % o for o in orphans[:3])))

        monotone = [(c, p, e) for c, p, e in
                    ((c, len(agg[c]["sigs"]) if c in agg else 0,
                      len(sigagg[c]["sigs"])) for c in sorted(sigagg))
                    if e < p]
        check("R8", not monotone,
              "exact diversity is never LESS than the prefix diversity, "
              "which it cannot be if the set really is a superset of the "
              "witness prefix",
              "all %d cells satisfy exact >= prefix" % len(sigagg)
              if not monotone else
              "violations: " + ", ".join("%s %d<%d" % m for m in monotone[:4]))

        check("R9", True,
              "REPORTED, not asserted: how much the prefix measurement "
              "understated, which is the measured VALUE of the repair",
              "%d of %d cells had their diversity understated by the prefix; "
              "largest gap %s"
              % (len(understated), len(sigagg),
                 "none" if not understated else
                 "%s %d -> %d" % max(understated, key=lambda x: x[2] - x[1])))

        check("R10", len(confirmed_mono) > 0,
              "the diversity-1 finding SURVIVES becoming exact -- these cells "
              "are now known to be closed by one stimulus, not merely "
              "observed to be over a prefix",
              "%d of the %d prefix-diversity-1 cells are CONFIRMED exactly 1: "
              "%s" % (len(confirmed_mono), len(mono),
                      ", ".join(confirmed_mono[:6])
                      + (" ..." if len(confirmed_mono) > 6 else "")))

        check("R11", True,
              "REPORTED: cells the bound refused a signature for are still "
              "lower bounds, and SIGNATURE_KEEP is the knob that trades log "
              "size against exactness",
              "%d of %d cells BOUNDED%s"
              % (len(bounded), len(sigagg),
                 "" if not bounded else ": " + ", ".join(bounded[:6])))
    say()

    say("=" * 78)
    say("SECTION 3.  Is the CLOSER stable across tests?")
    say("=" * 78)
    say("  A cell closed by a different sample in every test is being")
    say("  exercised by the test suite as a whole even if each test closes it")
    say("  once.  A cell closed by the SAME sample in every test is not.")
    say()
    multi = [c for c in sorted(agg) if len(agg[c]["tests"]) > 1]
    same_closer = [c for c in multi if len(agg[c]["closers"]) == 1]
    say("    cells appearing in more than one test          : %d" % len(multi))
    say("    of those, closed by the SAME signature in all  : %d"
        % len(same_closer))
    for c in same_closer:
        say("      %-30s %d tests, closer %s"
            % (c, len(agg[c]["tests"]), next(iter(agg[c]["closers"]))))
    check("R5", True,
          "REPORTED, not asserted: the stable-closer count is a property of "
          "this directed suite and there is no threshold this repository can "
          "defend for it yet",
          "%d of %d multi-test cells share one closer (%.1f %%)"
          % (len(same_closer), len(multi),
             100.0 * len(same_closer) / len(multi) if multi else float("nan")))
    say()

    say("=" * 78)
    say("SECTION 4.  What this audit CANNOT conclude")
    say("=" * 78)
    maxshown = max((c["shown"] for d in tests.values()
                    for c in d["cells"].values()), default=0)
    truncated = [cell for cell in sorted(agg)
                 if any(tests[t]["cells"][cell]["shown"]
                        < tests[t]["cells"][cell]["total"]
                        for t in tests if cell in tests[t]["cells"])]
    say("  The witness log is bounded (largest 'shown' in the transcript:")
    say("  %d), so the diversity in Section 2 is computed over a PREFIX of"
        % maxshown)
    say("  each cell's samples.  %d of %d cells are truncated in at least one"
        % (len(truncated), len(agg)))
    say("  test, which means their true diversity is >= the number reported.")
    check("R6", len(truncated) > 0,
          "the truncation is REAL and is named, so Section 2's numbers are "
          "read as lower bounds rather than as measurements",
          "%d of %d cells truncated in at least one test: %s"
          % (len(truncated), len(agg), ", ".join(truncated[:6])
             + (" ..." if len(truncated) > 6 else "")))
    say("  THE REPAIR IS DONE (2026-10-08).  The collector keeps a bounded")
    say("  set of distinct signatures per cell and Section 2b reads it, so")
    say("  Section 2's prefix numbers are no longer the best this audit can")
    say("  do -- they are kept because the gap between prefix and exact is")
    say("  itself the measurement of what the repair bought.")
    say()
    say("  WHAT IS STILL BOUNDED, and it is a different bound.  The")
    say("  signature set is capped at SIGNATURE_KEEP per cell, so a cell")
    say("  whose stimulus keeps varying past the cap is reported BOUNDED and")
    say("  its diversity is still a lower bound.  The difference from the")
    say("  witness prefix is that the cap REPORTS hitting itself, per cell,")
    say("  with a count of what it refused.  That is the whole of the")
    say("  improvement: not an unbounded log, but a bound that cannot be")
    say("  mistaken for a measurement.")
    say()
    say("  Two things this audit also does NOT claim:")
    say("    - it does not claim the collector is wrong.  Reporting 100.0 %")
    say("      bin coverage for a directed suite that closes each bin with")
    say("      one payload is an ACCURATE report of what was run.  The")
    say("      finding is about what the number licenses a reader to")
    say("      believe, which is the 2026-10-05 fault (a figure printed")
    say("      beside the thing it does not measure) one axis over.")
    say("    - it does not claim a diversity TARGET.  Choosing one is a")
    say("      reviewer's decision of the same kind as F7's goal and the")
    say("      cross-gating decision, and is left open deliberately.")
    say("    - and it does not claim the stimulus is now diverse.  Nothing")
    say("      about the suite changed today; only the measurement did.  The")
    say("      diversity-1 cells are still diversity-1 and are now known to")
    say("      be, which makes constrained-random stimulus from a UVM")
    say("      sequence a better-posed item than it was yesterday rather")
    say("      than a closed one.")
    say()

    npass = sum(1 for l in _LINES if "[PASS]" in l)
    nfail = sum(1 for l in _LINES if "[FAIL]" in l)
    say("=" * 78)
    say("  cells audited              : %d" % len(agg))
    say("  samples behind them        : %d"
        % sum(e["total"] for e in agg.values()))
    say("  prefix-diversity-1 cells   : %d (%d samples)"
        % (len(mono), sum(agg[c]["total"] for c in mono)))
    say("  truncated cells            : %d" % len(truncated))
    if sigagg:
        n_exact = sum(1 for c in sigagg if sigagg[c]["refused"] == 0)
        say("  cells with EXACT diversity : %d of %d" % (n_exact, len(sigagg)))
        say("  prefix understated         : %d cell(s)" % len(understated))
    say("RESULT: %s -- %d checks passed, %d failed"
        % ("ALL CHECKS PASS" if not _FAIL else "FAILURES: "
           + ", ".join(_FAIL), npass, nfail))
    say("=" * 78)

    with open(os.path.join(here, "run_axis_audit_%s.txt" % today), "w") as fh:
        fh.write("\n".join(_LINES) + "\n")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
