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
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IVL = os.environ.get('IVERILOG_INSTALL_DIR', '/tmp/iverilog_install')
IVL_BIN = os.path.join(IVL, 'usr/bin')
IVL_LIB = os.path.join(IVL, 'usr/lib/x86_64-linux-gnu/ivl')

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


def elaborate(files, label):
    """Really compile `files` with the pinned Icarus build."""
    if not os.path.isdir(IVL_BIN):
        return None, 'iverilog not installed at %s' % IVL_BIN
    out = os.path.join('/tmp', 'closure_%s.sim' % re.sub(r'\W', '_', label))
    # Relative paths, with cwd=ROOT, so that iverilog's diagnostics name
    # repository-relative files.  The first draft passed absolute paths and
    # the committed transcript then carried this machine's session directory
    # -- a property of where the audit ran rather than of what it found,
    # which is exactly what 2026-10-13 ruled out of a transcript.
    cmd = [os.path.join(IVL_BIN, 'iverilog'), '-B', IVL_LIB, '-g2012',
           '-o', out] + list(files)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT,
                           timeout=180)
    except subprocess.TimeoutExpired:
        return False, 'elaboration timed out'
    msg = (r.stdout + r.stderr).strip().splitlines()
    return r.returncode == 0, (msg[0] if msg else '')


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
        elif ok:
            print('  %-58s ELABORATES' % sc)
        else:
            print('  %-58s FAILS: %s' % (sc, msg[:60]))
        if ok is not None and bool(missing) == bool(ok):
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
    # (4) Every harness the audit calls OK must actually elaborate.
    bad = [sc for sc, ok in elab.items()
           if ok is False and not dict((r[0], r[3]) for r in rows)[sc]]
    check('(4) no harness passes the static check and then fails elaboration',
          not bad, 'disagreeing: %r' % (bad,))

    print()
    print('=' * 78)
    nb = len([1 for sc, ok in elab.items() if ok is False])
    print('RESULT: %d harness scripts audited, %d elaborated, %d FAILED to '
          'elaborate' % (len(scripts), len([1 for v in elab.values() if v]), nb))
    print('CONTROLS: %d passed, %d failed' % (passed, failed))
    print('=' * 78)
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
