# Auditing the list that chooses the work

**2026-10-03.** Live web search was not used. This session is an
internal-consistency audit of the repository's own planning artefacts, and
nothing below rests on a literature fetch.

---

## 1. The one artefact with no instrument pointed at it

Every automated session in this repository begins the same way: read
`AUTOMATION_LOG.md`, take the most recent **"Not yet covered (candidates for
future runs)"** list, pick an item, do it. That list does not *describe* the
work — it **selects** it.

By now almost everything here is checked by something:

| claim | instrument |
|---|---|
| a committed transcript matches its code | pristine-transcript audit (graphene repo) |
| a coverage bin is reachable | `reachable_cross_under_per_byte_rule.py` |
| a property earns its keep | per-property mutation coverage (09-23) |
| a mutant actually arrived | control A, and since 10-01 control B |
| an observer's window contains the DUT's | `payload_coverage_model.py` |

The list that decides which of those to run had nothing. So today it got an
instrument: `tools/open_item_staleness_audit.py`.

## 2. It was wrong, and in the most expensive way available

Rank 1, containment score 0.606:

> **The UVM environment against the UART RTL** — the register-bus agent, the
> serial agent with its standalone RX bit-driver, the reference-model
> scoreboard and the coverage collector. Open since the 09-17 bring-up
> unblocked it, and **untouched for twelve consecutive sessions** while the
> measurement work ran ahead of it. Worth saying plainly: Phase 4's stated
> milestone is this, and the sessions have been doing Phase 6 measurement
> instead.

Every one of the four named components exists, and has since 2026-09-18:

| the item names | it is actually called | where |
|---|---|---|
| register-bus agent | `UartRegAgent` | `examples/phase4_uvm_milestone/uart_uvm_tb.py` |
| serial agent + standalone RX bit-driver | `UartSerialAgent`, `UartSerialDriver` | same file |
| reference-model scoreboard | `UartScoreboard` | same file |
| coverage collector | `UartCoverage` | same file |

`progress.md` records the milestone **COMPLETE 2026-09-18** — 69 scoreboard
checks, 0 errors, 100.0 % functional bin coverage, 5 of 5 injected RTL defects
killed — and then says **PHASE 4 IS COMPLETE (2026-09-19)** in bold. Both
halves of the item are false: the milestone was met, and the Phase 6
measurement work was the *correct* next thing, not a substitution for it.

**Why this is worse than a false transcript.** 10-02's finding (in the
graphene repository) was a transcript that agreed byte-for-byte with its code
and was false. That misreports a **result**. A false open-items list
misdirects **labour** — and this one did, for twelve entries, from a position
at or near the top of the list.

**And the mechanism is specific and ugly.** The item was carried forward
*verbatim* for twelve entries with only the session count incremented. The one
part being actively maintained was the part that made it look increasingly
urgent. Twelve rounds of "untouched for N consecutive sessions" is a reproach
the sessions had already earned their way out of.

## 3. Why the fix is a ranking plus a committed judgement, not a threshold

`S3` computes, for each open item, the fraction of its distinctive tokens that
some `- [x]` block of `progress.md` also contains. It emits **no verdict**.

This repository has been bitten by magic numbers twice — 09-24's greedy
steering policy and 10-02's mis-specified `NUMERIC_RTOL` control — and a
containment score is worse than either, because it is a text-similarity
measurement with no physical meaning at all. No cut on it is defensible as
"stale".

**Rank 2 settles the argument.** *"Control B for the FOUR OLDER mutation
harnesses"* scores **0.600** — within 0.006 of the genuinely stale item — and
is wide open: `progress.md` carries it as an unchecked box in its own words,
and only `mutation_test_reachable_cross.py` has control B. It scores high
because "mutation", "mutant", "harness" and "control" are dense in several
*completed* checkboxes about mutation testing. **Any threshold that retired
rank 1 would have retired rank 2 with it.**

So the score's only job is to put candidates in front of someone.
`tools/open_item_adjudication.md` holds the judgement, with reasons, and S4's
exact check is that the adjudication covers every item at or above the
reporting cut and contains no orphan entries. The judgement is auditable
because it is on disk; a threshold would have made it reproducible and
arbitrary.

Verdicts today: **1 STALE, 5 OPEN.**

## 4. The audit nearly committed its own target fault

The first pass of the adjudication said simply "retired today". That was
wrong, and the reason is on line 468 of `progress.md`, under the Phase 6
capstone:

```
      - [ ] Full UVM environment built
```

Five words, unchecked. The log item being retired was **the only prose
anywhere pointing at that box.** Deleting it outright would have removed the
work's last mention while reporting a cleanup — "a repair built and then not
connected", one level up, *inside the instrument*. S4 now carries a structural
check: every `STALE` verdict must contain `REPLACED-BY:` or `NO-SUCCESSOR:` in
its body. **An audit of the list that chooses the work must not be able to
quietly delete work.**

## 5. And that box is the root cause, not a casualty of it

`- [ ] Full UVM environment built` says nothing about how it differs from a
Phase 4 milestone that is marked COMPLETE and *does* contain a full UVM
environment. A session reading the log could reasonably conclude the
environment did not exist, because the capstone box says a full environment is
not built and never says in what sense.

So **what looked like a contradiction between two artefacts was really one
underspecified checkbox**, and twelve entries of incrementing session count
grew on top of the silence. The two *are* different, and `progress.md` now
says how: the capstone box is a **roll-up** of four separately-unchecked
items — (a) constrained-random rather than directed stimulus *inside* the UVM
environment, (b) the SVA protocol checkers *bound into* it rather than
standing alone, (c) `PayloadAdmissibilityCoverage` wired into the live
`UartCoverage`, (d) the written methodology summary. It should therefore be
checked **last**, and it was never the actionable item it appeared to be.

## 6. Controls, and the one exact check

A detector that cannot fail certifies nothing. The ranker gets a synthetic
`progress.md` and two synthetic open items with known answers:

```
  C1  components all named in a COMPLETED checkbox -> ranks high   0.818
  C2  an unrelated item -> ranks low                               0.143
  C3  and C1's item ranks above C2's                               0.818 > 0.143
  M1  MUTATION TEST: delete the completed checkbox C1's item
      contradicts, and the same item must collapse        0.818 -> 0.000
  E1  EXACT: an item that is verbatim a completed block scores
      exactly 1.0 (containment of a set in itself)                 1.0
```

`M1` is the one that matters. Without it, `C1` could be passing merely because
the scorer returns a high number for everything — the 09-29/09-30 rule that a
check must be *shown* to fail, applied to a text scorer rather than to a
simulation. 12/12 pass.

---

**Methodological note.** The series so far has been about instruments and the
claims they check: a check that cannot fail (09-28), a mutation that does not
arrive (09-29), a control in the wrong place (09-30), a reference whose name
drifts (10-01), an agreement between two artefacts that is silent about the
world (10-02). **Today the subject is not an instrument or a claim but the
QUEUE** — and a stale queue entry is strictly more expensive than a stale
result, because a wrong result is wrong once while a wrong queue is wrong
every session until someone checks it, and nothing was checking it.

The sharper half is §5. The failure presented as a contradiction between two
artefacts, and the first adjudication treated it that way. It was an
**underspecified** artefact: a five-word checkbox that could be read as
agreeing or disagreeing with a completed milestone depending on what the
reader supplied. **A text too vague to be contradicted is also too vague to be
audited**, and it had sat in the capstone since the file was written. The
twelve-session error was not caused by anyone writing something false; it was
caused by nobody being able to tell.
