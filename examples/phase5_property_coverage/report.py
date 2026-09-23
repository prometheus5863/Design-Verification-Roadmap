#!/usr/bin/env python3
"""
report.py -- turn the raw verdicts into a per-property mutation-coverage
matrix, with the three guards that decide whether a cell may be scored.

GUARDS, in the order they are applied:
  G1  baseline clean must PASS            -- else the suite itself is broken
  G2  every baseline mutant must FAIL     -- an undetected mutant says
                                             nothing about any property
  G3  drop(p) clean must PASS             -- else the deletion broke the
                                             build; p is INCONCLUSIVE and is
                                             reported as such, never as
                                             redundant

Only cells surviving all three are scored.  A property is LOAD-BEARING if
some mutant flips DETECTED -> MISSED when it is deleted, and SUBSUMED (with
respect to this mutant set) if none does.
"""
import sys
import collections
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from build_variants import SUITES

res = {}
for f in sys.argv[1:]:          # later files override earlier ones
    for line in open(f):
        line = line.strip()
        if not line or line == "ALLDONE":
            continue
        d, v = line.rsplit(" ", 1)
        parts = d.split("/")
        res[(parts[-2], parts[-1])] = v

rows = []
bad_guard = []
for suite, cfg in SUITES.items():
    muts = list(cfg["mutants"])
    base_clean = res.get((suite, "base__clean"))
    if base_clean != "PASS":
        bad_guard.append(f"G1 {suite}: baseline clean = {base_clean}")
    undetected = [m for m in muts if res.get((suite, f"base__{m}")) != "FAIL"]
    for m in undetected:
        bad_guard.append(f"G2 {suite}/{m}: baseline = "
                         f"{res.get((suite, 'base__' + m))} (not detected)")
    scorable = [m for m in muts if m not in undetected]
    print()
    print("=" * 78)
    print(f"SUITE {suite}   properties {' '.join(cfg['props'])}   "
          f"mutants {' '.join(muts)}")
    print("=" * 78)
    print(f"  baseline clean : {base_clean}")
    print(f"  baseline mutants detected: {len(scorable)}/{len(muts)}")
    hdr = "  " + "prop".ljust(8) + "clean".ljust(9) + "".join(
        m.ljust(7) for m in muts) + "  verdict"
    print(hdr)
    for p in cfg["props"]:
        dc = res.get((suite, f"drop{p}__clean"))
        cells, owned = [], []
        for m in muts:
            if m not in scorable or dc != "PASS":
                cells.append("--")
                continue
            v = res.get((suite, f"drop{p}__{m}"))
            if v == "PASS":
                cells.append("ONLY")
                owned.append(m)
            elif v == "FAIL":
                cells.append("still")
            else:
                cells.append(f"?{v}")
        if dc != "PASS":
            verdict = f"INCONCLUSIVE (drop-clean = {dc})"
        elif owned:
            verdict = "LOAD-BEARING for " + ",".join(owned)
        else:
            verdict = "SUBSUMED by the rest (this mutant set)"
        print("  " + p.ljust(8) + str(dc).ljust(9)
              + "".join(c.ljust(7) for c in cells) + "  " + verdict)
        rows.append((suite, p, dc, owned, verdict))

print()
print("=" * 78)
print("SUMMARY")
print("=" * 78)
lb = [r for r in rows if r[3]]
sub = [r for r in rows if r[2] == "PASS" and not r[3]]
inc = [r for r in rows if r[2] != "PASS"]
print(f"  load-bearing : {len(lb):2d}  "
      + ", ".join(f"{s}/{p}" for s, p, _, _, _ in lb))
print(f"  subsumed     : {len(sub):2d}  "
      + ", ".join(f"{s}/{p}" for s, p, _, _, _ in sub))
print(f"  inconclusive : {len(inc):2d}  "
      + ", ".join(f"{s}/{p}" for s, p, _, _, _ in inc))
print()
print("  CONTROL: reset/R4 was measured redundant by an independent, "
      "hand-built")
print("  experiment on 2026-09-22.  This harness must reproduce that, or its "
      "new")
print("  answers are not believable.")
r4 = [r for r in rows if r[0] == "reset" and r[1] == "R4"]
if r4 and r4[0][2] == "PASS" and not r4[0][3]:
    print("  CONTROL PASSES: reset/R4 independently re-measured as SUBSUMED.")
    ok = True
else:
    print(f"  CONTROL FAILS: reset/R4 came back {r4[0][4] if r4 else 'missing'}"
          " -- the harness disagrees with 2026-09-22 and must be believed "
          "less than it is.")
    ok = False
if bad_guard:
    print()
    print("  GUARD VIOLATIONS (cells affected are unscored):")
    for b in bad_guard:
        print("    " + b)
print()
print("  SCOPE: 'subsumed' is relative to the mutant set listed above and to "
      "the BMC")
print("  depth of each job.  It is evidence that a property earns nothing "
      "HERE, not a")
print("  proof that it is redundant.  No property is deleted on the strength "
      "of it.")
sys.exit(0 if ok and not bad_guard else 1)
