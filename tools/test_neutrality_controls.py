#!/usr/bin/env python3
"""tools/test_neutrality_controls.py -- is the G2b neutrality arm REACHABLE?

WHY THIS EXISTS.  2026-10-25 ported the cosmetic-edit positive control from
`run_mutation_tests.sh`'s `G2` into runners B and D, which had none, and both
reported green on the first run.  A control that reports green and can never
report anything else is not a control.  This repository's recorded dominant
failure mode is exactly that -- a verdict answering a weaker question than the
one it was written to ask -- and the two preceding sessions each found an
instance: 2026-10-23 a refusal branch nothing reached, 2026-10-24 a mutant row
that had never been injected and whose compile error was scored as its
detection.  So the new arm is mutation-tested before it is trusted, and the
port is not claimed to work merely because it printed OK.

THE QUESTION, asked identically of each runner carrying a G2b arm:

    Inject one defect into a COPY of the runner, run it, and require the copy
    to ABORT -- non-zero exit AND a message naming the arm.

    N1  the comment-only edit is replaced by a REAL behavioural change (the
        STATUS decode row runner B's own T1 mutates, so the defect injected
        is one the benches demonstrably CAN see).  The arm must notice the
        edit is not neutral.  This is the positive control proper: it is the
        only mutation that proves the arm distinguishes a neutral edit from a
        behavioural one, which is the entire claim.
    N2  the edit is removed, so the "neutral" file is byte-identical to the
        RTL.  The `cmp -s` guard must refuse: a control that changes nothing
        controls nothing.
    N3  the edit emits text that is not Verilog.  The arm must refuse rather
        than read the resulting compile failure as a clean escape -- G3's
        failure mode occurring INSIDE the control that exists to make G3's
        verdicts attributable, i.e. the 2026-10-24 fault one level up.

A NEGATIVE CONTROL, because an injector that breaks a runner outright would
make every row above look like a success:

    N0  the UNMUTATED copy must reach G2b, pass, and exit 0.  Run first.  If
        the copy cannot pass, nothing below means anything.  This is the arm
        that earned its place on 2026-10-24, when the equivalent control
        caught a probe copy placed at the wrong directory depth.

WHERE THE COPY LIVES, and that is not a detail.  Both runners resolve `ROOT`
as `$(dirname $0)/../..`, so a copy at the wrong DEPTH resolves `ROOT` to a
directory with no `rtl/` and produces no rows at all -- precisely the defect
2026-10-24 caught in its own probe.  Each copy is therefore written BESIDE
the runner it copies, at the same depth, and removed afterwards.

NO COMMITTED RUNNER IS EDITED.

Usage:  python3 tools/test_neutrality_controls.py [B|D]
Run from the repo root.  With no argument every runner is tested; with a
runner letter only that one, because a full pass is ~6 minutes and the
automation environment caps a single call at 180 s.  The committed report is
the concatenation of the per-runner runs, and each run prints its own TOTAL,
so a partial report cannot be mistaken for a complete one.
"""

import io
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

RUNNERS = (
    ('B', 'examples/phase6_crv_uart/run_tx_empty_mutation_tests.sh'),
    ('D', 'examples/phase6_crv_uart/run_mutation_tests_bimodal.sh'),
)

# The two lines of the committed arm, as every runner carrying it holds them.
CP_LINE = 'cp "$RTL" "$WORK/neutral.v"'
COMMENT_TEXT = '// G2b cosmetic-edit control'

# A REAL behavioural change: tx_empty stuck clear in the STATUS decode.  This
# is runner B's own T1 mutant, chosen because both benches are known to detect
# it, so an N1 that does not abort cannot be excused as an undetectable edit.
REAL_SED = ("s/rx_avail, rx_full, tx_empty, tx_full};"
            "/rx_avail, rx_full, 1'b0, tx_full};/")
REAL_LINE = ('sed "%s" "$RTL" > "$WORK/neutral.v"'
             % REAL_SED.replace('"', '\\"'))

# THE NEEDLE IS ARM-SPECIFIC, AND THAT IS THE POINT.  The first draft of this
# file matched the bare string "ABORT" for N1 and N3.  Every abort in these
# runners prints "ABORT", G1's included, so that needle would have passed on a
# mutant that aborted for an unrelated reason and on a mutant whose two
# distinct failure modes produced one indistinguishable message -- the
# weak-question fault this repository has now found in seven of its own
# verdicts.  Each needle below is a sentence only the intended arm prints, and
# N1's and N3's differ, which is what makes "refused for the right reason"
# measurable rather than assumed.  Separating them required giving runner B
# its own compile guard; runner D already had one.
NEEDLES = {
    'B': {'n1': 'was not a clean escape in every',
          'n3': 'DOES NOT COMPILE, so the'},
    'D': {'n1': 'was not a clean PASS in both',
          'n3': 'does not COMPILE, so the'},
}


def mutate(src, tag):
    """The runner source with one defect injected, or None if the anchor is
    absent -- which is reported as a failed injection and never as a pass."""
    if tag == 'n0':
        return src
    if tag == 'n1':
        if src.count(CP_LINE) != 1:
            return None
        return src.replace(CP_LINE, REAL_LINE, 1)
    if tag == 'n2':
        # Drop the appending printf entirely: the continuation line that
        # follows it carries the redirection, so `: \` keeps the shell valid
        # while writing nothing.
        m = re.search(r"^printf '[^']*%s[^']*' \\\n" % re.escape('\\n'), src,
                      re.M)
        if not m:
            m = re.search(r"^printf .*%s.*\\\n" % re.escape(COMMENT_TEXT),
                          src, re.M)
        if not m:
            return None
        return src[:m.start()] + ': \\\n' + src[m.end():]
    if tag == 'n3':
        if src.count(COMMENT_TEXT) != 1:
            return None
        return src.replace(COMMENT_TEXT,
                           'this is not verilog and must not compile //', 1)
    raise AssertionError(tag)


def run_probe(runner, tag):
    """(returncode, output) for a mutated copy placed BESIDE the runner."""
    path = os.path.join(ROOT, runner)
    src = io.open(path, encoding='utf-8').read()
    mut = mutate(src, tag)
    if mut is None:
        return None, 'anchor not found'
    if tag != 'n0' and mut == src:
        return None, 'injection changed nothing'
    d, base = os.path.dirname(path), os.path.basename(path)[:-3]
    copy = os.path.join(d, '.probe_%s_%s.sh' % (base, tag))
    io.open(copy, 'w', encoding='utf-8').write(mut)
    try:
        p = subprocess.run(['bash', copy], cwd=ROOT, capture_output=True,
                           text=True, timeout=900)
        return p.returncode, p.stdout + p.stderr
    finally:
        os.remove(copy)


def main():
    checks = []

    def check(ok, label, detail=''):
        checks.append((bool(ok), label))
        print('  %-4s %s' % ('PASS' if ok else 'FAIL', label))
        for line in detail.splitlines():
            print('       %s' % line)

    print('=' * 62)
    print('IS THE G2b NEUTRALITY ARM REACHABLE?')
    print('=' * 62)
    print()

    only = [a.upper() for a in sys.argv[1:]]
    runners = [r for r in RUNNERS if not only or r[0] in only]
    if not runners:
        print('no runner matches %s; known: %s'
              % (only, ', '.join(n for n, _ in RUNNERS)))
        return 2
    for name, runner in runners:
        print('-' * 62)
        print('RUNNER %s  %s' % (name, runner))
        print('-' * 62)

        rc, out = run_probe(runner, 'n0')
        reached = ('G2b holds' in out) or ('comment-only edit escapes' in out)
        check(rc == 0 and reached,
              'N0 negative control: the UNMUTATED copy reaches G2b, passes '
              'and exits 0',
              'rc=%s  reached-G2b=%s\n%s' % (
                  rc, reached,
                  '(so the probe harness is not the perturbation)'
                  if rc == 0 and reached else
                  'the COPY is broken, not the arm -- every row below is '
                  'meaningless'))

        for tag, label, needle in (
            ('n1', 'N1 a REAL behavioural edit in place of the comment is '
                   'refused', NEEDLES[name]['n1']),
            ('n2', 'N2 an edit that changes NOTHING is refused',
             'controls nothing'),
            ('n3', 'N3 an edit that emits non-Verilog is refused, and by a '
                   'DIFFERENT message than N1', NEEDLES[name]['n3']),
        ):
            rc, out = run_probe(runner, tag)
            if rc is None:
                check(False, label,
                      'the injection itself failed (%s), so nothing was '
                      'measured' % out)
                continue
            hit = needle in out
            check(rc != 0 and hit, label,
                  'rc=%s  message-matched=%s%s'
                  % (rc, hit,
                     '' if (rc != 0 and hit) else
                     '\nneeded rc != 0 AND the abort message; a silent pass '
                     'here\nmeans the arm is unreachable and its green '
                     'verdict is worthless'))
        print()

    npass = sum(1 for ok, _ in checks if ok)
    print('=' * 62)
    print('TOTAL: %d passed, %d failed' % (npass, len(checks) - npass))
    for ok, label in checks:
        if not ok:
            print('   FAILED: %s' % label)
    print('=' * 62)
    return 0 if npass == len(checks) else 1


if __name__ == '__main__':
    sys.exit(main())
