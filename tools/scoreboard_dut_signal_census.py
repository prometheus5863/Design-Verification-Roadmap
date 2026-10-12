#!/usr/bin/env python3
"""
tools/scoreboard_dut_signal_census.py

A DUT-SIGNAL CENSUS FOR EVERY CHECKER IN THIS REPOSITORY.

Created 2026-10-12 out of the 2026-10-11 finding, which is this repository's
fourth variation on one theme:

  09-19/09-20  the subsystem reporting the verdict is not the one doing the
               checking
  10-10        a control must not read the thing it controls for
  10-11        and neither may a checker: a scoreboard that takes its
               reference from a DUT output is blind to exactly that output's
               defects.  Mutant M4 -- tx_full asserting one entry early --
               SURVIVED a 5/5 suite because the scoreboard derived push
               acceptance from the DUT's own STATUS.tx_full.

The checkable rule that came out of it:

  > For every DUT signal a checker reads, ask whether the checker could
  > detect that signal being wrong.  If not, predict it independently in the
  > window where that is possible, or state the blind spot.

This file mechanises the *census* half of that rule.  For every checker in
the repository it lists each DUT-observed quantity the checker reads, the
ROLE that read plays, and the MUTANT that would prove the signal is checked
rather than trusted.

WHAT THIS TOOL IS, AND WHAT IT IS NOT.  The rows are DECLARED by a reviewer.
A tool that tried to infer the role of a read by static dataflow would be
this repository's class (v) failure -- a procedure that certifies itself --
so no role here is inferred.  What is mechanical is the set of CONTROLS that
can FALSIFY the declaration:

  C1  STALENESS.  Every row carries an `evidence` substring that must still
      appear verbatim in the row's file.  A row whose evidence has been
      edited away is reported STALE and fails the census.
  C2  COMPLETENESS.  For each censused file, every DUT-observed read is
      extracted mechanically -- STATUS bit indices `st[..]` for the Verilog
      benches, `dut.<name>` for the cocotb ones -- and each must be covered
      by a row.  An extracted read with no row is an OMISSION and fails the
      census.  This is the direction that makes it a census rather than a
      list: it is the direction that can grow.
  C3  ALLOWLIST SIZE.  C2 needs an allowlist for TB-driven stimulus pins
      (`clk`, `psel`, `pwdata`, ...), which are written by the bench and are
      not DUT outputs.  An allowlist that swallows everything would make C2
      vacuous, so every allowlisted name carries a reason and the count is
      reported next to the covered count.
  C4  DISCRIMINATING POWER.  The census must contain at least one TRUSTED
      row.  A census in which every row is already PREDICTED has no power to
      find anything, and reporting it as clean would be the 2026-10-08
      failure: a control that cannot fail is not a control.

ROLES
  PREDICTED     the checker computes the expected value from its own model and
                compares.  A defect in the signal is observable.
  TRUSTED       the checker uses the DUT's value as its reference.  A defect
                in the signal corrupts the reference identically and is NOT
                observable.  This is the defect class.
  OBSERVED_ONLY sampled for coverage or logging; no reference role, so there
                is nothing for a defect to corrupt -- but also no check.
  SYNC_ONLY     read to decide WHEN to sample, not WHAT to expect.  A defect
                shows up as a timing failure rather than as a silent
                agreement, which is a weaker exposure than PREDICTED and a
                stronger one than TRUSTED.

Run:  python3 tools/scoreboard_dut_signal_census.py
Exit status is non-zero if any control fails.  Writes nothing; redirect to
tools/scoreboard_dut_signal_census_output.txt to commit a transcript.
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# STATUS bit map, from rtl/uart_controller.v:
#   {1'b0, overrun, parity, frame, rx_avail, rx_full, tx_empty, tx_full}
STATUS_BITS = {
    0: 'STATUS.tx_full',
    1: 'STATUS.tx_empty',
    2: 'STATUS.rx_full',
    3: 'STATUS.rx_avail',
    4: 'STATUS.frame_err',
    5: 'STATUS.parity_err',
    6: 'STATUS.overrun_err',
    7: 'STATUS.reserved',
}

# Pins the BENCH drives are STIMULUS, not DUT outputs: a DUT defect cannot
# reach them, so they are outside this census.  The first draft of this file
# declared them as a hand-written NAME LIST, and C2 immediately reported five
# omissions -- bfm_bad_par, bfm_bad_stop, bfm_bit_ps, bfm_mode, bfm_par --
# because the list had been written from the naming CONVENTION rather than
# from the file, and named bfm_parity/bfm_two_stop/bfm_div, which do not
# exist.  That is the graphene repository's 2026-10-09 rule in this
# repository: a list re-typed from memory measures its own transcription.
#
# The repair is not a corrected list.  A pin is bench-driven if the file
# ASSIGNS it, which the file itself states:
#
#     dut.<name>.value = ...      or    dut.<name>.setimmediatevalue(...)
#
# so the allowlist is now DERIVED and cannot be inflated by hand.  Two names
# stay declared because they are assigned in a helper this extractor does not
# follow.
DECLARED_DRIVEN = {
    'clk': 'bench-generated clock, assigned in a cocotb Clock coroutine',
    'rst_n': 'bench-driven reset, assigned in a shared _reset helper',
}


def driven_pins(text):
    """Names this file assigns, i.e. drives.  Derived, not declared."""
    out = set(DECLARED_DRIVEN)
    for m in re.finditer(r'\bdut\.([A-Za-z_]\w*)\.(?:value\s*=|'
                         r'setimmediatevalue)', text):
        out.add(m.group(1))
    return out


# ---------------------------------------------------------------------------
# THE CENSUS.  Declared, not inferred.
#   file, checker, quantity, role, mutant, status, evidence
# ---------------------------------------------------------------------------
CENSUS = [
    # --- the repaired case: the 2026-10-11 finding, proved by a live run ----
    dict(file='examples/phase6_uvm_crv_uart/uart_uvm_crv_tb.py',
         checker='UartScoreboard.write_bus',
         quantity='STATUS.tx_full (prdata[0])',
         role='PREDICTED',
         mutant='M4 -- tx_full asserts one entry early (tx_cnt >= 7)',
         status='PROVED BY RUN 2026-10-11: M4 SURVIVED before the repair and '
                'is DETECTED after it, naming the occupancy',
         escape_demonstrated=True,
         evidence='tx_full as a CHECKED OUTPUT'),
    dict(file='examples/phase6_uvm_crv_uart/uart_uvm_crv_tb.py',
         checker='UartScoreboard.write_bus',
         quantity='RX_DATA read value',
         role='PREDICTED',
         mutant='M2 -- RX data bit inverted at the mid-bit sample',
         status='PROVED BY RUN 2026-10-11 (M2 DETECTED)',
         evidence='self.q.append'),
    dict(file='examples/phase6_uvm_crv_uart/uart_uvm_crv_tb.py',
         checker='UartDriver.run_burst',
         quantity='STATUS error bits st[6:4] = frame_err, parity_err, '
                  'overrun_err',
         role='PREDICTED',
         mutant='M1 -- TX parity polarity swapped',
         status='PROVED BY RUN 2026-10-11: M1 is caught by this check and by '
                'NO data comparison at all, the byte still arriving correctly '
                'in loopback',
         evidence='clear sticky bits'),

    # --- the open case: the same hole, in the Verilog bench -----------------
    dict(file='examples/phase6_crv_uart/uart_crv_cov_tb.v',
         checker='run_burst push loop',
         quantity='STATUS.tx_full (st[0])',
         role='PREDICTED',
         mutant='M7 -- tx_full asserts one entry early (tx_cnt >= 7)',
         status='PROVED BY RUN 2026-10-12, in both directions.  This row was '
                'TRUSTED when the census was written: the driver read st[0] '
                'and enqueued on that basis, so an early tx_full corrupted '
                'the DUT gating and the reference model identically.  M7 '
                'ESCAPED on seeds 1/3/5 (8203/7926/7225 checks, all passing) '
                'and is DETECTED on all three after the repair, the first '
                'failing check naming the occupancy.  Repaired the same day '
                'the census found it, with an exact output-neutrality pass '
                'over 8 (seed, steer) combinations.',
         escape_demonstrated=True,
         evidence='tx_full agrees with predicted occupancy'),
    dict(file='examples/phase6_crv_uart/uart_crv_cov_tb.v',
         checker='sample_txq',
         quantity='STATUS.tx_empty (st[1]) and STATUS.tx_full (st[0])',
         role='OBSERVED_ONLY',
         mutant='M4 -- tx_cnt never increments on a lone push',
         status='PROVED BY RUN 2026-09-24: M4 is DETECTED here, but by the '
                'COVERAGE CRITERION (cp_txq.full becomes unreachable) and not '
                'by any data check -- a different exposure from a comparison',
         evidence='if      (s[1]) cov_txq[0]'),
    dict(file='examples/phase6_crv_uart/uart_crv_cov_tb.v',
         checker='run_burst status checks',
         quantity='STATUS error bits st[6:4] = frame_err, parity_err, '
                  'overrun_err',
         role='PREDICTED',
         mutant='M1 -- TX parity polarity swapped',
         status='PROVED BY RUN 2026-09-24 (M1 DETECTED)',
         evidence='push-phase status error bits clear'),
    dict(file='examples/phase6_crv_uart/uart_crv_cov_tb.v',
         checker='run_burst drain loop',
         quantity='RX_DATA read value (rd_data)',
         role='PREDICTED',
         mutant='M2 -- RX data bit inverted at the mid-bit sample',
         status='PROVED BY RUN 2026-09-24 (M2 DETECTED)',
         evidence='reg [7:0] expq [0:63]'),

    dict(file='examples/phase6_crv_uart/uart_crv_cov_tb.v',
         checker='run_burst drain loop',
         quantity='STATUS.rx_avail (st[3])',
         role='SYNC_ONLY',
         mutant='rx_avail asserting before the stop bit is sampled',
         status='FOUND BY THIS CENSUS 2026-10-12 -- the drain loop reads '
                'st[3] to decide when to read RX_DATA and no row named it. '
                'SYNC_ONLY rather than TRUSTED: an rx_avail that never '
                'asserts trips the per-burst watchdog, and one that asserts '
                'early reads a byte the receiver has not finished, which the '
                'data comparison catches. So the exposure exists, but it is '
                'indirect and no mutant has ever been run for it.',
         evidence='if (st[3]) begin'),

    # --- the pattern done right from the start ------------------------------
    dict(file='examples/phase1_milestone/sync_fifo_directed_tb.v',
         checker='check_flags',
         quantity='empty',
         role='PREDICTED',
         mutant='empty stuck at 0 after the first pop',
         status='PREDICTED BY CONSTRUCTION from ref_model.size(); the mutant '
                'has never been run',
         evidence='exp_empty = (ref_model.size() == 0)'),
    dict(file='examples/phase1_milestone/sync_fifo_directed_tb.v',
         checker='check_flags',
         quantity='full',
         role='PREDICTED',
         mutant='full asserting one entry early (count >= DEPTH-1)',
         status='PREDICTED BY CONSTRUCTION from ref_model.size(); the mutant '
                'has never been run -- and it is the exact shape of the '
                'defect that survived in the UART scoreboard, which is why '
                'this row is worth having even though it looks clean',
         evidence='exp_full  = (ref_model.size() == DEPTH)'),

    dict(file='examples/phase1_milestone/sync_fifo_directed_tb.v',
         checker='directed read/pop checks',
         quantity='rd_data',
         role='PREDICTED',
         mutant='rd_data driven from tx_wptr instead of tx_rptr',
         status='FOUND BY THIS CENSUS 2026-10-12 -- the bench compares '
                'rd_data against exp_data and exp_pop_data taken from its '
                'own ref_model, which is the right pattern, and no row named '
                'it. Mutant never run.',
         evidence='if (rd_data !== exp_data) begin'),

    # --- the RAL bench: a mirror is a reference model -----------------------
    dict(file='examples/phase4_ral/uart_ral_tb.py',
         checker='CHECK 4, STATUS at reset',
         quantity='STATUS (whole byte)',
         role='PREDICTED',
         mutant='tx_empty not set at reset',
         status='PREDICTED against the constant STATUS_RESET, which is a '
                'declared literal and not a DUT read; mutant never run',
         evidence='st == STATUS_RESET'),
    dict(file='examples/phase4_ral/uart_ral_tb.py',
         checker='CHECK 1, explicit predictor',
         quantity='CTRL read-back (mirror)',
         role='PREDICTED',
         mutant='CTRL storing pwdata[7:0] instead of pwdata[4:0]',
         status='PREDICTED: the mirror is moved by the predictor from the BUS '
                'WRITE, with auto_predict off, so the expected value does not '
                'come from the DUT; mutant never run',
         evidence='mirrored == 0x1B'),

    # --- the Phase 4 UVM milestone -----------------------------------------
    dict(file='examples/phase4_uvm_milestone/uart_uvm_tb.py',
         checker='RX_DATA scoreboard',
         quantity='prdata on an RX_DATA read',
         role='PREDICTED',
         mutant='M2 -- RX data bit inverted at the mid-bit sample',
         status='PREDICTED against the frame the BFM was told to send; mutant '
                'run in phase6 and not here',
         evidence='item.rdata == exp'),
    dict(file='examples/phase4_uvm_milestone/uart_uvm_tb.py',
         checker='error-bit checks',
         quantity='prdata STATUS parity/frame bits',
         role='PREDICTED',
         mutant='sticky error bit that never sets',
         status='PREDICTED from the BFM\'s injected defect, so the expected '
                'value is known independently; mutant never run',
         evidence='got_par = bool((item.rdata >> ST_PARITY_ERR) & 1)'),
    dict(file='examples/phase4_uvm_milestone/uart_uvm_tb.py',
         checker='frame-completion wait',
         quantity='bfm_done_cnt',
         role='SYNC_ONLY',
         mutant='bfm_done_cnt increments one bit-time early',
         status='NOT A DUT OUTPUT -- it is TB-side BFM infrastructure, so a '
                'defect in it is a bench bug rather than an escape. Censused '
                'because the read decides WHEN the scoreboard samples: an '
                'early increment samples RX_DATA before the frame lands, '
                'which shows up as a data mismatch and not as a silent '
                'agreement. Mutant never run.',
         evidence='while int(dut.bfm_done_cnt.value) == before'),
]

CENSUSED_FILES = sorted({r['file'] for r in CENSUS})

passed = 0
failed = 0


def check(label, ok, detail=''):
    global passed, failed
    if ok:
        passed += 1
        print('  [PASS] %s' % label)
    else:
        failed += 1
        print('  [FAIL] %s' % label)
    if detail:
        for line in detail.split('\n'):
            print('         %s' % line)


def read(rel):
    with open(os.path.join(ROOT, rel)) as f:
        return f.read()


def extract_reads(rel, text):
    """Mechanical extraction of DUT-observed reads.  Returns a set of
    quantity names, plus the set of allowlisted driven pins actually seen."""
    found = set()
    allowed = set()
    if rel.endswith(('.v', '.sv')):
        # STATUS bit reads in the benches go through `st` / `s` (the task
        # argument), so take both.  Single bits and ranges.
        for var in ('st', 's'):
            for m in re.finditer(r'\b%s\[(\d+)\]' % var, text):
                found.add(STATUS_BITS[int(m.group(1))])
            for m in re.finditer(r'\b%s\[(\d+):(\d+)\]' % var, text):
                hi, lo = int(m.group(1)), int(m.group(2))
                for b in range(lo, hi + 1):
                    found.add(STATUS_BITS[b])
        if re.search(r'\brd_data\b', text):
            found.add('rd_data')
        # the FIFO bench reads flags as bare pins
        for name in ('empty', 'full'):
            if re.search(r'\b%s\s*!==' % name, text):
                found.add(name)
    else:
        driven = driven_pins(text)
        for m in re.finditer(r'\bdut\.([A-Za-z_]\w*)', text):
            name = m.group(1)
            if name in driven:
                allowed.add(name)
            else:
                found.add(name)
        if re.search(r'\bprdata\b', text):
            found.add('prdata')
    return found, allowed


def covered_by_census(rel, quantity):
    """A row covers an extracted quantity when the quantity's name appears in
    the row's declared `quantity` string.  Deliberately a substring test and
    deliberately reported: a row that names several bits covers each."""
    for r in CENSUS:
        if r['file'] != rel:
            continue
        q = r['quantity']
        if quantity in q or quantity.split('.')[-1] in q:
            return r
    return None


def main():
    print('=' * 78)
    print('DUT-SIGNAL CENSUS FOR EVERY CHECKER')
    print('=' * 78)
    print()
    print('  %d rows over %d files.' % (len(CENSUS), len(CENSUSED_FILES)))
    print()
    print('  Rule (2026-10-11): for every DUT signal a checker reads, ask')
    print('  whether the checker could detect that signal being wrong.  If')
    print('  not, predict it independently in the window where that is')
    print('  possible, or state the blind spot.')
    print()

    print('SECTION 1.  THE CENSUS')
    print('-' * 78)
    by_role = {}
    for rel in CENSUSED_FILES:
        print()
        print('  %s' % rel)
        for r in CENSUS:
            if r['file'] != rel:
                continue
            by_role.setdefault(r['role'], []).append(r)
            print('    %-13s %s' % (r['role'], r['quantity']))
            print('      checker : %s' % r['checker'])
            print('      mutant  : %s' % r['mutant'])
            for i, line in enumerate(_wrap(r['status'], 64)):
                print('      %s %s' % ('status  :' if i == 0 else '         ',
                                       line))
    print()
    print('  by role: %s'
          % ', '.join('%s %d' % (k, len(v)) for k, v in sorted(by_role.items())))

    print()
    print('SECTION 2.  C1 -- STALENESS')
    print('-' * 78)
    stale = []
    for r in CENSUS:
        if r['evidence'] not in read(r['file']):
            stale.append(r)
    for r in stale:
        print('   STALE: %s / %s -- evidence %r not found'
              % (r['file'], r['quantity'], r['evidence']))
    check('every row\'s evidence substring still appears verbatim in its file',
          not stale,
          '%d of %d rows checked against the files themselves.  A row whose '
          'evidence has been edited away is a claim about code that no longer '
          'exists, which is how a census becomes decoration.'
          % (len(CENSUS), len(CENSUS)))

    print()
    print('SECTION 3.  C2 -- COMPLETENESS, AND C3 -- ALLOWLIST SIZE')
    print('-' * 78)
    omissions = []
    total_found = 0
    total_allowed = 0
    for rel in CENSUSED_FILES:
        found, allowed = extract_reads(rel, read(rel))
        total_found += len(found)
        total_allowed += len(allowed)
        miss = sorted(q for q in found if covered_by_census(rel, q) is None)
        print('   %-58s reads %2d  allowlisted %2d  uncovered %d'
              % (os.path.basename(rel), len(found), len(allowed), len(miss)))
        for q in miss:
            omissions.append((rel, q))
    for rel, q in omissions:
        print('   OMISSION: %s reads %s with no census row' % (rel, q))
    check('every mechanically extracted DUT-observed read in every censused '
          'file is covered by a row',
          not omissions,
          '%d reads extracted across %d files, %d covered, %d omitted.  This '
          'is the direction that can grow: a new DUT read added to a censused '
          'file fails the census until someone states its role.'
          % (total_found, len(CENSUSED_FILES), total_found - len(omissions),
             len(omissions)))
    check('the driven-pin allowlist is DERIVED from assignment sites rather '
          'than declared, so it cannot be inflated by hand to make C2 pass',
          len(DECLARED_DRIVEN) <= 2 and total_found > 0,
          'only %d names are declared by hand (%s); every other allowlisted '
          'name was found because the file ASSIGNS it.  %d allowlist hits '
          'against %d censused reads.  The first draft declared a name list '
          'instead and got five of the names wrong, which C2 reported as '
          'omissions -- the list had been written from the naming convention '
          'rather than from the file.  An allowlist large enough to swallow '
          'the DUT outputs would make C2 pass on an empty census, which is '
          'the 2026-10-08 failure, and a derived one cannot grow that way.'
          % (len(DECLARED_DRIVEN), ', '.join(sorted(DECLARED_DRIVEN)),
             total_allowed, total_found))

    print()
    print('SECTION 4.  C4 -- DISCRIMINATING POWER')
    print('-' * 78)
    print('  AMENDED 2026-10-12, the same session this control was written,')
    print('  and the amendment is the interesting part.  C4 was first phrased')
    print('  as "the census must contain at least one TRUSTED row", on the')
    print('  2026-10-08 argument that a census reporting itself clean has no')
    print('  power to find anything.  That phrasing BROKE THE MOMENT THE')
    print('  DEFECT WAS FIXED: repairing the one TRUSTED row the census found')
    print('  made the control fail, so as written it REQUIRED A DEFECT TO')
    print('  EXIST.  A control must not demand that the thing it looks for')
    print('  still be there.')
    print()
    print('  The right question is not whether a defect is present now but')
    print('  whether this census has EVER been shown to find one.  So C4 now')
    print('  requires at least one row carrying a DEMONSTRATED ESCAPE: a')
    print('  mutant that was actually run against the pre-repair code and')
    print('  survived it.  That property is permanent, and it is the inverse')
    print("  of 2026-10-08's rule -- a control with no control is useless, and")
    print('  so is one that cannot pass on healthy code.')
    print()
    demo = [r for r in CENSUS if r.get('escape_demonstrated')]
    for r in demo:
        print('   DEMONSTRATED ESCAPE: %s' % r['file'])
        print('       %s, read by %s' % (r['quantity'], r['checker']))
        print('       mutant: %s' % r['mutant'])
    check('at least one row carries a mutant that was RUN against the '
          'pre-repair code and survived it, so this census is known to find '
          'the defect class it was built for',
          len(demo) >= 1,
          '%d rows with a demonstrated escape: %s.  Both are the same defect '
          'shape -- tx_full asserting one entry early against a checker that '
          'read tx_full -- found independently in a uvm-python scoreboard and '
          'in a Verilog driver, which is why the shape rather than the '
          'instance is what this census is organised around.'
          % (len(demo), ', '.join(os.path.basename(r['file']) for r in demo)))
    trusted = [r for r in CENSUS if r['role'] == 'TRUSTED']
    print()
    print('   open TRUSTED rows: %d' % len(trusted))
    for r in trusted:
        print('     %s / %s' % (r['file'], r['quantity']))
    check('and the count of open TRUSTED rows is REPORTED rather than '
          'required to be non-zero, so a clean census is a result and not a '
          'control failure',
          True,
          '%d open TRUSTED rows. Zero is the goal; the census says so '
          'explicitly instead of passing silently, because a clean report and '
          'an unexercised control look identical from outside and the '
          'demonstrated-escape count above is what distinguishes them.'
          % len(trusted))
    proved = [r for r in CENSUS if r['status'].startswith('PROVED BY RUN')]
    never = [r for r in CENSUS if 'never been run' in r['status']
             or 'never run' in r['status']]
    print()
    print('   rows proved by a mutant that was actually run : %d' % len(proved))
    print('   rows whose naming mutant has never been run   : %d' % len(never))
    check('and it reports how many rows are PROVED by a run rather than '
          'argued, because the second number is the honest measure of what '
          'this census knows',
          len(proved) >= 1 and len(never) >= 1,
          '%d proved by run, %d argued but unrun, %d other.  The unrun rows '
          'are not failures -- they are the backlog this census exists to '
          'make visible, and the FIFO bench\'s "full asserting one entry '
          'early" is the most interesting of them because it is the exact '
          'shape of the defect that was demonstrated twice above.'
          % (len(proved), len(never), len(CENSUS) - len(proved) - len(never)))

    print()
    print('=' * 78)
    print('CHECKS: %d passed, %d failed' % (passed, failed))
    print('=' * 78)
    print()
    print('VERDICT')
    print()
    print('  The census stands at %d rows: %s.'
          % (len(CENSUS),
             ', '.join('%d %s' % (len(v), k)
                       for k, v in sorted(by_role.items()))))
    print('  No TRUSTED row is open.  The one the census found on its first')
    print('  run -- the Verilog CRV bench reading STATUS.tx_full to decide')
    print('  whether its own push was accepted -- was repaired the same')
    print('  session, with M7 shown to escape before and to be detected')
    print('  after.  Two rows now carry a demonstrated escape, both of the')
    print('  same shape, found independently in two languages.')
    print()
    print('  What this census does NOT claim:')
    print('    1. That the roles are right.  They are declared by a reviewer;')
    print('       only the controls are mechanical.  A row declared PREDICTED')
    print('       that is really TRUSTED passes every control here, and the')
    print('       only thing that would catch it is running its mutant.')
    print('    2. That the file list is complete.  %d files are censused;'
          % len(CENSUSED_FILES))
    print('       the repository has more checkers than that, and C2 is')
    print('       complete only WITHIN a censused file.  Adding a file can')
    print('       only add rows, never remove them.')
    print('    3. That a PREDICTED row is safe.  It means a defect in that')
    print('       signal is observable by this checker, not that the')
    print('       prediction itself is right.')
    return failed


def _wrap(s, width):
    out, line = [], ''
    for w in s.split():
        if len(line) + len(w) + 1 > width:
            out.append(line)
            line = w
        else:
            line = (line + ' ' + w).strip()
    if line:
        out.append(line)
    return out


if __name__ == '__main__':
    sys.exit(1 if main() else 0)
