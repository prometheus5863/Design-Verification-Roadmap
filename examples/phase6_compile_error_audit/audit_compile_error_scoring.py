#!/usr/bin/env python3
"""examples/phase6_compile_error_audit/audit_compile_error_scoring.py

AUDIT: does a mutant that FAILS TO COMPILE score as a DETECTION?

WHY THIS EXISTS.  On 2026-10-22 `phase6_crv_uart/run_mutation_tests.sh` was
found to score `COMPILE_ERROR` as `DETECT`.  Its M7 row had therefore read
"predicted DETECT, got DETECT (as predicted)" in every committed report since
2026-10-12 -- with a stated reason naming a specific check -- for a mutant
whose injected sed emits the four characters \\x27 and has never been a
Verilog program.

That session named the generalisation and did not run it.  Four files mention
COMPILE_ERROR, three were unaudited, and the log recorded explicitly that
"none should be assumed clean".  One of the three was guessed to "may already
be correct" because it "reports it as its own verdict class".  THIS SCRIPT
ASKS THE QUESTION OF EACH RUNNER INSTEAD OF GUESSING.

THE QUESTION, asked identically of every runner:

    Inject a mutant whose edit SUCCEEDS (the file really changes, so the
    existing no-op guard passes) but whose product DOES NOT COMPILE.
    Then: (Q1) does the row score as detected?  (Q2) does the runner's own
    exit status reflect that something went wrong?

WHY BOTH QUESTIONS.  A false DETECT and a false PASS are different faults with
the same consequence.  Q1 asks what the table says; Q2 asks what a regression
driver sees.  A runner can print COMPILE_ERROR honestly in its table and still
exit 0, in which case a regression driver reads it as green and the honest
table is never looked at.  Q2 is the question 2026-10-22 did not think to ask,
and it is the one that separates the two shell runners.

THE PROBE IS THE HISTORICAL DEFECT, NOT AN INVENTED ONE.  Where a runner
injects by sed, the probe emits the literal text \\x27 -- the exact malformed
escape of the real M7 bug -- so what is measured is the fault that actually
occurred rather than a convenient substitute.

CONTROLS.  An audit that reports "defective" for every runner it touches has
measured its own probe, not the runners.

  A1  the probe really does fail to compile, and the file really does change.
      Compiled directly and required to return non-zero BEFORE any runner
      verdict is read.  Without this a silently-compiling probe would make
      every runner look clean.
  A2  NEGATIVE CONTROL: in the same run, each runner's OTHER rows -- mutants
      that compile and genuinely fail -- must still score as detected.  A
      probe that broke a runner outright would take those down with it, and
      the resulting "defective" would be the audit's own doing.
  A3  DECLARED EXPECTATION: the string each runner is expected to print is
      declared in this file BEFORE the run and the match is asserted, so a
      reader that silently found nothing cannot be mistaken for a runner
      that was clean.

No committed runner is edited.  Runner A needs no probe at all -- its defect
is in the committed file and reproduces live.  Runner B is copied and the
copy patched.  Runner C is imported and its mutant list extended IN MEMORY.
Runner D is read only, and reported as unmeasured rather than assumed clean.

Usage:  python3 examples/phase6_compile_error_audit/audit_compile_error_scoring.py
Run from the repo root, after sourcing tools/setup_iverilog.sh WITHOUT a pipe.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
IVL = os.environ.get('IVERILOG_INSTALL_DIR', '/tmp/iverilog_install')
IVL_BIN = os.path.join(IVL, 'usr/bin')
IVL_LIB = os.path.join(IVL, 'usr/lib/x86_64-linux-gnu/ivl')

RUNNER_A = 'examples/phase6_crv_uart/run_mutation_tests.sh'
RUNNER_B = 'examples/phase6_crv_uart/run_tx_empty_mutation_tests.sh'
RUNNER_C = 'examples/phase1_mutation/run_mutation_tests.py'
RUNNER_D = 'examples/phase6_crv_uart/run_mutation_tests_bimodal.sh'

UART_RTL = os.path.join(ROOT, 'rtl/uart_controller.v')
UART_TB = os.path.join(ROOT, 'examples/phase6_crv_uart/uart_crv_cov_tb.v')

# The literal text the real malformed sed emits: backslash, x, 2, 7.
PROBE_TEXT = r'4\x27d7'

FAILURES = []


def fail(msg):
    FAILURES.append(msg)
    print('      *** CONTROL FAILED: %s' % msg)


def rule(ch='-'):
    print(ch * 74)


def compile_uart(path, work):
    return subprocess.run(
        [os.path.join(IVL_BIN, 'iverilog'), '-B', IVL_LIB, '-g2012',
         '-o', os.path.join(work, 'sim'), path, UART_TB],
        capture_output=True, text=True)


# ---------------------------------------------------------------------------
# A1
# ---------------------------------------------------------------------------
def control_a1():
    print('A1  the probe changes the file AND does not compile')
    print('    (asserted BEFORE any runner verdict is read)')
    work = tempfile.mkdtemp(prefix='ce_a1.')
    src = open(UART_RTL).read()
    anchor = "wire tx_full  = (tx_cnt == 4'd8);"
    n = src.count(anchor)
    print('      anchor occurrences  : %d (1 required)' % n)
    if n != 1:
        fail('A1 anchor occurs %d times, expected 1' % n)
        return False
    bad = 'wire tx_full  = (tx_cnt >= %s);' % PROBE_TEXT
    dst = os.path.join(work, 'probe.v')
    open(dst, 'w').write(src.replace(anchor, bad, 1))
    changed = open(dst).read() != src
    c = compile_uart(dst, work)
    diag = (c.stdout + c.stderr).strip().splitlines()
    print('      probe text          : %s' % bad)
    print('      file changed        : %s (True required)' % changed)
    print('      iverilog returncode : %d (non-zero required)' % c.returncode)
    print('      first diagnostic    : %s' % (diag[0] if diag else '(none)'))
    if not changed:
        fail('A1 probe did not change the file -- the no-op guard would catch it')
    if c.returncode == 0:
        fail('A1 probe COMPILED -- it is not a compile-error probe at all')
    else:
        print('      OK -- it passes every existing no-op guard and reaches the')
        print('      scorer, which is exactly the path under audit.')
    shutil.rmtree(work, ignore_errors=True)
    print()
    return c.returncode != 0 and changed


# ---------------------------------------------------------------------------
# Runner A -- defect is committed; no probe needed.
# ---------------------------------------------------------------------------
def audit_a():
    rule()
    print('RUNNER A  %s' % RUNNER_A)
    rule()
    print('  Probe: NONE NEEDED.  Its committed M7 sed emits %s, so the defect'
          % PROBE_TEXT)
    print('  reproduces live from the unmodified repository.  2026-10-22')
    print('  established this by reading the script; this establishes it by')
    print('  running it.')
    print('  A3 declared expectation: the M7 row reads "got DETECT".')
    print()
    r = subprocess.run(['bash', os.path.join(ROOT, RUNNER_A)],
                       capture_output=True, text=True, cwd=ROOT)
    out = r.stdout + r.stderr
    lines = out.splitlines()
    m7 = ''
    for i, ln in enumerate(lines):
        if ln.strip().startswith('M7 '):
            m7 = '\n'.join(lines[i:i + 2])
            break
    print('  the M7 row, as the committed runner prints it:')
    for ln in m7.splitlines():
        print('      %s' % ln.strip())
    det = re.search(r'detected\s+:\s+(\d+)', out)
    pred = re.search(r'verdict as predicted\s+:\s+(\d+)\s*/\s*(\d+)', out)
    sur = re.search(r'surprises\s+:\s+(\d+)', out)
    ndet = int(det.group(1)) if det else -1
    print('  summary: detected=%s  as-predicted=%s/%s  surprises=%s  exit=%d'
          % (ndet, pred.group(1) if pred else '?',
             pred.group(2) if pred else '?',
             sur.group(1) if sur else '?', r.returncode))
    q1 = 'got DETECT' in m7
    print()
    print('  Q1 non-compiling mutant scores as DETECTED?  %s'
          % ('YES -- DEFECTIVE' if q1 else 'no'))
    print('  Q2 exit status reflects it?                  %s'
          % ('NO -- exits %d' % r.returncode if r.returncode == 0 else 'yes'))
    print('  A2 negative control: %d rows detected in all (>=2 required,'
          % ndet)
    print('     so the compiling mutants were not taken down with the probe)')
    if ndet < 2:
        fail('A2 runner A detected %d rows -- the run is broken, not the scorer'
             % ndet)
    if not q1:
        fail('A3 runner A did not print "got DETECT" for M7 -- expectation stale')
    print()
    return dict(q1=q1, exit=r.returncode, false_pass=(r.returncode == 0))


# ---------------------------------------------------------------------------
# Runner B -- copy; rewrite T3's replacement so it emits the probe text.
# ---------------------------------------------------------------------------
def audit_b():
    rule()
    print('RUNNER B  %s' % RUNNER_B)
    rule()
    print("  Probe: T3's sed replacement is rewritten so that it still CHANGES")
    print('  the file but emits %s.  T1, T2 and T4 are untouched and are the'
          % PROBE_TEXT)
    print('  negative control.  The committed runner is not edited: the copy')
    print('  sits at the same depth below the repo root so its own')
    print('  $(dirname $0)/../.. still resolves.')
    print('  A3 declared expectation: T3\'s matrix cells read COMPILE_ERROR.')
    print()
    src = open(os.path.join(ROOT, RUNNER_B)).read()
    old = ('row T3 "STATUS decode: tx_empty one entry EARLY" \\\n'
           '    "s/rx_avail, rx_full, tx_empty, tx_full};'
           "/rx_avail, rx_full, (tx_cnt <= 4'd1), tx_full};/\"")
    if src.count(old) != 1:
        fail('runner B T3 anchor occurs %d times, expected 1' % src.count(old))
        return None
    # Single-quoted in the copy, with a doubled backslash, so sed emits the
    # four characters \x27 rather than interpreting them as a hex escape.
    new = ('row T3 "PROBE: replacement text is not Verilog" \\\n'
           "    's/rx_avail, rx_full, tx_empty, tx_full};"
           "/rx_avail, rx_full, 4\\\\x27d1, tx_full};/'")
    pdir = os.path.join(ROOT, 'examples', '_ce_probe')
    os.makedirs(pdir, exist_ok=True)
    pth = os.path.join(pdir, 'probe_b.sh')
    open(pth, 'w').write(src.replace(old, new, 1))
    r = subprocess.run(['bash', pth], capture_output=True, text=True, cwd=ROOT)
    out = r.stdout + r.stderr
    shutil.rmtree(pdir, ignore_errors=True)
    print('  the detection matrix and final verdict, as the runner prints them:')
    for ln in out.splitlines():
        s = ln.strip()
        if re.match(r'^T[1-4]\s', s) and 'escaped at' not in s:
            print('      %s' % s)
        elif s.startswith('RESULT:'):
            print('      %s' % s)
    t3 = [l.strip() for l in out.splitlines() if re.match(r'^\s*T3\s', l)]
    t3row = t3[0] if t3 else ''
    shown = 'COMPILE_ERROR' in t3row
    q1 = bool(re.search(r'\b[1-4]/4\b', t3row))
    passed = 'RESULT: PASS' in out
    others = re.findall(r'^T[124]\s.*?(\d/4)', '\n'.join(
        l.strip() for l in out.splitlines()), re.M)
    print()
    print('  Q1 non-compiling mutant scores as DETECTED?  %s'
          % ('YES -- DEFECTIVE' if q1
             else 'no -- reported as COMPILE_ERROR' if shown else 'unclear'))
    print('  Q2 exit status reflects it?                  %s'
          % ('NO -- prints "RESULT: PASS" and exits 0' if passed and
             r.returncode == 0 else 'yes -- exit %d' % r.returncode))
    print('  A2 negative control: T1/T2/T4 still scored numerically: %s'
          % (', '.join(others) if others else 'NONE'))
    if not others:
        fail('A2 runner B lost its other rows -- the probe broke the run')
    if not shown:
        fail('A3 runner B did not print COMPILE_ERROR for T3')
    if shown and not q1:
        print()
        print('      NOT the fault that was expected.  The row is reported')
        print('      HONESTLY -- COMPILE_ERROR is printed, not folded into a')
        print('      detection count -- and the harness still exits 0 with')
        print('      "RESULT: PASS".  Its G1 baseline arm DOES refuse a compile')
        print('      error (it requires the literal string 0/4); only the')
        print('      mutant arm does not, because `row` never calls note_fail.')
        print('      So an entire mutation suite can fail to build and the')
        print('      regression stays green.')
    print()
    return dict(q1=q1, shown=shown, exit=r.returncode,
                false_pass=(passed and r.returncode == 0))


# ---------------------------------------------------------------------------
# Runner C -- import the committed module, extend MUTANTS in memory.
# ---------------------------------------------------------------------------
def audit_c():
    rule()
    print('RUNNER C  %s' % RUNNER_C)
    rule()
    print('  2026-10-22 guessed this one "may already be correct ... reports it')
    print('  as its own verdict class".  Probe: the committed module is')
    print('  imported and ONE mutant is appended to MUTANTS in memory, whose')
    print('  injection succeeds (sites=1 on the real anchor) and whose product')
    print('  is not Verilog.  Nothing on disk is touched.  M1-M5 are the')
    print('  negative control.')
    print('  A3 declared expectation: the probe row prints verdict=COMPILE_ERROR.')
    print()
    tmp = tempfile.mkdtemp(prefix='ce_c.')
    driver = os.path.join(tmp, 'drive.py')
    open(driver, 'w').write(
        'import importlib.util, sys\n'
        'spec = importlib.util.spec_from_file_location("committed", %r)\n'
        'm = importlib.util.module_from_spec(spec)\n'
        'spec.loader.exec_module(m)\n'
        'm.MUTANTS.append(dict(\n'
        "    name='P1  PROBE: injection succeeds, product is not Verilog',\n"
        '    anchor=m.FULL_ANCHOR,\n'
        "    new='assign full = (((;',\n"
        '    sites=1,\n'
        "    expect='DETECT',\n"
        "    why='the audit probe: this row must not be allowed to score as a"
        " detection'))\n"
        'sys.exit(m.main())\n' % os.path.join(ROOT, RUNNER_C))
    r = subprocess.run([sys.executable, driver], capture_output=True,
                       text=True, cwd=ROOT)
    out = r.stdout + r.stderr
    shutil.rmtree(tmp, ignore_errors=True)
    lines = out.splitlines()
    block = []
    for i, ln in enumerate(lines):
        if ln.startswith('P1 '):
            block = [l for l in lines[i:i + 7] if l.strip()]
            break
    print('  the probe row, as the committed runner scores it:')
    for ln in block:
        print('      %s' % ln.strip())
    summ = [l for l in lines if l.startswith('SUMMARY')]
    print('      %s' % (summ[0] if summ else '(no SUMMARY line)'))
    joined = '\n'.join(block)
    q1 = '-> DETECT' in joined
    named = 'COMPILE_ERROR' in joined
    m = re.search(r'SUMMARY: (\d+) mutants scored, (\d+) detected', out)
    print()
    print('  Q1 non-compiling mutant scores as DETECTED?  %s'
          % ('YES -- DEFECTIVE' if q1 else 'no'))
    print('  Q2 exit status reflects it?                  %s'
          % ('NO -- exits 0' if r.returncode == 0
             else 'yes -- exit %d' % r.returncode))
    print('  verdict class NAMED in the row?              %s'
          % ('yes' if named else 'no'))
    if q1 and named:
        print()
        print('      BOTH, AND THAT IS THE RESULT.  The class is named in the')
        print('      `verdict=` field and then collapsed into a detection one')
        print('      line later by')
        print("          got = 'ESCAPE' if r['verdict'] == 'PASS' else 'DETECT'")
        print('      and counted by the same test in the SUMMARY tally.  The')
        print('      2026-10-22 guess was built on the printed field; the')
        print('      scoring never consulted it.  NAMING A VERDICT CLASS IS NOT')
        print('      SCORING IT -- 2026-10-20\'s "naming is not invoking", one')
        print('      level further down.')
    if m:
        print()
        print('  A2 negative control: %s of %s rows detected (5 of the 6'
              % (m.group(2), m.group(1)))
        print('     are M1-M5, which compile and genuinely fail)')
        if int(m.group(2)) < 5:
            fail('A2 runner C detected %s rows -- the probe broke it' % m.group(2))
    else:
        fail('A2 runner C printed no SUMMARY line')
    if not named:
        fail('A3 runner C did not print COMPILE_ERROR for the probe row')
    print()
    return dict(q1=q1, named=named, exit=r.returncode,
                false_pass=(r.returncode == 0))


# ---------------------------------------------------------------------------
# Runner D -- read only.
# ---------------------------------------------------------------------------
def audit_d():
    rule()
    print('RUNNER D  %s' % RUNNER_D)
    rule()
    print('  2026-10-22 built this one with a G3 guard and described it as "the')
    print('  file must change AND the result must still compile".  That claim')
    print('  had never been exercised against a mutant that fails to compile:')
    print('  the guard was written, not run.')
    print()
    print('  A DEFECT IN THIS AUDIT\'S OWN FIRST READER, recorded rather than')
    print('  quietly fixed.  The first version of this function grepped for')
    print('  "must still compile" and reported the guard ABSENT.  The guard is')
    print('  present at line 258; what is absent is that WORDING -- the comment')
    print('  in the script says "A mutant that does not COMPILE has not been')
    print('  tested by anything".  A reader keyed to a remembered sentence')
    print('  instead of to the mechanism is this repository\'s standing')
    print('  RESOLVE-ON-SPELLING item, committed inside the audit written to')
    print('  catch readers that answer a weaker question than they were asked.')
    print('  It is why this row is now RUN rather than read.')
    print()
    print('  Probe: a copy with MUT_SEDS[0] replaced by the historical')
    print('  malformed sed, so M1 becomes the compile-error probe and M2-M7')
    print('  are the negative control.')
    print('  A3 declared expectation: the M1 row reads "DOES NOT COMPILE".')
    print()
    src = open(os.path.join(ROOT, RUNNER_D)).read()
    old_sed = ("  's/tx_par_bit <= (cfg_parity == PARITY_EVEN) ?  "
               "^tx_fifo\\[tx_rptr\\] :/tx_par_bit <= (cfg_parity == "
               "PARITY_EVEN) ?  ~^tx_fifo[tx_rptr] :/'")
    if src.count(old_sed) != 1:
        fail('runner D MUT_SEDS[0] anchor occurs %d times, expected 1'
             % src.count(old_sed))
        return None
    new_sed = ("  's/wire tx_full  = (tx_cnt == 4.d8);"
               "/wire tx_full  = (tx_cnt >= 4\\\\x27d7);/'")
    pdir = os.path.join(ROOT, 'examples', '_ce_probe')
    os.makedirs(pdir, exist_ok=True)
    pth = os.path.join(pdir, 'probe_d.sh')
    open(pth, 'w').write(src.replace(old_sed, new_sed, 1))
    r = subprocess.run(['bash', pth], capture_output=True, text=True, cwd=ROOT)
    out = r.stdout + r.stderr
    shutil.rmtree(pdir, ignore_errors=True)
    noncompile = 'DOES NOT COMPILE' in out
    badinj = re.search(r'injections that failed\s+:\s+(\d+)', out)
    nbad = int(badinj.group(1)) if badinj else -1
    # Count MUTANT ROWS, not lines carrying an n/5 anywhere: the closing
    # narrative also contains such strings, and an inflated control is a
    # control that cannot fail.
    scored = [l.strip() for l in out.splitlines()
              if re.match(r'^M[1-7]\b', l.strip())
              and re.search(r'\b[0-5]/5\b', l)]
    print('  what the runner printed for the probe row:')
    for ln in out.splitlines():
        if 'DOES NOT COMPILE' in ln:
            print('      %s' % ln.strip()[:98])
        elif 'syntax error' in ln and 'm7_committed' not in ln:
            print('      %s' % ln.strip()[:98])
    print('      (the runner also compiles an m7_committed.v of its own at the')
    print('       end as a demonstration; that diagnostic is not the probe\'s')
    print('       and is filtered out here)')
    print('  summary line: injections that failed = %s' % nbad)
    print('  exit code    : %d' % r.returncode)
    print()
    print('  Q1 non-compiling mutant scores as DETECTED?  %s'
          % ('YES -- DEFECTIVE' if not noncompile
             else 'no -- refused by G3, exactly as claimed'))
    print('  Q2 exit status reflects it?                  %s'
          % ('NO -- reports %d failed injection(s) and exits 0' % nbad
             if r.returncode == 0 else 'yes -- exit %d' % r.returncode))
    print('  A2 negative control: %d of the 6 non-probe mutant rows still'
          % len(scored))
    print('     scored numerically')
    if not scored:
        fail('A2 runner D lost its other rows -- the probe broke the run')
    if not noncompile:
        fail('A3 runner D did not print "DOES NOT COMPILE" for the probe row')
    if noncompile and nbad >= 1 and r.returncode == 0:
        print()
        print('      THE G3 REPAIR FIXED Q1 AND NOT Q2.  `BADINJ` is')
        print('      incremented, printed in the summary as "injections that')
        print('      failed", and then never consulted again: the script\'s')
        print('      last statement is `rm -rf "$WORK"`, so it exits 0.  The')
        print('      session that DISCOVERED this fault class built a runner')
        print('      that still reports it as a green run.')
    print()
    return dict(q1=(not noncompile), refused=noncompile, nbad=nbad,
                exit=r.returncode, false_pass=(r.returncode == 0))


def main():
    print('=' * 74)
    print('AUDIT -- does a mutant that FAILS TO COMPILE score as DETECTED?')
    print('  the 2026-10-22 ranked-first item: generalise the M7 finding')
    print('  date: %s' % subprocess.run(['date', '-u', '+%F'],
                                        capture_output=True,
                                        text=True).stdout.strip())
    print('=' * 74)
    print()
    if not os.path.isdir(IVL_BIN):
        print('ABORT: Icarus not found at %s -- source tools/setup_iverilog.sh'
              ' (without a pipe) first.' % IVL_BIN)
        return 2
    if not control_a1():
        print('ABORT: the probe is not a compile-error probe, so no row below')
        print('       would mean anything.')
        return 1

    ra, rb, rc, rd = audit_a(), audit_b(), audit_c(), audit_d()

    rule('=')
    print('RESULT TABLE')
    rule('=')
    print()
    hdr = ('runner', 'Q1 scores as', 'Q2 exit reflects', 'verdict')
    print('  %-8s %-24s %-20s %s' % hdr)
    print('  %-8s %-24s %-20s %s' % tuple('-' * len(h) for h in hdr))

    def row(tag, q1, shown, false_pass, verdict):
        a = 'DETECT' if q1 else ('refused' if shown else '-')
        b = 'no' if false_pass else 'yes'
        print('  %-8s %-24s %-20s %s' % (tag, a, b, verdict))

    row('A  sh', ra['q1'], False, ra['false_pass'],
        'DEFECTIVE (false DETECT)' if ra['q1'] else 'clean')
    if rb:
        row('B  sh', rb['q1'], rb['shown'], rb['false_pass'],
            'DEFECTIVE (false DETECT)' if rb['q1'] else
            'DEFECTIVE (false PASS)' if rb['false_pass'] else 'clean')
    row('C  py', rc['q1'], rc['named'], rc['false_pass'],
        'DEFECTIVE (false DETECT)' if rc['q1'] else 'clean')
    if rd:
        row('D  sh', rd['q1'], rd['refused'], rd['false_pass'],
            'DEFECTIVE (false DETECT)' if rd['q1'] else
            'DEFECTIVE (false PASS)' if rd['false_pass'] else 'clean')
    else:
        print('  %-8s %-24s %-20s %s' % ('D  sh', '(probe failed)', '-',
                                         'UNMEASURED'))
    print()
    print('  Q1 SPLITS THE RUNNERS.  A and C fold a compile error into a')
    print('  detection count.  B names it and does not count it.  D refuses it')
    print('  outright, exactly as its G3 claims.')
    print()
    print('  Q2 IS UNANIMOUS, AND IT IS THE RESULT.  NOT ONE of the four')
    print('  runners exits non-zero when a mutant fails to compile.  B prints')
    print('  "RESULT: PASS".  D prints the failed-injection count and then')
    print('  drops it.  A and C count the row as a win.  Under any regression')
    print('  driver that reads exit codes, an entire mutation suite can fail to')
    print('  build and the run stays green in all four.')
    print()
    print('  A single-question audit would have cleared B and D and found two')
    print('  of the four faults.  The question 2026-10-22 asked -- "does it')
    print('  score as DETECT?" -- is narrower than the exposure, which is the')
    print('  same shape as the fault it was asking about.')
    print()
    if FAILURES:
        print('CONTROLS: %d FAILED' % len(FAILURES))
        for f in FAILURES:
            print('   - %s' % f)
        rule('=')
        return 1
    print('CONTROLS: A1 the probe changes the file and does not compile;')
    print('          A2 every runner kept its compiling rows;')
    print('          A3 every declared expectation string was found.')
    rule('=')
    return 0


if __name__ == '__main__':
    sys.exit(main())
