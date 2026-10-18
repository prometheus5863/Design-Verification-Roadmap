"""
tools/shared_scratch_audit.py

A FIXED PATH IN A SHARED TEMP NAMESPACE IS A COLLISION WITH EVERY OTHER
SESSION, AND IT IS SILENT UNTIL IT IS NOT.

Created 2026-10-18, after tools/harness_file_closure_audit.py spent a whole
run reporting that ELEVEN harnesses "FAILED to elaborate" -- with its own
controls at 2 passed / 2 failed -- because its `iverilog -o` path was

    /tmp/closure_<script-path-with-underscores>.sim

a deterministic name in a namespace that outlives the session.  Yesterday's
run left those files behind owned by `nobody:nogroup`; this session's user
could not overwrite them; iverilog returned "Permission denied / Code
generator failure: -1"; and the audit reported that sentence as a verdict on
the Verilog.  The same run of tools/run_all_harnesses.sh reported eleven of
the accused scripts PASS, eleven lines further down the page.

That has been repaired in place.  This module exists because the repair fixes
ONE script, and the property is repository-wide: every harness here writes
scratch somewhere, and the automation runs in a fresh session each time on a
machine whose /tmp is not fresh.

WHAT THE SWEEP FOUND ON ITS FIRST RUN

Most harnesses were already right -- `mktemp -d /tmp/uart_mut.XXXXXX` and
friends, in six scripts.  Three were not:

  examples/phase6_uvm_crv_uart/run_mutation_tests.sh   WORK="/tmp/uvm_crv_mut"
  examples/phase5_property_coverage/run_property_coverage.sh  /tmp/pcov{,2,3}
  examples/phase5_property_coverage/run_chunk.sh       WORK="${WORK:-/tmp/pcov}"

All three are in suites that SKIP here (cocotb and sby are both absent), so
the fault was LATENT -- invisible on every run to date and waiting for the
first machine where those tools exist and a previous session had been.
Latent and harmless are not the same property.

AND THE TWO CASES NEEDED DIFFERENT FIXES, WHICH IS THE INTERESTING PART

phase6_uvm_crv_uart had no reason for a stable path; it was simply the one
mutation harness that had not been given `mktemp -d` like its six siblings.
It gets one.

phase5_property_coverage is the opposite: its stability is LOAD-BEARING.  Each
shell this automation gets is time-limited and background jobs do not survive
it, so the sweep is resumable by construction -- run_chunk.sh must find the
same $RESULTS on the next invocation, and randomising the path would break the
feature.  Randomising it would also have looked like a fix and passed any
check that only tests for `mktemp`.  So that path is SCOPED BY UID instead:
stable within a user, distinct between users.

Its exposure was also the worse of the two, and in the direction that matters.
`phase()` starts with `rm -rf "$work"`, which FAILS on a directory owned by
another user, and report.py then reads `$work/results.txt` -- so a stale
results file from another session is reported as this run's results, with no
error raised anywhere.  The closure audit failed LOUDLY and falsely; this one
would have succeeded quietly and falsely.  A third instance of the same shape
was hit in the sibling repository on the same day: a redirect to a stale
/tmp file failed with Permission denied while `tail` of that path returned a
PREVIOUS SESSION'S OUTPUT and looked like a successful run.

CLASSES
  PRIVATE   mktemp/mkdtemp -- cannot collide, does not outlive the run
  SCOPED    a stable path that is per-user (or otherwise session-scoped), with
            a stated reason; the reason is REQUIRED
  SHARED    a fixed path in a shared namespace, with no stated reason: a fault

THE EXEMPTION LIVES IN THE SOURCE, NOT IN HERE, and its reason is required --
the graphene repository's 2026-10-01 rule, for the same motive: a checker that
keeps the repository's reasons inside itself hides them from whoever reads the
line.  Marker, on or above the line:

    # scratch-shared-exempt: <reason>
"""

import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# A temp-namespace literal.
#
# THE FIRST DRAFT OF THIS PATTERN REQUIRED A TRAILING SLASH -- `/tmp/` -- and
# therefore MISSED THE ONE LINE THIS WHOLE MODULE WAS WRITTEN ABOUT:
#
#     out = os.path.join('/tmp', 'closure_%s.sim' % re.sub(r'\W', '_', label))
#
# in tools/harness_file_closure_audit.py, where the literal is '/tmp' with the
# separator supplied by os.path.join.  Verified against the pre-fix tree at
# 1e2529e: the draft found 8 SHARED rows in the three shell scripts and 0 in
# the Python file that actually caused the 2026-10-18 incident.  A checker that
# passes on the broken tree certifies nothing, and this one would have passed
# on the specific breakage it exists for.
#
# So /tmp is matched as a whole path COMPONENT -- followed by a separator, a
# quote, whitespace, a comma or a close-paren, or by end of line -- which
# covers os.path.join('/tmp', ...), Path('/tmp'), TMPDIR="/tmp" and the
# shell's /tmp/x alike.  Plant p_py_join below pins it.
TMP_LIT = re.compile(r'(?:/tmp|\$\{?TMPDIR\}?)(?=[/\'\"\s,);:]|$)')
# A private-by-construction creation.
PRIVATE = re.compile(r'\bmktemp\b|\bmkdtemp\b|\bTemporaryDirectory\b|'
                     r'\bNamedTemporaryFile\b')
# Session scoping that makes a stable path non-shared.
SCOPING = re.compile(r'\$\(id -u\)|\$\(id -un\)|\$UID|\$EUID|\bgetuid\(\)|'
                     r'\bgeteuid\(\)|\bgetpid\(\)|\$\$')
EXEMPT = re.compile(r'#\s*scratch-shared-exempt:\s*(\S.*)')

# Paths that are not scratch at all: the pinned toolchain install, which is a
# read-only shared cache by design and is created by tools/setup_iverilog.sh.
NOT_SCRATCH = ('/tmp/iverilog_install', '/tmp/oss-cad-suite')


def harness_files():
    out = []
    for base, _dirs, files in os.walk(ROOT):
        if '/.git' in base:
            continue
        for f in files:
            if f.endswith(('.sh', '.py')):
                out.append(os.path.relpath(os.path.join(base, f), ROOT))
    return sorted(out)


def classify_file(rel, text=None):
    """-> list of (lineno, line, cls, reason)."""
    if text is None:
        with open(os.path.join(ROOT, rel), encoding='utf-8',
                  errors='replace') as fh:
            text = fh.read()
    lines = text.split('\n')
    rows = []
    for i, line in enumerate(lines, 1):
        if not TMP_LIT.search(line):
            continue
        if any(ns in line for ns in NOT_SCRATCH):
            continue
        # A line inside a comment is documentation, not a path the script uses.
        stripped = line.lstrip()
        if stripped.startswith('#'):
            continue
        if PRIVATE.search(line):
            rows.append((i, line.strip(), 'PRIVATE', ''))
            continue
        reason = ''
        for probe in (line, lines[i - 2] if i >= 2 else '',
                      lines[i - 3] if i >= 3 else ''):
            m = EXEMPT.search(probe or '')
            if m:
                reason = m.group(1).strip()
                break
        if SCOPING.search(line) and reason:
            rows.append((i, line.strip(), 'SCOPED', reason))
        elif SCOPING.search(line):
            rows.append((i, line.strip(), 'SHARED', 'uid-scoped but NO stated '
                         'reason -- the marker is required'))
        else:
            rows.append((i, line.strip(), 'SHARED', reason or ''))
    return rows


# ---------------------------------------------------------------------------
# Plants, with exactly known answers
# ---------------------------------------------------------------------------

PLANTS = [
    ('p_private', 'WORK="$(mktemp -d /tmp/foo.XXXXXX)"', 'PRIVATE'),
    ('p_shared', 'WORK="/tmp/foo"', 'SHARED'),
    ('p_scoped_no_reason', 'WORK="/tmp/foo-$(id -u)"', 'SHARED'),
    ('p_scoped_with_reason',
     '# scratch-shared-exempt: resumable across shells\nWORK="/tmp/foo-$(id -u)"',
     'SCOPED'),
    ('p_comment_only', '#   WORK="/tmp/foo"  (this is prose)', None),
    ('p_toolchain', 'PATH="/tmp/iverilog_install/bin:$PATH"', None),
    ('p_py_tempdir', "d = tempfile.mkdtemp(prefix='/tmp/x')", 'PRIVATE'),
    # The blind spot that let the 2026-10-18 cause through the first draft:
    # a '/tmp' literal whose separator is supplied by os.path.join.
    ('p_py_join', "out = os.path.join('/tmp', 'closure_%s.sim' % label)",
     'SHARED'),
    ('p_py_join_private',
     "out = os.path.join(tempfile.mkdtemp(), 'closure.sim')", None),
    ('p_tmpdir_var', 'TMPDIR="/tmp"', 'SHARED'),
]


def main():
    passed = failed = 0

    def check(label, ok, detail=''):
        nonlocal passed, failed
        if ok:
            passed += 1
            print('  [PASS] %s' % label)
        else:
            failed += 1
            print('  [FAIL] %s' % label)
        if detail:
            print('         %s' % detail)

    print('=' * 78)
    print('SHARED-SCRATCH AUDIT -- does any harness write to a fixed path')
    print('in a namespace that outlives the session?')
    print('created 2026-10-18, after a fixed /tmp path made the closure audit')
    print('accuse eleven harnesses of a fault none of them had')
    print('=' * 78)

    print()
    print('-' * 78)
    print('1.  POSITIVE CONTROL ON THE CLASSIFIER')
    print('-' * 78)
    for name, snippet, want in PLANTS:
        rows = classify_file(__file__, text=snippet)
        got = rows[-1][2] if rows else None
        print('  planted %-22s expect %-8s got %s'
              % (name, want or 'IGNORED', got or 'IGNORED'))
        check('    plant %s classifies %s' % (name, want or 'IGNORED'),
              got == want, 'rows=%r' % (rows,))

    print()
    print('-' * 78)
    print('2.  THE REPOSITORY')
    print('-' * 78)
    all_rows = {}
    for rel in harness_files():
        if os.path.basename(rel) == os.path.basename(__file__):
            continue
        rows = classify_file(rel)
        if rows:
            all_rows[rel] = rows
    tally = {'PRIVATE': 0, 'SCOPED': 0, 'SHARED': 0}
    for rel, rows in sorted(all_rows.items()):
        print('  %s' % rel)
        for ln, line, cls, reason in rows:
            tally[cls] += 1
            print('      %-4d %-8s %s' % (ln, cls, line[:52]))
            if reason:
                print('           reason: %s' % reason[:60])
    print()
    print('  tally: %s' % tally)

    shared = [(rel, ln, line) for rel, rows in all_rows.items()
              for ln, line, cls, _r in rows if cls == 'SHARED']
    check('R1 no harness writes scratch to a fixed path in a shared namespace',
          not shared, 'SHARED rows: %r' % (shared,))
    check('R2 every SCOPED row carries a stated reason',
          all(r[3] for rows in all_rows.values() for r in rows
              if r[2] == 'SCOPED'),
          '%d scoped rows' % tally['SCOPED'])
    # NON-VACUITY: if the walker found nothing, R1 passes for the wrong reason.
    check('R3 the sweep actually examined temp-namespace lines '
          '(not vacuously clean)',
          sum(tally.values()) >= 6, 'tally %s' % tally)
    check('R4 the sweep looked at more than a handful of files',
          len(harness_files()) >= 20, '%d .sh/.py files' % len(harness_files()))

    # The repaired script must be PRIVATE and the resumable one SCOPED --
    # asserted by name, because "no SHARED rows" is also satisfied by deleting
    # the scripts.
    uvm = 'examples/phase6_uvm_crv_uart/run_mutation_tests.sh'
    pcov = 'examples/phase5_property_coverage/run_property_coverage.sh'
    check('R5 %s is PRIVATE' % os.path.basename(uvm),
          any(r[2] == 'PRIVATE' for r in all_rows.get(uvm, [])),
          'rows=%r' % (all_rows.get(uvm),))
    check('R6 the resumable sweep is SCOPED, not randomised '
          '(randomising it would break resumability and still pass R1)',
          any(r[2] == 'SCOPED' for r in all_rows.get(pcov, [])),
          'classes=%r' % ([r[2] for r in all_rows.get(pcov, [])],))

    print()
    print('=' * 78)
    print('RESULT: %d files scanned, %d with temp-namespace lines, '
          '%d SHARED' % (len(harness_files()), len(all_rows), tally['SHARED']))
    print('CONTROLS: %d passed, %d failed' % (passed, failed))
    print('=' * 78)
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
