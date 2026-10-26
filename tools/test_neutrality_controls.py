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

EXTENDED 2026-10-26 to runners E, F and G -- the three transcript-comparing
runners that gained the arm that day.  All five of the runners the 2026-10-25
item named were CHECKED FIRST and none had one, so unlike that session's item
(which named three runners of which one already carried a STRONGER arm) the
premise held.  E and F carry the arm over rtl/uart_controller.v; G carries it
over bfm/uart_rx_pin_bfm.v, the only one of the five whose mutation target is
not the RTL, which is why the shared helper takes a path rather than reading a
fixed one.

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

Usage:  python3 tools/test_neutrality_controls.py [B|D|E|F|G]
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
    # Added 2026-10-26 with the three ports.  These three carry the arm via
    # `mc_neutral_copy` in tools/mutation_controls.sh rather than an inlined
    # `cp`, so they are injected at a declared `# G2b-INJECT` marker with a
    # shell-function OVERRIDE instead of by rewriting a `cp` line.  Overriding
    # inside the COPY, not in the shared helper, is deliberate: the helper is
    # read by three runners and mutating it would test them all at once and
    # name none of them.
    ('E', 'examples/phase6_rx_pin_driver/run_mutation_tests.sh'),
    ('F', 'examples/phase6_baud_error_coverage/run_mutation_tests.sh'),
    ('G', 'examples/phase6_bfm_equivalence/run_mutation_tests.sh'),
)

# The runners whose arm is injected at the marker rather than at a `cp` line.
MARKER = '# G2b-INJECT -- tools/test_neutrality_controls.py replaces THIS LINE'
MARKER_RUNNERS = ('E', 'F', 'G')

# One override per defect, substituted for the marker line inside the COPY.
# N1 is a REAL behavioural edit, and for E/F it is the same STATUS-decode
# defect runner B's T1 uses, for the same reason: both benches demonstrably
# detect it, so a non-abort cannot be excused as an undetectable edit.  G
# mutates the BFM rather than the RTL, so its N1 edit has to be a BFM one --
# dropping the return-to-idle assignment, which is G's own row 8 and is
# DETECTED there with 968 errors.
# The two lines of the committed arm, as runners B and D hold it inline.
CP_LINE = 'cp "$RTL" "$WORK/neutral.v"'
COMMENT_TEXT = '// G2b cosmetic-edit control'

# A REAL behavioural change for B and D: tx_empty stuck clear in the STATUS
# decode.  This is runner B's own T1 mutant, chosen because both benches are
# known to detect it, so an N1 that does not abort cannot be excused as an
# undetectable edit.  E, F and G need their OWN rows -- see OVERRIDES below
# and the fault that comment records.
REAL_SED = ("s/rx_avail, rx_full, tx_empty, tx_full};"
            "/rx_avail, rx_full, 1'b0, tx_full};/")
REAL_LINE = ('sed "%s" "$RTL" > "$WORK/neutral.v"'
             % REAL_SED.replace('"', '\\"'))

OVERRIDES = {}

# N1 must be a defect the runner under test DEMONSTRABLY DETECTS, or a
# non-abort could be excused as an undetectable edit rather than read as a
# dead arm.  THE FIRST DRAFT GOT THIS WRONG AND THIS FILE SAID SO: it reused
# runner B's STATUS-decode `tx_empty` edit for E, the RX-pin bench, which
# does not look at that field at all.  E scored 3/4 with N1 passing SILENTLY
# -- the very "a control that can never fire" shape this file exists to
# catch, found in this file.  Each runner's N1 is now one of its OWN detected
# rows: M1 (BAUD_DIV ignored by the baud generator) for E and F, and row 8
# (the BFM's return-to-idle assignment dropped, 968 errors there) for G,
# which mutates the BFM and not the RTL.
_NEU_TAIL = 'cmp -s "$1" "$2" && return 1; return 0; }'
_N1_SED_RTL = "s|else if (baud_cnt == 8'd0) baud_cnt <= baud_div;|else if (baud_cnt == 8'd0) baud_cnt <= 8'd0;|"
_N1_SED_BFM = 's/rx = 1.b1;                       \\/\\/ return to idle//g'
_N1_RTL = ('mc_neutral_copy () { sed "' + _N1_SED_RTL
           + '" "$1" > "$2"; ' + _NEU_TAIL)
_N1_BFM = ('mc_neutral_copy () { sed "' + _N1_SED_BFM
           + '" "$1" > "$2"; ' + _NEU_TAIL)
_N2 = 'mc_neutral_copy () { cp "$1" "$2"; ' + _NEU_TAIL
_N3 = ('mc_neutral_copy () { cp "$1" "$2"; '
       'printf "\\nthis is not verilog\\n" >> "$2"; return 0; }')
for _r in ('E', 'F'):
    OVERRIDES[_r] = {'n1': _N1_RTL, 'n2': _N2, 'n3': _N3}
OVERRIDES['G'] = {'n1': _N1_BFM, 'n2': _N2, 'n3': _N3}

NEEDLES = {
    'B': {'n1': 'was not a clean escape in every',
          'n2': 'controls nothing',
          'n3': 'DOES NOT COMPILE, so the'},
    'D': {'n1': 'was not a clean PASS in both',
          'n2': 'controls nothing',
          'n3': 'does not COMPILE, so the'},
    # E and F share the N1 and N3 wording with each other but not within
    # themselves, which is the property that matters: a needle has to tell
    # THIS runner's arms apart, not tell runners apart.
    'E': {'n1': 'was NOT a clean escape, so this bench',
          'n2': 'byte-identical to the original',
          'n3': "void branch's own failure mode"},
    'F': {'n1': 'was NOT a clean escape, so the',
          'n2': 'byte-identical to the original',
          'n3': 'measured nothing rather than measuring a clean escape'},
    'G': {'n1': 'reported errors = ',
          'n2': 'byte-identical; it controls nothing',
          'n3': 'void branch\'s failure mode inside'},
}


def mutate_marker(src, name, tag):
    """Replace the declared `# G2b-INJECT` marker line with an override.

    Returns None if the marker is absent -- reported as a failed injection and
    never as a pass, which is the `BADINJ` distinction 2026-10-25 established.
    """
    if tag == 'n0':
        return src
    lines = src.splitlines(True)
    hit = [i for i, l in enumerate(lines) if l.startswith(MARKER)]
    if len(hit) != 1:
        return None
    lines[hit[0]] = OVERRIDES[name][tag] + '\n'
    return ''.join(lines)


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


def run_probe(runner, tag, name=None):
    """(returncode, output) for a mutated copy placed BESIDE the runner."""
    path = os.path.join(ROOT, runner)
    src = io.open(path, encoding='utf-8').read()
    mut = (mutate_marker(src, name, tag) if name in MARKER_RUNNERS
           else mutate(src, tag))
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

        rc, out = run_probe(runner, 'n0', name)
        reached = ('G2b holds' in out) or ('comment-only edit escapes' in out) \
            or ('compiles and escapes on RESULT: PASS' in out) \
            or ('errors = 0 on the comment-only edit' in out)
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
             NEEDLES[name]['n2']),
            ('n3', 'N3 an edit that emits non-Verilog is refused, and by a '
                   'DIFFERENT message than N1', NEEDLES[name]['n3']),
        ):
            rc, out = run_probe(runner, tag, name)
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
