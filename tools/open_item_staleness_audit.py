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


def stems(text):
    """`tokens()` with a crude suffix fold, for DIAGNOSIS ONLY.

    ADDED 2026-10-17.  The exact matcher below decides whether an entry is
    matched; this one decides, for an entry it did NOT match, whether the
    cause is a WORDING difference or a genuine RETIREMENT.  It is deliberately
    not substituted for `tokens()`: loosening the matcher would make the
    verdict "adjudicated" easier to earn, which is the opposite of what this
    audit is for, and a stemmer that silently accepted `tx_empty` for
    `tx_empty_prediction` would hide exactly the kind of item drift the file
    exists to catch.  So the loose form may only ever move a row from one
    REPORTED category to another, never from FAIL to PASS.

    The fold also splits identifier-case words -- `UartCoverage` ->
    {uart, coverage} -- which is the other half of the 2026-10-17 miss:
    `uvm coverage collector` against `UartCoverage collector`.
    """
    out = set()
    # Split identifier case BEFORE lowercasing, which is the half of the
    # 2026-10-17 miss that operating on tokens() cannot recover: by the time
    # `tokens()` has run, `UartCoverage` is the single token `uartcoverage`
    # and the boundary is gone.  The first draft of this function folded
    # suffixes over tokens() output and therefore fixed `wire`/`wired` and
    # missed `uvm coverage`/`UartCoverage` -- half a repair, and it left all
    # six 2026-10-17 entries in the RETIRED column, i.e. it changed nothing
    # the check reported.
    split = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', text)
    for t in tokens(split):
        part = t
        for suf in ('ingly', 'edly', 'ing', 'ies', 'ed', 'es', 's'):
            if part.endswith(suf) and len(part) - len(suf) >= 4:
                part = part[:-len(suf)]
                break
        out.add(part)
    return out


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

# A heading is a FULL standing list only if it carries this phrase.  Every
# one of the 45 session entries up to 2026-10-27 does; the 2026-10-27
# ADDENDUM's heading -- "Not yet covered - added by this addendum, ranked:"
# -- deliberately does not, because it lists ADDITIONS and not the standing
# list.  See open_item_headings() for what that cost.
FULL_LIST_MARKER = '(candidates for future runs)'

# REPAIRED 2026-11-04, AND THIS IS THE SAME FAULT AS THE 2026-10-28 ONE,
# ARRIVING FROM THE OTHER SIDE.  10-28 fixed an audit that had locked onto a
# five-item SUPPLEMENT because it took the LAST matching heading.  The
# remedy recognised one heading shape -- "**Not yet covered ... (candidates
# for future runs):**" -- and from 2026-10-29 the log stopped using it.  The
# 10-29, 10-30, 11-02 and 11-03 entries head their standing lists
#
#     **Open items, with blockers named:**
#
# so `open_item_headings` matched nothing in any of them, `standing_list`
# fell back to the newest heading it DID recognise, and this audit has been
# auditing the 2026-10-28 list for FOUR CONSECUTIVE SESSIONS while reporting
# a clean 36/0 against it.
#
# That is the staleness this tool exists to detect, in the tool itself, and
# it is the mechanical reason the vplan v2 item (RETIRED_WORDINGS, below)
# could be re-imported on 11-03 with nothing able to see it.  Matching on a
# single literal heading made the audit's scope depend on an editorial habit
# nobody had agreed to keep.
#
# The repair is a TUPLE of accepted FULL-list headings rather than one, and
# S0 (added the same day) asserts that the list actually audited comes from
# the LAST session entry in the log -- so the next heading rename fails this
# audit loudly instead of silently narrowing it.
FULL_LIST_HEADINGS = (
    r'\*\*Not yet covered([^\n]*)\n',
    r'\*\*(Open items, with blockers named[^\n]*)\n',
)


def open_item_headings(log_text):
    """Every standing-list heading, classified FULL or SUPPLEMENT.

    REPAIRED 2026-10-28, and the fault is worth stating because it was
    introduced by a deliberate, correct editorial decision.

    The 2026-10-27 addendum chose not to be a second `## 2026-10-27` entry
    and headed its five new items "Not yet covered - added by this addendum,
    ranked:".  open_item_blocks() took the LAST such heading, so from that
    commit onward this audit stopped auditing the standing list of ~33 items
    and audited a FIVE-item supplement instead -- S1 reported 1 named path
    where the standing list names many, S2 found 0 creation dates, and then
    S3 died with IndexError because REPORTING_CUT is 6 and ranked[5] does
    not exist in a list of five.

    The committed transcript shows a complete 26/4 run, so the tree carried
    a crashing tool behind a green-looking artefact for a day -- the
    repository's recurring failure, in the one tool whose job is to notice
    that the list has drifted from the tree.
    """
    out = []
    for m in re.finditer(FULL_LIST_HEADINGS[0], log_text):
        tail = m.group(1)
        kind = 'FULL' if FULL_LIST_MARKER in tail else 'SUPPLEMENT'
        out.append((m.start(), kind, ('Not yet covered' + tail).strip()))
    for pat in FULL_LIST_HEADINGS[1:]:
        for m in re.finditer(pat, log_text):
            out.append((m.start(), 'FULL', m.group(1).strip()))
    out.sort()
    return out


def last_session_offset(log_text):
    """Byte offset of the last `## ` session heading in the log.

    S0 uses it to assert that the list being audited belongs to the NEWEST
    entry.  Added 2026-11-04 with the heading repair above, because the
    repair fixes today's two spellings and nothing stops a third.
    """
    ms = list(re.finditer(r'(?m)^## .*', log_text))
    return ms[-1].start() if ms else 0


def _items_from(log_text, head_start):
    """The '- ' bullets of the list whose heading starts at `head_start`."""
    start = log_text.index('\n', head_start) + 1
    # The list ends at the next bold paragraph.
    #
    # CORRECTED 2026-10-28, and found by the control written for something
    # else.  This read `r'\n\*\*(?!Not yet covered)'`, so a list's body ran
    # straight THROUGH a following "Not yet covered" heading and absorbed
    # the next list's bullets as its own.  In the committed log it never
    # fired, because every entry puts a `**Commits this run:**` paragraph
    # between its list and the next heading -- so the bug was latent behind
    # a formatting convention, and L2 exposed it by planting the two
    # headings adjacent.  Had it fired, standing_list() would have
    # DOUBLE-COUNTED every supplement: once inside the full list's body and
    # once as its own contribution.
    m = re.search(r'\n\*\*', log_text[start:])
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
    return [i for i in items if i.strip()]


def standing_list(log_text):
    """The standing list as of the END of the log, and how it was assembled.

    The most recent FULL list, plus every SUPPLEMENT that appears AFTER it,
    in order.  A supplement lists additions to the list above it, so the
    union is the standing list; taking the supplement alone is what broke
    this audit on 2026-10-27, and taking only the full list would now drop
    five real items including that addendum's ranked-first one.

    Returns (items, provenance), where provenance is a list of
    (kind, heading, n_items) describing each contributing list.
    """
    heads = open_item_headings(log_text)
    if not heads:
        return [], []
    full_at = [i for i, h in enumerate(heads) if h[1] == 'FULL']
    first = full_at[-1] if full_at else 0
    items, prov = [], []
    for pos, kind, heading in heads[first:]:
        got = _items_from(log_text, pos)
        items.extend(got)
        prov.append((kind, heading, len(got)))
    return items, prov


def open_item_blocks(log_text, which=None):
    """Back-compatible wrapper.

    `which=None` (the new default) returns the STANDING LIST per
    standing_list().  An integer still selects one heading's list, which is
    what the controls use to plant a single list.
    """
    heads = open_item_headings(log_text)
    if not heads:
        return [], None
    if which is None:
        items, _prov = standing_list(log_text)
        return items, len(heads)
    return _items_from(log_text, heads[which][0]), len(heads)


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


def s4_adjudication(ranked, cut, all_items=None):
    """
    The committed judgement.  Format: one '## <verdict>: <quoted phrase>'
    heading per adjudicated item, verdict in {STALE, OPEN}, followed by a
    reason paragraph.  Returns (entries, covered, uncovered, extra).
    """
    if not os.path.exists(ADJUDICATION):
        return [], [], [(first_line(r[1], 60), None) for r in ranked[:cut]], [], []
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
    # Orphan detection matches against EVERY item in the list, not just the
    # head.  An OPEN entry that has merely dropped below the cut is not an
    # orphan -- its item is still queued, it just is not one of the six the
    # session must judge.  The first form of this check compared against the
    # head only and reported a correctly-adjudicated OPEN item as an orphan
    # the moment the list reordered; that is a check whose verdict depends on
    # a ranking position rather than on existence.
    pool = all_items if all_items is not None else [it for _s, it, _w in ranked]
    used = set()
    for it in pool:
        ti = tokens(it)
        for i, (verdict, phrase) in enumerate(entries):
            tp = tokens(phrase)
            if tp and len(tp & ti) / float(len(tp)) >= 0.75:
                used.add(i)
    # An ORPHAN is an entry that matches no top-ranked item.  For a STALE
    # verdict that is CORRECT and permanent: the item was retired from the
    # list, so of course it no longer ranks -- and the entry is the audit
    # trail, which must not be deleted to keep a check green.  Only a
    # lingering OPEN entry is an orphan worth reporting.
    unmatched = [i for i in range(len(entries))
                 if i not in used and entries[i][0] == 'OPEN']
    # SPLIT 2026-10-17.  `extra` used to be every unmatched OPEN entry, and
    # the check below reported all of them as having "lost its item from the
    # list entirely".  On 2026-10-17 six entries were unmatched and only FOUR
    # had lost their item; the other two were on the list under different
    # wording -- `wire` against `wired`, `uvm coverage collector` against
    # `UartCoverage collector` -- and one of those rewordings had been
    # produced by this file's own adjudication of 2026-10-14.  A verdict must
    # be gated on the mechanism it reports, so the mechanism is now measured:
    # an unmatched entry whose stems ARE contained in some item is a WORDING
    # miss and is reported as one; only the rest is a retirement.
    extra, wording = [], []
    for i in unmatched:
        ep = stems(entries[i][1])
        hit = None
        for it in pool:
            if ep and len(ep & stems(it)) / float(len(ep)) >= 0.75:
                hit = it
                break
        (wording if hit else extra).append((entries[i][1], hit))
    return entries, covered, uncovered, extra, wording


# ---------------------------------------------------------------------------
# S4b -- HEADING/BULLET EQUALITY, MECHANISED 2026-11-05
#
# The 2026-11-04 entry ranked this first and said why: the orphan count "moved
# 19 -> 4 while this entry was being written, purely from restoring carried
# wording", so the count "is not a progress metric until the heading/bullet
# equality is mechanised, and mechanising it is the real item: a check that
# each OPEN entry's heading appears verbatim as the head of some bullet."
#
# S4 matches an entry to an item by 0.75 token containment.  That is the right
# matcher for "is this item adjudicated at all" -- it has to survive a bullet
# being rewritten around its subject.  It is the wrong instrument for asking
# whether the two artefacts AGREE, because it cannot distinguish an entry whose
# heading IS a bullet's head from one that merely shares three quarters of its
# nouns with the bullet's body.  Those two look identical to S4 and behave
# completely differently when the list is edited: the first is stable, the
# second flips in and out of the orphan set on a rewording.  So the orphan
# count was measuring the session's own editing, exactly as 11-04 said.
#
# S4b asks the narrower question with an EXACT comparison.  Each OPEN entry is
# ALIGNED (its heading equals some bullet's head), MISALIGNED (it token-matches
# a bullet but equals no bullet's head) or ORPHAN (no bullet at all).  The
# failing condition is MISALIGNED: an entry that is only reachable through the
# loose matcher.  ORPHAN is not re-reported here -- S4 owns that verdict and
# two checks failing on one fact is one finding counted twice.


def bullet_head(bullet):
    """The head of a standing-list bullet: the bolded lead if there is one,
    else the text up to the first dash separator.

    The list's convention is `- **HEAD** -- gloss`, with the gloss carrying
    the session counts and the arguments.  Only the head names the item, and
    only the head is what an adjudication heading is supposed to quote.
    """
    b = bullet.strip()
    b = re.sub(r'^-\s*', '', b)
    b = ' '.join(b.split())
    m = re.match(r'\*\*(.+?)\*\*', b)
    if m:
        return m.group(1)
    return re.split(r'\s+(?:\u2014|\u2013|--)\s+', b)[0]


def norm_head(text):
    """Whitespace, case and markdown emphasis folded; NOTHING else.

    Deliberately not tokens() and not stems(): this comparison exists because
    the loose matchers cannot see a wording difference, so folding anything
    with meaning in it would defeat the point.  Backticks and asterisks go
    because they are typography, and a trailing colon or period goes because
    the heading format adds one; every word must still be there, in order.
    """
    t = ' '.join(text.split()).lower()
    t = t.replace('`', '').replace('*', '')
    t = t.replace('\u2014', '--').replace('\u2013', '--')
    return t.strip().rstrip('.:,;')


def s4b_heading_alignment(entries, items):
    """-> rows [(verdict, phrase, cls, detail)], one per adjudication entry.

    cls in {ALIGNED, MISALIGNED, ORPHAN} for OPEN entries.  STALE entries are
    classified too, and reported, but never counted as a fault: a STALE entry
    whose item has left the list is the audit trail doing its job, and
    requiring its heading to match a bullet would require the list to carry
    items it has retired.
    """
    heads = {}
    for it in items:
        heads.setdefault(norm_head(bullet_head(it)), it)
    rows = []
    for verdict, phrase in entries:
        np_ = norm_head(phrase)
        if np_ in heads:
            rows.append((verdict, phrase, 'ALIGNED',
                         'heading equals the head of a live bullet'))
            continue
        tp = tokens(phrase)
        hit = None
        for it in items:
            ti = tokens(it)
            if tp and len(tp & ti) / float(len(tp)) >= 0.75:
                hit = it
                break
        if hit is None:
            rows.append((verdict, phrase, 'ORPHAN',
                         'no bullet matches, loosely or exactly'))
        else:
            rows.append((verdict, phrase, 'MISALIGNED',
                         'reachable only through the 0.75 token matcher; the '
                         'bullet head is "%s"' % bullet_head(hit)))
    return rows


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

    # -- controls on the 2026-10-17 RETIRED/WORDING split.  The split moves
    # rows between two REPORTED categories, so a control on it has to show
    # that it moves the right ones and, crucially, that it does not move a
    # genuine retirement.  Without W3 below the split is a way to make a
    # failing check pass, which is what it must not be.
    items_w = ['- THE CAPSTONE BOX: (c) PayloadAdmissibilityCoverage wired '
               'into the live UartCoverage collector',
               '- something about baud tolerance measurement entirely']
    e_w = 'Wire PayloadAdmissibilityCoverage into the live UVM coverage collector'
    e_r = 'A mutant on the budget law exhaustive stimulus generator itself'
    def _is_wording(entry, pool):
        ep = stems(entry)
        return any(ep and len(ep & stems(it)) / float(len(ep)) >= 0.75
                   for it in pool)
    def _is_exact(entry, pool):
        tp = tokens(entry)
        return any(tp and len(tp & tokens(it)) / float(len(tp)) >= 0.75
                   for it in pool)
    res.append(('W1', 'the EXACT matcher misses an item that differs only in '
                      'wording', not _is_exact(e_w, items_w),
                'wire/wired and uvm-coverage-collector/UartCoverage-collector'))

    # -- controls on the 2026-11-04 case-insensitive retired-wording match.
    # R1 plants each retired phrase into a synthetic list and requires the
    # row to go RED; without it, "the phrase stays gone" passes for a
    # matcher that can never match anything.  R2 plants it in a DIFFERENT
    # CASE than the tuple stores, which is the specific evasion that let the
    # vplan item back in on 2026-11-03.
    planted = ['- ' + ph for _l, ph, _p, _n, _w in RETIRED_WORDINGS]
    red_all = all(not ok for ok, lbl, _d in s6_retired_wordings(planted)
                  if 'stays gone' in lbl)
    res.append(('R1', 'PLANTED: every retired wording, put back into the '
                      'list verbatim, turns its row RED', red_all,
                '%d phrases planted, %d rows red'
                % (len(planted),
                   sum(1 for ok, lbl, _d in s6_retired_wordings(planted)
                       if 'stays gone' in lbl and not ok))))
    swapped = ['- ' + (ph.upper() if ph.islower() else ph.lower())
               for _l, ph, _p, _n, _w in RETIRED_WORDINGS]
    red_ci = all(not ok for ok, lbl, _d in s6_retired_wordings(swapped)
                 if 'stays gone' in lbl)
    res.append(('R2', 'PLANTED, CASE SWAPPED: the same phrases in the '
                      'opposite case still turn their rows RED -- the '
                      '2026-11-03 evasion', red_ci,
                'this control FAILS against the case-sensitive matcher this '
                'section carried until 2026-11-04, which is why that '
                'matcher reported green on the session it was built to '
                'catch'))
    res.append(('W2', 'and the wording-tolerant form finds it',
                _is_wording(e_w, items_w),
                'so the row is reported WORDING, with the item it matches, '
                'rather than as a\n        retirement -- the sentence the old '
                'form printed about it was false'))
    res.append(('W3', 'NEGATIVE CONTROL: the loose form does NOT rescue an '
                      'entry whose item is really gone',
                not _is_wording(e_r, items_w),
                'the split must never be able to turn a FAIL into a PASS; it '
                'may only move a\n        row between two reported '
                'categories'))
    res.append(('W4', 'and identifier-case splitting is what does the work, '
                      'not the suffix fold alone',
                'coverage' in stems('UartCoverage')
                and 'uart' in stems('UartCoverage'),
                "stems('UartCoverage') = %s.  The first draft folded suffixes "
                "over tokens()\n        output, by which time `UartCoverage` "
                "is one token and the boundary is gone;\n        it fixed "
                "wire/wired, left all six 2026-10-17 entries RETIRED, and so "
                "changed\n        nothing the check reported."
                % sorted(stems('UartCoverage'))))

    # ---------------------------------------------------------------------
    # L1-L5 (2026-10-28): controls for the list-selection repair.
    #
    # The fault these are written against is not hypothetical: it was in the
    # tree for a day, and the committed transcript showed a complete 26/4
    # run while the tool died at S3 with IndexError.  Each planted log below
    # is a string, built here -- nothing is written into the repository, per
    # the standing "a module must not plant the pattern it censuses in the
    # tree other audits read" item.
    FULL_HEAD = '**Not yet covered (candidates for future runs):**\n'
    SUPP_HEAD = '**Not yet covered - added by this addendum, ranked:**\n'
    def _log(*parts):
        return '## entry\n\n' + '\n'.join(parts) + '\n\n**Commits:** 1\n'
    bullets_a = '- ALPHA item one\n- BETA item two\n- GAMMA item three\n'
    bullets_b = '- DELTA added later\n- EPSILON added later\n'

    only_full = _log(FULL_HEAD + bullets_a)
    full_then_supp = _log(FULL_HEAD + bullets_a, SUPP_HEAD + bullets_b)
    only_supp = _log(SUPP_HEAD + bullets_b)
    two_fulls = _log(FULL_HEAD + bullets_a, FULL_HEAD + bullets_b)

    it_full, _ = open_item_blocks(only_full)
    it_union, prov_union = standing_list(full_then_supp)
    it_supp, prov_supp = standing_list(only_supp)
    it_two, prov_two = standing_list(two_fulls)

    res.append(('L1', 'REGRESSION CONTROL: a log with one FULL list and no '
                      'supplement is read exactly as before',
                len(it_full) == 3 and 'ALPHA' in it_full[0],
                '%d items -- the 45 entries up to 2026-10-26 are all this '
                'shape, and the repair must not move them' % len(it_full)))
    res.append(('L2', 'a FULL list followed by a SUPPLEMENT is read as the '
                      'UNION, not as the supplement alone',
                len(it_union) == 5
                and [k for k, _h, _n in prov_union] == ['FULL', 'SUPPLEMENT'],
                '%d items from %s.  Reading the LAST heading gave 2 and is '
                'what broke\n        this audit on 2026-10-27; reading only '
                'the FULL list would now drop the\n        addendum\'s '
                'ranked-first item.'
                % (len(it_union), [(k, n) for k, _h, n in prov_union])))
    res.append(('L3', 'a SUPPLEMENT with no FULL list before it still parses '
                      'and is reported as a supplement',
                len(it_supp) == 2
                and [k for k, _h, _n in prov_supp] == ['SUPPLEMENT'],
                'the anchor check in main() is what calls this out; the '
                'parser must not crash on it'))
    res.append(('L4', 'and a second FULL list anchors on the LATER one',
                len(it_two) == 2 and 'DELTA' in it_two[0],
                'a new session entry supersedes the previous full list, '
                'which is the behaviour every entry relies on'))
    ranked_short = s3_rank(it_supp, completed_blocks(_SYNTH_PROGRESS))
    res.append(('L5', 'POSITIVE CONTROL for the IndexError: a list SHORTER '
                      'than REPORTING_CUT ranks without raising',
                len(ranked_short) == 2
                and min(REPORTING_CUT, len(ranked_short)) == 2,
                'REPORTING_CUT is %d and this list has %d items.  The '
                'unguarded read was\n        ranked[REPORTING_CUT - 1], '
                'which raised IndexError and killed S3, S4, S5 and S6\n'
                '        at once -- so the crash removed the five checks '
                'that would have reported it.'
                % (REPORTING_CUT, len(ranked_short))))
    return res


# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# S6 -- an open item's claim about a FILE'S CONTENT (added 2026-10-25)
# ---------------------------------------------------------------------------
#
# WHY S1 WAS NOT ENOUGH.  S1 checks that a path an item names EXISTS.  It
# says nothing about what is IN that file, and on 2026-10-25 the list was
# wrong in exactly that way: the ranked-first item read
#
#     "`G2` in runner A is the worked reference ... B, C and D have no such
#      arm, and a runner that cried detect on a neutral change would make
#      every DETECT it prints unattributable."
#
# `examples/phase1_mutation/run_mutation_tests.py` -- runner C -- has carried
# `G0b`, "positive control for the false DETECTED: a COSMETIC edit", since
# before the item was written, and `G0b` is STRONGER than runner A's `G2`:
# it requires the cosmetic edit to pass the bench, to change the raw
# transcript (so it would fool a byte-comparison criterion) and NOT to change
# the normalised one.  So a third of the ranked-first item was a request to
# build something that existed, and the session that acted on it would have
# built a weaker duplicate had it not read the file first.
#
# This is the same shape as the fault that created this module -- an item
# asserting a tree state the tree denies -- one level in: there the claim was
# "untouched for twelve sessions" about a finished component, here it is
# "has no such arm" about a file that has one.  The fix is the same fix: make
# the claim checkable.  Each row below is (claim, path, predicate, why), the
# predicate is a plain substring test against the file, and a row whose
# predicate FAILS means the open-items list is making a false claim, not that
# the code is broken.
#
# A row is retired by deleting it only when the claim is gone from the list.
# The graphene repository's standing-list audit keeps RETIRED rows that
# assert both that a wording stays gone and that the fact justifying its
# retirement still holds; that is the stronger form and this list should grow
# into it.

# A RETIRED WORDING, in the form the graphene repository's standing-list
# audit uses: the row asserts BOTH that the false phrase is gone from the
# most recent list AND that the fact which justified retiring it still holds.
# Two assertions, because either alone is satisfiable the wrong way -- a
# phrase can vanish because the item was dropped rather than corrected, and
# the justifying fact can survive while the phrase is revived.  A row that
# simply restated the false claim would be PERMANENTLY RED, which is the
# anti-pattern the sibling repository measured on the same day: a red row
# carries no information, and a suite that is always red hides its new
# members behind an unchanged score.
RETIRED_WORDINGS = (
    ('"B, C and D have no such arm" (2026-10-24 ranked-first item)',
     'have no such arm',
     'examples/phase1_mutation/run_mutation_tests.py',
     'G0b positive control for the false DETECTED: a COSMETIC edit',
     'runner C has carried G0b since before the item was written, and G0b is '
     'STRONGER than runner A\'s G2: it requires the cosmetic edit to pass '
     'the bench, to change the RAW transcript and NOT to change the '
     'normalised one.  A session acting on the item as written would have '
     'built a weaker duplicate.'),

    # ----------------------------------------------------------------------
    # ADDED 2026-11-04, AND IT IS THE ROW THE 2026-10-29 ENTRY ASKED FOR BY
    # NAME.  That entry found "A vplan v2 revision" still carried as an open
    # item although the work was committed on 2026-09-19 -- the plan's
    # Sections 1.1 and 2.4 re-specify STATUS[6:4] as sticky/read-to-clear --
    # and it diagnosed the mechanism exactly:
    #
    #     "the item's authority is OUTSIDE this repository, so correcting it
    #      here does not stop it being re-imported"
    #
    # and it proposed the remedy: a committed check for externally-sourced
    # list claims.  The remedy was logged as an item and NOT BUILT.
    #
    # THE PREDICTION THEN CAME TRUE.  The 2026-11-03 standing list carries
    # "A vplan v2 REVISION FOR THE STICKY STATUS BITS -- carried,
    # untouched", four sessions after 10-29 retired it, and nothing in the
    # tree could see it because this tuple had one entry.  So this row is
    # not a hypothetical guard: it is a row that WOULD HAVE FIRED on
    # 2026-11-03, and the commit that adds it deliberately reports it RED
    # against that list before the list is corrected.
    ('"a vplan v2 revision" (retired 2026-10-29; re-imported 2026-11-03)',
     'vplan v2 revision',
     'verification_plans/uart_controller_verification_plan.md',
     'sticky (read-to-clear):',
     'the plan has specified STATUS[6:4] as sticky/read-to-clear since v2 on '
     '2026-09-19 -- Section 1.1 and the register map -- and v14 (iii) gave '
     'that wording an executable form as protocol-checker rule S1 on '
     '2026-10-29.  An item asking for the revision is asking for work that '
     'is six weeks old, and a session acting on it would have re-specified '
     'a register that is already specified.'),
)


def s6_retired_wordings(items):
    """[(ok, label, detail)] for each retired wording: gone from the list,
    and the fact that justified retiring it still true."""
    listed = '\n'.join(items)
    # MATCHED CASE-INSENSITIVELY, added 2026-11-04, and the reason is the
    # defect this section exists for.  The vplan item was retired on
    # 2026-10-29 while the list spelled it "A vplan v2 revision" and
    # re-imported on 2026-11-03 spelled "A vplan v2 REVISION FOR THE STICKY
    # STATUS BITS".  A case-sensitive needle would have been evaded by
    # exactly the drift that carried the item back, so the matcher would have
    # reported green on the session it was built to catch.  Lowering both
    # sides is strictly stronger and does not weaken the 10-24 row, whose
    # needle is already lower case.
    low = listed.lower()
    out = []
    for label, phrase, path, needle, why in RETIRED_WORDINGS:
        gone = phrase.lower() not in low
        full = os.path.join(ROOT, path)
        holds = (os.path.exists(full)
                 and needle in open(full, encoding='utf-8').read())
        out.append((gone, 'the retired wording %s stays gone from the list'
                    % label,
                    'phrase %s the current list' % ('is absent from' if gone
                                                    else 'HAS RETURNED TO')))
        out.append((holds, 'and the fact that justified retiring it still '
                    'holds', '%s %s "%s"  --  %s'
                    % (path, 'still contains' if holds else 'NO LONGER '
                       'contains', needle[:38], why)))
    return out


CONTENT_CLAIMS = (
    ('runner B now HAS a cosmetic-edit positive control',
     'examples/phase6_crv_uart/run_tx_empty_mutation_tests.sh',
     'G2b neutrality control',
     True,
     'ported 2026-10-25; this row goes red if the port is ever reverted '
     'while the list still claims it was done.'),
    ('runner D now HAS a cosmetic-edit positive control',
     'examples/phase6_crv_uart/run_mutation_tests_bimodal.sh',
     'G2b neutrality control',
     True,
     'ported 2026-10-25, same reason.'),
    ('runner A still has the G2 arm the port was modelled on',
     'examples/phase6_crv_uart/run_mutation_tests.sh',
     'G2  neutrality control',
     True,
     'the worked reference.  If this disappears, the three ports above are '
     'no longer ports of anything and the family has no stated original.'),
    ('the new arms are mutation-tested rather than trusted',
     'tools/test_neutrality_controls.py',
     'N1 a REAL behavioural edit',
     True,
     'a control that reports green and can never report anything else is '
     'not a control; this row ties the arms to the suite that proves them '
     'reachable.'),

    # ----------------------------------------------------------------------
    # THE 2026-10-26 CHECK, RECORDED SO THE NEXT SESSION DOES NOT RE-ASK.
    # The 2026-10-25 ranked-first item named five runners and said "CHECK
    # BEFORE PORTING -- today's whole Section 4 is what happens when that
    # step is skipped, and S6 is where each answer should be recorded".  All
    # five were read on 2026-10-26 and none carried a neutral arm, so this
    # time the premise held; the answers are below rather than in prose, so
    # a future session reads a verdict instead of repeating the reading.
    # ----------------------------------------------------------------------
    ('runner E (phase6_rx_pin_driver) HAS a cosmetic-edit control',
     'examples/phase6_rx_pin_driver/run_mutation_tests.sh',
     'G2b NEUTRALITY CONTROL',
     True,
     'checked 2026-10-26: it had controls A/B/C and cmp -s and no neutral '
     'arm, and was ported the same day.  Red if the port is reverted while '
     'the list still claims it.'),
    ('runner F (phase6_baud_error_coverage) HAS a cosmetic-edit control',
     'examples/phase6_baud_error_coverage/run_mutation_tests.sh',
     'G2b NEUTRALITY CONTROL',
     True,
     'checked 2026-10-26, same answer and same day.  This is the bench whose '
     'stated point is that the coverage model detects nothing and only a '
     'check does, so what the check is sensitive to is load-bearing there.'),
    ('runner G (phase6_bfm_equivalence) HAS a cosmetic-edit control',
     'examples/phase6_bfm_equivalence/run_mutation_tests.sh',
     'G2b NEUTRALITY CONTROL',
     True,
     'checked 2026-10-26, same answer and same day.  The only one of the '
     'five whose mutation target is the BFM rather than the RTL, which is '
     'why mc_neutral_copy takes a path.'),
    ('the neutral EDIT is shared and the VERDICT is not',
     'tools/mutation_controls.sh',
     'IT DELIBERATELY DOES NOT JUDGE THE RESULT',
     True,
     'mc_neutral_copy performs the comment-only edit and refuses a '
     'byte-identical copy; each runner asserts its own pass criterion.  If '
     'this comment goes, the next port is liable to give several runners one '
     'criterion none of them uses.'),
    # ----------------------------------------------------------------------
    # THE THREE INVERTED REMINDER ROWS, TURNED OVER 2026-10-28.
    #
    # The 2026-10-26 session wrote these three deliberately BACKWARDS: each
    # asserted the absence of an arm, so each was green while the gap was
    # open and would go red "on the day the arm lands, which is the day the
    # list must be updated".  The arms landed on 2026-10-27 and all three
    # fired exactly as designed -- and the list was not updated, so the
    # 10-27 addendum's own ranked-first item is this turn-over.  The
    # instrument worked and nothing read it; that is the part worth keeping.
    #
    # They now assert the POST-LANDING fact, which is the direction a
    # standing row should point: red if the arm is ever reverted while the
    # list claims it.  The pre-landing wording is kept in each `why` rather
    # than deleted, because a row that changed polarity is exactly the kind
    # of history a later session needs in order to trust the row.
    # ----------------------------------------------------------------------
    ('phase4_ral HAS a cosmetic-edit control (ported 2026-10-27)',
     'examples/phase4_ral/run_mutation_tests.sh',
     'G2b',
     True,
     'this row read "phase4_ral still has NO cosmetic-edit control" from '
     '2026-10-26, when the bench was blocked on cocotb; it was an inverted '
     'REMINDER, green while the gap was open.  cocotb installed on '
     '2026-10-27 (see tools/setup_cocotb.sh) and the arm was ported the '
     'same day, so the reminder fired and is turned over here.  Red now if '
     'the port is reverted while the list claims it.'),
    ('phase6_uvm_crv_uart HAS a cosmetic-edit control (ported 2026-10-27)',
     'examples/phase6_uvm_crv_uart/run_mutation_tests.sh',
     'G2b',
     True,
     'same turn-over as the row above.  Its pre-landing wording recorded '
     'the distinction that made the port necessary: the runner already had '
     'an unmutated `control` ROW, which is a BASELINE -- it asks whether '
     'the bench passes on good RTL -- and not a neutrality arm, which asks '
     'whether it passes on RTL that is different but cannot behave '
     'differently.  Conflating the two is how a runner looks controlled and '
     'is not.'),
    ('the selftest covers all SEVEN runners, not the original five',
     'tools/test_neutrality_controls.py',
     "MARKER_RUNNERS = ('E', 'F', 'G', 'H', 'I')",
     True,
     'read "all FIVE runners, not the original two" from 2026-10-26 with '
     "the needle MARKER_RUNNERS = ('E', 'F', 'G').  H and I were added "
     '2026-10-27 with the two ports above, and the needle is the marker '
     'tuple itself, so the row tracks the number it claims rather than a '
     'comment about it.  35/35 across seven runners at the last full pass.'),
)


def s6_content_claims():
    """[(ok, claim, detail)] -- is each recorded claim about a file's content
    still true?  `expect` False means the substring must be ABSENT."""
    out = []
    for claim, path, needle, expect, why in CONTENT_CLAIMS:
        full = os.path.join(ROOT, path)
        if not os.path.exists(full):
            out.append((False, claim,
                        'the file named does not exist: %s' % path))
            continue
        found = needle in open(full, encoding='utf-8').read()
        out.append((found == expect, claim,
                    '%s  %s "%s"  --  %s'
                    % (path, 'contains' if found else 'lacks',
                       needle[:40], why)))
    return out


# ---------------------------------------------------------------------------
# S7 -- A DEPARTURE FROM THE LIST MUST BE ACCOUNTED FOR.  CREATED 2026-11-06.
#
# The 2026-11-05 entry ranked this first and specified it: "diff the
# bullet-head set of the newest list against the previous entry's and require
# every departure to be accounted for -- matched either by a STALE
# adjudication entry (completed or retired) or by an explicit removal note in
# the entry that dropped it.  Blocked on nothing."
#
# The reason it is wanted: four bullets left the list between 10-28 and 11-05
# with no artefact recording that they had, one of them for the SECOND time,
# while a bullet that announced its own closure stayed.  S4b made
# misalignment measurable and says nothing about departure.
#
# THE SPECIFICATION DOES NOT SURVIVE THE WHOLE LOG, AND THAT IS MEASURED
# RATHER THAN ASSERTED.  Applied to every consecutive pair of entries the
# diff reports 220 departures over 50 transitions, worst 31 in one step, and
# the number is dominated by CHANGES OF FORMAT, not losses.  Those figures
# are PRINTED by s7_history_scan rather than quoted here as a verdict; the
# three causes are:
#
#   * Entries 10-29, 10-30, 11-02 and 11-03 carry short lists -- 7, 9, 10 and
#     12 bullets -- where 10-28 carries 31 and 11-04 carries 33.  Those
#     entries do not enumerate the standing list at all.
#   * Entries 10-25..10-28, 11-04 and 11-05 fold the tail into one bullet
#     headed "The rest of the standing list is unchanged: ...", and its head
#     CARRIES THE FOLDED NAMES, so its wording changes every entry and it
#     never compares equal to the previous entry's.
#   * So 10-28 -> 10-29 alone reports 31 departures, every one of them a
#     presentation change.  Treating the compression bullet as INHERITANCE --
#     i.e. reading "the rest is unchanged" as carrying the previous entry's
#     tail forward -- was tried first and makes it worse, not better: because
#     that bullet's own head carries the folded names and so changes wording
#     every entry, the effective set accumulates to 68 items by 10-28 and
#     then collapses in a single step, turning a 31-departure artefact into a
#     68-departure one.  That experiment is recorded here because it is the
#     reason the simpler reading was kept.
#
# A diff over heads is therefore not a history-wide instrument on this log,
# and nothing here claims it is.  What IS decidable is exactly what the item
# asks for operationally -- the NEWEST transition, between two entries whose
# lists are both current -- so S7 is scoped to that and the history scan is
# printed as a REPORT with its numbers, which is the evidence for the scope.
#
# ROUTES, in precedence order.  A departure is accounted for if:
#   ADJUDICATED  tools/open_item_adjudication.md carries a STALE entry whose
#                heading equals the departed head.  This is the route the
#                committed history actually uses.
#   NOTED        the entry that dropped it carries an explicit removal note.
#                The convention is defined BY THIS CHECK and no committed
#                entry uses it yet, so this route is exercised only by its
#                control (C3) -- stated rather than implied, because an
#                untested path in an auditor is this repository's own
#                recurring fault.
#   REWORDED     some head that ARRIVED in the same transition contains 75 %
#                of the departed head's tokens.  A reworded bullet is not a
#                departure, and S4b is the precedent for using the exact
#                comparison and the loose one to answer different questions.
#   LOST         none of the above.  The fault.


S7_REMOVAL_NOTE = re.compile(
    r'(?mi)^\s*[-*]\s*\*\*(?:RETIRED|REMOVED|DROPPED) FROM THE LIST:\*\*'
    r'\s*(.+?)\s*$')

S7_COMPRESSION = re.compile(r'the rest of the standing list is unchanged',
                            re.I)


def session_entries(log_text):
    """[(date, text)] for every `## YYYY-MM-DD` session entry, oldest first."""
    marks = [mm.start() for mm in re.finditer(r'(?m)^## .*', log_text)]
    out = []
    for i, st in enumerate(marks):
        en = marks[i + 1] if i + 1 < len(marks) else len(log_text)
        d = re.match(r'## (\d{4}-\d\d-\d\d)', log_text[st:en])
        if d:
            out.append((d.group(1), log_text[st:en]))
    return out


def entry_heads(entry_text):
    """Normalised bullet heads of one entry's standing list."""
    its, _prov = standing_list(entry_text)
    return [norm_head(bullet_head(i)) for i in its]


def stale_adjudication_heads(adj_text):
    """Normalised headings of the STALE adjudication entries."""
    return {norm_head(p)
            for v, p in re.findall(r'^##\s+(STALE|OPEN):\s*(.+?)\s*$',
                                   adj_text, re.M) if v == 'STALE'}


def removal_notes(entry_text):
    """Normalised heads named by explicit removal notes in one entry."""
    return {norm_head(mm.group(1))
            for mm in S7_REMOVAL_NOTE.finditer(entry_text)}


def classify_departure(head, arrivals, stale_heads, notes):
    """-> (cls, detail).  Precedence: ADJUDICATED, NOTED, REWORDED, LOST."""
    if head in stale_heads:
        return 'ADJUDICATED', 'a STALE adjudication entry quotes this head'
    if head in notes:
        return 'NOTED', 'the entry that dropped it carries a removal note'
    th = tokens(head)
    for a in arrivals:
        if th and len(th & tokens(a)) / float(len(th)) >= 0.75:
            return 'REWORDED', 'arrived reworded as "%s"' % a[:58]
    return 'LOST', 'no adjudication, no removal note, no reworded arrival'


def s7_newest_transition(log_text, adj_text):
    """-> (prev_date, cur_date, rows).  rows = [(cls, head, detail)]."""
    ents = session_entries(log_text)
    if len(ents) < 2:
        return None, None, []
    (pd, _ptxt), (cd, ctxt) = ents[-2], ents[-1]
    ph, ch = entry_heads(ents[-2][1]), entry_heads(ctxt)
    cs = set(ch)
    arrivals = [h for h in ch if h not in set(ph)]
    stale_heads = stale_adjudication_heads(adj_text)
    notes = removal_notes(ctxt)
    rows = []
    for h in ph:
        if h in cs:
            continue
        cls, detail = classify_departure(h, arrivals, stale_heads, notes)
        rows.append((cls, h, detail))
    return pd, cd, rows


def s7_history_scan(log_text):
    """The evidence for S7's scope: (n_transitions, n_departures, worst,
    short_entries, compression_entries).  A REPORT, never a verdict."""
    ents = session_entries(log_text)
    heads = [(d, entry_heads(t)) for d, t in ents]
    n_tr = n_dep = 0
    worst = (None, 0)
    for i in range(1, len(heads)):
        pd, ph = heads[i - 1]
        cd, ch = heads[i]
        if not ph or not ch:
            continue
        dep = [h for h in ph if h not in set(ch)]
        if dep:
            n_tr += 1
            n_dep += len(dep)
            if len(dep) > worst[1]:
                worst = ('%s -> %s' % (pd, cd), len(dep))
    sizes = [(d, len(h)) for d, h in heads if h]
    short = [d for d, n in sizes[-10:] if n < 15]
    comp = [d for d, t in ents[-10:]
            if any(S7_COMPRESSION.search(h) for h in entry_heads(t))]
    return n_tr, n_dep, worst, short, comp


def s7_controls():
    """Planted logs with answers known by inspection.  -> [(tag, ok, detail)]."""
    def mk(date, bullets, extra=''):
        return ('## %s - a plant\n\n%s\n\n**Not yet covered '
                '(candidates for future runs):**\n\n%s\n\n'
                '**Commits this run:** 0\n'
                % (date, extra, '\n'.join('- **%s** -- gloss.' % b
                                          for b in bullets)))
    out = []
    # C1 a bullet simply vanishes: LOST.
    log1 = mk('2026-01-01', ['ITEM ALPHA', 'ITEM BETA']) + mk('2026-01-02',
                                                              ['ITEM BETA'])
    _p, _c, r1 = s7_newest_transition(log1, '# none\n')
    out.append(('C1 a bullet that vanishes with no trace is LOST',
                [x[0] for x in r1] == ['LOST'],
                'rows %r' % [(x[0], x[1]) for x in r1]))
    # C2 the same log, with a STALE adjudication quoting the head.
    _p, _c, r2 = s7_newest_transition(
        log1, '## STALE: ITEM ALPHA\n\nreason.\n')
    out.append(('C2 and ACCOUNTED once a STALE adjudication entry quotes it',
                [x[0] for x in r2] == ['ADJUDICATED'],
                'rows %r' % [(x[0], x[1]) for x in r2]))
    # C3 the same log, with an explicit removal note in the dropping entry.
    log3 = mk('2026-01-01', ['ITEM ALPHA', 'ITEM BETA']) + mk(
        '2026-01-02', ['ITEM BETA'],
        extra='- **RETIRED FROM THE LIST:** ITEM ALPHA')
    _p, _c, r3 = s7_newest_transition(log3, '# none\n')
    # SUPERSEDED DETAIL STRING, CORRECTED 2026-11-08 and the old wording kept
    # verbatim below.  It read:
    #
    #     'the ONLY exercise of this route; no committed entry uses the
    #      convention yet'
    #
    # That became FALSE on 2026-11-07, when two bullets were retired by the
    # NOTED route for the first time, and it stayed false through 11-08's own
    # NOTED retirement -- which the live S7 row printed EIGHT LINES ABOVE this
    # check, in the same transcript.  A detail string asserting that a route is
    # unexercised, printed directly beneath a measurement of that route being
    # exercised, is the 2026-10-18 fault class: a claim carried in prose beside
    # the number that refutes it.  It is corrected to say what the control
    # actually establishes, which does not depend on the live log at all.
    out.append(('C3 or a removal note in the entry that dropped it',
                [x[0] for x in r3] == ['NOTED'],
                'rows %r -- a PLANTED exercise of the NOTED route, '
                'independent of whether any committed entry uses it.  The '
                'superseded wording claimed it was the only exercise and no '
                'committed entry used the convention; that was true when '
                'written on 2026-11-05, became false on 11-07 and is printed '
                'above as part of the live S7 row'
                % [(x[0], x[1]) for x in r3]))
    # C4 THE ZERO CASE: nothing departs, so there is nothing to account for.
    log4 = mk('2026-01-01', ['ITEM ALPHA']) + mk('2026-01-02',
                                                 ['ITEM ALPHA', 'ITEM GAMMA'])
    _p, _c, r4 = s7_newest_transition(log4, '# none\n')
    out.append(('C4 a list that only GAINS a bullet reports no departure',
                r4 == [], 'rows %r' % (r4,)))
    # C5 a reworded head is not a departure.
    log5 = mk('2026-01-01', ['THE ALPHA ITEM OF INTEREST']) + mk(
        '2026-01-02', ['THE ALPHA ITEM OF INTEREST, NOW REWORDED'])
    _p, _c, r5 = s7_newest_transition(log5, '# none\n')
    out.append(('C5 a reworded head is REWORDED and not LOST',
                [x[0] for x in r5] == ['REWORDED'],
                'rows %r' % [(x[0], x[1]) for x in r5]))
    # C6 PRECEDENCE, and the answer is known: a departure that BOTH has a
    # STALE entry and a reworded arrival must read ADJUDICATED.  Without an
    # order the two routes would race and the verdict would depend on dict
    # iteration, which is the "verdict indexed by nothing" fault.
    _p, _c, r6 = s7_newest_transition(
        log5, '## STALE: THE ALPHA ITEM OF INTEREST\n\nreason.\n')
    out.append(('C6 ADJUDICATED takes precedence over REWORDED, so the '
                'verdict does not depend on route order',
                [x[0] for x in r6] == ['ADJUDICATED'],
                'rows %r' % [(x[0], x[1]) for x in r6]))
    # C7 THE THRESHOLD ITSELF, AND IT WAS ADDED BECAUSE A MUTANT SURVIVED.
    # The 2026-11-06 mutation test loosened the rewording threshold from 0.75
    # to 0.0 -- which makes ANY arrival absorb ANY departure -- and every
    # control stayed green.  The reason is that C1's plant has NO arrivals at
    # all, so the rewording loop never executes and the threshold is never
    # read.  An unguarded constant in a classifier is exactly the "lever with
    # no guard" fault, and the harness found it where inspection had not.
    #
    # C7 is the plant that reads it: a bullet vanishes AND an unrelated bullet
    # arrives in the same transition.  At 0.75 the arrival shares none of the
    # departed head's tokens, so the verdict must be LOST; at any threshold
    # low enough to absorb it the verdict becomes REWORDED and this control
    # goes red.
    log7 = mk('2026-01-01', ['ITEM ALPHA', 'ITEM BETA']) + mk(
        '2026-01-02', ['ITEM BETA', 'SOMETHING ENTIRELY DIFFERENT'])
    _p, _c, r7 = s7_newest_transition(log7, '# none\n')
    out.append(('C7 an unrelated ARRIVAL does not absorb a lost bullet -- the '
                '0.75 threshold is read, not merely declared',
                [x[0] for x in r7] == ['LOST'],
                'rows %r; added after a surviving mutant showed C1 never '
                'reaches the threshold' % [(x[0], x[1]) for x in r7]))
    return out


def unsuccessored_stale(entries, adj_text):
    """STALE entries that name neither REPLACED-BY: nor NO-SUCCESSOR:.

    ANCHORED ON THE HEADING, and that is the whole content of this function.
    Until 2026-11-09 the scan located each STALE entry with
    `adj_text.find(phrase)` -- the first occurrence of the heading text
    ANYWHERE in the file -- and read the successor out of whatever followed.
    This repository's own convention breaks that: a `REPLACED-BY:` line names
    its successor by the successor's full item phrase, so the first occurrence
    of a STALE entry's phrase is usually the predecessor's cross-reference,
    several hundred lines above the entry itself.

    Measured on 2026-11-09, on the entry added that session: the scan found
    the phrase inside the rx_avail entry's `REPLACED-BY:` line, sliced from
    there to the next `## ` heading, and reported NO SUCCESSOR NAMED for an
    entry whose NO-SUCCESSOR: line was eleven lines further down.  The
    false-RED was the visible half.  The false-GREEN is the half that matters:
    because the slice began just AFTER the words `REPLACED-BY:` on that line,
    a cross-reference sitting a little differently -- the phrase first, the
    marker after -- would have satisfied the check on behalf of an entry that
    names no successor at all.  C4c.2 is that case, planted.
    """
    out = []
    for verdict, phrase in entries:
        if verdict != 'STALE':
            continue
        m = re.search(r'^##[ \t]+STALE:[ \t]*' + re.escape(phrase) + r'[ \t]*$',
                      adj_text, re.M)
        if not m:
            out.append(phrase)
            continue
        nxt = adj_text.find('\n## ', m.end())
        body = adj_text[m.end():nxt if nxt > 0 else len(adj_text)]
        if 'REPLACED-BY:' not in body and 'NO-SUCCESSOR:' not in body:
            out.append(phrase)
    return out


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
    prov = standing_list(log)[1]
    done = completed_blocks(progress)

    print('=' * 78)
    print('OPEN-ITEM STALENESS AUDIT -- is the list that CHOOSES the work')
    print('consistent with the file that records what is finished?  (2026-10-03)')
    print('=' * 78)
    print('  AUTOMATION_LOG.md: %d "Not yet covered" lists; the STANDING '
          'list has %d items' % (n_lists, len(items)))
    # Added 2026-10-28.  Which lists contributed, and in which role.  Before
    # today this audit silently read whichever heading came last, and a
    # five-item addendum supplement was enough to make it audit the wrong
    # list and then crash.
    for kind, heading, n in prov:
        print('    %-10s %3d items   %s' % (kind, n, heading[:60]))
    # S0, added 2026-11-04 with the heading repair.  The repair teaches this
    # audit TWO heading spellings and nothing stops a third, so the thing
    # actually worth asserting is not which spelling matched but WHERE the
    # matched heading sits: inside the newest `## ` session entry.  Between
    # 2026-10-29 and 2026-11-03 this audit read a list four entries old and
    # reported 36/0 against it, and no check in the file could have said so.
    # S0 is that check.  It is deliberately about POSITION, not wording, so a
    # future rename fails it loudly instead of narrowing the audit silently.
    last_sec = last_session_offset(log)
    full_offsets = [o for o, k, _h in open_item_headings(log) if k == 'FULL']
    newest = max(full_offsets) if full_offsets else -1
    report(newest > last_sec,
           'S0 the standing list being audited belongs to the LAST session '
           'entry in the log (offset %d > %d), not to an older one'
           % (newest, last_sec))

    n_full = len([1 for k, _h, _n in prov if k == 'FULL'])
    report(n_full == 1,
           'the standing list is anchored on exactly one FULL list '
           '(found %d at or after the most recent; the anchor must be '
           'unambiguous)' % n_full)
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
    # CLAMPED 2026-10-28.  This read ranked[REPORTING_CUT - 1] unguarded and
    # raised IndexError on any list shorter than REPORTING_CUT -- which is
    # exactly what the five-item addendum supplement produced, killing the
    # audit at S3 so that S4, S5 and S6 never ran at all.  A list shorter
    # than the cut is a legitimate state (an early session, or a supplement
    # read on purpose by a control); it is not the same as a crash, and it
    # must be REPORTED rather than either raised or silently absorbed.
    cut = min(REPORTING_CUT, len(ranked))
    if cut < REPORTING_CUT:
        print('    (only %d ranked item(s): the reporting cut of %d is '
              'reduced to %d)' % (len(ranked), REPORTING_CUT, cut))
    for score, it, _w in ranked[:REPORTING_CUT + 4]:
        mark = '  <-- adjudicate' if cut and score >= ranked[cut - 1][0] else ''
        print('    %-6.3f %s%s' % (score, first_line(it, 86), mark))
    print('\n  top match for the highest-ranked item:')
    if ranked and ranked[0][2]:
        print('    %s' % first_line(ranked[0][2], 150))

    print('\n' + '-' * 78)
    print('S4 -- the committed adjudication of the top %d' % cut)
    print('-' * 78)
    entries, covered, uncovered, extra, wording = s4_adjudication(
        ranked, cut, all_items=items)
    print('  adjudication entries on disk: %d' % len(entries))
    for txt, verdict in covered:
        print('    %-7s %s' % (verdict, txt))
    for txt, _v in uncovered:
        print('    MISSING %s' % txt)
    for e, _hit in extra:
        print('    RETIRED %s' % first_line(e, 70))
    for e, hit in wording:
        print('    WORDING %s' % first_line(e, 70))
        print('            still on the list as: %s' % first_line(hit, 62))
    report(not uncovered, 'every item at or above the reporting cut is '
                          'adjudicated on disk, with a reason')
    # AMENDED 2026-10-28, per the 10-27 addendum's own complaint that this
    # check "reports it without naming which entry".  The orphan WAS printed,
    # as a RETIRED row some ten lines above -- so the complaint was not quite
    # right -- but a reader scanning for FAIL lines does not see it, and a
    # finding nobody can act on without re-deriving it is half a finding.
    # The names are now in the failure text itself.
    report(not extra, 'no OPEN adjudication entry has lost its item from the '
                      'list entirely (a STALE entry losing its item is the '
                      'audit trail working, not an orphan)%s'
                      % ('' if not extra else
                         '  --  %d orphan(s): %s'
                         % (len(extra),
                            '; '.join(first_line(e, 58) for e, _h in extra))))
    # The WORDING rows are NOT a failure: the item is on the list and the work
    # is tracked.  They are a defect in the LIST's stability, not in the
    # adjudication, and reporting them separately is the whole point of the
    # split -- the previous form failed the check above on them and said, in
    # the failure text, something false about where the item was.  What IS
    # required is that the two categories stay disjoint and account for every
    # unmatched OPEN entry, so a future loosening of either matcher cannot
    # quietly move a retirement into the benign column.
    report(not ({e for e, _ in extra} & {e for e, _ in wording}),
           'the RETIRED and WORDING categories are disjoint')

    # -- S4b ------------------------------------------------------------
    print('\n' + '-' * 78)
    print('S4b -- does each OPEN entry\'s heading EQUAL the head of a bullet?')
    print('-' * 78)
    print('  Mechanises the item the 2026-11-04 entry ranked first.  S4 asks')
    print('  whether an item is adjudicated AT ALL, with a 0.75 token match.')
    print('  This asks whether the two artefacts AGREE, with an exact one.')
    rows4b = s4b_heading_alignment(entries, items)
    for verdict, phrase, cls, detail in rows4b:
        print('    %-10s %-5s %s' % (cls, verdict, first_line(phrase, 56)))
        if cls != 'ALIGNED':
            print('               %s' % detail)
    mis = [r for r in rows4b if r[2] == 'MISALIGNED' and r[0] == 'OPEN']
    aligned = [r for r in rows4b if r[2] == 'ALIGNED' and r[0] == 'OPEN']
    orph = [r for r in rows4b if r[2] == 'ORPHAN' and r[0] == 'OPEN']
    print()
    print('  OPEN entries: %d ALIGNED, %d MISALIGNED, %d ORPHAN'
          % (len(aligned), len(mis), len(orph)))
    report(not mis,
           "every OPEN entry's heading equals the head of some live bullet, "
           "so the orphan set is decidable without the loose matcher%s"
           % ('' if not mis else
              '  --  %d misaligned: %s'
              % (len(mis), '; '.join(first_line(r[1], 44) for r in mis))))
    # The planted controls for the three classes.  Answers known before the
    # run, and independent of what the list and the adjudication currently
    # say -- which is the property the orphan COUNT lacks and the reason it
    # was not a progress metric.
    plant_items = [
        '- **AN ITEM WHOSE HEAD IS QUOTED EXACTLY** -- gloss, carried, with a '
        'session count that moves.',
        '- **AN ITEM WHOSE HEAD WAS REWORDED SLIGHTLY** -- gloss mentioning '
        'budget and stimulus and generator and mutant so the tokens still '
        'match.',
    ]
    plant_entries = [
        ('OPEN', 'AN ITEM WHOSE HEAD IS QUOTED EXACTLY'),
        ('OPEN', 'AN ITEM WHOSE HEAD WAS REWORDED'),
        ('OPEN', 'AN ITEM THAT IS NOT ON THE LIST AT ALL'),
        ('STALE', 'AN ITEM THAT IS NOT ON THE LIST AT ALL'),
    ]
    got = [r[2] for r in s4b_heading_alignment(plant_entries, plant_items)]
    report(got[0] == 'ALIGNED',
           'C4b.1 a heading quoting a bullet head verbatim -> ALIGNED  (got %s)'
           % got[0])
    report(got[1] == 'MISALIGNED',
           'C4b.2 a heading the token matcher still reaches, but which equals '
           'no bullet head -> MISALIGNED, not ALIGNED and not ORPHAN  (got %s)'
           % got[1])
    report(got[2] == 'ORPHAN',
           'C4b.3 a heading no bullet matches at all -> ORPHAN  (got %s)'
           % got[2])
    report(got[3] == 'ORPHAN' and
           not [r for r in s4b_heading_alignment(plant_entries, plant_items)
                if r[2] == 'MISALIGNED' and r[0] == 'STALE'],
           'C4b.4 a STALE entry is classified but never counted a fault, so '
           'the audit trail is not pressure to delete it')
    report(norm_head('**`FOO`  --  bar**') == norm_head('FOO  --  bar'),
           'C4b.5 norm_head folds typography and whitespace only')
    report(norm_head('A CHECK THAT CATCHES M1, M4 AND M5') !=
           norm_head('A CHECK THAT CATCHES M1 AND M4'),
           'C4b.6 and NOT meaning: dropping a term must change the key, or '
           'this comparison is just a slower token match')
    if wording:
        print('  NOTE: %d adjudicated item(s) are tracked under a different '
              'wording than the\n        entry that judged them.  The entry '
              'is right and the item is live; what\n        moved is the '
              'list.  Each is named above with the item it matches, so a\n'
              '        reviewer can align the two without re-deciding the '
              'verdict.' % len(wording))
    # A STALE verdict retires the only text pointing at a piece of work, so
    # it must say what inherits it.  Without this, an audit of the list that
    # chooses the work can itself delete work -- which is the "repair built
    # and then not connected" failure one level up.
    adj_text = (open(ADJUDICATION, encoding='utf-8').read()
                if os.path.exists(ADJUDICATION) else '')
    unsuccessored = unsuccessored_stale(entries, adj_text)
    for phrase in unsuccessored:
        print('    NO SUCCESSOR NAMED  %s' % first_line(phrase, 66))
    # NAMES IN THE FAILURE TEXT, 2026-11-05, for the same reason the orphan
    # check got them on 2026-10-28: this row went red today on four entries
    # that all carried a successor and spelled it `REPLACED-BY` without the
    # colon, and the failure said only that some STALE verdict somewhere was
    # unsuccessored.  A finding nobody can act on without re-deriving it is
    # half a finding.
    report(not unsuccessored, 'every STALE verdict names what inherits the '
                              'work (REPLACED-BY) or states there is none '
                              '(NO-SUCCESSOR)%s'
                              % ('' if not unsuccessored else
                                 '  --  %d without one: %s'
                                 % (len(unsuccessored),
                                    '; '.join(first_line(u, 52)
                                              for u in unsuccessored))))
    # C4c -- PLANTED CONTROLS ON THE ANCHOR, both directions.  The old
    # substring scan passes C4c.1 and FAILS C4c.2, which is why C4c.2 is here:
    # a check that can be satisfied on an entry's behalf by text belonging to
    # a different entry is worse than one that is merely noisy.
    # The ORDER inside the predecessor is what makes C4c.2 bite, and it was
    # got wrong once before being measured: with the marker written BEFORE the
    # phrase, the old substring slice began past the marker and the row went
    # red anyway, so the fixture agreed with the broken anchor.  Here the
    # phrase comes first and the predecessor's own marker follows it, which is
    # the ordinary shape of an entry that discusses its successor in prose and
    # then records its verdict.  Measured 2026-11-09 against a reverted copy:
    # old anchor -> C4c.2 GREEN (false), new anchor -> C4c.2 RED (correct).
    plant_adj = (
        '## STALE: THE PREDECESSOR\n\n'
        'Body discussing THE SUCCESSOR ITEM at length in prose.\n\n'
        '> **REPLACED-BY:** whatever inherits this one.\n\n'
        '## STALE: THE SUCCESSOR ITEM\n\n'
        'Body with no successor marker of its own at all.\n\n'
        '## OPEN: SOMETHING ELSE\n\nBody.\n')
    plant_ents = [('STALE', 'THE PREDECESSOR'),
                  ('STALE', 'THE SUCCESSOR ITEM'),
                  ('OPEN', 'SOMETHING ELSE')]
    c4c = unsuccessored_stale(plant_ents, plant_adj)
    report('THE PREDECESSOR' not in c4c,
           'C4c.1 a STALE entry that names REPLACED-BY: in its own body is '
           'successored')
    report('THE SUCCESSOR ITEM' in c4c,
           'C4c.2 THE FALSE-GREEN, PLANTED: a STALE entry naming no successor '
           'of its own is NOT rescued by a REPLACED-BY: line belonging to an '
           'earlier entry that mentions it  --  measured: the old substring '
           'anchor calls that entry successored (wrongly), the heading anchor '
           'calls it unsuccessored (correctly)')
    plant_adj2 = plant_adj.replace(
        '## STALE: THE SUCCESSOR ITEM\n\nBody with no successor marker of its '
        'own at all.',
        '## STALE: THE SUCCESSOR ITEM\n\n> **NO-SUCCESSOR:** answered.')
    report('THE SUCCESSOR ITEM' not in unsuccessored_stale(plant_ents, plant_adj2),
           'C4c.3 and the same entry WITH its own NO-SUCCESSOR: line is '
           'successored, so C4c.2 is not just a matcher that never passes')
    report(unsuccessored_stale([('STALE', 'A HEADING THAT IS NOT THERE')],
                               plant_adj) == ['A HEADING THAT IS NOT THERE'],
           'C4c.4 a STALE verdict with no matching heading is reported, not '
           'silently skipped')
    n_stale = sum(1 for v, _p in entries if v == 'STALE')
    print('  verdicts: %d STALE, %d OPEN'
          % (n_stale, sum(1 for v, _p in entries if v == 'OPEN')))

    print('\n' + '-' * 78)
    print('S5 -- controls on the ranker, and its mutation test')
    print('-' * 78)
    for tag, text, ok, detail in s5_controls():
        report(ok, '%s  %s   [%s]' % (tag, text, detail))

    print('\n' + '-' * 78)
    print("S6 -- an open item's claim about a FILE'S CONTENT (2026-10-25)")
    print('-' * 78)
    print('  S1 asks whether a path an item names EXISTS.  It cannot ask')
    print('  whether what the item SAYS about that file is true, and on')
    print('  2026-10-25 the ranked-first item was wrong in exactly that way:')
    print('  it said runners "B, C and D have no such arm" while runner C')
    print('  had carried a stronger one since before the item was written.')
    print()
    for ok, claim, detail in s6_retired_wordings(items):
        report(ok, claim)
        print('         %s' % detail)
    for ok, claim, detail in s6_content_claims():
        report(ok, '%s' % claim)
        print('         %s' % detail)

    print('\n' + '-' * 78)
    print('S7 -- every bullet that LEAVES the list is accounted for (2026-11-06)')
    print('-' * 78)
    adj_text = (open(ADJUDICATION, encoding='utf-8').read()
                if os.path.exists(ADJUDICATION) else '')
    n_tr, n_dep, worst, short, comp = s7_history_scan(log)
    print('  history scan, a REPORT and not a verdict -- it is the evidence')
    print('  for why S7 is scoped to the newest transition:')
    print('    transitions with departures : %d' % n_tr)
    print('    departures in total         : %d' % n_dep)
    print('    worst single transition     : %s, %d departures'
          % (worst[0], worst[1]))
    print('    recent entries with a SHORT list (<15 bullets): %s'
          % (', '.join(short) or 'none'))
    print('    recent entries folding the tail into one bullet: %s'
          % (', '.join(comp) or 'none'))
    print('  A head diff cannot tell a format change from a loss, so the')
    print('  %d above measures presentation and not work lost.  S7 itself'
          % n_dep)
    print('  is scoped to the newest transition, where both lists are')
    print('  current and the question is decidable.')
    print()
    pd_, cd_, rows = s7_newest_transition(log, adj_text)
    print('  newest transition: %s -> %s   %d departures'
          % (pd_, cd_, len(rows)))
    for cls, head, detail in rows:
        print('    %-12s %s' % (cls, head[:58]))
        print('                 %s' % detail)
    lost = [h for c, h, _d in rows if c == 'LOST']
    report(not lost,
           'S7 no bullet left the newest list unaccounted for '
           '(%d departures: %s)'
           % (len(rows),
              ', '.join('%s=%d' % (c, len([1 for x, _h, _d in rows if x == c]))
                        for c in ('ADJUDICATED', 'NOTED', 'REWORDED', 'LOST'))))
    if lost:
        for h in lost:
            print('         LOST: %s' % h)
    print()
    for tag, ok, detail in s7_controls():
        report(ok, '%s   [%s]' % (tag, detail))

    print('\n' + '=' * 78)
    print('RESULT: %d passed, %d failed' % (n_pass, n_fail))
    print('=' * 78)
    return n_fail


if __name__ == '__main__':
    sys.exit(1 if main() else 0)
