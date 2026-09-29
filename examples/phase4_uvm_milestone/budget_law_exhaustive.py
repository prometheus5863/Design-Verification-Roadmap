#!/usr/bin/env python3
"""Exhaustive check of the adaptive observer's budget law, all 256 bytes.

WHY THIS FILE EXISTS
--------------------
2026-09-29's `UartAdaptiveObserverTest` measured the adaptive observer's baud
budget on NINE frames -- one byte per `g_max` class -- found the
pre-registered law `1/(2*g_max)` wrong, and replaced it with

    |eps| < 1 / (2 * g_first),      g_first = 1 + ctz(data)   (9 for 0x00)

On the strength of that law the same run concluded that the observer CONTAINS
the DUT's window (slow 6.75%) for 254 of 256 bytes and fails for exactly two,
0x80 and 0x00 -- and vplan v7 is about to turn that into a sign-off criterion
naming those two bytes.

A criterion that names two bytes out of 256 is an extrapolation from five
measurements unless someone measures the other 251.  That is what this does.
It is a MODEL check, not a simulation: it drives the observer's own decode
method with synthesised edge timestamps instead of a Verilog BFM, and that
limitation is stated rather than hidden -- see "WHAT THIS DOES NOT SHOW".

WHAT IS REUSED AND WHAT IS REBUILT
----------------------------------
The decode under test is not re-implemented.  `UartEdgeRecorder` and
`UartAdaptiveEdgeObserver` are lifted OUT of `uart_uvm_tb.py` by source
extraction (ast.get_source_segment) and exec'd against a stub base class, so
the algorithm measured here is byte-identical to the algorithm the UVM
regression runs.  Re-typing it would have made a disagreement between the two
uninterpretable, which is the 2026-09-24 anchored-comparison rule.

What IS rebuilt is the stimulus: edges at `t0 + n * bit_ps` with
`bit_ps = round(BIT_PS_NOM * (1 + eps))`, which is what the Verilog BFM
produces and what `phase6_bfm_equivalence` T1 checked over 3472 trials.

WHAT THIS DOES NOT SHOW
-----------------------
Nothing about the DUT.  The DUT's window is a simulation result and stays one.
This file measures the INSTRUMENT, which is the half of the containment
comparison that is pure arithmetic on recorded times and therefore the half
that can be settled exhaustively without a simulator.
"""

import ast
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "uart_uvm_tb.py")
WANT = ["UartEdgeRecorder", "UartAdaptiveEdgeObserver"]

BIT_CYCLES = 16          # BAUD_DIV = 0, as the phase4 environment runs
CLK_NS = 10
BIT_PS_NOM = BIT_CYCLES * CLK_NS * 1000      # 160000 ps
N_DATA = 8
N_TOTAL = 1 + N_DATA + 1                     # 8N1

fails = []
def check(tag, ok, detail=""):
    print("  [%s] %s  %s" % ("PASS" if ok else "FAIL", tag, detail))
    if not ok:
        fails.append(tag)
    return ok


# ---------------------------------------------------------------- load ------
def load_observer():
    src = open(SRC).read()
    tree = ast.parse(src)
    chunks = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name in WANT:
            chunks.append((WANT.index(node.name), ast.get_source_segment(src, node)))
    if len(chunks) != len(WANT):
        raise SystemExit("source extraction found %d of %d classes" %
                         (len(chunks), len(WANT)))
    chunks.sort()
    ns = {"UVMComponent": object}
    exec("\n\n".join(c for _, c in chunks), ns)
    return ns["UartAdaptiveEdgeObserver"]


Obs = load_observer()


class ShimObserver(Obs):
    """The extracted observer with the UVM plumbing replaced by two fields.

    `__init__` is overridden rather than called through: the real one goes to
    UVMComponent for a parent handle that does not exist here.  Every method
    this file calls touches only `edges`, `t0` and `self_error_bp`.
    """

    def __init__(self):
        self.edges = []
        self.t0 = 0
        self.line = "rx"
        self.dut = None
        self.self_error_bp = 0


# ------------------------------------------------------------- stimulus -----
def bit_ps_for(eps_bp):
    """The BFM's expression, including its integer-ps rounding."""
    return int(round(BIT_PS_NOM * (1.0 + eps_bp / 10000.0)))


def frame_edges(data, eps_bp):
    """One 8N1 frame's transitions, as the recorder would have logged them.

    The leading (t, 1) entry is the idle-high edge the decoder's start-edge
    guard requires to exist before a falling edge; it sits two NOMINAL bit
    periods early so the guard's `t - prev_t >= ref0` holds at every eps.
    """
    bit_ps = bit_ps_for(eps_bp)
    t_start = 8 * BIT_PS_NOM
    edges = [(t_start - 2 * BIT_PS_NOM, 1)]
    lvl = 0
    for n in Obs.edge_positions(data, n_data=N_DATA):
        edges.append((t_start + n * bit_ps, lvl))
        lvl ^= 1
    return edges


def decode_once(data, eps_bp, self_error_bp=0):
    """Returns (ok, frame_or_None)."""
    obs = ShimObserver()
    obs.self_error_bp = self_error_bp
    obs.edges = frame_edges(data, eps_bp)
    dec = obs.decode_frames_adaptive(BIT_PS_NOM, n_data=N_DATA)
    if len(dec) != 1:
        return False, (dec[0] if dec else None)
    f = dec[0]
    return (f["data"] == data and f["stop_ok"]), f


# ------------------------------------------------------------ the sweep -----
COARSE = 5          # bp
CAP = 6000          # bp; the widest predicted budget is 5000 (g_first = 1)
ISLAND_STEP = 25


def clean_limit(data, sign, self_error_bp=0):
    """Largest |eps| in bp, 1 bp resolution, for which every step from 0 out to
    it decodes correctly.  Returns (limit_bp, n_edges_at_limit, first_bad_bp)."""
    last_ok = 0
    n_edges = None
    e = COARSE
    while e <= CAP:
        ok, f = decode_once(data, sign * e, self_error_bp)
        if not ok:
            break
        last_ok = e
        n_edges = f["n_edges"]
        e += COARSE
    else:
        return CAP, n_edges, None
    # refine upward from the last clean coarse step
    e = last_ok + 1
    while e <= CAP:
        ok, f = decode_once(data, sign * e, self_error_bp)
        if not ok:
            return e - 1, n_edges, e
        last_ok = e
        n_edges = f["n_edges"]
        e += 1
    return last_ok, n_edges, None


def island_scan(data, sign, limit_bp):
    """Clean points BEYOND the first failure -- a discontiguous tolerance
    region would invalidate the word 'budget' and has to be looked for rather
    than assumed away."""
    found = []
    e = ((limit_bp // ISLAND_STEP) + 2) * ISLAND_STEP
    while e <= CAP:
        ok, _ = decode_once(data, sign * e)
        if ok:
            found.append(sign * e)
        e += ISLAND_STEP
    return found


def main():
    out = []
    print("=" * 78)
    print("ADAPTIVE OBSERVER BUDGET LAW -- EXHAUSTIVE OVER ALL 256 BYTES")
    print("2026-09-29, model check on the extracted decode; BAUD_DIV=0, 8N1")
    print("=" * 78)
    print("BIT_PS_NOM = %d ps   coarse step %d bp   refine 1 bp   cap %d bp"
          % (BIT_PS_NOM, COARSE, CAP))
    print()

    # ---- V1: exactly-known values at eps = 0 ------------------------------
    print("V1  eps = 0 must be EXACT for every byte: decode = byte,")
    print("    margin exactly 0.5 bit, eps_hat exactly 0.0 bp.")
    bad = []
    for d in range(256):
        ok, f = decode_once(d, 0)
        if not ok or f["margin"] != 0.5 or f["eps_hat_bp"] != 0.0:
            bad.append((d, ok, None if f is None else f["margin"],
                        None if f is None else f["eps_hat_bp"]))
    check("V1 exact at eps=0, 256/256",
          not bad, "" if not bad else "offenders: %r" % bad[:6])

    # ---- V2: two independent routes to g_first ----------------------------
    print()
    print("V2  g_first by edge-walking == 1 + ctz(data) for all 256 bytes.")
    mism = [d for d in range(256)
            if Obs.g_first_for(d) != Obs.g_first_closed_form(d)]
    check("V2 g_first routes agree", not mism, "mismatches: %r" % mism[:8])

    # ---- V3: the measurement ---------------------------------------------
    print()
    print("V3  measured clean limit vs the two candidate laws, per byte.")
    print("    law A (measured 09-29):  100/(2*g_first)")
    print("    law B (pre-registered):  100/(2*g_max)   -- kept as the")
    print("    NEGATIVE CONTROL: a comparison that cannot reject a wrong law")
    print("    cannot confirm a right one.")
    print()
    print("  byte  gf  gm   pred_A%   pred_B%   meas+%   meas-%  A?  B?  nE  island")
    rows = []
    a_ok = b_ok = 0
    truncated = []
    islands = []
    for d in range(256):
        gf = Obs.g_first_for(d)
        gm = Obs.g_max_for(d)
        pa = 10000.0 / (2.0 * gf)          # bp
        pb = 10000.0 / (2.0 * gm)
        lp, nep, _ = clean_limit(d, +1)
        ln, nen, _ = clean_limit(d, -1)
        meas = min(lp, ln)
        # A law MATCHES when the measured 1 bp-resolution limit is the last
        # clean step at the bound: |meas - pred| <= 1 bp.  The one-step slack
        # is not fitted, it is the resolution -- and note 0xAA lands exactly
        # ON its 2500 bp bound because `round(2.5)` is 2 in Python, i.e. the
        # boundary case resolves in the observer's favour by a tie-break rule
        # and not by anything about UARTs.
        def matches(p):
            return abs(meas - p) <= 1.0
        ma, mb = matches(pa), matches(pb)
        a_ok += ma
        b_ok += mb
        n_avail = len(Obs.edge_positions(d, n_data=N_DATA)) - 1
        if nep is not None and nep < n_avail:
            truncated.append((d, nep, n_avail, lp))
        isl = island_scan(d, +1, lp) + island_scan(d, -1, ln)
        if isl:
            islands.append((d, isl[:4]))
        rows.append((d, gf, gm, pa, pb, lp, ln, ma, mb, nep))
        if d < 16 or d in (0x00, 0x01, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80,
                           0xAA, 0x55, 0xFF, 0x3C, 0x81, 0xC0, 0xE0, 0xF0):
            print("  0x%02X  %2d  %2d   %7.3f   %7.3f  %6d  %6d   %s   %s  %2s  %s"
                  % (d, gf, gm, pa / 100.0, pb / 100.0, lp, ln,
                     "Y" if ma else "n", "Y" if mb else "n",
                     "-" if nep is None else nep,
                     "yes" if any(x[0] == d for x in islands) else "-"))
    print("  ... (full 256-row table written below)")
    print()
    check("V3 law A (1/(2*g_first)) holds for all 256 bytes",
          a_ok == 256, "%d/256 match" % a_ok)
    check("V3 law B (1/(2*g_max)) is REJECTED -- negative control fires",
          b_ok < 256, "%d/256 match; %d bytes refute it" % (b_ok, 256 - b_ok))
    check("V3 tolerance region is contiguous (no clean islands beyond the "
          "first failure)", not islands, "islands on %d bytes: %r"
          % (len(islands), islands[:4]))

    # ---- V4: containment, now measured rather than extrapolated ----------
    print()
    print("V4  containment against the DUT's measured 8N1 window")
    print("    (slow 6.75%, fast 4.00%; uart_uvm_sim_output_2026-09-28.txt).")
    DUT_SLOW_BP, DUT_FAST_BP = 675, 400
    not_contained = [(d, lp, ln) for (d, gf, gm, pa, pb, lp, ln, ma, mb, ne)
                     in rows if lp < DUT_SLOW_BP or ln < DUT_FAST_BP]
    print("    bytes whose MEASURED window does not contain the DUT's: %d"
          % len(not_contained))
    for d, lp, ln in not_contained:
        print("      0x%02X  slow limit %+d bp (need %+d), fast limit %-d bp "
              "(need %d)" % (d, lp, DUT_SLOW_BP, ln, DUT_FAST_BP))
    predicted = sorted(d for d in range(256)
                       if 10000.0 / (2.0 * Obs.g_first_for(d)) <= DUT_SLOW_BP)
    check("V4 the measured non-containing set is exactly what law A predicts",
          sorted(d for d, _, _ in not_contained) == predicted,
          "measured %r vs predicted %r"
          % ([d for d, _, _ in not_contained], predicted))

    # ---- V5: positive control on the harness itself ----------------------
    print()
    print("V5  POSITIVE CONTROL ON THE MEASUREMENT (2026-09-29 rule: a")
    print("    mutation that does not arrive is indistinguishable from a")
    print("    system that does not respond).  Corrupt the observer's own")
    print("    starting reference by +2000 bp and require the measured limit")
    print("    to MOVE on the byte the law says is most sensitive.")
    probe = 0x00                      # g_first = 9, the tightest budget
    base, _, _ = clean_limit(probe, +1)
    mut, _, _ = clean_limit(probe, +1, self_error_bp=2000)
    print("    0x00 slow limit: clean %+d bp -> self-error +20%% %+d bp"
          % (base, mut))
    check("V5 the harness is sensitive to a corrupted observer reference",
          mut != base, "clean %d, mutated %d" % (base, mut))

    # ---- V6: the same law as a property of the OBSERVER, anchored to the
    #      morning's simulation ------------------------------------------
    print()
    print("V6  THE SAME LAW, RESTATED AS A PROPERTY OF THE OBSERVER, AND")
    print("    ANCHORED TO THIS MORNING'S SIMULATION RATHER THAN TO ITSELF.")
    print("    A4 in uart_uvm_sim_output_2026-09-29.txt swept a corruption of")
    print("    the observer's own STARTING reference over bytes 0xAA and 0x11")
    print("    and found the decode first breaks at 4000 bp = 40%.  If the law")
    print("    is really about the first assignment, the same threshold has to")
    print("    come out of arithmetic: the first gap is assigned as")
    print("    round(g*(1+eps)/(1+s)), which fails when")
    print("        g * |1/(1+s) - 1| > 1/2   ->   s* = 1/(1 - 1/(2*g)) - 1")
    print("    and for the binding byte of the pair that is a DERIVED number,")
    print("    not a measured one.")
    SIM_SWEEP = (500, 1000, 2000, 3000, 4000, 5000, 6000)
    SIM_BYTES = (0xAA, 0x11)
    SIM_THRESHOLD_BP = 4000          # from the committed simulation log
    g_bind = max(Obs.g_first_for(d) for d in SIM_BYTES)
    s_star = (1.0 / (1.0 - 1.0 / (2.0 * g_bind)) - 1.0) * 10000.0
    derived_first_break = min(e for e in SIM_SWEEP if e > s_star)
    print("    binding byte has g_first = %d  ->  s* = %.1f bp,"
          % (g_bind, s_star))
    print("    so the first sweep point above it is %d bp." % derived_first_break)
    model_break = None
    model_sweep = []
    for err_bp in SIM_SWEEP:
        bad = any(not decode_once(d, 0, self_error_bp=err_bp)[0]
                  for d in SIM_BYTES)
        model_sweep.append((err_bp, bad))
        if bad and model_break is None:
            model_break = err_bp
    print("    model sweep (err_bp, broke?): %r" % (model_sweep,))
    check("V6 model reproduces the SIMULATED self-error threshold",
          model_break == SIM_THRESHOLD_BP,
          "model %s bp, simulation %d bp" % (model_break, SIM_THRESHOLD_BP))
    check("V6 and both agree with the DERIVED s*",
          derived_first_break == SIM_THRESHOLD_BP,
          "derived %d bp" % derived_first_break)

    # ---- V7: the law is NOT two-sided, and the reason is one line of code --
    print()
    print("V7  THE LAW IS TWO-SIDED FOR g_first >= 2 AND ONE-SIDED FOR")
    print("    g_first == 1, WHICH THE 09-29 STATEMENT OF IT DOES NOT SAY.")
    print("    The exhaustive scan is what shows it: all 128 bytes with an odd")
    print("    value (g_first = 1) reach the %d bp FAST cap without a single" % CAP)
    print("    failure, while their SLOW limit sits at the predicted 4999 bp.")
    one = [r for r in rows if r[1] == 1]
    other = [r for r in rows if r[1] >= 2]
    print("    g_first == 1 : %d bytes, fast limits %d..%d bp (cap %d)"
          % (len(one), min(r[6] for r in one), max(r[6] for r in one), CAP))
    print("    g_first >= 2 : %d bytes, fast limit == slow limit on %d of them"
          % (len(other), sum(1 for r in other if r[5] == r[6])))
    check("V7 every g_first==1 byte survives to the fast cap",
          all(r[6] == CAP for r in one),
          "%d of %d" % (sum(1 for r in one if r[6] == CAP), len(one)))
    check("V7 every g_first>=2 byte is symmetric to 1 bp",
          all(abs(r[5] - r[6]) <= 1 for r in other),
          "%d of %d" % (sum(1 for r in other if abs(r[5] - r[6]) <= 1),
                        len(other)))
    print("    THE MECHANISM, and it is in the decode rather than in the")
    print("    arithmetic: the assignment is `dn = round(dt/T_ref)` followed by")
    print("    `if dn < 1: dn = 1`.  For g_first = 1 the only value a fast")
    print("    frame can round DOWN to is 0, and the clamp turns that 0 back")
    print("    into the correct 1 -- so the clamp, which exists to stop a")
    print("    nonsensical index, silently makes the fast side unbounded.  For")
    print("    g_first >= 2 the wrong value is >= 1 and the clamp cannot help.")
    probe_bytes = [d for d in range(256) if Obs.g_first_for(d) == 1][:4]
    dn_raw = []
    for d in probe_bytes:
        bit_ps = bit_ps_for(-CAP)
        pos = Obs.edge_positions(d, n_data=N_DATA)
        dt = (pos[1] - pos[0]) * bit_ps
        dn_raw.append((d, dt / float(BIT_PS_NOM), round(dt / float(BIT_PS_NOM))))
    print("    at %d bp fast, the RAW first assignment for %r is %r"
          % (-CAP, ["0x%02X" % d for d in probe_bytes],
             [r[2] for r in dn_raw]))
    check("V7 the clamp is demonstrably what rescues the fast side",
          all(r[2] == 0 for r in dn_raw),
          "raw dn values %r (0 means the clamp, not the fit, produced the "
          "right index)" % [r[2] for r in dn_raw])
    print("    RECORDED AS A LIMIT OF THIS MEASUREMENT: 'unbounded' here means")
    print("    'did not fail anywhere in the scanned +/-%d bp'.  A fast frame" % CAP)
    print("    beyond -100% is not physical, so the honest statement is that")
    print("    the fast side of the g_first == 1 class is not budget-limited.")

    # ---- the full table ---------------------------------------------------
    print()
    print("FULL TABLE (all 256 bytes)")
    print("byte,g_first,g_max,pred_A_pct,pred_B_pct,meas_slow_bp,meas_fast_bp,"
          "lawA_match,lawB_match,n_edges_at_limit")
    for (d, gf, gm, pa, pb, lp, ln, ma, mb, ne) in rows:
        print("0x%02X,%d,%d,%.4f,%.4f,%d,%d,%d,%d,%s"
              % (d, gf, gm, pa / 100.0, pb / 100.0, lp, ln,
                 1 if ma else 0, 1 if mb else 0, "" if ne is None else ne))

    print()
    print("BY g_first CLASS")
    print("g_first  n_bytes  pred_A%   min_meas_slow_bp  max_meas_slow_bp")
    for g in sorted(set(r[1] for r in rows)):
        sub = [r for r in rows if r[1] == g]
        print("%7d  %7d  %7.3f   %16d  %16d"
              % (g, len(sub), 10000.0 / (2.0 * g) / 100.0,
                 min(r[5] for r in sub), max(r[5] for r in sub)))

    if truncated:
        print()
        print("FRAME-WINDOW TRUNCATION at the limit (the observer's own guard")
        print("`tj - t > (n_total-0.5)*ref0` is written in NOMINAL periods, so")
        print("a slow-driven frame can outrun it and lose late edges from the")
        print("fit).  Bytes where fewer edges reached the fit than the frame")
        print("contains, at the slow limit: %d" % len(truncated))
        for d, ne, na, lp in truncated[:24]:
            print("  0x%02X  %d of %d edges at %+d bp" % (d, ne, na, lp))
        if len(truncated) > 24:
            print("  ... and %d more" % (len(truncated) - 24))

    print()
    print("=" * 78)
    print("RESULT: %s   (%d checks, %d failed%s)"
          % ("ALL CHECKS PASS" if not fails else "FAILURES PRESENT",
             11, len(fails), "" if not fails else ": " + ", ".join(fails)))
    print("=" * 78)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
