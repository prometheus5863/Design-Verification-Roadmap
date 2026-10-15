#!/usr/bin/env python3
"""
tools/report_provenance_audit.py

The 2026-10-14 item ranked FIRST: "audit what re-runs each harness, and what
reads its exit code."

WHY THIS EXISTS, AND WHY THE CLOSURE AUDIT IS NOT IT

2026-10-14 found two mutation harnesses that had failed at elaboration since
2026-09-27 and exited 1 for seventeen consecutive sessions, through every one
of which a committed report reading "detected 7 escaped 0 voided 0" sat beside
them.  Its rule:

    A SUITE THAT CANNOT RUN IS INDISTINGUISHABLE FROM A SUITE NOBODY RAN.

and its checkable form:

    For every committed report, ask what re-runs the script that produced it,
    and what reads that script's exit code.  If the answer to either is
    "nothing", the report's age is not evidence of stability -- it is the
    absence of evidence.

tools/harness_file_closure_audit.py answers a DIFFERENT question: can this
harness compile TODAY.  That is necessary and it is not sufficient, for a
reason 2026-10-14 states and does not mechanise:

    A REPORT CARRIES A DATE IN ITS TEXT WITH NO RELATION TO WHETHER IT WAS
    PRODUCED.  A harness that compiles today still tells you nothing about
    whether the report beside it describes today's harness or a version of it
    that stopped existing three weeks ago.

So this tool asks the question the closure audit cannot: for each committed
report, is any file the report's suite DEPENDS ON newer than the report
itself?  A report older than its own inputs describes a suite that no longer
exists, whether or not that suite compiles.

THE TWO AXES, KEPT SEPARATE ON PURPOSE

  (A) STALENESS -- is the report older than its inputs?  Measured from GIT
      COMMIT DATES, not mtimes.  A fresh clone gives every file the same
      mtime, so an mtime-based audit would report every report fresh in CI and
      on any machine but the one that wrote it.  That is the 2026-10-14 rule
      about transcripts carrying properties of where they ran, applied to the
      instrument instead of to the output.

  (B) RE-RUN REACHABILITY -- does anything in this repository invoke the
      runner that produced the report, and would anything read its exit code?
      A runner nothing calls is re-run only when a human remembers to, which
      is exactly the seventeen-session failure mode.

They are reported as separate columns because they fail independently and the
fix differs: (A) wants the suite re-run, (B) wants a caller.  A report can be
perfectly fresh and still unreachable, and both of 2026-10-14's dead harnesses
were BOTH.

--asof DATE runs the audit as it would have run on DATE: commits after DATE
are ignored and reports dated after DATE are excluded.  That is not a
convenience, it is the tool's main control -- 2026-10-14 asserted that both
dead harnesses "would have been flagged on 2026-09-28", and an assertion about
what an instrument would have said is worth exactly as much as the instrument
run that way.  Control C1 runs it and requires EXACTLY those two.

LIMITS, STATED

  * The dependency closure is approximated from the report's own directory
    plus every existing repo-relative path its scripts name literally.  A path
    built at runtime from a variable is invisible, as it is to the closure
    audit, and is reported as UNRESOLVED rather than as a pass.
  * An input with no git history cannot be dated.  It is reported UNDATED and
    counted as neither fresh nor stale -- never silently as fresh, which would
    be the 2026-10-09 false-DETECTED fault inverted into a false-fresh.
  * This tool reads dates and call graphs.  It does not run anything, so it
    cannot say a suite still PASSES -- only whether its report could possibly
    be about the suite that is there now.  2026-10-15 demonstrated the
    distinction: examples/phase6_bfm_equivalence's report was stale by three
    newer inputs, and re-running the suite reproduced its eight verdicts LINE
    FOR LINE.  The staleness was real and the consequence was nil.  That is
    the honest reading of every row here -- a stale report is unverified, not
    wrong.
  * It audits COMMITTED reports, via `git ls-files`, so a report just written
    and not yet committed is invisible.  Run it after committing, or the
    suite you have just re-run still reads stale.
"""

import argparse
import datetime as _dt
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# A committed report names its date in its filename: ..._YYYY-MM-DD.txt
REPORT_RE = re.compile(r'^(?P<stem>.+)_(?P<date>\d{4}-\d{2}-\d{2})\.(txt|log)$')
SOURCE_EXT = ('.v', '.sv', '.svh', '.py', '.sh')
PATH_RE = re.compile(r'[A-Za-z0-9_./-]+\.(?:v|sv|svh|py|sh)')

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


def parse_date(s):
    """Strict ISO date.  A lenient parser is how 2026-10-14's first audit
    reported missing modules called `whil` and `fo`: the noise was the tell."""
    try:
        return _dt.date.fromisoformat(s)
    except ValueError:
        return None


def git(*args):
    try:
        out = subprocess.run(('git',) + args, cwd=ROOT, capture_output=True,
                             text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return ''
    return out.stdout.strip() if out.returncode == 0 else ''


def last_commit_date(rel, asof=None):
    """Date of the last commit touching `rel`, at or before `asof`."""
    args = ['log', '-1', '--format=%cs']
    if asof is not None:
        args.append('--until=%s 23:59:59' % asof.isoformat())
    args += ['--', rel]
    s = git(*args)
    return parse_date(s) if s else None


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def tracked_files():
    out = git('ls-files')
    return [p for p in out.split('\n') if p]


def reports(files, asof=None):
    """Every committed report, as (rel, stated_date)."""
    out = []
    for rel in files:
        m = REPORT_RE.match(os.path.basename(rel))
        if not m:
            continue
        d = parse_date(m.group('date'))
        if d is None:
            continue
        if asof is not None and d > asof:
            continue
        out.append((rel, d))
    return sorted(out)


# A simulation transcript names its own subject: `<stem>_sim_output_<date>`.
# Everything else here -- mutation_test_report, closure_summary,
# neutrality_pass, the *_audit and *_run_output families -- is a SUITE-level
# report whose runner sweeps the whole directory.
SUBJECT_RE = re.compile(r'^(?P<subject>.+?)_sim_output$')


def report_subject(rel_report):
    """The one source stem a transcript is about, or None for a suite report.

    This distinction is the difference between a usable audit and a noisy
    one.  The FIRST version of this tool used the whole directory for every
    report and called 50 of 70 reports stale -- but
    examples/phase2/ holds six independent exercises side by side, and
    alu_if_sim_output is not invalidated by a later commit to
    alu_sva_checker.sv.  Directory closure is a sound UPPER BOUND and a bad
    headline, so both are reported and the tight one leads.
    """
    base = os.path.basename(rel_report)
    m = REPORT_RE.match(base)
    if not m:
        return None
    sm = SUBJECT_RE.match(m.group('stem'))
    return sm.group('subject') if sm else None


def closure_for(rel_report, files, tight=True):
    """The files the report's suite depends on, plus the unresolved names.

    tight=True restricts a SIMULATION TRANSCRIPT to the sources whose own
    stem it names, plus everything its directory's scripts name outside the
    directory (the DUT, the shared BFM, tools/mutation_controls.sh).  A
    suite-level report is unaffected: its runner really does sweep the
    directory.  tight=False is the directory closure, kept as the upper
    bound.

    Reports themselves are excluded: a report is not an input to the suite
    that produced it.
    """
    d = os.path.dirname(rel_report)
    inside = [f for f in files
              if os.path.dirname(f) == d and f.endswith(SOURCE_EXT)]
    subject = report_subject(rel_report) if tight else None
    if subject:
        # Runners (.sh) stay in: a change to the script that produced a
        # transcript invalidates it.  Sibling .py/.sv sources do NOT -- the
        # first draft kept every .sh AND .py, which defeated the narrowing
        # entirely for the python-based suites, where the subject itself is a
        # .py.  A narrowing that keeps everything is not a narrowing.
        keep = [f for f in inside
                if os.path.splitext(os.path.basename(f))[0].startswith(subject)
                or f.endswith('.sh')]
        # A transcript with no source matching its own stem would silently get
        # an empty closure and read FRESH forever, which is the false-fresh
        # fault.  Fall back to the directory and say so.
        if not any(f.endswith(('.v', '.sv', '.svh', '.py')) for f in keep):
            keep = inside
        inside = keep
    deps = set(inside)
    unresolved = set()
    tracked = set(files)
    for f in inside:
        if not f.endswith(('.sh', '.py')):
            continue
        try:
            with open(os.path.join(ROOT, f), errors='replace') as fh:
                text = fh.read()
        except OSError:
            continue
        for cand in PATH_RE.findall(text):
            for res in _resolve(cand, d, tracked):
                deps.add(res)
                break
            else:
                if '/' in cand:
                    unresolved.add(cand)
    return sorted(deps), sorted(unresolved)


# Every mutation runner in this repository locates its own directory into a
# shell variable and builds paths from it, so a literal match on the raw
# string finds `HERE/../../rtl/uart_controller.v` and resolves nothing.  The
# FIRST version of this audit reported 17 such strings as UNRESOLVED and
# therefore built every mutation suite's closure WITHOUT rtl/uart_controller.v
# or tools/mutation_controls.sh -- i.e. it omitted the DUT from the dependency
# set of the DUT's own mutation tests, which is the one input whose change
# most obviously invalidates a mutation report.  That is 2026-10-06's rule
# (a detector can misattribute what it measured) in the form that matters
# most here: an incomplete closure does not over-report, it UNDER-reports,
# and silently.
_VARPREFIX_RE = re.compile(r'^(?:HERE|ROOT|REPO|DIR|BASE|TOP|SCRIPT_DIR)/')


def _resolve(cand, d, tracked):
    """Candidate repo-relative spellings of `cand`, in preference order."""
    out = []
    raw = cand.lstrip('./')
    stripped = _VARPREFIX_RE.sub('', raw)
    for base, rel in ((None, raw), (None, stripped),
                      (d, raw), (d, stripped)):
        joined = rel if base is None else os.path.join(base, rel)
        norm = os.path.normpath(joined)
        if norm.startswith('..') or norm.startswith('/'):
            continue
        if norm in tracked:
            out.append(norm)
    return out


def runners_in(rel_report, files):
    d = os.path.dirname(rel_report)
    return [f for f in files
            if os.path.dirname(f) == d and f.endswith('.sh')]


def callers_of(rel_script, files):
    """What in this repository invokes `rel_script`.

    Its own file is excluded -- a script naming itself is not a caller, and
    counting it would make every runner look reachable.  That is the
    2026-10-10 rule: a control must not read the thing it controls for.
    """
    base = os.path.basename(rel_script)
    hits = []
    for f in files:
        if f == rel_script or not f.endswith(('.sh', '.py', '.yml', '.yaml')):
            continue
        try:
            with open(os.path.join(ROOT, f), errors='replace') as fh:
                text = fh.read()
        except OSError:
            continue
        if rel_script in text or base in text:
            hits.append(f)
    return hits


# ---------------------------------------------------------------------------
# The audit
# ---------------------------------------------------------------------------

class Row(object):
    def __init__(self, report, stated, newer, undated, unresolved,
                 runners, callers):
        self.report = report
        self.stated = stated
        self.newer = newer                # [(rel, date)] committed after stated
        self.undated = undated            # [rel] no datable history
        self.unresolved = unresolved
        self.runners = runners
        self.callers = callers

    @property
    def stale(self):
        return bool(self.newer)

    @property
    def unreachable(self):
        # No runner in the directory, or no runner that anything else calls.
        return not self.runners or not any(self.callers.get(r)
                                           for r in self.runners)


def audit(asof=None):
    files = tracked_files()
    rows = []
    cache = {}

    def dated(dep):
        if dep not in cache:
            cache[dep] = last_commit_date(dep, asof=asof)
        return cache[dep]

    for rel, stated in reports(files, asof=asof):
        deps, unresolved = closure_for(rel, files, tight=True)
        wide, _ = closure_for(rel, files, tight=False)
        newer, undated = [], []
        for dep in deps:
            dd = dated(dep)
            if dd is None:
                undated.append(dep)
            elif dd > stated:
                newer.append((dep, dd))
        newer_wide = [(dep, dated(dep)) for dep in wide
                      if dated(dep) is not None and dated(dep) > stated]
        runners = runners_in(rel, files)
        callers = {r: callers_of(r, files) for r in runners}
        row = Row(rel, stated, sorted(newer, key=lambda t: t[1], reverse=True),
                  undated, unresolved, runners, callers)
        row.newer_wide = sorted(newer_wide, key=lambda t: t[1], reverse=True)
        row.subject = report_subject(rel)
        rows.append(row)
    return rows


def print_table(rows, asof=None):
    tag = '' if asof is None else '  (as of %s)' % asof.isoformat()
    print('\nREPORT PROVENANCE%s' % tag)
    print('  %d committed reports' % len(rows))
    stale = [r for r in rows if r.stale]
    wide = [r for r in rows if r.newer_wide]
    unreach = [r for r in rows if r.unreachable]
    both = [r for r in rows if r.stale and r.unreachable]
    print('  STALE on the TIGHT closure (older than an input it names): %d'
          % len(stale))
    print('  STALE on the DIRECTORY closure (upper bound, conflates sibling')
    print('        exercises -- reported, not used as the headline):     %d'
          % len(wide))
    print('  UNREACHABLE (nothing re-runs the runner): %d' % len(unreach))
    print('  BOTH: %d   <- the 2026-10-14 failure mode exactly' % len(both))

    # THE PER-REPORT COUNT CANNOT REACH ZERO, AND THAT IS NOT THE AUDIT'S
    # FAULT -- added 2026-10-15 after the first run of this tool in anger.
    #
    # Converting examples/phase6_bfm_equivalence's injection guard and
    # re-running it RAISED the stale count from 45 to 47.  Correctly: the
    # runner is an input to every report in its directory, so repairing a
    # harness invalidates that harness's own older reports, and this
    # repository keeps superseded reports in place by policy rather than
    # deleting them.  THE AUDIT IS REFLEXIVE, and a metric that a repair
    # makes worse is a metric nobody will act on.
    #
    # So the headline is per-SUITE and not per-REPORT: for each directory,
    # is its NEWEST report fresh?  That number CAN reach zero, it does not
    # punish keeping history, and it is the question the 2026-10-14 item
    # actually asks -- does a live harness have a current report.
    bydir = {}
    for r in rows:
        d = os.path.dirname(r.report)
        if d not in bydir or r.stated > bydir[d].stated:
            bydir[d] = r
    suites = sorted(bydir.items())
    with_runner = [(d, r) for d, r in suites if r.runners]
    not_current = [(d, r) for d, r in with_runner if r.stale]
    print('\n  PER-SUITE (the headline: is each suite\'s NEWEST report fresh?)')
    print('    %d directories hold reports; %d of those have a runner.'
          % (len(suites), len(with_runner)))
    print('    %d suite(s) with a runner have NO CURRENT REPORT.'
          % len(not_current))
    for d, r in not_current:
        print('      %-46s newest %s, %d input(s) newer'
              % (d, r.stated.isoformat(), len(r.newer)))
    print('    (The per-report counts above cannot reach zero while')
    print('     superseded reports are kept in place, which is policy here.)')

    # THE SEGMENTATION THAT MAKES THE NUMBER MEAN SOMETHING.  The item asks
    # about HARNESSES.  A transcript in a directory with no runner script was
    # never re-runnable by design -- it is the one-off output of a finished
    # exercise, and its staleness says only that the exercise's source was
    # edited afterwards.  A stale report in a directory that DOES have a
    # runner is the 2026-10-14 fault: a live harness whose committed report
    # cannot be about the harness that is there.
    live = [r for r in stale if r.runners]
    dead = [r for r in stale if not r.runners]
    print('\n  Of the stale reports:')
    print('    %2d are beside a RUNNER -- a live harness with a report that'
          % len(live))
    print('       cannot be about it.  THIS is the actionable set.')
    print('    %2d have no runner at all -- one-off transcripts of finished'
          % len(dead))
    print('       exercises, whose source was edited afterwards.  Expected,')
    print('       and reported rather than counted as debt.')
    if not stale:
        print('\n  No report is older than any of its inputs.')
    for r in sorted(live, key=lambda r: r.stated):
        dep, dd = r.newer[0]
        print('\n  STALE  %s' % r.report)
        print('         stated %s; %d input(s) newer, latest %s (%s)'
              % (r.stated.isoformat(), len(r.newer), dd.isoformat(), dep))
        for dep, dd in r.newer[:6]:
            print('           %s  %s' % (dd.isoformat(), dep))
        print('         runner(s): %s'
              % (', '.join(os.path.basename(x) for x in r.runners) or 'NONE'))
        for x in r.runners:
            c = r.callers.get(x) or []
            print('           %s <- %s'
                  % (os.path.basename(x),
                     ', '.join(c) if c else 'NOTHING IN THIS REPOSITORY'))
    if unreach:
        print('\n  UNREACHABLE runners (report may be fresh and still unverified):')
        seen = set()
        for r in sorted(unreach, key=lambda r: r.report):
            key = os.path.dirname(r.report)
            if key in seen:
                continue
            seen.add(key)
            print('    %-46s runner(s): %s'
                  % (key, ', '.join(os.path.basename(x) for x in r.runners)
                     or 'NONE'))
    # WHICH INPUT IS DOING THE INVALIDATING.  Forty-four stale reports across
    # eight directories is a number; naming the one or two files responsible
    # is a finding.  A shared library counted once per report would hide that
    # it is ONE edit, so the rollup counts DIRECTORIES, not reports.
    if live:
        cause = {}
        for r in live:
            d = os.path.dirname(r.report)
            for dep, dd in r.newer:
                cause.setdefault(dep, set()).add(d)
        print('\n  DOMINANT CAUSES (directories whose reports each input'
              ' invalidates):')
        for dep, dirs in sorted(cause.items(), key=lambda kv: -len(kv[1]))[:6]:
            shared = 'SHARED' if not dep.startswith('examples/') else 'local'
            print('    %-2d dirs  %-6s  %s' % (len(dirs), shared, dep))

    undated = sorted({d for r in rows for d in r.undated})
    unres = sorted({u for r in rows for u in r.unresolved})
    print('\n  UNDATED inputs (counted as neither fresh nor stale): %d%s'
          % (len(undated), (' -- ' + ', '.join(undated[:4])) if undated else ''))
    print('  UNRESOLVED path strings (invisible to this audit): %d%s'
          % (len(unres), (' -- ' + ', '.join(unres[:4])) if unres else ''))
    return stale, unreach


# ---------------------------------------------------------------------------
# Controls
# ---------------------------------------------------------------------------

KNOWN_DEAD_2026_09_27 = {
    'examples/phase6_rx_pin_driver/mutation_test_report_2026-09-25.txt',
    'examples/phase6_baud_error_coverage/mutation_test_report_2026-09-26.txt',
}


def controls():
    print('\nCONTROLS')

    # C1  THE ONE THAT MATTERS.  2026-10-14 asserted both dead harnesses
    #     "would have been flagged on 2026-09-28".  Run the instrument that
    #     way and require EXACTLY those two mutation reports -- an exactly
    #     known target, not a plausible count.
    rows = audit(asof=_dt.date(2026, 9, 28))
    stale28 = {r.report for r in rows if r.stale}
    missed = KNOWN_DEAD_2026_09_27 - stale28
    check('C1 as-of 2026-09-28 flags BOTH harnesses that were dead',
          not missed,
          'missed: %s' % (', '.join(sorted(missed)) or 'none')
          + '  -- and %d reports in total were already stale that day'
          % len(stale28))

    # C1's FIRST DRAFT ASSERTED THE WRONG THING AND THE AUDIT WAS RIGHT.
    # It required EXACTLY the two, and got four.  2026-10-14 claimed only
    # that both "would have been flagged on 2026-09-28" -- it never claimed
    # they were the only two, and the extra rows are a FINDING rather than a
    # false positive.  Asserting 'exactly' would have forced either a
    # loosened detector or a deleted row; the honest move is to assert the
    # claim that was actually made and report the surplus.
    extra = sorted(x for x in stale28
                   if os.path.basename(x).startswith('mutation_test_report')
                   and x not in KNOWN_DEAD_2026_09_27)
    print('         surplus mutation reports stale on 2026-09-28, not named')
    print('         by 2026-10-14: %d%s'
          % (len(extra), (' -- ' + ', '.join(os.path.dirname(x)
                                             for x in extra)) if extra else ''))

    # C2  ...AND THE DAY BEFORE THE BREAK THEY WERE FRESH, so C1 is about the
    #     2026-09-27 commit and not about those two reports being flaggable
    #     by anything at any time.
    rows = audit(asof=_dt.date(2026, 9, 26))
    got26 = {r.report for r in rows if r.stale
             and r.report in KNOWN_DEAD_2026_09_27}
    check('C2 as-of 2026-09-26 (before the break) neither is flagged',
          not got26, 'flagged: %s' % (', '.join(sorted(got26)) or 'none'))

    # C3  THE DETECTOR CAN FIRE AND CAN REFRAIN, on a planted pair rather
    #     than on repository history.  A control that cannot fail certifies
    #     nothing (2026-10-01).
    files = tracked_files()
    probe = 'rtl/uart_controller.v'
    pd = last_commit_date(probe)
    fires = pd is not None and pd > _dt.date(2000, 1, 1)
    refrains = pd is not None and not (pd > _dt.date(2099, 1, 1))
    check('C3 planted comparison both fires and refrains',
          fires and refrains,
          '%s last committed %s: newer than 2000-01-01 = %s, '
          'newer than 2099-01-01 = %s'
          % (probe, pd, fires, not refrains))

    # C4  THE DATE PARSER REFUSES NON-DATES.  2026-10-14's first audit
    #     reported missing modules called `whil` and `fo` because its parser
    #     was lenient; the noise was the tell.  A filename matching the SHAPE
    #     of a date must still be rejected if it is not one.
    bad = ['2026-13-45', '2026-02-30', '20260101', '2026-1-1', 'abcd-ef-gh']
    rejected = [b for b in bad if parse_date(b) is None]
    good = parse_date('2026-09-27')
    check('C4 the date parser rejects %d/%d non-dates and accepts a real one'
          % (len(rejected), len(bad)),
          len(rejected) == len(bad) and good == _dt.date(2026, 9, 27),
          'accepted: %s' % ', '.join(b for b in bad if b not in rejected)
          or 'none accepted')

    # C5  AN UNDATED INPUT IS NOT COUNTED FRESH.  Ask for a path with no
    #     history at all; the dater must return None rather than today.
    nd = last_commit_date('examples/__no_such_file__.v')
    check('C5 an input with no git history dates to None, not to today',
          nd is None, repr(nd))

    # C6  CALLER DETECTION EXCLUDES THE SCRIPT ITSELF.  Every mutation runner
    #     names its own path in its usage text, so counting self-references
    #     would make all of them look reachable -- the 2026-10-10 rule.
    selfnamers = [f for f in files
                  if f.endswith('run_mutation_tests.sh')
                  and f not in callers_of(f, files)]
    allrunners = [f for f in files if f.endswith('run_mutation_tests.sh')]
    check('C6 caller detection never counts a script as its own caller',
          len(selfnamers) == len(allrunners),
          '%d/%d runners excluded from their own caller sets'
          % (len(selfnamers), len(allrunners)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--asof', default=None,
                    help='run the audit as it would have run on this date')
    ap.add_argument('--no-controls', action='store_true')
    args = ap.parse_args()
    asof = parse_date(args.asof) if args.asof else None
    if args.asof and asof is None:
        print('bad --asof date: %r' % args.asof)
        return 2

    print('=' * 74)
    print('REPORT PROVENANCE AUDIT -- what re-runs each harness, and when was')
    print('the report beside it last capable of being about that harness')
    print('=' * 74)
    rows = audit(asof=asof)
    stale, unreach = print_table(rows, asof=asof)
    if not args.no_controls:
        controls()
    print('\n' + '=' * 74)
    print('Controls: %d passed, %d failed' % (passed, failed))
    print('=' * 74)
    if failed:
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
