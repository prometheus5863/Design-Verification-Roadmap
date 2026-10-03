#!/usr/bin/env python3
"""
witness_soundness.py -- 2026-10-03

THE 2026-10-02 TOP ITEM, AND IT TURNS OUT TO BE WIDER THAN 10-02 RECORDED.

10-02 found that F7's cross goal cannot be closed without drawing `0x40`, the
one BORDERLINE byte, because `0x40` is the sole witness of the cross cell
(g_first = 7, transitions = 3).  It filed that as a conflict between a sign-off
criterion and F7's evidence rule, on one cell of one coverpoint, created that
day by the nine-byte exclusion.

Two of those three claims are wrong, and this module shows it by measurement.

WHAT THIS ADDS: A SECOND AXIS
-----------------------------
10-02's own closing item asks for the WITNESS COUNT of every coverage bin in
this repository, because the `0x40` conflict was reachable from v8's data and
was missed by asking only how many cells are reachable.  That item is right
that cardinality is not enough.  It is not enough in a second way too.

A bin needs a witness.  It also needs an ADMISSIBLE witness.  Those are
different requirements and this file measures both:

    scarce(bin)            <=>  |witnesses(bin)| == 1
    evidence_unsound(bin)  <=>  no witness of bin is ADMISSIBLE

A scarce bin is expensive to close.  An evidence-unsound bin cannot be closed
by an interpretable frame AT ALL -- every byte that reaches it is a byte whose
own F7 outcome is neither pass nor fail.  Scarcity is about cost.  Soundness is
about whether closing the bin means anything.  Section 5 shows the two axes are
independent in this very data, with a witness for each of the three populated
quadrants, so neither predicate can be inferred from the other.

THE THREE RESULTS
-----------------
1.  The conflict is NOT confined to the cross.  `g_first` bin 7 has exactly one
    legal witness under the nine-byte rule and that witness is `0x40`, so the
    `g_first` coverpoint has an evidence-unsound bin too.  v10's Amendment 1
    states that the 7/7 `g_first` goal "is CORRECT as committed and needs no
    amendment", and stated it positively and deliberately.  Its cardinality
    claim is exactly right -- Section 3 reproduces it as a PASS -- and its
    sign-off claim does not follow from it.

2.  The conflict DOES NOT DATE FROM 10-02.  Over all 256 bytes, `g_first` bin 7
    is reached only by `0x40` and `0xC0`, and v7 (09-29) recorded BOTH as
    borderline.  So `g_first` bin 7 has been evidence-unsound under v8's
    two-byte rule, and under no exclusion at all, since the coverpoint was
    built on 09-30.  The nine-byte exclusion did not create the defect; it
    removed `0xC0` and so turned a two-witness unsound bin into a one-witness
    unsound bin, which is the only reason a scarcity scan would now see it.
    Three consecutive revisions re-derived this cross and none asked the
    question of the coverpoint.

3.  The ways out are NOT three, and two of them are indistinguishable from
    every number this plan reports.  Section 6 computes four.  Excluding `0x40`
    (W1) and merging `g_first` 7 into a `6+` bin (W3) produce the SAME goal --
    6 bins, 4 bins, 15 reachable cells of 24, no unsound bin, the same scarce
    set -- and Section 7 shows a 40-seed closure sweep does not separate them
    either.  They differ only in whether `0x40` is still DRIVEN.  A reviewer
    reading "15 of 24" cannot tell whether the DUT is still exercised there.

METHOD NOTE
-----------
Primitives are IMPORTED from `payload_coverage_model` and the exclusion
derivations from `reachable_cross_under_per_byte_rule`, never re-typed, per the
09-24 anchored-comparison rule: a file that re-derives what it is checking
agrees with it by construction and reports nothing.  Section 2 reproduces four
committed numbers before any new one is computed, per 09-30 -- a control has to
sit where the failure enters, and the failure that matters here is "this
instrument is not measuring the committed coverage model".

Run:  python3 witness_soundness.py
"""

import os
import random
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import payload_coverage_model as M                      # noqa: E402
import reachable_cross_under_per_byte_rule as R         # noqa: E402

# Committed numbers this file must reproduce before it may be believed.
V8_CELLS, V8_GRID, V8_DRAWS = 23, 35, 703
V10_CELLS, V10_GRID, V10_DRAWS = 16, 28, 663
CLOSURE_SEED = 20260930
V8_SCARCE_CELLS = 11       # 10-02 Section 5: 11 of 23 had exactly one witness
V10_SCARCE_CELLS = 4       # 10-02 Section 5: 4 of 16
NO_EXCL_CELLS = 25         # 10-02 control C1
CLOSURE_CAP = 200000
SWEEP_SEEDS = tuple(range(1, 41))

_PASS, _FAIL = [], []


def check(label, ok, detail=""):
    (_PASS if ok else _FAIL).append(label)
    print("  [%s] %s" % ("PASS" if ok else "FAIL", label))
    if detail:
        for line in str(detail).rstrip("\n").split("\n"):
            print("        " + line)
    return ok


def head(n, title):
    print("\n" + "-" * 76)
    print("SECTION %s -- %s" % (n, title))
    print("-" * 76)


# ---------------------------------------------------------------------------
# THE INSTRUMENT
# ---------------------------------------------------------------------------
IDENT = lambda g: g                      # noqa: E731  -- v8/v10 g_first binning
CAP6 = lambda g: min(g, 6)               # noqa: E731  -- W3's merged 6+ bin


def classify_all(rows):
    """{byte: ADMISSIBLE|BORDERLINE|INADMISSIBLE} from the committed model."""
    return {b: M.classify(b, rows) for b in range(256)}


def witnesses(binner, excluded):
    """{bin_value: [bytes that reach it]} over the non-excluded population.

    `binner` maps a byte to its bin value, so one function serves the g_first
    coverpoint, the transition coverpoint and their cross.
    """
    out = {}
    for b in range(256):
        if b in excluded:
            continue
        out.setdefault(binner(b), []).append(b)
    return out


def soundness(wit, cls):
    """Per-bin witness census: total, and one count per admissibility class."""
    rep = {}
    for k, bs in wit.items():
        rep[k] = {
            "n": len(bs),
            "adm": sum(1 for b in bs if cls[b] == M.ADMISSIBLE),
            "bord": sum(1 for b in bs if cls[b] == M.BORDERLINE),
            "inadm": sum(1 for b in bs if cls[b] == M.INADMISSIBLE),
            "bytes": bs,
        }
    return rep


def scarce(rep):
    """Bins with exactly one witness -- 10-02's axis.  Cost."""
    return [k for k in sorted(rep) if rep[k]["n"] == 1]


def unsound(rep):
    """Bins with no ADMISSIBLE witness -- the new axis.  Meaning."""
    return [k for k in sorted(rep) if rep[k]["adm"] == 0]


def closure_draws(excluded, binner, seed, cap=CLOSURE_CAP):
    """Uniform draws over the legal set needed to hit every reachable bin."""
    legal = [b for b in range(256) if b not in excluded]
    need = set(binner(b) for b in legal)
    rng = random.Random(seed)
    hit, n = set(), 0
    while n < cap:
        n += 1
        hit.add(binner(rng.choice(legal)))
        if need <= hit:
            return n
    return None


# Bin functions.  g_first and transition_count come from the committed model.
def g_bin(gmap):
    return lambda b: gmap(M.g_first_of(b))


def t_bin(b):
    return M.transition_count(b)


def x_bin(gmap):
    return lambda b: (gmap(M.g_first_of(b)), M.transition_count(b))


# ---------------------------------------------------------------------------
def main():
    rows = M.load_measured()
    cls = classify_all(rows)
    nine = R.inadmissible_by_closed_form()
    two = {0x00, 0x80}
    none = set()

    print("=" * 76)
    print("WITNESS SOUNDNESS: DOES EVERY F7 COVERAGE BIN HAVE AN ADMISSIBLE")
    print("WITNESS?  (the 2026-10-02 top item, and it is wider than recorded)")
    print("=" * 76)

    # -----------------------------------------------------------------
    head(1, "the instrument, and an exactly-known value to anchor it")
    print("  A bin census partitions the legal set: every legal byte lands in")
    print("  exactly one bin of each coverpoint, so the witness counts must sum")
    print("  to the legal-set size EXACTLY.  Not approximately -- this is the")
    print("  arithmetic identity the whole instrument rests on, and a binner")
    print("  that double-counts or drops a byte fails it by construction.")
    for ename, excl in (("none", none), ("2-byte", two), ("9-byte", nine)):
        legal = 256 - len(excl)
        for cname, binner in (("g_first", g_bin(IDENT)), ("transitions", t_bin),
                              ("cross", x_bin(IDENT))):
            rep = soundness(witnesses(binner, excl), cls)
            tot = sum(r["n"] for r in rep.values())
            check("partition identity: %s coverpoint, %s exclusion" % (cname, ename),
                  tot == legal, "sum of witness counts %d == legal set %d" % (tot, legal))
            cl = sum(r["adm"] + r["bord"] + r["inadm"] for r in rep.values())
            check("class census is complete: %s / %s" % (cname, ename), cl == legal,
                  "adm+bord+inadm %d == legal set %d" % (cl, legal))

    print()
    print("  the committed classifier over all 256 bytes:")
    for k in (M.ADMISSIBLE, M.BORDERLINE, M.INADMISSIBLE):
        bs = [b for b in range(256) if cls[b] == k]
        print("    %-13s %3d  %s" % (k, len(bs),
              "" if len(bs) > 4 else " ".join("0x%02X" % b for b in bs)))
    check("the classifier has exactly two BORDERLINE bytes",
          sorted(b for b in range(256) if cls[b] == M.BORDERLINE) == [0x40, 0xC0],
          "0x40 and 0xC0 -- both recorded as borderline by v7 on 09-29, which is\n"
          "why Section 4 can say this defect predates the nine-byte rule")

    # -----------------------------------------------------------------
    head(2, "REGRESSION ANCHORS: reproduce what v8 and v10 committed")
    xr8 = soundness(witnesses(x_bin(IDENT), two), cls)
    xr10 = soundness(witnesses(x_bin(IDENT), nine), cls)
    xr0 = soundness(witnesses(x_bin(IDENT), none), cls)
    check("reproduces v8's 23 reachable cross cells", len(xr8) == V8_CELLS,
          "got %d" % len(xr8))
    check("reproduces v10's 16 reachable cross cells", len(xr10) == V10_CELLS,
          "got %d" % len(xr10))
    check("reproduces 10-02's no-exclusion control (25 cells)", len(xr0) == NO_EXCL_CELLS,
          "got %d" % len(xr0))
    d8 = closure_draws(two, x_bin(IDENT), CLOSURE_SEED)
    d10 = closure_draws(nine, x_bin(IDENT), CLOSURE_SEED)
    check("reproduces v8's 703-draw closure at seed %d" % CLOSURE_SEED, d8 == V8_DRAWS,
          "got %s" % d8)
    check("reproduces v10's 663-draw closure at seed %d" % CLOSURE_SEED, d10 == V10_DRAWS,
          "got %s" % d10)
    check("reproduces 10-02's single-witness cell counts (11 of 23, 4 of 16)",
          len(scarce(xr8)) == V8_SCARCE_CELLS and len(scarce(xr10)) == V10_SCARCE_CELLS,
          "got %d of %d and %d of %d" % (len(scarce(xr8)), len(xr8),
                                         len(scarce(xr10)), len(xr10)))
    print("        if any anchor above had failed, nothing below would be")
    print("        comparable with the committed goals and none of it would mean")
    print("        anything -- which is the 09-30 rule applied to an instrument")

    # -----------------------------------------------------------------
    head(3, "THE RESULT: soundness of every F7 bin, three coverpoints x three rules")
    for ename, excl in (("no exclusion", none), ("v8 2-byte", two), ("v10 9-byte", nine)):
        print("\n  --- %s (legal %d) ---" % (ename, 256 - len(excl)))
        for cname, binner in (("g_first", g_bin(IDENT)), ("transitions", t_bin),
                              ("cross", x_bin(IDENT))):
            rep = soundness(witnesses(binner, excl), cls)
            u, s = unsound(rep), scarce(rep)
            print("    %-11s bins=%-3d scarce=%-2d UNSOUND=%-2d %s"
                  % (cname, len(rep), len(s), len(u),
                     ("<- " + ", ".join(str(k) for k in u)) if u else ""))
            for k in u:
                print("                 bin %s: %d witness(es) %s, 0 admissible"
                      % (k, rep[k]["n"], " ".join("0x%02X" % b for b in rep[k]["bytes"])))

    g10 = soundness(witnesses(g_bin(IDENT), nine), cls)
    check("v10's Amendment 1 is RIGHT about cardinality: every g_first bin 1..7 "
          "keeps a legal witness",
          sorted(g10) == [1, 2, 3, 4, 5, 6, 7] and all(g10[k]["n"] >= 1 for k in g10),
          "7 bins, all non-empty -- v10 is reproduced as stated, not contradicted")
    check("AND the 7/7 goal is EVIDENCE-UNSOUND: bin 7 has zero admissible witnesses",
          g10[7]["adm"] == 0 and g10[7]["n"] == 1 and g10[7]["bytes"] == [0x40],
          "bin 7's only legal witness is 0x40, which is BORDERLINE.\n"
          "Both checks above pass at once, and that is the shape of the finding:\n"
          "v10's claim is true and its conclusion does not follow from it.  A\n"
          "coverpoint goal is a claim about evidence, not about non-emptiness.")
    check("the conflict is on ONE BYTE but TWO coverpoints, not one cell",
          unsound(g10) == [7] and unsound(xr10) == [(7, 3)]
          and g10[7]["bytes"] == [0x40] and xr10[(7, 3)]["bytes"] == [0x40],
          "g_first bin 7 and cross cell (7,3) are both witnessed only by 0x40,\n"
          "so 10-02's 'the cross cannot be closed without 0x40' understates it:\n"
          "NO F7 g_first goal of 7 bins can be closed without 0x40 either")

    # -----------------------------------------------------------------
    head(4, "THE DEFECT PREDATES v9 AND v10 -- it is not a cost of the nine-byte rule")
    g8 = soundness(witnesses(g_bin(IDENT), two), cls)
    g0 = soundness(witnesses(g_bin(IDENT), none), cls)
    print("  g_first bin 7 over ALL 256 bytes: %s"
          % " ".join("0x%02X:%s" % (b, cls[b][:4]) for b in g0[7]["bytes"]))
    check("g_first bin 7 is unsound under NO exclusion", g0[7]["adm"] == 0,
          "witnesses 0x40 and 0xC0, both BORDERLINE -- the bin has never had an\n"
          "admissible witness, at any exclusion this plan has ever used")
    check("g_first bin 7 is unsound under v8's two-byte rule too", g8[7]["adm"] == 0,
          "so the 7/7 goal was evidence-unsound on 09-30, the day it was written")
    check("but it was NOT scarce under v8, which is why a scarcity scan missed it",
          g8[7]["n"] == 2 and g10[7]["n"] == 1,
          "2 witnesses under v8, 1 under v10.  The nine-byte rule removed 0xC0\n"
          "and so made a long-standing unsound bin newly SCARCE.  10-02 saw the\n"
          "scarcity because it had just started measuring scarcity, and read it\n"
          "as a new conflict created by the exclusion.  It is an old conflict\n"
          "made visible by it -- which matters, because the fix does not belong\n"
          "in the exclusion's ledger of costs.")
    print()
    print("  v8's cross had TWO unsound cells and 10-02's own table lists both:")
    for k in unsound(xr8):
        print("    %s <- %s" % (k, " ".join("0x%02X" % b for b in xr8[k]["bytes"])))
    check("both of v8's unsound cross cells appear in 10-02's single-witness list",
          set(unsound(xr8)) == {(7, 1), (7, 3)},
          "(7,1)<-0xC0 and (7,3)<-0x40.  10-02 printed both rows and even\n"
          "annotated (7,1) as 'excluded by the 9-byte rule'.  The bytes were in\n"
          "front of it; the question 'does this cell have an ADMISSIBLE witness'\n"
          "was not asked.  This is 10-02's own lesson recurring one file later.")

    # -----------------------------------------------------------------
    head(5, "SCARCITY AND SOUNDNESS ARE INDEPENDENT AXES")
    t10 = soundness(witnesses(t_bin, nine), cls)
    quad = [
        ("scarce + SOUND", "transitions bin 9", t10[9]["n"], t10[9]["adm"],
         t10[9]["n"] == 1 and t10[9]["adm"] >= 1),
        ("scarce + UNSOUND", "g_first bin 7", g10[7]["n"], g10[7]["adm"],
         g10[7]["n"] == 1 and g10[7]["adm"] == 0),
        ("abundant + SOUND", "transitions bin 3", t10[3]["n"], t10[3]["adm"],
         t10[3]["n"] > 1 and t10[3]["adm"] >= 1),
    ]
    print("  %-18s %-20s %8s %8s" % ("quadrant", "witness bin", "n", "admis"))
    for q, nm, n, a, _ in quad:
        print("  %-18s %-20s %8d %8d" % (q, nm, n, a))
    check("three quadrants are populated, so neither predicate implies the other",
          all(ok for *_, ok in quad),
          "a scarce bin can be perfectly sound (transitions 9, sole witness 0x55,\n"
          "ADMISSIBLE) and an abundant bin can in principle be unsound.  So\n"
          "10-02's witness-count item and this one are two separate audits, and\n"
          "running the first would not have found what Section 3 found.")
    print()
    print("  The fourth quadrant (abundant + UNSOUND) is EMPTY in this data.  That")
    print("  is reported, not claimed impossible: it needs a bin all of whose many")
    print("  witnesses are borderline, and there are only two borderline bytes in")
    print("  the whole population.  A DUT with a wider borderline band would have")
    print("  one, and then no scarcity scan at any threshold would find it.")

    # The structural observation the no-exclusion row makes visible.
    g0u = unsound(soundness(witnesses(g_bin(IDENT), none), cls))
    print()
    print("  AND SOUNDNESS SUBSUMES THE EXCLUSION RULE ITSELF.  With no exclusion")
    print("  the unsound g_first bins are %s: bin 7 by two BORDERLINE" % g0u)
    print("  witnesses, bins 8 and 9 by one INADMISSIBLE witness each -- and bins 8")
    print("  and 9 are exactly what v8 removed by hand as illegal_bins.  So the")
    print("  nine-byte exclusion is the special case of this audit that handles")
    print("  INADMISSIBLE witnesses, and bin 7 is the case it cannot reach, because")
    print("  a borderline byte is legal to draw.  An audit written on soundness")
    print("  would have produced v8's illegal_bins AND bin 7 in one pass.")
    check("the no-exclusion unsound set is {7, 8, 9}, and 8 and 9 are v8's own "
          "illegal_bins",
          g0u == [7, 8, 9],
          "so this instrument re-derives the hand-made exclusion as a corollary,\n"
          "which is the strongest available evidence that it is measuring the\n"
          "right property rather than a new one invented to fit 0x40")

    # -----------------------------------------------------------------
    head(6, "THE WAYS OUT, COMPUTED RATHER THAN WEIGHED")
    ways = [
        ("W0 status quo", "v10 as committed: 0x40 drawn, counted, uninterpretable",
         nine, IDENT),
        ("W1 exclude 0x40", "widen the exclusion to ten bytes; 0x40 never driven",
         nine | {0x40}, IDENT),
        ("W3 merge to 6+", "keep driving 0x40; stop giving g_first 7 its own bin",
         nine, CAP6),
    ]
    print("  %-17s %-7s %-7s %-14s %-8s %s"
          % ("option", "g bins", "t bins", "cross", "unsound", "closure @%d" % CLOSURE_SEED))
    res = {}
    for name, _, excl, gmap in ways:
        g = soundness(witnesses(g_bin(gmap), excl), cls)
        t = soundness(witnesses(t_bin, excl), cls)
        x = soundness(witnesses(x_bin(gmap), excl), cls)
        u = len(unsound(g)) + len(unsound(t)) + len(unsound(x))
        d = closure_draws(excl, x_bin(gmap), CLOSURE_SEED)
        res[name] = (len(g), len(t), len(x), len(g) * len(t), u, d, excl, gmap)
        print("  %-17s %-7d %-7d %-14s %-8d %s"
              % (name, len(g), len(t), "%d of %d" % (len(x), len(g) * len(t)), u, d))
    print()
    print("  W2 ADMIT BORDERLINE AS COVERAGE EVIDENCE is not a row above, because")
    print("  it changes no count at all -- that is precisely its cost.  Quantified:")
    nb = len(unsound(xr10))
    print("    %d of %d cross cells (%.1f%%) and %d of %d g_first bins (%.1f%%) would"
          % (nb, len(xr10), 100.0 * nb / len(xr10),
             len(unsound(g10)), len(g10), 100.0 * len(unsound(g10)) / len(g10)))
    print("    rest on a frame whose F7 outcome is neither pass nor fail, and the")
    print("    coverage report would read 100% either way.")
    print()
    print("  W4 SPLIT THE CHECK, NOT THE BIN: drive 0x40, credit the bin, and")
    print("  exclude that frame from F7's TIMING oracle while keeping it under F1's")
    print("  data-integrity oracle.  It is the only option that preserves a 7-bin")
    print("  goal.  Its cost is that the cross stops being F7 evidence throughout,")
    print("  so 'F7 cross 16/16' would mean two different things in two cells.")
    print("  Not computed here: it needs an oracle change, not a goal change.")

    check("W1 and W3 are NUMERICALLY IDENTICAL goals",
          res["W1 exclude 0x40"][:5] == res["W3 merge to 6+"][:5],
          "6 g_first bins, 4 transition bins, 15 reachable cells of a 24-cell\n"
          "grid, zero unsound bins -- for both.  They are not the same decision:\n"
          "W1 stops driving 0x40, W3 keeps driving it and stops distinguishing\n"
          "it.  W1 gives up DUT exercise to buy a clean number; W3 gives up a\n"
          "coverage distinction and keeps the exercise.")
    check("both W1 and W3 remove every unsound bin", res["W1 exclude 0x40"][4] == 0
          and res["W3 merge to 6+"][4] == 0,
          "and W0 leaves two (g_first bin 7 and cross cell (7,3))")
    check("W1 also costs a g_first BIN, not just a cross cell",
          res["W1 exclude 0x40"][0] == 6 and res["W0 status quo"][0] == 7,
          "the 7/7 goal becomes 6/6.  This is the consequence v10 could not see,\n"
          "because it had concluded that the g_first goal needed no amendment and\n"
          "so never asked what excluding 0x40 would do to it.")

    # -----------------------------------------------------------------
    head(7, "DOES ANY NUMBER SEPARATE W1 FROM W3?  a 40-seed closure sweep")
    print("  At seed %d alone the figures are %s and %s draws, which looks like a"
          % (CLOSURE_SEED, res["W1 exclude 0x40"][5], res["W3 merge to 6+"][5]))
    print("  decisive difference and is not one.  Swept over %d seeds:" % len(SWEEP_SEEDS))
    sweeps = {}
    for name in ("W0 status quo", "W1 exclude 0x40", "W3 merge to 6+"):
        _, _, _, _, _, _, excl, gmap = res[name]
        s = [closure_draws(excl, x_bin(gmap), sd) for sd in SWEEP_SEEDS]
        sweeps[name] = s
        print("    %-17s mean %4.0f  median %4.0f  min %4d  max %4d"
              % (name, statistics.mean(s), statistics.median(s), min(s), max(s)))
    w1s, w3s = sweeps["W1 exclude 0x40"], sweeps["W3 merge to 6+"]
    wins = sum(1 for a, b in zip(w1s, w3s) if a < b)
    check("closure cost does NOT separate W1 from W3",
          0.3 * len(SWEEP_SEEDS) < wins < 0.7 * len(SWEEP_SEEDS),
          "W1 is faster on %d of %d seeds, and the ranges overlap almost entirely.\n"
          "So no number this verification plan reports -- not the bin counts, not\n"
          "the cell count, not the grid, not the closure cost -- distinguishes a\n"
          "plan that still drives 0x40 from one that does not.  Only the stimulus\n"
          "log does.  The vplan must therefore name WHICH option it took; the\n"
          "coverage report cannot carry that information." % (wins, len(SWEEP_SEEDS)))
    w0s = sweeps["W0 status quo"]
    check("and the single-seed 663 -> %s speedup is seed noise, not a speedup"
          % res["W1 exclude 0x40"][5],
          statistics.mean(w1s) >= statistics.mean(w0s) * 0.85,
          "W0 mean %.0f, W1 mean %.0f over %d seeds.  Removing the hardest cell\n"
          "did not measurably speed up closure.  Recorded because the one-seed\n"
          "comparison is exactly the figure a revision would be tempted to quote,\n"
          "and 10-02's own 703->663 'closes faster' line rests on the same single\n"
          "seed -- it hedged correctly, and this is the measurement behind the\n"
          "hedge." % (statistics.mean(w0s), statistics.mean(w1s), len(SWEEP_SEEDS)))

    # -----------------------------------------------------------------
    head(8, "CONTROLS")
    allsound = dict((b, M.ADMISSIBLE) for b in range(256))
    allbord = dict((b, M.BORDERLINE) for b in range(256))
    gsound = soundness(witnesses(g_bin(IDENT), nine), allsound)
    gbord = soundness(witnesses(g_bin(IDENT), nine), allbord)
    check("C1 the instrument responds to the EXCLUSION (three sizes, three answers)",
          (len(xr0), len(xr8), len(xr10)) == (25, 23, 16),
          "no exclusion 25, 2-byte 23, 9-byte 16")
    check("C2 the instrument responds to the CLASSIFIER, positively: with every "
          "byte ADMISSIBLE no bin is unsound",
          unsound(gsound) == [],
          "so 'bin 7 is unsound' is a fact about the committed classifier and not\n"
          "a constant this file prints")
    check("C3 the instrument responds to the CLASSIFIER, negatively: with every "
          "byte BORDERLINE every bin is unsound",
          len(unsound(gbord)) == len(gbord) == 7,
          "7 of 7 -- so the instrument is not hard-coded to find exactly one")
    check("C4 the instrument responds to the BINNER: capping g_first at 6 merges "
          "exactly one bin",
          len(soundness(witnesses(g_bin(CAP6), nine), cls)) == 6 and len(g10) == 7,
          "6 bins vs 7, and the merged bin is sound where bin 7 was not")
    check("C5 scarcity and soundness are measured SEPARATELY, not aliased",
          scarce(t10) == [9] and unsound(t10) == [] and scarce(g10) == [7]
          and unsound(g10) == [7],
          "the transition coverpoint has a scarce bin and NO unsound bin; the\n"
          "g_first coverpoint has a bin that is both.  An instrument that aliased\n"
          "the two would have to report transitions bin 9 as unsound, and it does\n"
          "not.")
    cap_x = soundness(witnesses(x_bin(CAP6), nine), cls)
    check("C6 W3's merged cross really loses a cell rather than renaming one",
          len(cap_x) == 15 and (7, 3) not in cap_x and (6, 3) in cap_x,
          "15 cells; (7,3) is gone and 0x40 now lands in (6,3) alongside\n"
          "%d admissible witnesses, which is WHY the bin becomes sound"
          % cap_x[(6, 3)]["adm"])

    # -----------------------------------------------------------------
    print("\n" + "=" * 76)
    print("SUMMARY")
    print("=" * 76)
    print("  the second axis            a bin needs an ADMISSIBLE witness, not just one")
    print("  g_first 7/7 goal          cardinality CORRECT (v10), evidence UNSOUND (new)")
    print("  unsound bins under v10    g_first bin 7 and cross cell (7,3), both <- 0x40")
    print("  age of the defect         present under v8 and under NO exclusion; v7 had")
    print("                            already recorded 0x40 and 0xC0 as borderline")
    print("  what the 9-byte rule did  made an old unsound bin newly SCARCE, hence visible")
    print("  ways out                  four; W1 and W3 give identical numbers")
    print("  W1 == W3 numerically      6 bins, 4 bins, 15 of 24, 0 unsound -- for both")
    print("  what separates them       nothing this plan reports; only the stimulus log")
    print("  closure sweep             W1 faster on %d of %d seeds -- i.e. not faster"
          % (wins, len(SWEEP_SEEDS)))
    for lab in _PASS:
        print("  PASS  %s" % lab)
    for lab in _FAIL:
        print("  FAIL  %s" % lab)
    print("\nTOTAL: %d passed, %d failed" % (len(_PASS), len(_FAIL)))
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
