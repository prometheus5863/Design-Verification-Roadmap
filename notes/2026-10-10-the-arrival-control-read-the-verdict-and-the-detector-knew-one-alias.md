# 2026-10-10 — The arrival control was reading the verdict, and two rows were not uncaught but unobservable

Session notes. Work: wire `mutation_test_witness_soundness.py` with the
2026-10-09 three-valued arrival control **and** the provenance field 10-09
opened as an item, then fix what the census found about itself.

Artefacts: `mutation_test_witness_soundness.py` (13/13 rows, extractor
selftest 14/14), `mutation_report_witness_soundness_2026-10-10.txt`,
`mutation_witness_soundness_selftest_2026-10-10.txt`,
`arrival_control_census.py` (0 faults, OPEN 4 of 6),
`arrival_control_census_output.txt`,
`arrival_control_census_selftest_2026-10-10.txt`, `progress.md`.

---

## 1. Why this harness, and the two defects it carried

`arrival_control_census.py` named it the cheapest unwired row: its target is
`witness_soundness.py`, a python mechanism, so it is the only other harness
re-runnable inside a session. It carried both of 10-09's open defects at once:

- **no arrival control at all** — a row marked SURVIVE was scored on the
  strength of a stimulus nobody had shown reached the mechanism (10-08: a
  false SURVIVED is worse than a missed defect, because it arrives with a
  transcript);
- **no provenance on a detection** — the rule was `detected = rc != 0`, and a
  python traceback exits non-zero too (10-09, in this repository's sibling
  harness: 3 of 6 detections turned out to be the interpreter).

## 2. Provenance, and the answer is the opposite of 10-09's

**9 of 9 detections here are a failing check. None is the interpreter.**
`mutation_test_reachable_cross.py` was 3 of 6 the other way. That difference
is the argument for the field existing: had this harness been assumed healthy
by analogy, or assumed sick by analogy, both guesses would have been wrong,
and the only way to know was to measure.

`provenance()` has a third branch, and it is a **fault** rather than a
tidy-up:

| observation | tag |
|---|---|
| non-zero exit, `TOTAL:` reports failures | `DETECTED_BY_CHECK` |
| non-zero exit, no `TOTAL:` line | `DETECTED_BY_CRASH` |
| non-zero exit, `TOTAL:` reports **0** failures | **FAULT** |
| exit 0, `TOTAL:` reports failures | **FAULT** |

The last two are the 09-19/09-20 decoupling — *the subsystem reporting the
verdict is not the one doing the checking* — which this repository has found
live twice. A harness that reads only one of the two cannot see it.

## 3. The finding: an arrival control must not read the verdict

`witness_soundness.py` prints its computed report in SECTIONS 1–8 and its
PASS/FAIL list after SUMMARY — **except** that SECTION 8's controls print
`[PASS]`/`[FAIL]` **inline**, interleaved with the numbers those controls
computed:

```
  [PASS] C1 the instrument responds to the EXCLUSION (three sizes, three answers)
        no exclusion 25, 2-byte 23, 9-byte 16
```

A block cut straight out of SECTIONS 1–8 therefore contains verdict tokens.
**An arrival control that reads a verdict token is reading the killer** — it
stops being independent of the exact thing it exists to be independent of, and
a mutant that flips one verdict and computes nothing new is scored ARRIVED.

`mechanism_block()` normalises `[PASS]`/`[FAIL]` to `[VERDICT]`. The harness
then computes arrival **both ways and reports the disagreement** instead of
asserting there is none:

```
  M8c  stripped INERT   raw ARRIVED   outcome KILLED
  M9   stripped INERT   raw ARRIVED   outcome KILLED
```

**Two rows disagree and no outcome changes**, because a killer outranks
arrival in both. So the strip changes nothing today, and it is kept anyway for
two reasons that are not "it might matter later": it makes the independence
structural rather than coincidental, and the verdict text is precisely the
artefact this repository has twice found decoupled from the checks. Reading
it would mean reading a value already known here to be unreliable.

**M9 is new and exists to make the disagreement visible.** It changes C1's
expected tuple from `(25, 23, 16)` to `(25, 23, 15)`: the suite fails, and
nothing computed changes, because C1's detail line is a **typed literal** and
not a format of the three lengths it checks.

## 4. Control A stopped being a tautology

Control A used to expect SURVIVE. Under a three-valued rule it came back
INERT — a run compared against itself always will.

The row is not useless, though; it is **the determinism control**. The harness
runs the suite twice — once for the baseline and once as row A — and compares
the two reports. `witness_soundness.py` sweeps 40 seeds; if any of that were
nondeterministic, the two runs would differ, control A would come back
ARRIVED, and **every INERT in the table below would be unreliable**. Control A
is now the precondition the rest of the instrument rests on, and its other
half — *the unmutated suite must pass* — moved into a pre-flight abort, where a
missing baseline block prints no rows at all (10-02's check R0).

An arrival control needs a determinism control under it, and nobody had
written one.

## 5. Two rows are not uncaught but unobservable

M8b — 10-03's compound form, *weaken C3's threshold and perturb what it
guards* — was specified **SURVIVE** and measures **INERT**.

The reason is the same as M9's: C3's detail is the typed literal
`"7 of 7 -- so the instrument is not hard-coded to find exactly one"`, so the
quantity M8b perturbs is **never printed**. The mutant does not reach anything
observable. It is not merely uncaught; it is **unobservable**, and the
threshold M8a weakens was its **sole observer**.

That is a sharpening of 10-02, not a loosening of it. 10-02 concluded the
threshold is load-bearing. Today's version: the threshold is *the only
load-bearing thing there is*, because the report carries no independent trace
of the quantity it guards. Weaken it and the quantity becomes not just
unchecked but invisible.

### The census that explains it, as a check rather than a note

| `check()` detail | count |
|---|---|
| derived from the quantity checked | 13 |
| **typed literal** | **18 (58 %)** |
| of the six C-controls, typed literal | **five** (C1–C5; C6 derives) |

Eighteen places where a mutant can change a verdict and change nothing in the
report — i.e. eighteen places no arrival control can see. 2026-10-01 said a
name that cannot drift is the whole requirement; this is the same fault in
detail-string form, and it is **measured** rather than noticed once.

The guard is written to **fail if the file improves**: if C1's or C3's detail
is ever derived, M8b and M9 become observable and their INERT expectations are
stale, so the harness says so. Reported and not fixed, because
`witness_soundness.py` owns a committed transcript.

And one more row worth keeping: **M8c is KILLED while being INERT.** An
assertion can observe what the report does not.

## 6. The census caught the session using it, and it was the mirror of its own 10-09 defect

After the registry row moved to THREE_VALUED, `arrival_control_census.py`
raised **F3 — the registry adjudicates THREE_VALUED and the source shows
NONE**. The registry was right; the classifier was wrong.

```python
uses_ac = re.search(r"\bAC\s*\.\s*arrival\s*\(|"
                    r"\barrival_control\s*\.\s*arrival\s*\(", code)
```

`mutation_test_reachable_cross.py` writes `import arrival_control as AC`, so
this worked. The new harness writes `as ac`.

**This is the mirror of the defect found in this same function on 10-09.**
That one was a **false positive from matching prose** — F4 raised against the
one harness that had just been wired, because its docstring quotes the rule it
retired. This is a **false negative from matching one alias**. Same root cause
three days apart: *a textual pattern standing in for a structural fact.*

The cheap repair was sitting right there: rename the new harness's alias to
`AC`. The census goes green, and it stays unable to read the next harness
anyone writes. That is the testing equivalent of widening a tolerance until it
passes — and the graphene repository's session today named exactly that move
as the thing its item 15 exists to catch. Repaired structurally, as 10-09's
was: the binding is read out of the import statement with `ast`, so every
alias works, from-imports work, and an alias that was never imported never
counts.

Eight alias cases in `--selftest`, including the two that must **not** count
(the call in a comment, the call in a string — 10-09's prose path, still
closed) and one alias nobody has used yet, so the next spelling is covered
before it is written. A misclassification raises a new **F6**.

## 7. Methodological note

09-17: a suite can pass against broken RTL. 09-18: and print PASS over its own
errors. 09-19/09-20: the subsystem reporting the verdict is not the one doing
the checking. 09-26: a reachability pre-pass answers "did my attempts reach
it". 09-30: a control has to sit where the failure enters. 10-01: an arrival
control that cannot fail is not a control. 10-05: a metric can be printed
beside the thing it does not measure. 10-06: and the detector can misattribute
what it measured. 10-07: an injection guard is a measurement. 10-08: a false
SURVIVED is worse than a missed defect. 10-09: and so is a false DETECTED — a
verdict must name the mechanism that produced it.

**10-10: AND A CONTROL MUST NOT READ THE THING IT CONTROLS FOR. An arrival
control that reads the suite's verdict is the killer wearing an arrival
control's name.**

The checkable rule: **an arrival block has to be cut from what the mechanism
COMPUTED, never from what the suite CONCLUDED** — and when a report interleaves
the two, as this repository's house style does, the cut has to be made
structurally and the two readings compared rather than one of them trusted.

Second rule, from §5: **a quantity whose only observer is the assertion that
checks it cannot be verified by anything downstream of that assertion.**
Mutation testing finds a weakened assertion only if something else prints the
quantity. The remedy is not a better mutant; it is a derived detail string.
Mechanisable: a census of every `check(label, cond, detail)` in this
repository, flagging a typed-literal detail as a place where a verdict can
move without the report moving. 18 of 31 in one file is the first data point.

Third, from §6: **a detector that failed twice in opposite directions failed
once, in the same place.** Prose matched as code, and one alias mistaken for
all aliases, are the same fault. Both repairs were structural and both were
available the first time.

**Cross-repository note.** The graphene session today reached the complementary
rule from the numerical side: *there is a fourth repair when a check
misbehaves — delete the criterion and check the claim instead.* Both sessions
are about what a check is actually attached to. There it was a round tolerance
with no claim underneath it; here it was an arrival block with the verdict
inside it. The crossover candidate is unchanged and now sharper: the graphene
mutation harnesses still compare verdicts rather than output blocks, and that
is precisely the mistake §3 names.
