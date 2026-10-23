#!/usr/bin/env python3
"""
examples/phase1_mutation/run_mutation_tests.py

Mutation-tests the Phase 1 milestone FIFO bench
(examples/phase1_milestone/sync_fifo_directed_tb.v).

WHY THIS EXISTS.  The 2026-10-12 DUT-signal census ranked this first among
its unrun rows:

    "that bench predicts full/empty from its own ref_model, which is the
     right pattern, and the mutant of exactly the shape demonstrated twice
     this week has never been run against it.  A PREDICTED row is a
     DECLARATION until a mutant tests it."

The shape is "a status flag asserts one entry early".  It escaped the
uvm-python UART bench (2026-10-11) and the Verilog UART bench (2026-10-12),
in both cases because the bench read the DUT's own flag to decide whether
its own reference model should be updated, so an early flag corrupted the
DUT's gating and the reference model identically.

This bench has BOTH patterns in the same task.  `check_flags()` compares
`full` against `ref_model.size() == DEPTH` -- a genuine prediction.  But
`do_push()` opens with

    was_full = full;                       // read from the DUT
    ...
    if (!was_full) ref_model.push_back(...);

-- the trusted read, verbatim, three lines above the prediction that is
supposed to make it safe.  The census recorded the file as PREDICTED.  This
script asks whether the prediction actually covers the trusted read, and
answers it with mutants rather than with the argument above.

THREE THINGS THIS SCRIPT DOES DIFFERENTLY FROM THE EXISTING RUNNERS.

(1) EXPECTED_SITES INJECTION GUARD, not `cmp -s`.  The 2026-10-07 audit named
    four runners that guard injection with "did the file change at all".
    That guard passes when a sed intended to hit one site hits three, and
    2026-10-12 added a fifth row with the same guard.  Here every mutant
    declares the number of sites it expects, the anchor is an exact string,
    and a count that is not the declared one aborts the row as
    INJECTION_FAILED rather than scoring it.  One row of that debt, paid.

(2) THE VERDICT IS READ FROM THE BENCH'S OWN CHECKER, and the weaker
    criteria are read SEPARATELY and reported beside it.  2026-10-09:
    a false DETECTED is as bad as a missed defect.  "The transcript
    differs" is not detection here, and this run found a sharper reason
    than the one it was written to illustrate.

    THE FIRST DRAFT'S NEUTRALITY PASS FAILED, on an identity injection,
    against a file whose only difference was its NAME.  Icarus prints
    `$error` as

        ERROR: base.v:89: sync_fifo: wr_en asserted while full=1 ...

    -- the SOURCE FILE AND LINE NUMBER are in the transcript.  So a
    transcript-diff criterion on this bench reports DETECTED for a mutant
    that merely changed the file name, and for any mutant that shifts a
    line number without changing behaviour.  M1 below inserts two lines
    above line 89 and would score DETECTED on that basis alone, before the
    simulation does anything.  This is not a hypothetical false DETECTED;
    it is one that fired on the first run of this script.

    The repair is both halves: every variant is written to the SAME path,
    and the comparison is made twice --

        verdict      the bench's own PASS/FAIL line        (the real one)
        errors       the bench's own error counter
        checks       how many checks the bench reached
        dut_errors   how many $error lines the DUT printed
        differs_raw  transcript differs byte-for-byte      (contaminated)
        differs_norm the same with `dut.v:NNN:` collapsed  (decontaminated)

    -- and the GAP between differs_raw and differs_norm is reported, because
    that gap is the size of the contamination.  2026-09-19/09-20: the
    subsystem reporting the verdict is not the one doing the checking.

(3) A NEUTRALITY PASS THAT CAN FAIL.  G0 injects the anchor onto itself --
    a real write through the real injection path, changing nothing -- and
    requires the transcript to be BYTE-IDENTICAL to baseline.  An identity
    mutant that comes back DETECTED means the harness is the perturbation.

Usage:  python3 examples/phase1_mutation/run_mutation_tests.py
Run from the repo root.
"""

import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RTL = os.path.join(ROOT, 'examples/phase1_milestone/sync_fifo.v')
TB = os.path.join(ROOT, 'examples/phase1_milestone/sync_fifo_directed_tb.v')

IVL = os.environ.get('IVERILOG_INSTALL_DIR', '/tmp/iverilog_install')
IVL_BIN = os.path.join(IVL, 'usr/bin')
IVL_LIB = os.path.join(IVL, 'usr/lib/x86_64-linux-gnu/ivl')

# ---------------------------------------------------------------------------
# The mutants.  Anchors are exact substrings of sync_fifo.v.
# ---------------------------------------------------------------------------

FULL_ANCHOR = ("assign full  = (wr_ptr[ADDR_WIDTH-1:0] == rd_ptr[ADDR_WIDTH-1:0]) &&\n"
               "                   (wr_ptr[ADDR_WIDTH]     != rd_ptr[ADDR_WIDTH]);")
EMPTY_ANCHOR = "assign empty = (wr_ptr == rd_ptr);"
RDDATA_ANCHOR = "assign rd_data = mem[rd_ptr[ADDR_WIDTH-1:0]];"

MUTANTS = [
    dict(
        name='M1  full asserts ONE ENTRY EARLY (occupancy 7 of 8)',
        anchor=FULL_ANCHOR,
        new=("logic [ADDR_WIDTH:0] wr_ptr_early;\n"
             "    assign wr_ptr_early = wr_ptr + 1'b1;\n"
             "    assign full  = (wr_ptr_early[ADDR_WIDTH-1:0] == rd_ptr[ADDR_WIDTH-1:0]) &&\n"
             "                   (wr_ptr_early[ADDR_WIDTH]     != rd_ptr[ADDR_WIDTH]);"),
        sites=1,
        expect='DETECT',
        why=('THE CENSUS ROW.  Exactly the shape that escaped the uvm-python bench '
             '(2026-10-11) and the Verilog UART bench (2026-10-12).  The design\'s own '
             'wrap-bit technique is preserved and wr_ptr is substituted by wr_ptr+1, so '
             'the flag is wrong by exactly one entry and by nothing else.'),
    ),
    dict(
        name='M2  full NEVER asserts',
        anchor=FULL_ANCHOR,
        new="assign full  = 1'b0;",
        sites=1,
        expect='DETECT',
        why=('the other direction of the same flag.  Included because the trusted read '
             '`was_full = full` fails OPEN here: the bench believes every push landed.'),
    ),
    dict(
        name='M3  empty asserts ONE ENTRY EARLY (occupancy 1 reads as empty)',
        anchor=EMPTY_ANCHOR,
        new="assign empty = (wr_ptr == rd_ptr) || (wr_ptr == rd_ptr + 1'b1);",
        sites=1,
        expect='DETECT',
        why=('the read-side twin.  `do_pop` reads `was_empty = empty` and gates BOTH the '
             'rd_data check and the ref_model pop on it, so an early empty silently '
             'disables the data comparison as well as desyncing the model.'),
    ),
    dict(
        name='M4  the wrap bit is dropped from full (full == empty)',
        anchor=FULL_ANCHOR,
        new="assign full  = (wr_ptr[ADDR_WIDTH-1:0] == rd_ptr[ADDR_WIDTH-1:0]);",
        sites=1,
        expect='DETECT',
        why=('the classic FIFO bug this module\'s header says the extra pointer bit '
             'exists to prevent.  An empty FIFO reads as full.'),
    ),
    dict(
        name='M5  rd_data returns the entry AFTER the front',
        anchor=RDDATA_ANCHOR,
        new="assign rd_data = mem[rd_ptr[ADDR_WIDTH-1:0] + 1'b1];",
        sites=1,
        expect='DETECT',
        why=('a pure data-path mutant with no flag involvement -- the control row for '
             'M1-M4, since it is the one the ref_model data comparison must catch on '
             'its own terms.'),
    ),
]

# ---------------------------------------------------------------------------


def inject(src_text, anchor, new, expected_sites):
    """Return (text, actual_sites).  Never silently partial."""
    n = src_text.count(anchor)
    if n != expected_sites:
        return None, n
    return src_text.replace(anchor, new, expected_sites), n


def run(rtl_path, workdir):
    sim = os.path.join(workdir, 'sim')
    c = subprocess.run([os.path.join(IVL_BIN, 'iverilog'), '-B', IVL_LIB,
                        '-g2012', '-o', sim, rtl_path, TB],
                       capture_output=True, text=True, cwd=workdir)
    if c.returncode != 0:
        return dict(compile_ok=False, out=c.stdout + c.stderr)
    # 15 s, and a HANG IS A RESULT, not a budget problem.  M3 below makes
    # the bench's `while (ref_model.size() > 0) do_pop(...)` loop forever:
    # an `empty` that asserts early stops the reference model draining, so
    # the testbench never terminates.  That is the suite failing to complete,
    # which is a detection -- but it has to be NAMED as a timeout rather than
    # silently read as "no FAIL line was printed, therefore PASS".
    r = subprocess.run(['timeout', '15', os.path.join(IVL_BIN, 'vvp'),
                        '-M', IVL_LIB, sim],
                       capture_output=True, text=True, cwd=workdir)
    timed_out = (r.returncode == 124)
    try:
        os.remove(os.path.join(workdir, 'sync_fifo_wave.vcd'))
    except OSError:
        pass
    return dict(compile_ok=True, out=r.stdout + r.stderr, timed_out=timed_out)


LINENO = re.compile(r'(dut\.v):\d+:')


def normalise(text):
    """Collapse the source line numbers Icarus embeds in every $error line.

    Everything else is left alone.  This is the ONLY normalisation applied,
    and it exists because the line number is a property of the injected
    file's layout, not of the DUT's behaviour.
    """
    return LINENO.sub(r'\1:L:', text)


def read(res):
    """Four SEPARATE readings of one run.  They are not combined here."""
    if not res['compile_ok']:
        return dict(verdict='COMPILE_ERROR', errors=None, dut_errors=0,
                    checks=None, out=res['out'])
    o = res['out']
    if res.get('timed_out'):
        m = re.search(r'Total checks = (\d+), errors = (\d+)', o)
        return dict(verdict='TIMEOUT', errors=None, dut_errors=0,
                    checks=None, out='<<TIMEOUT after 15 s>>')
    m = re.search(r'Total checks = (\d+), errors = (\d+)', o)
    checks = int(m.group(1)) if m else None
    errors = int(m.group(2)) if m else None
    if 'PASS: sync_fifo matched' in o:
        verdict = 'PASS'
    elif 'FAIL: sync_fifo had' in o:
        verdict = 'FAIL'
    else:
        verdict = 'NO_VERDICT'
    dut_errors = len(re.findall(r'sync_fifo: (?:wr_en|rd_en) asserted', o))
    return dict(verdict=verdict, errors=errors, dut_errors=dut_errors,
                checks=checks, out=o)


def main():
    print('=' * 74)
    print('MUTATION TEST -- examples/phase1_milestone/sync_fifo_directed_tb.v')
    print('the 2026-10-12 census\'s first-ranked unrun row')
    print('=' * 74)
    print()

    if not os.path.isdir(IVL_BIN):
        print('ABORT: Icarus not found at %s -- source tools/setup_iverilog.sh '
              '(without a pipe) first.' % IVL_BIN)
        return 2

    work = tempfile.mkdtemp(prefix='fifo_mut.')
    src = open(RTL).read()

    # -- G1 baseline ------------------------------------------------------
    # EVERY variant is written to this one path, so the file name cannot
    # enter the comparison.  (First draft used base.v / neutral.v / mut.v and
    # its neutrality pass failed on the file name alone.)
    DUT = os.path.join(work, 'dut.v')
    open(DUT, 'w').write(src)
    base = read(run(DUT, work))
    print('G1  baseline on unmodified RTL')
    print('      verdict=%s  checks=%s  errors=%s  dut $error lines=%d'
          % (base['verdict'], base['checks'], base['errors'], base['dut_errors']))
    if base['verdict'] != 'PASS':
        print('    ABORT -- a baseline that does not pass makes every row meaningless.')
        return 1
    print('      (the 2 $error lines are Tests 3 and 5, the DELIBERATE protocol')
    print('       violations.  They are in the PASSING transcript, which is why')
    print('       "the transcript differs" cannot be the detection criterion.)')
    print()

    # -- G0 neutrality: inject the anchor onto itself ---------------------
    print('G0  neutrality pass: the anchor injected onto ITSELF')
    neu_text, n = inject(src, FULL_ANCHOR, FULL_ANCHOR, 1)
    open(DUT, 'w').write(neu_text)
    neu = read(run(DUT, work))
    byte_same = (neu['out'] == base['out'])
    print('      a real write through the real injection path, changing nothing.')
    print('      transcript byte-identical to baseline: %s' % byte_same)
    print('      verdict=%s' % neu['verdict'])
    if not (byte_same and neu['verdict'] == 'PASS'):
        print('    ABORT -- the harness is the perturbation; no row below means anything.')
        return 1
    print()

    # -- G0b: a COSMETIC edit, which must look like a detection to the
    #         weak criterion and like nothing at all to the bench ---------
    print('G0b positive control for the false DETECTED: a COSMETIC edit')
    cos_text, _ = inject(src, FULL_ANCHOR,
                         '// cosmetic: two inserted lines, no behaviour\n'
                         '    // (this comment exists to move line 89)\n'
                         '    ' + FULL_ANCHOR, 1)
    open(DUT, 'w').write(cos_text)
    cos = read(run(DUT, work))
    cos_raw = (cos['out'] != base['out'])
    cos_norm = (normalise(cos['out']) != normalise(base['out']))
    print('      two comment lines inserted above the `full` assignment.')
    print('      verdict=%s  errors=%s  differs_raw=%s  differs_norm=%s'
          % (cos['verdict'], cos['errors'], cos_raw, cos_norm))
    ok = (cos['verdict'] == 'PASS' and cos_raw and not cos_norm)
    if ok:
        print('      ==> A TRANSCRIPT-DIFF CRITERION SCORES THIS AS DETECTED.')
        print('          The bench\'s own checker scores it as PASS, correctly,')
        print('          and the normalised diff agrees with the bench.  This is')
        print('          the false DETECTED of 2026-10-09, demonstrated rather')
        print('          than argued, on a DUT whose $error lines carry their own')
        print('          source line numbers into the transcript.')
    else:
        print('      ==> CONTROL DID NOT FIRE (raw=%s norm=%s verdict=%s).'
              % (cos_raw, cos_norm, cos['verdict']))
        print('          Without it the noise claim below is unsupported.')
    print()

    # -- the mutants ------------------------------------------------------
    rows = []
    for mut in MUTANTS:
        text, actual = inject(src, mut['anchor'], mut['new'], mut['sites'])
        print(mut['name'])
        if text is None:
            print('    INJECTION FAILED -- anchor matched %d site(s), declared %d.'
                  % (actual, mut['sites']))
            print('    NOT SCORED.  (With a `cmp -s` guard this row would have been')
            print('    scored as an escape against UNMODIFIED RTL.)')
            rows.append((mut, None, None))
            print()
            continue
        open(DUT, 'w').write(text)
        r = read(run(DUT, work))
        # G3 (2026-10-23).  A mutant whose edit APPLIED but whose result is
        # not Verilog has not been tested by anything, so it is an injection
        # failure and never a detection.  It joins the sed-matched-nothing
        # class above rather than getting a class of its own, because the two
        # are the same fault: the file was changed and the change was never a
        # program.  Before this guard the row scored DETECT -- the verdict
        # class was NAMED in the printed `verdict=` field below and then
        # collapsed one line later by
        #     got = 'ESCAPE' if r['verdict'] == 'PASS' else 'DETECT'
        # with the SUMMARY tally using the same test.  Naming a verdict class
        # is not scoring it.  Measured on 2026-10-23 with an injected probe:
        # the row read "-> DETECT, as predicted" and the run exited 0.
        if r['verdict'] == 'COMPILE_ERROR':
            print('    sites injected: %d (declared %d)' % (actual, mut['sites']))
            print('    INJECTION FAILED -- the edit applied but the result does')
            print('    not compile, so nothing was tested.  NOT SCORED, and')
            print('    never a detection (G3).')
            for ln in r['out'].strip().splitlines()[:2]:
                print('      %s' % ln.strip())
            rows.append((mut, None, None))
            print()
            continue
        differs = (r['out'] != base['out'])
        differs_norm = (normalise(r['out']) != normalise(base['out']))
        got = 'ESCAPE' if r['verdict'] == 'PASS' else 'DETECT'
        mark = 'as predicted' if got == mut['expect'] else \
               'SURPRISE (predicted %s)' % mut['expect']
        print('    sites injected: %d (declared %d)' % (actual, mut['sites']))
        print('    verdict=%-6s  errors=%-5s  checks=%-5s  dut $error=%d'
              % (r['verdict'], r['errors'], r['checks'], r['dut_errors']))
        print('    differs_raw=%-5s  differs_norm=%-5s%s'
              % (differs, differs_norm,
                 '   <-- raw is line-number noise only' if differs and not differs_norm
                 else ''))
        print('    -> %s, %s' % (got, mark))
        print('    why: %s' % mut['why'])
        if differs and got == 'ESCAPE':
            print('    *** differs_raw=True but the bench says PASS: this row is exactly')
            print('    *** the false DETECTED a transcript-diff criterion would report.')
        print()
        rows.append((mut, r, (differs, differs_norm)))

    # -- the reading that the separation buys -----------------------------
    print('-' * 74)
    print('WHAT THE WEAK CRITERION WOULD HAVE SAID')
    print('-' * 74)
    print()
    print('  %-46s %-8s %-9s %s'
          % ('mutant', 'raw', 'norm', "bench's own verdict"))
    disagree = 0
    noise = 0
    for mut, r, d in rows:
        if r is None:
            continue
        draw, dnorm = d
        real = (r['verdict'] != 'PASS')
        agree = (draw == real)
        if not agree:
            disagree += 1
        if draw and not dnorm:
            noise += 1
        print('  %-46s %-8s %-9s %-6s %s'
              % (mut['name'][:46], draw, dnorm, r['verdict'],
                 '' if agree else '<-- DISAGREE'))
    print()
    print('  rows where the RAW transcript diff and the bench\'s own checker')
    print('  disagree: %d' % disagree)
    print('  rows whose raw diff is PURE LINE-NUMBER NOISE: %d' % noise)
    print('  (0 here because all five mutants genuinely fail.  G0b above is')
    print('   the row that fires: cosmetic edit, raw=%s, norm=%s, verdict=%s.)'
          % (cos_raw, cos_norm, cos['verdict']))
    print()
    print('  And the neutrality pass G0 is the sharpest row of all: an')
    print('  identity injection, byte-identical behaviour, which the first')
    print('  draft of this script scored as a transcript difference because')
    print('  the file was called neutral.v instead of base.v.  A detection')
    print('  criterion that fires on the NAME OF THE FILE is not measuring')
    print('  the DUT.')
    print()

    scored = [(m, r) for m, r, _ in rows if r is not None]
    det = sum(1 for _, r in scored if r['verdict'] != 'PASS')
    esc = len(scored) - det
    pred = sum(1 for m, r in scored
               if ('ESCAPE' if r['verdict'] == 'PASS' else 'DETECT') == m['expect'])
    notrun = len(rows) - len(scored)
    print('=' * 74)
    print('SUMMARY: %d mutants scored, %d detected, %d escaped, %d/%d verdicts '
          'as predicted%s'
          % (len(scored), det, esc, pred, len(scored),
             ', %d NOT SCORED (injection failed)' % notrun if notrun else ''))
    print('=' * 74)
    print('CONTROLS: G1 baseline PASS; G0 identity injection byte-identical;')
    print('          G0b cosmetic edit separates the two criteria: %s'
          % ('FIRED' if ok else 'DID NOT FIRE'))
    print('=' * 74)
    return 0 if (notrun == 0 and pred == len(scored) and ok) else 1


if __name__ == '__main__':
    sys.exit(main())
