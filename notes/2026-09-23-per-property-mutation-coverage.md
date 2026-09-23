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

### 4.3 An escape, and a fifth way a passing property can mean nothing

N9 removes the clear of `frame_err` on a STATUS read — exactly the behaviour
C6 exists to state — and **the whole suite passes**.

Two explanations, and they call for opposite responses: C6 is broken, or the
defect is out of reach. The control settles it. N10 makes a STATUS read
*set* `frame_err` instead, which needs no RX activity at all; C6 and C7 both
fail it at step 3. So the properties are live, well-formed and evaluable.
Setting `frame_err` through the real RX path needs ~145 clocks against a BMC
depth of 20 — **the same solver-budget boundary day 1 hit from the datapath
side, day 2 from the register side and day 3 from the reset side, now met
from a fourth.**

The running list:

| # | a passing property can mean nothing when… | detected by |
|---|---|---|
| 1 | its antecedent is never satisfiable | a cover |
| 2 | it is satisfied only by pre-reset state through `$past` | a step-≥2 guard on the cover |
| 3 | it restates the design logic, so both mutate together | writing it from the spec, not the RTL |
| 4 | another property subsumes it | a per-property deletion experiment |
| 5 | **its defect's precondition lies beyond the bound** | **nothing here** |

Class 5 is the uncomfortable one. C6 is non-vacuous by its own cover,
non-subsumed, live, correctly written — and blind. The cover that would have
exposed it, `cover(f_csr_rd && paddr == ADDR_STATUS && $past(frame_err))`,
is sitting in the `FORMAL_CSR_DEEP` job that smtbmc cannot finish, which
means **the check that detects class 5 is blocked by the same budget that
creates it.** Mutation testing found it anyway, from the other side: the
mutant needs no cover to be reached, only a defect to be injected.

Interview framing, since this is the sort of question that gets asked as
"how do you know your formal testbench is any good?": *vacuity says the
property is evaluated; subsumption says it changes a verdict; neither says
the defect it guards is reachable inside the bound. Only mutation testing
distinguishes a property that is watching from a property that is watching a
door nobody can reach.*

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
that the suite cannot currently reach. **A coverage number that would have
deleted them is a coverage number that would have removed the only thing
that will catch N9 the day the bound gets deeper.**

## 7. Cost, for the next run

252 `sby` invocations, ~12 minutes on the session VM (2 cores, WASM Yosys +
z3). FIFO jobs ~2 s, CSR ~8 s, reset ~4 s. `run_chunk.sh` records each
verdict as it lands and never re-runs a completed variant, because this
repo's shells are time-limited and background jobs do not survive between
them — the sweep is resumable by construction and needs three or four calls.
