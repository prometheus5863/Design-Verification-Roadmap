#!/usr/bin/env python3
"""
report2.py -- phase 2. Split "subsumed" into the two things it can mean.

Phase 1 can only say that deleting a property changes no verdict. That is
compatible with two very different situations, and a report that does not
separate them is misleading:

  SHADOWED    p CAN detect a defect on its own, but something else in the
              compile detects it too, so p never changes a verdict.
              -> a real redundancy finding; p is doing work that is done
                 twice.
  UNEXERCISED p detects NOTHING on its own in this mutant set.
              -> not a statement about p at all. It is a statement about the
                 MUTANT SET: no injected defect touches the behaviour p
                 describes. The fix is more mutants, not fewer properties.

The discriminator is the solo experiment 2026-09-22 ran by hand for R4:
build a variant with p as the ONLY live property and re-run every mutant.

"Only" means only -- including across suites. The CSR job compiles
-DFORMAL -DFORMAL_CSR and the reset job -DFORMAL -DFORMAL_CSR_RESET, so both
silently carry the 2026-09-20 FIFO invariants. A CSR property found
redundant may be redundant against another day's suite, which is not
something a within-suite experiment can see.
"""
import sys
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from build_variants import SUITES

res = {}
for line in open(sys.argv[1]):
    line = line.strip()
    if not line:
        continue
    d, v = line.rsplit(" ", 1)
    parts = d.split("/")
    res[(parts[-2], parts[-1])] = v

targets = [a.split("/") for a in sys.argv[2:]]
print("=" * 78)
print("PHASE 2: solo detection power -- shadowed vs unexercised")
print("=" * 78)
classes = {}
for suite, p in targets:
    muts = list(SUITES[suite]["mutants"])
    oc = res.get((suite, f"only{p}__clean"))
    dc = res.get((suite, f"drop{p}__clean"))
    solo = [m for m in muts if res.get((suite, f"only{p}__{m}")) == "FAIL"]
    owned = [m for m in muts
             if res.get((suite, f"drop{p}__{m}")) == "PASS"
             and res.get((suite, f"base__{m}"), "FAIL") == "FAIL"]
    if oc != "PASS" or dc != "PASS":
        cls = f"INCONCLUSIVE (only-clean={oc}, drop-clean={dc})"
    elif owned:
        cls = "LOAD-BEARING for " + ",".join(owned)
    elif solo:
        cls = "SHADOWED -- detects " + ",".join(solo) + " alone, never uniquely"
    else:
        cls = "UNEXERCISED -- no mutant in this set is visible to it"
    classes[(suite, p)] = cls
    print(f"  {suite}/{p:<3} only-clean={str(oc):<5} drop-clean={str(dc):<5} "
          f"solo-detects={','.join(solo) if solo else '(none)':<14} {cls}")

print()
print("  Counts: "
      + ", ".join(f"{k}={sum(1 for c in classes.values() if c.startswith(k))}"
                  for k in ("LOAD-BEARING", "SHADOWED", "UNEXERCISED",
                            "INCONCLUSIVE")))
print()
print("  CONTROL, again: reset/R4 was hand-measured on 2026-09-22 as")
print("  detecting K3 alone while never changing a verdict -- i.e. SHADOWED,")
print("  not unexercised. Phase 2 must reproduce that distinction, not just")
print("  the coarse 'redundant' verdict phase 1 reproduced.")
r4 = classes.get(("reset", "R4"), "")
print("  CONTROL " + ("PASSES" if r4.startswith("SHADOWED")
                      else f"FAILS: got {r4}"))
