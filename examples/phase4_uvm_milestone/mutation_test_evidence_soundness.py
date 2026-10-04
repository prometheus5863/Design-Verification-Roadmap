#!/usr/bin/env python3
"""
mutation_test_evidence_soundness.py -- 2026-10-04

Mutation harness for `evidence_soundness_coverage.py`.

A self-checking suite that has never been shown to FAIL is a suite that has
been shown to run.  The 2026-09-17 precedent in this repository is a bench
that passed 55/55 against deliberately broken RTL; the 10-03 precedent is a
coverage goal that was green because the thing it checked was not the thing
it claimed.  So every mutant below changes the MEANING of a soundness
verdict, the suite is re-run under it, and the mutant must kill at least one
check.

Control A: the unmutated suite is fully green.
Control B: a mutation that must NOT be caught, so that "every mutant dies"
is a claim about the mutants and not a property of a suite that fails on any
perturbation at all.  B is `scarce_bins` loosened from `n == 1` to `n <= 1`:
semantically a different predicate, numerically identical on this
population, because a bin exists in the census only if some byte witnesses
it, so no bin has zero witnesses.  If B dies, the suite is reacting to the
act of patching.
"""

import io
import os
import sys
import contextlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import payload_coverage_model as M
import evidence_soundness_coverage as E

_PASS, _FAIL = [], []


def check(label, ok, detail=""):
    (_PASS if ok else _FAIL).append(label)
    print("  [%s] %s%s" % ("PASS" if ok else "FAIL", label,
                           ("  -- " + detail) if detail else ""))


def run_suite():
    """Run evidence_soundness_coverage.main() silently; return failed labels."""
    E._PASS, E._FAIL = [], []
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            E.main()
    except Exception as exc:                       # a crash is a detection,
        return ["<crashed: %r>" % (exc,)]          # but a weaker one -- named
    return list(E._FAIL)


class patched:
    """Rebind attributes on E (and on E.EvidenceSoundCoverage) temporarily."""

    def __init__(self, **kw):
        self.kw = kw

    def __enter__(self):
        self.old = {}
        for dotted, val in self.kw.items():
            obj, attr = (E.EvidenceSoundCoverage, dotted[4:]) \
                if dotted.startswith("cls.") else (E, dotted)
            self.old[dotted] = (obj, attr, getattr(obj, attr))
            setattr(obj, attr, val)
        return self

    def __exit__(self, *a):
        for obj, attr, val in self.old.values():
            setattr(obj, attr, val)
        return False


# --- mutants ---------------------------------------------------------------

def m1_borderline_only(self):
    """run_unsound: require a BORDERLINE witness, so a bin closed only by an
    INADMISSIBLE payload reads as sound.  This is the asymmetry 10-03 named,
    reintroduced on the run axis instead of the population axis."""
    out = []
    for name, _ in E.COVERPOINTS:
        for b in sorted(self.hits[name], key=repr):
            c = self.hits[name][b]
            if c[M.ADMISSIBLE] == 0 and c[M.BORDERLINE] > 0:
                out.append((name, b, c))
    return out


def m2_borderline_counts_as_evidence(self, coverpoint="cross"):
    """population_unsound: accept any non-INADMISSIBLE witness as evidence.
    THE HEADLINE MUTANT: this is exactly the rule vplan v8 through v10
    implemented, under which g_first bin 7 is sound and the 7/7 goal is
    correct.  If the suite does not kill this, the suite has not encoded the
    10-03 finding at all."""
    out = []
    for b, ws in self.reachable_population(coverpoint).items():
        if not any(M.classify(w, self.rows) != M.INADMISSIBLE for w in ws):
            out.append(b)
    return sorted(out, key=repr)


def m3_sound_equals_cardinality(self, coverpoint="cross"):
    """sound_coverage_pct collapses onto cardinality coverage: a bin counts
    as soundly covered if it was hit at all.  The two headline numbers then
    agree always, and the gap sign_off() reports can never open."""
    reach = self.reachable_population(coverpoint)
    hit = sum(1 for b in reach
              if sum(self.hits[coverpoint].get(b, {}).values()) > 0)
    return 100.0 * hit / len(reach), hit, len(reach)


def m4_record_cross_only(self, byte, cls):
    """_record only the cross coverpoint, leaving the marginals empty."""
    binner = dict(E.COVERPOINTS)["cross"]
    cell = self.hits["cross"].setdefault(
        binner(byte),
        {M.ADMISSIBLE: 0, M.BORDERLINE: 0, M.INADMISSIBLE: 0})
    cell[cls] += 1


def m5_sign_off_drops_population(self, coverpoint="cross"):
    """sign_off reports only the run-axis reason, dropping the structural
    one.  The gate then tells a reviewer to change the stimulus when the
    actual remedy is to change the goal -- a true statement that misdirects."""
    reasons = []
    run = [(cp, b) for cp, b, _ in self.run_unsound_bins() if cp == coverpoint]
    if run:
        reasons.append("%d bin(s) %r were closed in this run only by "
                       "non-admissible payloads" % (len(run),
                                                    [b for _, b in run]))
    return (not reasons), reasons


def m6_scarce_le_one(self, coverpoint="cross"):
    """CONTROL B: scarce means n <= 1 rather than n == 1.  A different
    predicate; identical on this population, because a bin with no witness
    does not appear in the census at all."""
    return sorted((b for b, ws in self.reachable_population(coverpoint).items()
                   if len(ws) <= 1), key=repr)


MUTANTS = [
    ("M1 run_unsound requires a BORDERLINE witness (inadmissible-only "
     "closure reads sound)", {"cls.run_unsound_bins": m1_borderline_only}),
    ("M2 population_unsound accepts BORDERLINE as evidence (vplan v8-v10's "
     "own rule)", {"cls.population_unsound_bins":
                   m2_borderline_counts_as_evidence}),
    ("M3 sound coverage collapses onto cardinality coverage",
     {"cls.sound_coverage_pct": m3_sound_equals_cardinality}),
    ("M4 _record writes only the cross, not the marginals",
     {"cls._record": m4_record_cross_only}),
    ("M5 sign_off drops the structural reason, keeping only the run one",
     {"cls.sign_off": m5_sign_off_drops_population}),
]


def main():
    print("=" * 76)
    print("MUTATION HARNESS: evidence_soundness_coverage.py  (2026-10-04)")
    print("=" * 76)
    print()

    base = run_suite()
    check("CONTROL A: the unmutated suite is fully green",
          base == [], "failures = %r" % (base,))

    killed = 0
    for name, kw in MUTANTS:
        with patched(**kw):
            fails = run_suite()
        ok = len(fails) > 0
        killed += ok
        check("  %s" % name, ok,
              "killed by %d check(s): %s" % (len(fails), "; ".join(
                  f[:70] for f in fails[:3]) if fails else "NONE"))

    with patched(**{"cls.scarce_bins": m6_scarce_le_one}):
        ctrlB = run_suite()
    check("CONTROL B: scarce as n<=1 instead of n==1 is NOT caught "
          "(identical on this population)", ctrlB == [],
          "failures = %r" % (ctrlB,))

    print()
    print("  Mutants killed: %d of %d" % (killed, len(MUTANTS)))
    print()
    print("=" * 76)
    print("SUMMARY: %d passed, %d failed; mutants killed %d/%d"
          % (len(_PASS), len(_FAIL), killed, len(MUTANTS)))
    for f in _FAIL:
        print("  FAILED: %s" % f)
    print("=" * 76)
    return 1 if (_FAIL or killed < len(MUTANTS)) else 0


if __name__ == "__main__":
    sys.exit(main())
