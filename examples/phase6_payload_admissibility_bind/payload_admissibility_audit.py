#!/usr/bin/env python3
"""
payload_admissibility_audit.py -- the structural half of wiring
`PayloadAdmissibilityCoverage` into the live `UartCoverage` collector.

WHY THIS FILE IS SEPARATE FROM THE BENCH
----------------------------------------
Wiring the admissibility model into the live collector is the item ranked
first on 2026-10-28, 10-29 and 10-30.  Doing it turned up a conflict that is
a property of the two coverage models ALONE -- it does not need the
simulator, the DUT, or a single driven frame to establish, and an audit that
needs a four-minute cocotb elaboration to state a fact about 256 bytes is an
audit nobody runs.  So the structural claims live here, in pure python, and
the LIVE measurement lives in `uart_uvm_payload_bind_tb.py` next door.  The
bench imports this file's census rather than recomputing it, per the 09-24
anchored-comparison rule.

Both halves import `payload_coverage_model` and
`examples/phase6_uvm_crv_uart/uart_uvm_crv_tb`; NEITHER re-types anything
from them.  That is the 2026-10-30 imported-stimulus decision applied to a
coverage model: against a copy, the claim "the live model's bins conflict
with the admissibility rule" is a claim about a fork, and the fork drifts
silently because both halves stay green.

------------------------------------------------------------------------------
THE FINDING, AND THE DECISION THE WIRING TURNS OUT TO FORCE
------------------------------------------------------------------------------
`uart_uvm_crv_tb.data_class()` is a six-bin coverpoint on the TX payload:

    bin 0: d == 0x00        bin 3: d in (0xAA, 0x55)
    bin 1: d == 0xFF        bin 4: even popcount, otherwise
    bin 2: one-hot          bin 5: odd popcount, otherwise

Bins 0 and 1 are SINGLETONS.  A singleton bin is closable only by its one
member, so if that member is excluded from F7 evidence the bin has NO
ADMISSIBLE WITNESS -- it cannot be closed by any payload that could carry
evidence, by any stimulus, ever.  That is the `illegal_bins` situation v7/v8
already resolved for `g_first` bins 8 and 9, arriving in a different
coverpoint, in a different example, with nothing linking the two.

AND WHICH BINS ARE AFFECTED DEPENDS ON A RULE NOBODY HAD TO CHOOSE UNTIL NOW.
This repository carries TWO exclusion rules, and the wiring is the first
thing that has to pick one:

  * THE VPLAN 2-BYTE RULE -- {0x00, 0x80} -- which is what
    `payload_coverage_model.classify()` implements and therefore what the
    live collector gets if it is wired to that module as it stands.
  * THE v9 NINE-BYTE RULE -- {0x00, 0x80, 0xC0, 0xE0, 0xF0, 0xF8, 0xFC,
    0xFE, 0xFF} -- `reachable_cross_under_per_byte_rule`'s closed form, which
    v9 widened the F7 exclusion to, and which is where the "16-cell cross"
    the 10-02 item tells this wiring to adopt comes from.

They do not agree about the live model:

  * under the 2-byte rule, ONE cp_data bin has no admissible witness (bin 0);
  * under the nine-byte rule, TWO do (bins 0 and 1), because 0xFF -- the
    entire membership of bin 1 -- is excluded by the closed form.

So the rule the open item tells the wiring to adopt is the rule that makes
the live coverage model LESS closable, not more.  Both of the affected bins
are also `byte_for_class` steering witnesses, so under either rule the
coverage-driven policy DELIBERATELY DRIVES an excluded byte whenever the bin
is unhit, for as long as the burst lasts.

`CovModel.closed()` requires all 30 bins, so **every CLOSED run recorded in
`closure_results.csv` necessarily drove at least one excluded payload.**  The
30-bin closure criterion and the F7 admissibility rule cannot both be
satisfied by one payload stream, under either rule.

**WHAT IS NOT CLAIMED.**  The CRV bench is not an F7 run.  It checks APB
protocol rules and loopback data integrity, neither of which depends on the
adaptive observer's baud window, so driving 0x00 or 0xFF there is legitimate
stimulus and is not a defect in that bench.  The conflict is one of SCOPE:
the closure number and the F7 evidence rule are each sound alone and cannot
be met by one stream.  Nothing here says the UART is wrong, and nothing here
RESOLVES the conflict -- choosing the rule, and choosing among the three ways
out, are specification decisions.  They are logged, not taken.

**WHAT WAS ALREADY KNOWN, AND IS CREDITED RATHER THAN REDISCOVERED.**
`witness_soundness.py` (10-03) and `evidence_soundness_coverage.py` (10-04)
built this exact axis -- `population_unsound_bins()`, "no admissible byte
reaches this bin at all", computable before a frame is driven -- and the
committed 10-04 transcript already reports cross cell `(7, 3)` as
population-unsound under the nine-byte rule.  What is new here is that the
axis had never been pointed at the LIVE cp_data coverpoint, only at F7's own
g_first/transition model.  S2 is the one-way channel again: an instrument
that could have answered the question existed for four weeks, in the same
repository, and nothing connected it to the collector the question is about.

------------------------------------------------------------------------------
WHAT IS CHECKED
------------------------------------------------------------------------------
  S1  CENSUS, EXHAUSTIVE over all 256 bytes: for every `cp_data` bin, how
      many admissible / borderline / inadmissible bytes it contains.  The
      claim is about a bin being EMPTY of admissible members, and emptiness
      over a finite set is checkable by enumeration rather than argument.
  S2  THE CONFLICT, as an exact statement: exactly one bin has no admissible
      witness, and it is bin 0, and its only member is 0x00.
  S3  POSITIVE CONTROL ON THE CENSUS.  A census that reported "no admissible
      witness" for every bin would satisfy S2's shape and mean nothing.  Five
      of the six bins must have at least one admissible witness, and the
      counts must sum to 256.
  S4  THE STEERING MAP, audited rather than assumed.  Each of the six
      `byte_for_class` witnesses is classified, and the audit requires that
      exactly one of them is inadmissible -- and that it is the one for the
      bin S2 identifies.  A steering map that drove an illegal byte for a bin
      that HAS a legal witness would be a different and more easily fixed
      defect; this check distinguishes the two.
  S5  NEGATIVE CONTROL: bin 2 (one-hot) CONTAINS the other inadmissible byte
      (0x80) and a borderline one (0x40), yet has six admissible members and
      the map picks an admissible one.  So "contains an inadmissible byte" and
      "cannot be closed admissibly" are different properties, and the audit
      must not conflate them -- which it demonstrates by finding bin 2
      unconflicted.
  S6  THE REACHABLE CROSS UNDER BOTH RULES, measured, not quoted.  The 10-02
      item says the wiring must adopt the cross goal, and the goal's SIZE is
      rule-dependent: 23 cells under the 2-byte rule, 16 under the nine-byte
      rule -- which is where the "16-cell cross" in the open-item text comes
      from, now identified rather than inherited.
      THIS CHECK WAS FIRST WRITTEN AS A PREDICTION AND THE PREDICTION WAS
      WRONG.  It asserted that excluding borderline payloads does not shrink
      the cross; it does, 23 -> 21, because the whole `g_first = 7` row is
      borderline-only.  The assertion is replaced by the measurement and the
      refutation is recorded, not quietly corrected.
  S7  MUTATION.  A census that counted BORDERLINE as admissible would miss a
      real conflict in any bin whose only non-inadmissible members are
      borderline.  The mutant is run and must change S1's answer for at least
      one bin, or the three-valued axis is doing no work here and the audit
      may as well be two-valued.
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_EX = os.path.dirname(_HERE)
for _p in (os.path.join(_EX, 'phase4_uvm_milestone'),
           os.path.join(_EX, 'phase6_uvm_crv_uart')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import payload_coverage_model as M                              # noqa: E402
import reachable_cross_under_per_byte_rule as R                  # noqa: E402

# The live coverpoint and the live steering map, IMPORTED.  uart_uvm_crv_tb
# imports cocotb at module scope, so it cannot be imported on a bare python3;
# the two pure functions are pulled out of its source by the same AST route
# the repository uses elsewhere rather than being re-typed here.  If that
# extraction fails the audit FAILS -- it does not fall back to a local copy,
# because a fallback copy is exactly the fork this file exists to prevent.
import ast                                                      # noqa: E402

CRV_SRC = os.path.join(_EX, 'phase6_uvm_crv_uart', 'uart_uvm_crv_tb.py')

_PASS, _FAIL = [], []


def check(label, ok, detail=""):
    (_PASS if ok else _FAIL).append(label)
    print("  [%s] %s" % ("PASS" if ok else "FAIL", label))
    if detail:
        print("         %s" % detail)
    return ok


def head(n, title):
    print()
    print("=" * 76)
    print("SECTION %s -- %s" % (n, title))
    print("=" * 76)


def import_live_functions():
    """
    Lift `data_class` and `byte_for_class` out of the live CRV testbench.

    Parsed and exec'd from the committed source so that the definitions used
    here ARE the definitions the live bench uses.  Only those two function
    definitions are exec'd -- not the module -- so no cocotb import is
    triggered and nothing else in that file can run as a side effect.
    """
    with open(CRV_SRC) as fh:
        tree = ast.parse(fh.read(), filename=CRV_SRC)
    want = {'data_class', 'byte_for_class'}
    found = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in want:
            mod = ast.Module(body=[node], type_ignores=[])
            ns = {}
            exec(compile(mod, CRV_SRC, 'exec'), ns)
            found[node.name] = ns[node.name]
    missing = want - set(found)
    if missing:
        raise AssertionError(
            "could not lift %s from %s -- the live bench has been renamed or "
            "restructured, and this audit must be repaired rather than given "
            "a local copy of the coverpoint" % (sorted(missing), CRV_SRC))
    return found['data_class'], found['byte_for_class']


BIN_NAMES = ("0x00", "0xFF", "one-hot", "0xAA/0x55",
             "even popcount", "odd popcount")


def census(rows, data_class, excluded, borderline_counts_as_admissible=False):
    """
    Per-cp_data-bin counts of each admissibility class, over all 256 bytes,
    under a given EXCLUSION rule.

    A byte in `excluded` is not evidence at all, so it is counted as
    INADMISSIBLE here whatever `classify()` would say about it on its own.
    That is the whole reason this function takes the rule as an argument:
    0xFF is ADMISSIBLE under the vplan rule and EXCLUDED under v9's, and the
    live bin 1 consists of nothing else.
    """
    out = {c: {M.ADMISSIBLE: 0, M.BORDERLINE: 0, M.INADMISSIBLE: 0}
           for c in range(6)}
    members = {c: [] for c in range(6)}
    for b in range(256):
        cls = M.INADMISSIBLE if b in excluded else M.classify(b, rows)
        if borderline_counts_as_admissible and cls == M.BORDERLINE:
            cls = M.ADMISSIBLE
        out[data_class(b)][cls] += 1
        members[data_class(b)].append(b)
    return out, members


def cross_cells(rows, excluded):
    """(legal cells, population-unsound cells) under an exclusion rule."""
    cells = {}
    for b in range(256):
        if b in excluded:
            continue
        cells.setdefault((M.g_first_of(b), M.transition_count(b)), []).append(b)
    unsound = sorted(k for k, v in cells.items()
                     if all(M.classify(x, rows) != M.ADMISSIBLE for x in v))
    return cells, unsound


def main():
    print("=" * 76)
    print("PAYLOAD ADMISSIBILITY vs THE LIVE cp_data COVERPOINT")
    print("2026-11-02.  The structural half of the item ranked first on")
    print("2026-10-28, 10-29 and 10-30.")
    print("=" * 76)

    rows = M.load_measured()
    data_class, byte_for_class = import_live_functions()

    vplan_rule = set(b for b in rows if M.classify(b, rows) == M.INADMISSIBLE)
    nine_rule = set(R.inadmissible_by_closed_form())
    RULES = (("vplan 2-byte", vplan_rule), ("v9 nine-byte", nine_rule))

    print()
    print("  admissibility model : payload_coverage_model (IMPORTED)")
    print("  closed-form rule    : reachable_cross_under_per_byte_rule "
          "(IMPORTED)")
    print("  coverpoint + map    : uart_uvm_crv_tb, lifted from source")
    print("  bytes classified    : %d" % len(rows))
    for name, excl in RULES:
        print("  %-20s: %s"
              % (name, ", ".join("0x%02X" % b for b in sorted(excl))))
    print("  BORDERLINE (classify): %s"
          % ", ".join("0x%02X" % b for b in
                      sorted(b for b in rows
                             if M.classify(b, rows) == M.BORDERLINE)))

    # ---- S1 ---------------------------------------------------------------
    head(1, "the census, exhaustive over all 256 bytes, under BOTH rules")
    cens, conflicted = {}, {}
    for name, excl in RULES:
        cen, members = census(rows, data_class, excl)
        cens[name] = (cen, members)
        conflicted[name] = [c for c in range(6)
                            if cen[c][M.ADMISSIBLE] == 0]
        print()
        print("  --- %s rule ---" % name)
        print("  %-4s %-16s %-6s %-5s %-6s %-9s %s"
              % ("bin", "meaning", "total", "adm", "bord", "excl/inadm",
                 "verdict"))
        for c in range(6):
            a = cen[c][M.ADMISSIBLE]
            print("  %-4d %-16s %-6d %-5d %-6d %-9d %s"
                  % (c, BIN_NAMES[c], sum(cen[c].values()), a,
                     cen[c][M.BORDERLINE], cen[c][M.INADMISSIBLE],
                     "NO ADMISSIBLE WITNESS" if a == 0 else "closable"))
    check("S1 the census covers all 256 bytes exactly once, under both rules",
          all(sum(sum(cens[n][0][c].values()) for c in range(6)) == 256
              for n, _ in RULES),
          "256 under each rule")

    # ---- S2 ---------------------------------------------------------------
    head(2, "the conflict, as an exact statement, and it is rule-dependent")
    _, mem_v = cens["vplan 2-byte"]
    ok2 = (conflicted["vplan 2-byte"] == [0]
           and conflicted["v9 nine-byte"] == [0, 1]
           and mem_v[0] == [0x00] and mem_v[1] == [0xFF])
    check("S2 bins 0 and 1 are singletons; ONE of them has no admissible "
          "witness under the vplan rule and BOTH do under v9's",
          ok2,
          "unclosable bins: %s under the 2-byte rule, %s under the nine-byte "
          "rule.  bin 0 = {0x00}, bin 1 = {0xFF}.  The rule the 10-02 open "
          "item tells this wiring to adopt is the one that makes the live "
          "model LESS closable.  CovModel.closed() requires all 30 bins, so "
          "every closed run in closure_results.csv drove an excluded payload."
          % (conflicted["vplan 2-byte"], conflicted["v9 nine-byte"]))

    # ---- S3 ---------------------------------------------------------------
    head(3, "positive control on the census")
    nclos = {n: len([c for c in range(6) if cens[n][0][c][M.ADMISSIBLE] > 0])
             for n, _ in RULES}
    check("S3 most bins DO have an admissible witness under both rules",
          nclos["vplan 2-byte"] == 5 and nclos["v9 nine-byte"] == 4,
          "closable bins: %d of 6 under the 2-byte rule, %d of 6 under the "
          "nine-byte rule.  A census reporting 'no admissible witness' "
          "everywhere would satisfy S2's shape and mean nothing; this is the "
          "control that it does not."
          % (nclos["vplan 2-byte"], nclos["v9 nine-byte"]))

    # ---- S4 ---------------------------------------------------------------
    head(4, "the steering map, audited rather than assumed")
    print("  %-5s %-8s %-14s %-9s %-14s"
          % ("bin", "witness", "classify()", "g_first", "excluded by"))
    map_bad = {n: [] for n, _ in RULES}
    for c in range(6):
        w = byte_for_class(c)
        by = [n for n, excl in RULES if w in excl]
        for n in by:
            map_bad[n].append(c)
        print("  %-5d 0x%02X     %-14s %-9d %-14s"
              % (c, w, M.classify(w, rows), M.g_first_of(w),
                 ", ".join(by) if by else "-"))
    check("S4 every steering witness that is excluded belongs to a bin S2 "
          "identifies -- so the conflict is in the BIN, not the map",
          (map_bad["vplan 2-byte"] == conflicted["vplan 2-byte"]
           and map_bad["v9 nine-byte"] == conflicted["v9 nine-byte"]),
          "excluded witnesses at bins %s (2-byte) and %s (nine-byte).  This "
          "matters: a map driving an illegal byte for a bin that HAS a legal "
          "witness would be a MAP defect, repairable by changing one entry.  "
          "These bins are singletons, so there is no other entry to change "
          "and only the vplan can resolve it."
          % (map_bad["vplan 2-byte"], map_bad["v9 nine-byte"]))

    # ---- S5 ---------------------------------------------------------------
    head(5, "negative control: containing an illegal byte is not the same "
            "as being unclosable")
    b2 = cens["vplan 2-byte"][0][2]
    check("S5 bin 2 contains 0x80 (inadmissible) and 0x40 (borderline) and "
          "is still closable admissibly",
          (b2[M.INADMISSIBLE] >= 1 and b2[M.BORDERLINE] >= 1
           and b2[M.ADMISSIBLE] >= 1
           and M.classify(byte_for_class(2), rows) == M.ADMISSIBLE),
          "bin 2: %d admissible, %d borderline, %d excluded; the map picks "
          "0x%02X, which is %s.  So the audit does not conflate 'contains an "
          "inadmissible byte' with 'cannot be closed admissibly' -- bin 2 is "
          "the first and not the second, and bins 0 and 1 are the second "
          "because they are SINGLETONS."
          % (b2[M.ADMISSIBLE], b2[M.BORDERLINE], b2[M.INADMISSIBLE],
             byte_for_class(2), M.classify(byte_for_class(2), rows)))

    # ---- S6 ---------------------------------------------------------------
    head(6, "the reachable cross under both rules, and a refuted prediction")
    sizes = {}
    for name, excl in RULES:
        cells, unsound = cross_cells(rows, excl)
        sizes[name] = (len(cells), unsound)
        print("  %-14s rule: %2d legal cross cells, %d population-unsound %s"
              % (name, len(cells), len(unsound), unsound))
    check("S6 the cross goal's SIZE is rule-dependent, and the nine-byte "
          "rule is the source of the open item's '16-cell cross'",
          sizes["vplan 2-byte"][0] == 23 and sizes["v9 nine-byte"][0] == 16,
          "23 cells under the 2-byte rule, 16 under the nine-byte rule.  The "
          "10-02 item's '16-cell cross' is therefore the NINE-BYTE rule's "
          "cross, which this audit identifies rather than inherits -- the "
          "item does not say which rule it means, and the two differ by 7 "
          "cells.")
    check("S6-b THE PREDICTION THIS CHECK WAS FIRST WRITTEN WITH WAS WRONG: "
          "excluding borderline payloads DOES shrink the 2-byte cross",
          len(sizes["vplan 2-byte"][1]) == 2
          and sizes["vplan 2-byte"][1] == [(7, 1), (7, 3)],
          "it was asserted that the borderline bytes share their cells with "
          "admissible ones, so that the cross is achievable on admissible "
          "evidence alone.  It is not: 23 -> 21.  Cells (7,1) and (7,3) are "
          "SINGLETONS holding 0xC0 and 0x40, and g_first = 7 means ctz = 6, "
          "which only those two bytes have -- so the cross's whole "
          "`g_first = 7` row IS the BORDERLINE set, exactly.  Recorded as a "
          "refutation rather than corrected quietly: the first form of this "
          "check would have shipped a false claim that passed.")
    check("S6-c the 10-04 transcript's single population-unsound cell is "
          "reproduced under the rule it used",
          sizes["v9 nine-byte"][1] == [(7, 3)],
          "nine-byte rule gives [(7, 3)], which is what "
          "evidence_soundness_2026-10-04.txt reports.  The two-cell answer "
          "above is not a contradiction of that file -- it is the same "
          "computation under the OTHER rule, and (7,1) disappears there "
          "because v9 excludes 0xC0 outright.  Credited, not rediscovered.")

    # ---- S7 ---------------------------------------------------------------
    head(7, "mutation: collapse the three-valued axis to two")
    cen_m, _ = census(rows, data_class, vplan_rule,
                      borderline_counts_as_admissible=True)
    base = cens["vplan 2-byte"][0]
    moved = [c for c in range(6)
             if cen_m[c][M.ADMISSIBLE] != base[c][M.ADMISSIBLE]]
    check("S7 counting BORDERLINE as admissible changes the census for at "
          "least one bin, so the third state is doing work here",
          len(moved) > 0,
          "bins whose admissible count moves under the mutant: %s.  The "
          "mutant does NOT change S2's answer -- bins 0 and 1 have no "
          "borderline member either -- which is worth stating plainly: "
          "today's cp_data conflict would have been found by a two-valued "
          "audit as well.  Where the third state is load-bearing is S6-b, "
          "where the two borderline bytes are the SOLE occupants of two "
          "cross cells and a two-valued audit would have called those cells "
          "closable." % moved)

    print()
    print("=" * 76)
    print("RESULT: %s   (%d passed, %d failed)"
          % ("PASS" if not _FAIL else "FAIL", len(_PASS), len(_FAIL)))
    print("=" * 76)
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
