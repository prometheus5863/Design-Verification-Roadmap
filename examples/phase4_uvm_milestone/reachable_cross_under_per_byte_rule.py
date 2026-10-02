#!/usr/bin/env python3
"""
reachable_cross_under_per_byte_rule.py -- 2026-10-02

THE 2026-10-01 TOP ITEM.  vplan v8's F7 coverage goals were derived from a
TWO-byte exclusion, and 10-01 replaced that exclusion with a NINE-byte one.
Until the goals are re-derived, F7's coverage goal and F7's admissibility rule
disagree about which bytes exist -- which is the one place 10-01's result left a
committed sign-off criterion arithmetically stale.

WHAT 10-01 ESTABLISHED, AND WHAT THIS DOES WITH IT
--------------------------------------------------
v7 compared a per-byte observer limit against ONE aggregate DUT number measured
over the pair {0x01, 0x80}.  A pair window is an intersection over its bytes, so
it is never wider than any member: substituting it for the byte's own window
understates the DUT, and an understated contained-set makes the containing set
look adequate.  The error has a known sign and it is the unsafe one.

Asked per byte:

    observer limit = (1/2) / g_first        g_first = 1 + ctz(b)
    DUT slow limit = (1/2 + p) / span       span    = index of the LAST
                                              transition in [0, d0..d7, 1]
    containment   <=>  span / g_first  >=  1 + 2p

The framed stream starts at 0 and ends at 1, so span >= g_first always, with
equality exactly when the stream has a single transition -- and there
containment needs p <= 0, which no receiver that samples after an edge can
give.  Nine bytes.  The admissible set is 247/256, not 252/256.

This module re-derives the F7 coverage goals under that exclusion.  It does NOT
re-measure anything: `g_first` comes from the committed exhaustive-measurement
CSV via payload_coverage_model, and the primitives (framed_bits,
transition_count, g_first_of, classify) are IMPORTED from the committed model
rather than re-typed, per the 09-24 anchored-comparison rule.  Re-typing them
here would make this file agree with the model by construction and tell us
nothing.

TWO REGRESSION ANCHORS AGAINST COMMITTED NUMBERS
------------------------------------------------
Before computing anything new, this file must reproduce the two numbers v8
committed under the OLD rule: 23 reachable cells of 35, and closure in 703
draws at seed 20260930.  If it cannot reproduce those, its new numbers are not
comparable with them and nothing below means anything.  This is 09-30's rule --
a control has to sit where the failure enters -- applied to a re-derivation: the
failure that matters here is "the new enumeration is not the old one with a
bigger exclusion", and the place it enters is the enumerator itself.

Run:  python3 reachable_cross_under_per_byte_rule.py
"""

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import payload_coverage_model as M      # noqa: E402  -- see the note above

# Committed numbers this file must reproduce before it is allowed to be
# believed.  Both come from vplan v8 / AUTOMATION_LOG 2026-09-30.
V8_REACHABLE_CELLS = 23
V8_FULL_GRID = 35
V8_CLOSURE_DRAWS = 703
V8_CLOSURE_SEED = 20260930
V8_TRANSITION_BINS = 5
V8_GFIRST_BINS = 7

CLOSURE_CAP = 200000
SEED_SWEEP = (1, 2, 3, 20260930, 20261002)

_PASS = []
_FAIL = []


def check(label, ok, detail=""):
    (_PASS if ok else _FAIL).append(label)
    print("  [%s] %s" % ("PASS" if ok else "FAIL", label))
    if detail:
        for line in str(detail).rstrip("\n").split("\n"):
            print("        " + line)
    return ok


# ---------------------------------------------------------------------------
# The one primitive the committed model does not have
# ---------------------------------------------------------------------------
def span_of(byte):
    """Index of the LAST transition in the framed stream [0, d0..d7, 1].

    The observer's first assigned gap ends at g_first; its last ends at span.
    payload_coverage_model has g_first_of and transition_count but not this,
    because before 10-01 nothing needed the position of the last edge -- the
    DUT's limit was taken as a single aggregate number.
    """
    bits = M.framed_bits(byte)
    last = 0
    for i in range(1, len(bits)):
        if bits[i] != bits[i - 1]:
            last = i
    return last


def inadmissible_by_geometry():
    """span == g_first: the containment inequality degenerates to p <= 0."""
    return {b for b in range(256) if span_of(b) == M.g_first_of(b)}


def inadmissible_by_transitions():
    """Exactly one transition in the framed stream."""
    return {b for b in range(256) if M.transition_count(b) == 1}


def inadmissible_by_closed_form():
    """256 - 2^k for k = 0..8.

    A single-transition stream must be 0 (start), then 0^k 1^(8-k) over the
    data bits, then 1 (stop).  With LSB-first transmission that payload is
    sum(2^i for i >= k) = 256 - 2^k.  Third route, and the only one that is
    arithmetic rather than a scan, so it cannot share a scanning bug with the
    other two.
    """
    return {(256 - (1 << k)) & 0xFF for k in range(M.N_DATA + 1)}


# ---------------------------------------------------------------------------
# Enumeration and closure, both parameterised by the exclusion
# ---------------------------------------------------------------------------
def reachable_cross(excluded):
    """{(g_first, transitions): [witness bytes]} over the non-excluded set."""
    out = {}
    for b in range(256):
        if b in excluded:
            continue
        out.setdefault((M.g_first_of(b), M.transition_count(b)), []).append(b)
    return out


def closure_draws(excluded, seed, cap=CLOSURE_CAP):
    """Draws a uniform generator over the legal set needs to close the cross."""
    reach = reachable_cross(excluded)
    need = set(reach)
    legal = [b for b in range(256) if b not in excluded]
    rng = random.Random(seed)
    hit = set()
    n = 0
    while n < cap:
        b = rng.choice(legal)
        n += 1
        hit.add((M.g_first_of(b), M.transition_count(b)))
        if need <= hit:
            return n, len(reach), len(legal)
    return None, len(reach), len(legal)


def grid_of(reach):
    gs = sorted({k[0] for k in reach})
    ts = sorted({k[1] for k in reach})
    return gs, ts, len(gs) * len(ts)


def main():
    rows = M.load_measured()
    print("=" * 76)
    print("F7 REACHABLE CROSS UNDER THE 2026-10-01 PER-BYTE RULE")
    print("Re-deriving vplan v8's coverage goals under a nine-byte exclusion")
    print("=" * 76)

    # -------------------------------------------------------------------
    print("\n" + "-" * 76)
    print("SECTION 1 -- the nine, derived three independent ways")
    print("-" * 76)
    geo = inadmissible_by_geometry()
    tra = inadmissible_by_transitions()
    clo = inadmissible_by_closed_form()
    print("  by geometry (span == g_first) : %s" %
          " ".join("0x%02X" % b for b in sorted(geo)))
    print("  by transitions (count == 1)   : %s" %
          " ".join("0x%02X" % b for b in sorted(tra)))
    print("  by closed form (256 - 2^k)    : %s" %
          " ".join("0x%02X" % b for b in sorted(clo)))
    check("all three derivations give the same set",
          geo == tra == clo,
          "geometry^transitions = %s\ngeometry^closed = %s"
          % (sorted(geo ^ tra), sorted(geo ^ clo)))
    check("the set has nine members, so the admissible set is 247/256",
          len(geo) == 9, "|inadmissible| = %d, admissible = %d"
          % (len(geo), 256 - len(geo)))
    NINE = geo

    print("\n  per-byte table (g_first from the committed CSV, not re-typed):")
    print("    %-6s %-8s %-6s %-10s" % ("byte", "g_first", "span", "span/g"))
    for b in sorted(NINE):
        g = rows[b]["g_first"]
        check_g = M.g_first_of(b)
        print("    0x%02X   %-8d %-6d %-10.4f%s"
              % (b, g, span_of(b), span_of(b) / float(g),
                 "" if g == check_g else "  <-- CSV/derivation MISMATCH"))
    mism = [b for b in sorted(NINE) if rows[b]["g_first"] != M.g_first_of(b)]
    check("the committed CSV's g_first agrees with the derivation on all nine",
          not mism, "mismatched: %s" % [hex(b) for b in mism])
    check("span/g_first is exactly 1 for every one of the nine",
          all(span_of(b) == rows[b]["g_first"] for b in NINE),
          "which is what collapses the containment inequality to p <= 0")

    # -------------------------------------------------------------------
    print("\n" + "-" * 76)
    print("SECTION 2 -- REGRESSION ANCHORS: reproduce v8's committed numbers")
    print("-" * 76)
    OLD = {b for b in range(256) if M.classify(b, rows) == M.INADMISSIBLE}
    print("  the live model's exclusion (payload_coverage_model.classify): %s"
          % " ".join("0x%02X" % b for b in sorted(OLD)))
    r_old = reachable_cross(OLD)
    gs_o, ts_o, grid_o = grid_of(r_old)
    print("  reachable cells %d of grid %d   g_first bins %s   transition bins %s"
          % (len(r_old), grid_o, gs_o, ts_o))
    check("reproduces v8's %d reachable cells" % V8_REACHABLE_CELLS,
          len(r_old) == V8_REACHABLE_CELLS,
          "got %d" % len(r_old))
    check("reproduces v8's %dx%d = %d full grid" % (len(gs_o), len(ts_o), V8_FULL_GRID),
          grid_o == V8_FULL_GRID, "got %d" % grid_o)
    check("reproduces v8's %d-bin transition coverpoint" % V8_TRANSITION_BINS,
          len(ts_o) == V8_TRANSITION_BINS, "got %d: %s" % (len(ts_o), ts_o))
    check("reproduces v8's %d/%d g_first goal" % (V8_GFIRST_BINS, V8_GFIRST_BINS),
          len(gs_o) == V8_GFIRST_BINS, "got %d: %s" % (len(gs_o), gs_o))
    n_old, _, legal_old = closure_draws(OLD, V8_CLOSURE_SEED)
    print("  closure at seed %d: %s draws over %d legal bytes"
          % (V8_CLOSURE_SEED, n_old, legal_old))
    check("reproduces v8's %d-draw closure EXACTLY at the same seed"
          % V8_CLOSURE_DRAWS,
          n_old == V8_CLOSURE_DRAWS,
          "got %s -- if this failed, the new numbers below would not be\n"
          "comparable with the committed ones and nothing here would mean\n"
          "anything" % n_old)

    # -------------------------------------------------------------------
    print("\n" + "-" * 76)
    print("SECTION 3 -- THE RESULT: the goals under the nine-byte exclusion")
    print("-" * 76)
    r_new = reachable_cross(NINE)
    gs_n, ts_n, grid_n = grid_of(r_new)
    print("                          v8 (2-byte)      v10 (9-byte)")
    print("  legal bytes             %-16d %d" % (256 - len(OLD), 256 - len(NINE)))
    print("  reachable cross cells   %-16d %d" % (len(r_old), len(r_new)))
    print("  full grid               %-16d %d" % (grid_o, grid_n))
    print("  g_first bins            %-16s %s" % (gs_o, gs_n))
    print("  transition bins         %-16s %s" % (ts_o, ts_n))
    print()
    print("  TWO committed goals move and one does not:")
    print("   * the g_first goal STAYS 7/7 -- every bin 1..7 keeps a legal")
    print("     witness, so v8's 7/7 survives the wider exclusion unchanged")
    check("the g_first goal is unchanged at 7 bins", gs_n == gs_o,
          "v8's 7/7 g_first criterion is CORRECT as committed and needs no "
          "amendment")
    print("   * the TRANSITION-COUNT goal goes 5 bins -> 4.  v8 derived 5 bins")
    print("     {1,3,5,7,9} from a parity theorem and that theorem is still")
    print("     true -- but transitions == 1 holds for EXACTLY the nine")
    print("     excluded bytes (Section 1's second derivation), so over the")
    print("     legal subset the 1 bin has no witness at all.  A 5-bin goal")
    print("     would now sit permanently at 80%.")
    check("the transition-count goal is 4 bins, not v8's 5",
          ts_n == [3, 5, 7, 9],
          "got %s; the 1 bin is unreachable because {transitions == 1} is "
          "exactly\nthe excluded set, which v8 could not have known because "
          "its exclusion\nwas two bytes neither of which exhausted that bin"
          % ts_n)
    print("   * the CROSS goal goes 23 cells -> %d, of a %d-cell grid"
          % (len(r_new), grid_n))
    print("     (a full-grid goal would report %.1f%% at actual closure)"
          % (100.0 * len(r_new) / grid_n))
    check("the cross goal is %d reachable cells" % len(r_new),
          len(r_new) == 16, "got %d" % len(r_new))

    # -------------------------------------------------------------------
    print("\n" + "-" * 76)
    print("SECTION 4 -- is the goal still SATISFIABLE?  (the v8 question, re-asked)")
    print("-" * 76)
    print("  v8 checked this rather than assuming it, and the wider exclusion")
    print("  re-opens it: an exclusion that removes a cell's only witness makes")
    print("  the goal unreachable, which is worse than a stale number.")
    n_new, tot_new, legal_new = closure_draws(NINE, V8_CLOSURE_SEED)
    print("  closure at seed %d: %s draws over %d legal bytes -> %d/%d cells"
          % (V8_CLOSURE_SEED, n_new, legal_new, tot_new, tot_new))
    check("the reduced cross still CLOSES under the nine-byte exclusion",
          n_new is not None,
          "%s draws" % n_new)
    sweep = [closure_draws(NINE, s)[0] for s in SEED_SWEEP]
    print("  across seeds %s: %s" % (list(SEED_SWEEP), sweep))
    print("    mean %.0f, min %d, max %d" % (sum(sweep) / float(len(sweep)),
                                             min(sweep), max(sweep)))
    check("closure is seed-robust (every seed closes)",
          all(x is not None for x in sweep), "%s" % sweep)
    print()
    print("  AND IT CLOSES FASTER THAN BEFORE, WHICH IS NOT THE OBVIOUS WAY")
    print("  ROUND: %d draws against v8's %d, with SEVEN FEWER legal bytes to"
          % (n_new, n_old))
    print("  draw from.  The reason is in the witness counts below -- the seven")
    print("  bytes the wider exclusion removed were themselves among the very")
    print("  rarest witnesses, so excluding them deleted the hardest cells")
    print("  rather than making the remaining ones harder to reach.")
    check("tightening the exclusion did not make closure slower",
          n_new <= n_old,
          "%d draws (9-byte rule) vs %d (2-byte rule) at the same seed"
          % (n_new, n_old))

    # -------------------------------------------------------------------
    print("\n" + "-" * 76)
    print("SECTION 5 -- single-witness cells, and which byte is now the hardest")
    print("-" * 76)
    sing_old = sorted((k, v) for k, v in r_old.items() if len(v) == 1)
    sing_new = sorted((k, v) for k, v in r_new.items() if len(v) == 1)
    print("  under v8's 2-byte rule: %d of %d cells had exactly ONE witness"
          % (len(sing_old), len(r_old)))
    for k, v in sing_old:
        mark = "  <- excluded by the 9-byte rule" if v[0] in NINE else ""
        print("      g_first=%d transitions=%d  <- 0x%02X%s" % (k[0], k[1], v[0], mark))
    print("  under the 9-byte rule: %d of %d cells have exactly ONE witness"
          % (len(sing_new), len(r_new)))
    for k, v in sing_new:
        cls = M.classify(v[0], rows)
        print("      g_first=%d transitions=%d  <- 0x%02X   (%s)"
              % (k[0], k[1], v[0], cls))
    n_excluded_singletons = sum(1 for _, v in sing_old if v[0] in NINE)
    check("the wider exclusion removed %d of v8's %d single-witness cells"
          % (n_excluded_singletons, len(sing_old)),
          n_excluded_singletons == 7,
          "which is the whole explanation of Section 4's faster closure, and\n"
          "it is measured here rather than asserted there")
    print()
    print("  THE OPEN ITEM 'is the hardest-to-cover bin ALWAYS the")
    print("  INADMISSIBLE one?' (09-30) gets a NEGATIVE and more specific")
    print("  answer. Under the 9-byte rule NOT ONE single-witness cell is")
    print("  inadmissible -- by construction, since an inadmissible byte is")
    print("  not drawn at all. But one of the four is BORDERLINE:")
    bord_sing = [v[0] for _, v in sing_new
                 if M.classify(v[0], rows) == M.BORDERLINE]
    for b in bord_sing:
        print("      0x%02X  g_first=%d span=%d -- the multi-transition byte with"
              % (b, M.g_first_of(b), span_of(b)))
        print("            the largest g_first, needing p <= 1/%d = %.4f against"
              % (M.g_first_of(b), 1.0 / M.g_first_of(b)))
        print("            a measured worst p of 0.1233: 14% of margin (10-01)")
    check("exactly one single-witness cell is BORDERLINE",
          len(bord_sing) == 1,
          "0x%02X is the ONLY witness of its cross cell, so the F7 cross goal\n"
          "CANNOT BE CLOSED WITHOUT DRAWING THE ONE BYTE WHOSE OUTCOME IS\n"
          "NEITHER PASS NOR FAIL. A sign-off criterion that requires an\n"
          "uninterpretable frame is a real finding about the goal, not about\n"
          "the DUT -- and it is new today: under v8's rule this cell had the\n"
          "same single witness, but v8 never asked which cells had one."
          % bord_sing[0] if bord_sing else "none found")

    # -------------------------------------------------------------------
    print("\n" + "-" * 76)
    print("SECTION 6 -- controls")
    print("-" * 76)
    # Positive control: the enumerator must RESPOND to the exclusion it is
    # given.  An enumerator that returns the same set for every exclusion would
    # reproduce the anchors above and still be measuring nothing.
    r_none = reachable_cross(set())
    gs_z, ts_z, grid_z = grid_of(r_none)
    print("  with NO exclusion: %d reachable cells, g_first bins %s, "
          "transition bins %s" % (len(r_none), gs_z, ts_z))
    check("C1 the enumerator responds to the exclusion (three sizes, three "
          "answers)",
          len({len(r_none), len(r_old), len(r_new)}) == 3,
          "no exclusion %d, 2-byte %d, 9-byte %d"
          % (len(r_none), len(r_old), len(r_new)))
    check("C2 g_first bins 8 and 9 exist with no exclusion and not with one",
          9 in gs_z and 8 in gs_z and 8 not in gs_n and 9 not in gs_n,
          "they are reachable only by 0x80 and 0x00, as 09-30 recorded")
    # Negative control on the closed form: it must NOT accidentally equal the
    # whole byte range or any other set of nine.
    check("C3 the closed form is nine DISTINCT bytes",
          len(inadmissible_by_closed_form()) == 9)
    # Positive control on the closure measurement: a goal that includes an
    # unreachable cell must NOT close, or the closure check proves nothing.
    reach_plus = dict(r_new)
    reach_plus[(1, 1)] = []          # the bin Section 3 just showed is dead
    need = set(reach_plus)
    legal = [b for b in range(256) if b not in NINE]
    rng = random.Random(7)
    hit = set()
    n = 0
    while n < 5000:
        b = rng.choice(legal)
        n += 1
        hit.add((M.g_first_of(b), M.transition_count(b)))
        if need <= hit:
            break
    check("C4 a goal containing the dead (g_first=1, transitions=1) cell does "
          "NOT close",
          not (need <= hit),
          "5000 draws left it at %d/%d -- so the Section 4 closure is a real\n"
          "measurement and not a loop that always terminates"
          % (len(hit & need), len(need)))

    print("\n" + "=" * 76)
    print("SUMMARY")
    print("=" * 76)
    print("  F7 admissible set            247/256  (was 252/256)")
    print("  g_first coverpoint goal      7 bins   UNCHANGED from v8")
    print("  transition coverpoint goal   4 bins   was 5 -- the 1 bin is dead")
    print("  cross goal                   %d cells  was 23, of a %d-cell grid"
          % (len(r_new), grid_n))
    print("  closure                      %d draws at seed %d, %d-%d across %d "
          "seeds" % (n_new, V8_CLOSURE_SEED, min(sweep), max(sweep), len(sweep)))
    print("  single-witness cells         4, one of them BORDERLINE (0x40)")
    for lab in _PASS:
        print("  PASS  %s" % lab)
    for lab in _FAIL:
        print("  FAIL  %s" % lab)
    print("\nTOTAL: %d passed, %d failed" % (len(_PASS), len(_FAIL)))
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
