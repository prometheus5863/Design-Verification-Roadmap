#!/usr/bin/env python3
"""
tools/verdict_bearing_census.py -- 2026-11-08

WHICH CASES IN A MUTATION RUNNER CARRY THE VERDICT, AND WHICH SIT OUTSIDE IT?

2026-11-07 measured a real defect in
examples/phase6_crv_uart/run_rx_avail_mutation_tests.sh: the adjudication loop
folded ALL FOUR rows into `sync_only_holds`, R4 included -- and R4 is the
CONTROL, the row that mutates the wire rather than the STATUS decode and so can
neither confirm nor refute a claim about what the bench reads.  A control that
can move the verdict it exists to sit outside makes the verdict answer a weaker
question than the one it was written to ask.  The repair was to make
`verdict_bearing` an explicit argument, so that which rows carry the verdict is
visible AT THE CALL SITE instead of implicit in the loop.

That entry then generalised the finding into a standing item, and the item
carries a CLAIM:

    "Every other runner here has controls mixed into the same loop as its
     mutants; none of them says which carry the verdict."

THIS MODULE EXISTS TO TEST THAT CLAIM, NOT TO ILLUSTRATE IT.  A census written
to confirm the sentence that commissioned it is the fault this repository has
recorded under several names, and the sentence is the sort that is easy to
write from one instance.  So the classes below are chosen to be able to come
back and say the claim is overstated, and the first thing Section 3 reports is
whether it did.

WHAT IS MEASURED, PER RUNNER
----------------------------
An ADJUDICATOR is a shell function that both (a) is called once per case with
the case's id, and (b) ... that is the whole question, so it is split:

  EXPLICIT         a verdict-writing adjudicator that takes a per-case
                   verdict-bearing flag.  The 11-07 repair.
  MIXED_IMPLICIT   a verdict-writing adjudicator called with at least one case
                   the file's own prose declares to be the control, and no
                   per-case flag.  THE DEFECT CLASS.
  REPORT_ONLY      an adjudicator that writes no verdict variable at all.  It
                   cannot be contaminated by a control because it decides
                   nothing -- a distinction the standing item's wording does
                   not make, and the reason this class exists.
  NO_ADJUDICATOR   no per-case adjudication function found.

A VERDICT VARIABLE is a name appearing in a condition within VERDICT_WINDOW
lines above a line that prints `RESULT: FAIL`.  That is the file's own
definition of what decides it, read off the decision rather than guessed from
naming.

AND EVERY `cmp -s`, WHICH ABSORBS THE CARRIED ITEM
--------------------------------------------------
The standing list has carried "CLASSIFY EVERY `cmp -s` AS VERDICT-BEARING OR
CONTROL-BEARING" since 2026-10-25, and 11-07 noted the two items are the same
question asked of different objects.  So they are answered by one instrument:
each `cmp -s` occurrence is classified by what its branch DOES --

  VERDICT           the branch assigns to, or increments, a verdict variable.
  CONTROL           the branch only reports, inside a block whose own text
                    names it a control.
  REQUIRES_READING  anything else, with the line quoted so the residue is a
                    worklist and not a silence.

THIS IS A SOURCE-LEVEL SCREEN AND IT SAYS SO.  It does not parse shell; it
reads function extents, assignments and call sites by line shape.  Its job is
to RANK FILES FOR READING and to make the population countable, which no
amount of prose about "every other runner" can do.  Where the shape is
ambiguous it returns REQUIRES_READING rather than a verdict, because a census
that guesses in order to report a clean number is worse than one that reports a
worklist -- 2026-10-25's rule, and the reason the three-valued outcome axis
exists.

ANCHORED ON TWO ANSWERS THAT ARE KNOWN FROM THE GIT HISTORY, not from
plausibility: run_rx_avail_mutation_tests.sh was repaired on 2026-11-07 and
MUST classify EXPLICIT; run_tx_empty_mutation_tests.sh is its unrepaired
sibling, written from the same template two days earlier, and whatever it
classifies as is a fact about the repository that the anchors pin.  Section 2
plants both directions on synthetic files whose answers are known by
construction, and Section 4 mutation-tests the classifier against the anchors.

Exit code is failure-conditional.
"""
import os
import re
import subprocess
import sys

# THIS MODULE'S OWN NAME, AS A LITERAL AND NOT AS basename(__file__).
#
# Needed by Section 4's self-exclusion (B2/B2b/B3), and a literal because
# under the mutation harness this module runs as `_vbc_mutant.py`: a
# self-exclusion written `basename(__file__)` matches nothing there and so
# switches itself off in exactly the run it exists for.  Found by running it,
# 2026-11-14 -- B2 stayed green while B2b went red.
SELF_CENSUS = "verdict_bearing_census.py"

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

VERDICT_WINDOW = 10

# How a file declares, in its own words, that a case is a control.  Taken from
# the two runners that do it rather than invented: both write "the control:"
# or "the control for" in the adjudication call site's expectation text.
CONTROL_PROSE = re.compile(r"\bthe control\b", re.I)

# A per-case verdict-bearing flag, under any of the spellings the repository
# might reasonably use.  Only the first exists today; the others are here so
# that a future runner adopting the repair under a different name is not
# counted as a defect.
FLAG_NAMES = ("verdict_bearing", "carries_verdict", "is_control",
              "verdict_bearing_case")
FLAG_RE = re.compile(r"\b(%s)\b" % "|".join(FLAG_NAMES))

# A TRAILING COMMENT ON THE DEF LINE BROKE THIS, AND THE ANCHOR IS WHAT
# CAUGHT IT (2026-11-08).  The first form required `{` at end of line, so
# `adj () {    # $1 id  $2 expectation text` -- which is how
# run_tx_empty_mutation_tests.sh and run_mutation_tests.sh write it -- was not
# seen as a function at all, and both files classified NO_ADJUDICATOR.  A
# census that silently fails to find the thing it counts reports a smaller
# population and reads as good news, which is the same hazard as a partition
# that drops a case.
FUNC_RE = re.compile(
    r"^([A-Za-z_][A-Za-z0-9_]*)\s*\(\)\s*\{\s*(?:#.*)?$")

# THE FIRST DEFINITION OF A VERDICT VARIABLE WAS TOO NARROW, AND THE ANCHOR
# CAUGHT THAT TOO -- it is the better of the two findings.  It read only what
# the script's `RESULT: FAIL` decision tests, i.e. what moves the EXIT CODE.
# But the variable the 11-07 defect contaminated was `sync_only_holds`, which
# the exit code never reads: it drives a printed CLAIM --
#
#     if [ "$sync_only_holds" -eq 1 ]; then
#         echo "  SYNC_ONLY is CONFIRMED for STATUS.rx_avail, ..."
#
# and `fail_count`, which is what the exit code reads, only counts control
# failures.  So under the narrow definition run_rx_avail_mutation_tests.sh --
# the one file known to carry the repair -- classified REPORT_ONLY, and the
# census would have reported that the defect it was written to find does not
# exist anywhere.
#
# THE DISTINCTION IS THE POINT AND NOT AN IMPLEMENTATION DETAIL.  These
# runners produce two verdicts: whether the harness itself is sound (the exit
# code, gated on controls) and whether the CLAIM under test holds (a printed
# adjudication).  A control contaminating the second is worse than a control
# contaminating the first, because the second is the answer the run exists to
# produce and nothing downstream re-derives it.  A verdict variable is
# therefore any name a conditional tests whose body prints a word from the
# vocabulary below -- read off what the file CONCLUDES, which is a superset of
# what it EXITS with.
VERDICT_WORDS = ("RESULT:", "CONFIRMED", "DOES NOT HOLD", "REFUTED",
                 "HOLDS", "VERDICT", "SURVIVED")
RESULT_FAIL_RE = re.compile(r'RESULT:\s*FAIL')
VARNAME_RE = re.compile(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)")
ASSIGN_RE = re.compile(r"(?:^|[;&|}{\s])([A-Za-z_][A-Za-z0-9_]*)=")
ARITH_RE = re.compile(r"\(\(\s*([A-Za-z_][A-Za-z0-9_]*)")

_PASS, _FAIL = [], []


def check(label, ok, detail=""):
    (_PASS if ok else _FAIL).append(label)
    print("  [%s] %s" % ("PASS" if ok else "FAIL", label))
    if detail:
        for line in detail.rstrip("\n").split("\n"):
            print("        " + line)
    return ok


def tracked_shell_runners():
    out = subprocess.run(["git", "ls-files", "*.sh"], cwd=REPO,
                         capture_output=True, text=True).stdout
    paths = [p for p in out.split("\n") if p.strip()]
    keep = []
    for p in paths:
        try:
            src = open(os.path.join(REPO, p), encoding="utf-8",
                       errors="replace").read()
        except OSError:
            continue
        # A runner, not a setup script: it injects mutants or compares
        # transcripts.  Both idioms are the repository's own.
        if "sed" in src and ("mutant" in src.lower() or "cmp -s" in src
                             or "MUT_" in src):
            keep.append(p)
    return sorted(keep)


def func_extents(lines):
    """{name: (start, end)} over 0-based line indices, end exclusive.

    A function is `name () {` on its own line, closed by `}` at column 0.
    That is the shape every function in this repository's runners has; a
    function written otherwise is simply not found, which costs a
    NO_ADJUDICATOR and not a wrong answer.
    """
    out = {}
    i = 0
    while i < len(lines):
        m = FUNC_RE.match(lines[i])
        if m:
            j = i + 1
            while j < len(lines) and lines[j].rstrip() != "}":
                j += 1
            out[m.group(1)] = (i, min(j + 1, len(lines)))
            i = j + 1
        else:
            i += 1
    return out


def verdict_variables(lines):
    """Names the file's own conclusions are gated on -- see VERDICT_WORDS.

    Read off the conclusion and not from naming: a variable called
    `fail_count` that nothing tests is not a verdict, and a variable called
    `h` that an adjudication tests is.
    """
    names = set()
    for n, line in enumerate(lines):
        if not line.lstrip().startswith(("if ", "elif ")):
            continue
        # THE `if` LINE ITSELF IS PART OF ITS OWN BODY, and leaving it out
        # broke all four plants while leaving the live anchors right -- a
        # one-line window is how a plant is written and a multi-line one is
        # how the live runners are.  Both shapes must count or the plants
        # stop being a control on the live answer.
        body = lines[n:min(len(lines), n + 1 + VERDICT_WINDOW)]
        if not any(w in b for b in body for w in VERDICT_WORDS):
            continue
        for vm in VARNAME_RE.finditer(line):
            names.add(vm.group(1))
    return names - {"0", "1"}


def writes_any(body_lines, names):
    """The verdict variables a function body assigns to or increments."""
    hit = set()
    for l in body_lines:
        for m in ASSIGN_RE.finditer(l):
            if m.group(1) in names:
                hit.add(m.group(1))
        for m in ARITH_RE.finditer(l):
            if m.group(1) in names:
                hit.add(m.group(1))
    return hit


def call_sites(lines, name, extent):
    """Top-level invocations of `name`, as (line index, joined text).

    Continuation lines matter: every adjudication call in this repository
    wraps, and the control prose is usually on the second line.
    """
    s, e = extent
    out = []
    i = 0
    while i < len(lines):
        if s <= i < e:
            i += 1
            continue
        l = lines[i]
        if re.match(r"^%s\s+\S" % re.escape(name), l):
            joined, j = l.rstrip("\\").strip(), i
            while j < len(lines) - 1 and lines[j].rstrip().endswith("\\"):
                j += 1
                joined += " " + lines[j].rstrip("\\").strip()
            out.append((i, joined))
            i = j + 1
        else:
            i += 1
    return out


def classify_runner(path):
    src = open(os.path.join(REPO, path), encoding="utf-8",
               errors="replace").read()
    lines = src.split("\n")
    vnames = verdict_variables(lines)
    funcs = func_extents(lines)
    best = None
    for name, extent in sorted(funcs.items()):
        body = lines[extent[0]:extent[1]]
        sites = call_sites(lines, name, extent)
        if len(sites) < 2:
            continue                      # not a per-case adjudicator
        written = writes_any(body, vnames)
        flagged = bool(FLAG_RE.search("\n".join(body[:4])))
        controls = [n for n, t in sites if CONTROL_PROSE.search(t)]
        cand = {
            "func": name, "n_cases": len(sites), "writes": sorted(written),
            "flagged": flagged, "control_sites": controls,
            "cases": sites,
        }
        if written and flagged:
            cand["klass"] = "EXPLICIT"
        elif written and controls:
            cand["klass"] = "MIXED_IMPLICIT"
        elif written:
            cand["klass"] = "VERDICT_NO_CONTROL"
        else:
            cand["klass"] = "REPORT_ONLY"
        rank = {"MIXED_IMPLICIT": 0, "EXPLICIT": 1, "VERDICT_NO_CONTROL": 2,
                "REPORT_ONLY": 3}
        if best is None or rank[cand["klass"]] < rank[best["klass"]]:
            best = cand
    if best is None:
        return {"klass": "NO_ADJUDICATOR", "func": None, "n_cases": 0,
                "writes": sorted(vnames), "flagged": False,
                "control_sites": [], "cases": []}
    return best


def _branch_extent(lines, n, cap=24):
    """The lines of the branch the comparison on line `n` feeds.

    THE WINDOW WAS WRONG TWICE AND BOTH WRONGS WERE MEASURED (2026-11-08).
    The first form looked seven lines ahead unconditionally, which reached
    PAST the next `cmp -s` in the planted file and classified a control
    comparison as VERDICT on the strength of the NEXT comparison's
    assignment; P5 caught that.  The second form capped at three lines and
    stopped at the next comparison, which fixed P5 and then reported ZERO
    verdict-bearing comparisons on the whole live tree -- because the real
    shape is

        if cmp -s "$RTL" "$WORK/mut.v"; then
            echo "  ..."
            echo "    INJECTION FAILED -- the sed matched nothing, ..."
            echo "    otherwise have scored as an escape against UNMODIFIED RTL."
            SURPRISES=$((SURPRISES+1))
            continue
        fi

    where the assignment is four lines down, inside the same `fi`.  A
    three-line window cannot see it.  So the window is now the BRANCH: from
    the comparison to the closing `fi` at the same indentation, which is the
    unit that actually determines what the comparison does.  Stopping at the
    next comparison is kept, because a second comparison begins a different
    branch.
    """
    base = len(lines[n]) - len(lines[n].lstrip())
    out = [lines[n]]
    for l in lines[n + 1:min(len(lines), n + 1 + cap)]:
        st = l.strip()
        if "cmp -s" in l:
            break
        ind = len(l) - len(l.lstrip())
        if st in ("fi", "fi;") and ind <= base:
            break
        if st and ind < base:
            break
        out.append(l)
    return out


def _is_mention(line, pos):
    """True iff the `cmp -s` at `pos` is prose rather than a command.

    Two cases, both literal and both cheap: the occurrence sits after a `#`
    that starts a comment, or it sits inside a quoted string (an odd number
    of quote characters precedes it).  Deliberately not a shell lexer -- it
    errs toward calling a real use a MENTION only when the line also has an
    unbalanced quote before it, which does not occur in this tree, and the
    residue class is a worklist either way.
    """
    head = line[:pos]
    if head.lstrip().startswith("#"):
        return True
    if "#" in head and not head.split("#")[0].strip():
        return True
    if "#" in head:
        before_hash = head.split("#")[0]
        if before_hash.count('"') % 2 == 0 and before_hash.count("'") % 2 == 0:
            return True
    return head.count('"') % 2 == 1 or head.count("'") % 2 == 1


def classify_cmp(path):
    """[(line no, class, text)] for every `cmp -s` in the file."""
    src = open(os.path.join(REPO, path), encoding="utf-8",
               errors="replace").read()
    lines = src.split("\n")
    vnames = verdict_variables(lines)
    out = []
    for n, line in enumerate(lines):
        if "cmp -s" not in line:
            continue
        # A MENTION IS NOT A USE, AND THE FIRST RUN COUNTED 45 OCCURRENCES OF
        # WHICH MOST WERE PROSE (2026-11-08).  This repository has the rule
        # already -- 2026-10-01 found exactly this loophole in
        # graphene_dead_name_sweep.py's sibling problem, and the same fault
        # turned up in the graphene repository's log audit on the same day --
        # and a census that counts the comments explaining why a `cmp -s`
        # guard was REPLACED as instances of a `cmp -s` guard is reporting a
        # population that does not exist.  Mentions are kept and counted as
        # their own class rather than dropped, because "how many places
        # discuss this idiom" is a real number; it is just not this number.
        if _is_mention(line, line.index("cmp -s")):
            out.append((n + 1, "MENTION", line.strip()))
            continue
        window = _branch_extent(lines, n)

        # ORDER AND SCOPE BOTH MATTER, AND P5 CAUGHT BOTH.  An earlier
        # version also looked BACKWARD a few lines for the control block's
        # own banner, which made every comparison following a `G2 neutrality
        # control` echo read as CONTROL -- including the verdict-bearing one
        # two lines later.  Evidence for CONTROL is now required in the
        # BRANCH THE COMPARISON FEEDS, not in its neighbourhood, and VERDICT
        # is asked first because an assignment to a verdict variable settles
        # the question whatever the surrounding prose says.
        if writes_any(window, vnames):
            k = "VERDICT"
        elif any(CONTROL_PROSE.search(l) or re.search(r"\bABORT\b", l)
                 or re.search(r"\bcontrols? (nothing|changed)\b", l, re.I)
                 for l in window):
            k = "CONTROL"
        else:
            k = "REQUIRES_READING"
        out.append((n + 1, k, line.strip()))
    return out


# ---------------------------------------------------------------------------
# THE MUTANT PREMISE CENSUS (2026-11-13)
#
# Created as the ranked-first item of the 2026-11-12 entry, which was created
# by `M4` going stale.  `M4`'s requirement was that the mutant turn check `B2`
# red, on the stated premise that "every real one assigns several lines into
# its branch".  That premise was true on 2026-11-08 and false four days later:
# six non-mention occurrences now have a one-line branch, so under the mutant
# the live tree still yields a non-empty VERDICT and CONTROL class and `B2`
# stays green.  A mutant whose requirement rests on a property of the TREE
# dies silently when the tree moves.
#
# TWO REPAIRS, AND THE SECOND IS THE GENERAL ONE.
#
#   (a) `M4` is re-anchored on a property of the CLASSIFIER instead: the
#       mutant must CHANGE THE SECTION-4 TALLY.  That is what a wrong window
#       does by definition, whatever the tree happens to contain, and it
#       cannot be satisfied by a tree that has drifted.
#   (b) Every mutant's premise is moved OUT OF ITS PROSE and into a declared
#       relation that is checked against the live tree.  This is the standing
#       item NO INSTRUMENT IN THIS REPOSITORY READS A CHECK'S PROSE, met from
#       the only sound side: not by teaching an instrument to read prose, but
#       by taking the facts out of the prose.
#
# THE PREMISES ARE RELATIONS, NOT MAGNITUDES, AND THAT IS THE LESSON FROM
# `M4`.  "Every real occurrence has a multi-line branch" is a magnitude-like
# claim about a population and it expired.  "Most non-mention occurrences
# have a multi-line branch" survives adding a file.  The live magnitudes are
# REPORTED alongside each relation rather than asserted, which is the
# repository's own carried item S7 SHOULD REPORT THE PREDICTED COUNT
# ALONGSIDE THE MEASURED ONE getting an instance here.


def tree_stats():
    """Every number any mutant's premise depends on, measured once."""
    out = subprocess.run(["git", "ls-files", "*.sh", "*.py"], cwd=REPO,
                         capture_output=True, text=True).stdout
    files = sorted(p for p in out.split("\n") if p.strip())
    tally, total = {}, 0
    multi, single = 0, 0
    for p in files:
        rows = classify_cmp(p)
        for _n, k, _t in rows:
            total += 1
            tally[k] = tally.get(k, 0) + 1
        if not rows:
            continue
        lines = open(os.path.join(REPO, p), encoding="utf-8",
                     errors="replace").read().split("\n")
        for i, line in enumerate(lines):
            if "cmp -s" not in line:
                continue
            if _is_mention(line, line.index("cmp -s")):
                continue
            if len(_branch_extent(lines, i)) > 1:
                multi += 1
            else:
                single += 1
    # THE WIDE REGEX IS THE MODULE'S OWN `FUNC_RE`, NOT A COPY OF IT, AND THE
    # NARROW ONE IS BUILT BY CONCATENATION.  Writing either literal out here
    # would put `M1`'s mutation anchor in the source a second time, and the
    # PLANTED guard would correctly report M1 as a FAULT IN THE TEST rather
    # than as a control -- this module's own "a module must not plant the
    # pattern it censuses" hazard, arriving in the measurement of a premise.
    # Caught by running it.  The concatenation is deliberate here and is the
    # opposite of the 2026-11-12 finding that a census matching a
    # concatenated string cannot see a concatenation: there the concatenation
    # hid a real site from an instrument, here it keeps a measurement out of
    # an instrument's own population.
    wide = FUNC_RE
    narrow = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)"
                        + r"\s*\(\)\s*\{\s*$")
    trailing = 0
    for p in tracked_shell_runners():
        lines = open(os.path.join(REPO, p), encoding="utf-8",
                     errors="replace").read().split("\n")
        for l in lines:
            st = l.strip()
            if wide.match(st) and not narrow.match(st):
                trailing += 1
                break
    return {"tally": tally, "total": total, "multi_branch": multi,
            "single_branch": single, "trailing_comment_runners": trailing,
            "runners": len(tracked_shell_runners())}


# id -> (the premise as a RELATION, a function of tree_stats() -> bool,
#        a function of tree_stats() -> the live magnitudes as a string)
#
# A premise of None is a mutant whose premise is not reducible to a relation
# over these numbers.  Those are COUNTED and NAMED by check C2 rather than
# left silent -- the same worklist discipline as REQUIRES_READING in B1.
PREMISES = {
    "M1": ("at least one tracked runner writes its adjudicator def-line with "
           "a trailing comment, so the narrow regex would misclassify a real "
           "runner",
           lambda s: s["trailing_comment_runners"] >= 1,
           lambda s: "%d of %d tracked runners do"
                     % (s["trailing_comment_runners"], s["runners"])),
    "M2": (None, None,
           lambda s: "its premise names a particular file and a particular "
                     "dated repair, which is not a relation over these "
                     "numbers"),
    "M3": ("prose occurrences are the LARGEST single class, so counting them "
           "as uses inflates the population of real guards rather than "
           "nudging it",
           lambda s: (s["tally"].get("MENTION", 0)
                      == max(s["tally"].values())),
           lambda s: "MENTION %d of %d total; %d non-mention, so counting "
                     "prose inflates the real population by %.0f per cent"
                     % (s["tally"].get("MENTION", 0), s["total"],
                        s["total"] - s["tally"].get("MENTION", 0),
                        100.0 * s["tally"].get("MENTION", 0)
                        / max(1, s["total"] - s["tally"].get("MENTION", 0)))),
    "M4": ("MOST non-mention occurrences have a multi-line branch -- stated "
           "as a majority and not as 'every', which is the form that expired",
           lambda s: s["multi_branch"] > s["single_branch"],
           lambda s: "%d multi-line against %d one-line; the one-line ones "
                     "are why the old 'every' premise failed"
                     % (s["multi_branch"], s["single_branch"])),
}


# ---------------------------------------------------------------------------
# Planted files, whose answers are known BY CONSTRUCTION
# ---------------------------------------------------------------------------
PLANT_EXPLICIT = '''#!/bin/sh
holds=1
adj () {
    local id="$1" verdict_bearing="$2" exp="$3"
    echo "$id $exp"
    [ "$verdict_bearing" = 1 ] && holds=0
}
adj A1 1 "a real row"
adj A2 0 "the control: it changes the DUT"
if [ "$holds" -ne 1 ]; then echo "RESULT: FAIL"; fi
'''

PLANT_MIXED = '''#!/bin/sh
holds=1
adj () {
    local id="$1" exp="$2"
    echo "$id $exp"
    holds=0
}
adj A1 "a real row"
adj A2 "the control: it changes the DUT"
if [ "$holds" -ne 1 ]; then echo "RESULT: FAIL"; fi
'''

PLANT_REPORT = '''#!/bin/sh
fail_count=0
adj () {
    local id="$1" exp="$2"
    echo "$id $exp"
}
adj A1 "a real row"
adj A2 "the control: it changes the DUT"
if [ "$fail_count" -ne 0 ]; then echo "RESULT: FAIL"; fi
'''

PLANT_NO_CONTROL = '''#!/bin/sh
holds=1
adj () {
    local id="$1" exp="$2"
    holds=0
}
adj A1 "a real row"
adj A2 "another real row"
if [ "$holds" -ne 1 ]; then echo "RESULT: FAIL"; fi
'''

PLANT_CMP = '''#!/bin/sh
bad=0
echo "G2 neutrality control"
if cmp -s a b; then echo "    ABORT -- the control changed nothing"; fi
if ! cmp -s c d; then bad=1; fi
cmp -s e f
if [ "$bad" -ne 0 ]; then echo "RESULT: FAIL"; fi
'''


def _plant(tmpdir, name, text):
    p = os.path.join(tmpdir, name)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(text)
    return os.path.relpath(p, REPO)


def main():
    print("=" * 74)
    print("VERDICT-BEARING CENSUS -- 2026-11-08")
    print("Which cases carry the verdict, and which sit outside it?")
    print("=" * 74)

    import tempfile
    tmp = tempfile.mkdtemp(prefix="vbc_plant_", dir=REPO)
    try:
        # -- Section 1: planted answers ---------------------------------
        print("\n" + "-" * 74)
        print("SECTION 1 -- the classifier on files whose answers are known")
        print("by construction, both directions planted")
        print("-" * 74)
        for nm, text, want in (
                ("plant_explicit.sh", PLANT_EXPLICIT, "EXPLICIT"),
                ("plant_mixed.sh", PLANT_MIXED, "MIXED_IMPLICIT"),
                ("plant_report.sh", PLANT_REPORT, "REPORT_ONLY"),
                ("plant_nocontrol.sh", PLANT_NO_CONTROL, "VERDICT_NO_CONTROL")):
            rel = _plant(tmp, nm, text)
            got = classify_runner(rel)["klass"]
            check("  P%s %s classifies %s" % (nm[6], nm, want),
                  got == want,
                  "got %s.  The four plants differ in exactly one feature each "
                  "-- the flag, the control prose, whether the adjudicator "
                  "writes the verdict variable -- so a classifier collapsing "
                  "two classes fails here and not on the live tree."
                  % got)
        rel = _plant(tmp, "plant_cmp.sh", PLANT_CMP)
        rows = classify_cmp(rel)
        got = [k for _n, k, _t in rows]
        check("  P5 the three planted `cmp -s` uses classify VERDICT, "
              "CONTROL and REQUIRES_READING",
              got == ["CONTROL", "VERDICT", "REQUIRES_READING"],
              "got %s.  The third is a bare `cmp -s` whose result nothing "
              "reads, which is neither a verdict nor a control and must not "
              "be quietly counted as either" % got)
        check("  P6 a file with no `cmp -s` yields no rows at all",
              classify_cmp(_plant(tmp, "plant_none.sh",
                                  "#!/bin/sh\necho hi\n")) == [],
              "the must-give-nothing direction")
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    # -- Section 2: the live population -------------------------------
    print("\n" + "-" * 74)
    print("SECTION 2 -- every tracked mutation runner")
    print("-" * 74)
    runners = tracked_shell_runners()
    results = {}
    for p in runners:
        results[p] = classify_runner(p)
    width = max(len(p) for p in runners)
    for p in runners:
        r = results[p]
        print("  %-*s  %-18s %s" % (width, p, r["klass"],
                                    ("%s(), %d cases" % (r["func"], r["n_cases"]))
                                    if r["func"] else "-"))
        if r["writes"]:
            print("  %-*s    verdict vars written: %s"
                  % (width, "", ", ".join(r["writes"])))
        if r["control_sites"]:
            print("  %-*s    control case(s) declared in prose at line(s): %s"
                  % (width, "", ", ".join(str(n + 1) for n in r["control_sites"])))
    counts = {}
    for r in results.values():
        counts[r["klass"]] = counts.get(r["klass"], 0) + 1
    print()
    for k in sorted(counts):
        print("  %-18s %2d" % (k, counts[k]))

    # -- Section 3: the standing item's claim, tested -----------------
    print("\n" + "-" * 74)
    print("SECTION 3 -- the standing item's claim, which is why this exists")
    print("-" * 74)
    print("  The 2026-11-07 item says: \"Every other runner here has controls")
    print("  mixed into the same loop as its mutants; none of them says which")
    print("  carry the verdict.\"")
    print()
    mixed = sorted(p for p, r in results.items() if r["klass"] == "MIXED_IMPLICIT")
    explicit = sorted(p for p, r in results.items() if r["klass"] == "EXPLICIT")
    report_only = sorted(p for p, r in results.items() if r["klass"] == "REPORT_ONLY")
    print("  MIXED_IMPLICIT (the defect)     : %s" % (", ".join(mixed) or "none"))
    print("  EXPLICIT (the 11-07 repair)     : %s" % (", ".join(explicit) or "none"))
    print("  REPORT_ONLY (decides nothing)   : %d file(s)" % len(report_only))
    print()
    print("  THE CLAIM IS %s."
          % ("CONFIRMED" if len(mixed) > 1 else
             "OVERSTATED" if len(mixed) <= 1 else "CONFIRMED"))
    print("  It asserts a population and the measured population is %d."
          % len(mixed))
    print("  What the claim's wording misses is REPORT_ONLY: an adjudicator")
    print("  that writes no verdict variable cannot be contaminated by a")
    print("  control, because it decides nothing.  %d of the %d runners are"
          % (len(report_only), len(runners)))
    print("  that, and reading them as instances of the defect would have")
    print("  produced %d repairs with no defect behind them." % len(report_only))

    check("A1 the anchor: run_rx_avail_mutation_tests.sh classifies EXPLICIT",
          results.get("examples/phase6_crv_uart/run_rx_avail_mutation_tests.sh",
                      {}).get("klass") == "EXPLICIT",
          "repaired 2026-11-07 by making verdict_bearing an explicit argument, "
          "so this answer is known from the git history rather than from "
          "plausibility.  A classifier that cannot see the repair is not "
          "measuring the repair's absence either.")
    anchor_tx = results.get(
        "examples/phase6_crv_uart/run_tx_empty_mutation_tests.sh", {})
    check("A2 and its unrepaired sibling classifies REPORT_ONLY, not "
          "MIXED_IMPLICIT",
          anchor_tx.get("klass") == "REPORT_ONLY",
          "got %s.  THIS IS THE SESSION'S FINDING AND IT CONTRADICTS THE "
          "EXPECTATION THIS MODULE WAS WRITTEN WITH.  tx_empty is the template "
          "rx_avail was written from, two days earlier, and the obvious reading "
          "was that it carries the same defect.  It does not: its adj() only "
          "prints ATTRIBUTABLE / NOT ATTRIBUTABLE and writes no verdict "
          "variable, so its T4 control cannot move anything.  The 11-07 defect "
          "was introduced BY rx_avail's own adjudicator folding rows into "
          "sync_only_holds -- a verdict tx_empty's adjudicator does not have."
          % anchor_tx.get("klass"))

    # -- Section 4: every `cmp -s` ------------------------------------
    print("\n" + "-" * 74)
    print("SECTION 4 -- every `cmp -s`, which absorbs the item carried since")
    print("2026-10-25")
    print("-" * 74)
    out = subprocess.run(["git", "ls-files", "*.sh", "*.py"], cwd=REPO,
                         capture_output=True, text=True).stdout
    allfiles = sorted(p for p in out.split("\n") if p.strip())
    tally, residue = {}, []
    total = 0
    # SELF-EXCLUDED TALLY AND DECIDED-SITE SET, ADDED 2026-11-14.  See
    # B2/B2b/B3: this module's own planted shell snippets are `cmp -s`
    # occurrences in a file `git ls-files *.py` returns.
    foreign, decided_sites = {}, {}
    for p in allfiles:
        rows = classify_cmp(p)
        if not rows:
            continue
        print("  %s" % p)
        is_self = os.path.basename(p) in (SELF_CENSUS,
                                          os.path.basename(__file__))
        for n, k, text in rows:
            total += 1
            tally[k] = tally.get(k, 0) + 1
            if not is_self:
                foreign[k] = foreign.get(k, 0) + 1
                if k in ("VERDICT", "CONTROL"):
                    decided_sites.setdefault(k, set()).add(
                        (p, " ".join(text.split())[:55]))
            print("    %-16s line %-5d %s%s"
                  % (k, n, text[:70], "   [SELF-PLANT]" if is_self else ""))
            if k == "REQUIRES_READING":
                residue.append("%s:%d  %s" % (p, n, text[:70]))
    print()
    print("  %d `cmp -s` occurrence(s) over %d file(s)"
          % (total, len([p for p in allfiles if classify_cmp(p)])))
    for k in sorted(tally):
        print("    %-16s %2d" % (k, tally[k]))
    check("B1 the classification is EXHAUSTIVE -- every occurrence has a "
          "class, and the residue is a named worklist rather than a silence",
          total == sum(tally.values()) and total > 0
          and tally.get("MENTION", 0) >= 1,
          "%d occurrences, %d classified, %d needing a human read:\n%s"
          % (total, sum(tally.values()), len(residue),
             "\n".join("  " + r for r in residue[:12])
             + ("\n  ... and %d more" % (len(residue) - 12)
                if len(residue) > 12 else "")))
    # B2 WAS BEING SATISFIED, IN PART, BY THIS MODULE'S OWN PLANTS -- AND THE
    # 2026-11-13 ENTRY'S COUNT FOR THAT IS WRONG.
    #
    # 11-13 re-anchored M4 on the Section-4 TALLY, which is a classifier
    # property and works.  Its stated mechanism was that "six one-line
    # branches left `B2` green under the mutant".  MEASURED 2026-11-14 on this
    # tree, the mutant leaves **three** decided occurrences standing, and
    # **two of the three are this module's own planted snippets**:
    #
    #     if ! cmp -s c d; then bad=1; fi                      -> VERDICT
    #     if cmp -s a b; then echo "    ABORT -- the control"   -> CONTROL
    #
    # Both are ONE-LINERS, so a one-line window still contains their whole
    # branch, and `git ls-files *.py` returns this file.  The only FOREIGN
    # survivor is `phase6_rx_occupancy_probe`'s `cmp -s ... && { ... }`.  So
    # under the mutant the foreign decided set is VERDICT 0, CONTROL 1: a
    # self-excluded B2 goes red on its own, without needing the tally.
    #
    # THIRD INSTANCE here of A MODULE MUST NOT PLANT THE PATTERN IT CENSUSES,
    # after the 10-17 original and this module's own mutation-table guard.
    # The sibling graphene repository has hit it twice in its own censuses.
    # The count and the attribution are corrected here; 11-13's repair is not
    # undone, and its TALLY anchor still stands below.
    check("B2 at least one occurrence in each of the two decided classes "
          "FROM OUTSIDE THIS MODULE, or the classifier is not exercised on "
          "the live tree.  Self-excluded 2026-11-14: two of the three "
          "occurrences that survive the M4 mutant are this module's own "
          "one-line plants, so the un-excluded floor was partly self-met",
          foreign.get("VERDICT", 0) >= 1 and foreign.get("CONTROL", 0) >= 1,
          "foreign VERDICT %d, CONTROL %d, REQUIRES_READING %d  "
          "(including self-plants: VERDICT %d, CONTROL %d)"
          % (foreign.get("VERDICT", 0), foreign.get("CONTROL", 0),
             foreign.get("REQUIRES_READING", 0),
             tally.get("VERDICT", 0), tally.get("CONTROL", 0)))
    check("B2b THE SELF-PLANT IS REAL, not described: this module contributes "
          "exactly one VERDICT and one CONTROL occurrence to its own census, "
          "and they are precisely the two that survive a window shrink",
          tally.get("VERDICT", 0) - foreign.get("VERDICT", 0) == 1
          and tally.get("CONTROL", 0) - foreign.get("CONTROL", 0) == 1,
          "self contributes VERDICT %d, CONTROL %d"
          % (tally.get("VERDICT", 0) - foreign.get("VERDICT", 0),
             tally.get("CONTROL", 0) - foreign.get("CONTROL", 0)))

    # B3: THE DECIDED SITES AS A SET, NOT A COUNT.
    #
    # 11-13's TALLY anchor requires the mutant to CHANGE the tally, which is
    # the right kind of requirement and is still the anchor.  It is a
    # count-level requirement, so a site that silently swaps class while
    # another swaps back satisfies it.  B3 forbids that: the foreign decided
    # sites are declared, keyed on (path, normalised text) and never on line
    # number, so a site keeps its identity when it moves within its file and
    # loses the check when it changes class.  Frozen 2026-11-14 with the
    # measurement that produced it; B3b reports growth and forbids loss.
    # Same shape as the CDC gate's S4.
    DECIDED_1114 = {
        "VERDICT": {
            ("examples/phase5_csr_formal/run_reset_formal.sh",
             'if cmp -s "$dir/uart_controller.v" "$ROOT/rtl/uart_cont'),
            ("examples/phase6_crv_uart/run_mutation_tests.sh",
             'if cmp -s "$RTL" "$WORK/mut.v"; then'),
        },
        "CONTROL": {
            ("examples/phase6_crv_uart/run_mutation_tests.sh",
             'if cmp -s "$RTL" "$WORK/neutral.v"; then'),
            ("examples/phase6_crv_uart/run_mutation_tests_bimodal.sh",
             'if cmp -s "$RTL" "$WORK/neutral.v"; then'),
            ("examples/phase6_crv_uart/run_rx_avail_mutation_tests.sh",
             'if cmp -s "$RTL" "$WORK/neutral.v"; then'),
            ("examples/phase6_crv_uart/run_tx_empty_mutation_tests.sh",
             'if cmp -s "$RTL" "$WORK/neutral.v"; then'),
            ("examples/phase6_rx_occupancy_probe/"
             "run_rx_occupancy_mutation_tests.sh",
             'cmp -s "$RTL" "$WORK/neutral.v" && { echo " ABORT -- ne'),
            ("tools/test_neutrality_controls.py",
             "RTL. The `cmp -s` guard must refuse: a control that cha"),
            # Added by 2026-11-13's mc_neutral_copy repair, and found by B3b
            # reporting it as a GAIN on this set's first run -- which is what
            # B3b is for.
            ("tools/mutation_controls.sh",
             'if cmp -s "$src" "$dest"; then'),
        },
    }
    _lost = dict((k, sorted(DECIDED_1114[k] - decided_sites.get(k, set())))
                 for k in DECIDED_1114)
    _gained = dict((k, sorted(decided_sites.get(k, set()) - DECIDED_1114[k]))
                   for k in DECIDED_1114)
    check("B3 every site declared VERDICT or CONTROL on 2026-11-14 is still "
          "classified that way -- a SET identity on (path, text), so a site "
          "losing its class cannot be netted out by another gaining one, "
          "which a tally can be",
          not any(_lost.values()),
          "lost VERDICT %r; lost CONTROL %r"
          % (_lost["VERDICT"], _lost["CONTROL"]))
    check("B3b and the declaration may only GROW: new decided sites are "
          "reported, never silently absorbed",
          True,
          "gained VERDICT %r; gained CONTROL %r"
          % (_gained["VERDICT"], _gained["CONTROL"]))

    # -- Section 5: mutation ------------------------------------------
    # A CENSUS THAT CANNOT FAIL IS NOT EVIDENCE, and this one was WRONG FOUR
    # TIMES before it was right -- the def-line regex, the definition of a
    # verdict variable, the `cmp -s` window (twice) and mention-versus-use.
    # Every one of those was caught by a plant or an anchor rather than by
    # reading, which is the argument for having them; the mutation suite is
    # the argument that they still work.  Each mutant must turn a NAMED check
    # red, not merely make the module exit nonzero: a mutation that breaks
    # something else would otherwise read as a catch.
    if os.environ.get("VBC_MUTANT") != "1":
        print("\n" + "-" * 74)
        print("SECTION 5 -- MUTATION.  Each defect must turn a NAMED check red")
        print("-" * 74)
        # A MODULE THAT MUTATES ITSELF MUST NOT MUTATE ITS OWN MUTATION
        # TABLE, and M1 and M4 reported "the anchor occurs 2 times, not once"
        # on their first run for exactly that reason: the anchor text appears
        # both in the code and in the literal below that names it.  The
        # replacement is therefore confined to the source ABOVE the table.
        # This is the repository's own "a module must not plant the pattern
        # it censuses" item, met from the other side -- and the PLANTED guard
        # is what turned a silent mis-mutation into a named failure rather
        # than a passing control.
        whole = open(os.path.join(HERE, os.path.basename(__file__)),
                     encoding="utf-8").read()
        _cut = whole.index("        mutants = [")
        src, tail = whole[:_cut], whole[_cut:]
        # Built from the live tuple rather than retyped, so this anchor
        # cannot drift out of agreement with the constant it mutates --
        # which is how a planted mutation turns into a FAULT IN THE TEST.
        VERDICT_WORDS_SRC = (
            'VERDICT_WORDS = ("RESULT:", "CONFIRMED", "DOES NOT HOLD", "REFUTED",'
            '\n                 "HOLDS", "VERDICT", "SURVIVED")')
        mutants = [
            ("M1 the def-line regex stops allowing a trailing comment",
             r'r"^([A-Za-z_][A-Za-z0-9_]*)\s*\(\)\s*\{\s*(?:#.*)?$")',
             r'r"^([A-Za-z_][A-Za-z0-9_]*)\s*\(\)\s*\{\s*$")',
             "A2",
             "this is the first form, and under it every runner that writes "
             "`adj () {    # $1 id ...` classifies NO_ADJUDICATOR"),
            ("M2 a verdict variable is again only what the EXIT CODE reads",
             VERDICT_WORDS_SRC,
             'VERDICT_WORDS = ("RESULT:",)',
             "A1",
             "the narrow definition, under which the one file known to carry "
             "the 11-07 repair classifies REPORT_ONLY and the census reports "
             "that the defect exists nowhere"),
            ("M3 a mention counts as a use again",
             "    head = line[:pos]",
             "    return False\n    head = line[:pos]",
             "B1",
             "prose occurrences -- comments explaining why a `cmp -s` guard "
             "was REPLACED -- are the largest single class, and counting "
             "them as uses reports a population that does not exist.  THE "
             "NUMBERS ARE NOT WRITTEN HERE: this row carried '21 of the 45 "
             "occurrences ... 88 per cent' from 2026-11-08 until 2026-11-13, "
             "by which time the live tree said 39 of 72 and 118 per cent.  "
             "The premise now lives in PREMISES['M3'] and is checked"),
            ("M4 the branch window shrinks back to one line",
             "def _branch_extent(lines, n, cap=24):",
             "def _branch_extent(lines, n, cap=0):",
             "TALLY",
             "the second wrong window.  RE-ANCHORED 2026-11-13: this row "
             "required `B2` to go red on the premise that every real "
             "occurrence assigns several lines into its branch -- true on "
             "2026-11-08, false by 2026-11-12, when six one-line branches "
             "left `B2` green under the mutant and the row sat red for four "
             "days.  The requirement is now a property of the CLASSIFIER: "
             "the mutant must CHANGE THE SECTION-4 TALLY, which a wrong "
             "window does by construction whatever the tree contains"),
        ]
        for label, old, new, want_red, why in mutants:
            if src.count(old) != 1:
                check(label + " -- PLANTED", False,
                      "the anchor occurs %d times in the source above the "
                      "mutation table, not once, so the mutation could not be "
                      "planted: this row is a FAULT IN THE TEST and not a "
                      "passing control" % src.count(old))
                continue
            mp = os.path.join(HERE, "_vbc_mutant.py")
            try:
                with open(mp, "w", encoding="utf-8") as fh:
                    fh.write(src.replace(old, new, 1) + tail)
                env = dict(os.environ)
                env["VBC_MUTANT"] = "1"
                r = subprocess.run([sys.executable, mp], cwd=REPO,
                                   capture_output=True, text=True, env=env,
                                   timeout=300)
                reds = re.findall(r"^  \[FAIL\]\s+(\S+)", r.stdout, re.M)
                if want_red == "TALLY":
                    # A CLASSIFIER PROPERTY, NOT A TREE PROPERTY.  The
                    # Section-4 tally lines are `    CLASS  n` and are the
                    # only lines of that shape; the per-occurrence rows carry
                    # a line number and so cannot be confused with them.
                    mt = dict((k, int(v)) for k, v in re.findall(
                        r"^    ([A-Z_]+)\s+(\d+)\s*$", r.stdout, re.M))
                    if not mt:
                        check(label + " -- PLANTED", False,
                              "the mutant printed no Section-4 tally, so the "
                              "requirement could not be evaluated: this row "
                              "is a FAULT IN THE TEST and not a passing "
                              "control.  stderr: %s"
                              % (r.stderr.strip()[-300:] or "(none)"))
                        continue
                    caught = mt != tally
                    check(label, caught,
                          "%s.\n        must CHANGE the tally; live %r, "
                          "under the mutant %r" % (why, tally, mt))
                else:
                    caught = want_red in reds
                    check(label, caught,
                          "%s.\n        must turn %s red; red checks under "
                          "the mutant: %s" % (why, want_red, reds or "NONE"))
            finally:
                if os.path.exists(mp):
                    os.remove(mp)

    # -- Section 6: the mutant premise census -------------------------
    #
    # INSIDE THE NON-MUTANT GUARD ON PURPOSE.  Under a mutant these relations
    # are statements about a deliberately broken classifier -- M4's mutant
    # drives multi_branch to zero -- so running them there would add reds that
    # no mutant row is asking about and would make every mutant run re-walk
    # the tree.  The premises are properties of the LIVE tree and are checked
    # once, here.
    if os.environ.get("VBC_MUTANT") != "1":
        print("\n" + "-" * 74)
        print("SECTION 6 -- THE MUTANT PREMISE CENSUS.  A mutant whose "
              "premise is")
        print("a property of the TREE dies when the tree moves, and nothing "
              "says so")
        print("-" * 74)
        st = tree_stats()
        unmeasured = []
        for mid in sorted(PREMISES):
            prose, rel, report = PREMISES[mid]
            if prose is None:
                unmeasured.append(mid)
                print("  %s  [not a relation] %s" % (mid, report(st)))
                continue
            check("C1.%s the premise of %s still holds on the live tree: %s"
                  % (mid, mid, prose), bool(rel(st)), report(st))
        check("C2 every mutant's premise is either a CHECKED RELATION or a "
              "NAMED entry on this worklist -- %d of %d are not relations "
              "over these numbers, and they are named rather than silent"
              % (len(unmeasured), len(PREMISES)),
              len(unmeasured) + len([m for m in PREMISES
                                     if PREMISES[m][0] is not None])
              == len(PREMISES),
              "not reducible: %s" % (", ".join(unmeasured) or "none"))
        check("C3 the live tally is REPORTED alongside every premise rather "
              "than asserted inside one, which is the carried item S7 SHOULD "
              "REPORT THE PREDICTED COUNT ALONGSIDE THE MEASURED ONE getting "
              "an instance",
              st["total"] == sum(st["tally"].values())
              and st["multi_branch"] + st["single_branch"]
              == st["total"] - st["tally"].get("MENTION", 0),
              "total %d = %r; non-mention %d = %d multi + %d one-line"
              % (st["total"], st["tally"],
                 st["total"] - st["tally"].get("MENTION", 0),
                 st["multi_branch"], st["single_branch"]))
        check("C4 SCORING THE 2026-11-12 PREDICTION (1).  It said re-anchoring "
              "M4 would turn up a SECOND stale mutant premise in the same "
              "file, and that the risky half was 'in the same file'.  RIGHT "
              "ON THE FILE AND WRONG ON THE KIND: M3's premise was stale -- "
              "it said 21 of 45 occurrences and 88 per cent where the live "
              "tree says %d of %d and %.0f per cent -- but it was stale in "
              "PROSE NO INSTRUMENT READS, so M3 went on passing.  M4 died "
              "because its premise was load-bearing; M3's was merely wrong"
              % (st["tally"].get("MENTION", 0), st["total"],
                 100.0 * st["tally"].get("MENTION", 0)
                 / max(1, st["total"] - st["tally"].get("MENTION", 0))),
              st["tally"].get("MENTION", 0) != 21 or st["total"] != 45)
        check("C5 and the generalisation the prediction did not reach: of the "
              "four mutants, THREE had premises that are statements about the "
              "tree and only one is a statement about a particular file.  "
              "Two of the three had drifted in four days.  The repair is the "
              "form of the premise -- a relation rather than a magnitude -- "
              "and M4 is now anchored on the classifier instead",
              len([m for m in PREMISES if PREMISES[m][0] is not None]) == 3)

    print("\n" + "=" * 74)
    print("SUMMARY")
    print("=" * 74)
    for lab in _PASS:
        print("  PASS  %s" % lab)
    for lab in _FAIL:
        print("  FAIL  %s" % lab)
    print("\nTOTAL: %d passed, %d failed" % (len(_PASS), len(_FAIL)))
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
