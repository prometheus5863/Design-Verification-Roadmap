#!/usr/bin/env python3
"""Payload admissibility coverage model for the Phase 4 UART F7 checks.

WHY THIS FILE EXISTS
--------------------
vplan v7 (2026-09-29) made two sign-off criteria out of one exhaustive
measurement, and neither of them has anything to enforce it:

  (i)  0x00 and 0x80 MAY NOT CARRY F7 EVIDENCE.  The adaptive observer's baud
       budget is |eps| < 1/(2*g_first) with g_first = 1 + ctz(data), so for
       those two bytes the observer's window (555 and 625 bp) is NARROWER than
       the DUT's (675 bp slow).  A disagreement on such a frame looks exactly
       like a DUT failure and is not one.  A uniform random payload draws one
       of them in 0.78% of frames.
  (ii) 0x40 and 0xC0 are BORDERLINE, not passing.  g_first = 7 gives 714 bp
       against the DUT's 675, a margin of 39 bp, while 2026-09-25 measured one
       oversample tick of initial edge phase moving a limit by 0.69% of eps
       (= 69 bp).  The margin is inside the uncertainty, so the outcome is
       neither pass nor fail.

v7 also amended 2026-09-28's requirement that an observer state its own window:
an adaptive observer has no single window, so it must state its window AS A
FUNCTION OF WHAT IT ADAPTS TO AND COVER THAT.  That makes a ctz(data)
coverpoint a sign-off dependency rather than a nice-to-have, and it is the
repository's top open item as of 2026-09-29.

WHAT IS ANCHORED AND WHAT IS DERIVED
------------------------------------
The admissibility classes are NOT recomputed from the law.  They are derived
from the MEASURED per-byte limits in the committed
`budget_law_exhaustive_2026-09-29.txt` CSV block, read from that file.  This is
the 2026-09-24 anchored-comparison rule: re-typing 1/(2*g_first) here would
make the coverage model agree with the law by construction and tell us nothing
about whether the law's own measurement supports the two sign-off sets.  The
law is used only as a SECOND ROUTE and required to agree (V2).

THE THIRD STATE IS THE POINT
----------------------------
A coverage model with pass/fail bins cannot express (ii), and the 2026-09-26
item "apply the three-valued outcome axis to phase6_crv_uart's crosses" has
been open since.  Here the axis is intrinsic: ADMISSIBLE / BORDERLINE /
INADMISSIBLE, with INADMISSIBLE treated as an ILLEGAL bin -- something that
must RAISE when sampled, not merely be counted -- because counting it is what
lets an uninterpretable frame into an F7 pass.

WHAT THIS DOES NOT SHOW
-----------------------
Nothing new about the DUT or the observer.  It is a coverage model and its
claims are about which payloads may be used as evidence, not about whether the
UART works.
"""

import ast
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MEAS = os.path.join(HERE, "budget_law_exhaustive_2026-09-29.txt")

# The DUT's measured window, as budget_law_exhaustive.py states it.
DUT_SLOW_BP, DUT_FAST_BP = 675, 400

# 2026-09-25: one oversample tick of initial edge phase moves a measured limit
# by 0.69% of eps.  1 bp = 0.01% of eps, so that is 69 bp.  This is the only
# hand-carried number in the file and it is the one the BORDERLINE class turns
# on, so V3 gives it a negative control rather than trusting it.
PHASE_UNCERTAINTY_BP = 69

N_DATA = 8

ADMISSIBLE = "ADMISSIBLE"
BORDERLINE = "BORDERLINE"
INADMISSIBLE = "INADMISSIBLE"

_fails = []
_PASSES = [0]


def check(tag, ok, detail=""):
    print("  [%s] %s  %s" % ("PASS" if ok else "FAIL", tag, detail))
    if ok:
        _PASSES[0] += 1
    else:
        _fails.append(tag)
    return ok


# ---------------------------------------------------------------------------
# The measured table, read rather than re-derived
# ---------------------------------------------------------------------------

def load_measured(path=None):
    """
    Parse the CSV block out of the committed exhaustive-measurement log.
    Returns {byte: {'g_first','g_max','meas_slow_bp','meas_fast_bp'}}.

    Reading the committed LOG rather than re-running the measurement is
    deliberate: the log is the artefact the sign-off criterion was written
    against, so if the two ever disagree this file must notice.
    """
    path = path or MEAS
    rows = {}
    pat = re.compile(r"^0x([0-9A-Fa-f]{2}),(\d+),(\d+),"
                     r"([\d.]+),([\d.]+),(\d+),(\d+),([01]),([01]),(\d+)\s*$")
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            m = pat.match(line)
            if not m:
                continue
            b = int(m.group(1), 16)
            rows[b] = {
                "g_first": int(m.group(2)),
                "g_max": int(m.group(3)),
                "pred_A_pct": float(m.group(4)),
                "meas_slow_bp": int(m.group(6)),
                "meas_fast_bp": int(m.group(7)),
                "lawA_match": m.group(8) == "1",
                "n_edges": int(m.group(10)),
            }
    return rows


def ctz(byte):
    """Count trailing zeros, with ctz(0) == 8 for an 8-bit payload."""
    if byte == 0:
        return N_DATA
    n = 0
    while not byte & 1:
        byte >>= 1
        n += 1
    return n


def g_first_of(byte):
    """
    Bit-index of the observer's FIRST assigned gap, counted from the start
    edge.  For 8N1 LSB-first the first level change after the start bit is at
    the lowest set bit, so g_first = 1 + ctz(data), and 9 for 0x00 (the first
    change is the stop bit).
    """
    return 1 + ctz(byte)


def framed_bits(byte):
    """The 10 line levels of an 8N1 frame: start, d0..d7 LSB first, stop."""
    return [0] + [(byte >> i) & 1 for i in range(N_DATA)] + [1]


def transition_count(byte):
    """
    Adjacent-level transitions in the framed bit stream, including
    start->d0 and d7->stop.  This is the coverpoint open since 2026-09-26: it
    is the quantity the naive fixed-period recorder's error depends on, and it
    is ORTHOGONAL to g_first rather than a function of it -- which is why the
    cross below is worth measuring and not just the two margins.
    """
    bits = framed_bits(byte)
    return sum(1 for a, b in zip(bits, bits[1:]) if a != b)


def classify(byte, rows):
    """
    Three-valued admissibility, derived from the MEASURED limits.

    INADMISSIBLE: the observer's window does not contain the DUT's, so a
                  disagreement carries no information about the DUT.
    BORDERLINE:   it does contain it, but by less than the 2026-09-25 phase
                  sensitivity, so the containment itself is inside the
                  measurement uncertainty.
    ADMISSIBLE:   contained with margin.
    """
    r = rows[byte]
    slow, fast = r["meas_slow_bp"], r["meas_fast_bp"]
    if slow < DUT_SLOW_BP or fast < DUT_FAST_BP:
        return INADMISSIBLE
    if (slow - DUT_SLOW_BP) < PHASE_UNCERTAINTY_BP or \
            (fast - DUT_FAST_BP) < PHASE_UNCERTAINTY_BP:
        return BORDERLINE
    return ADMISSIBLE


# ---------------------------------------------------------------------------
# The coverage model
# ---------------------------------------------------------------------------

class PayloadAdmissibilityCoverage:
    """
    A coverpoint on g_first, a coverpoint on the framed transition count, their
    cross, and an ILLEGAL-bin mechanism that RAISES instead of counting.

    `sample()` is what a UVM coverage collector's write() would call.  It is
    kept free of any simulator dependency so the whole model is checkable on a
    bare python3, which is why this file runs in the regression ahead of the
    simulator tests (the 2026-09-29 precedent).
    """

    def __init__(self, rows, raise_on_illegal=True):
        self.rows = rows
        self.raise_on_illegal = raise_on_illegal
        self.ctz_bins = {g: 0 for g in range(1, N_DATA + 2)}   # g_first 1..9
        self.tr_bins = {}
        self.cross = {}
        self.classes = {ADMISSIBLE: 0, BORDERLINE: 0, INADMISSIBLE: 0}
        self.illegal_hits = []

    def sample(self, byte):
        cls = classify(byte, self.rows)
        self.classes[cls] += 1
        if cls == INADMISSIBLE:
            self.illegal_hits.append(byte)
            if self.raise_on_illegal:
                raise IllegalPayload(
                    "payload 0x%02X is INADMISSIBLE for F7: observer window "
                    "%d bp slow / %d bp fast does not contain the DUT's "
                    "%d/%d, so a disagreement on this frame is not evidence "
                    "about the DUT" % (byte,
                                       self.rows[byte]["meas_slow_bp"],
                                       self.rows[byte]["meas_fast_bp"],
                                       DUT_SLOW_BP, DUT_FAST_BP))
            return cls
        g, t = g_first_of(byte), transition_count(byte)
        self.ctz_bins[g] = self.ctz_bins.get(g, 0) + 1
        self.tr_bins[t] = self.tr_bins.get(t, 0) + 1
        self.cross[(g, t)] = self.cross.get((g, t), 0) + 1
        return cls

    def reachable_cross(self):
        """
        Which (g_first, transitions) pairs a LEGAL payload can produce at all.

        Enumerated over all 256 bytes rather than reasoned about, because the
        two coverpoints are not independent -- g_first fixes the low bits, which
        constrains the achievable transition count -- and a coverage goal that
        includes unreachable bins can never be met.  That is the 2026-09-26
        lesson (illegal bins fired against correct RTL for 21 frames) in its
        other direction.
        """
        out = {}
        for b in range(256):
            if classify(b, self.rows) == INADMISSIBLE:
                continue
            out.setdefault((g_first_of(b), transition_count(b)), []).append(b)
        return out

    def coverage_pct(self):
        reach = self.reachable_cross()
        hit = sum(1 for k in reach if self.cross.get(k, 0) > 0)
        return 100.0 * hit / len(reach), hit, len(reach)


class IllegalPayload(AssertionError):
    """Raised when an INADMISSIBLE payload is sampled into an F7 run."""


def _inadmissible_under(rows, slow_need, fast_need):
    """
    The INADMISSIBLE set under a hypothetical DUT window.  Used only as a
    negative control on `classify`: a classification that returns vplan v7's
    two bytes no matter what window it is given would be agreeing with v7 by
    construction.  Written as its own function rather than by rebinding the
    module constants, because rebinding a module attribute that another
    function has captured is exactly the write-only-knob fault the graphene
    repository spent 2026-09-29 and 2026-09-30 on.
    """
    out = []
    for b in rows:
        slow, fast = rows[b]["meas_slow_bp"], rows[b]["meas_fast_bp"]
        if slow < slow_need or fast < fast_need:
            out.append(b)
    return sorted(out)


# ---------------------------------------------------------------------------
def main():
    print("=" * 78)
    print("PAYLOAD ADMISSIBILITY COVERAGE MODEL -- ctz(data) coverpoint, its")
    print("illegal bins, and the cross with the framed transition count")
    print("2026-09-30.  Closes the 2026-09-29 top item (vplan v7 sign-off")
    print("dependency) and the transition-count coverpoint open since 09-26.")
    print("=" * 78)

    rows = load_measured()
    print()
    print("V0  the committed measurement is present and complete")
    check("256 bytes read from budget_law_exhaustive_2026-09-29.txt",
          len(rows) == 256, "got %d" % len(rows))

    print()
    print("V1  g_first, two independent routes, anchored to the committed CSV")
    mism = [b for b in rows if g_first_of(b) != rows[b]["g_first"]]
    check("1 + ctz(data) == the measured g_first column, 256/256",
          not mism, "mismatches: %s" % mism[:8])
    print("    (the law is used as a SECOND ROUTE only; the classes below come")
    print("     from the measured limit columns, not from 1/(2*g_first))")

    print()
    print("V2  the INADMISSIBLE set, derived from measured limits")
    inad = sorted(b for b in rows if classify(b, rows) == INADMISSIBLE)
    for b in inad:
        r = rows[b]
        print("    0x%02X  g_first=%d  slow %d bp (need %d)  fast %d bp "
              "(need %d)" % (b, r["g_first"], r["meas_slow_bp"], DUT_SLOW_BP,
                             r["meas_fast_bp"], DUT_FAST_BP))
    check("derived INADMISSIBLE set == vplan v7's {0x00, 0x80}",
          inad == [0x00, 0x80], "got %s" % ["0x%02X" % b for b in inad])
    # negative control: the derivation must be able to produce a DIFFERENT
    # answer, or agreeing with v7 means nothing.
    relaxed = _inadmissible_under(rows, 500, 300)
    tightened = _inadmissible_under(rows, 5000, 400)
    check("NEGATIVE CONTROL: a 500/300 window makes the set EMPTY",
          relaxed == [], "got %d bytes" % len(relaxed))
    # This expectation was WRONG on the first run of this file and is
    # corrected rather than removed: it was filed as "128 bytes, the g_first >= 2
    # class", forgetting that the g_first = 1 class measures 4999 bp, which is
    # also below 5000.  A 5000 bp demand excludes EVERY byte.  Recorded because
    # a negative control whose expected value is wrong is not a control.
    check("NEGATIVE CONTROL: a 5000/400 window excludes ALL 256 bytes",
          len(tightened) == 256,
          "%d bytes -- the g_first = 1 class measures 4999 bp, so even it "
          "fails a 5000 bp demand" % len(tightened))
    print("    so the classification tracks the window it is given and does")
    print("    not reproduce v7's two bytes by construction")

    print()
    print("V3  the BORDERLINE set, and the one hand-carried number")
    bord = sorted(b for b in rows if classify(b, rows) == BORDERLINE)
    for b in bord:
        r = rows[b]
        print("    0x%02X  g_first=%d  slow %d bp, margin %d bp against a "
              "%d bp phase uncertainty"
              % (b, r["g_first"], r["meas_slow_bp"],
                 r["meas_slow_bp"] - DUT_SLOW_BP, PHASE_UNCERTAINTY_BP))
    check("derived BORDERLINE set == vplan v7's {0x40, 0xC0}",
          bord == [0x40, 0xC0], "got %s" % ["0x%02X" % b for b in bord])
    print("    PHASE_UNCERTAINTY_BP = %d is the only number typed into this"
          % PHASE_UNCERTAINTY_BP)
    print("    file rather than read from the measurement, so it gets its own")
    print("    sensitivity sweep -- a threshold that produced the same answer")
    print("    for every value would not be measuring anything:")
    seen = {}
    for u in (0, 20, 39, 40, 69, 100, 200, 400):
        s = tuple(b for b in sorted(rows)
                  if classify(b, rows) != INADMISSIBLE and
                  (rows[b]["meas_slow_bp"] - DUT_SLOW_BP < u or
                   rows[b]["meas_fast_bp"] - DUT_FAST_BP < u))
        seen[u] = s
        print("      u=%3d bp -> %d borderline byte(s) %s"
              % (u, len(s), ["0x%02X" % b for b in s][:6]))
    check("the borderline set RESPONDS to the threshold (>=3 distinct sets)",
          len(set(seen.values())) >= 3,
          "%d distinct sets over 8 thresholds" % len(set(seen.values())))
    check("39 bp is the exact boundary: u=39 excludes 0x40/0xC0, u=40 "
          "includes them", seen[39] == () and seen[40] == (0x40, 0xC0),
          "confirms the 09-29 margin of 39 bp from the measured column")

    print()
    print("V4  the cross, and which bins a LEGAL payload can reach at all")
    cov = PayloadAdmissibilityCoverage(rows)
    reach = cov.reachable_cross()
    gs = sorted({g for g, t in reach})
    ts = sorted({t for g, t in reach})
    print("    g_first bins present : %s" % gs)
    print("    transition bins      : %s" % ts)
    print("    full grid %d x %d = %d cells; REACHABLE = %d"
          % (len(gs), len(ts), len(gs) * len(ts), len(reach)))
    unreach = [(g, t) for g in gs for t in ts if (g, t) not in reach]
    print("    UNREACHABLE cells (%d), enumerated over all 256 bytes rather"
          % len(unreach))
    print("    than argued: %s" % (unreach[:12],))
    check("the cross is NOT a full grid -- the two coverpoints are dependent",
          len(reach) < len(gs) * len(ts),
          "%d of %d cells reachable; a goal over the full grid could never "
          "be met" % (len(reach), len(gs) * len(ts)))
    check("every reachable cell is witnessed by an explicit byte",
          all(v for v in reach.values()))
    check("the two coverpoints are nonetheless ORTHOGONAL, not redundant",
          len(ts) > 1 and max(len(set(transition_count(b) for b in v))
                              for v in reach.values()) >= 1 and
          len({t for g, t in reach if g == 1}) > 1,
          "g_first=1 alone spans transition counts %s"
          % sorted({t for g, t in reach if g == 1}))

    print()
    print("V5  the illegal bin must RAISE, not count")
    cov2 = PayloadAdmissibilityCoverage(rows)
    raised = False
    try:
        cov2.sample(0x00)
    except IllegalPayload as exc:
        raised = True
        msg = str(exc)
    check("sampling 0x00 raises IllegalPayload", raised,
          msg[:88] if raised else "it was silently counted")
    # positive control on the mechanism: it must NOT raise on a legal byte,
    # or "raises" would be indistinguishable from "always raises".
    cov3 = PayloadAdmissibilityCoverage(rows)
    quiet = True
    try:
        cov3.sample(0x01)
    except IllegalPayload:
        quiet = False
    check("POSITIVE CONTROL: sampling 0x01 does not raise", quiet,
          "a mechanism that always raises detects nothing")
    check("and 0x01 was counted into its bins",
          cov3.cross.get((g_first_of(0x01), transition_count(0x01))) == 1)
    cov4 = PayloadAdmissibilityCoverage(rows, raise_on_illegal=False)
    for b in (0x00, 0x80, 0x01):
        cov4.sample(b)
    check("with raising disabled the illegal hits are still RECORDED",
          cov4.illegal_hits == [0x00, 0x80],
          "so a survey run can measure the rate without aborting")

    print()
    print("V6  the 0.78% figure vplan v7 quotes, recomputed")
    p_illegal = 100.0 * len(inad) / 256.0
    print("    uniform random payload draws an INADMISSIBLE byte in %.4f%% "
          "of frames" % p_illegal)
    check("matches vplan v7's 0.78%%", abs(p_illegal - 0.78) < 0.01,
          "%.4f%% = %d/256" % (p_illegal, len(inad)))
    print("    BORDERLINE adds %.4f%%, so %.2f%% of uniform frames are not"
          % (100.0 * len(bord) / 256.0, 100.0 * (len(inad) + len(bord)) / 256.0))
    print("    clean F7 evidence -- about 1 frame in 64.")

    print()
    print("V7  a constrained-random generator that excludes the illegal bins")
    print("    must still be able to CLOSE the reachable cross")
    import random
    rng = random.Random(20260930)
    cov5 = PayloadAdmissibilityCoverage(rows)
    legal = [b for b in range(256) if classify(b, rows) != INADMISSIBLE]
    draws = 0
    pct = 0.0
    while draws < 20000:
        cov5.sample(rng.choice(legal))
        draws += 1
        pct, hit, tot = cov5.coverage_pct()
        if hit == tot:
            break
    print("    %d draws from the %d legal bytes -> %.1f%% of the %d reachable"
          % (draws, len(legal), pct, tot))
    print("    cross bins")
    check("the reachable cross CLOSES under illegal-bin exclusion",
          pct == 100.0, "%.1f%% after %d draws" % (pct, draws))
    check("and no illegal payload was ever drawn", cov5.illegal_hits == [])
    # A goal stated over the FULL grid instead would not close.  Show it.
    full_grid = len(gs) * len(ts)
    check("a goal over the full %dx%d grid would report %.1f%% at closure "
          "and never reach 100%%" % (len(gs), len(ts),
                                     100.0 * len(reach) / full_grid),
          len(reach) < full_grid,
          "which is why the reachable set is enumerated and not assumed")

    print()
    print("V8  regression guard: the model must AGREE with the law's own")
    print("    per-byte verdict column in the committed measurement")
    disagree = [b for b in rows
                if rows[b]["lawA_match"] is not True]
    check("law A matched all 256 bytes in the committed run",
          not disagree, "%d rows where lawA_match == 0" % len(disagree))
    by_class = {}
    for b in rows:
        by_class.setdefault(classify(b, rows), []).append(b)
    print("    ADMISSIBLE   %3d bytes" % len(by_class.get(ADMISSIBLE, [])))
    print("    BORDERLINE   %3d bytes  %s"
          % (len(by_class.get(BORDERLINE, [])),
             ["0x%02X" % b for b in sorted(by_class.get(BORDERLINE, []))]))
    print("    INADMISSIBLE %3d bytes  %s"
          % (len(by_class.get(INADMISSIBLE, [])),
             ["0x%02X" % b for b in sorted(by_class.get(INADMISSIBLE, []))]))
    check("the three classes partition all 256 bytes",
          sum(len(v) for v in by_class.values()) == 256)

    print()
    print("COVERPOINT SUMMARY -- what a sign-off run must show")
    print("  coverpoint ctz_g_first : bins %s" % gs)
    print("     illegal_bin inadmissible = {0x00, 0x80}  (RAISE, not count)")
    print("     the g_first = 8 and 9 bins are reachable ONLY by those two")
    print("     bytes, so excluding them EMPTIES two bins of the coverpoint --")
    print("     a coverage goal of 9/9 g_first bins is UNACHIEVABLE for an F7")
    print("     run and must be stated as 7/7 over the legal subset.")
    g_legal = sorted({g_first_of(b) for b in legal})
    g_all = sorted({g_first_of(b) for b in range(256)})
    print("     g_first over all 256 : %s" % g_all)
    print("     g_first over legal   : %s" % g_legal)
    check("excluding the illegal bytes removes exactly the g_first 8 and 9 "
          "bins", set(g_all) - set(g_legal) == {8, 9},
          "so v7's exclusion and a 9-bin coverage goal are INCOMPATIBLE, and "
          "this is a NEW consequence of v7 that v7 does not state")
    print("  coverpoint framed_transitions : bins %s" % ts)
    print("     ALL FIVE BINS ARE ODD, and that is a PARITY THEOREM rather")
    print("     than an artefact of enumeration: the framed stream begins at 0")
    print("     (start bit) and ends at 1 (stop bit), and every transition")
    print("     flips the level, so the count of transitions between a 0 and a")
    print("     1 must be odd.  The coverpoint therefore has 5 bins, not 10,")
    print("     for ALL 8-bit payloads and any frame with a 0 start and a 1")
    print("     stop -- so this is a bound on the coverage model, not a")
    print("     measurement of this DUT.  (2026-09-23 asked which design rules")
    print("     here could be restated as parities or bounds; this is one.)")
    parity_ok = all(t % 2 == 1 for t in ts)
    exhaustive_parity = all(transition_count(b) % 2 == 1 for b in range(256))
    check("every transition count over all 256 bytes is ODD",
          parity_ok and exhaustive_parity,
          "5 reachable bins %s, not the 10 a naive 0..9 coverpoint would "
          "declare" % ts)
    # the parity must be a property of the START/STOP levels, not of 8N1
    # length: a frame with the SAME start and stop level must give EVEN counts.
    same_level = []
    for b in range(256):
        bits = [0] + [(b >> i) & 1 for i in range(N_DATA)] + [0]
        same_level.append(sum(1 for x, y in zip(bits, bits[1:]) if x != y))
    check("POSITIVE CONTROL on the parity argument: a 0-start/0-stop frame "
          "gives EVEN counts for all 256 bytes",
          all(t % 2 == 0 for t in same_level),
          "so the parity follows from the endpoint levels, as claimed, and "
          "not from the frame length")
    print("  cross ctz_g_first x framed_transitions : %d reachable of %d"
          % (len(reach), full_grid))

    print()
    print("=" * 78)
    if _fails:
        print("RESULT: %d CHECK(S) FAILED  %s" % (len(_fails), _fails))
    else:
        print("RESULT: ALL CHECKS PASS   (%d checks, 0 failed)"
              % (len(_fails) + _PASSES[0]))
    print("=" * 78)
    return 1 if _fails else 0


if __name__ == "__main__":
    sys.exit(main())
