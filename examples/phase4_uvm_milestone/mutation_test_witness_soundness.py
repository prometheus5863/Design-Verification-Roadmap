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

2026-10-10 -- AN ARRIVAL CONTROL, AND PROVENANCE ON THE POSITIVE COLUMN
----------------------------------------------------------------------
This harness was the cheapest unwired row of `arrival_control_census.py`
(2026-10-09) and it carried BOTH of that session's open defects:

  * NO ARRIVAL CONTROL AT ALL.  A row marked SURVIVE was scored on the
    strength of a stimulus nobody had shown reached the mechanism.  2026-10-08:
    a mutant reporting SURVIVED under a stimulus that cannot reach it is a
    false finding about working code, and it arrives with a transcript.
  * NO PROVENANCE ON A DETECTION.  The rule was `detected = rc != 0`, and a
    python traceback also exits non-zero.  2026-10-09, in this repository's own
    `mutation_test_reachable_cross.py`: three of six detections turned out to
    be the interpreter catching the mutant, reported in the same column and the
    same words as the three a check caught.

Both are fixed here, and one NEW observation came out of fixing the first.

THE ARRIVAL BLOCK MUST NOT CONTAIN THE VERDICTS
-----------------------------------------------
`witness_soundness.py` prints its computed report in SECTIONS 1-8 and its
PASS/FAIL list after SUMMARY -- except that SECTION 8's controls print
`[PASS]`/`[FAIL]` INLINE, interleaved with the numbers those controls computed.
An arrival block cut straight out of SECTIONS 1-8 therefore contains verdict
tokens, and an arrival control that reads a verdict token is reading the
killer: it stops being independent of the thing it exists to be independent of.
`mechanism_block()` normalises `[PASS]`/`[FAIL]` to `[VERDICT]` for that
reason, and the harness computes arrival BOTH WAYS and reports the
disagreement rather than asserting there is none (2026-10-09's rule, applied to
this session's own instrument).

M9 is the mutant that makes the disagreement visible: it changes C1's expected
tuple from (25, 23, 16) to (25, 23, 15), so C1 FAILS while the numbers it
prints are byte-identical -- because C1's detail string is a TYPED LITERAL,
"no exclusion 25, 2-byte 23, 9-byte 16", and not derived from the three lengths
it checks.  Verdict-stripped arrival calls M9 INERT, which is correct: it
reached no mechanism.  Raw arrival calls it ARRIVED, on the strength of a
`[PASS]` that became a `[FAIL]`.

M9 also records a small fault in the audited file: a check whose detail cannot
drift with the quantity it checks is 2026-10-01's naming fault in its
detail-string form.  It is reported, not fixed, because `witness_soundness.py`
owns a committed transcript.

WHAT CHANGED IN THE EXPECTATION TABLE, AND WHY THAT IS NOT A LOOSENING
----------------------------------------------------------------------
Three rows previously expected SURVIVE and now expect INERT: control B's
rename, and M8a's threshold weakening.  Both of them change no computed
quantity, so under a three-valued control the honest verdict is that they never
arrived -- the same thing that happened to `mutation_test_reachable_cross.py`'s
required-to-survive rows on 2026-10-09, where an INERT count was the
specification.  M8b still expects SURVIVED, and that is the whole point of the
compound form: it perturbs `allbord`, which C3 reports, so it ARRIVES and is
not caught.

Run:  python3 mutation_test_witness_soundness.py
      python3 mutation_test_witness_soundness.py --selftest   (extractor only)
"""

import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import arrival_control as ac

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, "witness_soundness.py")
SURVIVE, DETECT, INERT = "SURVIVE", "DETECT", "INERT"

BY_CHECK = "DETECTED_BY_CHECK"
BY_CRASH = "DETECTED_BY_CRASH"
INCONSISTENT = "EXIT_CODE_DISAGREES_WITH_VERDICT_TEXT"

# (id, expectation, description, [(old, new), ...])
MUTANTS = [
    ("A", INERT,
     "control A: no edit at all. Under a three-valued arrival control this row "
     "is NOT a tautology -- the harness runs the suite twice and compares the "
     "two reports, so an ARRIVED here would mean the audited suite is "
     "NONDETERMINISTIC and every INERT below would be unreliable. Control A is "
     "now the DETERMINISM control that the rest of the table rests on; the "
     "'must pass unmutated' half is checked in the pre-flight abort above, "
     "where a missing block stops the run (10-02 check R0)", []),
    ("B", INERT,
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

    ("M8a", INERT,
     "weaken C3's threshold ALONE (7 of 7 unsound -> at least one unsound). A "
     "weakened assertion still holds on correct input, so this MUST survive; "
     "requiring detection here would be the 10-02 M6 mis-specification",
     [("          len(unsound(gbord)) == len(gbord) == 7,",
       "          len(unsound(gbord)) >= 1,")]),
    ("M8b", INERT,
     "weaken C3's threshold AND perturb what it guards: allbord now marks only "
     "0x40 borderline. 10-03 required SURVIVE here; 10-10 measures INERT, and "
     "that SHARPENS the finding rather than weakening it. C3's detail string is "
     "the typed literal \"7 of 7 -- so the instrument is not hard-coded...\", so "
     "the perturbed quantity is never PRINTED: the mutant is not merely "
     "uncaught, it is UNOBSERVABLE, and the weakened threshold was its SOLE "
     "observer. 10-02 concluded the threshold is load-bearing; this says the "
     "threshold is the only load-bearing thing there is",
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

    ("M9", DETECT,
     "break C1's EXPECTED TUPLE only (25,23,16) -> (25,23,15). The suite must "
     "fail, and NOTHING COMPUTED CHANGES, because C1's detail line is a typed "
     "literal rather than a format of the three lengths it checks. This is the "
     "row that makes the verdict-stripped and raw arrival rules disagree: "
     "stripped says INERT (correctly -- no mechanism was reached), raw says "
     "ARRIVED on the strength of a [PASS] becoming a [FAIL]",
     [("          (len(xr0), len(xr8), len(xr10)) == (25, 23, 16),",
       "          (len(xr0), len(xr8), len(xr10)) == (25, 23, 15),")]),
]


# ---------------------------------------------------------------------------
# the mechanism's output block
# ---------------------------------------------------------------------------
VERDICT_TOKENS = ("[PASS]", "[FAIL]")


def mechanism_block(out, strip_verdicts=True):
    """The lines witness_soundness.py prints as its COMPUTED REPORT, i.e.
    SECTION 1 up to (not including) the SUMMARY banner.

    Returns None when either marker is absent, which is what gives
    arrival_control a NO_OBSERVATION rather than a comparison against "".

    strip_verdicts=True normalises SECTION 8's inline [PASS]/[FAIL] to
    [VERDICT].  Without it this block contains the suite's verdicts and the
    arrival control is no longer independent of the killer -- see the module
    docstring, and M9 for the row where the two rules disagree.
    """
    if not out:
        return None
    lines = out.split("\n")
    start = end = None
    for i, ln in enumerate(lines):
        if start is None and ln.startswith("SECTION "):
            start = i
        if ln.strip() == "SUMMARY":
            end = i
            break
    if start is None or end is None or end <= start:
        return None
    body = lines[start:end]
    while body and set(body[-1].strip()) in ({"="}, set()):
        body.pop()
    if strip_verdicts:
        body = [ln.replace("[PASS]", "[VERDICT]").replace("[FAIL]", "[VERDICT]")
                for ln in body]
    return "\n".join(body) + "\n"


def detail_census(path=None):
    """Which of the audited suite's `check(label, cond, detail)` calls print a
    detail DERIVED from the quantity they check, and which print a TYPED
    LITERAL?  -> (literal_labels, derived_labels)

    This exists because it is the mechanism behind two INERT rows below.  A
    check whose detail is a literal reports a number that CANNOT DRIFT with
    what it verifies, so a mutant that perturbs that quantity changes the
    verdict and changes nothing in the report -- which makes it invisible to
    any arrival control, this one included.  2026-10-01's "a name that cannot
    drift is the whole requirement", in detail-string form.
    """
    import ast
    src = open(path or TARGET, encoding="utf-8").read()
    lit, der = [], []
    for node in ast.walk(ast.parse(src)):
        if not (isinstance(node, ast.Call)
                and getattr(node.func, "id", "") == "check"):
            continue
        label = " ".join(ast.get_source_segment(src, node.args[0]).split())
        label = label.strip('"').replace('" "', "")[:62]
        if len(node.args) < 3:
            lit.append(label + "   [NO DETAIL AT ALL]")
            continue
        seg = ast.get_source_segment(src, node.args[2])
        derived = ("%" in seg or ".format" in seg
                   or seg.lstrip().startswith("f\"")
                   or seg.lstrip().startswith("f'"))
        (der if derived else lit).append(label)
    return lit, der


def provenance(rc, total_line):
    """What produced a non-zero exit: a failing check, or a crash?  -> (tag, detail)

    2026-10-09: a verdict must name the mechanism that produced it.  The third
    branch is the one this repository has twice found live (09-19, 09-20) --
    the subsystem reporting the verdict decoupled from the one doing the
    checking -- so it is a FAULT here and not a tidy-up.
    """
    failed = None
    if total_line and "failed" in total_line:
        try:
            failed = int(total_line.split("passed,")[1].split("failed")[0])
        except (IndexError, ValueError):
            failed = None
    if rc == 0:
        if failed:
            return INCONSISTENT, ("exit 0 but the verdict text reports %d "
                                  "failing checks" % failed)
        return "", ""
    if failed is None:
        return BY_CRASH, ("no TOTAL line at all: the suite died before "
                          "reporting, so the interpreter caught this mutant "
                          "and no check did")
    if failed == 0:
        return INCONSISTENT, ("non-zero exit but the verdict text reports 0 "
                              "failing checks")
    return BY_CHECK, "%d of the suite's own checks failed" % failed


def run_mutant(mid, edits):
    """-> (rc, total_line, stdout, error).  rc is None on a harness error."""
    src = open(TARGET, encoding="utf-8").read()
    for old, new in edits:
        if old not in src:
            return None, None, "", "EDIT DID NOT APPLY: %r" % old[:60]
        if src.count(old) != 1:
            return None, None, "", "EDIT NOT UNIQUE (%d matches)" % src.count(old)
        src = src.replace(old, new)
    path = os.path.join(HERE, "_mutant_%s.py" % mid)
    try:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(src)
        p_ = subprocess.run([sys.executable, path], capture_output=True,
                            text=True, timeout=900)
        tail = [l for l in p_.stdout.strip().split("\n")
                if l.startswith("TOTAL:")]
        err = ""
        if not tail and p_.stderr.strip():
            err = p_.stderr.strip().split("\n")[-1][:90]
        return p_.returncode, (tail[-1] if tail else None), p_.stdout, err
    finally:
        if os.path.exists(path):
            os.remove(path)


# ---------------------------------------------------------------------------
# selftest: the extractor, exercised on its own failure paths
# ---------------------------------------------------------------------------
def selftest():
    """2026-10-01: a control that cannot fail is not a control, and that
    applies to the block extractor too."""
    ok = bad = 0

    def t(label, cond, detail=""):
        nonlocal ok, bad
        ok += bool(cond)
        bad += not cond
        print("  [%s] %s" % ("PASS" if cond else "FAIL", label))
        if detail:
            print("         %s" % detail)

    sample = ("banner\n"
              "SECTION 1 -- x\n"
              "  value 7\n"
              "  [PASS] a control\n"
              "        detail 7 of 7\n"
              "============\n"
              "SUMMARY\n"
              "  [PASS] a verdict\n"
              "TOTAL: 1 passed, 0 failed\n")
    blk = mechanism_block(sample)
    t("the block starts at SECTION 1 and stops before SUMMARY",
      blk.startswith("SECTION 1 -- x") and "SUMMARY" not in blk
      and "a verdict" not in blk, repr(blk))
    t("inline verdict tokens are normalised away",
      "[VERDICT]" in blk and "[PASS]" not in blk and "[FAIL]" not in blk)
    t("and are NOT normalised when the caller asks for the raw block",
      "[PASS]" in mechanism_block(sample, strip_verdicts=False))
    t("a [PASS] -> [FAIL] flip with no numeric change is INVISIBLE to the "
      "stripped block and VISIBLE to the raw one -- M9's mechanism",
      mechanism_block(sample.replace("[PASS] a control", "[FAIL] a control"))
      == blk
      and mechanism_block(sample.replace("[PASS] a control",
                                         "[FAIL] a control"),
                          strip_verdicts=False)
      != mechanism_block(sample, strip_verdicts=False))
    t("no SECTION marker -> None, so arrival_control sees NO_OBSERVATION",
      mechanism_block("SUMMARY\nTOTAL: 0 passed, 0 failed\n") is None)
    t("no SUMMARY banner (a suite that died mid-report) -> None",
      mechanism_block("SECTION 1 -- x\n  value 7\n") is None)
    t("empty output -> None", mechanism_block("") is None)
    t("None output -> None", mechanism_block(None) is None)
    t("and None reaches arrival_control as NO_OBSERVATION",
      ac.arrival(blk, None)[0] == ac.NO_OBSERVATION)

    t("provenance: non-zero with failing checks is BY_CHECK",
      provenance(1, "TOTAL: 40 passed, 6 failed")[0] == BY_CHECK)
    t("provenance: non-zero with NO TOTAL line is BY_CRASH",
      provenance(1, None)[0] == BY_CRASH)
    t("provenance: non-zero with 0 failing checks is a FAULT, not a detection",
      provenance(1, "TOTAL: 46 passed, 0 failed")[0] == INCONSISTENT)
    t("provenance: exit 0 while the text reports failures is the same FAULT "
      "from the other side (09-19, 09-20 both found this live)",
      provenance(0, "TOTAL: 40 passed, 6 failed")[0] == INCONSISTENT)
    t("provenance: a clean pass carries no provenance tag",
      provenance(0, "TOTAL: 46 passed, 0 failed")[0] == "")

    print()
    print("TOTAL: %d passed, %d failed" % (ok, bad))
    return 1 if bad else 0


def main():
    print("=" * 76)
    print("MUTATION TEST -- witness_soundness.py")
    print("  with the 2026-10-09 three-valued arrival control and provenance")
    print("  on the positive column")
    print("=" * 76)
    print("  DETECT  the suite must FAIL, and the harness records WHAT failed:")
    print("          a check (%s) or the interpreter (%s)." % (BY_CHECK, BY_CRASH))
    print("  SURVIVE the mutant must ARRIVE at the mechanism and not be caught.")
    print("  INERT   the mutant changes nothing the mechanism reports, so it")
    print("          neither survived nor was killed.  Three rows are specified")
    print("          INERT; an INERT row anywhere else is bad news.")
    print()

    base_rc, base_total, base_out, base_err = run_mutant("A", [])
    base_blk = mechanism_block(base_out)
    base_raw = mechanism_block(base_out, strip_verdicts=False)
    if base_rc != 0 or base_blk is None:
        print("  CONTROL A FAILED (rc=%r, block=%s) -- ABORTING."
              % (base_rc, "absent" if base_blk is None else "present"))
        print("  2026-10-02 check R0: a baseline that is not a baseline makes")
        print("  every row below meaningless, so no row is printed.")
        return 1

    ok = bad = 0
    counts = {}
    disagree = []
    rows = []
    for mid, exp, desc, edits in MUTANTS:
        rc, total, out, err = run_mutant(mid, edits)
        if rc is None:
            print("  [FAIL] %-4s HARNESS ERROR | %s" % (mid, err))
            bad += 1
            continue
        blk = mechanism_block(out)
        token, a_detail = ac.arrival(base_blk, blk,
                                     what="SECTION 1-8 computed report")
        raw_token = ac.arrival(base_raw,
                               mechanism_block(out, strip_verdicts=False))[0]
        prov, p_detail = provenance(rc, total)
        killers = []
        if prov == BY_CHECK:
            killers.append("a failing check (%s)" % total)
        elif prov == BY_CRASH:
            killers.append("an unhandled exception")
        outcome, o_reason = ac.classify(killers, token)
        if prov == INCONSISTENT:
            outcome, o_reason = "FAULT", p_detail

        want = {DETECT: "KILLED", SURVIVE: "SURVIVED", INERT: "INERT"}[exp]
        good = (outcome == want)
        if exp == DETECT and good:
            good = (prov == BY_CHECK)
        ok += good
        bad += not good
        counts[outcome if prov != BY_CRASH else BY_CRASH] = \
            counts.get(outcome if prov != BY_CRASH else BY_CRASH, 0) + 1
        if raw_token != token:
            disagree.append((mid, token, raw_token, outcome))
        rows.append((mid, exp, outcome, prov))

        print("  [%s] %-4s expect %-8s -> %-9s %-18s | arrival %s"
              % ("PASS" if good else "FAIL", mid, exp, outcome,
                 prov or "-", token))
        if total:
            print("         %s" % total)
        elif err:
            print("         no TOTAL line; stderr: %s" % err)
        print("         arrival : %s" % a_detail)
        if p_detail:
            print("         verdict : %s" % p_detail)
        print("         outcome : %s" % o_reason)
        for line in [desc[i:i + 68] for i in range(0, len(desc), 68)]:
            print("         " + line)
        print()

    print("=" * 76)
    print("TOTAL: %d of %d mutants behaved as required" % (ok, ok + bad))
    print()
    print("  outcome census: %s"
          % ", ".join("%s %d" % (k, v) for k, v in sorted(counts.items())))
    by_check = sum(1 for _, _, o, pr in rows if o == "KILLED" and pr == BY_CHECK)
    by_crash = sum(1 for _, _, o, pr in rows if pr == BY_CRASH)
    print("  detections BY A FAILING CHECK   : %d" % by_check)
    print("  detections BY AN UNHANDLED EXCEPTION: %d" % by_crash)
    if by_crash:
        print("    -- conditional exposure.  One defensive `except` around the")
        print("       suite would turn these into silent passes with no row of")
        print("       this harness changing.  2026-10-09, same measurement in")
        print("       mutation_test_reachable_cross.py: 3 of 6.")
    else:
        print("    -- every detection here is a check's, so this harness's")
        print("       detection power does not rest on the interpreter.  That")
        print("       is a MEASUREMENT, not an assumption: 2026-10-09 found")
        print("       3 of 6 the other way in a sibling harness.")
    print()
    lit, der = detail_census()
    print("  WHY TWO ROWS ARE INERT RATHER THAN SURVIVED -- a census of the")
    print("  audited suite's own check() detail strings:")
    print("    detail DERIVED from the checked quantity : %d" % len(der))
    print("    detail a TYPED LITERAL                   : %d  (%.0f %%)"
          % (len(lit), 100.0 * len(lit) / max(1, len(lit) + len(der))))
    c1_lit = any(l.startswith("C1 ") for l in lit)
    c3_lit = any(l.startswith("C3 ") for l in lit)
    print("    C1 detail is a typed literal : %s" % c1_lit)
    print("    C3 detail is a typed literal : %s" % c3_lit)
    c_lit = [k for k in range(1, 7)
             if any(l.startswith("C%d " % k) for l in lit)]
    print("    of the six C-controls, %d print a typed literal: %s"
          % (len(c_lit), ", ".join("C%d" % k for k in c_lit)))
    if c1_lit and c3_lit:
        print("    -- so M9 (perturbs what C1 checks) and M8b (perturbs what C3")
        print("       checks) change a VERDICT and change nothing in the report.")
        print("       They are INERT because the quantities they perturb are")
        print("       never printed, which means the weakened/broken assertion")
        print("       was the SOLE OBSERVER of each.  This is a real property of")
        print("       witness_soundness.py, reported and not fixed: that file")
        print("       owns a committed transcript.")
        print("    EXPECTATION GUARD: if either detail is ever DERIVED, M8b and")
        print("    M9 become observable and their rows above must change from")
        print("    INERT.  That is why this census is a check and not a note.")
    else:
        print("    -- one of C1/C3 now DERIVES its detail, so the INERT")
        print("       expectations above are STALE and must be revisited.")
        bad += 1
        ok -= 0
    print()
    print("  VERDICT-STRIPPED vs RAW arrival, measured rather than asserted:")
    if disagree:
        for mid, t_, r_, o_ in disagree:
            print("    %-4s stripped %-14s raw %-14s outcome %s"
                  % (mid, t_, r_, o_))
        print("    %d row(s) disagree, and NO outcome changes, because a killer"
              % len(disagree))
        print("    outranks arrival in every one of them.  The strip is kept")
        print("    anyway: it makes the arrival control independent of the")
        print("    killer BY CONSTRUCTION rather than by coincidence, and this")
        print("    repository has twice (09-19, 09-20) found the verdict-")
        print("    reporting subsystem decoupled from the checking one -- which")
        print("    is exactly the case where reading a verdict token would be")
        print("    reading a value already known here to be unreliable.")
    else:
        print("    no row disagrees -- which, given M9 exists to produce a")
        print("    disagreement, means the extractor is not doing its job.")
    print()
    print("  control A present and its block present: the baseline is a")
    print("                     baseline (10-02 check R0), or nothing printed")
    print("  control B INERT  : a semantics-preserving rename reaches no")
    print("                     mechanism, so it is INERT and not SURVIVED")
    print("  A is the DETERMINISM control: the suite is run twice and the two")
    print("                     reports compared, so ARRIVED here would mean")
    print("                     every INERT in the table is unreliable")
    print("  M8a/M8b/M8c      : the 10-02 compound form, and 10-10 moves M8b")
    print("                     from SURVIVE to INERT -- a sharpening, not a")
    print("                     loosening.  M8a changes only a threshold and")
    print("                     reports nothing; M8b perturbs a quantity C3")
    print("                     checks but never PRINTS, so it is not merely")
    print("                     uncaught but UNOBSERVABLE, and the weakened")
    print("                     threshold was its sole observer; M8c is the")
    print("                     same perturbation with the threshold intact")
    print("                     and is KILLED while still being INERT -- an")
    print("                     assertion can observe what the report does not")
    print("  M9               : the row that separates the two arrival rules,")
    print("                     and it records that C1's detail string is a")
    print("                     typed literal rather than a format of the")
    print("                     lengths it checks -- 10-01's naming fault in")
    print("                     detail-string form, reported not fixed")
    return 1 if bad else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    sys.exit(main())
