#!/usr/bin/env python3
"""
tools/cdc_structural_check_mutation.py -- mutation test for the structural
CDC checker's OWN self-test.

WHY
---
`cdc_structural_check.py --selftest` reports 25/25.  So did an earlier
version of it whose R2 rule could not run at all, because a two-direction
ANSI port line made every such module outputless; the suite was green and
the rule was dead.  A self-test's score is evidence about the suite only
once something has shown the suite can go red.

2026-09-17 recorded the same lesson from the other direction: a UART bench
passing 55/55 against deliberately broken RTL.  2026-11-10's CDC mutation
harness applied that to the RTL.  This applies it to the INSTRUMENT: each
mutant below is a plausible defect in the checker's source, and the
requirement is that `--selftest` FAILS for every one.  A mutant that leaves
the suite green names a check nobody wrote.

Usage:
    python3 tools/cdc_structural_check_mutation.py
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, "cdc_structural_check.py")
ROOT = os.path.dirname(HERE)

# (id, description, old_text, new_text)
MUTANTS = [
    ("M1", "is_synchroniser() answers from the NAME alone again",
     "    if not SYNC_MODULE_RE.search(mod.name):\n        return False",
     "    if not SYNC_MODULE_RE.search(mod.name):\n        return False\n"
     "    return True"),
    ("M2", "R1 never fires (the reconvergence rule removed)",
     '        for blk in mod.blocks:\n            if blk.clock is None:\n'
     '                continue\n            hits = [ln for ln, net in '
     'blk.reads if net == d_net]',
     '        for blk in mod.blocks:\n            if blk.clock is None:\n'
     '                continue\n            hits = []'),
    ("M3", "R2 accepts a one-flop synchroniser (threshold off by one)",
     "            if depth < 2:", "            if depth < 1:"),
    ("M4", "R3 treats an unresolvable width as safe",
     "        if width is None and wtext is not None:",
     "        if False and wtext is not None:"),
    ("M5", "the Gray exemption exempts everything",
     "        if _gray_driven(d_net):", "        if True or _gray_driven(d_net):"),
    ("M6", "the instance regex loses its word boundaries (the `if (` bug)",
     'r"\\s*(" + _IDENT + r")\\b\\s*(#\\s*\\([^;]*?\\))?\\s*(" + _IDENT +\n'
     '            r")\\b\\s*\\(", line)',
     'r"\\s*(" + _IDENT + r")\\s*(#\\s*\\([^;]*?\\))?\\s*(" + _IDENT +\n'
     '            r")\\s*\\(", line)'),
    ("M7", "`initial` no longer ends the preceding always block",
     'if re.match(r"\\s*(initial|final|task|function|endtask|endfunction|"\n'
     '                    r"specify|endspecify)\\b", line):',
     'if re.match(r"\\s*(zzzz_never_matches)\\b", line):'),
    ("M8", "a port line's second direction is ignored again",
     "            for idx, (pos, direction) in enumerate(marks):",
     "            for idx, (pos, direction) in enumerate(marks[:1]):"),
    ("M9", "multi-statement lines are not split",
     '                segments = [seg for seg in stripped.split(";") if seg.strip()]',
     '                segments = [stripped]'),
]


def run_selftest(path, cwd):
    proc = subprocess.run([sys.executable, path, "--selftest",
                           "--root", ROOT],
                          cwd=cwd, capture_output=True, text=True,
                          timeout=180)
    fails = len(re.findall(r"^  FAIL ", proc.stdout, re.M))
    return proc.returncode, fails, proc.stdout


def main():
    src = open(TARGET, encoding="utf-8").read()
    print("=" * 74)
    print("MUTATION TEST -- tools/cdc_structural_check.py's own self-test")
    print("=" * 74)

    tmp = tempfile.mkdtemp(prefix="cdcmut_")
    try:
        # the checker walks ROOT for .v files, so the mutant must live in a
        # tree that still contains them: copy the file, not the repository
        work = os.path.join(tmp, "cdc_structural_check.py")
        shutil.copy(TARGET, work)
        rc, fails, _ = run_selftest(work, HERE)
        print("\nBASELINE (unmutated): rc=%d, %d failing check(s)"
              % (rc, fails))
        if rc != 0 or fails:
            print("BASELINE IS NOT GREEN -- every mutant verdict below would "
                  "be meaningless.  Stopping.")
            return 2

        print("\n%-4s %-62s %s" % ("id", "mutant", "verdict"))
        print("-" * 74)
        detected, survived, unapplied = [], [], []
        for mid, desc, old, new in MUTANTS:
            if old not in src:
                unapplied.append(mid)
                print("%-4s %-62s ANCHOR LOST" % (mid, desc[:62]))
                continue
            open(work, "w", encoding="utf-8").write(src.replace(old, new, 1))
            rc, fails, out = run_selftest(work, HERE)
            if rc != 0 and fails:
                detected.append(mid)
                first = re.search(r"^  FAIL  (\S+)", out, re.M)
                print("%-4s %-62s detected by %s (%d fail)"
                      % (mid, desc[:62], first.group(1) if first else "?",
                         fails))
            else:
                survived.append(mid)
                print("%-4s %-62s SURVIVED" % (mid, desc[:62]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("-" * 74)
    print("%d detected, %d survived, %d anchors lost, of %d"
          % (len(detected), len(survived), len(unapplied), len(MUTANTS)))
    if unapplied:
        print("\nANCHOR LOST means this harness and the checker have drifted "
              "apart: the mutant's text is no longer in the source, so "
              "nothing was tested.  Treated as a FAILURE, not a skip.")
    if survived:
        print("\nSURVIVED means the self-test cannot tell the difference "
              "between the checker and a broken checker:")
        for mid in survived:
            print("  - %s %s" % (mid, dict((m[0], m[1])
                                           for m in MUTANTS)[mid]))
    verdict = "ALL_DETECTED" if not survived and not unapplied else "INCOMPLETE"
    print("\nMUTATION_RESULT: %s (%d/%d)"
          % (verdict, len(detected), len(MUTANTS)))
    return 0 if verdict == "ALL_DETECTED" else 1


if __name__ == "__main__":
    sys.exit(main())
