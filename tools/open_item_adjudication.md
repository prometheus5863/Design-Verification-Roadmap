# Adjudication of the top-ranked open items

Companion to `tools/open_item_staleness_audit.py`. The audit produces a
**ranking**; this file is the **judgement**, written by the session that read
it. One `##` heading per item, verdict `STALE` or `OPEN`, with a reason.

The audit requires that every item at or above its reporting cut appear here,
and that nothing here fails to match a top-ranked item. It does **not** derive
a verdict from a score: a containment score is a text-similarity measurement
and no cut on it would be defensible as "stale". Keeping the judgement on disk
with reasons makes it auditable; deriving it from a threshold would make it
reproducible and arbitrary.

**Last adjudicated: 2026-10-03**, twice. The first pass ranked against the
10-02 list (0.606, 0.600, 0.500, 0.400, 0.308, 0.286); appending this
session's own list changed the head, so it was re-adjudicated against the
10-03 list (0.375, 0.333, 0.286, 0.235, 0.222, 0.222). **That is a property of
the design, not an accident: the adjudication is pinned to a ranking, and the
ranking moves when the list does, so a new list and a refreshed adjudication
belong in the same commit.** Note also that the whole ranking fell — the
highest score dropped from 0.606 to 0.375 once the stale item left the list,
which is the clearest single piece of evidence that it was the outlier.

---

## STALE: The UVM environment against the UART RTL — the register-bus agent, the serial agent, the reference-model scoreboard and the coverage collector

**Score 0.606, rank 1. Verdict: STALE, and it has been for twelve entries.**

The item describes four components as the clear next step. All four exist and
have existed since 2026-09-18:

| component the item names | where it actually is |
|---|---|
| register-bus agent | `UartRegAgent`, `examples/phase4_uvm_milestone/uart_uvm_tb.py` |
| serial agent (incl. standalone RX bit-driver) | `UartSerialAgent` + `UartSerialDriver`, same file |
| reference-model scoreboard | `UartScoreboard`, same file |
| coverage collector | `UartCoverage`, same file |

`progress.md` records the milestone as **COMPLETE 2026-09-18** with "69
scoreboard checks, 0 errors, 100.0% functional bin coverage" and a 5-of-5
mutation result, and then states **PHASE 4 IS COMPLETE (2026-09-19)** in bold.
The item's own text — "Phase 4's stated milestone is this, and the sessions
have been doing Phase 6 measurement instead" — is therefore false in both
halves: the milestone was met, and the Phase 6 work was the correct next thing,
not a substitution for it.

What makes this worth recording rather than just deleting: the item was carried
forward **verbatim for twelve consecutive entries, with the session count
incremented each time**. The incrementing count is what made it look
increasingly urgent, and the count was the only part of it that was being
maintained. It held a position at or near the top of the list throughout, and
the sessions it reproached had done the work before the count started.

The sub-items the entry parked behind it (RAL basics, virtual sequencers,
active/passive agents, constrained-random UART stimulus) are likewise complete
per `progress.md` — RAL on 09-19 with 8/8 and 5-of-5 mutants, virtual
sequencers and active/passive on 09-18 — **except** constrained-random
stimulus, which `progress.md` itself carries forward honestly under "What
Phase 4 did NOT cover": stimulus is still directed everywhere while the vplan
assigns most features to constrained-random. That one survives as its own item
and is not retired with its parent.

**But it is not retired to nothing, and this is the part that nearly went
wrong.** `progress.md` line 468 carries, under the Phase 6 **capstone**, an
unchecked box reading simply `- [ ] Full UVM environment built`. Deleting the
log item outright would have retired the only text pointing at that box — the
exact "repair built and then not connected" failure the graphene repository's
10-02 session named. So:

REPLACED-BY: the Phase 6 capstone's unchecked `Full UVM environment built`
box (`progress.md` line 468), restated in the log with what actually
distinguishes it from the Phase 4 milestone.

**And the ambiguity between those two is the root cause of the twelve-session
error.** `- [ ] Full UVM environment built` says nothing about how it differs
from a Phase 4 milestone that is COMPLETE and contains a full UVM environment.
A session reading only the log could reasonably believe the environment did
not exist, because the capstone box says a full environment is not built and
does not say in what sense. The two are genuinely different — the capstone
also requires SVA protocol checkers, constrained-random rather than directed
stimulus, and a written methodology summary, all of which are separately
unchecked — but nothing said so. The replacement wording in today's log entry
states the difference, so the next session inherits a distinction rather than
a contradiction.

## OPEN: Control B for the FOUR OLDER mutation harnesses

**Score 0.600, rank 2. Verdict: OPEN.** The high score is a text artefact:
"mutation", "mutant", "harness" and "control" are dense in several completed
checkboxes about mutation testing. `progress.md` line 936 carries this as an
**unchecked** `- [ ]` box in its own words, and the only harness with control B
is `examples/phase4_uvm_milestone/mutation_test_reachable_cross.py` (2026-10-02)
plus the budget-law re-derivation. The four older harnesses still have control
A only. A real instance of the ranker scoring high on a genuinely open item,
which is exactly why the verdict is not derived from the score.

## OPEN: A mutant on `budget_law_exhaustive.py`'s own stimulus generator

**Score 0.500, rank 3. Verdict: OPEN.** `mutation_report_budget_law_2026-09-29.txt`
mutates the law under test, not the generator that produces its stimulus.
Nothing in the tree targets the generator. Created 09-29, still not done.

## OPEN: The F7 cross cannot be closed without drawing `0x40`, and `0x40` is BORDERLINE

**Score 0.400, rank 4. Verdict: OPEN, and it is the repository's top item.**
Created 10-02 and recorded in the vplan at v10. It is the first conflict
between two sign-off criteria rather than between a criterion and a number,
and all three ways out change what a coverage number means. Untouched.

## OPEN: Wire `PayloadAdmissibilityCoverage` into the live UVM coverage collector

**Score 0.308, rank 5. Verdict: OPEN.** `UartCoverage` in
`uart_uvm_tb.py` is the live collector and does not reference
`PayloadAdmissibilityCoverage`. Created 09-30. After 10-02 it must also adopt
the 4-bin transition goal and the 16-cell cross, so the item has grown rather
than aged.

## OPEN: Audit every "what this does not change" paragraph in the vplan

**Score 0.286, rank 6. Verdict: OPEN.** Created 10-02 as the general form of
that session's finding. v10 contains such a paragraph of its own and it has had
no more checking than v9's did.

## STALE: The four unchecked capstone boxes as newly disambiguated — constrained-random stimulus inside the UVM environment, SVA checkers bound into it, the coverage wiring, the methodology summary

**Rank 2 on the 10-03 list, score 0.333. Verdict: OPEN.** Created today as the
named successor to the retired item. It scores high for the obvious reason —
it quotes the completed Phase 4 milestone in order to say what it is *not* —
which is a second, benign false-positive mode for the ranker, distinct from
rank 2 of the first pass: that one shared vocabulary by accident, this one
shares it on purpose. Both are reasons the verdict is not derived from the
score.

The substantive sub-item is **(a)**: `examples/phase6_crv_uart/` implements
constrained-random, coverage-driven UART stimulus in plain Verilog-2001 and has
never been driven from a UVM sequence. That is an integration task against
existing, measured machinery rather than new study, which makes it the most
actionable thing on the list.

> **[2026-10-17: verdict changed OPEN → STALE, and the text above is kept
> intact.** Sub-item **(a)** — the one this entry called "the most actionable
> thing on the list" — was closed, and 2026-10-14's adjudication narrowed the
> remaining three to a lettered remainder, which the list now carries under a
> different name. So most of this heading's text is no longer work: two of
> the four boxes are gone and the entry out-states its item by enough that
> the audit's 0.75 containment test cannot match it even with the wording
> fold added today. **The correct action in 2026-10-14 was this verdict, with
> a successor named, and it was not taken** — which is how an entry whose
> work is live came to be reported as having lost its item. Recorded here
> rather than backdated.
> **REPLACED-BY:** THE CAPSTONE BOX'S LETTERED REMAINDER — (b) the SVA
> protocol checkers bound into the existing UVM environment, and (c)
> `PayloadAdmissibilityCoverage` wired into the live `UartCoverage`
> collector. Nothing from this entry is retired except sub-item (a), which is
> done, and the methodology summary, which 2026-10-14 judged written.**]**

## OPEN: Apply the three-valued outcome axis to phase6_crv_uart's crosses, and audit every remaining runner for the "greps a file it did not just write" pattern

**Rank 6 on the 10-03 list, score 0.222. Verdict: OPEN.** A compound bullet
carrying several items from 09-23 through 09-27. It enters the adjudicated head
only because the list shortened by one, and nothing in it has been touched.
Flagged for a future session to **split**: a compound bullet cannot be
adjudicated as a unit, and S3 scores it as one, so its individual members are
invisible to the ranking.

---

# Adjudication pass of 2026-10-17

**Last adjudicated before today: 2026-10-14.** Three list revisions have
landed since (10-15, 10-16 and the chunked-runner session), and the audit
reported the consequence as **6 MISSING and 6 ORPHAN** — 10 passed, 2 failed —
which was the only thing keeping `tools/run_all_harnesses.sh` red. The design
note at the top of this file says a new list and a refreshed adjudication
belong in the same commit; three lists landed without one, and this pass is
the catch-up.

**One thing this pass found that the audit cannot say:** the six ORPHANs are
not one phenomenon. Four are entries whose item **left the list with no
verdict at all** — exactly the loss this file exists to prevent — and two are
entries whose item is **still on the list under different wording**, where
`ORPHAN` is reported with the words "has lost its item from the list
entirely" and that sentence is false. The audit's own matcher is a 0.75
token-containment test, so `Wire PayloadAdmissibilityCoverage into the live
UVM coverage collector` does not match the live item `(c)
PayloadAdmissibilityCoverage wired into the live UartCoverage collector`:
`wire`/`wired` and `uvm coverage collector`/`UartCoverage collector`. **A
verdict resolved on spelling** — the same class of defect the graphene
repository found in two docstrings on the same day, and the same class as its
own 2026-10-01 dead-name loophole. The four dropped items are **restored to
the list** in today's AUTOMATION_LOG rather than having their entries deleted,
because deleting the entry to make the check green is the one move this file
is built to refuse. The matcher is split in the same session: see
`tools/open_item_staleness_audit.py`, S4.

---

## STALE: A MUTANT FOR THE NEW tx_empty PREDICTION

**Score 0.750, rank 1. Verdict: OPEN.** The highest score on the list and it
is a text artefact of the usual kind — "mutant", "prediction", "tx" and
"empty" are all dense in completed scoreboard checkboxes. Checked rather than
inferred: **no mutation report in the repository mentions `tx_empty`**
(`grep -rl tx_empty examples/*/mutation_report*` is empty across all twelve
reports), while `tx_empty` is predicted by the scoreboard and read by the RTL
and the CRV bench. So the prediction is live and unmutated. Created 10-12,
carried five sessions, and it is the cheapest remaining mutant to write:
the prediction exists, the harness exists, and the only missing piece is the
injection.

> **Re-adjudicated 2026-10-25: STALE.** The mutant was built on 2026-10-21 —
> `examples/phase6_crv_uart/run_tx_empty_mutation_tests.sh`, rows `T1`–`T4`,
> with `T4` included deliberately as the attributability control rather than as
> a fourth test of the prediction. The item left the list that day and this
> entry was not updated, which made it one of the three orphaned `OPEN`
> entries failing `S4` behind a transcript last regenerated 2026-10-17.
> **NO-SUCCESSOR:** the prediction now has its mutants; the separate
> `rx_avail` SYNC_ONLY row is a different mutant, carried on its own.

---

## OPEN: A CHECK THAT CATCHES M1, M4 AND M5 ON THEIR OWN TERMS

**Score 0.667, rank 2. Verdict: OPEN.** Created 10-09. The three mutants are
still only caught collectively: `phase6_rx_pin_driver`'s 10-14 report shows
them detected by **aggregate check counts** (`M1 59  M4 14  M5 1`) and by a
**single** distinguishing check each in the signature row (`M1 1  M4 2  M5
1`), which is the detection-by-side-effect the item was created to replace.
M5 in particular rests on exactly one check. Nothing in the tree asserts the
specific property each of the three breaks. Untouched for eight sessions, and
it is one of the two items (with the `tx_empty` mutant) whose cost is bounded
and known.

## OPEN: MORE SEEDS ON THE CLOSURE DISTRIBUTION

**Score 0.333, rank 3. Verdict: OPEN, and narrowed.** Partially answered
already and the entry should say so: `witness_soundness.py` ran a **40-seed**
sweep for the W1-vs-W3 comparison (means 473 vs 499, ranges overlapping),
which is what established that v10's 703→663 "speedup" was seed noise. What
remains is the **distribution** rather than the comparison — the committed
closure figures (703, 663, 387–663 across five seeds) are still single-seed
or five-seed numbers quoted in the vplan as if characteristic. The item is
resumable by construction, and its remaining value is a stated expectation
with a spread, not another point.

## OPEN: A REPOSITORY-WIDE DETAIL-STRING CENSUS

**Score 0.333, rank 4. Verdict: OPEN.** Created 10-10. Checked: there is no
file in `tools/` that does this (`ls tools/ | grep -i detail` is empty), and
the two worked instances remain the hand-derived C1/C3 strings in
`witness_soundness.py`. It is the general form of a finding that has now
recurred in several suites — a detail string that describes a check's intent
rather than its measurement — and it is the kind of item that only a census
closes, since any individual instance looks fine.

## OPEN: MAKE run_all_harnesses.sh ITSELF REACHABLE

**Score 0.310, rank 5. Verdict: OPEN, and deliberately not actionable
unilaterally.** Created 10-16 as the recursion of that session's own lesson:
the caller now reads every runner's exit code and **nothing reads the
caller's**. There is no CI here, so the only honest forms are a line in the
session prompt or a `tools/` entry point a run cannot skip — both of which
change how the automation is driven rather than what the repository contains.
That is a reviewer's decision, recorded as such, the same treatment F7's
W0/W1/W3/W4 choice has had for three sessions. **Today is itself evidence for
it:** this adjudication exists because an audit went red and a session
happened to run the caller; nothing required that.

## STALE: RAL BASICS, ACTIVE/PASSIVE AGENTS, vplan v2 — the surviving part of the standing Phase 4 list

**Score 0.333, rank 6. Verdict: STALE, all three components.** This is the
last fragment of the Phase 4 standing list whose parent entry was retired as
STALE on 2026-10-03, and it has the same defect for the same reason: it names
work that was finished before the item started being carried.

| component | state |
|---|---|
| RAL basics | **DONE 2026-09-19.** `examples/phase4_ral/uart_ral_tb.py`, a six-register `uvm_reg_block`, 8/8 with 5-of-5 mutants. The audit's own S3 output names this completed checkbox as the top match for this item. |
| active/passive agents | **DONE 2026-09-18**, per `progress.md`, in the same milestone as the serial and register agents. |
| vplan v2 | **Superseded thirteen times over.** The plan is at **v13 (2026-10-05)**; v2 is from 09-17. A "v2 revision" is not outstanding work, it is a version that happened. |

**NO-SUCCESSOR:** all three
components are complete, so there is no residue to inherit. This is not the
case where a STALE verdict hides live work — contrast the four restored items
below, where it would have been. The one piece of Phase 4 content that *is*
still open is already carried separately and correctly as **THE CAPSTONE
BOX'S LETTERED REMAINDER** (b) and (c), which this entry does not cover and
must not be read as retiring.

---

# The six ORPHAN entries, dispositioned

## Restored to the list, not retired: Control B for the FOUR OLDER mutation harnesses

**Verdict: OPEN, unchanged, and the entry was never the problem.** The item
left the list some time after 10-03 **with no verdict**. Re-checked today:
`tools/mutation_controls.sh` is shared, but control B — a grep for the
INSERTED text, as distinct from control A's grep for the removed text — is
still only exercised by `phase4_uvm_milestone`'s suites and the budget-law
re-derivation. The four older harnesses still have control A only. Restored
to today's list. **Note it is NOT the same item as 2026-10-16's "run every
mutation suite with its toolchain deliberately removed"**, which is about
false SKIPs; this one is about false DETECTEDs from an anchor that cannot
distinguish a mutant that was applied from one that was already there.

## Restored to the list, not retired: A mutant on budget_law_exhaustive.py's own stimulus generator

**Verdict: OPEN, unchanged.** Dropped from the list with no verdict.
`mutation_report_budget_law_2026-09-29.txt` still mutates the law under test
and not the generator that produces its stimulus; nothing in the tree targets
the generator. Created 09-29. Restored.

## Restored to the list, not retired: The F7 cross cannot be closed without drawing 0x40, and 0x40 is BORDERLINE

**Verdict: OPEN, and this is the most serious of the four silent drops.** The
2026-10-03 entry called it "the repository's top item". It then left the list
with no verdict while **three vplan revisions were written about it** — v11
re-measured it and recommended W3 "flagged for sign-off rather than applied",
v12 gave the BORDERLINE case a mechanism and split the soundness axis in two,
v13 found the same pattern independently in a second collector. So the item
was neither done nor abandoned: **it was worked on continuously and dropped
off the list of things being tracked**, which is the worst available
combination because the decision it is waiting for is a reviewer's. F7's goal
remains W0 with two unsound bins. Restored, and it should be read with v11's
W1/W3/W4 options and v12's two-number sign-off refusal.

## Restored to the list, not retired: Audit every "what this does not change" paragraph in the vplan

**Verdict: OPEN, unchanged.** Created 10-02 as the general form of that
session's finding; dropped with no verdict. **v13 contains such a paragraph of
its own** — "What this revision does not change: no coverpoint, no bin, no
goal, no sign-off criterion, and no number in any committed transcript" — and
it has had no more checking than v9's did, which is the sentence the item was
created about. Restored.

## Not an orphan: Wire PayloadAdmissibilityCoverage into the live UVM coverage collector

**Verdict: OPEN, and the item is on the list.** It is carried as **(c)** of
THE CAPSTONE BOX'S LETTERED REMAINDER: "`PayloadAdmissibilityCoverage` wired
into the live `UartCoverage` collector". The audit calls it an ORPHAN because
its 0.75 token-containment test fails on `wire` against `wired` and `uvm
coverage collector` against `UartCoverage collector`. **The entry is correct,
the item is live, and the audit's sentence about it is false.** Reported here
and fixed in the matcher in the same session, per the rule that a verdict must
be gated on the mechanism it reports.

## Not an orphan, and superseded in wording only: The four unchecked capstone boxes as newly disambiguated

**Verdict: OPEN, under its current name.** 2026-10-14's adjudication narrowed
the four boxes to a lettered remainder — (a) constrained-random stimulus
inside the UVM environment was closed, leaving (b) the SVA protocol checkers
bound into the existing UVM environment and (c) the coverage wiring — and the
list item was reworded to **THE CAPSTONE BOX'S LETTERED REMAINDER**
accordingly. Same work, narrower and renamed. A second matcher miss, from a
rewording the adjudication process itself produced, which is the more
troubling of the two: **this file's own correct operation is what made the
check fail.**

---

# Second adjudication pass of 2026-10-17, same session

**Why there are two passes today.** Restoring the four silently-dropped items
to the list **moved the ranking head**, so four items that were previously
below the reporting cut are now above it and unadjudicated. This is precisely
what the design note at the top of this file describes — *"the adjudication is
pinned to a ranking, and the ranking moves when the list does, so a new list
and a refreshed adjudication belong in the same commit"* — and 2026-10-03
needed a second pass for the same reason. **It is a property of the design and
not an accident, and today is the second recorded instance, which makes it a
pattern rather than a one-off:** any session that changes the item list owes
the audit a re-adjudication before the caller can be green.

## OPEN: CLASSIFY EVERY cmp -s AS VERDICT-BEARING OR CONTROL-BEARING

**Heading corrected again 2026-10-28.** It read *"THE ONE REMAINING `cmp -s`
RUNNER — phase6_uvm_crv_uart"*, which named a COUNT this entry's own verdict
says is unverifiable; the list bullet was re-worded to name the work instead,
and the two drifted apart, orphaning this entry. Renamed to match. That is the
third payment on the standing *align the adjudication headings with the list
wording* item, and the second on this entry alone — which is the argument that
the alignment should be mechanical: the heading and the bullet are two copies
of one string and nothing keeps them equal.

**Heading corrected 2026-10-26.** It read `phase6_crv_uart`, which is a
DIFFERENT directory and the one whose runners A, B and D are fully
controlled; the runner this entry is about is `phase6_uvm_crv_uart`. The
mismatch was invisible while the list's wording happened to be similar
enough for the ranker to match the two, and it surfaced the moment the
list bullet was re-worded. That is the standing *align the adjudication
headings with the list wording* item, paid again.

**Verdict: OPEN, and the item's own COUNT is unverified — which is the more
useful finding.** The item says one remains, down from four, plus
`phase6_uvm_crv_uart` whose `cmp -s` 2026-10-16 deliberately did not bundle in.
A plain `grep -rln 'cmp -s' examples/` today returns **ten runner files**,
including `phase6_rx_pin_driver/run_mutation_tests.sh` and
`phase6_bfm_equivalence/run_mutation_tests.sh` — **the two this repository
names as the worked references for having been fixed.**

That does not mean the fixes were not made. `cmp -s` in a *control* (checking
that an injection landed, or that a cosmetic edit did not move a transcript) is
not the same as `cmp -s` *as the verdict*, and the fix was about the latter.
**But nothing in the repository distinguishes the two**, so "one remaining" is
a number no instrument here can reproduce, and it has been carried as if it
were measured. Cheapest route, and it is the same shape as the census work
already done for scoreboard reads: classify every `cmp -s` occurrence as
verdict-bearing or control-bearing, and require each to be one or the other —
the 2026-10-16 rule that *a set with a silent default has no members you can
name*, applied to this count instead of to the runner list.

## OPEN: A MUTANT FOR THE rx_avail SYNC_ONLY ROW

**Verdict: OPEN, and confirmed as the census's weakest row.**
`tools/scoreboard_dut_signal_census_output.txt` carries `SYNC_ONLY
STATUS.rx_avail (st[3])` with its exposure argument in prose — "decide when to
read RX_DATA and no row named it" — and it is one of only **2 SYNC_ONLY rows
of 18** (`OBSERVED_ONLY 1, PREDICTED 13, SYNC_ONLY 2, TRUSTED 2`). A SYNC_ONLY
role is the census's claim that a signal is *read to sequence the bench* and
never *checked*, which is exactly the claim a mutant tests: break the signal
and the bench should hang or mis-sequence rather than report a mismatch. No
mutant targets it. Untouched since creation.

## OPEN: EXTEND THE CENSUS TO THE REMAINING CHECKERS

**Verdict: OPEN, with the boundary quoted from the census itself.** The census
is complete *within* its five files and says so in its own words: "13 reads
extracted across 5 files, 13 covered, 0 omitted … **complete only WITHIN a
censused file. Adding a file can** …". So this item is not a gap in the
instrument but the instrument's stated scope limit, and it is the honest kind
of open item: the file list is the part no check can grow by itself. Worth
pairing with the `cmp -s` item above, since both are "enumerate the population
before trusting a count".

## STALE: A COSMETIC-EDIT POSITIVE CONTROL IN EVERY RUNNER THAT COMPARES TRANSCRIPTS

**Verdict: STALE as of 2026-10-25 — the work is done, and a third of the
item's own premise was false.** Created 10-13, re-worded by the 2026-10-24
entry as *"A COSMETIC-EDIT POSITIVE CONTROL IN THE OTHER THREE RUNNERS"*,
which is the wording change that orphaned this entry and left `S4` red for a
day.

Original reasoning, kept: ten runners compare transcripts; the control that
proves a comparison can *fail* on a change that does not matter exists in only
a few. The 10-13 session's own `W4` was the argument in miniature — a first
draft of `stems()` changed the audit's behaviour in a way its output could not
distinguish from the intended change, and only a control aimed at the
mechanism caught it.

What 2026-10-25 found and did:

| runner | state before | state after |
|---|---|---|
| A `run_mutation_tests.sh` | `G2`, added 2026-10-24 | unchanged; the worked reference |
| B `run_tx_empty_mutation_tests.sh` | none | `G2b`, plus its own compile guard so "not neutral" and "did not build" are distinct findings |
| C `phase1_mutation/run_mutation_tests.py` | **`G0b`, all along** | unchanged |
| D `run_mutation_tests_bimodal.sh` | none | `G2b` |

**The 2026-10-24 item said "B, C and D have no such arm". C had one, and a
stronger one** — `G0b` requires the cosmetic edit to pass the bench, to change
the *raw* transcript (so it would fool a byte-comparison criterion) and *not*
to change the normalised one, where A's `G2` asks only for compile-and-escape.
A session acting on the item as written would have built a weaker duplicate in
a file that already had the better version. `S6` was added to this audit so
that a claim of this shape — an item asserting what is *inside* a file, which
`S1` cannot check — is re-verified against the tree.

**NO-SUCCESSOR:** the four runners the item names now each carry the arm, and
`tools/test_neutrality_controls.py` proves the two new ones are reachable
(8/8: a real behavioural edit, a no-op edit and a non-compiling edit are each
refused, by arm-specific messages, with an unmutated-copy negative control).
The broader "ten runners compare transcripts" ambition is **not** retired by
this entry and is carried separately as the standing sweep over the remaining
runners.

---

## OPEN: GIVE THE FIVE SUITES WITHOUT A CURRENT REPORT ONE

**Verdict: OPEN, and blocked rather than neglected.** Adjudicated 2026-10-25,
having been at or above the reporting cut without an entry since the
2026-10-24 list was written — which is one of the two gaps that left `S4` red
for a day.

The item is real: a suite with a runner and no current committed report is a
suite whose last measured state is unknown, and this repository has twice
found a committed report that outlived the code it described. It is not
actionable in this environment, because all five need `cocotb` or `sby`, and
neither installs under the current egress allowlist. Every session that has
touched it has recorded the same block.

The honest form of the item is therefore *"five suites cannot be reported on
until the toolchain question is settled"*, and the toolchain question is the
real open item behind it. It stays OPEN rather than STALE because nothing has
been done and the need has not lapsed — but it should not rank as if it were
available work, and a future session that ranks it first will find it blocked
within one command.

## OPEN: THE 40 COMMENT-ONLY EDGES, NOW CLASSIFIED BUT NOT READ

**Verdict: OPEN, and it is the cheapest unblocked content item on the list.**
Adjudicated 2026-10-25, the second of the two gaps that left `S4` red.

Created 2026-10-20, when the report-provenance relation classified 40 edges as
comment-only. Classified is not read: the classification says the edit touched
no executable line, and says nothing about whether the comment it changed
still describes the code beneath it. A comment that contradicts its code is
this repository's most-recorded fault — three docstring instances and one
transcript instance to date — and 40 unread edges is the largest untouched
population of candidates for it anywhere in the tree.

Unlike most of the list this needs no toolchain: the edges are already
enumerated in a committed report, and reading them is a matter of judgement
rather than simulation. It stays OPEN and is worth ranking **above** the
blocked items, which is the opposite of how a text-similarity score ranks it.

---

## OPEN: NO MUTANT IN THE CRV SUITE IS CAUGHT BY COVERAGE ALONE

**Verdict: OPEN, and it is unevidenced rather than wrong.** Adjudicated
2026-10-25, having reached the reporting cut without an entry.

The claim under it — *"coverage closure is a pass criterion, not a report
line"* — is the bench's own stated design. What is missing is an instance: no
mutant in the suite is detected by the closure criterion and by nothing else,
so the criterion has never been shown to carry a detection on its own. The
2026-10-22 session looked for such a mutant and did not find one; that is a
negative result about the search, not about the criterion.

It stays OPEN because it is the cheapest way to put the bench's pass-criterion
decision under an instance, and because the alternative — removing closure
from the pass criterion — would change what the bench claims and should not be
done on the strength of an absent example. Needs no toolchain beyond Icarus,
which makes it one of the few unblocked items above the cut.

## OPEN: RUN EVERY MUTATION SUITE WITH ITS TOOLCHAIN DELIBERATELY REMOVED

**Verdict: OPEN, and the family it belongs to grew again today.** Adjudicated
2026-10-25, having reached the reporting cut without an entry. Created
2026-10-16; two suites gate on a missing toolchain, four have never been
tested that way.

The question is what a suite prints when the thing it needs is absent. This
repository has now recorded four ways that goes wrong quietly: a false SKIP is
quiet, a false DETECT is quiet, a false PASS from a counter nobody reads is
quieter, and an injection that was never a program is quietest of all, because
it looks exactly like a success. Today adds a fifth that is adjacent rather
than identical: **a control that cannot fail reports green indefinitely**, and
`tools/test_neutrality_controls.py` exists because two such controls were
written this session.

Unblocked — removing a toolchain needs no toolchain — and it pays off across
every suite at once rather than one.

---

## STALE for the three runnable runners, OPEN and blocked for two: A COSMETIC-EDIT CONTROL IN THE REMAINING TRANSCRIPT-COMPARING RUNNERS

**Verdict: the work is done where it can be done, and the item's premise held
this time.** Created 2026-10-25 as that session's ranked-first item, after the
2026-10-24 wording of its predecessor turned out to be false about one of the
three runners it named.

The item's own instruction was the valuable part: *"CHECK BEFORE PORTING —
today's whole §4 is what happens when that step is skipped, and `S6` is where
each answer should be recorded so the next session does not re-ask."* All five
runners were read on 2026-10-26 before anything was written, and **none
carried a neutral arm**, so unlike the 2026-10-24 item this one was not
asserting a tree state the tree denied.

| runner | controls before | neutral arm? | 2026-10-26 |
|---|---|---|---|
| `phase6_bfm_equivalence` | A/B/C + `cmp -s` | no | **ported** |
| `phase6_baud_error_coverage` | C + `cmp -s` | no | **ported** |
| `phase6_rx_pin_driver` | C + `cmp -s` + M7 structural guard | no | **ported** |
| `phase4_ral` | A/B/C + `MC_SELFTEST=1` | no | recorded, blocked on cocotb |
| `phase6_uvm_crv_uart` | an unmutated `control` ROW | no | recorded, blocked on cocotb |

**The distinction the `phase6_uvm_crv_uart` row turns on is worth stating
once.** An unmutated `control` row is a **baseline**: it asks whether the
bench passes on *good* RTL. A neutrality arm asks whether it passes on RTL
that is *different but cannot behave differently*. The two look alike in a
report and answer opposite questions, and conflating them is how a runner
looks controlled and is not.

**What is shared, and what deliberately is not.** `mc_neutral_copy` in
`tools/mutation_controls.sh` performs the comment-only edit and refuses a
byte-identical copy. It does **not** judge the result: each runner asserts the
criterion its own rows are scored by (`RESULT: PASS` for E and F with their
own plumbing, `errors = 0` for G). That split is the 2026-10-25 rule applied
to the helper itself — the *edit* is identical everywhere, the *verdict* is
not, and a helper that judged would silently hand several runners one
criterion none of them uses.

**NO-SUCCESSOR for the three ported runners.** `S6` now carries seven rows
recording the five answers plus the shared-edit/own-verdict split and the
selftest's coverage, and `tools/test_neutrality_controls.py` proves all five
arms reachable (20/20). **The two blocked runners are carried by the standing
toolchain item**, not by a revival of this one: the real obstacle there is
that cocotb does not install under the current egress allowlist, which is a
single item behind five separate symptoms and should be ranked as one.

**And this entry records a fault in its own session's first draft**, because
it is the same fault the entry above records: `N1` for runner E was planted
with runner B's STATUS-decode edit, which the RX-pin bench cannot see, so the
positive control could not fire and scored green. Second session running in
which a positive control was planted somewhere it could not reach, and the
first in which the file that exists to catch that shape contained it.

## OPEN: CHECK EVERY OTHER SED IN EVERY RUNNER FOR THE M7 ESCAPING FAULT

**Adjudicated 2026-10-28**, on its first appearance at or above the reporting
cut. It entered the top six because the list moved, not because the item
changed — which is the property the header of this file records: the
adjudication is pinned to a ranking, and the ranking moves when the list does.

**Verdict: OPEN, and the item is narrower than its title suggests, which is
the useful part.** The M7 fault was a `sed` program whose replacement text
contained a character `sed` reads as syntax, so the injection did not land the
edit the row claimed while the runner still scored the row. The item asks for
every other `sed` in every runner to be read for the same shape.

Two reasons it has not been done, and only one of them is good:

1. The population is not enumerated. Nobody has counted the `sed` programs in
   the runners, so "every other" names no set — the 2026-10-16 rule that *a
   set with a silent default has no members you can name*, in the same form as
   the `cmp -s` count item now ranked first. **The enumeration is the work**,
   and it is a grep plus a classification, needing no toolchain.
2. It has been treated as a reading task rather than a measurable one. The
   mechanical form is stronger and already has a precedent in this
   repository: the declared-sites guard (`phase6_bfm_equivalence`, converted
   2026-10-15) asks of each injection *did the edit land at the site I
   declared*, which catches the M7 class **without reading any `sed` at all**.
   Converting the remaining runners to that guard would discharge this item as
   a by-product, and is testable by a mutation on the `sed` itself.

The 2026-10-27 addendum's session added two more instances of the shape it
names — `sed` programs embedded in shell-function overrides embedded in Python
string literals, in H's and I's `N1` arms — so the population grows faster
than the reading would.

## OPEN: ALIGN THE ADJUDICATION HEADINGS WITH THE LIST WORDING

**Adjudicated 2026-10-28**, on the day it rose into the top six — and it rose
because this session re-worded the bullet that describes it, which is the item
demonstrating itself.

**Verdict: OPEN, and its character has changed: it is a MECHANISABLE item, not
a discipline one.** That is the adjudication, and the reason to write it down.

It was paid **three times in this one session**, and twice on orphans that
writing the day's own log entry created:

| entry | why it orphaned |
|---|---|
| `THE ONE REMAINING cmp -s RUNNER` | the bullet was re-worded to name the WORK; the heading named the COUNT |
| `GIVE THE FIVE SUITES WITHOUT A CURRENT REPORT ONE` | 10-27 tracked it inside a five-part bullet that today's entry rewrote |
| `Wire PayloadAdmissibilityCoverage into the live UVM coverage collector` | the same five-part bullet |

Each was repaired by making the two strings agree — two bullets re-worded to
their entries' phrasing, one heading renamed to its bullet's. And that is the
whole mechanism: **a bullet and its adjudication heading are two copies of one
string, and nothing in this repository keeps them equal.** A session that
improves a bullet's wording silently breaks a match, and the breakage surfaces
as an *orphan*, which reads like a retired item rather than like a typo.

So the repair is not "be careful when re-wording". It is a check: every `OPEN`
entry's heading must appear, verbatim, as the head of some bullet on the
standing list. That is strictly stronger than the present 0.75 stem-containment
ranker, which is what has been absorbing the drift and, in absorbing it, hiding
it — the `WORDING` category added 2026-10-17 exists precisely because the
ranker was papering over this.

**Why it is not done today.** A verbatim check would fail on the entries that
have *legitimately* diverged — the `STALE` ones, whose items are gone on
purpose and whose headings are the audit trail — so it needs the `OPEN`/`STALE`
split the file already carries, and a declared exemption list for any `OPEN`
entry whose heading is deliberately shorter than its bullet. That is the same
registry-plus-reason shape the sibling graphene repository built three times on
this same date, and it is a session's work rather than an afternoon's.
