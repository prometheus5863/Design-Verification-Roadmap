#!/usr/bin/env python3
"""
evidence_soundness_coverage.py -- 2026-10-04

THE MECHANISM THE BORDERLINE CASE DID NOT HAVE.

Open item, created 2026-10-03: *give the BORDERLINE case a mechanism, as
`illegal_bins` gives the inadmissible case one.*  v8's
`PayloadAdmissibilityCoverage.sample()` RAISES `IllegalPayload` the moment an
INADMISSIBLE payload is sampled into an F7 run.  Nothing anywhere reported a
bin whose only witnesses are BORDERLINE -- which is exactly why `g_first`
bin 7 stayed invisible through four vplan revisions while the mechanism for
its sibling bins (8 and 9, unsound by INADMISSIBLE witness) worked on the
day it was written.  2026-10-03 named the asymmetry; this file closes it.

WHY A SUBCLASS AND NOT AN EDIT
------------------------------
`payload_coverage_model.py` carries ~30 committed validations, several
quoting a superseded 0.78 % figure, and its `classify()` still implements
vplan v8's TWO-byte rule where the vplan now says nine.  Rewiring it is a
separate open item, deliberately deferred twice with reasons.  So the
mechanism arrives here as a subclass that adds state and adds verdicts and
changes no existing number: `payload_coverage_model.py` is untouched and its
2026-09-30 transcript stays valid.  When the rewiring happens, this is the
class the UVM collector should hold, so the 09-30 "wire it into the live
collector" item gets a better target rather than a stale one.

TWO AXES THAT HAVE BEEN RUNNING TOGETHER, AND THEY ARE NOT THE SAME
-------------------------------------------------------------------
`witness_soundness.py` (10-03) answers a question about the POPULATION:
is there any admissible byte that reaches this bin at all?  That is
structural -- it is a property of the DUT, the classifier and the exclusion
rule, computable before a single frame is driven, and if the answer is no
the bin cannot be closed meaningfully by ANY stimulus.

A coverage collector answers a question about a RUN: which bins did this
stimulus hit?  Combining the two gives a verdict neither has on its own:

    population_unsound(bin)  <=>  no witness of bin is ADMISSIBLE
                                  (structural; no stimulus can fix it)
    run_unsound(bin)         <=>  bin was HIT, and no ADMISSIBLE sample
                                  hit it (this run's closure of this bin
                                  rests on uninterpretable evidence)

**A population-SOUND bin can be run-unsound.**  That is the case no
instrument in this repository could previously report, and it is the common
one in practice: the bin is closeable with good evidence, and this
particular run did not do it.  A cardinality report says 100 %.  Section 5
constructs such a bin by search rather than by assertion, and reports
honestly if the search comes back empty.

So this class reports TWO coverage numbers and the gap between them:

    coverage_pct()        -- v8's: a bin counts as covered if it was hit
    sound_coverage_pct()  -- a bin counts as covered only if an ADMISSIBLE
                             sample hit it

and `sign_off()` REFUSES when the first is 100 % and the second is not,
naming the bins.  `raise_on_unsound_closure=True` makes it a hard failure at
sample time, exactly parallel to `raise_on_illegal`.  The parallel is the
point of the item: the inadmissible case had a mechanism and the borderline
case had prose.

WHAT THIS DOES NOT DO
---------------------
It does not decide W1/W3/W4 for F7's goal.  That remains the top item and it
changes a committed sign-off criterion, so it is a decision for a reviewer,
not for a module.  What this adds is that under W0-as-committed the
unsoundness is now REPORTED by the live model instead of being recorded in a
plan that the model does not read.

It also does not rewire `classify()`.  Instead -- and this is the one new
number for the deferred item rather than a nudge toward it -- Section 6
measures what the rewiring will change, by running the identical census
under the live two-byte rule and the vplan's nine-byte rule and diffing the
verdicts.  A deferred item with a measured cost is a different thing from a
deferred item with a reason.
"""

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import payload_coverage_model as M
import reachable_cross_under_per_byte_rule as R

_PASS, _FAIL = [], []


def check(label, ok, detail=""):
    (_PASS if ok else _FAIL).append(label)
    print("  [%s] %s%s" % ("PASS" if ok else "FAIL", label,
                           ("  -- " + detail) if detail else ""))
    return ok


def head(n, title):
    print()
    print("=" * 76)
    print("SECTION %s -- %s" % (n, title))
    print("=" * 76)


class UnsoundClosure(AssertionError):
    """Raised when a coverage bin's only closing evidence in this run is a
    payload whose own F7 outcome is neither pass nor fail.

    Deliberately an AssertionError subclass, like `IllegalPayload`, so that
    the two failure modes are caught by the same `except` in a regression
    runner that does not care which kind of bad evidence it got.
    """


# Bin functions.  IMPORTED behaviour, not re-typed: g_first_of and
# transition_count come from the committed model, per the 09-24 rule that a
# file re-deriving what it checks agrees with it by construction.
COVERPOINTS = (
    ("g_first", lambda b: M.g_first_of(b)),
    ("transitions", lambda b: M.transition_count(b)),
    ("cross", lambda b: (M.g_first_of(b), M.transition_count(b))),
)


class EvidenceSoundCoverage(M.PayloadAdmissibilityCoverage):
    """v8's coverage model plus per-bin EVIDENCE accounting.

    Adds, for each of the three coverpoints, a per-bin count of hits broken
    down by the sampled payload's admissibility class.  Nothing existing is
    modified: `ctz_bins`, `tr_bins` and `cross` keep counting exactly what
    they counted, so `coverage_pct()` is bit-for-bit v8's number.
    """

    def __init__(self, rows, raise_on_illegal=True,
                 raise_on_unsound_closure=False, excluded=None):
        super().__init__(rows, raise_on_illegal=raise_on_illegal)
        self.raise_on_unsound_closure = raise_on_unsound_closure
        # `excluded` is the rule under which POPULATION soundness is judged.
        # None means "use the live classifier's own INADMISSIBLE set", which
        # is v8's two-byte rule -- stated, not assumed, because the vplan
        # says nine and that disagreement is a live open item.
        self.excluded = excluded
        # hits[cp][bin][class] -- integer counts, so every census below is a
        # partition identity and can be checked exactly rather than to a
        # tolerance.
        self.hits = {name: {} for name, _ in COVERPOINTS}
        self.n_samples = 0

    # -- live path ---------------------------------------------------------
    def sample(self, byte):
        cls = M.classify(byte, self.rows)
        # v8's sample() raises before touching any bin for an INADMISSIBLE
        # payload.  Call it first so that behaviour, including the raise, is
        # unchanged; only record evidence for samples it accepted.
        result = super().sample(byte)
        self.n_samples += 1
        if cls == M.INADMISSIBLE:
            # reached only when raise_on_illegal is False.  The sample DID
            # land in v8's bins in that mode, so its evidence is recorded --
            # an inadmissible witness is bad evidence, not absent evidence,
            # and silently dropping it here would make a run-unsound bin
            # look unhit instead of badly hit.
            self._record(byte, cls)
            return result
        self._record(byte, cls)
        if self.raise_on_unsound_closure:
            bad = self.run_unsound_bins()
            if bad:
                cp, b, census = bad[0]
                raise UnsoundClosure(
                    "coverpoint %s bin %r is closed in this run only by "
                    "non-admissible payloads (%d borderline, %d inadmissible, "
                    "0 admissible); closing it does not mean the DUT passed "
                    "there" % (cp, b, census[M.BORDERLINE],
                               census[M.INADMISSIBLE]))
        return result

    def _record(self, byte, cls):
        for name, binner in COVERPOINTS:
            cell = self.hits[name].setdefault(
                binner(byte),
                {M.ADMISSIBLE: 0, M.BORDERLINE: 0, M.INADMISSIBLE: 0})
            cell[cls] += 1

    # -- run axis ----------------------------------------------------------
    def run_unsound_bins(self):
        """[(coverpoint, bin, census)] for bins hit in this run with zero
        ADMISSIBLE hits.  A bin never hit is absent: unhit is an ordinary
        coverage hole and already reported by coverage_pct()."""
        out = []
        for name, _ in COVERPOINTS:
            for b in sorted(self.hits[name], key=repr):
                c = self.hits[name][b]
                if sum(c.values()) > 0 and c[M.ADMISSIBLE] == 0:
                    out.append((name, b, c))
        return out

    def sound_coverage_pct(self, coverpoint="cross"):
        """Coverage counting a bin as covered only when an ADMISSIBLE sample
        hit it.  Denominator is the reachable population, same as v8's."""
        reach = self.reachable_population(coverpoint)
        hit = sum(1 for b in reach
                  if self.hits[coverpoint].get(b, {}).get(M.ADMISSIBLE, 0) > 0)
        return 100.0 * hit / len(reach), hit, len(reach)

    def cardinality_coverage_pct(self, coverpoint="cross"):
        """v8's notion, generalised to any of the three coverpoints, so the
        two numbers below are computed the same way and their difference is
        attributable to the soundness rule alone."""
        reach = self.reachable_population(coverpoint)
        hit = sum(1 for b in reach
                  if sum(self.hits[coverpoint].get(b, {}).values()) > 0)
        return 100.0 * hit / len(reach), hit, len(reach)

    # -- population axis ---------------------------------------------------
    def excluded_set(self):
        if self.excluded is not None:
            return set(self.excluded)
        return {b for b in range(256)
                if M.classify(b, self.rows) == M.INADMISSIBLE}

    def reachable_population(self, coverpoint="cross"):
        """{bin: [witness bytes]} over the non-excluded population."""
        binner = dict(COVERPOINTS)[coverpoint]
        excl = self.excluded_set()
        out = {}
        for b in range(256):
            if b in excl:
                continue
            out.setdefault(binner(b), []).append(b)
        return out

    def population_unsound_bins(self, coverpoint="cross"):
        """Bins no ADMISSIBLE byte can reach.  STRUCTURAL: computable with no
        stimulus at all, which is what makes this the `illegal_bins`-analogue
        -- a build-time guard rather than a run-time one."""
        out = []
        for b, ws in self.reachable_population(coverpoint).items():
            if not any(M.classify(w, self.rows) == M.ADMISSIBLE for w in ws):
                out.append(b)
        return sorted(out, key=repr)

    def scarce_bins(self, coverpoint="cross"):
        """10-02's axis, for the quadrant table.  Cost, not meaning."""
        return sorted((b for b, ws in self.reachable_population(coverpoint).items()
                       if len(ws) == 1), key=repr)

    # -- the gate ----------------------------------------------------------
    def sign_off(self, coverpoint="cross"):
        """(ok, reasons).  The mechanism the BORDERLINE case lacked.

        Refuses on three distinct grounds, kept separate because they have
        different remedies:
          - a population-unsound bin is in the goal        -> change the GOAL
          - a bin was closed in this run only by bad evidence -> change the
            STIMULUS
          - cardinality coverage is 100 % while sound coverage is not ->
            the headline number overstates closure
        """
        reasons = []
        pop = self.population_unsound_bins(coverpoint)
        if pop:
            reasons.append(
                "goal contains %d population-unsound bin(s) %r: no admissible "
                "payload reaches them under this exclusion rule, so no "
                "stimulus can close them meaningfully" % (len(pop), pop))
        run = [(cp, b) for cp, b, _ in self.run_unsound_bins() if cp == coverpoint]
        if run:
            reasons.append(
                "%d bin(s) %r were closed in this run only by non-admissible "
                "payloads" % (len(run), [b for _, b in run]))
        card, ch, ct = self.cardinality_coverage_pct(coverpoint)
        snd, sh, st = self.sound_coverage_pct(coverpoint)
        if card >= 100.0 and snd < 100.0:
            reasons.append(
                "cardinality coverage reads %.1f %% (%d/%d) while sound "
                "coverage is %.1f %% (%d/%d): the headline number overstates "
                "closure by %d bin(s)" % (card, ch, ct, snd, sh, st, ch - sh))
        return (not reasons), reasons


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

# Committed anchors, reproduced BEFORE any new number is computed, per
# 2026-09-30.  Source: witness_soundness_2026-10-03.txt, Section 4 tables.
# A file that re-derives these would agree with itself; these are quoted
# from the transcript and the derivation is independent.
ANCHORS = {
    "none":  {"g_first": (9, 2, [7, 8, 9]), "transitions": (5, 1, []),
              "cross": (25, 13, [(7, 1), (7, 3), (8, 1), (9, 1)])},
    "two":   {"g_first": (7, 0, [7]), "transitions": (5, 1, []),
              "cross": (23, 11, [(7, 1), (7, 3)])},
    "nine":  {"g_first": (7, 1, [7]), "transitions": (4, 1, []),
              "cross": (16, 4, [(7, 3)])},
}


def census(rows, excluded):
    cov = EvidenceSoundCoverage(rows, excluded=excluded)
    return {name: (len(cov.reachable_population(name)),
                   len(cov.scarce_bins(name)),
                   cov.population_unsound_bins(name))
            for name, _ in COVERPOINTS}


def main():
    rows = M.load_measured()
    nine = set(R.inadmissible_by_closed_form())
    two = {b for b in range(256) if M.classify(b, rows) == M.INADMISSIBLE}
    rules = {"none": set(), "two": two, "nine": nine}

    print("=" * 76)
    print("EVIDENCE-SOUNDNESS COVERAGE: THE MECHANISM THE BORDERLINE CASE")
    print("DID NOT HAVE  (2026-10-04)")
    print("=" * 76)

    head(1, "committed anchors reproduced before any new number")
    check("the live classifier's INADMISSIBLE set is v8's two bytes",
          sorted(two) == [0x00, 0x80], "0x%02X 0x%02X" % tuple(sorted(two)))
    check("the closed-form rule gives the vplan's nine bytes", len(nine) == 9,
          " ".join("0x%02X" % b for b in sorted(nine)))
    bord = sorted(b for b in range(256)
                  if M.classify(b, rows) == M.BORDERLINE)
    check("the classifier has exactly two BORDERLINE bytes",
          bord == [0x40, 0xC0], "0x%02X 0x%02X" % tuple(bord))
    for rule in ("none", "two", "nine"):
        got = census(rows, rules[rule])
        for cp in ("g_first", "transitions", "cross"):
            want = ANCHORS[rule][cp]
            check("anchor %-5s / %-11s bins/scarce/unsound" % (rule, cp),
                  got[cp] == want,
                  "got %r, committed %r" % (got[cp], want))

    head(2, "exactly-known values: every census is a PARTITION")
    cov = EvidenceSoundCoverage(rows, raise_on_illegal=False, excluded=nine)
    rng = random.Random(20261004)
    legal = [b for b in range(256) if b not in nine]
    for _ in range(2000):
        cov.sample(rng.choice(legal))
    # A per-bin class census must sum to the bin's total hits, and the bins
    # must sum to the number of samples, for EVERY coverpoint.  These are
    # integer identities, so they are exact, and they are exact under
    # ADDITION OF NON-NEGATIVE INTEGERS -- no tolerance and no float.
    for name, _ in COVERPOINTS:
        tot = sum(sum(c.values()) for c in cov.hits[name].values())
        check("partition: %s class counts sum to the sample count exactly"
              % name, tot == cov.n_samples,
              "%d == %d" % (tot, cov.n_samples))
    # and the three coverpoints must agree with each other, since each sample
    # lands in exactly one bin of each
    sums = [sum(sum(c.values()) for c in cov.hits[n].values())
            for n, _ in COVERPOINTS]
    check("partition: the three coverpoints see the same sample count",
          len(set(sums)) == 1, "%r" % (sums,))
    # cross bins must refine the marginals exactly
    gmarg = {}
    for (g, t), c in cov.hits["cross"].items():
        gmarg[g] = gmarg.get(g, 0) + sum(c.values())
    check("partition: the cross marginalises onto g_first exactly",
          gmarg == {g: sum(c.values()) for g, c in cov.hits["g_first"].items()})

    head(3, "the mechanism: run-unsound vs population-unsound are DIFFERENT")
    # (a) the structural case, which is the one 10-03 found
    cov_s = EvidenceSoundCoverage(rows, excluded=nine)
    check("population-unsound under the vplan rule: g_first bin 7",
          cov_s.population_unsound_bins("g_first") == [7],
          "witnesses %r, all non-admissible"
          % cov_s.reachable_population("g_first")[7])
    check("and cross cell (7, 3)",
          cov_s.population_unsound_bins("cross") == [(7, 3)])
    # (b) a run that closes a bin only with a BORDERLINE payload
    cov_b = EvidenceSoundCoverage(rows, excluded=nine)
    cov_b.sample(0x40)
    bad = cov_b.run_unsound_bins()
    check("a run that samples only 0x40 reports run-unsound bins",
          len(bad) == 3,
          "%r" % ([(cp, b) for cp, b, _ in bad],))
    # (c) THE CASE NO INSTRUMENT HERE COULD REPORT: a population-SOUND bin
    #     closed in a run only by bad evidence.  Found by search over all
    #     three coverpoints, not asserted -- and the first form of this
    #     search was WRONG and is recorded here rather than silently fixed.
    #     It ranged over `nine | borderline` as "the bad bytes", which
    #     conflates the vplan's EXCLUSION set with the live classifier's
    #     admissibility CLASS: it picked 0xE0, which the nine-byte rule
    #     excludes but `classify()` calls ADMISSIBLE, so sampling it is good
    #     evidence and the check failed on its own false premise.  The set
    #     that matters is {b : classify(b) != ADMISSIBLE}, and it must be
    #     searched over every coverpoint, because a byte can sit in a
    #     population-unsound bin of one coverpoint and a population-sound
    #     bin of another -- which is exactly what 0x40 does.
    probe = EvidenceSoundCoverage(rows, raise_on_illegal=False, excluded=nine)
    bad_bytes = [b for b in range(256)
                 if b not in nine and M.classify(b, rows) != M.ADMISSIBLE]
    witness = None
    for name, binner in COVERPOINTS:
        pop_unsound = set(probe.population_unsound_bins(name))
        pop = probe.reachable_population(name)
        for b in bad_bytes:
            k = binner(b)
            if k in pop_unsound:
                continue
            adm = [w for w in pop.get(k, [])
                   if M.classify(w, rows) == M.ADMISSIBLE]
            if adm:
                witness = (name, b, k, adm)
                break
        if witness:
            break
    if witness is None:
        check("a population-SOUND bin can be closed run-unsound", False,
              "SEARCH CAME BACK EMPTY -- reported, not papered over")
    else:
        name, b, k, adm = witness
        cov_c = EvidenceSoundCoverage(rows, raise_on_illegal=False,
                                      excluded=nine)
        cov_c.sample(b)
        run_bins = [x[1] for x in cov_c.run_unsound_bins() if x[0] == name]
        check("a population-SOUND bin can be closed run-unsound "
              "(the case no instrument here could report)",
              k in run_bins
              and k not in set(cov_c.population_unsound_bins(name)),
              "payload 0x%02X (%s) closes %s bin %r, which has %d admissible "
              "witness(es) %r it did not use -- so the bin is CLOSEABLE with "
              "interpretable evidence and this run did not do it, which a "
              "cardinality report calls covered and a population audit calls "
              "sound" % (b, M.classify(b, rows), name, k, len(adm), adm[:4]))
        check("CONTROL: the two axes are therefore NOT aliased -- the same "
              "payload is run-unsound on a sound bin and on an unsound one",
              set(x[1] for x in cov_c.run_unsound_bins()
                  if x[0] == "g_first") == {7},
              "0x%02X makes transitions bin 3 run-unsound (population-sound) "
              "AND g_first bin 7 run-unsound (population-unsound): one "
              "payload, two different verdicts, two different remedies" % b)

    # (d) ADDED 2026-10-04 BY THE MUTATION HARNESS, not by foresight.  M1
    #     loosens run_unsound to require a BORDERLINE witness, so a bin
    #     closed only by an INADMISSIBLE payload reads as sound -- the exact
    #     asymmetry 10-03 named, reintroduced on the run axis instead of the
    #     population axis -- and the suite as first written did not kill it,
    #     because no check anywhere closed a bin with an inadmissible
    #     payload.  The harness did not merely confirm this suite; it found
    #     a hole in it.  Both kinds of bad evidence are now asserted on, so
    #     the verdict is about ADMISSIBILITY and not about one subclass of
    #     its failure.
    cov_i = EvidenceSoundCoverage(rows, raise_on_illegal=False, excluded=nine)
    cov_i.sample(0x00)
    inadm_bins = {(cp, b): c for cp, b, c in cov_i.run_unsound_bins()}
    check("a bin closed only by an INADMISSIBLE payload is ALSO run-unsound "
          "(M1's hole, found by the harness)",
          ("g_first", 9) in inadm_bins
          and inadm_bins[("g_first", 9)][M.INADMISSIBLE] == 1
          and inadm_bins[("g_first", 9)][M.BORDERLINE] == 0,
          "0x00 closes g_first bin 9 with 1 inadmissible and 0 borderline "
          "witnesses: %r" % (sorted(inadm_bins, key=repr),))
    check("so the run verdict keys on ADMISSIBILITY, not on which kind of "
          "bad evidence: both the borderline-only and inadmissible-only "
          "closures are reported",
          ("g_first", 7) in {(cp, b) for cp, b, _ in cov_b.run_unsound_bins()}
          and ("g_first", 9) in inadm_bins)

    head(4, "the gate: sign_off() refuses, and names which remedy applies")
    cov_f = EvidenceSoundCoverage(rows, raise_on_illegal=False, excluded=nine)
    for b in [x for x in range(256) if x not in nine]:
        cov_f.sample(b)          # drive the entire legal population
    card = cov_f.cardinality_coverage_pct("cross")
    snd = cov_f.sound_coverage_pct("cross")
    print("  exhaustive legal stimulus, cross coverpoint:")
    print("    cardinality coverage %.2f %% (%d/%d)" % card)
    print("    sound       coverage %.2f %% (%d/%d)" % snd)
    check("exhaustive stimulus reaches 100 % CARDINALITY coverage",
          card[0] == 100.0)
    check("and does NOT reach 100 % SOUND coverage -- the gap is the "
          "population-unsound cell",
          snd[0] < 100.0,
          "overstatement = %d bin(s)" % (card[1] - snd[1]))
    ok, reasons = cov_f.sign_off("cross")
    check("sign_off() REFUSES an exhaustive run that reads 100 %", not ok,
          "%d reason(s)" % len(reasons))
    for r in reasons:
        print("      - %s" % r)
    check("and it separates the GOAL remedy from the STIMULUS remedy",
          any("change the GOAL" in r or "no stimulus can close" in r
              for r in reasons)
          and any("closed in this run" in r for r in reasons))
    # the raise path, parallel to IllegalPayload
    cov_r = EvidenceSoundCoverage(rows, excluded=nine,
                                  raise_on_unsound_closure=True)
    try:
        cov_r.sample(0x40)
        raised = False
    except UnsoundClosure as exc:
        raised, msg = True, str(exc)
    check("raise_on_unsound_closure=True raises UnsoundClosure on 0x40, "
          "exactly as raise_on_illegal raises IllegalPayload on 0x00", raised,
          msg if raised else "no raise")
    check("UnsoundClosure is an AssertionError, like IllegalPayload, so one "
          "except clause catches both kinds of bad evidence",
          issubclass(UnsoundClosure, AssertionError)
          and issubclass(M.IllegalPayload, AssertionError))
    # and a good run must NOT raise -- otherwise the gate fails on everything
    cov_g = EvidenceSoundCoverage(rows, excluded=nine,
                                  raise_on_unsound_closure=True)
    try:
        for b in [x for x in range(256)
                  if x not in nine and M.classify(x, rows) == M.ADMISSIBLE]:
            cov_g.sample(b)
        clean = True
    except UnsoundClosure as exc:
        clean, why = False, str(exc)
    check("CONTROL: an admissible-only run does NOT raise", clean,
          "%d admissible payloads driven, 0 unsound closures" % cov_g.n_samples
          if clean else why)

    head(5, "v8's numbers are unchanged -- this subclass ADDS, it does not edit")
    base = M.PayloadAdmissibilityCoverage(rows, raise_on_illegal=False)
    sub = EvidenceSoundCoverage(rows, raise_on_illegal=False)
    rng2 = random.Random(20261004)
    seq = [rng2.randrange(256) for _ in range(500)]
    for b in seq:
        base.sample(b)
        sub.sample(b)
    check("ctz_bins identical to the base class on the same 500-sample run",
          base.ctz_bins == sub.ctz_bins)
    check("tr_bins and cross identical too",
          base.tr_bins == sub.tr_bins and base.cross == sub.cross)
    check("coverage_pct() identical -- v8's headline number is untouched",
          base.coverage_pct() == sub.coverage_pct(),
          "%.4f %% (%d/%d)" % base.coverage_pct())
    check("classes census identical", base.classes == sub.classes)

    head(6, "what the DEFERRED rewiring will cost, measured rather than deferred")
    # The live classify() implements v8's two-byte rule; the vplan says nine.
    # Rather than nudge at that item again, measure the diff in verdicts.
    c2, c9 = census(rows, two), census(rows, nine)
    print("  %-12s %-22s %-22s" % ("coverpoint", "live 2-byte rule",
                                   "vplan 9-byte rule"))
    for cp in ("g_first", "transitions", "cross"):
        print("  %-12s bins=%-2d scarce=%-2d uns=%-2d  bins=%-2d scarce=%-2d uns=%-2d"
              % (cp, c2[cp][0], c2[cp][1], len(c2[cp][2]),
                 c9[cp][0], c9[cp][1], len(c9[cp][2])))
    print("  unsound sets:")
    for cp in ("g_first", "transitions", "cross"):
        print("    %-12s 2-byte %r   9-byte %r" % (cp, c2[cp][2], c9[cp][2]))
    check("the rewiring does NOT change WHICH g_first bin is unsound",
          c2["g_first"][2] == c9["g_first"][2] == [7],
          "bin 7 under both rules -- so the headline defect 10-03 found is "
          "NOT an artefact of the rule disagreement")
    check("but it DOES change the cross: 2 unsound cells become 1",
          len(c2["cross"][2]) == 2 and len(c9["cross"][2]) == 1,
          "%r -> %r; (7,1) leaves the goal because the nine-byte rule "
          "excludes its only witnesses, not because it became sound"
          % (c2["cross"][2], c9["cross"][2]))
    check("and it changes the transition coverpoint's CARDINALITY, which no "
          "soundness verdict would have shown",
          c2["transitions"][0] != c9["transitions"][0],
          "%d bins -> %d bins" % (c2["transitions"][0], c9["transitions"][0]))

    head(7, "the four quadrants, now computable from the LIVE model")
    cov_q = EvidenceSoundCoverage(rows, excluded=nine)
    for cp in ("g_first", "transitions", "cross"):
        sc = set(cov_q.scarce_bins(cp))
        un = set(cov_q.population_unsound_bins(cp))
        allb = set(cov_q.reachable_population(cp))
        print("  %-12s abundant+sound %2d  abundant+UNSOUND %2d  "
              "scarce+sound %2d  scarce+UNSOUND %2d"
              % (cp, len(allb - sc - un), len(un - sc),
                 len(sc - un), len(sc & un)))
    check("the abundant+UNSOUND quadrant is still EMPTY in this population, "
          "and that is a fact about F7's two borderline bytes, not a theorem",
          all(len(set(cov_q.population_unsound_bins(cp))
                  - set(cov_q.scarce_bins(cp))) == 0
              for cp in ("transitions", "cross")),
          "g_first bin 7 has 1 witness under the nine-byte rule, so it is "
          "scarce+unsound; a model with a wider borderline band would put a "
          "bin in the empty quadrant, which NO scarcity scan at any "
          "threshold would find")

    print()
    print("=" * 76)
    print("SUMMARY: %d passed, %d failed" % (len(_PASS), len(_FAIL)))
    for f in _FAIL:
        print("  FAILED: %s" % f)
    print("=" * 76)
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
