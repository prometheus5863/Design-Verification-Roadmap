# Study notes: verification planning + directed/random/coverage-driven trade-offs (Phase 3)

*Date: 2026-09-05. First session after a five-day gap (no sessions
2026-09-01 through 2026-09-04); picks up directly from the 2026-08-31
session's "not yet covered" list. Covers `progress.md`'s two remaining
Phase 3 conceptual items -- "Verification planning (features -> checks ->
coverage -> tests)" and "Directed vs. constrained-random vs.
coverage-driven trade-offs" -- together, since the planning process
(Section 1) is what decides, feature by feature, which of the three
stimulus strategies discussed in Section 2 actually gets used. WebSearch
and WebFetch were both available and used this session.*

## 1. Verification planning: features -> checks -> coverage -> tests

A verification plan (vplan/testplan) is a specification-derived document
that answers "what needs to be verified and how do we know when it's
done" *before* any testbench code is written -- as the OpenHW Group's
CORE-V project (a real, in-production open-source RISC-V verification
effort) puts it in their own planning guide, "a complete, high quality
verification plan can be the most valuable item produced by a
verification project" (Source 1 below). It deliberately separates *what*
gets tested from *how* -- the testbench architecture (Phase 2's
layered-component concepts, already covered) is a separate concern from
the plan.

### 1.1 The features -> checks -> coverage -> tests chain

Synthesizing ChipVerify's seven-section vplan template (Source 2) and
CORE-V's spreadsheet-column template (Source 1), the chain has four
distinct links, each one narrower/more concrete than the last:

1. **Features** -- derived directly from the DUT's specification, one row
   per distinct behavior (not one row per signal). CORE-V's own worked
   example: for an RV32I `ADDI` instruction, the feature list isn't
   "test ADDI" but decomposes into *register* variations (does it work
   from/to every one of x0-x31, including the x0-is-hardwired-zero
   special case), *operand bit-pattern* variations (immediate/operand
   corner values: 0, all-ones, sign-extension boundary), and *side-effect*
   checks (no unintended register writes, correct PC advance) --
   explicitly choosing not to enumerate all ~10^13 possible operand
   combinations, but "the minimal amount of coverage to have confidence
   that a feature is sufficiently tested." This is the single most
   reusable idea from this source for this repo's own future DUTs: a
   feature list is a designed *sample* of the input space justified by
   engineering judgment, not an attempt at exhaustion.
2. **Checks** -- for each feature, how a violation would actually be
   *caught*: a scoreboard/reference-model comparison, an assertion
   (Section 6.5's Phase 5 topic later), a signature/self-check, or a
   directed pass/fail assertion in a simple testbench. ChipVerify's
   template calls this "Pass/Fail Criteria" and is explicit that a
   feature without a stated check is not actually verified no matter how
   much stimulus reaches it -- coverage without checking just proves the
   DUT was *exercised*, not that it behaved correctly.
3. **Coverage** -- the *evidence* that every feature's stimulus space was
   actually reached, closing the loop back to item 1. ChipVerify
   distinguishes code coverage (structural: line/branch/toggle/FSM-state,
   typically targeted at 90-95%) from functional coverage (semantic:
   covergroups/coverpoints tied directly to the feature list, e.g. a
   `parity_mode` coverpoint with even/odd/none/mid-stream-switch bins for
   a UART's parity feature -- ChipVerify's own worked example, directly
   reusable for this session's chosen DUT, Section 3 below).
4. **Tests** -- the actual test list/regression: which stimulus strategy
   (directed, constrained-random, or a coverage-driven random loop --
   Section 2) generates which feature's coverage, with a priority/order
   (CORE-V's template includes a priority column so a partial regression
   still exercises the most important features first).

### 1.2 Sign-off and process

Both sources agree a vplan needs an explicit **sign-off criterion** stated
up front, not decided informally at the end: ChipVerify's template lists
coverage thresholds + zero known critical bugs + a clean regression as the
three standard gates. CORE-V's guide additionally treats the vplan itself
as a *living, reviewed* artifact for an open-source project -- proposed via
a pull request, reviewed with designers and verification leads before
testbench work starts, and its status tracked alongside the code -- which
is the same "plan before code, and let the plan's status track the
project's real status" discipline this repo's own `progress.md`/
`AUTOMATION_LOG.md` pairing already follows, just formalized into the
project's actual (future) DUT verification artifact rather than this
repo's own meta-tracking.

## 2. Directed vs. constrained-random vs. coverage-driven: trade-offs

Three stimulus-generation strategies exist along a spectrum from
fully-authored to fully-automatic, and Section 1's plan is exactly what
decides, feature-by-feature, which one to spend effort on:

- **Directed testing**: an engineer writes exact stimulus for a specific,
  anticipated scenario. Strength: precise, easy to debug, and the only
  practical option for a scenario that must hit an *exact* condition (a
  specific corner value, a specific sequence of back-to-back protocol
  events) that random stimulus would rarely stumble into on its own.
  Weakness (Source 3, "The Art of Verification"): "extremely
  time-consuming and difficult to maintain for complex designs" and
  fundamentally bounded by what the verification engineer *thought to
  anticipate" -- it cannot find a bug the author didn't already imagine,
  which is exactly the class of bug most likely to escape to silicon.
- **Constrained-random verification (CRV)**: stimulus fields are
  randomized within legal constraints (Phase 2's `rand`/`constraint`
  material, already covered -- on this repo's pinned Icarus 10.3 build,
  demonstrated via hand-written `$urandom_range`-based equivalents rather
  than native `randomize()`, per 2026-08-26 notes) and checked against a
  reference model/scoreboard rather than a pre-computed expected value,
  so the same checking code works no matter what random stimulus arrived.
  Strength: reaches many more combinations per engineer-hour than hand
  authoring, and *can* find scenarios nobody anticipated. Weakness: random
  stimulus alone gives no guarantee of reaching every feature -- without
  coverage feedback it can waste huge simulation time on already-well-exercised
  corners while rare-but-important ones stay unhit by chance.
- **Coverage-driven verification (CDV)**: CRV plus a functional-coverage
  model in the loop, so unreached bins can be identified and either (a)
  fixed by tightening/re-weighting the randomization's constraints/`dist`
  weights toward the gap, or (b) closed with a small number of targeted
  directed tests. This repo's own Phase 2 milestone
  (`examples/phase2_milestone/alu_combined_tb.sv`, 2026-08-29) already
  *is* a (manually-implemented, Icarus-10.3-workaround) instance of this
  loop: a coverage-driven stopping criterion that kept generating
  randomized transactions until all op/corner/cross bins closed, rather
  than running a fixed random trial count and hoping.

**The practical consensus across the sources reviewed this session (2 and
3)**: none of these three replaces the others; the vplan's job (Section 1)
is to assign the right one per feature. CRV/CDV should carry the bulk of
the state-space exploration (fast coverage progress, corner cases nobody
explicitly enumerated), while directed tests remain the right tool for (a)
a small number of known-critical exact scenarios that matter enough to
guarantee deterministically, and (b) mopping up whatever specific coverage
holes remain after a CDV regression plateaus -- "The Art of Verification"
frames this explicitly as the recommended hybrid: run constrained-random
first, then write a small number of directed tests targeted at the
specific gaps coverage reports left over, rather than choosing one
methodology exclusively.

## 3. Applying this to the Phase 3 milestone

`progress.md`'s Phase 3 milestone calls for "a written verification plan
(markdown, in this repo) for a moderately complex DUT (e.g. a simple
APB/AHB-lite peripheral or a UART)... used directly as the spec for the
Phase 4 UVM testbench." This session's plan, written using the
features/checks/coverage/tests structure and the strategy-assignment
reasoning from Sections 1-2 above, is for a **UART controller with a
register interface, TX/RX FIFOs, and an interrupt output** --
`verification_plans/uart_controller_verification_plan.md`. This DUT choice
is deliberate, not arbitrary: it is *also* the concrete example already
named in this repo's own README for the Phase 6 capstone project ("a UART
or SPI controller wrapped with a register interface"), so today's Phase 3
plan is written to double as an early draft of that eventual capstone's
spec, rather than a one-off exercise DUT that would need re-planning later.
ChipVerify's own worked example (Source 2) happens to use a UART parity
feature to illustrate the features->coverage mapping, which is used
directly (with attribution) as one of the plan's coverage-model examples.

## 4. Sources

1. OpenHW Group, CORE-V-VERIF, "How to Write a Verification Plan
   (Testplan)" / VerificationPlanning101.md,
   [github.com/openhwgroup/core-v-verif](https://github.com/openhwgroup/core-v-verif/blob/master/docs/VerifPlans/VerificationPlanning101.md)
   -- a real, in-production open-source RISC-V verification project's own
   planning guide and spreadsheet template; used for the features/checks/
   coverage/tests column structure and the RV32I ADDI worked example.
2. ChipVerify, "Verification Plan,"
   [chipverify.com/verification/verification-plan](https://chipverify.com/verification/verification-plan)
   -- seven-section vplan template (design overview, features, methodology,
   test plan, coverage plan, sign-off criteria, resource/schedule) and the
   UART parity coverage-mapping example reused in Section 3.
3. "The Art of Verification," "Directed Testing Vs Constraint Random
   Verification,"
   [theartofverification.com/directed-testing-vs-constraint-random-verification](https://theartofverification.com/directed-testing-vs-constraint-random-verification/)
   -- strengths/weaknesses of each approach and the recommended
   CRV-then-directed-gap-filling hybrid summarized in Section 2.

**Search access notes:** all three fetches succeeded this session; no
access failures to record (unlike several prior sessions in both repos'
logs).

## 5. Not yet covered / candidates for future sessions

- The verification plan itself (Section 3) is the Phase 3 milestone
  deliverable, written as a separate file this session -- see
  `verification_plans/uart_controller_verification_plan.md` and today's
  `AUTOMATION_LOG.md` entry for what it covers and what it deliberately
  leaves as a Phase 4 (UVM) concern.
- Before Phase 4 (UVM) coding begins, the toolchain question flagged
  repeatedly since 2026-08-25 (this repo's pinned Icarus 10.3 build cannot
  host a real UVM environment: no virtual-interface class members, no
  `mailbox`, no class-handle containers) still needs to be resolved with a
  concrete choice of simulator/toolchain -- not discovered mid-Phase-4.
