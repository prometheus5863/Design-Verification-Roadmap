#!/usr/bin/env python3
"""
tools/harness_file_closure_audit.py

Asks of every Verilog mutation/bench harness in this repository the one
question none of its guards asks: CAN IT COMPILE AT ALL?

WHY THIS EXISTS

2026-10-14 converted examples/phase6_rx_pin_driver/run_mutation_tests.sh to
the declared-sites injection guard and found, before reaching the guard, that
the script does not run.  On 2026-09-27 the RX pin driver was extracted into
bfm/uart_rx_pin_bfm.v and the bench rewritten to instantiate it; that commit
checked both BENCH runners and did not touch this MUTATION runner's compile
line.  Every invocation since died at elaboration with "Unknown module type:
uart_rx_pin_bfm", aborted at its own baseline check and exited 1 -- for
seventeen sessions, through every one of which a report reading "detected 7
escaped 0 voided 0" sat beside it.

The baseline guard worked.  It refused to score rows it could not trust.
Nothing read the exit code, because nothing re-runs the script.

    A SUITE THAT CANNOT RUN IS INDISTINGUISHABLE FROM A SUITE NOBODY RAN.

Every guard added here since 2026-09-30 sits INSIDE a harness and answers "is
this verdict sound".  None answers "did this harness run".  This tool is that
question, asked statically so it costs seconds rather than a simulation.

HOW, AND WHAT IT CANNOT SEE

For each harness script it collects the literal `*.v` paths the script
mentions anywhere -- which is what the 2026-09-27 omission looks like: the
script never names bfm/uart_rx_pin_bfm.v at all -- then, for each testbench
among them, resolves the modules that bench instantiates against a repo-wide
module index and requires every one to be defined in a file the script
mentions.

Two limits, stated rather than papered over:

  * A path built at runtime from a variable the script never writes out as a
    literal is invisible here.  Reported as UNRESOLVED_PATHS, not as a pass.
  * Finding every required module in a mentioned file does NOT prove the
    script passes those files to iverilog in the right invocation.  So the
    static verdict is CONFIRMED by an actual elaboration of the closure with
    the real compiler.  A script can still pass the static check and fail the
    elaboration, and that difference is the interesting output.

The audit is the 2026-10-01 shape: run it as a MEASUREMENT before changing
any harness, and report finding nothing as the negative result it would be.
"""

import os
import re
import atexit
import shutil
import subprocess
import tempfile
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IVL = os.environ.get('IVERILOG_INSTALL_DIR', '/tmp/iverilog_install')
IVL_BIN = os.path.join(IVL, 'usr/bin')
IVL_LIB = os.path.join(IVL, 'usr/lib/x86_64-linux-gnu/ivl')

# Session-private scratch.  See the long note above elaborate().  Created
# lazily at import and removed at exit, so nothing this audit writes can be
# inherited by, or collide with, another session.
SCRATCH = tempfile.mkdtemp(prefix='harness_closure_')
atexit.register(shutil.rmtree, SCRATCH, True)

# Verilog keywords that can follow an identifier in instantiation position.
NOT_A_MODULE = {
    'begin', 'end', 'if', 'else', 'case', 'endcase', 'always', 'assign',
    'initial', 'wire', 'reg', 'integer', 'real', 'input', 'output', 'inout',
    'parameter', 'localparam', 'function', 'endfunction', 'task', 'endtask',
    'generate', 'endgenerate', 'for', 'while', 'repeat', 'forever', 'fork',
    'join', 'posedge', 'negedge', 'or', 'and', 'not', 'nand', 'nor', 'xor',
    'xnor', 'buf', 'module', 'endmodule', 'default', 'signed', 'unsigned',
    'genvar', 'defparam', 'specify', 'endspecify', 'automatic', 'static',
    'logic', 'bit', 'byte', 'int', 'longint', 'shortint', 'void', 'return',
    'break', 'continue', 'typedef', 'enum', 'struct', 'union', 'class',
    'endclass', 'package', 'endpackage', 'import', 'export', 'extern',
    'virtual', 'local', 'protected', 'rand', 'randc', 'constraint', 'do',
    'foreach', 'unique', 'priority', 'wait', 'disable', 'force', 'release',
    'deassign', 'pullup', 'pulldown', 'tri', 'supply0', 'supply1', 'time',
}

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
        print('         %s' % detail)


def strip_comments(text):
    text = re.sub(r'/\*.*?\*/', ' ', text, flags=re.S)
    text = re.sub(r'//[^\n]*', ' ', text)
    return text


def verilog_files():
    out = []
    for base, _dirs, files in os.walk(ROOT):
        if '/.git' in base:
            continue
        for f in files:
            if f.endswith('.v') or f.endswith('.sv'):
                out.append(os.path.relpath(os.path.join(base, f), ROOT))
    return sorted(out)


def module_index(files):
    """module name -> [files that define it]"""
    idx = {}
    for rel in files:
        try:
            with open(os.path.join(ROOT, rel), 'r', encoding='utf-8',
                      errors='replace') as fh:
                txt = strip_comments(fh.read())
        except OSError:
            continue
        for m in re.finditer(r'\bmodule\s+([A-Za-z_]\w*)', txt):
            idx.setdefault(m.group(1), []).append(rel)
    return idx


def instantiated(rel):
    """Module names this file instantiates (names it needs from elsewhere)."""
    with open(os.path.join(ROOT, rel), 'r', encoding='utf-8',
              errors='replace') as fh:
        txt = strip_comments(fh.read())
    defined = set(re.findall(r'\bmodule\s+([A-Za-z_]\w*)', txt))
    need = set()
    # `type inst (`  or  `type #(...) inst (`
    #
    # The [ \t]+ between the type and the instance name is load-bearing, and
    # the first draft had [ \t]* there.  With the star, a Verilog TASK CALL
    # `apb_read(addr, d);` matches by splitting the identifier itself: the
    # type group takes `apb_rea`, the instance group takes `d`, and the audit
    # reported eight to twenty-one nonexistent modules per harness with names
    # one character short of a real task.  The noise was the tell -- a missing
    # module called `whil` is a parser bug, not a missing module -- and the
    # lesson is this repository's own 2026-10-06: a detector can misattribute
    # what it measured.  A module instantiation always has whitespace or a
    # parameter list between the type and the instance name.
    for m in re.finditer(r'^[ \t]*([A-Za-z_]\w*)[ \t]*(#\s*\([^;]*?\))?'
                         r'[ \t]+([A-Za-z_]\w*)[ \t]*\(', txt, flags=re.M):
        t = m.group(1)
        if t in NOT_A_MODULE or t in defined:
            continue
        if m.group(3) in NOT_A_MODULE:
            continue
        need.add(t)
    return need, defined


def harness_scripts():
    out = []
    for base, _dirs, files in os.walk(ROOT):
        if '/.git' in base:
            continue
        for f in files:
            if (f.startswith('run_') and (f.endswith('.sh') or f.endswith('.py'))):
                out.append(os.path.relpath(os.path.join(base, f), ROOT))
    return sorted(out)


def mentioned_v_paths(rel):
    with open(os.path.join(ROOT, rel), 'r', encoding='utf-8',
              errors='replace') as fh:
        txt = fh.read()
    paths = set(re.findall(r'[A-Za-z0-9_][A-Za-z0-9_./-]*\.s?v\b', txt))
    real, missing = set(), set()
    for p in paths:
        if os.path.isfile(os.path.join(ROOT, p)):
            real.add(p)
        else:
            missing.add(p)
    # a variable-built path such as "$WORK/mut_$i.v" lands in `missing`
    return sorted(real), sorted(missing)


# ---------------------------------------------------------------------------
# SCRATCH, AND WHY IT IS NOT IN /tmp ANY MORE  (2026-10-18)
# ---------------------------------------------------------------------------
# This audit spent 2026-10-18 reporting that ELEVEN harnesses "FAILED to
# elaborate", with CONTROLS at 2 passed / 2 failed, and every one of those
# verdicts was false.  The cause, measured rather than inferred:
#
#   $ ls -la /tmp/closure_examples_phase1_mutation_run_mutation_tests_py.sim
#   -rwxr-xr-x 1 nobody nogroup 21099 Oct 17 11:39 ...
#   $ id -un
#   rcw-01yjbzptk5n2oaw6cot1pa4j
#   $ iverilog ... -o /tmp/closure_examples_phase1_..._py.sim rtl/... tb/...
#   /tmp/closure_examples_phase1_mutation_run_mutation_tests_py.sim: Permission denied
#   error: Code generator failure: -1
#
# The output path was DETERMINISTIC in a SHARED namespace, so the previous
# session's artefacts were still sitting there, owned by a different user, and
# every elaboration died trying to overwrite one.  iverilog was fine: the same
# command with a fresh -o succeeded, rc=0.  And in the same run of
# tools/run_all_harnesses.sh that carried this audit's accusation, eleven of
# the accused scripts are reported PASS, eleven lines further down -- the two
# claims contradicted each other on one page.
#
# TWO SEPARATE DEFECTS, and they are worth keeping apart because they have
# different fixes.
#
#   (a) A deterministic name in a shared, session-outliving namespace collides
#       BY CONSTRUCTION -- with the previous session, and with any other
#       session running this audit concurrently.  Fixed by a private
#       mkdtemp(), which cannot collide and does not outlive the run.
#
#   (b) The audit could not tell "this closure does not elaborate" (a fact
#       about the repository) from "the audit could not run an elaboration at
#       all" (a fact about the machine), so it reported the second as the
#       first.  That is this repository's own 2026-10-17 rule broken by one of
#       its own tools: WHEN A CHECK'S FAILURE MESSAGE NAMES A CAUSE, THE CAUSE
#       MUST BE MEASURED, NOT INFERRED FROM THE CHECK FIRING.  "FAILED to
#       elaborate" is a sentence about Verilog, and it was derived from a
#       nonzero exit status that had nothing to do with Verilog.
#
# Fixing (a) alone would have made today's run green and left (b) in place for
# the next environment to trip -- the worse outcome, because the audit would
# have gone on being able to make an unfounded accusation and would simply not
# have made one today.  So the verdict gains a third value, ENV, and the RESULT
# line counts it separately and never folds it into the harness count.

ENV_MARKERS = (
    'permission denied',
    'code generator failure',
    'no such file or directory',
    'cannot open',
    'read-only file system',
    'no space left on device',
)


def _redact(msg):
    """Strip session-private paths out of anything that reaches the
    transcript.  SCRATCH carries a random mkdtemp suffix, so a message quoting
    it verbatim would make this audit's transcript differ on every run -- and
    this file already forbids exactly that ("a property of where the audit ran
    rather than of what it found", 2026-10-13).  The first draft of the
    2026-10-18 fix printed it in control (5)'s detail line and would have
    committed an unreproducible transcript."""
    out = (msg or '')
    out = out.replace(SCRATCH, '<SCRATCH>')
    out = out.replace(tempfile.gettempdir(), '<TMP>')
    return out


def _is_env_failure(msg):
    """True when the elaboration failed for a reason that is about the machine
    and not about the Verilog.  Deliberately conservative: a message that does
    not match is treated as a REAL elaboration failure, so a genuine defect is
    never explained away as an environment problem.  The asymmetry is the
    point -- (b) above was the audit erring in the other direction."""
    low = (msg or '').lower()
    return any(m in low for m in ENV_MARKERS)


def elaborate(files, label, outdir=None):
    """Really compile `files` with the pinned Icarus build.

    Returns (verdict, msg) where verdict is True (elaborates), False (does
    not), None (iverilog unavailable) or 'ENV' (the elaboration could not be
    carried out here, which is not a statement about `files`)."""
    if not os.path.isdir(IVL_BIN):
        return None, 'iverilog not installed at %s' % IVL_BIN
    out = os.path.join(outdir or SCRATCH, 'closure_%s.sim'
                       % re.sub(r'\W', '_', label))
    # Relative paths, with cwd=ROOT, so that iverilog's diagnostics name
    # repository-relative files.  The first draft passed absolute paths and
    # the committed transcript then carried this machine's session directory
    # -- a property of where the audit ran rather than of what it found,
    # which is exactly what 2026-10-13 ruled out of a transcript.  The -o path
    # is absolute and session-private and is NEVER printed, for the same
    # reason.
    cmd = [os.path.join(IVL_BIN, 'iverilog'), '-B', IVL_LIB, '-g2012',
           '-o', out] + list(files)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT,
                           timeout=180)
    except subprocess.TimeoutExpired:
        return False, 'elaboration timed out'
    msg = (r.stdout + r.stderr).strip().splitlines()
    first = msg[0] if msg else ''
    if r.returncode != 0 and _is_env_failure(' '.join(msg)):
        return 'ENV', _redact(first)
    return r.returncode == 0, _redact(first)


def main():
    print('=' * 78)
    print('HARNESS FILE-CLOSURE AUDIT -- can each harness compile at all?')
    print('created 2026-10-14, out of a runner that had not compiled since 09-27')
    print('=' * 78)
    print()

    vfiles = verilog_files()
    idx = module_index(vfiles)
    scripts = harness_scripts()
    print('  Verilog files indexed : %d' % len(vfiles))
    print('  modules defined       : %d' % len(idx))
    print('  harness scripts found : %d' % len(scripts))
    dupes = {k: v for k, v in idx.items() if len(v) > 1}
    if dupes:
        print()
        print('  modules defined in MORE THAN ONE file (a closure built from the')
        print('  index alone would be ambiguous for these, so they are named):')
        for k, v in sorted(dupes.items()):
            print('      %-28s %s' % (k, ', '.join(v)))

    print()
    print('-' * 78)
    print('PER HARNESS')
    print('-' * 78)
    rows = []
    for sc in scripts:
        real, unresolved = mentioned_v_paths(sc)
        tbs = [p for p in real if 'tb' in os.path.basename(p)
               or p.startswith('examples/')]
        need = set()
        for p in real:
            n, _d = instantiated(p)
            need |= n
        have = set()
        for p in real:
            _n, d = instantiated(p)
            have |= d
        missing = sorted(m for m in need - have if m in idx)
        unknown = sorted(m for m in need - have if m not in idx)
        rows.append((sc, real, unresolved, missing, unknown, tbs))
        status = 'OK' if not missing and not unknown else 'INCOMPLETE'
        print()
        print('  %-62s %s' % (sc, status))
        print('      .v files named      : %s' % (', '.join(real) or '(none)'))
        if unresolved:
            print('      UNRESOLVED_PATHS    : %s   (built from variables;'
                  % ', '.join(unresolved[:4]))
            print('                            invisible to this audit, not a pass)')
        if missing:
            print('      MISSING, and the repository HAS them:')
            for m in missing:
                print('          %-26s defined in %s' % (m, ', '.join(idx[m])))
        if unknown:
            print('      MISSING and NOT DEFINED ANYWHERE: %s'
                  % ', '.join(unknown))

    print()
    print('-' * 78)
    print('CONFIRMATION BY REAL ELABORATION')
    print('-' * 78)
    print('  The static verdict above is a claim about file lists.  Each')
    print('  harness whose named files include a bench is now actually compiled')
    print('  with the pinned Icarus build, because a script can satisfy the')
    print('  static check and still fail to elaborate.')
    print()
    elab = {}
    for sc, real, _unres, missing, _unknown, tbs in rows:
        benches = [p for p in real if re.search(r'_tb\.s?v$', p)]
        if not benches:
            continue
        files = [p for p in real if p.endswith(('.v', '.sv'))]
        ok, msg = elaborate(files, sc)
        elab[sc] = ok
        if ok is None:
            print('  %-58s SKIPPED (%s)' % (sc, msg))
        elif ok == 'ENV':
            print('  %-58s ENV: %s' % (sc, msg[:60]))
            print('      the elaboration could not be CARRIED OUT here; this')
            print('      is not a verdict on this harness.  See the note above')
            print('      elaborate() -- 2026-10-18.')
        elif ok:
            print('  %-58s ELABORATES' % sc)
        else:
            print('  %-58s FAILS: %s' % (sc, msg[:60]))
        if ok not in (None, 'ENV') and bool(missing) == bool(ok):
            print('      note: static said %s and elaboration said %s'
                  % ('INCOMPLETE' if missing else 'OK',
                     'ELABORATES' if ok else 'FAILS'))

    print()
    print('-' * 78)
    print('CONTROLS')
    print('-' * 78)
    # (1) The audit must reproduce the 2026-09-27 omission if it is reinstated.
    #     A control that cannot fail certifies nothing (2026-10-01), so the
    #     omission is reinstated SYNTHETICALLY here -- the bench's closure
    #     minus the BFM must fail to elaborate, with that module named.
    bench = 'examples/phase6_rx_pin_driver/uart_rx_pin_tb.v'
    bfm = 'bfm/uart_rx_pin_bfm.v'
    rtl = 'rtl/uart_controller.v'
    if all(os.path.isfile(os.path.join(ROOT, f)) for f in (bench, bfm, rtl)):
        ok_without, msg_without = elaborate([rtl, bench], 'ctrl_without_bfm')
        ok_with, _m = elaborate([rtl, bfm, bench], 'ctrl_with_bfm')
        check('(1) the 2026-09-27 omission, reinstated synthetically, FAILS '
              'elaboration and names the module',
              ok_without is False and 'uart_rx_pin_bfm' in (msg_without or ''),
              'without the BFM: %r' % (msg_without or '')[:90])
        check('(2) and the same closure WITH the BFM elaborates, so (1) is '
              'about the omission and not about the bench',
              ok_with is True, 'with the BFM: ok=%r' % (ok_with,))
    # (3) The module index must be able to resolve the module the omission
    #     was about -- otherwise the static half would report UNKNOWN for a
    #     module the repository plainly defines.
    check('(3) the module index resolves uart_rx_pin_bfm to exactly one file',
          idx.get('uart_rx_pin_bfm') == [bfm],
          'index says %r' % (idx.get('uart_rx_pin_bfm'),))
    # (4) Every harness the audit calls OK must actually elaborate.  ENV rows
    #     are excluded BY IDENTITY, not by a filter on the message: an ENV row
    #     is not a verdict on the harness, so counting it here is the 2026-10-18
    #     defect itself.
    bad = [sc for sc, ok in elab.items()
           if ok is False and not dict((r[0], r[3]) for r in rows)[sc]]
    check('(4) no harness passes the static check and then fails elaboration',
          not bad, 'disagreeing: %r' % (bad,))

    # (5) THE CONTROL THAT PROVES THE DISTINCTION, against an exactly known
    #     behaviour.  Reproduce 2026-10-18's cause synthetically: a closure
    #     that is known to elaborate, compiled into an output path that is
    #     deliberately unwritable.  The audit must say ENV and must NOT say
    #     FAILS.  A three-valued verdict whose third value is never exercised
    #     is a comment (2026-10-01), and this is the one row that would have
    #     caught today's run on the day.
    if all(os.path.isfile(os.path.join(ROOT, f)) for f in (bench, bfm, rtl)):
        locked = os.path.join(SCRATCH, 'locked')
        os.makedirs(locked, exist_ok=True)
        os.chmod(locked, 0o500)                      # readable, not writable
        try:
            v_env, m_env = elaborate([rtl, bfm, bench], 'ctrl_env', locked)
        finally:
            os.chmod(locked, 0o700)
        check('(5) a closure known to elaborate, sent to an unwritable output '
              'path, is reported ENV and not FAILS',
              v_env == 'ENV', 'verdict=%r msg=%r' % (v_env, (m_env or '')[:80]))
        check('(6) and the SAME closure with a writable path elaborates, so '
              '(5) is about the path and not about the files',
              elaborate([rtl, bfm, bench], 'ctrl_env_ok')[0] is True)

    # (7) The two categories must be DISJOINT, so that no future widening of
    #     ENV_MARKERS can move a real elaboration failure into the benign
    #     column.  (Design-Verification-Roadmap, 2026-10-17: where two causes
    #     produce the same failure they are two reported categories with a
    #     disjointness check between them.)
    real_fail = {sc for sc, ok in elab.items() if ok is False}
    env_fail = {sc for sc, ok in elab.items() if ok == 'ENV'}
    check('(7) the FAILS and ENV sets are disjoint',
          not (real_fail & env_fail), 'overlap %r' % sorted(real_fail & env_fail))

    # (8) And the scratch directory must be private, which is the other half
    #     of the fix.  A deterministic path under /tmp is what collided.
    check('(8) the elaboration scratch directory is session-private, not a '
          'fixed path in a shared namespace',
          SCRATCH.startswith(tempfile.gettempdir())
          and os.path.basename(SCRATCH).startswith('harness_closure_')
          and SCRATCH != tempfile.gettempdir(),
          'scratch is <TMP>/harness_closure_* (suffix redacted: it is random, '
          'and a transcript must not record where the audit ran)')

    print()
    print('=' * 78)
    nb = len([1 for sc, ok in elab.items() if ok is False])
    nenv = len([1 for sc, ok in elab.items() if ok == 'ENV'])
    nok = len([1 for v in elab.values() if v is True])
    print('RESULT: %d harness scripts audited, %d elaborated, %d FAILED to '
          'elaborate' % (len(scripts), nok, nb))
    # ENV is reported on its own line and is NEVER folded into the count
    # above.  Before 2026-10-18 these eleven were in the FAILED column and the
    # sentence "FAILED to elaborate" was a claim about Verilog derived from a
    # file-permission error.
    print('        %d could not be elaborated here at all (ENV -- a fact '
          'about the machine,' % nenv)
    print('        not about the harness; see the note above elaborate())')
    print('CONTROLS: %d passed, %d failed' % (passed, failed))
    print('=' * 78)
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
