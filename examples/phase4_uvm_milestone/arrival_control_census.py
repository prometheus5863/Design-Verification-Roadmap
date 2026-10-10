#!/usr/bin/env python3
"""arrival_control_census.py -- 2026-10-09.

A STANDING instrument over every mutation harness in this repository,
reporting for each one whether it has an arrival control and of which kind.

WHY A CENSUS AND NOT A PROSE ITEM.  2026-10-08's backlog entry reads: "the
arrival control, wired into the other harnesses -- [five named files] all score
SURVIVED without first showing the mutant changed anything.  Any of those five
could be carrying the same thing now."  That is accurate and it is a sentence,
so it goes stale the moment a harness is added or one is wired, and nothing
reports the staleness.  The graphene repository hit this on 2026-10-08 with its
potential census and the fix transferred is the same: make the backlog item a
MEASUREMENT with a staleness guard, so a harness that exists and is absent from
the registry below is reported as a FAULT rather than as nothing.

WHAT IT CAN FAIL ON, because 2026-10-01 settled that a control which cannot
fail is not a control:

  F1  a mutation harness exists on disk and is absent from the registry
  F2  a registry row names a file that does not exist
  F3  the registry's adjudication DISAGREES with what the source shows --
      a row claiming THREE_VALUED whose file does not import arrival_control,
      or a row claiming NONE whose file does
  F4  a harness classified THREE_VALUED still contains a two-valued
      `!= baseline`-style arrival comparison IN ITS CODE
  F5  a file could not be tokenised, so it was classified on raw text

F3 is the one that matters: it is what stops this census from becoming a list
of intentions.  The registry cannot claim a harness is wired unless the source
agrees, and it cannot claim one is unwired if the source shows otherwise.

CLASSIFICATIONS

  THREE_VALUED   imports arrival_control and uses its three-valued arrival()
  TWO_VALUED     has an arrival comparison of 10-08's `blk != baseline` form,
                 which scores a MISSING block as ARRIVED
  NONE           scores SURVIVED with no arrival evidence at all

Run: python3 arrival_control_census.py
     python3 arrival_control_census.py --selftest   (exercises F1 and F3)
"""
import io
import ast
import os
import re
import sys
import tokenize

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))

THREE_VALUED = "THREE_VALUED"
TWO_VALUED = "TWO_VALUED"
NONE = "NONE"

# ---------------------------------------------------------------------------
# The registry.  One row per mutation harness, with an explicit adjudication.
# ---------------------------------------------------------------------------
REGISTRY = [
    ("examples/phase4_uvm_milestone/mutation_test_reachable_cross.py",
     THREE_VALUED,
     "wired 2026-10-09.  Target is a python suite, so it can be re-run in a "
     "session; that is why it went first.  Its three required-to-survive rows "
     "come back INERT, which is the harness's own 10-02 argument measured, and "
     "it found that 3 of its 6 detections were the suite CRASHING."),

    ("examples/phase4_uvm_milestone/mutation_test_signatures.py",
     TWO_VALUED,
     "10-08's original arrival control, `arrived = (blk != baselines[tc])`.  "
     "BASELINE side guarded (no block -> ABORT, 10-02's R0); MUTANT side NOT: "
     "a mutant run emitting no signature block gives blk = '', which differs "
     "from the baseline, so the row is scored SURVIVED on a block that does "
     "not exist.  NOT rewired yet: one uvm-python sim per row, which no single "
     "session has re-run, and an unverified edit to a committed instrument is "
     "worse than a measured gap."),

    ("examples/phase4_uvm_milestone/mutation_test_witnesses.py",
     NONE,
     "scores KILLED/SURVIVED from `caught` alone.  Needs a uvm-python sim per "
     "row."),

    ("examples/phase4_uvm_milestone/mutation_test_coverage_axis.py",
     NONE,
     "scores KILLED/SURVIVED from `caught` alone.  Needs a uvm-python sim per "
     "row."),

    ("examples/phase4_uvm_milestone/mutation_test_evidence_soundness.py",
     NONE,
     "runs the suite via run_suite(); no arrival evidence.  Needs a "
     "uvm-python sim per row."),

    ("examples/phase4_uvm_milestone/mutation_test_witness_soundness.py",
     THREE_VALUED,
     "wired 2026-10-10, the second python-target harness and the cheapest row "
     "this census named.  It also closed 10-09's provenance item for its own "
     "positive column: 9 of 9 detections are a failing check and none is the "
     "interpreter, measured rather than assumed.  Two findings came out of "
     "wiring it.  (1) An arrival block cut out of a report that prints "
     "verdicts INLINE contains those verdicts, so the arrival control stops "
     "being independent of the killer; the block extractor normalises "
     "[PASS]/[FAIL] to [VERDICT] and the harness measures the disagreement "
     "(2 rows, no outcome change).  (2) 18 of 31 of the audited suite's own "
     "check() detail strings are TYPED LITERALS, five of the six C-controls "
     "among them, so a mutant perturbing those quantities changes a verdict "
     "and changes nothing in the report -- which is why M8b moved from "
     "SURVIVE to INERT: it is not merely uncaught, it is unobservable."),
]


def code_only(text):
    """`text` with every comment and string literal removed.

    DEFECT FOUND AND FIXED WHILE WRITING THIS CENSUS, 2026-10-09, and it is
    the same class as 2026-10-06's.  The first draft classified on the raw
    file, and it raised F4 against mutation_test_reachable_cross.py -- the one
    harness that HAD just been wired three-valued -- because that harness's
    docstring EXPLAINS the retired rule and therefore contains the literal
    text `mutant != baseline`.  The detector could not tell a rule from a
    description of a rule.

    10-06 anchored the S-tag regex on its colon because `S-[a-f] FAILED` also
    matched inside the summary sentence that merely NAMED the checks.  Same
    fault: a pattern that matches prose about the thing as well as the thing.
    09-28 established that prose is a detector; this is the other direction --
    prose being DETECTED AS code -- and in a repository whose house style is
    long explanatory docstrings it is not a corner case, it is the default.

    Tokenising and dropping COMMENT/STRING is the structural fix rather than a
    cleverer regex, which would be the same bet again.  A file that does not
    tokenise falls back to the raw text and is reported, because silently
    classifying an unparseable file is how a census starts lying.
    """
    try:
        out = []
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type in (tokenize.COMMENT, tokenize.STRING):
                continue
            out.append(tok.string)
        return " ".join(out), True
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return text, False


def arrival_control_binding(text):
    """The NAME `arrival_control` is bound to in `text`, or None.

    DEFECT FOUND 2026-10-10, and it is the MIRROR of the one found while
    writing this file on 2026-10-09.  The first version of classify_source()
    looked for the literal alias spellings it had seen:

        uses_ac = re.search(r"\bAC\s*\.\s*arrival\s*\(|"
                            r"\barrival_control\s*\.\s*arrival\s*\(", code)

    `mutation_test_reachable_cross.py` writes `import arrival_control as AC`,
    so that worked.  `mutation_test_witness_soundness.py`, wired 2026-10-10,
    writes `as ac`, and the census reported **NONE for a harness that is
    correctly wired** -- F3 against a true registry row.

    10-09's defect in this same function was a FALSE POSITIVE from matching
    prose; this is a FALSE NEGATIVE from matching one alias.  Same root cause
    both times: a textual pattern standing in for a structural fact.  The
    cheap repair available today was to rename the new harness's alias to
    `AC`, which would have made the census pass while leaving it unable to
    read the next harness anyone writes -- the testing equivalent of widening
    a tolerance until it goes green.  Repaired structurally instead: the
    binding is read out of the import statement, so every alias works and an
    alias that is never imported never counts.
    """
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name == "arrival_control":
                    return a.asname or a.name
        elif isinstance(node, ast.ImportFrom):
            if node.module == "arrival_control":
                for a in node.names:
                    if a.name == "arrival":
                        return "<from-import>"
    return None


def classify_source(text):
    """What the source actually shows, independent of the registry.

    Classification runs on CODE ONLY -- see code_only() for why.
    """
    code, tokenised = code_only(text)
    binding = arrival_control_binding(text)
    imports_ac = binding is not None
    if binding == "<from-import>":
        uses_ac = bool(re.search(r"\barrival\s*\(", code))
    elif binding:
        uses_ac = bool(re.search(r"\b%s\s*\.\s*arrival\s*\("
                                 % re.escape(binding), code))
    else:
        uses_ac = False
    two_valued = bool(re.search(r"!=\s*baselines?\b|"
                                r"\bbaselines?\s*\[[^\]]*\]\s*!=", code))
    if imports_ac and uses_ac:
        return THREE_VALUED, two_valued, tokenised
    if two_valued:
        return TWO_VALUED, two_valued, tokenised
    return NONE, two_valued, tokenised


def discover(repo=REPO):
    """Every mutation harness on disk, as a repo-relative path."""
    found = []
    for root, dirs, files in os.walk(repo):
        dirs[:] = [d for d in dirs if d != ".git"]
        for fn in files:
            if fn.startswith("mutation_test") and fn.endswith(".py"):
                found.append(os.path.relpath(os.path.join(root, fn), repo))
    return sorted(found)


def audit(repo=REPO, registry=REGISTRY, extra_on_disk=()):
    faults = []
    rows = []

    on_disk = set(discover(repo)) | set(extra_on_disk)
    registered = {r[0] for r in registry}

    for path in sorted(on_disk - registered):
        faults.append(("F1", path,
                       "a mutation harness exists on disk and is absent from "
                       "the registry: the census cannot report what it has not "
                       "been told about, so this is a fault and not a blank"))

    for path, claim, note in registry:
        full = os.path.join(repo, path)
        if not os.path.exists(full):
            faults.append(("F2", path,
                           "the registry names a file that does not exist"))
            rows.append((path, claim, "MISSING", note))
            continue
        text = open(full, encoding="utf-8", errors="replace").read()
        shown, has_two_valued, tokenised = classify_source(text)
        if not tokenised:
            faults.append(("F5", path,
                           "the file could not be tokenised, so it was "
                           "classified on raw text including its comments and "
                           "docstrings -- see code_only()"))
        rows.append((path, claim, shown, note))
        if shown != claim:
            faults.append(("F3", path,
                           "the registry adjudicates %s and the source shows "
                           "%s" % (claim, shown)))
        if claim == THREE_VALUED and has_two_valued:
            faults.append(("F4", path,
                           "classified THREE_VALUED but still contains a "
                           "two-valued `!= baseline` arrival comparison"))
    return rows, faults


def main(selftest=False):
    print("=" * 78)
    print("ARRIVAL-CONTROL CENSUS over every mutation harness in this repository")
    print("2026-10-09" + ("   MODE: SELFTEST" if selftest else ""))
    print("=" * 78)
    print()

    if selftest:
        # F1: pretend a harness exists that the registry does not know about.
        # F3: a registry row that claims THREE_VALUED for a file that is not.
        bogus = [("examples/phase4_uvm_milestone/mutation_test_witnesses.py",
                  THREE_VALUED, "SELFTEST: deliberately wrong adjudication"),
                 ("examples/selftest/does_not_exist_mutation_test.py",
                  NONE, "SELFTEST: a registry row with no file")]
        rows, faults = audit(
            registry=bogus,
            extra_on_disk=("examples/selftest/mutation_test_not_registered.py",))
        codes = sorted({f[0] for f in faults})
        print("  injected: one unregistered harness (F1), one registry row")
        print("            naming a missing file (F2), and one row claiming")
        print("            THREE_VALUED for a file that does not import")
        print("            arrival_control (F3)")
        print()
        print("  AND THE PROSE CHECK, which is why code_only() exists: the")
        print("  live run must NOT raise F4 against")
        print("  mutation_test_reachable_cross.py, whose docstring quotes the")
        print("  very string F4 searches for.")
        live_rows, live_faults = audit()
        prose_f4 = [f for f in live_faults
                    if f[0] == "F4" and "reachable_cross" in f[1]]
        print("  F4 raised against reachable_cross on the live registry: %s"
              % ("YES -- the regex is reading prose again" if prose_f4
                 else "no"))
        print()
        print("  AND THE ALIAS CHECK, added 2026-10-10 after this function")
        print("  reported NONE for a correctly wired harness because it spells")
        print("  its import `as ac` and the pattern knew only `as AC`:")
        alias_cases = [
            ("import arrival_control as ac\nx = ac.arrival(a, b)\n",
             THREE_VALUED, "lowercase alias"),
            ("import arrival_control as AC\nx = AC.arrival(a, b)\n",
             THREE_VALUED, "the alias 10-09 happened to use"),
            ("import arrival_control\nx = arrival_control.arrival(a, b)\n",
             THREE_VALUED, "no alias at all"),
            ("import arrival_control as zz\nx = zz.arrival(a, b)\n",
             THREE_VALUED, "an alias nobody has used yet"),
            ("from arrival_control import arrival\nx = arrival(a, b)\n",
             THREE_VALUED, "a from-import"),
            ("x = ac.arrival(a, b)\n", NONE,
             "`ac.arrival(` with NO import -- must NOT count"),
            ("import arrival_control as ac\n# ac.arrival(a, b)\n", NONE,
             "the call in a COMMENT -- 10-09's prose path, still closed"),
            ("import arrival_control as ac\nd = 'ac.arrival(a, b)'\n", NONE,
             "the call in a STRING -- same"),
        ]
        alias_bad = 0
        for src_, want, why in alias_cases:
            got = classify_source(src_)[0]
            good = got == want
            alias_bad += not good
            print("    [%s] %-44s -> %s" % ("PASS" if good else "FAIL",
                                            why, got))
        if alias_bad:
            faults.append(("F6", "classify_source",
                           "%d alias case(s) misclassified" % alias_bad))
        print()
        for code, path, detail in faults:
            print("  %-3s %s" % (code, path))
            print("      %s" % detail)
        print()
        want = ["F1", "F2", "F3"]
        ok = (codes == want) and not prose_f4
        print("  fault codes raised: %s   expected: %s" % (codes, want))
        print("  [%s] SELFTEST: F1, F2 and F3 are all reachable, and F4 does"
              % ("PASS" if ok else "FAIL"))
        print("        not fire on a docstring that merely describes the rule")
        print("=" * 78)
        print("SELFTEST: %s" % ("PASS" if ok else "FAIL"))
        print("=" * 78)
        return 0 if ok else 1

    rows, faults = audit()

    print("  %-56s %-13s %s" % ("harness", "registry", "source shows"))
    print("  " + "-" * 74)
    for path, claim, shown, note in rows:
        flag = "" if claim == shown else "   <-- DISAGREES"
        print("  %-56s %-13s %s%s"
              % (os.path.basename(path), claim, shown, flag))
    print()

    counts = {}
    for _, claim, _, _ in rows:
        counts[claim] = counts.get(claim, 0) + 1
    print("  THREE_VALUED: %d   TWO_VALUED: %d   NONE: %d   total: %d"
          % (counts.get(THREE_VALUED, 0), counts.get(TWO_VALUED, 0),
             counts.get(NONE, 0), len(rows)))
    print()

    print("  PER-HARNESS ADJUDICATION")
    print("  " + "-" * 74)
    for path, claim, shown, note in rows:
        print("  %s  [%s]" % (os.path.basename(path), claim))
        for line in _wrap(note, 68):
            print("      %s" % line)
    print()

    if faults:
        print("  FAULTS")
        print("  " + "-" * 74)
        for code, path, detail in faults:
            print("  %-3s %s" % (code, path))
            for line in _wrap(detail, 68):
                print("      %s" % line)
        print()
    else:
        print("  No faults: every harness on disk is registered, every "
              "registry row")
        print("  exists, and every adjudication agrees with its source.")
        print()

    open_rows = counts.get(TWO_VALUED, 0) + counts.get(NONE, 0)
    print("  OPEN: %d of %d harnesses still score SURVIVED without a "
          "three-valued" % (open_rows, len(rows)))
    print("  arrival control.  That is a measured number with a staleness")
    print("  guard, which is what this file is for -- the 10-08 backlog")
    print("  sentence it replaces could not notice a harness being added.")
    print()
    print("  Both python-target harnesses are now wired (10-09, 10-10).  Every")
    print("  remaining open row needs a uvm-python SIMULATION PER MUTANT, which")
    print("  is a different size of job and is not pretended otherwise:")
    print("    mutation_test_signatures.py       TWO_VALUED, mutant side")
    print("                                      unguarded -- the worst of the")
    print("                                      remaining rows, because it has")
    print("                                      a control that misreports")
    print("    the other three                   NONE at all")
    print("  So the cheap half of this item is DONE and what is left is one")
    print("  session's worth of simulator work, not four sentences of backlog.")
    print()
    print("=" * 78)
    print("RESULT: %s   (%d fault(s), %d harness(es) open)"
          % ("PASS" if not faults else "FAIL", len(faults), open_rows))
    print("=" * 78)
    return 0 if not faults else 1


def _wrap(s, width):
    words, out, cur = s.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            out.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        out.append(cur)
    return out


if __name__ == "__main__":
    sys.exit(main(selftest="--selftest" in sys.argv))
