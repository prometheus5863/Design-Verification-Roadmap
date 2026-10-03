#!/usr/bin/env python3
"""
mutation_test_witness_soundness.py -- 2026-10-03

Mutation harness for witness_soundness.py.

A suite that passes tells you nothing until you know it can fail.  Each mutant
below is a defect injected into a COPY of the suite (never the committed file);
a mutant that is NOT detected is a hole in the suite, not a success.

CONTROL A (09-19 onward): the unmutated suite must PASS, or a detection means
only that the suite is broken.
CONTROL B (required repository-wide by the 10-01 list): a SEMANTICS-PRESERVING
edit must leave the suite PASSING.  Without it, a suite that failed on any edit
whatever would score 100% and its detections would say nothing about WHICH
edit.

THE COMPOUND FORM, CARRIED FORWARD FROM 10-02 RATHER THAN REDISCOVERED.
10-02's M6 weakened an assertion and required detection, and escaped correctly:
a weakened assertion still holds on correct input, so no self-run can catch it.
The lesson there was that a weakening needs three mutants, not one.  M8 below
is in that form from the start:
    M8a  weaken a check's threshold alone            -> must SURVIVE
    M8b  weaken it AND perturb what it guards        -> must SURVIVE  (the point)
    M8c  perturb the same quantity, threshold intact -> must be DETECTED
Only the three together establish that the threshold is load-bearing.  M8b is
the one that matters: it is a real defect that the weakened suite cannot see,
which is what makes the weakening dangerous rather than untidy.

Run:  python3 mutation_test_witness_soundness.py
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, "witness_soundness.py")
SURVIVE, DETECT = "SURVIVE", "DETECT"

# (id, expectation, description, [(old, new), ...])
MUTANTS = [
    ("A", SURVIVE, "control A: no edit at all -- the suite must pass unmutated", []),
    ("B", SURVIVE,
     "control B: semantics-preserving -- rename a local loop variable in "
     "witnesses()",
     [("    for b in range(256):\n        if b in excluded:\n            continue\n"
       "        out.setdefault(binner(b), []).append(b)",
       "    for byte_ in range(256):\n        if byte_ in excluded:\n            continue\n"
       "        out.setdefault(binner(byte_), []).append(byte_)")]),

    ("M1", DETECT,
     "unsound() tests EMPTINESS instead of admissibility -- the exact confusion "
     "the finding is about",
     [('return [k for k in sorted(rep) if rep[k]["adm"] == 0]',
       'return [k for k in sorted(rep) if rep[k]["n"] == 0]')]),
    ("M2", DETECT,
     "soundness() counts BORDERLINE as admissible -- bin 7 would read sound",
     [('"adm": sum(1 for b in bs if cls[b] == M.ADMISSIBLE),',
       '"adm": sum(1 for b in bs if cls[b] != M.INADMISSIBLE),')]),
    ("M3", DETECT,
     "scarce() looks for two witnesses instead of one",
     [('return [k for k in sorted(rep) if rep[k]["n"] == 1]',
       'return [k for k in sorted(rep) if rep[k]["n"] == 2]')]),
    ("M4", DETECT,
     "CAP6 caps at 7, so W3 merges nothing and cannot equal W1",
     [("CAP6 = lambda g: min(g, 6)", "CAP6 = lambda g: min(g, 7)")]),
    ("M5", DETECT,
     "the partition identity is compared against 256 rather than the legal set, "
     "so it stops being an identity under any exclusion",
     [("        legal = 256 - len(excl)", "        legal = 256")]),
    ("M6", DETECT,
     "witnesses() ignores its exclusion argument -- every anchor and control "
     "that depends on the exclusion must break",
     [("        if b in excluded:\n            continue\n        out.setdefault",
       "        if False:\n            continue\n        out.setdefault")]),
    ("M7", DETECT,
     "closure_draws() computes `need` over all 256 bytes rather than the legal "
     "set, so it waits for bins that cannot be drawn",
     [("    need = set(binner(b) for b in legal)",
       "    need = set(binner(b) for b in range(256))")]),

    ("M8a", SURVIVE,
     "weaken C3's threshold ALONE (7 of 7 unsound -> at least one unsound). A "
     "weakened assertion still holds on correct input, so this MUST survive; "
     "requiring detection here would be the 10-02 M6 mis-specification",
     [("          len(unsound(gbord)) == len(gbord) == 7,",
       "          len(unsound(gbord)) >= 1,")]),
    ("M8b", SURVIVE,
     "weaken C3's threshold AND perturb what it guards: allbord now marks only "
     "0x40 borderline. MUST ALSO SURVIVE -- and that is the finding: the "
     "weakened check cannot see a classifier override that no longer overrides, "
     "so C3 would stop being a negative control while still printing PASS",
     [("          len(unsound(gbord)) == len(gbord) == 7,",
       "          len(unsound(gbord)) >= 1,"),
      ("    allbord = dict((b, M.BORDERLINE) for b in range(256))",
       "    allbord = dict((b, M.BORDERLINE if b == 0x40 else M.ADMISSIBLE)\n"
       "                   for b in range(256))")]),
    ("M8c", DETECT,
     "perturb the same quantity with C3's threshold INTACT -- must be detected, "
     "which is what proves the threshold was load-bearing all along",
     [("    allbord = dict((b, M.BORDERLINE) for b in range(256))",
       "    allbord = dict((b, M.BORDERLINE if b == 0x40 else M.ADMISSIBLE)\n"
       "                   for b in range(256))")]),
]


def run_mutant(mid, edits):
    src = open(TARGET, encoding="utf-8").read()
    for old, new in edits:
        if old not in src:
            return None, "EDIT DID NOT APPLY: %r" % old[:60]
        if src.count(old) != 1:
            return None, "EDIT NOT UNIQUE (%d matches)" % src.count(old)
        src = src.replace(old, new)
    path = os.path.join(HERE, "_mutant_%s.py" % mid)
    try:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(src)
        p = subprocess.run([sys.executable, path], capture_output=True,
                           text=True, timeout=600)
        tail = [l for l in p.stdout.strip().split("\n") if l.startswith("TOTAL:")]
        return p.returncode, (tail[-1] if tail else
                              ("no TOTAL line; stderr: " +
                               p.stderr.strip().split("\n")[-1][:90]
                               if p.stderr.strip() else "no TOTAL line"))
    finally:
        if os.path.exists(path):
            os.remove(path)


def main():
    print("=" * 76)
    print("MUTATION TEST -- witness_soundness.py")
    print("=" * 76)
    print("  a mutant marked DETECT must make the suite FAIL (non-zero exit).")
    print("  a mutant marked SURVIVE must leave it PASSING.")
    print()
    ok = bad = 0
    for mid, exp, desc, edits in MUTANTS:
        rc, note = run_mutant(mid, edits)
        if rc is None:
            verdict, good = "HARNESS ERROR", False
        else:
            detected = rc != 0
            good = detected if exp == DETECT else not detected
            verdict = ("detected" if detected else "survived")
        ok += good
        bad += not good
        print("  [%s] %-4s expect %-7s -> %-8s | %s"
              % ("PASS" if good else "FAIL", mid, exp, verdict, note))
        for line in [desc[i:i + 68] for i in range(0, len(desc), 68)]:
            print("         " + line)
        print()
    print("=" * 76)
    print("TOTAL: %d of %d mutants behaved as required" % (ok, ok + bad))
    print("  control A present: the unmutated suite passes, so a detection means")
    print("                     something")
    print("  control B present: a semantics-preserving edit leaves it passing, so")
    print("                     a detection says something about WHICH edit")
    print("  M8a/M8b/M8c: the 10-02 compound form for a weakened assertion, in")
    print("               that form from the start rather than after an escape")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
