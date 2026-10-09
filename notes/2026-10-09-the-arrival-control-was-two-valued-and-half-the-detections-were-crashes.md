# The arrival control was two-valued, and half the detections were crashes

**2026-10-09.** Session notes. New: `examples/phase4_uvm_milestone/arrival_control.py`
(+ `arrival_control_selftest.txt`), `arrival_control_census.py`
(+ `arrival_control_census_output.txt`), and the arrival control wired into
`mutation_test_reachable_cross.py`
(+ `mutation_reachable_cross_arrival_2026-10-09.txt`).

---

## 1. What was picked, and why this one

10-08 left two items at the top:

> **A POSITIVE CONTROL THAT MAKES S-f FIRE** — … Until it exists, S-f is a
> control with no control.
>
> **THE ARRIVAL CONTROL, WIRED INTO THE OTHER HARNESSES** — … Any of those five
> could be carrying the same thing now.

The second was taken, for a reason that decided the shape of the whole session:
**four of the five named harnesses need a uvm-python simulation per mutant
row**, which no single session has re-run, and one does not. So the choice was
between wiring five harnesses and running none, or wiring one and measuring it.
Wiring without running produces a committed instrument nobody has seen work —
09-19's class, the subsystem reporting the verdict not being the one doing the
checking. One, run, with the rest made into a measured number.

## 2. The arrival control was two-valued, and the gap was in the half nobody guarded

10-08 mechanised the arrival rule inside `mutation_test_signatures.py` as

```python
blk     = signature_block(out)      # "" when the block is absent
arrived = (blk != baselines[tc])
```

The **baseline** side is guarded. Control A with no signature block prints
"one with no signature block has nothing for the arrival control to compare
against" and ABORTS — correct, and it is 10-02's check R0: *this artefact does
not contain what I audit* is a failed check, not a crash and not a pass.

**The mutant side has no such guard.** If a mutant run emits no signature
block, `blk` is `""`, `"" != baseline` is True, `arrived` is True, and absent a
killer the row is scored **SURVIVED on the strength of a block that does not
exist**.

The two cases a two-valued comparison conflates:

| observation | what it means | two-valued verdict |
|---|---|---|
| the block differs | the mutant reached the mechanism | ARRIVED → SURVIVED |
| **there is no block** | the mechanism was **not observed** | ARRIVED → SURVIVED |

The second is the stronger evidence that something is wrong, and it is scored
as the weaker of the two available verdicts. Same shape as 10-06, where the
detector misattributed what it had measured, and as 10-02's
`ZeroDivisionError`: the absence of the artefact read as a value of it.

`arrival_control.py` is three-valued — ARRIVED / INERT / NO_OBSERVATION — with
NO_OBSERVATION voiding the row the way `controls_text()`'s unusable tokens do.
`classify()` lets a killer outrank arrival (a mutant the suite caught arrived
by construction) and admits only ARRIVED to SURVIVED.

**The retired rule is kept as `two_valued_legacy()` so the disagreement is
measured rather than argued** (10-02: when two artefacts agree, that is a fact
about two artefacts — and the same holds when they disagree). Of seven selftest
cases, **five disagree**: four the old rule scored SURVIVED (absent mutant
block, whitespace-only block, `None`, absent *baseline*) and one it scored
INERT (both absent, which compare equal). 10-01: a control that cannot fail is
not a control, and both NO_OBSERVATION sides are exercised.

### The selftest's own count check failed, and was repaired by deriving it

The disagreement check was first written with a literal `4` and failed at `5`:
the draft had counted the legacy-SURVIVED cases and forgotten the both-absent
case. Repaired by **deriving** the number from the property that actually
holds — the legacy rule has no NO_OBSERVATION value, so every NO_OBSERVATION
case disagrees by construction and nothing else can — rather than by editing
the literal to 5. The graphene repository's session the same day hit the same
choice three times and reached the same rule: **when an exactness check fails,
find out what it measured before deciding what to change.**

## 3. What wiring it actually found, which is not what it was pointed at

`mutation_test_reachable_cross.py`, 9 rows, all 9 still behaving as required.

**Expected result.** Three rows are *required* to survive: CONTROL B's
semantics-preserving rename, and M6a/M6b, whose prose has argued since 10-02
that "a weakened assertion still holds on correct input, so no self-run can
catch it". All three come back **INERT** — the harness's own argument turned
from prose into a byte comparison. The suite did not fail to notice the mutant;
the mutant produced nothing for it to notice. The report says explicitly that
an INERT count is the specification here and bad news everywhere else, because
otherwise the next reader subtracts three from a detection score.

**Unexpected result.** M1, M4 and M5 come back **NO_OBSERVATION**:

```
  M1 span_of returns g_first ...        NO_OBSERVATION  (suite crashed)
        ZeroDivisionError: float division by zero
  M4 reachable_cross ignores the exclusion   NO_OBSERVATION  (suite crashed)
        TypeError: unsupported operand type(s) for +: 'int' and 'NoneType'
  M5 closure gives up after one draw         NO_OBSERVATION  (suite crashed)
        TypeError: unsupported operand type(s) for +: 'int' and 'NoneType'
```

The harness scored all three **"DETECTED (correct)"**, because its rule was

```python
detected = (f_ is None) or (f_ > 0)
```

and `f_ is None` means *the `TOTAL:` line is missing*, i.e. the suite **died**.

> **Three of this harness's six detections were the python interpreter catching
> the mutant, reported in the same column and the same words as the three a
> check caught.**

| detected by | count | mutants |
|---|---|---|
| a failing check | **3** | M2, M3, M6c |
| an unhandled exception | **3** | M1, M4, M5 |

That is 10-06's misattribution — credit assigned to a mechanism that did not
earn it — and it is the **mirror image of 10-08's false SURVIVED: a false
DETECTED**, a true-positive outcome reached by a mechanism other than the one
being measured.

### Scored honestly in both directions

It would be wrong to re-score these as escapes. A crash means the mutant was
**not silently accepted**, so none of the three is a hole in the suite today,
and claiming otherwise would be the opposite error. What is true is that the
exposure is **conditional**, and that is exactly why it deserves a number:

> If the suite is ever made to degrade gracefully, or wrapped in a
> `try/except`, **3 of 6 detections become silent passes and no row of this
> harness changes.**

A single defensive `except Exception: print("TOTAL: 0 passed, 0 failed")`
anywhere in that suite would halve its measured detection power without
failing anything. The counts are now split DETECTED_BY_CHECK against
DETECTED_BY_CRASH, the split is printed, and writing a check that catches each
of the three on its own terms is a named follow-on item rather than a repair
attempted in the session that found the need for it.

## 4. A census, because the backlog entry could not notice its own staleness

10-08's item is a sentence listing five files. A sentence cannot notice a
harness being added, a harness being wired, or a registry row that claims more
than its source does. `arrival_control_census.py` is that item as a
measurement, with the graphene repository's 10-08 staleness-guard pattern: **a
harness on disk and absent from the registry is a FAULT, not a blank.**

Five failure paths; F1 (unregistered harness), F2 (registry row with no file)
and F3 (adjudication disagrees with source) are exercised by `--selftest`
against injected rows. F3 is the one that matters — it is what stops the census
becoming a list of intentions.

| harness | arrival control |
|---|---|
| `mutation_test_reachable_cross.py` | **THREE_VALUED** (today) |
| `mutation_test_signatures.py` | TWO_VALUED (10-08; mutant side unguarded) |
| `mutation_test_witnesses.py` | NONE |
| `mutation_test_coverage_axis.py` | NONE |
| `mutation_test_evidence_soundness.py` | NONE |
| `mutation_test_witness_soundness.py` | NONE — **cheapest remaining** |

**OPEN: 5 of 6, 0 faults.**

`mutation_test_signatures.py` is deliberately **not** rewired. It needs one
uvm-python sim per row; this session could not re-run it; and an unverified
edit to a committed instrument is worse than a gap that is measured and
reported. That reasoning is in the registry row, not only here.

### And the census flagged the one harness it had just wired

The first draft classified on the raw file and raised **F4** — "still contains
a two-valued comparison" — against `mutation_test_reachable_cross.py`, the
single harness that *had* been wired three-valued. The reason: **that harness's
docstring explains the retired rule, and therefore contains the literal text
`mutant != baseline`.** The detector could not tell a rule from a description
of a rule.

This is 10-06 exactly. There, a bare `S-[a-f] FAILED` regex also matched inside
the summary sentence that merely *named* the checks, crediting S-f with
detections it never made; the fix was to anchor on the colon. It is also the
inverse of 09-28: prose is a detector, and here prose was **detected as code**.
In a repository whose house style is long explanatory docstrings, this is not a
corner case — it is the default.

Fixed **structurally**, not with a cleverer regex, which would be the same bet
again: classification runs on a `tokenize` stream with COMMENT and STRING
dropped; a file that will not tokenise raises F5 rather than being quietly
classified on prose; and `--selftest` asserts that F4 does *not* fire against
`reachable_cross` on the live registry, so the prose path is a standing
regression check and not a one-time repair.

## 5. Methodological note

09-17: a suite can pass against broken RTL. 09-18: and print PASS over its own
errors. 09-19/09-20: the subsystem reporting the verdict is not the one doing
the checking. 09-26: a reachability pre-pass answers "did my attempts reach
it". 09-30: a control has to sit where the failure enters. 10-01: an arrival
control that cannot fail is not a control. 10-05: a metric can be printed
beside the thing it does not measure. 10-06: and the detector can misattribute
what it measured. 10-07: an injection guard is a measurement, so "did the file
change" is the wrong question. 10-08: and a mutant reporting SURVIVED under a
stimulus that cannot reach it is a false finding about working code, strictly
worse than a missed defect because it arrives with a transcript.

**10-09: AND THE SAME IS TRUE OF A DETECTION. A MUTANT SCORED DETECTED BECAUSE
THE SUITE CRASHED IS A CLAIM ABOUT THE SUITE'S CHECKS THAT THE SUITE'S CHECKS
DID NOT MAKE.**

The checkable rule: **a verdict must name the mechanism that produced it.**
"DETECTED" is not a verdict; "detected by a failing check" and "detected by an
unhandled exception" are, and they have different futures — the second
evaporates the moment the code under test learns to fail gracefully. 10-08
mechanised this for SURVIVED and the arrival control is the instrument; today
is the observation that the positive column needed the same treatment and
nobody had looked, because a true positive feels like it needs no provenance.

Second rule, from §4: **a pattern that matches a rule also matches prose about
the rule, and in this repository prose about rules is most of the text.** Two
detectors have now been bitten by it three days apart (10-06's S-tag regex,
today's F4), and both were repaired by making the matcher structural — anchor
on a colon, tokenise and drop strings — rather than by making the pattern more
specific. The generalisable form: **a textual detector over this repository's
own source must be told where the code ends.**

## 6. What was not done

- **`mutation_test_signatures.py` is not rewired.** Needs a uvm-python sim per
  row. It is the TWO_VALUED row in the census and the reason is recorded there.
- **The four sim-based harnesses are not wired.** Measured, not pretended.
- **No check was written for M1/M4/M5's crashes.** Naming the need and filling
  it in the same session is how a repair gets written to the shape of the
  finding rather than the shape of the fault.
- **Item 1, the positive control that makes S-f fire, was not touched.** It
  needs the same sim loop as the four harnesses above and is unchanged at the
  top of the backlog.
