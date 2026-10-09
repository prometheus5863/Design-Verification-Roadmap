#!/usr/bin/env python3
"""Mutation test for reachable_cross_under_per_byte_rule.py, 2026-10-02.

Control A (09-30): the unmutated suite must PASS, or a detection proves
nothing.
Control B (10-01 item, 'every mutant in this repository needs control B'): a
SEMANTICS-PRESERVING edit must leave the suite PASSING, or the suite is merely
failing on any edit and its detections carry no information about which edit.

THE ARRIVAL CONTROL, ADDED 2026-10-09 (`arrival_control.py`).  2026-10-08's
rule: a mutant may be scored SURVIVED only after it has been shown to have
changed something the mechanism prints.  This harness is the first of the five
named in 10-08's backlog item to be wired, because it is the only one whose
target is a python suite rather than a uvm-python simulation and so can be
re-run inside one session -- the point of wiring one and measuring it rather
than wiring five and running none.

WHAT IT MEASURES HERE, and this was not obvious before running it.  Three rows
of this harness are REQUIRED to survive: CONTROL B (a semantics-preserving
rename) and M6a/M6b, whose prose argues that "a weakened assertion still holds
on correct input, so no self-run can catch it".  Both of those are arguments
that the mutant changes nothing the suite prints -- which is exactly what the
arrival control measures.  So for this harness the arrival control does not
hunt false SURVIVED verdicts; it turns the harness's own central argument from
prose into a byte comparison.  A row scored INERT here is the harness's thesis
CONFIRMED, not a defect found, and that distinction is recorded because an
INERT count is read as bad news in every other harness.
"""
import os, re, shutil, subprocess, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import arrival_control as AC

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

# The mechanism's output block, for the arrival control.  For this harness the
# mechanism IS the suite's printed check output, so the block is every PASS/FAIL
# line plus the TOTAL -- i.e. everything the suite ASSERTS, with the derived
# tables and set listings excluded on purpose.  A mutant that changes a printed
# table without changing any verdict has not reached the detection mechanism,
# which is the thing being mutation-tested.
BLOCK_RE = re.compile(r"^\s*(?:\[(?:PASS|FAIL)\]|PASS|FAIL)\b.*$|^TOTAL:.*$",
                      re.M)


def mechanism_block(stdout):
    """-> the mechanism's verdict block, or "" if the suite printed none.

    Returning "" rather than raising is deliberate: arrival_control.arrival()
    turns it into NO_OBSERVATION, which VOIDS the row.  A two-valued
    `mutant != baseline` would have called it ARRIVED.
    """
    lines = [m.group(0).rstrip() for m in BLOCK_RE.finditer(stdout)]
    return "\n".join(lines)


def run(d):
    p = subprocess.run([sys.executable, SRC], cwd=d, capture_output=True, text=True)
    blk = mechanism_block(p.stdout)
    m = re.search(r"TOTAL: (\d+) passed, (\d+) failed", p.stdout)
    if not m:
        return None, None, p.stdout[-400:] + p.stderr[-400:], blk
    return int(m.group(1)), int(m.group(2)), "", blk

def main():
    print("=" * 76)
    print("MUTATION TEST -- reachable_cross_under_per_byte_rule.py  2026-10-02")
    print("=" * 76)
    base = tempfile.mkdtemp(prefix="dvmut_")
    clean = os.path.join(base, "clean")
    shutil.copytree(HERE, clean)
    npass, nfail, err, baseline_blk = run(clean)
    print("\nCONTROL A -- the unmutated suite")
    print("  %s passed, %s failed   %s" % (npass, nfail, err))
    ok_a = (nfail == 0 and npass and npass >= 20)
    print("  [%s] control A: a detection below means something only if this "
          "passes" % ("PASS" if ok_a else "FAIL"))
    n_block = len(baseline_blk.splitlines())
    ok_blk = n_block >= 20
    print("  [%s] control A printed a %d-line mechanism block for the arrival "
          "control to compare against" % ("PASS" if ok_blk else "FAIL", n_block))
    if not ok_blk:
        print("  ABORTING: a baseline with no mechanism block is not a "
              "baseline (2026-10-02 check R0).")
        shutil.rmtree(base, ignore_errors=True)
        return 1
    ok_a = ok_a and ok_blk
    results = []
    src0 = open(os.path.join(clean, SRC)).read()
    for name, old, new, should_detect in MUTANTS:
        d = os.path.join(base, re.sub(r"\W+", "_", name)[:40])
        shutil.copytree(clean, d)
        path = os.path.join(d, SRC)
        s = open(path).read()
        if old not in s:
            results.append((name, should_detect, None, None,
                            "MUTANT NOT APPLIED", AC.NO_OBSERVATION, "", False))
            continue
        s = s.replace(old, new, 1)
        if name.startswith("M6b"):
            # the compound half: also perturb the measurement the anchor guards
            assert "V8_CLOSURE_SEED = 20260930" in s
            s = s.replace("V8_CLOSURE_SEED = 20260930",
                          "V8_CLOSURE_SEED = 20260931", 1)
        open(path, "w").write(s)
        p_, f_, e_, blk = run(d)
        crashed = (f_ is None)          # no TOTAL line: the suite did not finish
        detected = crashed or (f_ > 0)
        arr_tok, arr_detail = AC.arrival(baseline_blk, blk,
                                        what="the suite's verdict block")
        results.append((name, should_detect, detected, (p_, f_), e_,
                        arr_tok, arr_detail, crashed))
    print("\nMUTANTS")
    print("-" * 76)
    agree = 0
    n_inert = 0
    n_voided = 0
    for name, should, detected, tally, e, arr_tok, arr_detail, crashed in results:
        if detected is None:
            verdict = "NOT APPLIED"
        elif should and detected:
            verdict = ("DETECTED-BY-CRASH (see below)" if crashed
                       else "DETECTED-BY-CHECK (correct)")
            agree += 1
        elif should and not detected:
            verdict = "*** ESCAPED ***"
        elif (not should) and (not detected):
            verdict = "SURVIVED (correct -- control B)"; agree += 1
        else:
            verdict = "*** CONTROL B FALSE ALARM ***"
        print("  %-58s %s" % (name[:58], verdict))
        if tally and tally[0] is not None:
            print("        tally: %s passed, %s failed" % tally)
        if detected is not None:
            print("        arrival: %s" % arr_tok)
            if arr_tok == AC.INERT:
                n_inert += 1
            elif arr_tok == AC.NO_OBSERVATION:
                n_voided += 1
        if e:
            print("        " + e.strip().split("\n")[-1][:90])
    print("-" * 76)
    print("  %d of %d mutants behaved as required" % (agree, len(results)))
    print("  Six mutants must be DETECTED, three must SURVIVE: the")
    print("  semantics-preserving rename (the 10-01 control-B requirement) and")
    print("  M6a/M6b, which together with M6c show that the 703 anchor's")
    print("  strictness is load-bearing and cannot be tested by a self-run")
    print("  that only weakens it.")

    # ------------------------------------------------------------------
    # The arrival control's own report, 2026-10-09
    # ------------------------------------------------------------------
    print()
    print("ARRIVAL CONTROL (arrival_control.py, three-valued)")
    print("-" * 76)
    print("  %-58s %s" % ("mutant", "arrival"))
    for name, should, detected, tally, e, arr_tok, arr_detail, crashed in results:
        if detected is None:
            continue
        print("  %-58s %-15s %s"
              % (name[:58], arr_tok, "(suite crashed)" if crashed else ""))
    print()
    print("  INERT: %d   ARRIVED: %d   NO_OBSERVATION: %d"
          % (n_inert,
             sum(1 for r in results
                 if r[2] is not None and r[5] == AC.ARRIVED),
             n_voided))
    print()
    print("  Every row this harness REQUIRES to survive is expected to be")
    print("  INERT, and that is the point rather than a problem:")
    print("    CONTROL B is a semantics-preserving rename, so a byte-identical")
    print("      verdict block is its specification, not a weakness.")
    print("    M6a and M6b weaken an assertion that still holds on correct")
    print("      input.  The harness has argued since 10-02 that no self-run")
    print("      can catch that.  INERT is that argument MEASURED: the suite")
    print("      did not fail to notice the mutant, the mutant produced")
    print("      nothing for it to notice.")
    print("  So an INERT count here is not the bad news it is in the other")
    print("  harnesses.  What would be bad news is an ARRIVED row scored")
    print("  SURVIVED -- a mutant that changed the verdict block and went")
    print("  uncaught -- and there are none.")
    arrived_and_survived = [
        r[0] for r in results
        if r[2] is False and r[5] == AC.ARRIVED]
    ok_arr = not arrived_and_survived
    print("  [%s] no row is both ARRIVED and uncaught"
          % ("PASS" if ok_arr else "FAIL"))
    if arrived_and_survived:
        for n in arrived_and_survived:
            print("        ARRIVED AND UNCAUGHT: %s" % n)

    # Every NO_OBSERVATION row must be accounted for by a crash.  A row with
    # no verdict block and no crash would be the real void: the suite finished,
    # printed nothing the mechanism reports, and was scored anyway.
    unexplained = [r[0] for r in results
                   if r[5] == AC.NO_OBSERVATION and r[2] is not None
                   and not r[7]]
    ok_void = not unexplained
    print("  [%s] every NO_OBSERVATION row is explained by the suite crashing"
          % ("PASS" if ok_void else "FAIL"))
    for n in unexplained:
        print("        UNEXPLAINED NO_OBSERVATION: %s" % n)

    # ------------------------------------------------------------------
    # The detection split, 2026-10-09.  This is the session's finding.
    # ------------------------------------------------------------------
    by_check = [r[0] for r in results if r[2] and not r[7]]
    by_crash = [r[0] for r in results if r[2] and r[7]]
    print()
    print("DETECTION SPLIT -- what actually caught each detected mutant")
    print("-" * 76)
    print("  DETECTED BY A FAILING CHECK : %d" % len(by_check))
    for n in by_check:
        print("      %s" % n[:66])
    print("  DETECTED BY AN UNHANDLED EXCEPTION : %d" % len(by_crash))
    for n in by_crash:
        print("      %s" % n[:66])
    print()
    print("  Before today both columns read 'DETECTED (correct)'.  The")
    print("  detection rule is `detected = (f_ is None) or (f_ > 0)`, and")
    print("  `f_ is None` means the TOTAL line is absent -- the suite did not")
    print("  finish.  A crash is not this suite's checks catching anything;")
    print("  it is the python interpreter catching it, in the same column and")
    print("  the same words.  2026-10-06: credit assigned to a mechanism that")
    print("  did not earn it.")
    print()
    print("  Why this is NOT simply a bug to be scored as an escape: a crash")
    print("  does mean the mutant was not silently accepted, so the mutant")
    print("  is genuinely not a hole in the suite today.  The exposure is")
    print("  CONDITIONAL and that is what makes it worth a number -- if the")
    print("  suite is ever made to degrade gracefully, or wrapped in a")
    print("  try/except, %d of %d detections become silent passes and NO ROW"
          % (len(by_crash), len(by_check) + len(by_crash)))
    print("  OF THIS HARNESS CHANGES.  A check that would catch each of the")
    print("  three on its own terms is a named follow-on item, not a repair")
    print("  attempted in the same session that found the need for it.")
    ok_split = len(by_check) > 0
    print("  [%s] at least one detection is by a failing check, so the suite "
          "is not detecting purely by crashing"
          % ("PASS" if ok_split else "FAIL"))
    shutil.rmtree(base, ignore_errors=True)
    return 0 if (ok_a and agree == len(results) and ok_arr
                 and ok_void and ok_split) else 1

if __name__ == "__main__":
    sys.exit(main())
