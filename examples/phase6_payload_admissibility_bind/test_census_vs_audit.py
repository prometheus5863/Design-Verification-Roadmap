#!/usr/bin/env python3
"""
test_census_vs_audit.py -- the live census, driven over all 256 bytes, must
reproduce the structural audit's census EXACTLY.  Plus a mutation test that
requires this comparison to be able to fail.

WHY THIS EXISTS
---------------
`AdmissibilityCensus` and `payload_admissibility_audit.census()` compute the
same thing by different routes: the live one byte-at-a-time as a subscriber
sees them, the audit one as a sweep over the input space.  They share
`payload_coverage_model` and the AST-lifted `data_class`, but NOT the
accumulation logic -- which is exactly where a live sampler goes wrong
(double-counting, off-by-one on the rule, a class that silently falls through
to ADMISSIBLE).  Driving every byte exactly once makes the two directly
comparable, and the comparison is an EQUALITY over 6 bins x 3 classes x 2
rules rather than a tolerance.

The simulated runs cannot do this: in 1884 random payloads bin 0 appeared 6
times and the borderline pair 17, so most of the table is never exercised by
a run of any affordable length.  Exhaustive and cheap beats sampled and slow,
and this takes under a second with no simulator.

THE MUTATION, AND WHAT IT IS FOR
--------------------------------
A comparison between two things that share a dependency can pass because
both are wrong in the same way.  M1 breaks the live census's rule handling --
`classify_under` ignores the exclusion set and returns the model's own class
-- which is the single most plausible real defect here, since it is what the
code would do if someone "simplified" it.  The suite must FAIL under M1.  On
2026-11-02 a testbench passed 55/55 against deliberately broken RTL, so a
self-checking suite without a shown failure is not evidence.

Run: python3 test_census_vs_audit.py   (needs the cocotb venv, since the
bench module imports cocotb at module scope)
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_EX = os.path.dirname(_HERE)
for _p in (os.path.join(_EX, 'phase4_uvm_milestone'),
           os.path.join(_EX, 'phase6_uvm_crv_uart'),
           _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import payload_coverage_model as M                               # noqa: E402
import payload_admissibility_audit as AUD                        # noqa: E402
import uart_uvm_payload_bind_tb as T                             # noqa: E402

_PASS, _FAIL = [], []


def check(label, ok, detail=""):
    (_PASS if ok else _FAIL).append(label)
    print("  [%s] %s" % ("PASS" if ok else "FAIL", label))
    if detail:
        print("         %s" % detail)
    return ok


def sweep(census):
    for b in range(256):
        census.sample_byte(b)
    return census


def audit_table(census, rule):
    """The audit's census, reshaped to the live census's per-bin counters."""
    excl = census.vplan_rule if rule == 'vplan' else census.nine_rule
    cen, _members = AUD.census(census.rows, census.data_class, excl)
    per_bin = [sum(cen[c].values()) for c in range(6)]
    per_bin_inadm = [cen[c][M.INADMISSIBLE] for c in range(6)]
    totals = {M.ADMISSIBLE: 0, M.BORDERLINE: 0, M.INADMISSIBLE: 0}
    for c in range(6):
        for k in totals:
            totals[k] += cen[c][k]
    return per_bin, per_bin_inadm, totals


def run(census, label):
    """Compare one census against the audit under both rules."""
    ok = True
    for rule in ('vplan', 'v9'):
        a_bin, a_bin_inadm, a_tot = audit_table(census, rule)
        same_tot = census.by_rule[rule] == a_tot
        ok = check("%s / %s rule: the 3-class totals are EQUAL to the "
                   "structural audit's" % (label, rule),
                   same_tot,
                   "live %s vs audit %s" % (census.by_rule[rule], a_tot)) and ok
        if rule == 'vplan':
            ok = check("%s / per-bin totals are EQUAL, bin for bin"
                       % label,
                       census.per_bin == a_bin,
                       "live %s vs audit %s" % (census.per_bin, a_bin)) and ok
            ok = check("%s / per-bin INADMISSIBLE counts are EQUAL"
                       % label,
                       census.per_bin_inadm == a_bin_inadm,
                       "live %s vs audit %s"
                       % (census.per_bin_inadm, a_bin_inadm)) and ok
    return ok


class MutantM1(T.AdmissibilityCensus):
    """M1: `classify_under` ignores the exclusion rule.

    The defect a simplification would introduce: the two rules collapse onto
    `classify()` and become indistinguishable, so 0xFF (excluded by v9,
    ADMISSIBLE on its own) is miscounted and the v9 column goes wrong while
    the vplan column stays RIGHT -- which is why a one-rule test would miss
    it and this suite checks both.
    """

    def classify_under(self, byte, rule):
        return M.classify(byte, self.rows)


def main():
    print("=" * 76)
    print("LIVE CENSUS vs STRUCTURAL AUDIT -- exhaustive over all 256 bytes")
    print("=" * 76)
    print()
    print("  the reference is payload_admissibility_audit.census(), the same")
    print("  function the 11-02 structural half reports from; the subject is")
    print("  uart_uvm_payload_bind_tb.AdmissibilityCensus driven one byte at")
    print("  a time, which is how the live subscriber is driven.")
    print()
    print("SECTION 1 -- the shipped census")
    good = sweep(T.AdmissibilityCensus(mode='survey'))
    run(good, "live")

    print()
    print("SECTION 2 -- the mutant, which the suite must REJECT")
    mut = sweep(MutantM1(mode='survey'))
    before = len(_FAIL)
    run(mut, "M1 rule-blind")
    detected = len(_FAIL) > before
    # The mutant's failures are expected, so remove them from the tally and
    # record the detection itself as the check.
    del _FAIL[before:]
    check("M1 IS DETECTED -- a rule-blind census does not reproduce the "
          "audit", detected,
          "the v9 column moves from %s to %s: 0xFF and the seven other "
          "single-transition bytes stop being excluded.  The vplan column "
          "is UNCHANGED by the mutation, so a suite that checked only the "
          "vplan rule would score this mutant as clean."
          % (good.by_rule['v9'], mut.by_rule['v9']))
    check("M1's vplan column really is unchanged, which is why both rules "
          "are checked", good.by_rule['vplan'] == mut.by_rule['vplan'],
          "both %s -- the vplan exclusion set and the model's own "
          "INADMISSIBLE set are the SAME two bytes, so ignoring the rule "
          "costs nothing there.  That coincidence is the reason this "
          "mutation is worth having."
          % (good.by_rule['vplan'],))

    print()
    print("SECTION 3 -- sanity: every byte counted exactly once")
    check("the sweep saw all 256 bytes, once each",
          good.seen == 256 and sum(good.per_bin) == 256
          and len(good.byte_hist) == 256
          and set(good.byte_hist.values()) == {1},
          "seen %d, per_bin sum %d, distinct bytes %d"
          % (good.seen, sum(good.per_bin), len(good.byte_hist)))

    print()
    print("=" * 76)
    print("%d checks, %d passing, %d failing"
          % (len(_PASS) + len(_FAIL), len(_PASS), len(_FAIL)))
    print("=" * 76)
    return 1 if _FAIL else 0


if __name__ == '__main__':
    sys.exit(main())
