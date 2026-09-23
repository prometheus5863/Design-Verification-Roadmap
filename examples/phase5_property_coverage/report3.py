#!/usr/bin/env python3
"""
report3.py -- phase 3. Close the holes phase 2 found, and see what happens.

Phase 2 said C1, C6, C7 (CSR) and P3 (FIFO) are UNEXERCISED: no mutant in
the 2026-09-20/09-21 sets is visible to them. That is a statement about the
mutant set, so the response is to inject the missing defects and re-measure.

Each gap mutant targets one property, and there are three possible outcomes,
all of them informative:

  DETECTED, and MISSED when the target property is deleted
      -> the hole is closed. The property moves from UNEXERCISED to
         LOAD-BEARING and the mutant set is genuinely better.
  DETECTED, but still detected without the target property
      -> the property is SHADOWED after all; something else sees the defect.
  NOT DETECTED AT ALL
      -> an ESCAPE. The suite does not catch a real defect. This is the
         only outcome that is about the DESIGN's verifiability rather than
         about bookkeeping, and it is the one worth a note.
"""
import sys
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from build_variants import SUITES

res = {}
for f in sys.argv[1:]:
    for line in open(f):
        line = line.strip()
        if not line:
            continue
        d, v = line.rsplit(" ", 1)
        parts = d.split("/")
        res[(parts[-2], parts[-1])] = v

PLAN = [("csr", "C1", "N8"), ("csr", "C6", "N9"), ("fifo", "P3", "M6")]
print("=" * 78)
print("PHASE 3: gap-closing mutants for the properties phase 2 found "
      "UNEXERCISED")
print("=" * 78)
for suite, prop, m in PLAN:
    desc = SUITES[suite]["gap_mutants"][m][0]
    base = res.get((suite, f"base__{m}"))
    drop = res.get((suite, f"drop{prop}__{m}"))
    only = res.get((suite, f"only{prop}__{m}"))
    if base != "FAIL":
        verdict = (f"ESCAPE -- the FULL suite does not detect {m}")
    elif drop == "PASS":
        verdict = f"HOLE CLOSED -- {prop} is now LOAD-BEARING for {m}"
    else:
        verdict = f"{prop} SHADOWED for {m} -- something else catches it"
    print(f"  {m:<4} targets {suite}/{prop:<3} base={str(base):<5} "
          f"drop{prop}={str(drop):<5} only{prop}={str(only):<5}  {verdict}")
    print(f"       ({desc})")

print()
n10 = res.get(("csr", "base__N10"))
print("  CONTROL N10, for the N9 escape. N9 removes the clear of frame_err on")
print("  a STATUS read and the suite does not notice. Two explanations: C6 is")
print("  broken, or frame_err simply cannot be SET within the job's depth of")
print("  20 (a real frame error needs ~145 clocks -- the same solver-budget")
print("  boundary days 1, 2 and 3 all hit). N10 makes a STATUS read SET")
print("  frame_err instead, which needs no RX activity at all.")
print(f"  N10 verdict: {n10}")
if n10 == "FAIL":
    print("  => C6 and C7 are LIVE and evaluable; they fail N10 at step 3.")
    print("     The N9 escape is therefore a BOUND problem, not a property")
    print("     problem: a property can be non-vacuous, non-subsumed, live")
    print("     and still blind to a real defect whose precondition lies")
    print("     beyond the BMC depth. That is a FIFTH way a passing property")
    print("     can mean nothing, and no vacuity check in this repo detects")
    print("     it -- the cover that would have (`cover(... $past(frame_err))`)")
    print("     is the one sitting in the FORMAL_CSR_DEEP job that smtbmc")
    print("     cannot finish.")
else:
    print("  => UNEXPECTED. C6 does not even catch a bit it sets itself.")
    print("     Investigate C6 before believing anything else about it.")
