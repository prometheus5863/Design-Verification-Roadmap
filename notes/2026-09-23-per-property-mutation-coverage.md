# Per-property mutation coverage, and the fifth way a passing property can mean nothing

Phase 5, day 4. 2026-09-23.

## 1. Why this, and why now

2026-09-22 ran a deletion experiment on one property. R4 (reset dominates a
concurrent bus write) turned out to be subsumed by R1: no mutant could
distinguish the suite with R4 from the suite without it. The log made the
generalisation the top open item — *"the 2026-09-20 FIFO invariants (P1–P4)
and the 2026-09-21 CSR properties (C1–C9) have never been asked whether any
of them is subsumed, and today's result says the question has a non-trivial
answer. It is cheap and mechanical."*

Cheap and mechanical turned out to be right about the cost — 252 `sby`
invocations, about twelve minutes — and wrong about the *shape*. Doing it
for one property by hand and doing it for seventeen by script are not the
same exercise, and three things showed up that the single-property version
structurally could not.

## 2. The measurement, and the distinction phase 1 cannot make

For a property `p` and a mutant `m`:

```
baseline(m)   full suite on RTL+m          expect FAIL
drop(p)       suite without p, clean RTL   expect PASS   (guard)
drop(p, m)    suite without p, on RTL+m
```

`drop(p, m) == PASS` while `baseline(m) == FAIL` means `p` is the only thing
that sees `m`: **load-bearing**. If no mutant does that, `p` never changes a
verdict.

And that is where a one-property experiment stops, because "never changes a
verdict" is two completely different situations wearing the same result:

* **SHADOWED** — `p` *can* detect a defect on its own; something else
  detects it too. A real redundancy finding.
* **UNEXERCISED** — `p` detects *nothing* on its own. This is not a fact
  about `p` at all. It is a fact about the **mutant set**: no injected
  defect touches the behaviour `p` describes.

The first invites a conversation about whether the suite is larger than it
needs to be. The second says the measurement is not finished. Reporting them
as one number would recommend deleting a property whose actual problem is
that nobody ever tested it — which is the opposite of the right action.

The discriminator is the solo experiment 09-22 ran by hand for R4: make `p`
the only live property and re-run every mutant. Phase 2 does that for every
candidate, and **"only" has to mean only, including across suites** — which
is where the first surprise came from.

## 3. The matrix

Of **17** properties: **9 load-bearing**, **4 shadowed**, **4 unexercised**.

```
fifo   P1 LOAD-BEARING (M2)   P2 LOAD-BEARING (M4,M5)   P3 unexercised   P4 shadowed
csr    C1 unexercised   C2 (N1)   C3 (N2)   C4 (N3)   C5 (N4)
       C6 unexercised   C7 unexercised   C8 shadowed   C9 (N7)
reset  R1 LOAD-BEARING (K2)   R2 shadowed   R3 LOAD-BEARING (K6)   R4 shadowed
```

**The control.** The harness must independently reproduce the one answer
already known, or its sixteen new answers are worth nothing. Phase 1
reproduces R4 as subsumed; phase 2 reproduces the finer form — R4 detects
K1, K3 and K4 alone and none of them uniquely. Both pass.

## 4. Three findings that are not bookkeeping

### 4.1 Cross-suite subsumption

The CSR job compiles `-DFORMAL -DFORMAL_CSR` and the reset job
`-DFORMAL -DFORMAL_CSR_RESET`. **Both silently carry the 2026-09-20 FIFO
invariants.** So when C8 (RX_DATA pop-on-read, and no pop when empty) comes
back shadowed, what shadows it is not another CSR property: it is P1/P2 from
a different day's suite, catching the same underflow first.

No within-suite experiment can see this, and the 09-22 experiment was
within-suite. The general form is worth carrying to an interview: **a
property's redundancy is a property of the COMPILE, not of the suite it was
written in.** Two suites that are independent on paper share a namespace, a
define set and a solver the moment they are compiled together.

### 4.2 C1 had been advertising its own hole for two days

C1's comment says, verbatim: *"a width mutation is exactly what this
catches."* No width mutation had ever been injected. Phase 2 called C1
unexercised; phase 3 injected N8 (the INT_EN write drops its top bit); N8 is
detected, and **missed** when C1 is deleted. Hole closed, C1 reclassified
load-bearing.

Same shape for P3: unexercised against M1–M5, load-bearing the moment M6
(`tx_full` computed from the empty constant, so full and empty coincide)
exists.

Two of the four unexercised properties were one mutant away from being the
only thing standing between the design and a defect. That is the argument
for the phase-2 split in one sentence.

### 4.3 An escape — and a correction to what this session first claimed

N9 removes the clear of `frame_err` on a STATUS read — exactly the behaviour
C6 exists to state — and **the whole suite passes**.

The first draft of this note called that a **fifth way a passing property can
mean nothing**, on the reading that C6 is well-formed, non-subsumed and still
blind. **That was wrong, and it was wrong in the most avoidable way: the
answer was already in this repo.** 2026-09-21 had established exactly this,
by exactly this method, and asserted it rather than hoping for it — stage 3b
of `run_csr_formal.sh` injects N5 (`if (1'b0 && rd_en && paddr ==
ADDR_STATUS)`), disables the read-to-clear path entirely, and **requires the
mutant to SURVIVE**, with the ~145-clock argument written out beside it. N9
is N5 in a different disguise. The escape is class 1 on the list below —
plain vacuity — not a new class.

The lesson is not about formal verification. It is that **a mechanical sweep
over seventeen properties re-derives things the repo already knows and
presents them all with the same confidence as the things it does not**, and
the reader who can tell the difference is the one who read the earlier
session's script. Which is an argument for the sweep being cheap, not for it
being trusted.

What *is* new is the control, and it is worth keeping. N5 establishes that C6
cannot be broken at this depth. It does not establish that C6 is any good:
a property that is syntactically nonsense would survive N5 identically.
**N10** makes a STATUS read *set* `frame_err` — no RX activity needed, so the
antecedent is reachable in three steps — and C6 and C7 both fail it at step
3. So the pair separates two things N5 alone cannot:

| observation | consistent with |
|---|---|
| N5/N9 survive | C6 unreachable **or** C6 vacuous nonsense |
| N5/N9 survive **and** N10 dies at step 3 | C6 unreachable **only** |

That is the difference between *"we believe C6 is bounded-vacuous"* and
*"C6 is a working property pointed at a door the solver cannot reach"*, and
it costs one extra mutant.

The running list, unchanged in length:

| # | a passing property can mean nothing when… | detected by |
|---|---|---|
| 1 | its antecedent is never satisfiable in the bound | a cover, a survivor mutant (N5), **or a targeted mutant from the other side (N9)** |
| 2 | it is satisfied only by pre-reset state through `$past` | a step-≥2 guard on the cover |
| 3 | it restates the design logic, so both mutate together | writing it from the spec, not the RTL |
| 4 | another property subsumes it | a per-property deletion experiment |

The one methodological addition today makes to class 1 is the third detector:
the cover that would show C6's antecedent reachable sits in the
`FORMAL_CSR_DEEP` job smtbmc cannot finish, so on the cover side the check is
blocked by the same budget that creates the problem. A mutant needs no cover
to be reached — only a defect to be injected — so it gets the answer anyway.
That is worth saying in an interview: **when the budget blocks the check that
would expose a bound problem, mutation testing reaches the same conclusion
from the other direction.**

## 5. The bug the guards caught

G3 — the drop-one variant must still PASS on clean RTL — exists because a
deletion experiment fails silently in an interesting way. It earned its place
on the first run.

The FIFO suite's cover block is **also called C1**
(`// ---- C1: cover, to prove the properties are not vacuous`, inside
`` `ifdef FORMAL ``). A bare banner search for `// ---- C1` found that block
instead of the CSR property, and deleted from there to the CSR C2 banner —
across two `` `endif ``s. The job returned
`ERROR: Found \`endif outside of macro conditional branch`, G3 scored the row
INCONCLUSIVE, and `span()` is now region-aware.

The transferable part is not the fix. It is that **a name collision between
two suites is completely invisible until something addresses properties by
name**, and nothing in a normal flow ever does. Both files were reviewed,
both pass, both are correct; the collision existed for three days and cost
nothing until a script tried to talk about "C1".

## 6. What was NOT done, deliberately

**No property was deleted.** Not P4, not C8, not R2, not R4. Each is
annotated in place with its classification and the reason it is kept:

* P4 — the only property constraining the *rate* of change; P1/P2 do not.
* C8 — shadowed only because this job also compiles `-DFORMAL`; it would
  earn its place in a job built without it.
* R2 — the only protocol-level statement of the reset values; R1's
  unconditional form does not scale past a small register file.
* R4 — as 09-22 argued: it states an intent R1 only implies.

And finding 4.3 is the reason that stance is right rather than merely
cautious. C6 and C7 look, in the raw phase-1 matrix, like the two most
obviously deletable properties in the repo. They are guarding a real defect
that the suite cannot currently reach, and N10 shows they will catch it the
moment it becomes reachable. **A coverage number that would have deleted them
is a coverage number that would have removed the only thing that will catch
N9 the day the bound gets deeper** — and note that the number would have been
computed by today's script, which is an argument for not letting a script
that measures seventeen properties in twelve minutes decide anything on its
own.

## 7. Cost, for the next run

252 `sby` invocations, ~12 minutes on the session VM (2 cores, WASM Yosys +
z3). FIFO jobs ~2 s, CSR ~8 s, reset ~4 s. `run_chunk.sh` records each
verdict as it lands and never re-runs a completed variant, because this
repo's shells are time-limited and background jobs do not survive between
them — the sweep is resumable by construction and needs three or four calls.
