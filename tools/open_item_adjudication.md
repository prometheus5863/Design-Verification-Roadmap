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

**Last adjudicated: 2026-10-03.** Ranking at that date: 0.606, 0.600, 0.500,
0.400, 0.308, 0.286 for the six items below.

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

Retired today. The sub-items the entry parked behind it (RAL basics, virtual
sequencers, active/passive agents, constrained-random UART stimulus) are
likewise complete per `progress.md` — RAL on 09-19 with 8/8 and 5-of-5
mutants, virtual sequencers and active/passive on 09-18 — **except**
constrained-random stimulus, which `progress.md` itself carries forward
honestly under "What Phase 4 did NOT cover": stimulus is still directed
everywhere while the vplan assigns most features to constrained-random. That
one survives as its own item and is not retired with its parent.

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
