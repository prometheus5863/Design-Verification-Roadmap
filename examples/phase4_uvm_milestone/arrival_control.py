#!/usr/bin/env python3
"""arrival_control.py -- the 2026-09-29 arrival control, shared and
THREE-VALUED.  2026-10-09.

Background.  2026-10-08 established the rule that a mutant may be scored
SURVIVED only after it has been shown to have changed something the mechanism
under test prints, and mechanised it inside
`mutation_test_signatures.py` as

    blk      = signature_block(out)          # "" if the block is absent
    arrived  = (blk != baselines[tc])

That is a two-valued comparison, and it is the one line of that session's work
that this module exists to replace.

THE GAP, which is asymmetric and was in the half that was not guarded.
`mutation_test_signatures.py` guards the BASELINE side: if control A produces
no signature block it prints "one with no signature block has nothing for the
arrival control to compare against" and ABORTS.  Correct, and it is 2026-10-02
check R0's rule -- "this artefact does not contain what I audit" is a failed
check, not a crash and not a pass.  **The MUTANT side has no such guard.**  If a
mutant run emits no signature block at all, `blk` is "" and the baseline is
not, so `blk != baseline` is True, `arrived` is True, and -- absent a killer --
the row is scored **SURVIVED on the strength of a block that does not exist**.

The two cases a two-valued comparison conflates:

    the block DIFFERS          -> the mutant reached the mechanism
    the block is NOT THERE     -> the mechanism was not observed at all

and the second is the stronger evidence of something being wrong, scored as the
weaker of the two possible verdicts.  Same shape as 2026-10-06 (the detector
misattributing what it measured) and as the ZeroDivisionError of 2026-10-02:
the absence of the artefact being read as a value of it.

So arrival is three-valued here:

    ARRIVED         the mutant's block is present and differs from the baseline
    INERT           the mutant's block is present and is byte-identical
    NO_OBSERVATION  one of the two blocks is missing or empty

and NO_OBSERVATION voids the row rather than scoring it, exactly as the text
controls' unusable tokens do in `mutation_test_signatures.controls_text()`.

Every path below is exercised by `--selftest`, including both NO_OBSERVATION
sides and a direct comparison against the retired two-valued rule showing the
verdict they disagree on.  2026-10-01: a control that cannot fail is not a
control, and that applies to this one too.
"""
import sys

ARRIVED = "ARRIVED"
INERT = "INERT"
NO_OBSERVATION = "NO_OBSERVATION"


def arrival(baseline_block, mutant_block, what="the mechanism's output block"):
    """-> (token, detail).

    `baseline_block` / `mutant_block` are the mechanism-specific blocks the
    caller extracted from control A's run and from the mutant's run.  A caller
    whose extractor returns None or "" for "not found" gets NO_OBSERVATION
    rather than a comparison, which is the whole point of this module.
    """
    b_missing = baseline_block is None or baseline_block.strip() == ""
    m_missing = mutant_block is None or mutant_block.strip() == ""
    if b_missing and m_missing:
        return (NO_OBSERVATION,
                "neither control A nor the mutant produced %s, so there is "
                "nothing to compare and the two absences would compare EQUAL "
                "-- which a two-valued rule scores as INERT" % what)
    if b_missing:
        return (NO_OBSERVATION,
                "control A produced no %s, so the baseline is not a baseline "
                "(2026-10-02 check R0)" % what)
    if m_missing:
        return (NO_OBSERVATION,
                "the mutant produced no %s at all.  A two-valued `mutant != "
                "baseline` rule reports this as ARRIVED, because an absent "
                "block differs from a present one, and the row is then scored "
                "SURVIVED on the strength of evidence that does not exist"
                % what)
    if mutant_block == baseline_block:
        return (INERT,
                "the mutant's %s is BYTE-IDENTICAL to control A's: the mutant "
                "changed nothing this mechanism reports" % what)
    return (ARRIVED,
            "the mutant's %s differs from control A's, so the mutant reached "
            "the mechanism" % what)


def two_valued_legacy(baseline_block, mutant_block):
    """The retired rule, kept so the disagreement can be MEASURED rather than
    asserted.  `mutation_test_signatures.py` 2026-10-08, verbatim semantics:
    an absent block is spelled "" and "" != baseline is True."""
    b = "" if baseline_block is None else baseline_block
    m = "" if mutant_block is None else mutant_block
    return ARRIVED if m != b else INERT


def classify(killers, arrival_token):
    """The outcome of one mutant row.  -> (outcome, reason).

    A killer outranks arrival: a mutant the suite caught arrived by
    construction, whatever the block says.  Below that, only ARRIVED may be
    scored SURVIVED.
    """
    if killers:
        return "KILLED", "the suite failed: %s" % ", ".join(killers)
    if arrival_token == ARRIVED:
        return "SURVIVED", "the mutant reached the mechanism and was not caught"
    if arrival_token == INERT:
        return ("INERT",
                "the mutant changed nothing the mechanism reports, so it "
                "neither survived nor was killed -- it never arrived")
    return ("VOIDED",
            "arrival could not be observed, so no verdict is available for "
            "this row")


def usable(outcome):
    """Rows that carry information about the suite's detection power."""
    return outcome in ("KILLED", "SURVIVED")


# ---------------------------------------------------------------------------
# selftest -- every branch, both NO_OBSERVATION sides, and the disagreement
# ---------------------------------------------------------------------------
def selftest():
    B = "COV_SIGNATURE: 9 of 256 cells EXACT\n  mask=0x00ff\n"
    M_SAME = "COV_SIGNATURE: 9 of 256 cells EXACT\n  mask=0x00ff\n"
    M_DIFF = "COV_SIGNATURE: 7 of 256 cells EXACT\n  mask=0x003f\n"

    cases = [
        ("baseline present, mutant differs", B, M_DIFF, ARRIVED, "SURVIVED"),
        ("baseline present, mutant identical", B, M_SAME, INERT, "INERT"),
        ("mutant block ABSENT (the 10-08 gap)", B, "", NO_OBSERVATION, "VOIDED"),
        ("mutant block is whitespace only", B, "   \n ", NO_OBSERVATION, "VOIDED"),
        ("mutant block is None", B, None, NO_OBSERVATION, "VOIDED"),
        ("baseline ABSENT (R0, guarded upstream too)", "", M_DIFF,
         NO_OBSERVATION, "VOIDED"),
        ("BOTH absent -- compare EQUAL, so a two-valued rule says INERT",
         "", "", NO_OBSERVATION, "VOIDED"),
    ]

    print("=" * 76)
    print("arrival_control.py SELFTEST")
    print("=" * 76)
    print()
    print("  %-46s %-15s %s" % ("case", "arrival", "outcome (no killers)"))
    print("  " + "-" * 72)
    ok = True
    for label, b, m, want_tok, want_out in cases:
        tok, _ = arrival(b, m)
        out, _ = classify([], tok)
        good = (tok == want_tok and out == want_out)
        ok = ok and good
        print("  %-46s %-15s %-10s %s"
              % (label[:46], tok, out, "[PASS]" if good else
                 "[FAIL] wanted %s/%s" % (want_tok, want_out)))

    print()
    print("  A killer outranks arrival, including an INERT row:")
    tok, _ = arrival(B, M_SAME)
    out, reason = classify(["UVM_ERROR=1"], tok)
    good = (out == "KILLED")
    ok = ok and good
    print("    arrival=%s with a killer -> %s   %s"
          % (tok, out, "[PASS]" if good else "[FAIL]"))

    print()
    print("  WHERE THE RETIRED TWO-VALUED RULE DISAGREES, measured:")
    print("  %-46s %-12s %-12s %s"
          % ("case", "two-valued", "three-valued", "verdict it produced"))
    print("  " + "-" * 72)
    disagreements = 0
    for label, b, m, want_tok, want_out in cases:
        new_tok, _ = arrival(b, m)
        old_tok = two_valued_legacy(b, m)
        if old_tok != new_tok:
            disagreements += 1
            old_out, _ = classify([], old_tok)
            new_out, _ = classify([], new_tok)
            print("  %-46s %-12s %-12s %s -> %s"
                  % (label[:46], old_tok, new_tok, old_out, new_out))
    # The expected count is DERIVED, not typed in.  The legacy rule has no
    # NO_OBSERVATION value at all, so every case the three-valued rule calls
    # NO_OBSERVATION is a disagreement by construction, and no other case can
    # be one (both rules agree on present-and-differs and present-and-equal).
    # The first draft of this check carried a literal 4 and FAILED at 5,
    # because it had counted the cases where the legacy rule said SURVIVED and
    # forgotten the both-absent case where it said INERT.  Repaired by
    # deriving the number rather than by editing the literal -- 2026-10-09's
    # graphene session hit the same choice on the same day and the rule is the
    # same one: when an exactness check fails, find out what it measured.
    want_disagreements = sum(
        1 for _, b, m, _, _ in cases if arrival(b, m)[0] == NO_OBSERVATION)
    as_survived = sum(
        1 for _, b, m, _, _ in cases
        if arrival(b, m)[0] == NO_OBSERVATION
        and classify([], two_valued_legacy(b, m))[0] == "SURVIVED")
    as_inert = want_disagreements - as_survived
    print()
    print("  %d of %d cases disagree, and that is exactly the number of"
          % (disagreements, len(cases)))
    print("  NO_OBSERVATION cases: the legacy rule has no such value, so every")
    print("  one of them disagrees by construction and nothing else can.")
    print("  Of those %d, the legacy rule scored %d SURVIVED and %d INERT."
          % (want_disagreements, as_survived, as_inert))
    print("  THE %d SURVIVED ONES ARE THE DANGEROUS HALF: an absent mutant"
          % as_survived)
    print("  block, a whitespace-only one, a None, and an absent BASELINE.  In")
    print("  each the mechanism was not observed at all, and 'SURVIVED' is a")
    print("  claim that it WAS observed and said nothing -- a false finding")
    print("  about working code, which 2026-10-08 ranked strictly worse than a")
    print("  missed defect because it arrives with a transcript.")
    good = (disagreements == want_disagreements and want_disagreements > 0)
    ok = ok and good
    print("  [%s] every NO_OBSERVATION case disagrees with the legacy rule, "
          "and no other case does" % ("PASS" if good else "FAIL"))

    print()
    print("  usable() admits only rows that carry detection information:")
    for o in ("KILLED", "SURVIVED", "INERT", "VOIDED"):
        print("    %-9s -> %s" % (o, usable(o)))
    good = (usable("KILLED") and usable("SURVIVED")
            and not usable("INERT") and not usable("VOIDED"))
    ok = ok and good
    print("  [%s] INERT and VOIDED are not usable"
          % ("PASS" if good else "FAIL"))

    print()
    print("=" * 76)
    print("SELFTEST: %s" % ("PASS" if ok else "FAIL"))
    print("=" * 76)
    return 0 if ok else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    print(__doc__)
    print("Run with --selftest to exercise every branch.")
    sys.exit(0)
