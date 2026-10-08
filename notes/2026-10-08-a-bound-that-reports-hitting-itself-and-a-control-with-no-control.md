# A bound that reports hitting itself, and a control with no control

**2026-10-08.** The run-axis audit named its own successor on 2026-10-06 and
this session built it. The build went as specified. What did not go as
specified was the mutation harness, whose first run said the mechanism fails
to detect its two most important faults — and was wrong, in a way that took a
new control to see.

---

## 1. The repair, exactly as 10-06 specified it

2026-10-06's `run_axis_audit.py` ended with its own top open item:

> the collector should keep a **bounded set of distinct payload signatures**
> per cell alongside its first-N witnesses. That makes diversity exact at the
> same log cost, because the set stops growing once the stimulus stops
> varying — which is precisely the case this audit is trying to detect.

`UartCoverage` now does. A **signature** is a witness with the two per-sample
fields removed: no ordinal, no simulation time, only the analysis port and the
item's own `convert2string()`. Two samples carrying identical stimulus
therefore collapse to one entry, and the size of the set *is* the cell's
stimulus diversity.

### Why this is not just a larger `WITNESS_KEEP`

A witness list answers *which sample closed this cell, and in what order.*
Order is what counts destroy, and is why witnesses carry an ordinal. A
signature set answers *how many different things hit this cell*, and for that
the ordinal is **noise** — it would make every entry distinct and the count
meaningless. Two bookkeepings, two questions, the same samples. Which is
exactly why check **S-d** requires them to agree: every retained witness's
stimulus must appear in its cell's signature set, because both paths see the
same samples and a witness whose stimulus is absent means the signature path
missed one.

### The bound reports hitting itself

`SIGNATURE_KEEP = 16`, and `sig_overflow` counts the distinct signatures the
bound **refused**, per cell. A cell prints `EXACT` or `BOUNDED (+n refused)`.
2026-10-03's rule in its sharpest form: *a bound that cannot report hitting
itself is not a bound, it is a silent truncation* — and a silent truncation
that prints the word `EXACT` is worse than no signature set at all, because
the entire purpose of the set is to let a reader stop labelling diversity
numbers as lower bounds.

## 2. The measurement, and the finding survives it

`run_axis_audit.py` Section 2b, 11 checks, 0 failed:

| | |
|---|---|
| **all 9 prefix-diversity-1 cells CONFIRMED exactly 1** | the 10-06 finding survives becoming a measurement |
| **7 of 27 cells UNDERSTATED by the prefix** | largest gap `cp_rx_error.frame` **7 → 19** |
| **5 of 27 still BOUNDED** | with refused counts printed |

The first row was **not guaranteed**, and the second is why. The prefix
measurement was not merely conservative in principle — it was wrong about a
quarter of the cells in practice. It just happened not to be wrong about the
nine cells the finding rested on. Had it been, 10-06's central result would
have evaporated on contact with an exact measurement, and the only way to
know which of those two worlds we were in was to build the thing.

**Nothing about the suite changed today. Only the measurement did.** The
diversity-1 cells are still diversity-1, and are now *known* to be — which
makes constrained-random stimulus from a UVM sequence a *better-posed* item
than it was yesterday rather than a closed one.

## 3. S-f: five checks that are all blind to the same thing

S-a through S-e are **all computed from `self.signatures`**. That is not a
stylistic observation; it means all five are structurally blind to one fault:
a cell whose `sig_overflow` stops incrementing prints `EXACT` while
truncating. The precise failure the mechanism exists to prevent, and nothing
was watching for it.

**S-f** compares the stored accounting against an independent witness:

```
popcount(sig_mask[cell])  <=  len(signatures[cell]) + sig_overflow[cell]
```

`sig_mask` is 64 bits per cell with one bit set per `crc32` residue of every
distinct signature ever seen, stored or refused. `popcount` is a **one-sided**
lower bound on the true distinct count — hash collisions can only lose bits,
never invent them — so S-f can only fire on a real accounting error. It is
computed on a code path that never reads `self.signatures`, which is the whole
point: *the control sits where the failure enters* (2026-09-30), not beside it.

`crc32` and not `hash()`: Python's `hash()` of a `str` is salted per process,
so a check built on it would not be reproducible between runs, and **a check
whose verdict depends on the process is not a check.**

## 4. The mutation harness said the mechanism was broken. It was not.

Seven mutants. First run:

```
  S4   SURVIVED    sig_overflow stops incrementing
  S5   SURVIVED    the SIGNATURE_KEEP bound is removed
```

Read at face value, that says the mechanism fails to detect its two most
important faults — including the one S-f was added for, one commit after
adding it.

It says nothing of the kind. Both rows ran against
`test_uart_uvm_milestone`, in which **27 of 27 cells are EXACT**. The bound
never bites there. `sig_overflow` is never incremented; the cap is never
reached. Breaking a counter that never increments, or removing a cap that is
never approached, changes nothing observable.

**Those mutants did not survive. They never arrived.**

This is 2026-09-29's rule — *a mutation that does not arrive is
indistinguishable from a system that does not respond* — in the one place this
repository had not yet put a control for it. It was one commit away from being
recorded as "the mechanism does not detect S4/S5", which would have been a
false finding about working code, published with a transcript to back it up.

### Two repairs, and the second does not depend on noticing the first

1. **Each row names its testcase.** S4, S5 and S6 run against
   `test_uart_adaptive_observer`, whose longer run leaves 5 of 11 cells
   `BOUNDED`, so both faults are reachable. Control A is re-run for **every
   distinct testcase**, because a baseline taken under a different stimulus is
   not a baseline — comparing S4 against the milestone baseline would be
   comparing two different experiments.
2. **An arrival control.** Every mutant's own `COV_SIGNATURE` block is
   compared against control A's block for the same testcase. Byte-identical
   scores the row **INERT** — neither killed nor survived, exactly as a voided
   injection is. *A row can only be called SURVIVED after it has been shown to
   have done something.*

Second run, with both in place:

```
  S1   KILLED      S-b                       membership test dropped
  S2   KILLED      S-d                       signature keeps a per-sample field
  S3   KILLED      S-a, S-d, S-e, S-f        filed under the wrong cell
  S4   KILLED      S-f                       sig_overflow stops incrementing
  S5   KILLED      S-c                       the bound is removed
  S6   INERT       -                          the crc32 mask stops updating
  B    INERT       -                          CONTROL B, f-string rewrite
```

**S4's killer column is `S-f` and nothing else.** That converts the claim in
§3 from an argument about code paths into a result: the independent mask
detects the fault the other five are blind to, and the other five do not
detect it by accident.

## 5. The two INERT rows, which are the most interesting lines in the table

### Control B is INERT, and that is *stronger* than SURVIVED

Control B's entire claim is that a different implementation produces the
**same output**. `SURVIVED` only says the suite did not complain — a proxy.
`INERT` says the printed signature block is byte-identical to the baseline's,
which is the claim itself. The arrival control was added for S4 and S5 and
sharpened control B for free.

### S6 is INERT, which measures a limitation of S-f

Disabling the `crc32` mask entirely changes nothing anyone can see. With an
empty mask, `popcount` is 0, which is `<=` any accounting, so S-f passes.

**S-f is one-sided.** It detects an accounting that is too small. It cannot
detect its own evidence going missing.

That is a **control with no control** — precisely what 2026-10-07's
`phase4_ral` work built a *positive control* for, in this same repository, one
session ago. Nothing here requires S-f to **fire** on a case where it should.
Recorded as an open item rather than papered over, and it is the reason S6 is
in the table at all: *a mutant whose job is to find out which of two things is
true has to be run even when its outcome is not required.*

## 6. A post-injection control in python, closing a standing item

`AUTOMATION_LOG` 2026-10-07 recorded that this repository's python-injected
mutants are guarded by `assert old in s`, which is **control B's anchor test
and not control B**: it checks the text was there *before*, not that it is
gone *after*. `tools/mutation_controls.sh` grew `mc_controls_text` for exactly
this and nothing called it.

`controls_text()` in the new harness is its python equivalent. It runs on all
seven rows, and voids any row whose verdict is not usable. Its failure path is
**exercised rather than argued for**: `--selftest` injects a
`B_SELF_MATCHING` row (a replacement that still contains its own anchor) and a
`NOT_INJECTED` row (a replacement identical to the anchor), and requires the
harness to void both. It does, and that transcript is committed.

## 7. A ZeroDivisionError is not a verdict

`run_axis_audit.py` crashed when pointed at a transcript that was still being
written: it reported "0 of 0" cells and then died inside R4's percentage,
producing a traceback and **no `RESULT` line**, which the runner could only
classify as "0 RESULT lines, expected 1" — a message about the audit's output
format rather than about the artefact.

New check **R0**: an offline audit of a committed artefact has to be able to
say *"this artefact does not contain what I audit"* as a **failed check**,
because that is a fact about the artefact and is exactly what a reviewer needs
told. Its failure path was exercised against a witness-free log before being
committed: `rc=1`, `FAILURES: R0`, no traceback.

The crash was self-inflicted — the runner's own output had been redirected
into the file the audit reads — but the fix is not about that mistake. Any
truncated, rotated or partially-copied transcript reaches this audit the same
way, and before today every one of them produced a traceback instead of a
verdict.

## 8. Methodological note

09-17: a suite can pass against broken RTL. 09-18: and print PASS over its own
errors. 09-19/09-20: the subsystem reporting the verdict is not the subsystem
doing the checking. 09-26: a reachability pre-pass answers "did my attempts
reach it", not "is it reachable". 09-30: a control has to sit where the failure
enters. 10-01: and an arrival control that cannot fail is not a control. 10-05:
a metric can be printed beside the thing it does not measure. 10-06: and the
detector that measures a metric can misattribute what it measured. 10-07: an
injection guard is a measurement, so "did the file change" is the wrong
question.

**10-08: AND A MUTANT THAT REPORTS SURVIVED UNDER A STIMULUS THAT CANNOT REACH
IT IS A FALSE FINDING ABOUT WORKING CODE — WHICH IS STRICTLY WORSE THAN A
MISSED DEFECT, BECAUSE IT ARRIVES WITH A TRANSCRIPT.**

The checkable rule: **a mutant may be scored SURVIVED only after it has been
shown to have changed something the mechanism prints.** Mechanised here as the
arrival control, which needs no judgement: compare the mutant's own output
block against the baseline's for the same testcase, and report INERT on
byte-identity. The repair that *does* need judgement — choosing a testcase in
which the fault is reachable — then becomes a visible gap rather than a silent
pass.

And the corollary, from §5: **the same control makes a correct-rewrite control
stronger.** Control B wants byte-identical output; before today it could only
observe that nothing complained.

### A cross-repository note

The graphene repository's session today built a mutation harness for its
potential census with five mutants, and included an **inert control** for
exactly this class: the same injection placed inside a comment, required *not*
to flip the verdict. That harness was written before this one ran, and it
guards against a mutant that does not arrive *textually*. What this session
found is the other half of the class — a mutant that arrives textually,
compiles, runs, and is unreachable under the chosen **stimulus**. Both halves
are 2026-09-29, and neither harness had both. The arrival control above is the
candidate to cross back: the graphene mutation harnesses compare verdicts, not
output blocks, so an inert mutant there would still read as a pass.
