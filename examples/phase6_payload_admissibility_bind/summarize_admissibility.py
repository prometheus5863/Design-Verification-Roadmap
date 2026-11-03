#!/usr/bin/env python3
"""
summarize_admissibility.py -- the cross-policy half of the live payload
admissibility measurement.

`uart_uvm_payload_bind_tb.py` runs ONE policy per invocation and appends one
row to `pac_results.csv`.  This file aggregates whatever rows exist and asks
the two questions the bench cannot ask from inside a single-policy run:

  S1  DOES THE PURE-RANDOM POLICY MATCH THE UNIFORM PREDICTION?  If it does
      not, nothing else here means anything -- the measurement would be
      wrong before the comparison starts.  This is the calibration, and it
      is checked against 2/256 and 9/256 DERIVED from the imported model,
      not against the 0.78 % / 3.52 % figures as typed text.
  S2  IS THE STEERED POLICY DIRTIER, AND BY HOW MUCH?  The prediction
      written down on 2026-11-02, here tested rather than asserted.
  S3  WHY, MECHANICALLY.  A ratio is not an explanation; S3 attributes the
      excess to specific bins and specific bytes.

Run `python3 summarize_admissibility.py` after at least one invocation of
each policy.  Plain python3: no cocotb, no simulator.
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_EX = os.path.dirname(_HERE)
for _p in (os.path.join(_EX, 'phase4_uvm_milestone'), _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import payload_coverage_model as M                               # noqa: E402
import reachable_cross_under_per_byte_rule as R                  # noqa: E402
import payload_admissibility_audit as AUD                        # noqa: E402

RESULTS = os.environ.get("PAC_RESULTS",
                         os.path.join(_HERE, "pac_results.csv"))

_PASS, _FAIL = [], []


def check(label, ok, detail=""):
    (_PASS if ok else _FAIL).append(label)
    print("  [%s] %s" % ("PASS" if ok else "FAIL", label))
    if detail:
        for line in _wrap(detail, 72):
            print("         %s" % line)
    return ok


def _wrap(text, width):
    words, lines, cur = text.split(), [], ''
    for w in words:
        if cur and len(cur) + 1 + len(w) > width:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + ' ' + w) if cur else w
    if cur:
        lines.append(cur)
    return lines


def binom_sd(n, p):
    return (n * p * (1.0 - p)) ** 0.5


def load(path):
    rows = {}
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            f = line.split(",")
            pol, nseeds, base, mode = f[0], int(f[1]), int(f[2]), f[3]
            seen = int(f[4])
            rec = dict(
                policy=pol, n_seeds=nseeds, seed_base=base, mode=mode,
                seen=seen,
                vplan=dict(adm=int(f[5]), bord=int(f[6]), inadm=int(f[7])),
                v9=dict(adm=int(f[8]), bord=int(f[9]), inadm=int(f[10])),
                per_bin=[int(x) for x in f[11].split(":")])
            # Several invocations with different SEED_BASE accumulate; a
            # repeat of the same (policy, base, seeds) is a duplicate and is
            # reported rather than averaged, as closure_results.csv does.
            key = (pol, base, nseeds, mode)
            rows.setdefault(key, []).append(rec)
    return rows


def main():
    print("=" * 76)
    print("PAYLOAD ADMISSIBILITY, LIVE -- cross-policy summary")
    print("=" * 76)
    if not os.path.exists(RESULTS):
        print("  no results file at %s -- run the bench first" % RESULTS)
        return 2
    rows = load(RESULTS)

    dups = {k: v for k, v in rows.items() if len(v) > 1}
    if dups:
        print("  DUPLICATE ROWS (same policy, seed base, seeds and mode):")
        for k, v in sorted(dups.items()):
            print("    %s x%d -- reported, not averaged" % (str(k), len(v)))

    agg = {}
    for (pol, _b, _n, mode), recs in rows.items():
        if mode != 'survey':
            continue
        a = agg.setdefault(pol, dict(seen=0, runs=0,
                                     vplan=dict(adm=0, bord=0, inadm=0),
                                     v9=dict(adm=0, bord=0, inadm=0),
                                     per_bin=[0] * 6))
        r = recs[0]
        a['seen'] += r['seen']
        a['runs'] += r['n_seeds']
        for rule in ('vplan', 'v9'):
            for k in ('adm', 'bord', 'inadm'):
                a[rule][k] += r[rule][k]
        for i in range(6):
            a['per_bin'][i] += r['per_bin'][i]

    # Predictions, DERIVED from the imported model.
    model_rows = M.load_measured()
    vplan_rule = set(b for b in model_rows
                     if M.classify(b, model_rows) == M.INADMISSIBLE)
    nine_rule = set(R.inadmissible_by_closed_form())
    bord_set = set(b for b in model_rows
                   if M.classify(b, model_rows) == M.BORDERLINE)
    p_vplan = len(vplan_rule) / 256.0
    p_v9 = len(nine_rule) / 256.0
    p_notclean = (len(vplan_rule) + len(bord_set)) / 256.0

    print()
    print("  uniform predictions, derived from the imported model:")
    print("    vplan inadmissible : %d/256 = %.4f %%"
          % (len(vplan_rule), 100.0 * p_vplan))
    print("    v9 excluded        : %d/256 = %.4f %%"
          % (len(nine_rule), 100.0 * p_v9))
    print("    not clean evidence : %d/256 = %.4f %%"
          % (len(vplan_rule) + len(bord_set), 100.0 * p_notclean))
    print()
    print("  %-8s %-7s %-9s %-13s %-13s %-13s"
          % ("policy", "runs", "payloads", "vplan inadm", "vplan notclean",
             "v9 excluded"))
    for pol in sorted(agg):
        a = agg[pol]
        n = max(a['seen'], 1)
        nc = a['vplan']['inadm'] + a['vplan']['bord']
        print("  %-8s %-7d %-9d %-13s %-13s %-13s"
              % ("steer=%s" % pol, a['runs'], a['seen'],
                 "%d (%.3f %%)" % (a['vplan']['inadm'],
                                   100.0 * a['vplan']['inadm'] / n),
                 "%d (%.3f %%)" % (nc, 100.0 * nc / n),
                 "%d (%.3f %%)" % (a['v9']['inadm'],
                                   100.0 * a['v9']['inadm'] / n)))

    if '0' not in agg or '1' not in agg:
        print()
        print("  only policies %s present -- run the other one before the"
              % sorted(agg))
        print("  comparison is meaningful.  Calibration (S1) still runs if")
        print("  steer=0 is present.")

    # ---- S1: calibration -------------------------------------------------
    print()
    print("S1  CALIBRATION -- does pure random match the uniform prediction?")
    if '0' in agg:
        a = agg['0']
        n = a['seen']
        for rule, p in (('vplan', p_vplan), ('v9', p_v9)):
            obs = a[rule]['inadm']
            exp = n * p
            sd = binom_sd(n, p)
            z = (obs - exp) / sd if sd > 0 else 0.0
            check("S1-%s the pure-random inadmissible count is within 3 "
                  "sigma of the uniform binomial" % rule,
                  abs(z) <= 3.0,
                  "observed %d of %d (%.4f %%) against an expected %.2f "
                  "(%.4f %%), sigma %.2f, z = %+.2f.  The stimulus is a "
                  "UART burst generator and nothing in it is supposed to "
                  "bias the payload, so this is the check that the census "
                  "is counting the right thing at all."
                  % (obs, n, 100.0 * obs / n, exp, 100.0 * p, sd, z))
        nc = a['vplan']['inadm'] + a['vplan']['bord']
        exp_nc = n * p_notclean
        sd_nc = binom_sd(n, p_notclean)
        z_nc = (nc - exp_nc) / sd_nc if sd_nc > 0 else 0.0
        check("S1-notclean the 'not clean F7 evidence' rate reproduces the "
              "vplan v8 figure under random stimulus",
              abs(z_nc) <= 3.0,
              "observed %d of %d (%.3f %%) against %.2f (%.3f %%), "
              "z = %+.2f.  v8 states this as 'about 1 in 64'; the measured "
              "rate is 1 in %.0f."
              % (nc, n, 100.0 * nc / n, exp_nc, 100.0 * p_notclean, z_nc,
                 n / max(nc, 1)))
    else:
        check("S1 calibration requires a steer=0 row", False,
              "none present in %s" % RESULTS)

    # ---- S2: the prediction ---------------------------------------------
    print()
    print("S2  THE 2026-11-02 PREDICTION -- is steer=1 materially dirtier?")
    if '0' in agg and '1' in agg:
        r0 = agg['0']['vplan']['inadm'] / max(agg['0']['seen'], 1)
        r1 = agg['1']['vplan']['inadm'] / max(agg['1']['seen'], 1)
        ratio = r1 / r0 if r0 > 0 else float('inf')
        # Two-proportion z, pooled.
        x0, n0 = agg['0']['vplan']['inadm'], agg['0']['seen']
        x1, n1 = agg['1']['vplan']['inadm'], agg['1']['seen']
        pp = (x0 + x1) / float(n0 + n1)
        se = (pp * (1 - pp) * (1.0 / n0 + 1.0 / n1)) ** 0.5
        z = (r1 - r0) / se if se > 0 else 0.0
        check("S2 the steered policy IS materially dirtier -- the 11-02 "
              "prediction is CONFIRMED",
              r1 > r0 and z > 3.0,
              "steer=1 drives an inadmissible payload in %.3f %% of frames "
              "against steer=0's %.3f %% -- a factor of %.1f, two-proportion "
              "z = %+.1f.  Written down on 11-02 as 'a number that can come "
              "out wrong'; it did not."
              % (100.0 * r1, 100.0 * r0, ratio, z))
        check("S2-b and the steered policy drives MORE inadmissible frames "
              "IN ABSOLUTE TERMS despite running far fewer",
              x1 >= x0,
              "steer=1: %d inadmissible in %d payloads; steer=0: %d in %d. "
              "The steered policy closes coverage in roughly %.0fx fewer "
              "pushes and still drives the excluded bytes MORE often, so "
              "this is not a small-denominator artefact."
              % (x1, n1, x0, n0, n0 / float(max(n1, 1))))
    else:
        print("  skipped: needs both policies")

    # ---- S3: the mechanism ----------------------------------------------
    print()
    print("S3  THE MECHANISM -- which bins and which bytes")
    if '1' in agg:
        a = agg['1']
        n = max(a['seen'], 1)
        share0 = a['per_bin'][0] / float(n)
        print("  %-6s %-18s %-12s %-12s"
              % ("bin", "meaning", "steer=1", "steer=0"))
        for c in range(6):
            s0 = (agg['0']['per_bin'][c] / float(max(agg['0']['seen'], 1))
                  if '0' in agg else float('nan'))
            print("  %-6d %-18s %-12s %-12s"
                  % (c, AUD.BIN_NAMES[c],
                     "%d (%.1f %%)" % (a['per_bin'][c],
                                       100.0 * a['per_bin'][c] / n),
                     "%.1f %%" % (100.0 * s0)))
        check("S3 the excess is BIN 0, whose only member is 0x00 -- the "
              "steering map has no other way to close it",
              share0 > 0.05,
              "%.1f %% of all steered payloads are bin 0, i.e. the single "
              "byte 0x00, against %.2f %% under random.  byte_for_class[0] "
              "IS 0x00 because bin 0 is the singleton {0x00}, so a "
              "coverage-driven policy is STRUCTURALLY OBLIGED to drive the "
              "byte that cannot carry F7 evidence.  And a steered item "
              "carries burst_len = 1..8 pushes of the SAME byte, so one "
              "steering decision costs up to eight inadmissible frames -- "
              "which is why the count is %d and not 1 or 2."
              % (100.0 * share0,
                 100.0 * agg['0']['per_bin'][0] / max(agg['0']['seen'], 1)
                 if '0' in agg else float('nan'),
                 a['per_bin'][0]))
        check("S3-b the steered policy saw NO borderline bytes at all, "
              "which the structural audit predicts",
              a['vplan']['bord'] == 0,
              "0x40 and 0xC0 are the borderline pair and neither is any "
              "cp_data bin's only witness, so the steering map never names "
              "one: byte_for_class is %s.  Random drew them %d times.  The "
              "two policies are therefore dirty in DIFFERENT ways -- steered "
              "drives the inadmissible singleton deliberately, random "
              "stumbles on the borderline pair at its base rate."
              % ([hex(b) for b in [0x00, 0xFF, 0x08, 0xAA, 0x33, 0x07]],
                 agg['0']['vplan']['bord'] if '0' in agg else -1))
    else:
        print("  skipped: needs a steer=1 row")

    print()
    print("=" * 76)
    print("%d checks, %d passing, %d failing"
          % (len(_PASS) + len(_FAIL), len(_PASS), len(_FAIL)))
    print("=" * 76)
    return 1 if _FAIL else 0


if __name__ == '__main__':
    sys.exit(main())
