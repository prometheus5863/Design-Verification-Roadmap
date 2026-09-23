# Per-property mutation coverage

Phase 5, day 4 (2026-09-23). Answers the question 2026-09-22 opened and
could only answer for one property: **which properties in this repo's formal
suites are actually pulling their weight?**

Run it with:

```bash
source tools/setup_formal.sh        # do NOT pipe it -- see 2026-09-18
examples/phase5_property_coverage/run_property_coverage.sh
```

Recorded output: `property_coverage_run_output_2026-09-23.txt`
(252 `sby` invocations; about 12 minutes on the session VM, 2 cores).

## What it measures

Mutation testing, as this repo has used it since 2026-09-17, scores a suite:
inject a defect, require the suite to fail. That says nothing about which
property did the failing. Attributing detection to **individual** properties
costs one variant per (property, mutant) pair and answers a question code
coverage cannot: *if I deleted this property, would any verdict change?*

Three phases, each answering what the previous one could not.

| phase | experiment | distinguishes |
|---|---|---|
| 1 | delete one property, re-run every mutant | does it ever change a verdict? |
| 2 | keep one property as the *only* live one | **shadowed** vs **unexercised** |
| 3 | inject the defects the unexercised ones were written for | hole closed, shadowed after all, or an **escape** |

Phase 2 is the one that matters, and it is why phase 1 alone is not enough.
"Deleting it changes nothing" is compatible with two opposite situations:

* **SHADOWED** — the property *can* catch a defect on its own, but something
  else catches it too. A real redundancy finding.
* **UNEXERCISED** — the property catches *nothing* on its own. That is not a
  statement about the property at all; it is a statement about the **mutant
  set**. The fix is more mutants, not fewer properties.

A report that collapses these two into "redundant" would recommend deleting
a property whose real problem is that nobody ever tested it.

## Results, 2026-09-23

Of **17** properties across the three suites:

* **9 load-bearing** — P1, P2 (FIFO); C2, C3, C4, C5, C9 (CSR); R1, R3 (reset)
* **4 shadowed** — P4, C8, R2, R4
* **4 unexercised** — P3, C1, C6, C7 → two holes closed in phase 3, one escape

Three findings worth more than the bookkeeping:

1. **Cross-suite subsumption.** The CSR job compiles `-DFORMAL -DFORMAL_CSR`
   and the reset job `-DFORMAL -DFORMAL_CSR_RESET`, so **both silently carry
   the 2026-09-20 FIFO invariants**. C8 (RX_DATA pop-on-read) detects N6 on
   its own and never uniquely, because P1/P2 catch the same underflow. A
   within-suite experiment cannot see this; the 2026-09-22 R4 experiment was
   within-suite.

2. **C1's hole was the one its own comment predicted.** C1 says *"a width
   mutation is exactly what this catches"* — and no width mutation had ever
   been injected. N8 (INT_EN write drops its top bit) is detected, and
   **missed** with C1 deleted. Same story for P3 and M6. Both holes closed.

3. **An escape that was already known, and a control that adds to it.** N9
   removes the clear of `frame_err` on a STATUS read — precisely what C6
   describes — and **the whole suite passes**. This session first wrote that
   up as a new failure class; it is not. 2026-09-21 had already established
   it, by the same method: stage 3b of `run_csr_formal.sh` injects N5,
   disables the read-to-clear path entirely and **requires the mutant to
   survive**, with the ~145-clocks-against-depth-20 argument beside it. N9 is
   N5 in a different disguise, and the correction is recorded rather than
   quietly dropped.

   The **control is** new and is worth keeping. N5 shows C6 cannot be broken
   at this depth; it does not show C6 is any good, since syntactic nonsense
   would survive N5 identically. **N10** makes a STATUS read *set*
   `frame_err` — reachable in three steps — and C6 and C7 both fail it at
   step 3. The pair separates *"unreachable"* from *"unreachable or
   nonsense"*, which one survivor mutant cannot.

   The transferable part: the cover that would expose this from the cover
   side sits in the `FORMAL_CSR_DEEP` job smtbmc cannot finish, so **the
   check is blocked by the same budget that creates the problem**. A mutant
   needs no cover to be reached, so it gets the answer anyway.

## Guards

Nothing is scored unless it survives three guards, because a deletion
experiment fails silently in an interesting way.

* **G1** baseline clean must PASS.
* **G2** every baseline mutant must FAIL — an undetected mutant says nothing
  about any property.
* **G3** the drop-one variant must still PASS on clean RTL. If deleting the
  block broke the build, the property is **INCONCLUSIVE**, never "redundant".

G3 earned its place on the first run. The FIFO suite's cover block is *also*
called `C1` (`// ---- C1: cover, to prove the properties are not vacuous`,
inside `` `ifdef FORMAL ``), so a bare banner search for `// ---- C1` found
the FIFO block and deleted across two `` `endif ``s. The job came back
`ERROR: Found \`endif outside of macro conditional branch` and G3 turned it
into INCONCLUSIVE rather than a wrong answer. `span()` now searches inside
each property family's own `` `ifdef `` region. **A name collision between two
suites is invisible until something addresses properties by name.**

## Control

The harness must independently reproduce the one answer already known.

* Phase 1: R4 subsumed — 2026-09-22's hand-built result. **Reproduced.**
* Phase 2: R4 *shadowed*, detecting K1/K3/K4 alone but never uniquely — the
  finer form. **Reproduced.**

A harness that disagreed with the known answer would not be believed about
the sixteen answers that are new.

## Scope

"Subsumed" and "unexercised" are relative to **this mutant set** and to each
job's **BMC depth**. They are evidence that a property earns nothing *here*,
not a proof of redundancy. **No property is deleted on the strength of this
measurement** — the same stance 2026-09-22 took with R4, and finding 3 above
is the reason it is the right one: the two most suspicious-looking properties
in the whole matrix, C6 and C7, turn out to be guarding a real defect the
suite cannot reach.

## Files

| file | what it is |
|---|---|
| `build_variants.py` | generates every variant; holds the mutant definitions and the region-aware `span()` |
| `run_chunk.sh` | resumable runner — records verdicts as they land, never re-runs a completed variant |
| `report.py` | phase 1 matrix and the three guards |
| `report2.py` | phase 2, shadowed vs unexercised |
| `report3.py` | phase 3, gap-closing mutants and the N10 control |
| `run_property_coverage.sh` | driver for all three phases |
| `property_coverage_run_output_2026-09-23.txt` | the recorded run |
