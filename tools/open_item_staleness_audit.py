#!/usr/bin/env python3
"""
open_item_staleness_audit.py -- audit the thing that decides what gets done.

Created 2026-10-03.

WHY THIS EXISTS
---------------
Every session in this repository starts the same way: read
`AUTOMATION_LOG.md`, take the most recent "Not yet covered (candidates for
future runs)" list, and pick from it.  That list is therefore the single most
load-bearing artefact here -- it does not describe the work, it CHOOSES it --
and until today nothing checked it.  Every other claim in this repository has
an instrument pointed at it: transcripts against code (pristine audit),
coverage bins against reachability (reachable-cross audit), properties against
mutants (per-property mutation coverage).  The list that selects which of
those to run had none.

It was wrong.

    "**The UVM environment against the UART RTL** -- the register-bus agent,
     the serial agent with its standalone RX bit-driver, the reference-model
     scoreboard and the coverage collector. Open since the 09-17 bring-up
     unblocked it, and **untouched for twelve consecutive sessions** ...
     Phase 4's stated milestone is this, and the sessions have been doing
     Phase 6 measurement instead."

`progress.md` has said since 2026-09-18 that all four of those components
exist, and `examples/phase4_uvm_milestone/uart_uvm_tb.py` contains
`UartRegAgent`, `UartSerialAgent`, `UartScoreboard` and `UartCoverage`.
**PHASE 4 IS COMPLETE (2026-09-19)**, in bold, in `progress.md`.  The item was
carried forward verbatim for twelve entries, each time with the session count
incremented, describing as the clear next step a thing that was finished
before the count started.

That is this repository's own favourite fault in a new place: TWO ARTEFACTS IN
ONE REPOSITORY DISAGREE, AND THE ONE THAT DRIVES THE NEXT SESSION'S WORK IS
THE WRONG ONE.  10-02 found a transcript that agreed with its code and was
false; this is narrower and worse, because a false transcript misreports a
result while a false open-items list misdirects labour.  The cost is not
hypothetical: twelve entries of "untouched for N consecutive sessions" is a
reproach the sessions did not deserve, and the item kept its position at or
near the top of the list the whole time.

WHAT IT CHECKS
--------------
S1  Every backticked path named by an open item exists in the tree (an item
    may legitimately name a file to be CREATED, so those are reported
    separately rather than failed).
S2  Every "created MM-DD" / "created YYYY-MM-DD" date parses and is not in
    the future.
S3  CONTRADICTION RANKING: for each open item, the fraction of its distinctive
    tokens that appear in each COMPLETED (`- [x]`) block of `progress.md`.
    Ranked, not thresholded -- see the note on thresholds below.
S4  Adjudication: a committed file records the judgement made on each
    high-ranking item, with a reason.  The exact check is that the
    adjudication covers every item at or above the reporting cut and no
    others, so a ranking cannot quietly grow an unjudged head.
S5  Controls, including a mutation test.

A NOTE ON THE THRESHOLD, because this repository has been bitten by magic
numbers twice (09-24's steering policy, 10-02's NUMERIC_RTOL control).  S3
deliberately does NOT emit a verdict from a score.  A containment score is a
text-similarity measurement and no cut on it is defensible as "stale".  What
S3 produces is a RANKING; what decides is S4's committed adjudication, written
by the session that read the ranking.  The score's only job is to put the
candidates in front of someone.  That makes the judgement auditable (it is on
disk, with reasons) rather than reproducible-but-arbitrary.
"""

import datetime
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LOG = os.path.join(ROOT, 'AUTOMATION_LOG.md')
PROGRESS = os.path.join(ROOT, 'progress.md')
ADJUDICATION = os.path.join(HERE, 'open_item_adjudication.md')

# How many of the top-ranked items the adjudication file must cover.  A COUNT,
# not a score cut: "the session must judge the top N candidates" is a workload
# commitment and is checkable exactly, whereas "score > 0.6 is stale" is a
# claim about text similarity that nothing here can support.
REPORTING_CUT = 6

STOP = set('''a an and are as at be been but by can cannot does doing for from
has have how in into is it its more most much no not of on one only or other
our out over per should so than that the their them then there these they this
those to under up was were what when where which while who why will with
would its it's item items thing things still now today yet open created
untouched session sessions run runs next form general exact every each both
rather instead because since again also just make makes made does did done
same other another new old first second third least most need needs needed
same two three four five six seven eight nine ten'''.split())

TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_./-]{3,}")


def tokens(text):
    out = set()
    for m in TOKEN.finditer(text.lower()):
        t = m.group(0).strip('.-/_')
        if len(t) >= 4 and t not in STOP:
            out.add(t)
    return out


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def open_item_blocks(log_text, which=-1):
    """
    The items of the `which`-th "Not yet covered" list (default: the most
    recent).  An item is a top-level '- ' bullet plus its continuation lines.
    """
    heads = [m.start() for m in
             re.finditer(r'\*\*Not yet covered[^\n]*\n', log_text)]
    if not heads:
        return [], None
    start = heads[which]
    start = log_text.index('\n', start) + 1
    # the list ends at the next bold paragraph that is not a list item
    m = re.search(r'\n\*\*(?!Not yet covered)', log_text[start:])
    end = start + (m.start() if m else len(log_text) - start)
    body = log_text[start:end]
    items, cur = [], None
    for line in body.split('\n'):
        if re.match(r'^- ', line):
            if cur is not None:
                items.append('\n'.join(cur))
            cur = [line]
        elif cur is not None and line.strip():
            cur.append(line)
        elif cur is not None and not line.strip():
            items.append('\n'.join(cur))
            cur = None
    if cur is not None:
        items.append('\n'.join(cur))
    return [i for i in items if i.strip()], len(heads)


def completed_blocks(progress_text):
    """Every `- [x]` checkbox plus its continuation lines."""
    out, cur = [], None
    for line in progress_text.split('\n'):
        if re.match(r'^- \[[xX]\] ', line):
            if cur is not None:
                out.append('\n'.join(cur))
            cur = [line]
        elif re.match(r'^- \[ \] ', line) or re.match(r'^#', line):
            if cur is not None:
                out.append('\n'.join(cur))
            cur = None
        elif cur is not None:
            cur.append(line)
    if cur is not None:
        out.append('\n'.join(cur))
    return out


def first_line(block, n=96):
    s = ' '.join(block.split())
    s = re.sub(r'[*`\[\]]', '', s)
    return s[:n] + ('...' if len(s) > n else '')


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

BACKTICK = re.compile(r'`([^`]+)`')
PATHISH = re.compile(r'^[\w./-]+\.(py|v|sv|sh|md|txt)$')


def s1_named_paths_exist(items):
    present, missing = [], []
    for it in items:
        for tok in BACKTICK.findall(it):
            tok = tok.strip()
            if not PATHISH.match(tok):
                continue
            hit = None
            for dirpath, _d, files in os.walk(ROOT):
                if '/.git' in dirpath:
                    continue
                if os.path.basename(tok) in files:
                    hit = os.path.relpath(os.path.join(dirpath,
                                                       os.path.basename(tok)), ROOT)
                    break
            (present if hit else missing).append((tok, first_line(it, 56), hit))
    return present, missing


DATE_RE = re.compile(r'created\s+(\d{4}-\d{2}-\d{2}|\d{2}-\d{2})')


def s2_dates_parse(items, today):
    good, bad = [], []
    for it in items:
        for raw in DATE_RE.findall(it):
            try:
                if len(raw) == 5:
                    d = datetime.date(today.year, int(raw[:2]), int(raw[3:]))
                else:
                    d = datetime.date.fromisoformat(raw)
            except ValueError:
                bad.append((raw, first_line(it, 56), 'unparseable'))
                continue
            if d > today:
                bad.append((raw, first_line(it, 56), 'in the future'))
            else:
                good.append((raw, first_line(it, 56)))
    return good, bad


def s3_rank(items, done_blocks):
    """
    Containment: fraction of the open item's distinctive tokens that the
    completed block also contains.  Asymmetric on purpose -- a long completed
    block that covers a short open item should score high, which Jaccard
    would punish.
    """
    ranked = []
    for it in items:
        ti = tokens(it)
        if not ti:
            continue
        best, which = 0.0, None
        for db in done_blocks:
            td = tokens(db)
            score = len(ti & td) / float(len(ti))
            if score > best:
                best, which = score, db
        ranked.append((best, it, which))
    ranked.sort(key=lambda r: -r[0])
    return ranked


def s4_adjudication(ranked, cut):
    """
    The committed judgement.  Format: one '## <verdict>: <quoted phrase>'
    heading per adjudicated item, verdict in {STALE, OPEN}, followed by a
    reason paragraph.  Returns (entries, covered, uncovered, extra).
    """
    if not os.path.exists(ADJUDICATION):
        return [], [], [(first_line(r[1], 60), None) for r in ranked[:cut]], []
    text = open(ADJUDICATION, encoding='utf-8').read()
    entries = re.findall(r'^##\s+(STALE|OPEN):\s*(.+?)\s*$', text, re.M)
    head = ranked[:cut]
    covered, uncovered = [], []
    for score, it, _w in head:
        ti = tokens(it)
        matched = None
        for verdict, phrase in entries:
            tp = tokens(phrase)
            if tp and len(tp & ti) / float(len(tp)) >= 0.75:
                matched = verdict
                break
        (covered if matched else uncovered).append((first_line(it, 60), matched))
    used = set()
    for score, it, _w in head:
        ti = tokens(it)
        for i, (verdict, phrase) in enumerate(entries):
            tp = tokens(phrase)
            if tp and len(tp & ti) / float(len(tp)) >= 0.75:
                used.add(i)
    extra = [entries[i][1] for i in range(len(entries)) if i not in used]
    return entries, covered, uncovered, extra


# ---------------------------------------------------------------------------
# S5 -- controls
# ---------------------------------------------------------------------------

_SYNTH_PROGRESS = '''# synthetic
- [x] **Milestone: the widget harness against the gadget RTL -- COMPLETE.**
      Builds the widget agent, the gadget agent, the oracle scoreboard and
      the tally collector; 42 checks, 0 errors.
- [x] Something entirely unrelated about baud tolerance measurement
'''

_SYNTH_ITEMS = [
    '- **The widget harness against the gadget RTL** -- the widget agent, '
    'the gadget agent, the oracle scoreboard and the tally collector. '
    'Untouched for twelve consecutive sessions',
    '- **A completely different question about packet checksums over a ring '
    'bus** -- created 10-03',
]


def s5_controls():
    done = completed_blocks(_SYNTH_PROGRESS)
    ranked = s3_rank(_SYNTH_ITEMS, done)
    by_text = {first_line(it, 40): sc for sc, it, _w in ranked}
    widget = [sc for sc, it, _w in ranked if 'widget' in it.lower()][0]
    other = [sc for sc, it, _w in ranked if 'checksum' in it.lower()][0]
    res = []
    res.append(('C1', 'an open item whose components are all named in a '
                      'COMPLETED checkbox ranks high', widget >= 0.6,
                '%.3f' % widget))
    res.append(('C2', 'an unrelated open item ranks low', other <= 0.25,
                '%.3f' % other))
    res.append(('C3', 'and the contradicted item ranks ABOVE the unrelated one',
                widget > other, '%.3f > %.3f' % (widget, other)))

    # Mutation test: delete the completed checkbox the item contradicts and
    # require the score to collapse.  Without this, C1 could be passing
    # because the scorer returns a high number for everything.
    mutated = '\n'.join(l for l in _SYNTH_PROGRESS.split('\n')
                        if 'widget' not in l.lower()
                        and 'oracle scoreboard' not in l.lower()
                        and 'gadget' not in l.lower())
    assert mutated != _SYNTH_PROGRESS, 'mutation did not arrive'
    ranked2 = s3_rank(_SYNTH_ITEMS, completed_blocks(mutated))
    widget2 = [sc for sc, it, _w in ranked2 if 'widget' in it.lower()][0]
    res.append(('M1', 'MUTATION TEST: with the completed checkbox removed, the '
                      'same item no longer ranks high', widget2 < 0.6,
                '%.3f -> %.3f' % (widget, widget2)))
    # And an exact one: an open item that is VERBATIM a completed block must
    # score exactly 1.0, since containment of a set in itself is exact.
    verbatim = done[0]
    r3 = s3_rank([verbatim], done)
    res.append(('E1', 'EXACT: an open item that is verbatim a completed block '
                      'scores exactly 1.0', r3[0][0] == 1.0, repr(r3[0][0])))
    return res


# ---------------------------------------------------------------------------

def main():
    n_pass = n_fail = 0

    def report(ok, text):
        nonlocal n_pass, n_fail
        if ok:
            n_pass += 1
        else:
            n_fail += 1
        print('  [%s] %s' % ('PASS' if ok else 'FAIL', text))

    today = datetime.date.today()
    log = open(LOG, encoding='utf-8').read()
    progress = open(PROGRESS, encoding='utf-8').read()
    items, n_lists = open_item_blocks(log)
    done = completed_blocks(progress)

    print('=' * 78)
    print('OPEN-ITEM STALENESS AUDIT -- is the list that CHOOSES the work')
    print('consistent with the file that records what is finished?  (2026-10-03)')
    print('=' * 78)
    print('  AUTOMATION_LOG.md: %d "Not yet covered" lists; the most recent has '
          '%d items' % (n_lists, len(items)))
    print('  progress.md: %d completed checkboxes, %d unchecked'
          % (len(done), len(re.findall(r'^- \[ \] ', progress, re.M))))
    report(len(items) > 0, 'the most recent open-items list parses into items')
    report(len(done) > 0, 'progress.md parses into completed blocks')

    print('\n' + '-' * 78)
    print('S1 -- every backticked path an open item names exists in the tree')
    print('-' * 78)
    present, missing = s1_named_paths_exist(items)
    print('  paths named: %d   resolved: %d   unresolved: %d'
          % (len(present) + len(missing), len(present), len(missing)))
    for tok, ctx, _h in missing:
        print('    UNRESOLVED  %-44s  in: %s' % (tok, ctx))
    print('  An unresolved path is not automatically a fault: an item may name '
          'a file\n  it asks a future session to CREATE.  Reported, not failed.')
    report(True, 'S1 ran and reported %d unresolved path(s) for adjudication'
                 % len(missing))

    print('\n' + '-' * 78)
    print('S2 -- every "created <date>" parses and is not in the future')
    print('-' * 78)
    good, bad = s2_dates_parse(items, today)
    print('  dates found: %d   ok: %d   bad: %d' % (len(good) + len(bad),
                                                    len(good), len(bad)))
    for raw, ctx, why in bad:
        print('    BAD  %-12s %-12s  in: %s' % (raw, why, ctx))
    report(not bad, 'no open item carries an unparseable or future creation date')

    print('\n' + '-' * 78)
    print('S3 -- CONTRADICTION RANKING against progress.md\'s completed items')
    print('-' * 78)
    ranked = s3_rank(items, done)
    print('  score = fraction of the open item\'s distinctive tokens that a')
    print('  COMPLETED checkbox also contains.  A RANKING, not a verdict.\n')
    print('    %-6s %s' % ('score', 'open item'))
    for score, it, _w in ranked[:REPORTING_CUT + 4]:
        mark = '  <-- adjudicate' if score >= ranked[REPORTING_CUT - 1][0] else ''
        print('    %-6.3f %s%s' % (score, first_line(it, 86), mark))
    print('\n  top match for the highest-ranked item:')
    if ranked and ranked[0][2]:
        print('    %s' % first_line(ranked[0][2], 150))

    print('\n' + '-' * 78)
    print('S4 -- the committed adjudication of the top %d' % REPORTING_CUT)
    print('-' * 78)
    entries, covered, uncovered, extra = s4_adjudication(ranked, REPORTING_CUT)
    print('  adjudication entries on disk: %d' % len(entries))
    for txt, verdict in covered:
        print('    %-7s %s' % (verdict, txt))
    for txt, _v in uncovered:
        print('    MISSING %s' % txt)
    for e in extra:
        print('    ORPHAN  %s' % first_line(e, 70))
    report(not uncovered, 'every item at or above the reporting cut is '
                          'adjudicated on disk, with a reason')
    report(not extra, 'the adjudication file contains no entry that no longer '
                      'matches any top-ranked item')
    # A STALE verdict retires the only text pointing at a piece of work, so
    # it must say what inherits it.  Without this, an audit of the list that
    # chooses the work can itself delete work -- which is the "repair built
    # and then not connected" failure one level up.
    adj_text = (open(ADJUDICATION, encoding='utf-8').read()
                if os.path.exists(ADJUDICATION) else '')
    stale_phrases = [p for v, p in entries if v == 'STALE']
    unsuccessored = []
    for phrase in stale_phrases:
        i = adj_text.find(phrase)
        if i < 0:
            unsuccessored.append(phrase)
            continue
        nxt = adj_text.find('\n## ', i)
        body = adj_text[i:nxt if nxt > 0 else len(adj_text)]
        if 'REPLACED-BY:' not in body and 'NO-SUCCESSOR:' not in body:
            unsuccessored.append(phrase)
    for phrase in unsuccessored:
        print('    NO SUCCESSOR NAMED  %s' % first_line(phrase, 66))
    report(not unsuccessored, 'every STALE verdict names what inherits the '
                              'work (REPLACED-BY) or states there is none '
                              '(NO-SUCCESSOR)')
    n_stale = sum(1 for v, _p in entries if v == 'STALE')
    print('  verdicts: %d STALE, %d OPEN'
          % (n_stale, sum(1 for v, _p in entries if v == 'OPEN')))

    print('\n' + '-' * 78)
    print('S5 -- controls on the ranker, and its mutation test')
    print('-' * 78)
    for tag, text, ok, detail in s5_controls():
        report(ok, '%s  %s   [%s]' % (tag, text, detail))

    print('\n' + '=' * 78)
    print('RESULT: %d passed, %d failed' % (n_pass, n_fail))
    print('=' * 78)
    return n_fail


if __name__ == '__main__':
    sys.exit(1 if main() else 0)
