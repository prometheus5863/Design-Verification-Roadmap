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
# A line whose temp literal sits inside a message rather than in a path the
# line acts on.  Deliberately only the message-emitting forms; see the note
# at the MENTION branch in classify_file.
MENTION_CTX = re.compile(r'^\s*(?:echo|printf|mc__detail)\b'
                         r'|^\s*"[^"]*"\s*\\?\s*$')
# ... but a message form that REDIRECTS or PIPES is acting on a path, not
# describing one.  Plant p_redirect_is_use pins this: `printf '%s' "$OUT" >
# "/tmp/cdc_mode.txt"` starts with printf and is the 2026-10-18 write.
MENTION_NOT = re.compile(r'>>?|\|')

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
        # A MENTION IS NOT A USE (added 2026-11-13).
        #
        # The sibling repository's tolerance census had to learn this on
        # 2026-11-08 and this one had the same defect: a path printed in a
        # DIAGNOSTIC MESSAGE is counted here as a path the script writes to.
        # Narrowly drawn on purpose.  `echo`/`printf` and this repository's
        # own `mc__detail` message wrapper only -- NOT `grep`, `cat`, `df` or
        # a redirect, because reading a fixed path in a shared namespace is
        # precisely the 2026-10-18 incident this module exists for and a
        # stale file read as this run's output is the fault, not a mention.
        # Counted as its own class rather than dropped: how many places
        # DISCUSS a shared path is a real number; it is just not R1's number.
        if MENTION_CTX.search(line) and not MENTION_NOT.search(line):
            rows.append((i, line.strip(), 'MENTION', 'the literal is inside '
                         'a diagnostic message, not a path this line uses'))
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
    # the 2026-11-13 class, with the three cases that must NOT join it
    ('p_mention_echo', 'echo "SETUP FAILED -- see /tmp/setup.log"', 'MENTION'),
    ('p_mention_detail', 'mc__detail "tried TMPDIR=${TMPDIR:-unset}, /tmp"',
     'MENTION'),
    ('p_read_is_use', 'if grep -q PASS /tmp/cdc_mode0.txt; then', 'SHARED'),
    ('p_redirect_is_use', 'printf \'%s\' "$OUT" > "/tmp/cdc_mode.txt"',
     'SHARED'),
    ('p_df_is_use', 'df -P "$TMPDIR" | tail -1', 'SHARED'),
]


# ===========================================================================
# THE SCRATCH-BASE CENSUS (2026-11-13)
#
# A SECOND QUESTION ABOUT THE SAME LINES, AND THE FIRST CENSUS CANNOT SEE IT.
#
# Everything above asks whether a scratch path can COLLIDE.  It finds its
# population by matching a `/tmp` or `$TMPDIR` literal, so
#
#     WORK="$(mktemp -d)"
#
# is invisible to it: there is no literal on the line.  That line is PRIVATE
# and uncollidable and it is also the line that broke this repository on
# 2026-11-13, because its base is whatever `TMPDIR` happens to be and the
# filesystem `TMPDIR` pointed at was full.  `mktemp` failed, the shell set
# `WORK` to the EMPTY STRING, the run continued, and every "$WORK/x" became an
# absolute path at the filesystem root.
#
# What followed is the part worth a census.  examples/phase6_bfm_equivalence
# wrote its golden copy to /golden.v, was refused, and its G2b neutrality arm
# then aborted with "the neutral copy is byte-identical; it controls nothing"
# -- a CORRECT REFUSAL WITH A FALSE DIAGNOSIS, naming a mechanism a reader
# would then go and audit.  examples/phase4_ral reported "NORESULT on
# unmodified RTL" and pointed at /baseline.log.  Both suites were dark and
# neither said why.
#
# THE FOURTH AND FIFTH ENCOUNTERS WITH THIS DISK.  2026-11-07 added the
# iverilog/vvp wrappers that probe TMPDIR; 2026-11-09 recorded the symptom;
# 2026-11-12 found the repair's installed surface and the used surface were
# disjoint and moved all 20 invocation sites.  None of it reaches a runner's
# OWN `mktemp -d`, which is not an iverilog call.  And on 2026-11-13 the same
# full filesystem also defeated the documented uvm-python install recipe from
# 2026-09-06, by way of pip's CACHE directory -- which `TMPDIR` does not move
# and which that note does not mention.  Same disk, three surfaces.
#
# So this census takes every creation site and classifies WHERE ITS BASE
# COMES FROM, which is a property of the line and not of the environment.

CREATE = re.compile(r'\bmktemp\b[^\n]*|\bmkdtemp\s*\(|'
                    r'\bTemporaryDirectory\s*\(')
BASE_CLASSES = ('BASE_HELPER', 'BASE_PINNED', 'BASE_EXPLICIT',
                'BASE_TMPDIR_GUARDED', 'BASE_TMPDIR_BARE',
                'BASE_INHERITED_PY', 'BASE_INHERITED_SH')

# THE CENSUS FOUND A POPULATION FIVE TIMES THE EXPECTED ONE, AND SPLITTING IT
# IS THE FINDING.  The first run of this section reported 33 inherited sites
# where the repair had addressed six.  The other twenty-seven are Python:
# `tempfile.mkdtemp()` and `TemporaryDirectory()`, which also take their base
# from TMPDIR.  They are NOT the same severity and the gate must not pretend
# they are: Python RAISES on a failed creation, so the run stops at the site
# with a traceback that names the directory.  The shell form assigns the EMPTY
# STRING and keeps going, which is what turned a disk fault into a neutrality
# verdict on 2026-11-13.  Loud and wrong beats silent and wrong, so the gate
# is the shell class and the Python class is a named worklist.


def classify_base(line, nextline=''):
    """Where a scratch-creation line takes its base from, or None if the line
    is not a creation site.

    Comments and prose are excluded the same way the collision census
    excludes them: a creation inside a comment is discussion, not a site.
    """
    st = line.strip()
    if st.startswith('#'):
        return None
    if 'mc_workdir' in line:
        return 'BASE_HELPER'
    if not CREATE.search(line):
        return None
    if any(n in line for n in NOT_SCRATCH) or 'IVL' in line:
        return 'BASE_PINNED'
    if re.search(r'\$\{?TMPDIR\}?', line):
        # A guarded site handles the failure on the same line or the next one.
        if re.search(r'\|\|', line) or re.search(r'\|\|', nextline):
            return 'BASE_TMPDIR_GUARDED'
        return 'BASE_TMPDIR_BARE'
    # An explicit literal base: immune to TMPDIR entirely.  Checked before
    # the inherited verdict so a template with a base is never called bare.
    if re.search(r'mktemp\b[^\n]*[\'\"]?/(?:tmp|var)/', line) \
            or re.search(r'(?:mkdtemp|TemporaryDirectory)\s*\([^)]*dir\s*=',
                         line) \
            or re.search(r'mktemp\b[^\n]*\$\{?\w+\}?/', line):
        return 'BASE_EXPLICIT'
    if re.search(r'\bmkdtemp\s*\(|\bTemporaryDirectory\s*\(', line):
        return 'BASE_INHERITED_PY'
    return 'BASE_INHERITED_SH'


# THIS MODULE MUST NOT CENSUS ITSELF, AND IT DID, AND THE FIRST RUN SAID SO.
#
# Its plants are creation lines by construction and its prose quotes them, so
# the first full run reported 8 BASE_INHERITED_SH and 2 BASE_TMPDIR_BARE rows
# INSIDE THIS FILE -- a population of its own controls, reported as findings
# about the repository.  The sibling repository hit the identical thing on the
# same day and generalised a SELF-only exclusion into a declared class; this
# is the shell-and-python form of it.  The exclusion is declared here and
# check S-b5 asserts the file is outside its own population, so the next
# instrument added to this repository has a precedent rather than a surprise.
CENSUS_PLANTING_FILES = ('tools/shared_scratch_audit.py',)


def base_census():
    """[(rel, lineno, cls, line)] over the whole tree, excluding the files
    that plant the pattern this censuses."""
    rows = []
    for rel in harness_files():
        if rel in CENSUS_PLANTING_FILES:
            continue
        try:
            lines = open(os.path.join(ROOT, rel), encoding='utf-8',
                         errors='replace').read().split('\n')
        except OSError:
            continue
        for i, line in enumerate(lines):
            cls = classify_base(line, lines[i + 1] if i + 1 < len(lines)
                               else '')
            if cls:
                rows.append((rel, i + 1, cls, line.strip()))
    return rows


BASE_PLANTS = [
    ('b_inherited_sh', 'WORK="$(mktemp -d)"', 'BASE_INHERITED_SH'),
    ('b_inherited_py', "work = tempfile.mkdtemp(prefix='fifo_mut.')",
     'BASE_INHERITED_PY'),
    ('b_explicit', 'WORK="$(mktemp -d /tmp/foo.XXXXXX)"', 'BASE_EXPLICIT'),
    ('b_tmpdir_bare', 'WORK="$(mktemp -d "$TMPDIR/foo.XXXXXX")"',
     'BASE_TMPDIR_BARE'),
    ('b_tmpdir_default', 'WORK="$(mktemp -d "${TMPDIR:-/tmp}/foo.XXXXXX")"',
     'BASE_TMPDIR_BARE'),
    ('b_helper', 'WORK="$(mc_workdir foo)" || exit 1', 'BASE_HELPER'),
    ('b_pinned', 'WORK="$(mktemp -d "${IVL}/tmp/probe.XXXXXX")"',
     'BASE_PINNED'),
    ('b_comment', '#   WORK="$(mktemp -d)"   (this is prose)', None),
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
    tally = {'PRIVATE': 0, 'SCOPED': 0, 'SHARED': 0, 'MENTION': 0}
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

    check('R7 THE MENTION CLASS, AND WHAT IT DOES NOT EXCUSE (2026-11-13): '
          '%d row(s) are diagnostic messages naming a temp path and %d are '
          'real uses.  R1 above is RED on those %d and WAS RED BEFORE TODAY '
          '-- measured at HEAD before any of this session\'s edits: 35 SHARED, '
          '15 controls passing, 1 failing.  So this module is a THIRD red '
          'harness that the 2026-11-12 red set (two) did not name'
          % (tally['MENTION'], tally['SHARED'], tally['SHARED']),
          tally['MENTION'] >= 1 and tally['SHARED'] >= 1,
          'the %d SHARED rows are printed above, file by file, and are the '
          'worklist; narrowing MENTION further would hide uses, which is why '
          'grep, cat, df and every redirect stay SHARED' % tally['SHARED'])

    print()
    print('-' * 78)
    print('4.  THE SCRATCH-BASE CENSUS -- a second question about the same')
    print('    lines, and the collision census above cannot see it')
    print('-' * 78)
    for name, snippet, want in BASE_PLANTS:
        lines = snippet.split('\n')
        got = None
        for i, l in enumerate(lines):
            got = classify_base(l, lines[i + 1] if i + 1 < len(lines) else '')
            if got:
                break
        check('S-b0.%s plant classifies %s' % (name, want), got == want,
              'got %r' % (got,))

    brows = base_census()
    btally = {}
    for _rel, _n, cls, _line in brows:
        btally[cls] = btally.get(cls, 0) + 1
    for cls in BASE_CLASSES:
        if cls in btally:
            print('    %-22s %2d' % (cls, btally[cls]))
    for rel, n, cls, line in brows:
        if cls in ('BASE_INHERITED_SH', 'BASE_TMPDIR_BARE'):
            print('      %-20s %s:%d  %s' % (cls, rel, n, line[:60]))
    check('S-b1 the base classification is EXHAUSTIVE over every creation '
          'site -- %d site(s) in %d class(es), and every one has a class'
          % (len(brows), len(btally)),
          len(brows) == sum(btally.values()) and len(brows) > 0,
          'classes: %r' % (btally,))
    danger = [r for r in brows
              if r[2] in ('BASE_INHERITED_SH', 'BASE_TMPDIR_BARE')]
    pyrows = [r for r in brows if r[2] == 'BASE_INHERITED_PY']
    check('S-b2 THE GATE: no creation site takes its base from TMPDIR '
          'invisibly or without handling the failure.  On 2026-11-13 there '
          'were SIX bare sites and TWO unguarded TMPDIR sites, and two '
          'mutation suites were dark because of them',
          len(danger) == 0,
          'offending sites:\n%s'
          % ('\n'.join('  %s:%d  %s' % (r[0], r[1], r[3][:70])
                        for r in danger) or '  none'))
    check('S-b2b AND THE WORKLIST THE GATE DELIBERATELY EXCLUDES: %d Python '
          'site(s) take their base from TMPDIR too, via tempfile.  They are '
          'named, not gated, because tempfile RAISES on a failed creation -- '
          'the run stops at the site with a traceback naming the directory, '
          'where the shell form assigns the empty string and carries on.  '
          'Loud and wrong is a different defect from silent and wrong'
          % len(pyrows),
          len(pyrows) == len([r for r in brows
                              if r[2] == 'BASE_INHERITED_PY']),
          'files: %s' % ', '.join(sorted(set(r[0] for r in pyrows))[:8]))
    # THE BLIND SPOT, DEMONSTRATED AND NOT ASSERTED.
    bare = 'WORK="$(mktemp -d)"'
    check('S-b3 the collision census CANNOT see the class this one exists '
          'for: on a bare creation line it returns no rows at all, because '
          'its population is lines carrying a /tmp or $TMPDIR literal and '
          'this line carries neither.  Same shape as the 2026-11-12 finding '
          'that a census matching a concatenated string cannot see a '
          'concatenation',
          classify_file(__file__, text=bare) == []
          and classify_base(bare) == 'BASE_INHERITED_SH',
          'collision census rows: %r; base census class: %r'
          % (classify_file(__file__, text=bare), classify_base(bare)))
    repaired = {
        'examples/phase6_bfm_equivalence/run_mutation_tests.sh': 'BASE_HELPER',
        'examples/phase4_ral/run_mutation_tests.sh': 'BASE_HELPER',
        'tools/audit_mutation_anchors.sh': 'BASE_HELPER',
        'tools/test_mutation_controls.sh': 'BASE_HELPER',
        'examples/phase6_rx_occupancy_probe/'
        'run_rx_occupancy_mutation_tests.sh': 'BASE_HELPER',
        'examples/phase5_csr_formal/run_reset_formal.sh': 'BASE_EXPLICIT',
        'examples/phase5_csr_formal/run_csr_formal.sh': 'BASE_EXPLICIT',
        'examples/phase5_formal_uart/run_formal.sh': 'BASE_EXPLICIT',
        # the six bare FILE temporaries this census found that the repair had
        # not looked for: `LOG="$(mktemp)"`, same hazard, no -d
        'examples/phase4_uvm_milestone/run_phase4_uvm.sh': 'BASE_EXPLICIT',
        'examples/phase6_baud_error_coverage/run_baud_cov.sh': 'BASE_EXPLICIT',
        'examples/phase6_rx_pin_driver/run_rx_pin.sh': 'BASE_EXPLICIT',
    }
    missing = []
    for rel, want in sorted(repaired.items()):
        if not any(r[0] == rel and r[2] == want for r in brows):
            missing.append((rel, want,
                            [r[2] for r in brows if r[0] == rel]))
    check('S-b5 this module is OUTSIDE its own population: its plants are '
          'creation lines by construction, and the first run of this section '
          'reported 8 BASE_INHERITED_SH and 2 BASE_TMPDIR_BARE rows inside '
          'it -- its own controls, reported as findings about the repository',
          not any(r[0] in CENSUS_PLANTING_FILES for r in brows),
          'rows from excluded files: %r'
          % [r for r in brows if r[0] in CENSUS_PLANTING_FILES])
    check('S-b4 every site repaired on 2026-11-13 is NAMED here and is in '
          'the class the repair put it in -- %d of them, five onto the '
          'mc_workdir helper and three onto an explicit base because they do '
          'not source tools/mutation_controls.sh' % len(repaired),
          not missing, 'not as declared: %r' % (missing,))

    print()
    print('=' * 78)
    print('RESULT: %d files scanned, %d with temp-namespace lines, '
          '%d SHARED' % (len(harness_files()), len(all_rows), tally['SHARED']))
    print('CONTROLS: %d passed, %d failed' % (passed, failed))
    print('=' * 78)
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
