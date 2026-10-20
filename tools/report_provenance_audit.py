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


# Populated by closure_for(); read by the table and by control P2.
_PROSE_EDGES = {}


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
    prose = set()
    unresolved = set()
    tracked = set(files)
    for f in inside:
        if not f.endswith(('.sh', '.py')):
            continue
        codep, prosep, unres = named_paths(f, d, tracked)
        deps |= codep
        prose |= prosep
        unresolved |= unres
    # A PROSE edge is held in the DIRECTORY closure and kept out of the tight
    # one.  See the note above code_only().  `inside` members are never
    # demoted: being in the directory is not a claim about naming.
    prose -= deps
    if not tight:
        deps |= prose
    _PROSE_EDGES[rel_report] = sorted(prose)
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


# ---------------------------------------------------------------------------
# NAMING IS NOT INVOKING, AND NAMING IS NOT FEEDING  (2026-10-20)
# ---------------------------------------------------------------------------
# The 2026-10-18 entry ranked one item first and named two mechanisms in this
# file.  Both are real; the mechanism of the second one is NOT the one that
# entry guessed, and the consequence it warned about does not occur.
#
#   (1) callers_of() RESOLVED ON BASENAME.  Six harnesses in this repository
#       are called run_mutation_tests.sh, so each was reported as a caller of
#       the other five.  They are SIBLINGS.  Visible in the committed output
#       of 2026-10-18, where one runner's caller list is five sibling runners
#       plus four tools that only read it.
#
#   (2) "NAMES THE RUNNER" WAS TREATED AS "IS AN INPUT TO ITS RESULTS".  The
#       entry attributed this to the caller relation leaking into the
#       closure.  Measured, it is simpler and worse: closure_for() ran
#       PATH_RE over the WHOLE TEXT of every script in the directory,
#       COMMENTS INCLUDED.  A path named in prose became a dependency.
#
#       The exact edge that forced 2026-10-18 to re-run the baud bench is
#       line 35 of examples/phase6_baud_error_coverage/run_mutation_tests.sh:
#
#           # tools/harness_file_closure_audit.py after the first was found
#
#       a sentence about an auditor, which made that auditor an input to the
#       bench's mutation report, which made the report stale the moment the
#       auditor was edited.  40 such comment-only edges exist, 17 % of the
#       235 edges this audit was building closures from.  The sibling repo
#       named resolve-on-spelling its dominant failure mode on the same day:
#       this is that, with the spelling being "appears in the file".
#
# THE FIX IS NOT "STRIP COMMENTS", because that direction is the dangerous
# one.  tools/mutation_controls.sh names rtl/uart_controller.v ONLY in prose
# -- its code builds the path from a variable -- so a naive strip would drop
# the DUT from the dependency set of the DUT's own mutation tests.  That is
# precisely the under-report fault the comment above _VARPREFIX_RE says the
# first version of this audit committed, and an under-report here is silent.
#
# So an edge gains a CLASS rather than being kept or deleted:
#
#     CODE   the path is named outside comments      -> a dependency
#     PROSE  the path is named ONLY inside comments  -> reported, and held in
#                                                       the DIRECTORY closure
#                                                       only, never the tight
#                                                       one
#
# which is the TIGHT / DIRECTORY pattern this file already uses for the other
# closure, and keeps every demoted edge visible instead of dropping it.
#
# Only WHOLE-LINE comments are stripped.  A trailing-# rule would have to
# decide whether the # in `sed 's/#//'` opens a comment, and a rule that can
# remove code to protect a metric is the wrong trade here.  Conservative in
# the direction that cannot under-report: if in doubt, the edge stays CODE.
#
# WHAT THE STANDING ITEM GOT WRONG, recorded rather than quietly corrected.
# 2026-10-18 warned: "repairing this LOWERS the stale count, and the ratchet
# fails UNDER budget by design -- so STALE_SUITE_BUDGET must be lowered in the
# same commit."  Measured: the per-report count moves 49 -> 48 and the
# beside-a-RUNNER figure 48 -> 47, but the number the ratchet actually reads
# -- suites with a runner and NO CURRENT REPORT -- is 5 before and 5 after,
# on the same five directories.  STALE_SUITE_BUDGET is NOT lowered, and
# control P4 pins that equality so that a future change which does move it
# cannot move it unnoticed.  The warning was about the right risk and the
# wrong number.

_COMMENT_LINE_RE = re.compile(r'^[ \t]*#')


_CODE_CACHE = {}


def code_only(text):
    """`text` with whole-line # comments removed.  See the note above."""
    if text not in _CODE_CACHE:
        _CODE_CACHE[text] = '\n'.join(
            ln for ln in text.splitlines()
            if not _COMMENT_LINE_RE.match(ln))
    return _CODE_CACHE[text]


_READ_CACHE = {}


def _read(rel):
    """Cached because the relations are computed per (runner, report) pair and
    re-read the same scripts hundreds of times.  The tree does not change
    during a run; a run that mutated it would be reading its own output."""
    if rel not in _READ_CACHE:
        try:
            with open(os.path.join(ROOT, rel), errors='replace') as fh:
                _READ_CACHE[rel] = fh.read()
        except OSError:
            _READ_CACHE[rel] = ''
    return _READ_CACHE[rel]


def named_paths(rel, d, tracked):
    """(code_edges, prose_edges, unresolved) for one script.

    prose_edges are resolved paths this file names ONLY in whole-line
    comments.  The two sets are disjoint by construction and control P1
    requires it of the whole repository.
    """
    txt = _read(rel)
    def resolve_all(t):
        out, unres = set(), set()
        for cand in PATH_RE.findall(t):
            for res in _resolve(cand, d, tracked):
                out.add(res)
                break
            else:
                if '/' in cand:
                    unres.add(cand)
        return out, unres
    allp, unres = resolve_all(txt)
    codep, _ = resolve_all(code_only(txt))
    return codep, allp - codep, unres


# ---------------------------------------------------------------------------
# THE CALLER RELATION, which now requires an INVOCATION
# ---------------------------------------------------------------------------
# A caller is a file that RUNS the script.  Three forms exist here and all
# three are real:
#
#     an exec verb        bash X / sh X / source X / . X / exec X / python3 X
#                         (timeout 300 bash X reaches it through the verb)
#     a manifest record   X|KIND|requires|budget|note   -- tools/run_all_
#                         harnesses.sh drives everything from such a table and
#                         then runs `bash "$path"`, so the record IS the call
#     a subprocess call   subprocess.run([... 'X' ...]) and relatives
#
# A BARE BASENAME IS CREDITED ONLY WHEN IT IS UNIQUE IN THE REPOSITORY.  When
# six files share it, `bash run_mutation_tests.sh` does not say which one, and
# resolving it to all six is mechanism (1).  Such a reference becomes a third
# value, AMBIGUOUS: reported, never credited.  Guessing would be the sibling
# repository's resolve-on-spelling again -- a question about identity answered
# by a test on text.
#
# mentions_of() keeps the old relation and is printed as the UPPER BOUND, so
# the artefact stays visible rather than being replaced by a smaller number
# nobody can check against the old one.

_EXEC_VERB = r'(?:bash|sh|zsh|ksh|source|\.|exec|python3?|pytest)'
_SUBPROC = r'subprocess\.(?:run|call|check_call|check_output|Popen)'


def _invocation_patterns(spelling):
    q = re.escape(spelling)
    return (
        # an exec verb, possibly via timeout/env, then the path
        re.compile(r'(?:^|[;&|(]|\&\&|\|\|)\s*'
                   r'(?:timeout\s+\S+\s+|env\s+\S+\s+)*'
                   + _EXEC_VERB + r'\s+(?:-\S+\s+)*'
                   r'["\']?(?:\$\{?(?:ROOT|HERE|REPO|TOP|DIR|BASE)\}?/)?'
                   + q + r'["\']?(?:\s|$|["\';&|)])', re.M),
        # ./path or "$DIR"/path executed directly
        re.compile(r'(?:^|[;&|(]|\&\&|\|\|)\s*'
                   r'["\']?(?:\./|\$\{?(?:ROOT|HERE|REPO|TOP|DIR|BASE)\}?/)'
                   + q + r'["\']?(?:\s|$|["\';&|)])', re.M),
        # a manifest record: the path is the first field of a |-table line
        re.compile(r'^' + q + r'\|', re.M),
        # subprocess, anywhere in the call's argument text
        re.compile(_SUBPROC + r'\s*\((?:[^()]|\([^()]*\))*?' + q,
                   re.S),
    )


def _invokes(text, spelling):
    """Does `text`, ALREADY stripped of comments, invoke `spelling`?"""
    return any(p.search(text) for p in _invocation_patterns(spelling))


def _invokes_in(text, spelling):
    """Does raw `text` invoke `spelling`?

    WHAT THIS STRIP DOES AND DOES NOT CATCH, measured rather than assumed --
    the first draft of control I6 asserted the wrong case and the predicate
    was right.

    A plain usage comment, `#   bash tools/run_all_harnesses.sh --list`, is
    ALREADY not an invocation without this strip: the exec verb must sit at a
    statement boundary, and a leading `#` is not one.  So I6's first draft
    required the strip to make the difference on that line, it made no
    difference, and the draft would have passed against a predicate with no
    strip at all.

    The strip is load-bearing for a comment that contains a shell operator
    BEFORE the verb, because the operator is a statement boundary:

        # to re-run: cat seeds | bash examples/.../run_mutation_tests.sh
        # then: cd x && bash examples/.../run_mutation_tests.sh
        # note; bash examples/.../run_mutation_tests.sh was removed

    all three of which match the invocation patterns unstripped and none of
    which runs anything.  Mutant M6 of 2026-10-20 -- dropping this strip --
    escaped the whole suite twice, first against the tree (no such line
    exists in it today) and then against I6's first draft.  Those are the
    three shapes it is pinned on now."""
    return _invokes(code_only(text), spelling)


def basename_is_unique(rel_script, files):
    base = os.path.basename(rel_script)
    return len([f for f in files if os.path.basename(f) == base]) == 1


def invocations_of(rel_script, files):
    """Files that actually RUN rel_script.  (callers, ambiguous)

    Its own file is excluded, as before -- the 2026-10-10 rule that a control
    must not read the thing it controls for.
    """
    base = os.path.basename(rel_script)
    unique = basename_is_unique(rel_script, files)
    callers, ambiguous = [], []
    for f in files:
        if f == rel_script or not f.endswith(('.sh', '.py', '.yml', '.yaml')):
            continue
        raw = _read(f)
        if _invokes_in(raw, rel_script):
            callers.append(f)
        elif _invokes_in(raw, base):
            (callers if unique else ambiguous).append(f)
    return callers, ambiguous


def mentions_of(rel_script, files):
    """The 2026-10-18 relation, kept as the reported UPPER BOUND."""
    base = os.path.basename(rel_script)
    hits = []
    for f in files:
        if f == rel_script or not f.endswith(('.sh', '.py', '.yml', '.yaml')):
            continue
        text = _read(f)
        if rel_script in text or base in text:
            hits.append(f)
    return hits


def callers_of(rel_script, files):
    """Back-compatible name: the TIGHT relation's credited callers only."""
    return invocations_of(rel_script, files)[0]


# ---------------------------------------------------------------------------
# The audit
# ---------------------------------------------------------------------------

class Row(object):
    def __init__(self, report, stated, newer, undated, unresolved,
                 runners, callers, ambiguous=None, mentions=None):
        self.report = report
        self.stated = stated
        self.newer = newer                # [(rel, date)] committed after stated
        self.undated = undated            # [rel] no datable history
        self.unresolved = unresolved
        self.runners = runners
        self.callers = callers            # TIGHT: things that INVOKE
        self.ambiguous = ambiguous or {}  # bare-basename, not attributable
        self.mentions = mentions or {}    # UPPER BOUND: things that NAME

    @property
    def stale(self):
        return bool(self.newer)

    @property
    def unreachable(self):
        # No runner in the directory, or no runner anything INVOKES.  The
        # tight relation is deliberate: before 2026-10-20 this read the
        # mention relation, under which six sibling run_mutation_tests.sh
        # scripts made each other look reachable.
        return not self.runners or not any(self.callers.get(r)
                                           for r in self.runners)

    @property
    def unreachable_by_mention(self):
        """The same question under the 2026-10-18 relation, kept so the two
        numbers can be compared instead of one replacing the other."""
        return not self.runners or not any(self.mentions.get(r)
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
        callers, ambiguous = {}, {}
        for r in runners:
            callers[r], ambiguous[r] = invocations_of(r, files)
        mentions = {r: mentions_of(r, files) for r in runners}
        row = Row(rel, stated, sorted(newer, key=lambda t: t[1], reverse=True),
                  undated, unresolved, runners, callers, ambiguous, mentions)
        row.prose = _PROSE_EDGES.get(rel, [])
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
    print('  UNREACHABLE (nothing INVOKES the runner): %d' % len(unreach))
    print('  BOTH: %d   <- the 2026-10-14 failure mode exactly' % len(both))

    # THE TWO CALLER RELATIONS, SIDE BY SIDE.  The tight one is the verdict;
    # the mention relation is the 2026-10-18 behaviour, reported as the upper
    # bound so the correction is checkable against the number it replaced
    # rather than simply appearing as a smaller figure.
    um = [r for r in rows if r.unreachable_by_mention]
    print('  UNREACHABLE under the 2026-10-18 MENTION relation (upper bound,')
    print('        counts a file that merely NAMES the runner): %d' % len(um))
    amb = sorted({a for r in rows for v in r.ambiguous.values() for a in v})
    print('  BARE-BASENAME references that name no single script (AMBIGUOUS,')
    print('        reported and never credited as a caller): %d' % len(amb))
    prose_all = sorted({e for r in rows for e in getattr(r, 'prose', [])})
    print('  PROSE dependency edges held out of the tight closure (a path a')
    print('        script names only in a comment): %d' % len(prose_all))
    for e in prose_all[:8]:
        print('        %s' % e)

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
            a = r.ambiguous.get(x) or []
            m = r.mentions.get(x) or []
            print('           %s <- %s'
                  % (os.path.basename(x),
                     ', '.join(c) if c else 'NOTHING INVOKES IT'))
            extra = [f for f in m if f not in c]
            if extra:
                print('               names it but does not run it (%d): %s'
                      % (len(extra), ', '.join(extra[:5])))
            if a:
                print('               AMBIGUOUS bare-basename refs: %s'
                      % ', '.join(a[:5]))
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

    # C6  CALLER DETECTION EXCLUDES THE SCRIPT ITSELF, under BOTH relations.
    #     Every mutation runner names its own path in its usage text, so
    #     counting self-references would make all of them look reachable --
    #     the 2026-10-10 rule.  Checked for the mention relation too, because
    #     that one is still reported as the upper bound and an upper bound
    #     that counts self-reference is not a bound on anything.
    allrunners = [f for f in files if f.endswith('run_mutation_tests.sh')]
    selfnamers = [f for f in allrunners if f not in callers_of(f, files)]
    selfmention = [f for f in allrunners if f not in mentions_of(f, files)]
    check('C6 neither relation counts a script as its own caller',
          len(selfnamers) == len(allrunners)
          and len(selfmention) == len(allrunners),
          'tight %d/%d, mention %d/%d excluded from their own sets'
          % (len(selfnamers), len(allrunners),
             len(selfmention), len(allrunners)))

    # -----------------------------------------------------------------------
    # 2026-10-20: the controls for the two corrected relations
    # -----------------------------------------------------------------------
    # I4 plants its cases as TEXT passed to the predicate, not as files in the
    # tree.  Writing a file containing `bash examples/.../run_mutation_tests.sh`
    # into this repository would make that file a real caller of a real runner
    # and would be read by every other audit here -- the sibling repository's
    # 2026-10-17 item, "a module must not plant the pattern it censuses in the
    # tree other audits read", which this file can simply avoid.

    # I1  THE MANIFEST IS AN INVOCATION, against an exactly known target: the
    #     set of HARNESS paths parsed independently out of the shell file.  If
    #     the new relation cannot see the table that actually drives every run
    #     in this repository, it reports the entire repository unreachable --
    #     a failure far worse than the artefact it replaces, so it is pinned
    #     to the manifest's own contents rather than to a count.
    man = _read('tools/run_all_harnesses.sh')
    declared = [ln.split('|')[0] for ln in man.splitlines()
                if '|HARNESS|' in ln and not ln.lstrip().startswith('#')]
    declared = [x for x in declared if x in set(files)]
    seen_by_relation = [x for x in declared
                        if 'tools/run_all_harnesses.sh' in callers_of(x, files)]
    check('I1 the manifest in run_all_harnesses.sh is recognised as invoking '
          'all %d HARNESS paths it declares' % len(declared),
          len(declared) > 0 and len(seen_by_relation) == len(declared),
          'missed: %s' % (', '.join(x for x in declared
                                    if x not in seen_by_relation) or 'none'))

    # I2  THE ARTEFACT IS GONE AND STILL VISIBLE.  Exactly known target: the
    #     sibling run_mutation_tests.sh scripts.  None may be a caller of
    #     another under the tight relation, and the mention relation must
    #     still list them -- otherwise this control would pass equally well
    #     against a relation that had simply stopped finding anything.
    sibs = sorted(f for f in files if f.endswith('run_mutation_tests.sh'))
    cross = [(a, b) for a in sibs for b in sibs
             if a != b and b in callers_of(a, files)]
    mention_cross = [(a, b) for a in sibs for b in sibs
                     if a != b and b in mentions_of(a, files)]
    check('I2 none of the %d sibling run_mutation_tests.sh scripts is a '
          'caller of another, while the mention relation still shows %d such '
          'pairs' % (len(sibs), len(mention_cross)),
          len(sibs) >= 6 and not cross and len(mention_cross) >= 20,
          'tight cross-pairs: %s' % (cross[:3] or 'none'))

    # I3  AN AUDITOR READS AND NAMES; IT DOES NOT RUN.  These three name
    #     harness scripts by construction -- enumerating them is their job --
    #     and under the 2026-10-18 relation that made them callers of
    #     everything they enumerate.
    auditors = ['tools/harness_file_closure_audit.py',
                'tools/report_provenance_audit.py',
                'tools/shared_scratch_audit.py']
    runners = sorted(f for f in files
                     if os.path.basename(f).startswith('run_')
                     and f.endswith(('.sh', '.py')))
    wrong = [(a, r) for r in runners for a in auditors
             if a in callers_of(r, files)]
    check('I3 no auditor is credited as a caller of any of the %d runners'
          % len(runners), not wrong, 'credited: %s' % (wrong[:3] or 'none'))

    # I4  THE PREDICATE FIRES AND REFRAINS, on planted text.  A control that
    #     cannot fail certifies nothing (2026-10-01).
    tgt = 'examples/phase6_crv_uart/run_mutation_tests.sh'
    must_fire = [
        'bash %s' % tgt,
        'sh %s\n' % tgt,
        'source "%s"' % tgt,
        'timeout 300 bash "$ROOT/%s"' % tgt,
        './%s --quick' % tgt,
        '%s|HARNESS|-|300|note' % tgt,
        "subprocess.run(['bash', '%s'], check=True)" % tgt,
        'cd x && bash %s' % tgt,
    ]
    must_refrain = [
        '# %s after the first was found by hand' % tgt,
        'echo "see %s for the method"' % tgt,
        '# superseded by %s' % tgt,
        'A report sits beside %s and nothing re-runs it.' % tgt,
    ]
    fired = [t for t in must_fire if _invokes(code_only(t), tgt)]
    refrained = [t for t in must_refrain if not _invokes(code_only(t), tgt)]
    check('I4 the invocation predicate fires on %d/%d real invocations and '
          'refrains on %d/%d prose references'
          % (len(fired), len(must_fire), len(refrained), len(must_refrain)),
          len(fired) == len(must_fire) and len(refrained) == len(must_refrain),
          'missed: %r  false: %r'
          % ([t for t in must_fire if t not in fired],
             [t for t in must_refrain if t not in refrained]))

    # I5  A BARE BASENAME SHARED BY SIX FILES IS NOT ATTRIBUTED.  The third
    #     value exists only if it is exercised; an unexercised third value is
    #     a comment (2026-10-01).
    shared_base = 'run_mutation_tests.sh'
    nshare = len([f for f in files if os.path.basename(f) == shared_base])
    uniq_script = 'tools/report_provenance_audit.py'
    check('I5 %r is shared by %d tracked files and so is NOT unique, while '
          'a one-of-a-kind script IS' % (shared_base, nshare),
          nshare >= 6
          and not basename_is_unique('examples/phase6_crv_uart/' + shared_base,
                                     files)
          and basename_is_unique(uniq_script, files))

    # I6  AN EXEC VERB INSIDE A COMMENT IS NOT A CALL -- on the three shapes
    #     for which the comment strip is actually load-bearing, which are not
    #     the shape this control's first draft used.  See _invokes_in() for
    #     the measurement and for mutant M6's two escapes.  Each of these
    #     matches the invocation patterns when the comment is NOT stripped,
    #     so the control fails the moment the strip is removed.
    prose_calls = [
        '# to re-run: cat seeds | bash %s' % tgt,
        '# then: cd x && bash %s' % tgt,
        '# note; bash %s was removed' % tgt,
    ]
    leaks = [c for c in prose_calls if _invokes_in(c, tgt)]
    unstripped_would_leak = [c for c in prose_calls if _invokes(c, tgt)]
    real = 'cd "$ROOT" || exit 1\nbash %s\n' % tgt
    check('I6 none of the %d prose shapes carrying a shell operator is '
          'credited as a call, while a real invocation is'
          % len(prose_calls),
          not leaks and _invokes_in(real, tgt)
          and len(unstripped_would_leak) == len(prose_calls),
          'leaked: %r; without the strip %d/%d would leak'
          % (leaks, len(unstripped_would_leak), len(prose_calls)))

    # P1  CODE AND PROSE EDGES ARE DISJOINT, repository-wide.  Where two
    #     causes produce the same symptom they are two reported categories
    #     with a disjointness check between them (2026-10-17).
    overlap = []
    tracked = set(files)
    for f in files:
        if not f.endswith(('.sh', '.py')):
            continue
        c, pr, _u = named_paths(f, os.path.dirname(f), tracked)
        if c & pr:
            overlap.append((f, sorted(c & pr)))
    check('P1 the CODE and PROSE edge sets are disjoint for all %d scripts'
          % len([f for f in files if f.endswith(('.sh', '.py'))]),
          not overlap, 'overlapping: %s' % (overlap[:2] or 'none'))

    # P2  THE EXACT EDGE 2026-10-18 CALLED UNREAL IS CLASSIFIED PROSE, and is
    #     gone from the bench's tight closure while remaining in the
    #     directory closure.  Exactly known, not a count.
    bench = 'examples/phase6_baud_error_coverage'
    auditor = 'tools/harness_file_closure_audit.py'
    runner = bench + '/run_mutation_tests.sh'
    c, pr, _u = named_paths(runner, bench, tracked)
    reps = [(r, d) for r, d in reports(files) if os.path.dirname(r) == bench]
    newest = max(reps, key=lambda t: t[1])[0] if reps else None
    tight_deps = set(closure_for(newest, files, tight=True)[0]) if newest else set()
    wide_deps = set(closure_for(newest, files, tight=False)[0]) if newest else set()
    check('P2 the baud bench names %s only in prose, and it is out of the '
          'tight closure and still in the directory closure' % auditor,
          auditor in pr and auditor not in c
          and auditor not in tight_deps and auditor in wide_deps,
          'prose=%s code=%s tight=%s wide=%s'
          % (auditor in pr, auditor in c,
             auditor in tight_deps, auditor in wide_deps))

    # P3  THE UNDER-REPORT GUARD, and its FIRST DRAFT ASSERTED A FALSEHOOD.
    #     The draft required every mutation suite's closure to contain
    #     rtl/uart_controller.v and tools/mutation_controls.sh.  It FAILED on
    #     three suites -- and the three absences are CORRECT:
    #     phase6_bfm_equivalence mutates bfm/uart_rx_pin_bfm.v and not the
    #     DUT at all, and phase6_crv_uart and phase6_uvm_crv_uart carry their
    #     own controls and never source the shared ones.  Measured before and
    #     after the comment-strip, all three absences are IDENTICAL, so the
    #     change did not cause them.
    #
    #     The universal was plausible and wrong; the conditional is the thing
    #     actually at risk.  Every path a script names IN CODE must survive
    #     into the closure -- i.e. the strip removed no edge that code spells.
    missing = []
    _dirclosure = {}
    for f in files:
        if not f.endswith(('.sh', '.py')):
            continue
        d = os.path.dirname(f)
        if d not in _dirclosure:
            _dirclosure[d] = set(closure_for(f, files, tight=False)[0])
        c, _pr, _u = named_paths(f, d, tracked)
        for dep in sorted(c - _dirclosure[d]):
            missing.append((f, dep))
    check('P3 every edge a script spells IN CODE survives into its closure '
          '(the strip cannot under-report)',
          not missing, 'dropped: %s' % (missing[:3] or 'none'))

    # P4  THE NUMBER THE RATCHET READS DID NOT MOVE, which contradicts the
    #     2026-10-18 warning that this repair would lower it and force
    #     STALE_SUITE_BUDGET down.  Pinned as an equality so that a future
    #     change which does move it cannot move it unnoticed, and so that the
    #     budget in tools/run_all_harnesses.sh and this file cannot drift.
    rows_now = audit()
    bydir = {}
    for r in rows_now:
        dd = os.path.dirname(r.report)
        if dd not in bydir or r.stated > bydir[dd].stated:
            bydir[dd] = r
    not_current = [d for d, r in sorted(bydir.items()) if r.runners and r.stale]
    budget = None
    m = re.search(r'^STALE_SUITE_BUDGET=(\d+)', man, re.M)
    if m:
        budget = int(m.group(1))
    check('P4 the per-suite headline is %d, equal to STALE_SUITE_BUDGET=%s -- '
          'the 2026-10-18 warning that this repair lowers it is not borne out'
          % (len(not_current), budget),
          budget is not None and len(not_current) == budget,
          'suites: %s' % ', '.join(not_current))


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
