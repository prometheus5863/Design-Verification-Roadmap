#!/usr/bin/env python3
"""Mutation test for reachable_cross_under_per_byte_rule.py, 2026-10-02.

Control A (09-30): the unmutated suite must PASS, or a detection proves
nothing.
Control B (10-01 item, 'every mutant in this repository needs control B'): a
SEMANTICS-PRESERVING edit must leave the suite PASSING, or the suite is merely
failing on any edit and its detections carry no information about which edit.
"""
import os, re, shutil, subprocess, sys, tempfile

SRC = "reachable_cross_under_per_byte_rule.py"
HERE = os.path.dirname(os.path.abspath(__file__))

MUTANTS = [
  ("M1 span_of returns g_first, collapsing the nine to all 256",
   '        if bits[i] != bits[i - 1]:\n            last = i',
   '        if bits[i] != bits[i - 1]:\n            last = min(i, M.g_first_of(byte))',
   True),
  ("M2 closed form uses 2^k instead of 256 - 2^k",
   'return {(256 - (1 << k)) & 0xFF for k in range(M.N_DATA + 1)}',
   'return {(1 << k) & 0xFF for k in range(M.N_DATA + 1)}',
   True),
  ("M3 the single-transition test becomes == 3",
   'return {b for b in range(256) if M.transition_count(b) == 1}',
   'return {b for b in range(256) if M.transition_count(b) == 3}',
   True),
  ("M4 reachable_cross ignores the exclusion it is given",
   '        if b in excluded:\n            continue',
   '        if False:\n            continue',
   True),
  ("M5 closure gives up after one draw",
   'def closure_draws(excluded, seed, cap=CLOSURE_CAP):',
   'def closure_draws(excluded, seed, cap=1):',
   True),
  # M6's FIRST FORM WAS MIS-SPECIFIED AND IT ESCAPED, CORRECTLY.  It weakened
  # the 703-draw anchor to `n_old is not None` and required detection.  But a
  # weakened assertion still HOLDS on correct input, so no self-run can catch
  # it: running the suite tests the measurement against the assertion, and this
  # mutant changes the assertion, not the measurement.  (The same fault form as
  # 2026-10-02's graphene control C2, found the same day in the other
  # repository -- a control built from the wrong quantity.)  Recorded rather
  # than deleted, and replaced by the COMPOUND form that does test what the
  # first form was reaching for: whether the anchor's strictness is
  # load-bearing.  Three parts, and only together do they say anything.
  ("M6a weaken the 703 anchor alone -- must SURVIVE, because a weakened "
   "assertion still holds on correct input",
   '          n_old == V8_CLOSURE_DRAWS,',
   '          n_old is not None,',
   False),
  ("M6b weaken the anchor AND perturb the measurement -- must SURVIVE, "
   "which is what makes the weakening dangerous",
   '          n_old == V8_CLOSURE_DRAWS,\n',
   '          n_old is not None,\n',
   False),
  ("M6c perturb the measurement with the anchor INTACT -- must be DETECTED, "
   "which is what makes the anchor load-bearing",
   'V8_CLOSURE_SEED = 20260930',
   'V8_CLOSURE_SEED = 20260931',
   True),
  ("CONTROL B -- semantics-preserving: rename a local loop variable",
   '    bits = M.framed_bits(byte)\n    last = 0\n    for i in range(1, len(bits)):\n'
   '        if bits[i] != bits[i - 1]:\n            last = i\n    return last',
   '    bits = M.framed_bits(byte)\n    where = 0\n    for j in range(1, len(bits)):\n'
   '        if bits[j] != bits[j - 1]:\n            where = j\n    return where',
   False),
]

def run(d):
    p = subprocess.run([sys.executable, SRC], cwd=d, capture_output=True, text=True)
    m = re.search(r"TOTAL: (\d+) passed, (\d+) failed", p.stdout)
    if not m:
        return None, None, p.stdout[-400:] + p.stderr[-400:]
    return int(m.group(1)), int(m.group(2)), ""

def main():
    print("=" * 76)
    print("MUTATION TEST -- reachable_cross_under_per_byte_rule.py  2026-10-02")
    print("=" * 76)
    base = tempfile.mkdtemp(prefix="dvmut_")
    clean = os.path.join(base, "clean")
    shutil.copytree(HERE, clean)
    npass, nfail, err = run(clean)
    print("\nCONTROL A -- the unmutated suite")
    print("  %s passed, %s failed   %s" % (npass, nfail, err))
    ok_a = (nfail == 0 and npass and npass >= 20)
    print("  [%s] control A: a detection below means something only if this "
          "passes" % ("PASS" if ok_a else "FAIL"))
    results = []
    src0 = open(os.path.join(clean, SRC)).read()
    for name, old, new, should_detect in MUTANTS:
        d = os.path.join(base, re.sub(r"\W+", "_", name)[:40])
        shutil.copytree(clean, d)
        path = os.path.join(d, SRC)
        s = open(path).read()
        if old not in s:
            results.append((name, should_detect, None, None, "MUTANT NOT APPLIED"))
            continue
        s = s.replace(old, new, 1)
        if name.startswith("M6b"):
            # the compound half: also perturb the measurement the anchor guards
            assert "V8_CLOSURE_SEED = 20260930" in s
            s = s.replace("V8_CLOSURE_SEED = 20260930",
                          "V8_CLOSURE_SEED = 20260931", 1)
        open(path, "w").write(s)
        p_, f_, e_ = run(d)
        detected = (f_ is None) or (f_ > 0)
        results.append((name, should_detect, detected, (p_, f_), e_))
    print("\nMUTANTS")
    print("-" * 76)
    agree = 0
    for name, should, detected, tally, e in results:
        if detected is None:
            verdict = "NOT APPLIED"
        elif should and detected:
            verdict = "DETECTED (correct)"; agree += 1
        elif should and not detected:
            verdict = "*** ESCAPED ***"
        elif (not should) and (not detected):
            verdict = "SURVIVED (correct -- control B)"; agree += 1
        else:
            verdict = "*** CONTROL B FALSE ALARM ***"
        print("  %-58s %s" % (name[:58], verdict))
        if tally and tally[0] is not None:
            print("        tally: %s passed, %s failed" % tally)
        if e:
            print("        " + e.strip().split("\n")[-1][:90])
    print("-" * 76)
    print("  %d of %d mutants behaved as required" % (agree, len(results)))
    print("  Six mutants must be DETECTED, three must SURVIVE: the")
    print("  semantics-preserving rename (the 10-01 control-B requirement) and")
    print("  M6a/M6b, which together with M6c show that the 703 anchor's")
    print("  strictness is load-bearing and cannot be tested by a self-run")
    print("  that only weakens it.")
    shutil.rmtree(base, ignore_errors=True)
    return 0 if (ok_a and agree == len(results)) else 1

if __name__ == "__main__":
    sys.exit(main())
