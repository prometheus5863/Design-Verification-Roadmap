# Progress Checklist

Status legend: `[ ]` not started, `[~]` in progress, `[x]` done.

Last updated: 2026-09-07

## Phase 1 — Digital Logic & HDL Fundamentals
- [x] Combinational logic review (Boolean algebra, muxes, encoders, ALUs)
- [x] Sequential logic review (latches vs. flip-flops, FSMs, timing basics)
- [x] Verilog-2001 fundamentals (modules, always blocks, blocking vs.
      non-blocking assignment)
- [x] Synthesizable coding style + simple self-checking testbenches
- [x] Milestone: synchronous FIFO or FSM design + directed testbench
      (Icarus Verilog + GTKWave)
- [x] **Milestone bench mutation-tested** (2026-10-13,
      `examples/phase1_mutation/`, 5 mutants / 5 detected / 5-of-5 verdicts as
      predicted, 3 controls). The 2026-10-12 census's first-ranked unrun row:
      `full` asserting one entry early, the shape that escaped two UART benches
      this week. DETECTED, 5 errors at 134 checks. `empty` one-early is also
      detected but **by timeout** -- the drain loop gates its own pop on the
      DUT's flag, so the bench never terminates. The bench has the trusted-read
      pattern verbatim (`was_full = full` gating `ref_model.push_back`) and
      survives it only because `check_flags` predicts the same signal on every
      operation that reads it.

## Phase 2 — SystemVerilog for Verification
- [x] SV data types, interfaces/modports
- [x] OOP testbench components (transactions, generators, drivers,
      monitors, scoreboards)
- [x] Randomization (`rand`/`randc`, constraints, `randomize()`, `dist`)
      -- concepts covered; native `randomize()`/`constraint`/`inside`/`dist`
      confirmed UNAVAILABLE on this build's Icarus Verilog 10.3 (see
      notes/2026-08-26-*.md); demonstrated via hand-written
      `$urandom_range`-based equivalents instead (manual weighted-`dist`
      opcode picker, manual `randc`-like corner-value queue)
- [x] Functional coverage (`covergroup`/`coverpoint`/`cross`)
      -- concepts covered; native `covergroup` confirmed UNAVAILABLE on
      this build's Icarus Verilog 10.3 (parser does not recognize the
      keyword at all -- see
      notes/2026-08-26-functional-coverage-covergroup-gap.md);
      demonstrated via a hand-written bin-counter + cross model with an
      at_least-N closure target and a coverage-driven stimulus-stopping
      loop instead
- [x] Basic SVA (`assert property`, immediate vs. concurrent)
      -- concepts covered (sequences, properties, |->/|=>, disable iff,
      assert/assume/cover); native immediate assertions AND concurrent
      `assert property` both confirmed UNAVAILABLE on this build's Icarus
      Verilog 10.3 (see notes/2026-08-28-*.md) -- a total gap, not a
      partial one, matching the randomize()/covergroup pattern; demonstrated
      via a dedicated assertion-style checker (independent reference model
      + `if/$error` idiom) for the existing ALU DUT instead, including a
      deliberate expected-fail case proving the checker works
      (examples/phase2/alu_sva_checker.sv)
- [x] Milestone: constrained-random SV testbench w/ scoreboard + coverage
      for a small DUT -- integrates the manual-workaround randomization,
      functional-coverage, and assertion-style-checker examples above
      into one combined testbench (`examples/phase2_milestone/alu_combined_tb.sv`)
      reusing `alu_dut` unmodified; runs a scoreboard AND an
      independently-formulated assertion-style checker on every
      transaction (deliberately two different reference-model
      formulations, not one checked twice). Compiled/run with the pinned
      Icarus Verilog 10.3: 252 scoreboard checks/0 errors, 253
      assertion-checker checks (252 real + 1 deliberate fail, which
      correctly failed)/252 passed, all coverage (op/a_corner/cross)
      closed at 100% after 252 transactions. See
      notes/2026-08-29-phase2-milestone-combined-testbench.md.

**Phase 2 (SystemVerilog for Verification) is now fully complete.**

## Phase 3 — Verification Methodology Fundamentals
- [x] Layered testbench architecture concepts -- transaction/sequencer-
      generator/driver/monitor/agent/scoreboard/environment/test roles
      and why each exists (reuse, separation of stimulus from checking);
      see notes/2026-08-31-layered-testbench-architecture-and-tlm-
      basics.md, Sections 1-2. Section 4 synthesizes this repo's own
      Phase 2 tooling-gap findings (no mailbox, no virtual-interface
      class member, no class-handle in/ref args or containers) into a
      unified explanation of why driver/monitor could only be
      demonstrated as procedural code, not real class objects, on the
      pinned Icarus Verilog 10.3 build -- and why Phase 4's real UVM
      milestone will need a different simulator
- [x] TLM basics -- port/export/imp roles, analysis-port broadcast
      semantics (`write()`), and why decoupled channels (not direct
      references between layer objects) are what make the layers above
      independently reusable; see notes/2026-08-31-*.md, Section 3.
      Connects directly to the already-documented `mailbox`-unavailable
      finding from 2026-08-25 as a concrete instance of "this build
      lacks a TLM channel type," not a separate issue
- [x] Verification planning (features -> checks -> coverage -> tests)
      -- the features/checks/coverage/tests chain, sign-off criteria, and
      why a vplan is written spec-first before testbench code; grounded
      against a real open-source project's own planning guide (OpenHW
      Group CORE-V-VERIF) and ChipVerify's vplan template; see
      notes/2026-09-05-verification-planning-and-stimulus-strategy-
      tradeoffs.md, Section 1
- [x] Directed vs. constrained-random vs. coverage-driven trade-offs
      (**quantified 2026-09-24**: the trade-off was studied in Phase 2 and
      is now a measurement -- 7.3x on the mean, 10.7x on the worst seed,
      2.9x on the best, spread 6.1x -> 1.7x. See
      `examples/phase6_crv_uart/closure_sweep_2026-09-24.txt`)
      -- strengths/weaknesses of each and the recommended CRV-then-
      directed-gap-filling hybrid; connected back to this repo's own
      Phase 2 milestone (`alu_combined_tb.sv`) as an already-built,
      hand-implemented instance of the coverage-driven loop; see
      notes/2026-09-05-*.md, Section 2
- [x] Milestone: written verification plan for a chosen DUT --
      `verification_plans/uart_controller_verification_plan.md`: a full
      9-feature (F1-F9) verification plan for a UART controller with
      register interface, TX/RX FIFOs, and an interrupt output (the same
      DUT already named in this repo's Phase 6 capstone description),
      with per-feature checks, functional-coverage coverpoints/crosses,
      an explicit per-feature directed/random/coverage-driven strategy
      assignment, a 14-test test list, and stated sign-off criteria. No
      RTL or testbench code written yet -- this is deliberately a
      spec-first planning document, to become the Phase 4 UVM
      testbench's spec per the README's stated milestone

**Phase 3 (Verification Methodology Fundamentals) is now fully complete.**

## Phase 4 — UVM

**Toolchain resolved 2026-09-06** -- every Phase 2/3 session since
2026-08-25 flagged that this repo's pinned Icarus Verilog build cannot
compile SystemVerilog classes at all, making a *native* SV-UVM
environment impossible here. Resolved by adopting
[uvm-python](https://github.com/tpoikela/uvm-python) (a Python/cocotb
port of UVM 1.2 that runs on Icarus) instead of a different HDL
simulator or a commercial one this environment doesn't have a license
for. See notes/2026-09-06-uvm-python-toolchain-resolution.md for the
research/decision writeup (including two real installation/version
gotchas: `python-constraint` needs `--use-pep517`, and uvm-python 0.4.0
requires `cocotb<2.0`, not the latest cocotb 2.x).

- [x] UVM class hierarchy, phases, factory pattern -- real (not
      hand-rolled) `UVMComponent`/`UVMTest`/`UVMEnv`/`UVMAgent` hierarchy
      with `build_phase`/`connect_phase`/`run_phase` and
      objection-based termination, factory-registered via
      `uvm_component_utils`/`uvm_object_utils`, running against the
      Phase 2 `alu_dut` on the pinned Icarus build via uvm-python; see
      `examples/phase4_uvm_python/alu_uvm_tb.py` and its sim output log
      (`driven=40 sampled=40 checked=40 errors=0`, `TESTS=1 PASS=1`)
- [x] TLM ports/exports/analysis ports, sequences/sequencers -- a real
      `UVMSequence`/`UVMSequencer`/`UVMDriver` pull-mode handshake and a
      real `UVMAnalysisPort`/`uvm_analysis_imp_decl` broadcast from
      monitor to scoreboard are both demonstrated (the actual TLM
      channel type `notes/2026-08-31-*.md` Section 3 could only describe
      conceptually). **Virtual sequencer and concurrent sequences added
      2026-09-18**: `UartVirtualSequencer` holds handles to the register
      and serial sequencers, and `UartFullDuplexVSeq` (reached via
      `get_sequencer()`, not a pointer handed in by the test) starts
      register-side TX and serial-side RX stimulus *simultaneously* with
      `cocotb.start_soon`, so the DUT transmits and receives at the same
      time -- full duplex, which back-to-back sequences cannot produce.
      Three analysis imps (`_reg`/`_rx`/`_tx`) feed one scoreboard. See
      `examples/phase4_uvm_milestone/uart_uvm_tb.py`
- [x] Drivers, monitors, active/passive agents -- real `UVMDriver`/
      `UVMMonitor` classes demonstrated (see above). **Active/passive
      exercised 2026-09-18**: one `UartSerialAgent` class instantiated
      ACTIVE on the `rx` input (sequencer + driver + monitor) and PASSIVE
      on the `tx` output (monitor only -- neither child built). Not a
      cosmetic flag: `tx` is a DUT output, so an agent there physically
      cannot be active, and a driver on it would be a contention bug.
      `connect_phase` carries a runtime assertion that the passive
      instance built no driver and no sequencer
- [x] UVM environment, virtual sequencers, scoreboards via analysis ports
      -- all three done as of 2026-09-18 (`UartEnv`, `UartVirtualSequencer`,
      `UartScoreboard` on three analysis imps with a real reference model:
      it predicts tx frames from TX_DATA writes, predicts RX_DATA reads
      from frames observed on rx, and models the STATUS error bits as
      sticky/read-to-clear)
- [x] Configuration (`uvm_config_db`, factory overrides) -- plain
      `UVMConfigDb.set`/`get` demonstrated (passing the cocotb DUT handle
      into the environment, 2026-09-06); factory overrides demonstrated
      2026-09-07 via both API entry points -- a global type override
      (`examples/phase4_uvm_python/alu_uvm_factory_type_override_tb.py`)
      and a path-specific instance override
      (`alu_uvm_factory_inst_override_tb.py`) -- both substituting a
      drop-in `AluScoreboardOpHistogram` for `AluScoreboard` with no
      changes to `AluEnv`/`AluAgent` source, and both verified (not just
      logged) via a runtime-type assertion in `connect_phase`. Required
      a prerequisite fix to `AluEnv.build_phase`/`AluAgent.build_phase`
      (child creation routed through `<Class>.type_id.create()` rather
      than direct constructor calls, otherwise overrides register but
      are silently never consulted) -- see
      notes/2026-09-07-factory-overrides-and-config-db.md, Section 2
- [x] **RAL basics -- DONE 2026-09-19, and Phase 4 is now COMPLETE.**
      `examples/phase4_ral/uart_ral_tb.py`: a six-register `uvm_reg_block`
      for `rtl/uart_controller.v`, an 18-line `uvm_reg_adapter`, and a
      `uvm_reg_predictor` fed from the bus **monitor** with
      `auto_predict` deliberately OFF (explicit prediction), sitting on
      the 2026-09-18 APB-lite agent, which is imported and reused
      unchanged. **8/8 checks pass**, including the two built-in generic
      sequences `UVMRegHWResetSeq` and `UVMRegBitBashSeq` -- neither
      written for this UART, and between them they kill three of five
      mutants. Mutation tested: **5 injected defects, 5 killed, 0
      survivors**, one mutant per targeted check.
      Two registers are excluded for stated reasons rather than papered
      over: **RX_DATA**'s read pops the RX FIFO, a side effect no
      `uvm_reg` access policy can express; **STATUS** mixes four volatile
      live bits with three read-to-clear error bits, and since UVM does
      not *compare* volatile fields, a `hw_reset` sweep over it silently
      checks nothing -- so its reset value is checked by hand, which
      mutant M4 confirms is the only thing that catches a tx_full /
      tx_empty swap. See
      `notes/2026-09-19-ral-register-model-and-the-harness-that-had-the-bug.md`
- [x] **DUT for the Phase 4 milestone exists (2026-09-17)** -- the
      milestone had been gated since 2026-09-05 on a DUT that did not
      exist: the UART verification plan was written spec-first and its
      own Section 7 flagged the RTL as a Phase 4 dependency, and the
      Phase 1-3 8-bit ALU is too small to carry the plan's 9 features
      (no registers, no FIFOs, no serial framing, no interrupt).
      `rtl/uart_controller.v` (394 lines, Verilog-2001, compiles and
      simulates on the pinned Icarus 10.3 build) now implements the
      plan's Section 1 spec in full: APB-lite register interface, all
      six registers, 8-entry TX/RX FIFOs, 16x-oversample baud
      generator, TX/RX framing FSMs with parity and 1-2 stop bits,
      loopback mode and a masked level interrupt. Brought up against a
      directed self-checking regression
      (`examples/phase4_rtl_bringup/uart_controller_tb.v`, 60 checks
      T1-T12 mapped to plan features F1-F9): **60 passed, 0 failed**.
      Deliberately NOT a UVM testbench -- bringing up a new DUT inside
      a new UVM environment makes every failure ambiguous between the
      two; the UVM environment is now built against a known-good DUT.
      See notes/2026-09-17-uart-rtl-bringup-and-status-polling-hazard.md
- [x] **Milestone: full UVM testbench w/ 2-3 sequences/tests + coverage
      target -- COMPLETE 2026-09-18.**
      `examples/phase4_uvm_milestone/uart_uvm_tb.py` (~1030 lines) against
      the unmodified `rtl/uart_controller.v`: register (APB-lite) agent,
      active serial RX agent with a standalone bit-driver, passive serial
      TX agent, reference-model scoreboard, functional-coverage collector,
      virtual sequencer, five sequences (`UartConfigSeq`, `UartTxSeq`,
      `UartRxFrameSeq`, `UartDrainSeq`, `UartFullDuplexVSeq`) run under
      three frame formats. Result: **69 scoreboard checks, 0 errors,
      100.0% functional bin coverage** over 5 coverpoints and 1 cross;
      coverage below target is itself a UVM_ERROR. Mutation tested:
      **5 injected RTL defects, 5 killed, 0 survivors** -- but only after
      the first pass exposed two real testbench defects (a regression that
      reported PASS while the scoreboard printed UVM_ERRORs, and a sticky
      error bit whose *clearing* was never checked). See
      `notes/2026-09-18-uvm-environment-and-the-green-regression-that-wasnt.md`
      and `examples/phase4_uvm_milestone/mutation_test_report_2026-09-18.txt`

**PHASE 4 IS COMPLETE (2026-09-19).** Every topic and the milestone are
done: class hierarchy and phases, factory and `uvm_config_db`, TLM and
analysis ports, sequences/sequencers/drivers/monitors, active vs passive
agents, virtual sequencers and concurrent sequences, environment and
scoreboard, functional coverage, and now RAL. The DUT
(`rtl/uart_controller.v`) and the vplan it is built against
(`verification_plans/uart_controller_verification_plan.md`, now at v2)
both exist and are exercised by three independent benches: the directed
bring-up regression, the UVM milestone environment, and the register
model.

**What Phase 4 did NOT cover, carried forward honestly:** stimulus is
still directed everywhere, while the vplan's Section 3 assigns most
features to constrained-random; code coverage (Section 5 targets 95%) has
never been measured, because Icarus has no native support; and F7's
baud-tolerance number is unmeasured. These are Phase 6 / capstone items
now, not Phase 4 gaps to reopen.

> **Updated 2026-09-25.** The third is now closed too. F7's baud
> tolerance is measured in `examples/phase6_rx_pin_driver/` by a driven-pin
> receiver on an independent timebase -- 8N1 +6.25% / -4.50%, 8E1 +5.60% /
> -4.05% -- and the plan's F7 strategy is revised to match (v3). **Only
> code coverage remains unmeasured of the three**, and that one is a
> toolchain limit rather than a gap in the work: Icarus has no native
> support.

> **Updated 2026-09-27.** The Phase 4 UVM environment now measures F7 itself.
> `UartSerialDriver` no longer counts DUT clock cycles: it programs
> `bfm/uart_rx_pin_bfm.v`, the repository's single pin driver, whose only
> timebase is `bit_ps`. Measured at `BAUD_DIV=0`: 8N1 **+6.75% / -4.00%**,
> both inside the derived +/-1.00% band around the 09-25 numbers measured at
> `BAUD_DIV=1`. **The window WIDTH is 10.75% at both divisors, identical to
> the basis point, with the whole window displaced +0.50%** -- which is why
> vplan v5 signs F7 off on width plus a stated centre offset rather than on
> two limits. Recorded honestly alongside it: until today every frame this
> environment had ever driven had its bit edges exactly on DUT clock edges,
> so the receiver's oversampling had never been exercised off-grid here --
> under a 69-check regression at 100% functional coverage.

> **Updated 2026-09-24.** The first of those three is closed:
> `examples/phase6_crv_uart/` drives constrained-random, coverage-driven
> stimulus with a closure pass criterion, over the register interface and
> the loopback datapath. The third is **not** closed and now has a reason
> rather than a backlog entry -- mutation M5 showed that loopback shares
> one baud generator between TX and RX, so F7 is unmeasurable in this
> bench shape at any level of effort. The second is unchanged.

**The single most valuable thing Phase 4 produced is not a testbench.**
Three sessions in a row found the same defect class -- *the subsystem
reporting the verdict was not the subsystem doing the checking*:
2026-09-17, checks that never ran; 2026-09-18, cocotb's PASS line
ignoring UVM_ERRORs; 2026-09-19, `make`'s exit code ignoring cocotb's
FAIL, in the mutation harness whose whole purpose is to catch exactly
that. Mutation testing found all three and nothing else did. Carry both
into Phase 5: a formal tool's exit code, a regression runner parsing a
log, and a coverage merge that silently drops a database are the same
shape.

## Phase 5 — Assertions & Formal Verification
- [~] SVA in depth (sequences, properties, local variables, assume/assert/cover)
      -- **studied 2026-09-20**
      (`notes/2026-09-20-sva-and-formal-bounded-vs-unbounded.md` Section 2),
      but the concurrent-assertion **sequence layer is not runnable on
      either tool here**: Icarus 10.3 has essentially no concurrent-assertion
      support and Yosys 0.69's `-formal` accepts assert/assume/cover/$past
      without `##`, `[*]`, `|->` or local variables. Properties are
      therefore written in the SymbiYosys immediate-assertion-on-a-clock-edge
      style. Not closed: `##`/`[*]`/`|->`/local variables are studied and
      unexercised
- [x] Formal verification concepts (model checking, bounded vs. unbounded)
      -- **done 2026-09-20**, and not only on paper: the UART FIFO
      invariants are proved by **temporal induction**, an unbounded result,
      and the difference from the bounded BMC result was forced into the
      open by mutant M1 (below)
- [x] Practical formal use cases (connectivity, X-prop, CSR, deadlock)
      -- surveyed 2026-09-20 with a verdict on each for this DUT (notes
      Section 5), and **CSR closed 2026-09-21**: nine properties on the
      six-register APB map in `rtl/uart_controller.v` under
      `` `ifdef FORMAL_CSR ``, with `examples/phase5_csr_formal/` running
      bmc (depth 20) / prove / cover plus seven mutants and two guard
      stages -- **15 passed, 0 failed**. The seven reusable CSR
      obligations (reset value, read-back, reserved bits, RO/WO
      protection, decode isolation, access side effects, clear semantics)
      are written up in `notes/2026-09-21-csr-formal-properties-and-bounded-vacuity.md`
      Section 2, including the O(n) contrapositive form of decode
      isolation. **Two caveats recorded rather than glossed:** the
      read-to-clear and error-rise properties are **vacuously true at
      depth 20** -- the antecedent needs a complete UART frame, ~145
      clocks -- and that vacuity is *asserted* by a mutant (N5) required
      to survive, not merely suspected; and **reset-value properties are
      still unchecked**, because the `f_past_valid` idiom disables
      everything during reset -- **this second caveat is CLOSED 2026-09-22**
      (see the next item). X-prop and liveness remain out of scope for
      this toolchain, connectivity is not applicable to a single peripheral
- [x] **Reset-value properties -- done 2026-09-22.** The seventh CSR
      obligation, and the one 2026-09-21 left owed. R1 (28 architectural
      registers), R2 (the read port, including `STATUS = 8'h02` rather than
      `8'h00`, because `tx_empty` is a live decode of `tx_cnt == 0`), R3
      (`irq` low out of reset) and R4 (reset dominates a concurrent bus
      write), under `` `ifdef FORMAL_CSR_RESET `` with the **mirror-image
      guard** `(f_past_valid && !$past(rst_n))` -- the exact inverse of the
      guard every other property in the repo uses, which is *why* the gap
      existed: a correct convention, uniformly applied, with a blind spot.
      `examples/phase5_csr_formal/run_reset_formal.sh`, five stages,
      **15 passed, 0 failed**: the Phase 4 bench still 60/60, bmc depth 12,
      both covers reached at steps 3 and 4 (step >= 2 guard held), six
      mutants detected, one (M7, corrupting the un-reset RX FIFO storage)
      **required to survive** so that R2's deliberate omission of
      `ADDR_RX_DATA` is proved rather than described, and the 2026-09-20
      and 2026-09-21 suites re-run unchanged.
      **Caveats recorded, not glossed:** (a) a reset asserted mid-frame is
      NOT covered -- reaching a frame is ~145 clocks, the same solver-budget
      boundary days 1 and 2 hit from the other two directions; (b) **R4 is
      measurably REDUNDANT.** Stage 5 rebuilds the RTL with R4 removed and
      with only R4 kept and runs the defect R4 was written for against both;
      both detect it, so R1 subsumes R4 and R4 changes no verdict anywhere.
      That is a **fourth** way a passing property can be worth less than it
      looks, distinct from the three vacuity shapes listed on 2026-09-21 --
      R4's antecedent is satisfiable, its cover is reached, and all three
      vacuity tests are blind to it. R4 is annotated in place, not deleted.
      Write-up: `notes/2026-09-22-reset-value-properties-and-property-subsumption.md`
- [x] **Per-property mutation coverage -- done 2026-09-23.** 2026-09-22
      measured one property (R4) and the log made generalising it the top
      open item. `examples/phase5_property_coverage/` now does it for all
      **17** properties of all three suites: **252 sby invocations, ~12
      minutes**, three phases. Phase 1 deletes each property and re-runs
      every mutant; phase 2 keeps each candidate as the **only** live
      property, which is what separates SHADOWED (it can detect something,
      never alone) from UNEXERCISED (no mutant in the set is visible to it);
      phase 3 injects the defects the unexercised ones were written for.
      **9 load-bearing, 4 shadowed, 4 unexercised**, and two of the four
      holes closed on the spot (N8 for C1, M6 for P3 -- both now
      load-bearing). **Control:** the harness independently reproduces
      2026-09-22's hand-built R4 answer in phase 1 and its finer form in
      phase 2, without which its sixteen new answers would not be believable.
      **Findings recorded, not glossed:** (a) **cross-suite subsumption** --
      the CSR and reset jobs compile `-DFORMAL`, so both silently carry the
      2026-09-20 FIFO invariants, and C8 is shadowed by P1/P2 from a
      different day's suite, which no within-suite experiment can see;
      (b) C1's own comment said *"a width mutation is exactly what this
      catches"* and no width mutation had ever been injected -- a property
      advertised its coverage hole for two days; (c) a **name collision**
      (the FIFO cover block is also called `C1`) made the first run delete
      across two `` `endif ``s, caught by the G3 guard as INCONCLUSIVE rather
      than scored as a wrong answer -- invisible until something addresses
      properties by name; (d) **a correction made in-session**: the N9
      escape was first written up as a fifth failure class and is not one --
      2026-09-21's survivor mutant N5 had already established it. What
      survives is the **N10 control**, which separates "antecedent
      unreachable" from "antecedent unreachable OR property empty", a
      distinction one survivor mutant cannot make. **No property was
      deleted**; all seven reclassified ones are annotated in place with the
      reason they are kept.
      Write-up: `notes/2026-09-23-per-property-mutation-coverage.md`
- [x] Hands-on SymbiYosys/Yosys exercise -- **done 2026-09-20**.
      `tools/setup_formal.sh` installs Yosys 0.69 + SymbiYosys + z3 without
      root via the YoWASP WASM builds; `examples/phase5_formal_uart/`
      runs bmc / prove / cover plus a ten-run mutation stage, and
      **extended 2026-09-21** with a second suite, `examples/phase5_csr_formal/`,
      on the register map. Its Stage 4 re-runs the 2026-09-20 FIFO jobs
      with `-DFORMAL` only and requires PASS, so the claim "the new block
      did not disturb the old suite" is checked rather than asserted; its
      Stage 1 does the same one level down for the Phase 4 Icarus
      regression (60/60)
- [x] Milestone: SVA property suite + one formal property check w/
      documented result -- **done 2026-09-20**, with the SVA caveat above.
      Five properties (count range, pointer/count consistency, flag
      consistency, no silent over/underflow, two covers) in
      `rtl/uart_controller.v` under `` `ifdef FORMAL ``. Real RTL: bmc
      depth 24 PASS, **prove PASS by k-induction**, cover PASS with both
      statements reached (steps 10 and 6, so non-vacuous). Five mutants
      injected into COPIES, all five detected. Output recorded in
      `examples/phase5_formal_uart/formal_run_output_2026-09-20.txt`
      (10 passed, 0 failed)

**The verdict-vs-checking defect class, fourth occurrence -- and the first
caught in advance.** `prove` mode has THREE outcomes. Mutant M1 returns
`DONE (UNKNOWN, rc=4)`: basecase passes, induction fails. That is not a
counterexample -- the induction step starts from an arbitrary
property-satisfying state, which may be unreachable -- so a harness scoring
"prove did not return PASS" as a kill would claim a bug the tool never
found, and would call a correct-but-not-k-inductive design broken. The same
mutant under `bmc` gives `DONE (FAIL, rc=2)` with a real trace.
`run_formal.sh` scores bmc FAIL and prints the prove verdict as commentary.
The three earlier occurrences (2026-09-17, 09-18, 09-19) were all found
after the fact; this one was recognised before it produced a wrong number,
which is the first sign that the rule has actually been learned.

**Two guards worth keeping.** Stage 1 re-runs the Phase 4 60-check
regression and requires 60/60 before any formal work, so "the `` `ifdef
FORMAL `` block is invisible to Icarus" is checked rather than claimed.
Stage 4 deletes P1 and re-proves P2 to measure whether P1 is needed as a
strengthening invariant: it is not, and the negative result is recorded as
measured rather than quietly dropped.

## Phase 6 — Industry Flow & Capstone
- [x] **A DUT-signal census for every checker** (2026-10-12,
      `tools/scoreboard_dut_signal_census.py`, 6/6 controls): 16 rows over 5
      files, each naming the mutant that would prove the signal is checked
      rather than trusted. Its completeness control failed on the first run
      and found two uncensused reads plus five wrong names in the tool's own
      allowlist. The one TRUSTED row -- the Verilog CRV bench reading
      `STATUS.tx_full` to decide whether its own push was accepted -- was
      repaired the same session, M7 shown to escape three seeds before and be
      detected on all three after, with an exact output-neutrality pass over
      8 (seed, steer) combinations. Then the repair broke the census's own
      discriminating-power control, which had required a TRUSTED row to
      exist; see the note below.
      **Annotated 2026-10-22.** The before/after above is **true** and was
      **never produced by the committed runner**. `run_mutation_tests.sh`
      has injected M7 with one backslash too many since this very commit
      (`0a6c9bb`), emitting `4\x27d7`, which is a syntax error — and that
      runner scores `COMPILE_ERROR` as `DETECT`. So every committed report
      has recorded M7 as detected without ever compiling it, and a compile
      error cannot produce a before/after in either direction. Reproduced
      today with a correct injection: M7 escapes the pre-repair bench 3/3
      and is detected by the current one 5/5 in both modes. The claim
      stands; its evidence was not in the repository. See
      `examples/phase6_crv_uart/run_mutation_tests_bimodal.sh` (G3).
- [ ] Surrounding flow overview (lint, regression infra, coverage merge,
      waveform debug, bug triage)
- [ ] CDC verification basics
- [ ] Interview-prep pass (common question patterns)
- [ ] Capstone: UVM verification environment for register-mapped
      peripheral (UART/SPI controller with interrupt + FIFO datapath)
      - [~] Verification plan written -- early draft completed in Phase 3
            (**v3 revision DONE 2026-09-25**: F7 re-specified. v1 assigned
            F7 to directed checking of the TX bit period -- a check on the
            baud GENERATOR -- while F7's engineering content is the
            RECEIVER's tolerance to a transmitter at a different rate.
            v1 flagged that number "to be finalized once RTL exists" and it
            stayed open twenty days because **no bench the plan described
            could produce it**: every bench ran in loopback. The strategy
            becomes a driven-pin receiver on an independent timebase, the
            v1 TX-period check is retained as necessary and explicitly
            insufficient, and the measured table is inserted. The same
            revision absorbs the four other corrections the item had been
            carrying: unspecified reset values (09-22), C6/C7 assigned to
            formal where formal provably cannot reach them (09-23),
            Section 3's CRV assignment being unsatisfiable for F7 (09-24),
            and F3's sampling-margin corners plus F4's corrupted-parity
            check having been assigned to loopback stimulus that cannot
            produce them)
            (**v2 revision DONE 2026-09-19**: the plan's "live status"
            wording could not hold for the three STATUS error bits, which
            must be sticky/read-to-clear to be observable through a
            register read at all. Three independent findings forced it --
            the RTL bring-up 2026-09-17, the UVM environment's
            read-to-clear check 2026-09-18, and the register model
            2026-09-19, which cannot express the two halves of STATUS in
            one access policy. v2 also adds Section 1.2 on RX_DATA's
            read-side-effect. v1's text is annotated in place, not
            deleted; the plan's own Section 7 anticipated exactly this
            kind of RTL-informed correction)
            (`verification_plans/uart_controller_verification_plan.md`,
            2026-09-05); to be revisited/revised once Phase 4 RTL and
            testbench bring-up experience is available (see that plan's
            Section 7)
      - [ ] **Full UVM environment built** -- *disambiguated 2026-10-03,
            and the wording above is the root cause of a twelve-session
            error.* Phase 4's milestone environment
            (`examples/phase4_uvm_milestone/uart_uvm_tb.py`) is COMPLETE
            as of 2026-09-18 and contains a register agent, an active
            serial RX agent, a passive serial TX agent, a reference-model
            scoreboard, a functional-coverage collector, a virtual
            sequencer and five sequences. This box is NOT that, and said
            nothing about how it differed, so `AUTOMATION_LOG.md` carried
            "the UVM environment against the UART RTL ... untouched for
            twelve consecutive sessions" as a top open item for twelve
            entries describing work finished before the count started --
            see `tools/open_item_adjudication.md`. What this box actually
            still requires, stated so the next session inherits a
            distinction rather than a contradiction:
            **(a)** ~~constrained-random rather than directed stimulus
            inside the UVM environment (the CRV machinery exists in
            `examples/phase6_crv_uart/` in plain Verilog and has never
            been driven from a UVM sequence)~~ — **DONE 2026-10-11**,
            `examples/phase6_uvm_crv_uart/`: the same constraints, the
            same 30-bin model and the same DUT, with the generator as a
            `UVMSequence` through a `UVMSequencer`, a `UVMDriver` on the
            APB-lite interface, a passive `UVMMonitor` on a real
            `UVMAnalysisPort` and two independent subscribers on it
            (scoreboard and coverage collector). 5/5 mutants behave as
            required. Deferred for four consecutive sessions before this
            one;
            **(b)** the SVA protocol checkers of the next box, bound into
            that environment rather than standing alone;
            **(c)** `PayloadAdmissibilityCoverage` wired into the live
            `UartCoverage` collector (its own open item since 09-30;
            retargeted 2026-10-04 to the soundness-reporting subclass
            `EvidenceSoundCoverage`, and **sharpened 2026-10-05**: the
            audit below found the live collector's metric does not
            measure its own cross at all, so (c) now has a prerequisite
            -- the cross has to be gated, with its one unreachable cell
            excluded in the same change, before there is a sound metric
            to wire anything into);
            **(d)** the written methodology summary of the last box.
            Each is separately unchecked, so this box is a ROLL-UP of
            them and should be checked last, not first
      - [x] **Three-axis coverage audit run on the live `UartCoverage`
            collector (DONE 2026-10-05)** -- the first named target of the
            2026-10-03 item *run the soundness audit on every other
            coverage model here*, widened 2026-10-04 to three axes.
            `examples/phase4_uvm_milestone/coverage_axis_audit.py`
            (**17 checks, 0 failed**;
            `mutation_report_coverage_axis_2026-10-05.txt`, **6 of 6**
            with control A and control B). An OFFLINE CENSUS over the
            three committed sim logs (12 coverage reports), which is the
            route 2026-10-04 named and which audits a run already in the
            repository rather than one it generated for itself. Both
            anchors read real artefacts: the logged percentages are
            recomputed from the logged bin counts and required to match
            **exactly under the log's own one-decimal rounding** (0
            mismatches), and the structural claim is parsed out of
            `uart_uvm_tb.py` with `ast`. Findings:
            **F1** `coverage_percent()` reads `self.bins` and never
            `self.cross`, so the milestone's 100.0 % is 19 of 19 BINS and
            the nine-cell cross printed three lines above it is gated by
            nothing -- and vplan Section 5 names "coverpoints/**crosses**",
            so this is a plan-vs-implementation discrepancy;
            **F2** `(none, parity)` is unreachable by construction, so the
            cross's achievable cardinality is 8/9 and the committed run is
            AT that ceiling, not incomplete;
            **F1+F2 interact** -- folding the cross in without excluding
            that cell tops the metric out at 96.43 % against a target of
            100 and makes the gate unsatisfiable, so the two must land
            together and the choice is a reviewer's;
            **F3** 5 of the 8 closed cross cells rest on a single witness
            and all 5 are ERROR cells;
            **F4** the TEMPORAL axis that 2026-10-04 filed as a question
            has a concrete instance here, exhibited from the source
            (CTRL write at line 1367, cfg update at line 1368) rather
            than asserted. Nothing was changed: no coverpoint, no bin, no
            goal, no sign-off criterion, no committed number. The RUN axis
            is the honest gap and is reported as one -- the logs record
            counts, not per-sample witnesses, so run soundness is not
            decidable offline at all
      - [x] **The RUN axis is measurable, and measured** (**DONE
            2026-10-06**, closing the prerequisite the 10-05 three-axis
            audit named). `UartCoverage` now records PER-SAMPLE WITNESSES
            -- sample ordinal, simulation time, analysis port and the
            item's own `convert2string()` -- for every cell, bounded at
            `WITNESS_KEEP = 4`, with five runtime assertions (W-a..W-e)
            requiring the witness bookkeeping and the printed counts to
            agree. All five UVM tests re-run and committed
            (`uart_uvm_sim_output_2026-10-06.txt`, 5 PASS / 0 FAIL,
            "audit verdict PASS over checks W-a to W-e" at 54, 913, 913,
            1283 and 2315 coverage samples); mutation harness
            `mutation_test_witnesses.py` **5 of 5**, control A passed,
            control B survived.
            **THE MEASUREMENT** (`run_axis_audit.py`, offline over the
            committed transcript, 6 checks / 0 failed, now gated in
            `run_phase4_uvm.sh` as a third model check): 9 of 27 cells are
            hit more than once and closed by a SINGLE repeated stimulus
            every time. The whole payload coverpoint is the clearest case
            -- `cp_tx_data` reports 5/5 bins hit and each of its five
            RANGE bins was closed three times by one byte (0x00, 0x3c,
            0xa5, 0xd2, 0xff). `cp_rx_error.parity` twice by 0x7e;
            `wr_baud` and `wr_int` seven times each by one write. **The
            milestone test reports 100.0 % functional coverage.** This is
            the 10-05 fault one axis over: a figure that measures exactly
            what it says (bins touched) printed beside the question a
            reader reads it as answering (bins exercised).
            **A METHODOLOGICAL RESULT FROM THE SAME RUN:** the audit reads
            all five tests because a per-test view would have been wrong
            -- in the milestone test `cp_rx_error.frame` is closed three
            times by 0xc3 and looks monotonous, but the baud-tolerance
            tests close it with 0x01 and 0x55.
            **LIMIT, stated in the transcript before the numbers:**
            diversity is a PREFIX measurement over the first 4 samples
            (7 of 27 cells truncated), so every number is a lower bound.
            The repair -- a bounded SET of distinct signatures per cell
            alongside the first-N witnesses -- is this item's successor and
            is listed in `AUTOMATION_LOG.md`. No diversity TARGET is
            proposed; that changes a sign-off criterion and is a
            reviewer's decision
      - [x] **Diversity is EXACT, and the diversity-1 finding survives it**
            (**DONE 2026-10-08**, closing the successor the 10-06 run-axis
            item named for itself). `UartCoverage` now keeps, per cell, a
            bounded list of DISTINCT stimulus signatures beside its
            first-`WITNESS_KEEP` witnesses -- a signature being a witness
            with the ordinal and the simulation time removed, so two
            samples carrying the same stimulus collapse and the size of
            the set IS the cell's diversity. `SIGNATURE_KEEP = 16`, and
            the bound REPORTS hitting itself: `sig_overflow` counts the
            distinct signatures it refused, per cell, so a cell prints
            EXACT or `BOUNDED (+n refused)` and is never read as a
            measurement when it is a lower bound.
            **Not merely a larger `WITNESS_KEEP`:** a witness list answers
            which sample closed a cell and in what order, which is why
            witnesses carry an ordinal; a signature set answers how many
            DIFFERENT things hit it, for which the ordinal is noise that
            would make every entry distinct. Two bookkeepings, two
            questions, same samples -- so check S-d requires them to agree.
            **Six runtime assertions, S-a..S-f**, and S-f is the one that
            earns its keep: S-a..S-e are ALL computed from the stored
            list, so all five are blind to a cell whose `sig_overflow`
            stopped incrementing -- it would print EXACT while silently
            truncating, the exact fault the mechanism exists to prevent.
            S-f compares the stored accounting against an INDEPENDENT
            64-bit crc32 mask (popcount is a one-sided lower bound;
            collisions lose bits, never invent them) on a code path that
            never reads the stored list. `crc32` and not `hash()`, because
            `hash()` of a `str` is salted per process and a check whose
            verdict depends on the process is not a check.
            **THE MEASUREMENT** (`run_axis_audit.py` Section 2b, 11 checks
            / 0 failed): **all 9 prefix-diversity-1 cells are CONFIRMED
            exactly 1** -- the 10-06 finding survives becoming a
            measurement, which was not guaranteed; **7 of 27 cells had
            their diversity UNDERSTATED by the prefix**, largest gap
            `cp_rx_error.frame` 7 -> 19, so the prefix was not merely
            conservative in principle but wrong about a quarter of the
            cells, and none of those were the cells the finding rested on;
            **5 of 27 remain BOUNDED** with their refused counts printed.
            All five UVM tests re-run and committed
            (`uart_uvm_sim_output_2026-10-08.txt`, 5 PASS / 0 FAIL,
            "audit verdict PASS over checks S-a to S-f").
            **Mutation harness `mutation_test_signatures.py`: 5 of 5 fault
            mutants killed, and S4 (`sig_overflow` stops incrementing) is
            killed by S-f ALONE** -- which turns the claim that S-a..S-e
            are blind to it from an argument about code paths into a
            result. Its `--selftest` mode is committed too.
            **AN ARRIVAL CONTROL, forced by that harness's first run.** It
            reported S4 and S5 as SURVIVED, i.e. that the mechanism misses
            its two most important faults. It misses nothing: both ran
            against the milestone test, where 27 of 27 cells are EXACT, so
            the bound never bites, `sig_overflow` never increments and the
            cap is never reached. **Those mutants never arrived.** Each
            row now names its testcase (S4/S5/S6 run against
            `test_uart_adaptive_observer`, 5 of 11 cells BOUNDED), control
            A is re-run per distinct testcase because a baseline from a
            different stimulus is not a baseline, and every mutant's own
            `COV_SIGNATURE` block is compared against that baseline --
            byte-identical scores the row **INERT**, neither killed nor
            survived. A row can only be called SURVIVED once it has been
            shown to have done something. This is 2026-09-29's rule in the
            one place this repository had not yet put a control for it, and
            it was one commit away from being recorded as a real gap.
            **TWO INERT ROWS, both informative.** Control B is INERT rather
            than SURVIVED, which is STRONGER: its claim is that a different
            implementation produces the same output, and INERT asserts the
            printed block is byte-identical rather than merely that nothing
            complained. **S6 (the crc32 mask stops being updated) is INERT,
            which measures a limitation of S-f: it is ONE-SIDED.** With an
            empty mask popcount is 0, which is <= any accounting, so S-f
            passes -- it detects an accounting that is too small and cannot
            detect its own evidence going missing. A positive control that
            requires S-f to FIRE does not exist yet and is a new open item,
            of exactly the kind 2026-10-07's `phase4_ral` work built.
            **A SECOND, SMALLER DEFECT FIXED: a `ZeroDivisionError` is not
            a verdict.** `run_axis_audit.py` crashed when pointed at a
            transcript that was still being written -- "0 of 0" cells, then
            a traceback inside R4's percentage and NO `RESULT` line, which
            the runner could only read as "0 RESULT lines, expected 1". New
            check R0 reports "this artefact does not contain what I audit"
            as a FAILED CHECK, because that is a fact about the artefact and
            is what a reviewer needs told; its failure path was exercised
            against a witness-free log before being committed. Any
            truncated, rotated or partially-copied transcript reached this
            audit the same way, and before today every one produced a
            traceback instead of a verdict
      - [ ] SVA protocol checkers added
      - [x] Functional coverage report + closure target stated
            (**DONE 2026-09-24**, `examples/phase6_crv_uart/`, the top and
            longest-standing open item). Constrained-random,
            coverage-driven UART stimulus in plain Verilog-2001 --
            rejection sampling with a bounded attempt budget standing in
            for a constraint solver (309 rejections on a random run,
            worst single draw 11, budget 200) and counter arrays standing
            in for a covergroup, because Icarus 10.3 has none of `rand`,
            `constraint` or `covergroup`. 30 bins over 5 coverpoints and
            2 crosses; **closure is a PASS CRITERION, not a report
            line**, and that decision earned itself twice over (see the
            two notes below). Measured over 8 seeds, same constraints,
            same seeds, steered vs pure random: mean 341 -> 47
            transactions to closure (**7.3x**), worst seed 643 -> 60
            (**10.7x**), best seed 105 -> 36 (2.9x), seed-to-seed spread
            6.1x -> 1.7x. **The spread is the result**: coverage-driven
            stimulus buys predictability of closure rather than speed,
            and a regression budget is set by the worst case. Mutation
            report: 6 injected into COPIES of the RTL, 4 detected,
            2 escaped, **6/6 verdicts as predicted in advance**
            (`mutation_test_report_2026-09-24.txt`)
      - [ ] Written summary of methodology/results
      - [x] Constrained-random stimulus driven at the RX PIN rather than
            through loopback -- created 2026-09-24 by mutation M5, and
            the reason F7's baud tolerance was unmeasured: in
            loopback the TX and RX engines SHARE one baud generator, so a
            wrong divisor desynchronises nothing and **no loopback bench
            at any level of sophistication can detect a baud-rate
            error**. Structural, not a stimulus gap.
            (**DONE 2026-09-25**, `examples/phase6_rx_pin_driver/`, 888
            lines, 93 checks, 0 errors, 3 seeds.) The driver holds its own
            bit period and reads nothing from the DUT's clock, baud
            counter or oversample tick; loopback is off throughout.
            **F7 measured at last**: 8N1 tolerates a transmitter 6.25%
            slow / 4.50% fast, 8E1 5.60% / 4.05%. Three properties of
            that matter more than the numbers -- it is **asymmetric**
            (late drift off a stop bit is harmless because the line idles
            high, so the fast side is bound by the last sample carrying a
            VALUE and the slow side by the last STOP bit); **parity costs
            tolerance**, so F7's number is per frame format, while a
            second stop bit costs nothing; and it is a **band, not a
            number**, because uncontrolled edge phase against the
            free-running 16x counter quantises the sample point in
            1/16-bit steps, one of which is 0.69% of eps. The defensible
            claim is "better than +/-4.0% in every configuration
            measured". T0 **measures** the sample point rather than
            trusting the RTL comment, which says mid-bit (0.5000) and is
            wrong by up to two oversample ticks -- so pre-registered
            predictions P1 and P4, derived from that comment, are scored
            FAIL and left in the file. Two independent routes to the
            tolerance (a sweep, and arithmetic on the measured sample
            point) agree, and that cross-check is the only thing in the
            suite that catches two of the seven mutants. **Mutation: 7
            injected, 7 detected, 0 escaped** -- including M1, the
            BAUD_DIV mutant that escaped the 09-24 loopback bench, which
            is the row the directory exists for
            (`mutation_test_report_2026-09-25.txt`). Also newly reachable
            and all impossible in loopback: framing errors, parity errors
            in both polarities, deterministic overrun with the eight
            queued bytes verified intact, and the start-bit glitch filter
      - [x] A coverpoint on the driven baud ERROR -- created 2026-09-25 by
            the v3 plan revision. `cp_baud_div`'s corner bins measure the
            divisor REGISTER, not the tolerance; F7 needs bins on
            {0, within +/-2%, within +/-4%, beyond the limit} and a
            closure criterion over them. The stimulus now exists; the
            coverage model does not.
            (**DONE 2026-09-26**, `examples/phase6_baud_error_coverage/`,
            ~1030 lines, 11 checks, 0 errors, 3 seeds; mutation 5 detected,
            1 expected escape, 0 unexpected, 0 voided.) T1 disposes of the
            premise first: sweeping eps from -8% to +8%, which takes the
            receiver from perfect through broken and back, `cp_baud_div`
            reports **1 of 4 bins hit, unchanged throughout** -- a coverage
            report on a register nobody wrote.
            **The bins the item asked for are the wrong bins, measured
            three ways.** They do not PARTITION the domain (8N1's slow
            limit is +6.25%, so +5% is outside "within +/-4%" and inside
            the limit and belongs to no band; a fifth band was needed and
            took 19 of the 28 frames of the steered closure run). Their
            absolute edges disagree with the DUT on **7 of 12** probe rows.
            And the "beyond the limit" edge is a MEASURED number that moved
            **0.50% of eps, optimistically**, when two of six trial bytes
            were swapped (`0x3C`/`0x81` for `0x01`/`0x80` -- the latter put
            a lone 1 next to the start and stop bits, exactly where a
            drifting sample lands on a differing neighbour), so a bin whose
            edge is measured inherits the optimism of the stimulus that
            measured it.
            **What must not be written into sign-off:** "beyond the limit
            implies an error". It is false and data-dependent, as 09-25's
            own staircase showed (8/8 frames failed with `data[7]=0`, 0/8
            with `data[7]=1`), so it is neither a bin nor an assertion.
            **Reachable is not reached:** pure random stimulus did NOT
            close in 250 frames -- the error outcome in the fifth band
            lives in the last few basis points below the limit -- while the
            same criterion closes in 28 once the generator aims at its
            first unhit cell. A cell can be reachable, correctly judged
            reachable, and still out of a uniform generator's reach.
            **The coverage model itself detects nothing:** in every detected
            mutation row the first failure is the anchored cross-check of
            the measured tolerance against 09-25's values, and every mutant
            fills the same bins. Plan revised to **v4**
      - [x] **A reachability pre-pass turned into illegal bins fires
            against correct RTL -- created and closed 2026-09-26.** 09-24's
            finding 9 says to check a bin is reachable before putting it in
            a closure criterion. Implemented with TWO verdicts (reachable
            if the pre-pass produced the cell, unreachable otherwise, every
            unreachable cell an illegal bin), an illegal bin **fired
            against correct RTL 21 frames into the random run** -- band 3 x
            byte-lost, eps = -4.71% on 8O1, with a data pattern and edge
            phase the pre-pass had not tried. **A pre-pass answers "did my
            attempts reach it", which is not "is it reachable".** Fixed
            with three verdicts: REACHED (into the closure criterion),
            EXCLUDED BY ARGUMENT (the only illegal bins -- at eps = 0 no
            drift accumulates and the initial phase is worth < 1/16 bit
            against a half-bit margin) and OPEN (neither goal nor
            assertion, an honest unknown). Seed 2 of the committed output
            shows the same refutation happening safely under the new
            scheme, at frame 127, reported as a result. Also recorded:
            "unreachable" is a property of a bin AND a stimulus space --
            `eps == 0` x frame error is excluded for well-formed frames and
            trivially reachable once the stop bit may be corrupted
      - [x] **Fold the independent-timebase driver into the Phase 4 UVM
            environment as a real `uvm_driver` -- DONE 2026-09-27**, with
            the prerequisite discharged first. Created 2026-09-25, top item
            from 2026-09-26. `bfm/uart_rx_pin_bfm.v` is now the
            repository's ONE pin driver -- no clock port, no cycles
            counted, its only timebase `bit_ps` -- and Phase 4 plus both
            phase6 benches drive it, from two languages. The verbatim
            duplication is gone. `examples/phase4_uvm_milestone/
            uart_uvm_top.v` instantiates the DUT beside the BFM and
            `UartSerialDriver` programs it instead of bit-banging
            `dut.rx`; `UartFrameItem` gained `eps_bp` and `phase_ps`.
            Deliberately not a Python reimplementation of the timebase --
            that would have been the third copy the item existed to
            prevent. Measured from UVM: 8N1 slow **+6.75%**, fast
            **-4.00%**, both inside the derived +/-1.00% band around
            09-25's numbers, at `BAUD_DIV=0` where phase6 ran at
            `BAUD_DIV=1`. See `examples/phase6_bfm_equivalence/` for the
            ps-resolution proof that the extraction is a pure refactor
      - [x] **Both phase6 regression runners were reading YESTERDAY'S log
            -- FOUND AND FIXED 2026-09-27.** Not previously on any list.
            `run_rx_pin.sh` and `run_baud_cov.sh` piped each seed to a
            FIXED `/tmp` path and gated on `grep -q 'RESULT: PASS'`
            against it; the sandbox reuses `/tmp` across sessions with
            different uid mappings, so `tee` failed with "Permission
            denied" and `grep` read the 2026-09-26 file, which said PASS.
            Demonstrated: a bench edited to print `RESULT: FAIL` was
            reported as `ALL 1 SEEDS PASS`, exit 0. Both directions are
            live -- a stale PASS log gives a false pass, no writable log
            gives a false failure. Fixed with a private `mktemp` log, an
            empty log counting as FAILURE, and exactly one `^RESULT:` line
            required. The verdict-vs-checking class at the OUTERMOST layer
      - [x] The tolerance window's WIDTH is divisor-invariant and its
            CENTRE is not -- created 2026-09-27, **BUILT AND CLOSED
            2026-10-01**, and both halves came out stronger than stated.
            `examples/phase6_divisor_window/uart_divisor_window_tb.v`,
            16 checks, 18483 frames, plain Verilog on Icarus: six
            divisors (0,1,2,3,7,15) x four edge phases, 5 bp grid.
            **The width is EXACTLY 1/9 = 1111.1 bp in all 24 cases**
            (measured 1105-1110, bracketing it everywhere) and it moves
            with neither the divisor nor the phase -- because the slow
            limit is `(1/2+p)/span`, the fast limit is `(1/2-p)/span`,
            and the sampling lateness `p` cancels from the sum. **And
            that 1/9 is twice v6's `1/18` lock-once budget**, so the two
            windows 09-28 called 11.00% and 11.10% are EQUAL and the
            whole containment failure is displacement. The CENTRE,
            conversely, moves **50-53 bp with the edge phase at every
            divisor** -- the same size as the entire divisor-driven
            variation from div 1 to div 15 -- so the +0.50% two-point
            shift was confounded, and the committed slow 675 / fast 400
            pair reproduces exactly at HALF AN OVERSAMPLE TICK and at no
            other of four phases. Three of my own pre-registered
            predictions were refuted (A2a, P3, P5) and are kept in the
            suite as failing checks, so its expected result is
            `13/16 ... 3 failed` and `run_divisor_window.sh` gates on
            exactly that. ORIGINAL ITEM TEXT:
      - [x] (as filed 2026-09-27) The most concrete open experiment. 10.75% wide at both `BAUD_DIV=0` and
            `BAUD_DIV=1`, identical to the basis point, with the whole
            window displaced +0.50%. Candidate mechanism: `rx_sync`'s
            one-clock delay is 1/32 of a bit at `BAUD_DIV=1` and 1/16 at
            `BAUD_DIV=0`, predicting ~0.33% against a measured 0.50% --
            inside one 25 bp grid step, so this grid cannot tell them
            apart. The experiment: one bench, both divisors, 5 bp grid
      - [x] An INDEPENDENT observer for the serial line -- created
            2026-09-27, **BUILT AND CLOSED 2026-09-28**, and it did not
            give F7 an oracle. `UartSerialMonitorIndep` never references
            `dut.clk`: it waits on a falling edge of the PIN and advances
            with `Timer` in ps on its own spec-derived period, enforced
            structurally (check V2 reads the class's own source and fails
            if `dut.clk`/`RisingEdge`/`BIT_CYCLES` appears in its body).
            `UartEdgeRecorder` records transition TIMESTAMPS and decodes
            offline with a per-frame margin. Both are in the Phase 4 env,
            neither wired to the scoreboard on purpose. Four decoders on
            one sweep of 256 frames
            (`test_uart_independent_observer`): DUT 10.75% wide centred
            **+1.38%**; clock-synchronous 11.00% at +0.75%; independent
            **11.10% at exactly +0.00%**; recorder the same.
            **WIDTH IS NOT CONTAINMENT** -- the observer is WIDER and
            still does not contain the DUT's displaced window, and at 13
            baud errors from +5.60% to +7.75% the DUT receives cleanly
            while the observer does not. Any observer that locks once on
            the start edge and counts a nominal period has an 8N1 budget
            of exactly **1/18 = 5.5556%**, against the DUT's 6.75% slow
            limit, so the whole class is disqualified by arithmetic
            (vplan v6). Disagreement with the DUT, reported as a RESULT
            per the item's own request: 7.65% clock-synchronous, 18.82%
            independent, 18.24% recorder -- against 0.39% measured 09-27,
            i.e. a genuinely independent observer disagrees ~24x more
            often. Q1 also **locates v5's centre offset in the DUT**,
            since the independent observer's window is centred at exactly
            zero. See notes/2026-09-28-width-is-not-containment.md
      - [x] A coverpoint on the data pattern's adjacent-bit TRANSITION
            count -- created 2026-09-26 by the trial-set experiment above.
            **BUILT AND CLOSED 2026-09-30 in the same file as the `ctz`
            coverpoint, and it has 5 BINS AND NOT 10, by a parity theorem
            rather than by enumeration:** the framed stream begins at 0
            (start bit) and ends at 1 (stop bit) and every transition flips
            the level, so the count between unequal endpoints is
            necessarily ODD -- bins `{1,3,5,7,9}`. This holds for any
            payload width and any frame with unequal start and stop levels,
            so it is a bound on the coverage model, not a measurement of
            this DUT. Positive control on the argument: a 0-start/0-stop
            frame gives EVEN counts for all 256 bytes, so the parity comes
            from the endpoint levels and not from the frame length. A 0..9
            coverpoint would have sat permanently at 50%. **The cross with
            `ctz` has 23 reachable cells of 35**, enumerated over all 256
            bytes rather than argued, because `g_first` fixes the low bits
            and so constrains the achievable transition count -- full-grid
            closure would report 65.7% at actual closure. This also answers
            2026-09-23's question of which rules here could be restated as
            parities or bounds. ORIGINAL ENTRY FOLLOWS, unchanged:
            The baud tolerance depends on whether adjacent bits differ, so
            the right data coverpoint for F7 is the transition count and
            not the byte value; `cp_data`'s one-hot / AA-55 / popcount bins
            do not measure it.
            **PROMOTED 2026-09-28 from a preference to a SIGN-OFF
            DEPENDENCY (vplan v6), with a quantitative reason.** The edge
            recorder's per-frame margin is an EXACT function of the frame's
            transition pattern -- a boundary with no transition across it
            is not an edge, so the nearest-edge distance depends on which
            adjacent bits differ. Matched to a closed form over 170 probes
            to **0.0000 bit** once the data dependence was included, having
            been out by up to 0.27 bit while it was assumed away. A
            coverage model over byte VALUES therefore cannot span the
            margin.
            **Second instance 2026-09-29, and it generalises the item:**
            the adaptive observer's BUDGET is an exact function of a
            different per-byte quantity, `1 + ctz(data)`. Two orthogonal
            per-byte functions now determine what an F7 result means, and
            neither is a function of the byte's value in any way a value
            or range coverage model can span. The general form, for the
            interview answer as much as for the vplan: **an instrument
            that derives its reference from the signal it measures makes
            the signal's content part of its own specification, and owes
            a coverage model over whatever the adaptation depends on**
      - [x] An observer that RE-DERIVES the bit period per frame from
            the measured edge spacing -- created 2026-09-28,
            **BUILT AND CLOSED 2026-09-29, and it DOES contain the DUT's
            window -- conditionally, and the condition is on the
            STIMULUS.** Every observer built before it locks once on the
            start edge and counts a nominal period, which caps its 8N1
            budget at 1/18 = 5.5556% by arithmetic. The edge recorder was
            the right KIND of instrument and did not yet do this.
            `UartAdaptiveEdgeObserver` + `test_uart_adaptive_observer`
            assign each inter-edge gap an integer bit index
            `round(dt/T_ref)` and update `T_ref` to the running
            least-squares estimate, so the period comes from the frame.
            **The pre-registered budget law `1/(2*g_max)` is WRONG and the
            replacement is the session's result**: only the FIRST gap is
            assigned against the observer's own period, because the LS
            update has already replaced it by the second, so
            `|eps| < 1/(2*g_first)` with `g_first = 1 + ctz(data)` --
            **the observer's tolerance is set by the position of the
            lowest set bit in the payload and by nothing else in the
            byte**, over a 9x range. Measured on ALL 256 bytes at 1 bp
            resolution rather than the nine frames the simulation ran
            (`budget_law_exhaustive.py`, 256/256, `g_max` law kept as a
            negative control and refuted by 166 bytes, tolerance region
            verified contiguous, no simulator needed so it runs first in
            `run_phase4_uvm.sh`). Containment holds for 254 of 256 and
            fails for exactly `0x00` (5.56%) and `0x80` (6.25%) against
            the DUT's 6.75% slow limit -- **now a measurement over the
            whole input space, not an extrapolation.** Also measured: the
            law is two-sided for `g_first >= 2` and ONE-SIDED for
            `g_first = 1`, where the decode's `if dn < 1: dn = 1` clamp
            turns the only value a fast first gap can wrongly round to
            back into the right one. vplan v7. See
            notes/2026-09-29-the-lowest-set-bit.md
      - [x] A coverpoint on `ctz(data)` -- created 2026-09-29 and a
            SIGN-OFF DEPENDENCY on arrival (vplan v7), for the same reason
            as the transition-count coverpoint below and orthogonal to it:
            `ctz` sets the adaptive observer's BUDGET, transition count
            sets its per-frame MARGIN, and no coverage model over byte
            values or ranges spans either. Nine bins (`g_first` 1..9), of
            which two (`0x80`, `0x00`) must be **excluded** from carrying
            F7 evidence rather than merely counted -- so this is an
            illegal-bin question as much as a coverage one.
            **BUILT AND CLOSED 2026-09-30, and building it found that
            vplan v7's two clauses CONTRADICT each other.**
            `examples/phase4_uvm_milestone/payload_coverage_model.py`,
            **24/24**, simulator-free, wired into `run_phase4_uvm.sh` under
            the 09-27 gate discipline; log
            `payload_coverage_model_2026-09-30.txt`.
            - **The contradiction:** `g_first = 9` is reachable only by
              `0x00` and `g_first = 8` only by `0x80`, so excluding those
              two bytes EMPTIES two bins of the coverpoint v7 just made a
              sign-off dependency. A 9/9 goal is unachievable for any legal
              F7 run. Amended to 7/7 over the legal subset with those two
              as `illegal_bins` (vplan v8).
            - **Anchored, not re-derived:** the admissibility classes come
              from the MEASURED per-byte limit columns of the committed
              `budget_law_exhaustive_2026-09-29.txt` CSV, read from that
              file, with `1/(2*g_first)` used only as a second route and
              required to agree 256/256. Two negative controls confirm the
              classification tracks the window it is given -- a 500/300
              window empties the set, a 5000/400 window takes all 256.
            - **The illegal bin RAISES rather than counts**, with a
              positive control requiring it NOT to raise on `0x01`.
            - **1.56% of uniform frames, not 0.78%**, are not clean F7
              evidence once BORDERLINE is counted; the 0.78% is confirmed
              exactly as 2/256 and is the inadmissible half only.
            - **A constrained-random generator excluding the illegal bytes
              still closes the cross:** 703 draws close all 23 reachable
              cells, so the exclusion does not make the goal unreachable.
            - Mutation report: 6 injected, **6 detected, 0 escaped**, each
              with a positive control on the mutation itself;
              `mutation_report_payload_coverage_2026-09-30.txt`
      - [x] `0x40` and `0xC0` are BORDERLINE, not passing -- created
            2026-09-29, **CLOSED 2026-10-01 by splitting them**, which is
            not the answer the item expected. `0xC0` is a
            SINGLE-TRANSITION byte (`g_first = span = 7`) and is now
            **excluded outright**, not borderline: its measured DUT slow
            limit is 825 bp against the observer's 714. `0x40` is
            multi-transition (`g_first = 7`, `span = 9`) and is
            **contained**, measured 650 bp against 714. So the pair was
            never one question. `0x40` is the new margin to watch: it
            needs `p <= 1/7 = 0.1429` and the largest `p` measured
            anywhere is `0.1233` -- 14% of headroom. The 39 bp figure was
            for `0xC0` and is superseded for that byte. ORIGINAL TEXT:
      - [x] (as filed 2026-09-29) A correction to the same day's own
            254/256 framing. `g_first = 7` gives a 7.143% window against
            the DUT's 6.75% slow limit: a margin of **39 bp**, while
            09-25 measured one oversample tick of initial edge phase
            moving a limit by 0.69% of eps. The margin is inside the
            uncertainty, so containment at the third-tightest byte class
            is not established. This is the strongest reason yet to do the
            two-divisor 5 bp window measurement already open above, and
            those two items should be closed together
      - [ ] A mutant on `budget_law_exhaustive.py`'s own STIMULUS
            generator -- created 2026-09-29 and recorded in the mutation
            report as not done. The three mutants run today all touch the
            decode. A defect in `frame_edges`/`bit_ps_for` would move the
            model without moving the simulation, and V6 -- the one check
            anchored to the committed simulation log -- is the only thing
            that would notice, so its sensitivity is untested
      - [x] The DUT's +1.38% window displacement needs a NEW candidate
            mechanism -- created 2026-09-28 by Q1's success,
            **ANSWERED 2026-10-01, and the answer is partly that the
            quantity is not what it looked like.** (a) The +1.38% is not
            a property of the DUT alone: the centre spans 87-137 bp over
            four edge phases at `BAUD_DIV=0`, and +1.38% is the value at
            one of them. (b) `rx_sync` is a REAL contributor and not the
            whole: mutated out (a genuine combinational bypass, M3), it
            moves **20 of 37** committed window entries. (c) The new
            structural term is the **ninth oversample tick**:
            `rx_mid = os_tick & (rx_os == 8)` fires on the NINTH tick
            after `rx_os` is zeroed, not the eighth, which is +1/16 bit
            of lateness that does not scale with the divisor. (d) My
            pre-registered quantitative model built on that term is
            nonetheless **FALSIFIED** -- the latency recovered from the
            centre is non-monotone in the divisor and comes out negative
            (P3), which is unphysical. So the mechanism is identified in
            kind and NOT in magnitude, and that is where it is left.
            ORIGINAL TEXT:
      - [x] (as filed 2026-09-28) `rx_sync`'s one-clock delay is 1/16 of
            a bit at `BAUD_DIV=0` = 6.25%, four and a half times the
            measured 1.38%, so that candidate does not fit its own
            magnitude. With the measurement path exonerated
            (the independent observer's window is centred at exactly zero),
            the displacement is the receiver's. But `rx_sync`'s one-clock
            delay is 1/16 of a bit at `BAUD_DIV=0` = 6.25%, four and a half
            times the measured 1.38%, so that candidate does not fit its
            own magnitude and the 09-27 note's mechanism has to be replaced
      - [ ] Audit the other benches' observers for the CONTAINMENT
            property -- created 2026-09-28. The phase6 benches measure F7
            too and not one of them states its own window, which vplan v6
            now requires of anything offered as F7 evidence.
            **Widened 2026-09-29 by vplan v7:** the audit must now ask a
            second question of each observer -- not only "what is your
            window" but "does your window DEPEND on the stimulus, and is
            that dependence covered". Every fixed-period observer answers
            no to the second, which is the one case where the v6 form of
            the question was sufficient
      - [x] **The `g_first` / transition / cross goals RE-DERIVED against
            the nine-byte exclusion (vplan v10, 2026-10-02)** -- the
            2026-10-01 top item, done. `examples/phase4_uvm_milestone/
            reachable_cross_under_per_byte_rule.py`, log
            `reachable_cross_per_byte_rule_2026-10-02.txt`, 21 checks /
            0 failed; sensitivity
            `mutation_report_reachable_cross_2026-10-02.txt`, 9 of 9
            mutants as required with control A **and control B**. The
            nine are derived three independent ways and required to
            agree (`span == g_first`, `transitions == 1`, and the closed
            form `256 - 2^k`, the last being arithmetic rather than a
            scan so it cannot share a scanning bug with the others), and
            v8's committed 23-of-35 cross and **703-draw closure at seed
            20260930 are reproduced EXACTLY** before any new number is
            computed. Results: **the 7/7 `g_first` goal is UNCHANGED and
            correct as committed**; the framed-transition goal is **4
            bins, not 5** (the parity theorem still holds, but
            `transitions == 1` is true for exactly the nine excluded
            bytes, so the `1` bin has no legal witness and a 5-bin goal
            would sit permanently at 80%); the cross is **16 reachable
            cells of 28**; closure is **663 draws**, which is FASTER than
            v8's 703 from seven FEWER legal bytes, because 7 of v8's 11
            single-witness cells were themselves among the newly excluded
            -- measured, not argued
      - [x] **The F7 cross cannot be closed without drawing `0x40`, and
            `0x40` is BORDERLINE** -- created 2026-10-02 as the top item,
            **measured and closed 2026-10-03 (vplan v11)**, and two of
            the three things it asserted were wrong.
            `examples/phase4_uvm_milestone/witness_soundness.py` +
            `witness_soundness_2026-10-03.txt`, 46 checks / 0 failed;
            `mutation_report_witness_soundness_2026-10-03.txt`, 12 of 12
            with control A, control B and the 10-02 compound form.
            Anchored first against five committed numbers (v8's 23-of-35
            and 703 draws, v10's 16-of-28 and 663, 10-02's 25-cell
            control and its 11-of-23 and 4-of-16 single-witness counts),
            all exact. **The generalisation: a bin needs an ADMISSIBLE
            witness, not just a witness.** `scarce(bin)` governs the cost
            of closing it; `evidence_unsound(bin)` -- no witness is
            ADMISSIBLE -- governs whether closing it means anything, and
            the two are independent (three of four quadrants populated;
            transition bin 9 is scarce and perfectly sound). **(i) One
            byte, but TWO coverpoints:** `0x40` is also the sole legal
            witness of `g_first` bin 7, so v10's 7/7 goal -- the one
            amendment of five it declared "correct as committed and needs
            no change" -- cannot be closed by an interpretable frame
            either. Its cardinality claim is reproduced as a PASS; the
            sign-off conclusion does not follow from it. **(ii) The
            defect dates from v8, not from v9's exclusion:** over all 256
            bytes bin 7 is reached only by `0x40` and `0xC0`, and v7
            recorded BOTH as borderline on 09-29, so the bin has never
            had an admissible witness. The nine-byte rule removed `0xC0`
            and made an old unsound bin newly *scarce*, which is the only
            reason a scarcity scan now sees it. **(iii) Four ways out,
            and two of them change nothing a reader can see:** excluding
            `0x40` and merging `g_first` 7 into a `6+` bin give the same
            6 bins / 4 bins / 15 of 24 / zero unsound, and a 40-seed
            sweep does not separate their closure cost either (W1 faster
            on 22 of 40, means 499 vs 421). No number in the vplan
            distinguishes a plan that still drives `0x40` from one that
            does not -- only the stimulus log does. **And the instrument
            re-derives v8's hand-made `illegal_bins` as a corollary** (no
            exclusion -> unsound bins `{7,8,9}`, where 8 and 9 are
            unsound by *inadmissible* witness), so soundness is the
            general rule of which the exclusion is the special case
      - [ ] **DECIDE between W1, W3 and W4 for F7's goal** -- created
            2026-10-03 and **the new top item**, and the one thing today
            deliberately did not do: the derivation is committed but the
            choice changes a committed sign-off criterion, so v11 flags
            it for review rather than applying it. W3 (merge `g_first` 7
            into `6+`) is recommended because it is numerically identical
            to W1 while keeping `0x40` in the stimulus, so W1 pays for
            the clean number with DUT exercise it did not have to give
            up; W4 (exclude the one frame from F7's *timing* oracle while
            keeping it under F1's) is the only option preserving a 7-bin
            goal and needs an oracle change rather than a goal change.
            **Until it is decided F7's goal is W0 as committed, with two
            evidence-unsound bins** -- now recorded rather than implicit
      - [ ] **Run the soundness audit on EVERY OTHER coverage model in
            this repository** -- created 2026-10-03, **not done, and
            2026-10-04 made it bigger rather than smaller**. F7's three
            coverpoints are now audited on a *third* axis as well (run
            soundness), so every other model here is unaudited on three
            axes, not two: `examples/phase6_crv_uart/`'s Verilog
            coverpoints and crosses, the live `UartCoverage` collector in
            `uart_uvm_tb.py`, and `phase5_property_coverage`'s per-property
            model. The Verilog ones are the harder half, because
            `EvidenceSoundCoverage` is a python class and Icarus has no
            coverage API -- the realistic route is an offline census over
            the same stimulus log rather than a live collector. The fourth
            quadrant, abundant-and-unsound, is empty in F7's data and is
            **not** claimed impossible: it needs a bin all of whose many
            witnesses are borderline, and F7's population has only two
            borderline bytes. A model with a wider borderline band would
            have one, **and no scarcity scan at any threshold would find
            it** -- so this is not subsumed by the witness-count item
      - [x] **Give the BORDERLINE case a mechanism, as `illegal_bins`
            gives the inadmissible case one -- DONE 2026-10-04
            (vplan v12).** `examples/phase4_uvm_milestone/evidence_soundness_coverage.py`,
            **39 checks / 0 failed**, `evidence_soundness_2026-10-04.txt`;
            `mutation_report_evidence_soundness_2026-10-04.txt`, **5 of 5**
            with control A and control B. `EvidenceSoundCoverage` is a
            SUBCLASS of `PayloadAdmissibilityCoverage`, so
            `payload_coverage_model.py` is untouched and its 09-30
            transcript stays valid -- `ctz_bins`, `tr_bins`, `cross`,
            `coverage_pct()` and the class census are all checked
            identical on a shared 500-sample run.
            `raise_on_unsound_closure=True` raises `UnsoundClosure`, an
            `AssertionError` like `IllegalPayload`, so one `except`
            catches both kinds of bad evidence -- the symmetry the item
            asked for. **And the item was smaller than what it found:**
            POPULATION-unsound (structural, no admissible byte reaches
            the bin, unfixable by stimulus) and RUN-unsound (the bin was
            hit and nothing admissible hit it) are different properties,
            and 10-03 measured only the first. `0x40` closes
            `transitions` bin 3 -- which has **83 admissible witnesses it
            did not use** -- and `g_first` bin 7, which has none: one
            payload, two verdicts, **two different remedies**. On an
            exhaustive legal run F7 now reports cardinality **100.00 %
            (16/16)** against sound **93.75 % (15/16)**, and
            `sign_off()` refuses while naming which of three grounds
            applies. Two faults of the session recorded rather than
            fixed quietly: the witness search was wrong in its first
            form (ranged over the exclusion SET rather than the
            admissibility CLASS, picked `0xE0`, failed on its own false
            premise), and **mutant M1 survived the first run** because no
            check anywhere closed a bin with an *inadmissible* payload --
            the 10-03 asymmetry reintroduced on the run axis by the
            session removing it from the population axis; two checks
            added, 37/37 -> 39/39
      - [ ] **`payload_coverage_model.py`'s `classify()` still implements
            the TWO-byte rule** -- created 2026-10-02, **still deferred on
            2026-10-04 but no longer at unknown cost.** The rewiring's
            effect is now measured
            (`evidence_soundness_coverage.py` Section 6, which runs the
            identical census under both rules): which `g_first` bin is
            unsound does **not** change (bin 7 under both, so 10-03's
            headline defect is not an artefact of the rule disagreement);
            the cross drops from two unsound cells `{(7,1),(7,3)}` to one
            `{(7,3)}`, and `(7,1)` leaves the goal because the nine-byte
            rule excludes its only witnesses, **not because it became
            sound**; and the transition coverpoint loses a *bin* (5 -> 4),
            which no soundness verdict would ever have shown. A deferred
            item with a measured cost is a different thing from a deferred
            item with a reason. Original note follows: the live half of
            the item just closed. The model raises `IllegalPayload` on
            `0x00` and `0x80` and silently admits the other seven, so the
            live coverage model and vplan v10 disagree about which
            payloads may carry F7 evidence. Deliberately not touched in
            the same session: that file carries roughly thirty committed
            validations and several quote the superseded 0.78% figure, so
            rewiring it means re-deriving those too. The exact set, the
            exact goals and the closure evidence it needs are now
            committed
      - [x] **A coverage model that reports SCARCITY as well as
            cardinality -- DONE 2026-10-04**, created 2026-10-02 and
            narrowed 2026-10-03. `EvidenceSoundCoverage.scarce_bins()`
            and `.population_unsound_bins()` are methods on a LIVE
            coverage model, and `.cardinality_coverage_pct()` /
            `.sound_coverage_pct()` report the two headline numbers side
            by side so the gap between them is visible rather than
            derivable. The four-quadrant table in Section 7 is now
            computed from the live model instead of from an offline
            instrument. **Narrower than it sounds, and said so:** this is
            true of the F7 payload model only -- see the "every other
            coverage model" item above, which is the same gap one level
            out
      - [ ] **Audit every containment claim in this repository for an
            AGGREGATE on the contained side** -- created 2026-10-01 by
            today's finding, and the general form of it. The error is
            silent (an aggregate window is an ordinary number that is
            simply the wrong one) and one-directional (intersecting over
            a set shrinks the contained window, which flatters the
            container), so it cannot be caught on the containing side at
            all. Every `X contains Y` in the vplan and the benches needs
            the question "what was Y measured over?" asked of it
      - [ ] **Is `0x40` still contained at a receiver with more sampling
            lateness?** -- created 2026-10-01. It needs `p <= 1/7` and
            the worst `p` measured here is 0.1233 against 0.1429. The
            ten-byte boundary is a property of the frame format only
            while that inequality holds; one more oversample tick of
            lateness moves `0x40` into the excluded set and the exclusion
            stops being derivable from the payload alone
      - [ ] **Two redundant encodings of the sample cadence, and only one
            is load-bearing** -- created 2026-10-01 by the M2/M6 mutant
            pair. Moving the `rx_edge` strobe from 15 ticks to 14 changes
            NOTHING (0 of 37 entries); moving the `rx_os` wrap from 15 to
            14 changes EVERYTHING (37 of 37). So the state machine's bit
            boundary can move two ticks without moving one sampling
            instant. Whether the redundancy should be removed in the RTL
            or asserted as an invariant is open -- but a constant that
            can be mutated with no observable effect is a constant no
            test can be said to cover
      - [x] **Every mutant in this repository needs control B** -- created
            2026-10-01, **mechanism and audit done 2026-10-07**, and it is a
            correction to the 09-30 rule rather than an addition. 09-30
            required a positive control that the mutation ARRIVED,
            implemented as a grep for the INSERTED text. This file's own
            first M3 passed that control while being semantically inert, and
            was wrongly filed as a suite weakness. Control B -- the REPLACED
            text must be ABSENT from the mutant -- catches it instantly and
            is a property of the diff rather than of the run.
            `tools/mutation_controls.sh` now provides controls A, B and C
            (site count, reported not enforced) with a 12-case self-test that
            forces every verdict it can return, and
            `tools/audit_mutation_anchors.sh` applied them to all 16
            sed-injected mutants in the repository: **none is
            half-injected**, reported as the negative result it is.
            **Three rows are not what their own harness can certify**, and
            the first is the item's own answer: `phase6_crv_uart` M3 inserts
            `tx_state <= TX_IDLE;`, text that ALREADY EXISTS at
            `rtl/uart_controller.v:204`, so control A **cannot fail** on it
            and only control B certifies that mutant.
            `phase6_rx_pin_driver` M4 changes **two** sites while being
            described as one defect, and its M3 uses `0,/re/s||repl|`, an
            address-scoped substitution with an empty pattern for which no
            text-level control can be formed at all.
            `phase4_ral` is wired to the controls and verified on the real
            toolchain (5/5 killed, 0 voided), **with a positive control
            (`MC_SELFTEST=1`) that voids a deliberately half-injected row**,
            so the guard's failure path is exercised by the regression
            rather than argued for
      - [ ] **Wire the controls into the remaining harnesses, and repair the
            three rows the audit named** -- created 2026-10-07.
            `phase6_crv_uart`, `phase6_rx_pin_driver`,
            `phase4_rtl_bringup`, `phase4_uvm_milestone` and
            `phase6_bfm_equivalence` still guard with `cmp -s` or with a
            python-side `assert old in s`. The three repairs are: give
            `phase6_crv_uart` M3 an inserted text that does not already
            exist in the DUT (or accept it as OK_A_VACUOUS explicitly in its
            report), state `phase6_rx_pin_driver` M4's two sites in its
            description, and rewrite that harness's M3 with an explicit
            pattern instead of the empty-pattern form
      - [ ] **A control for the PYTHON-injected mutants** -- created
            2026-10-07. Two rows (`phase6_crv_uart` M6,
            `phase6_rx_pin_driver` M7) do their real injection in python with
            `assert old in s`, which is control B's anchor test and NOT
            control B: it checks the text was there before, not that it is
            gone after. `mc_controls_text` exists for them and nothing calls
            it yet
      - [ ] Apply the three-valued outcome axis to `phase6_crv_uart`'s
            crosses -- created 2026-09-26. Those 30 bins are all
            stimulus-side; today's cross shows the reachability structure
            lives on the OUTCOME axis, where 7 of 15 cells turned out
            unreachable because the axes are causally linked. The question
            is how many of the CRV bench's cells are illegal bins in
            disguise

### The census's first-ranked row, run — and a detection criterion that fired on the name of a file (2026-10-13)

The 2026-10-12 DUT-signal census ranked one row first among its unrun ones:
the Phase 1 FIFO bench predicts `full`/`empty` from its own `ref_model`,
which is the right pattern, and the mutant of the shape that escaped two
benches that week had never been run against it. *A PREDICTED row is a
declaration until a mutant tests it.*

**Run. 5 mutants, 5 detected, 5/5 verdicts as predicted.** The declaration
holds. But the reason is more useful than the score.

**The bench contains BOTH patterns, three lines apart, in the same task.**

```systemverilog
was_full = full;                        // the trusted read, verbatim
@(posedge clk); #1;
if (!was_full) ref_model.push_back(pushed_value);
wr_en = 1'b0;
check_flags(tag);                       // full vs ref_model.size()==DEPTH
```

The two UART benches had the first line and nothing like the last one. Here
`check_flags()` independently predicts the same flag on **every operation
that reads it**, so a desync caused by the trusted read is caught by the very
next check.

> **A trusted read is safe exactly where the same quantity is independently
> predicted at the same rate. What was wrong in the UART benches was never
> the trusted read on its own — it was a trusted read with no corresponding
> prediction.**

Which also means **TRUSTED and PREDICTED are roles of a READ, not of a
signal**, and the census's one-row-per-(file, checker, quantity) schema
cannot say that. It listed this file as PREDICTED and **missed both of its
TRUSTED reads**. Both are rows now, carrying measured verdicts. `empty` is
the worse of the two: `was_empty` gates the `rd_data` comparison as well as
the pop, so a defect there *disables a check* rather than only desyncing a
model.

**M3 does not print FAIL. It hangs.** `while (ref_model.size() > 0)
do_pop(...)` never terminates once `empty` reads high at occupancy 1, because
the pop that would drain the model is gated on the DUT's flag. A detection —
but a runner reading "no FAIL line, therefore PASS" scores it an escape, so
`TIMEOUT` is a named verdict in the runner rather than folded into either.

#### And the detection criterion fired on the name of a file

The runner's **first draft failed its own neutrality pass** — an identity
injection, byte-identical behaviour. Icarus prints `$error` as

```
ERROR: base.v:89: sync_fifo: wr_en asserted while full=1 at time 115000 ...
```

— **the source file and line number are in the transcript**. So a
transcript-diff criterion on this bench reports DETECTED for a mutant that
only changed the file's *name*, and for any mutant that shifts a line number
without changing behaviour. M1 inserts two lines above line 89 and would have
scored DETECTED on that basis alone, before the simulation did anything.

Repaired both ways — one path for every variant, and the comparison reported
twice, raw and with `dut.v:NNN:` collapsed — and then given a **positive
control that fires**: G0b inserts two comment lines above the `full`
assignment and measures `verdict=PASS, errors=0, differs_raw=True,
differs_norm=False`. The 2026-10-09 false DETECTED, demonstrated on real
output rather than argued.

This DUT is unusual in printing `$error` from inside the RTL on deliberate
protocol violations, so its *passing* baseline already carries two ERROR
lines. That is what makes the contamination visible here; it is present
wherever a transcript carries anything that is a property of the file rather
than of the behaviour.

#### A verdict sentence that was prose about a derived number

The census's closing line, `print('  No TRUSTED row is open.')`, was a
literal. Adding two TRUSTED rows made the derived count three hundred lines
above print **2** while that line still printed **0** — in the same
transcript, in the same run. Both are derived now.

> **The repository's own rule — an allowlist should state what the file
> states — applies to a verdict as much as to a list.**

Also paid down one row of the 2026-10-07 debt: this runner guards injection
with a declared **EXPECTED_SITES** count against an exact anchor, not with
`cmp -s`. A `cmp -s` guard passes when a sed meant for one site hits three.

## Notes

This checklist is updated by each automated study session as work is
completed. See `AUTOMATION_LOG.md` for the dated narrative log of what
was actually done in each session (more detail than this checklist
alone conveys).

**A pre-pass answers "did my attempts reach it" (2026-09-26).** Not "is it
reachable". A reachability pre-pass converted directly into illegal bins fired
against correct RTL 21 frames into a random run. Reachability needs three
verdicts, not two: reached, excluded *by argument*, and open — and only the
argued exclusions may be asserted. "Unreachable" is also never a property of a
bin, but of a bin and a stimulus space.

**A coverage bin licenses no implication (2026-09-26).** It records that
stimulus reached a region, not what happens there. "Beyond the measured
tolerance ⇒ an error" is false and data-dependent for this DUT, so it is
neither a bin nor an assertion. Relatedly: in every mutation row the detector
was a check, never the coverage model — every mutant filled the same bins.

**A cover can be reached for the wrong reason (2026-09-21).** The vacuity
cover written for the STATUS read-to-clear property passed on its first
run, at the earliest possible step. The witness trace showed why: this DUT
has a **synchronous** reset, so at step 0 -- before the first clock edge --
the solver may choose any register value, and `$past()` one cycle later
**reaches back across the reset boundary** and returns the pre-reset value
the design had already discarded. The cover fired on garbage. Assertions
were unaffected: every one using `$past` was already guarded by
`$past(rst_n)`. Only the covers lacked the guard, because *a cover feels
like a query and an assertion feels like an obligation* -- and it is the
same guard for the same reason. All covers are now guarded, and the runner
**fails the run if any cover is reached before step 2**.

Fifth occurrence of the verdict-vs-checking class (09-17, 09-18, 09-19,
09-20), second caught before it produced a wrong number. New sub-lesson:
**a PASS whose step number is implausible is a finding.** The tool was
truthful -- the cover really was reachable -- and the conclusion drawn from
it was wrong anyway.

**An injection guard is a measurement, and `cmp` is the wrong one
(2026-10-07).** `sed 's|A|B|'` replaces the first match on each line, so an
anchor occurring twice on one line yields a mutant carrying HALF the defect --
and `cmp -s mutant original` passes it, because the mutant does differ. The
distinction that matters is not *did the file change* but *did the replaced
text go away*, and the two faults that both leave the pattern matching the
mutant are told apart by whether the OCCURRENCE COUNT WENT DOWN: fewer means a
half-injection, the same or more means the pattern matches its own
replacement and control B is vacuous rather than failing. Writing the
self-test produced the same confusion on the first attempt, which is the
evidence that the distinction needs a count and not a judgement.

**And the audit's own first run produced twelve false findings
(2026-10-07).** It read each harness's mutant table by sourcing its
declarations; those fragments set their own `RTL`, so the sourced phase4_ral
fragment overwrote the audit's path and every subsequent row came back "the
anchor is not in the original" -- about a file that did not exist. Twelve
false findings that looked exactly like twelve real ones. 09-30's rule applies
to the auditor too: *the control has to sit where the failure enters*, and
this one was reading a variable the thing under audit could write.

**An arrival control can be two-valued, and the unguarded half scores a
missing block as SURVIVED (2026-10-09).** 10-08's arrival control was
`arrived = (blk != baselines[tc])`, where the block extractor returns `""`
when the block is absent. The BASELINE side is guarded — control A with no
block aborts the harness, which is 10-02's R0 rule. The MUTANT side is not: an
absent block differs from a present baseline, so `arrived` is True, and absent
a killer the row is scored SURVIVED **on the strength of a block that does not
exist**. The two cases conflated are *the block differs* and *there is no
block*, and the second — the stronger evidence of something being wrong — is
scored as the weaker verdict. `arrival_control.py` is three-valued (ARRIVED /
INERT / NO_OBSERVATION), keeps the retired rule as `two_valued_legacy()` so
the disagreement is **measured** (5 of 7 selftest cases, 4 of which the old
rule scored SURVIVED), and exercises every branch including both
NO_OBSERVATION sides.

**Half of a harness's detections were the suite crashing (2026-10-09).** With
the arrival control wired into `mutation_test_reachable_cross.py`, three of its
nine rows came back NO_OBSERVATION — M1, M4 and M5 make the suite raise
(`ZeroDivisionError`, `TypeError`) so it prints no verdict block at all. The
harness scored all three "DETECTED (correct)", because its rule was
`detected = (f_ is None) or (f_ > 0)` and `f_ is None` means the TOTAL line is
missing, i.e. **the suite died**. Three of six detections were the python
interpreter catching the mutant, in the same column and the same words as the
three a check caught — 10-06's misattribution, and the mirror image of 10-08's
false SURVIVED: a **false DETECTED**, reached by a mechanism other than the one
being measured. Scored honestly in both directions: a crash does mean the
mutant was not silently accepted, so these are not holes today, and the
exposure is **conditional** — if the suite is ever made to degrade gracefully
or wrapped in a `try/except`, 3 of 6 detections become silent passes and *no
row of the harness changes*. Counts are now split DETECTED_BY_CHECK against
DETECTED_BY_CRASH.

**A pattern that matches prose about a rule matches prose about a rule
(2026-10-09).** `arrival_control_census.py`'s first draft classified harnesses
on their raw source and raised F4 — "still contains a two-valued comparison" —
against the one harness that had just been wired three-valued, because that
harness's **docstring quotes the retired rule it replaced**. Same fault as
10-06's un-anchored `S-[a-f] FAILED` regex matching inside the sentence that
merely named the checks, and the inverse of 09-28: prose being detected *as*
code. In a repository whose house style is long explanatory docstrings this is
the default case. Fixed structurally — classification runs on a tokenised
stream with COMMENT and STRING dropped, an un-tokenisable file raises F5
instead of being classified on prose, and `--selftest` asserts F4 does *not*
fire on the live registry, so the prose path is a standing regression check.

### Arrival-control coverage across the mutation harnesses (2026-10-09)

Measured by `examples/phase4_uvm_milestone/arrival_control_census.py`, with a
staleness guard: a harness on disk and absent from its registry is a FAULT.

| harness | arrival control |
|---|---|
| `mutation_test_reachable_cross.py` | **THREE_VALUED** (wired 2026-10-09) |
| `mutation_test_signatures.py` | TWO_VALUED (10-08; mutant side unguarded) |
| `mutation_test_witnesses.py` | NONE |
| `mutation_test_coverage_axis.py` | NONE |
| `mutation_test_evidence_soundness.py` | NONE |
| `mutation_test_witness_soundness.py` | **THREE_VALUED** (wired 2026-10-10) |

**OPEN: 4 of 6**, 0 faults (2026-10-10). **Both python-target harnesses are now
wired**, so the cheap half of this item is done and every remaining open row
needs a uvm-python simulation per mutant — one session's worth of simulator
work rather than four sentences of backlog. The worst remaining row is
`mutation_test_signatures.py`, because TWO_VALUED is not a gap but a control
that *misreports*.

### Wiring the second harness, and what it found (2026-10-10)

`mutation_test_witness_soundness.py`, 13/13 rows as required, extractor
selftest 14/14. Reports:
`mutation_report_witness_soundness_2026-10-10.txt`,
`mutation_witness_soundness_selftest_2026-10-10.txt`.

**Provenance on the positive column, and the answer is the opposite of
10-09's.** 9 of 9 detections here are a failing check and **none** is the
interpreter, against 3 of 6 by crash in `mutation_test_reachable_cross.py`.
That is a measurement, not an assumption, and `provenance()` carries a third
branch that is a **fault** rather than a tidy-up: a non-zero exit with zero
failing checks, or exit 0 with failures in the verdict text — the 09-19/09-20
decoupling, which this repository has found live twice.

**An arrival block must not contain the verdicts.** `witness_soundness.py`
prints SECTION 8's controls with `[PASS]`/`[FAIL]` *inline* among the numbers
those controls computed, so a block cut straight out of SECTIONS 1–8 carries
verdict tokens — and an arrival control that reads a verdict token is reading
the killer it exists to be independent of. `mechanism_block()` normalises them
to `[VERDICT]`, and the harness computes arrival **both ways and reports the
disagreement** rather than asserting there is none: 2 rows, no outcome change,
because a killer outranks arrival in both. The strip is kept anyway —
independence by construction rather than by coincidence.

**Control A is now the determinism control.** It used to expect SURVIVE, which
under a three-valued rule is a tautology (a run compared against itself). The
harness runs the suite **twice** and compares the two reports, so an ARRIVED
here would mean the audited suite is nondeterministic and **every INERT in the
table is unreliable**. The "must pass unmutated" half moved into a pre-flight
abort (10-02's R0): a missing baseline block prints no rows at all.

**Two rows are not uncaught but UNOBSERVABLE, and that sharpens 10-02's
compound form.** M8b — weaken C3's threshold *and* perturb what it guards —
was specified SURVIVE on 10-03 and measures **INERT**. C3's detail string is
the typed literal `"7 of 7 — so the instrument is not hard-coded to find
exactly one"`, so the perturbed quantity is **never printed**: the mutant
reaches nothing observable, and the threshold M8a weakens was its **sole
observer**. 10-02 concluded the threshold is load-bearing; this says it is the
only load-bearing thing there is. A new M9 does the same to C1 and exists to
make the two arrival rules disagree.

**A census of the audited suite's own `check()` detail strings**, which
explains both rows and is a check rather than a note: **18 of 31 details are
typed literals**, five of the six C-controls among them — places where a
mutant changes a verdict and changes nothing in the report, so no arrival
control can see it. The guard fails *if the file improves*: derive C1's or
C3's detail and M8b/M9 become observable, and their rows must change. Reported
and not fixed, because `witness_soundness.py` owns a committed transcript.

Also recorded: M8c is KILLED while being INERT. **An assertion can observe
what the report does not.**

**A detector that knew one import alias, and the mirror of 10-09's defect
(2026-10-10).** The census caught the session using it: F3 fired —
*the registry adjudicates THREE_VALUED and the source shows NONE* — and the
registry was right. `classify_source()` matched the alias spellings it had
seen (`AC.arrival(`, `arrival_control.arrival(`); the new harness writes
`as ac`. 10-09's defect in the same function was a **false positive from
matching prose**; this is a **false negative from matching one alias**. Same
root cause three days apart: a textual pattern standing in for a structural
fact. The cheap repair — rename the new harness's alias to `AC` — would have
turned the census green while leaving it unable to read the next harness
anyone writes. Repaired structurally, as 10-09's was: the binding is read out
of the import statement with `ast`. Eight alias cases in `--selftest`,
including the comment and string paths that must *not* count and one alias
nobody has used yet; a misclassification raises a new F6.

### CRV from a UVM sequence, and a ratio with a stable denominator (2026-10-11)

Phase 6 capstone box **(a)** closed, after four consecutive sessions deferred
it in favour of measurement infrastructure. `examples/phase6_uvm_crv_uart/`
runs the constrained-random, coverage-driven UART stimulus of
`examples/phase6_crv_uart/` from a real UVM sequence against the unmodified
`rtl/uart_controller.v`: same four constraints, same rejection budget, same
30-bin model over 5 coverpoints and 2 crosses, same bin-to-stimulus steering
map. 5/5 mutants behave as required; `summarize_closure.py` 8/8 over 6 paired
seeds.

**The 13.68× speedup is a ratio with a stable denominator and an unstable
numerator.** A UVM sequence is an object that can be started again, so N seeds
× 2 policies run in one elaboration where a Verilog bench needs a separate
`vvp` per seed. In the Verilog bench's own unit — TX_DATA pushes:

| policy | pushes to closure | median | spread | CV |
|---|---|---|---|---|
| pure random | 131, 228, 272, 279, 364, 1745 | 275.5 | **13.32×** | **1.218** |
| steered | 41, 42, 44, 48, 53, 58 | 46.0 | 1.41× | 0.141 |

09-24's **steered** figure of 47 reproduces — it lands in [41, 58] across a
different language, framework and RNG, which is evidence about the *method*
rather than about two artefacts. Its **pure-random** 643 lands inside a range
13.3× wide, which says almost nothing. The ratio spans **2.26× to 42.56×**
across seeds, an 18.8× range around the single sample this file quoted.

What survives is stronger than what is lost: steering wins on *every* seed and
the distributions do not overlap (steered max 58 < random min 131), and the
steered cost is **8.7× tighter in CV**. **Coverage steering makes closure cost
predictable** — a plan can be scheduled against 46 ± 7 pushes and cannot be
scheduled against 131…1745 at all. That is the argument a single seed per
policy cannot make, because one run has no spread.

**Three defects in the new bench, each found by the measurement disagreeing
with the old one and each recorded in place.** `STEER_AFTER = 24` was ported
across without its unit — the Verilog bench counts *pushes*, the first draft
applied 24 to *sequence items*, and a burst carries 1–8 of them, so the
pure-random head start silently became 4.5× the Verilog bench's and the
measured speedup was dominated by the prefix. An off-by-one (`cov.items` set
*after* `finish_item`) reported closure at exactly 24 items for every seed —
the hand-off point — for a closure that happened during the 25th, making
steering look like it closed coverage without ever running. And
`random.Random(seed*7919 + steer)` gave the two policies *different* streams,
mixing the policy with the draw; same seed for both now, so the runs are
identical until the hand-off.

One hypothesis is recorded as **refuted** rather than deleted: the unlabelled
unit looked like the explanation and is not — the per-item and per-push
speedups agree to 1.01×, because the mean burst length is the same under both
policies and divides out. Where the unit mattered was the hand-off constant.

**And the scoreboard's own improvement had a blind spot, found by mutation
testing in the same session.** The scoreboard is fed only by the monitor and
*derives* push acceptance from observed traffic instead of being told by the
driver — which removes this repository's 09-19/09-20 coupling. But it derived
acceptance from the DUT's own `STATUS.tx_full`, so mutant **M4** (tx_full
asserting one entry early) corrupted the reference model in exactly the same
way, the two agreed, and **M4 SURVIVED**.

> **A checker that reads a DUT output as ground truth cannot detect a defect
> in that output.**

The same shape as 10-10's "a control must not read the thing it controls for",
now in the scoreboard. Repaired by making `tx_full` a *checked output*: the
burst is filled with the engine disabled, so occupancy is exactly the number
of accepted `TX_DATA` writes since the last `en=0` CTRL write, and the
scoreboard predicts `tx_full` with no help from the DUT. M4 is now killed
naming the occupancy. The prediction is claimed only inside that window — the
only window in which this bench observes `tx_full` at all — so nothing is
given up, and claiming it outside would be the 10-05 defect. **The Verilog
bench in `examples/phase6_crv_uart/` still has the same hole**, for the same
reason: its driver reads `tx_full` and enqueues on that basis. New open item.

M2 also earns a line: an inverted TX parity bit is caught by the STATUS
error-bit check and by **no data comparison at all** — the byte still arrives
correctly in loopback. That check was carried over on the argument that a
spurious error must fail the run even though no data check would notice; this
is the first time it has been shown to be the only thing between a real defect
and a green run.

### A DUT-signal census for every checker, and a control that required a defect to exist (2026-10-12)

The top-ranked open item, created the previous session out of a scoreboard
that read the DUT output it was meant to check. The rule it left behind:
**for every DUT signal a checker reads, ask whether the checker could detect
that signal being wrong; if not, predict it independently or state the blind
spot.** `tools/scoreboard_dut_signal_census.py` mechanises the census half.

**16 rows over 5 files** — 13 PREDICTED, 2 SYNC_ONLY, 1 OBSERVED_ONLY, 0
TRUSTED. Each row names the checker, the DUT-observed quantity, the role that
read plays, the **mutant that would prove the signal is checked rather than
trusted**, and whether that mutant has actually been run (7 yes, 7 no, 2
other).

**The roles are declared, not inferred.** A tool that inferred a read's role
by static dataflow would be this repository's class (v) failure, a procedure
that certifies itself. What is mechanical is the four controls that can
falsify the declaration: staleness (every row's evidence substring must still
appear verbatim in its file), completeness (every mechanically extracted DUT
read must be covered by a row), allowlist derivation, and discriminating
power.

**Completeness failed on the first run, which is what it is for.** Ten
omissions, split three ways:

* **Two were real.** The Verilog CRV bench reads `STATUS.rx_avail` to decide
  when to read `RX_DATA` and no row named it — SYNC_ONLY, exposure indirect,
  mutant never run. And the Phase 1 FIFO bench compares `rd_data` against its
  own `ref_model`, the right pattern, also unnamed.
* **Five were the tool's own defect.** The driven-pin allowlist had been
  written as a hand list *from the naming convention rather than from the
  file*, naming three signals that do not exist and missing five that do. The
  repair is not a corrected list but a **derived** one: a pin is bench-driven
  if the file assigns it. An allowlist that states what the file states cannot
  be inflated by hand to make the completeness control pass.
* **Three were a vocabulary mismatch** between rows naming `STATUS error bits
  [6:4]` and an extractor naming `frame_err`/`parity_err`/`overrun_err`. **A
  completeness control only works if the declaration and the extraction speak
  the same vocabulary.**

**The one TRUSTED row was closed the same session.** The Verilog CRV bench
read `STATUS.tx_full` and enqueued to its reference model only when that bit
was clear — the Verilog twin of the hole repaired in the uvm-python bench the
previous session, deferred that day because the file owns committed
transcripts. Measured rather than argued in both directions: **M7**
(`tx_full = tx_cnt >= 7`) **escaped** on seeds 1/3/5 with 8203/7926/7225
checks all passing, and is **detected on all three after the repair**, the
first failing check naming the occupancy. `tx_full` is now predicted from the
bench's own occupancy count during the fill phase, with the prediction's
**starting point checked rather than assumed** — a predicted occupancy that
begins from an unverified zero is a second guess — and claimed only inside
the window where the bench can observe it. Full suite: 7 mutants, 5 detected,
2 escaped, **7/7 verdicts as predicted**. Output-neutrality pass **exact**
across all 8 (seed, steer) combinations: identical outside the two
check-count lines.

> **An untaken branch is not an unused branch — it is the branch the defect
> takes.** The trusted branch is dead in every passing run (`pushes skipped =
> 0`), which is both why neutrality is exact and why the defect was invisible.
> The mutant is what brings it to life, taking it 1–2 times per run.

**And then the repair broke the census.** The discriminating-power control had
been phrased as *"the census must contain at least one TRUSTED row"*, on the
earlier argument that a census reporting itself clean has no power to find
anything. Fixing the one TRUSTED row made it fail.

> **A control must not demand that the thing it looks for still be there.**

The right question is not whether a defect is present now but whether the
census has **ever been shown to find one**. The control now requires at least
one row with a **demonstrated escape** — a mutant actually run against
pre-repair code and shown to survive it — which is a permanent property. Two
rows qualify, and they are the same defect shape found independently in two
languages, which is why the census is organised around the shape rather than
the instance. The open-TRUSTED count is now *reported* rather than required
to be non-zero, because a clean report and an unexercised control look
identical from outside, and the demonstrated-escape count is what
distinguishes them.

This is the inverse of the 2026-10-08 rule. A control with no control is
useless; so is one that cannot pass on healthy code.

---

### Session note, 2026-10-14 — two harnesses had not compiled since 2026-09-27, and nothing noticed

The session set out to pay the 2026-10-07 debt: convert the remaining
runners' injection guards from `cmp -s` ("did the file change at all") to the
declared-sites form. It paid that debt for two runners, and found something
bigger on the way to the first one.

**`examples/phase6_rx_pin_driver/run_mutation_tests.sh` has failed at
elaboration since 2026-09-27.** That day the RX pin driver was extracted into
`bfm/uart_rx_pin_bfm.v` and both benches were rewritten to instantiate it. The
commit verified both BENCH runners and reported their outputs reproducing byte
for byte. It did not touch either MUTATION runner's compile line, which still
named only the RTL and the bench. Every invocation since has died with
`Unknown module type: uart_rx_pin_bfm`, aborted at its own baseline check and
exited 1 — for **seventeen sessions**, through every one of which
`mutation_test_report_2026-09-25.txt` sat in the directory reading
`detected 7 escaped 0 voided 0`.

The baseline guard behaved exactly as designed. It refused to score rows it
could not trust. Nothing read the exit code, because nothing re-runs the
script.

> **A SUITE THAT CANNOT RUN IS INDISTINGUISHABLE FROM A SUITE NOBODY RAN.**
> Both produce no new output. Every guard this repository has added since
> 2026-09-30 sits INSIDE a harness and answers "is this verdict sound". None
> of them answers "did this harness run at all", and six consecutive sessions
> went to the first question while two harnesses sat dead.

**The second one was found by a tool, not by hand.**
`tools/harness_file_closure_audit.py` asks the compile-at-all question of
every harness in the repository, twice over: statically, by requiring every
module a bench instantiates to be defined in a `.v` file the script actually
names — which is what the omission looks like from outside, the script never
mentioning `bfm/` at all — and then by really elaborating that closure with
the pinned Icarus build, because a script can satisfy the static check and
still fail to compile. **20 harness scripts audited, 11 with a bench to
compile, 2 failing before this session and 0 after.** Both halves named
`examples/phase6_baud_error_coverage/run_mutation_tests.sh` independently.

**The verdicts are unchanged in both, line for line**, which is what makes
this measurable rather than alarming: RX-pin 7/7 detected with the same error
counts and first FAIL lines as 2026-09-25 (59, 9, 3, 14, 1, 3, 4), baud
coverage 5 detected + 1 expected escape with the same counts as 2026-09-26
(9, 1, 6, 2, 5). So the BFM extraction *was* output-neutral exactly as it
claimed — it was the harnesses' compile lines it missed.

> **Both seventeen-session-old reports were telling the truth about the RTL
> and lying about having been produced.**

**The debt itself, paid for two runners.** `tools/mutation_controls.sh` gains
`mc_require_sites`: control C **enforced** rather than reported. Each mutant
declares its site count and a row measuring a different number aborts as
`INJECTION_FAILED` instead of scoring. A reported-only control was not enough
for the reason the header now records — nothing ever reads the report back —
and the 2026-10-13 anchor audit's `OK_MULTISITE:2` row sat unstated in a
committed report for that reason. The declaration is also an **RTL regression
guard**, the half that only bites later: the anchors live in the harness and
the anchored lines live in `rtl/uart_controller.v`, so an RTL edit that
duplicates or deletes one silently changes what every mutant built on it
injects, and `cmp -s` passes that.

Two mutants now declare 2 sites (`phase6_rx_pin_driver` M4,
`phase6_baud_error_coverage` M5 — the parity anchor, on two RTL lines in
both). Fully injected, so their kills were always real; each kill names the
suite's response to a **compound** change, which the reports presented as one
defect. Declared, that is legal and stated.

Both directories' stop-bit mutant carried the same unparsable
`0,/re/s||repl|` sed — an address-scoped substitution with an empty pattern
reusing the address regex, for which no text-level control can be formed at
all. The anchor occurs exactly once in the RTL, so the scoping was inert.
Rewritten to an explicit pattern in both, each verified **byte-identical** by
`cmp`, and each now passes the full control set. That retires the one repair
the 2026-10-13 audit named — and finds its twin, which that audit missed
because the two harnesses were audited for different properties.

**And the new audit carried two faults of its own, both fixed before it was
committed.** Its instantiation regex allowed zero whitespace between the type
and the instance name, so a Verilog task call `apb_read(addr, d);` matched by
splitting the identifier itself and the audit reported eight to twenty-one
nonexistent missing modules per harness, with names one character short of
real tasks. The noise was the tell: a missing module called `whil` is a parser
bug, not a missing module — **2026-10-06's rule, that a detector can
misattribute what it measured, in a brand-new instrument.** And it passed
absolute paths to `iverilog`, so its committed transcript carried this
machine's session directory: a property of where the audit ran rather than of
what it found, which is exactly what 2026-10-13 ruled out of a transcript.

---

### Session note, 2026-10-15 — a report's date has no relation to whether it was produced, and the audit that says so is reflexive

**The 2026-10-14 item ranked first, built:** `tools/report_provenance_audit.py`,
6/6 controls, with its transcript. Plus the fourth of six `cmp -s` runner
conversions, and a re-run that turns one of the audit's own flags into a
measurement.

#### 1. The question the closure audit cannot ask

`tools/harness_file_closure_audit.py` (2026-10-14) asks whether a harness can
compile **today**. That is necessary and it is not sufficient:

> **A report carries a date in its text with no relation to whether it was
> produced. A harness that compiles tells you nothing about whether the report
> beside it describes today's harness or a version that stopped existing three
> weeks ago.**

The new audit asks two things, kept on separate axes because they fail
independently and want different fixes:

| axis | question | fix |
|---|---|---|
| **STALENESS** | is the report older than an input it depends on? | re-run the suite |
| **RE-RUN REACHABILITY** | does anything in this repository invoke the runner? | give it a caller |

Dates come from **git commit dates, not mtimes**. A fresh clone gives every
file the same mtime, so an mtime-based audit reports everything fresh on any
machine but the one that wrote it — 2026-10-13's rule about transcripts
carrying properties of where they ran, applied to the instrument instead of to
the output.

#### 2. The result, and the three shared files responsible

47 of 70 committed reports are stale on the tight closure, 46 of them beside a
live runner. The count is not the finding; the cause rollup is, and it counts
**directories** rather than reports so that one edit does not look like forty:

| directories invalidated | input | |
|---|---|---|
| 4 | `tools/mutation_controls.sh` | SHARED |
| 4 | `rtl/uart_controller.v` | SHARED |
| 3 | `bfm/uart_rx_pin_bfm.v` | SHARED |

> **The dominant pattern is not rot. It is SHARED-DEPENDENCY EDITS WITH
> PARTIAL RE-RUNS.**

The top row is **yesterday's**: 2026-10-14 edited the shared mutation-control
library and re-ran two of the suites depending on it. The `bfm/` row is the
2026-09-27 refactor that session found twice — and it reached a **third**
suite, `examples/phase4_uvm_milestone`, whose report has been stale since then
and still is.

#### 3. The per-report count cannot reach zero, which retired the first headline

Converting `examples/phase6_bfm_equivalence`'s guard and re-running it **raised**
the stale count from 45 to 47. Correctly: the runner is an input to every
report in its directory, so **repairing a harness invalidates that harness's
own older reports**, and this repository keeps superseded reports in place by
policy rather than deleting them.

> **The audit is reflexive, and a metric that a repair makes worse is a metric
> nobody will act on.**

The headline is now **per-suite**: for each directory, is its *newest* report
fresh? That number can reach zero, it does not punish keeping history, and it
is what the item actually asks. It read **6** suites with a runner and no
current report before today's re-run and **5** after — the first time this
measure has moved.

Still without a current report: `phase4_ral`, `phase4_uvm_milestone`,
`phase5_csr_formal`, `phase5_formal_uart`, `phase6_uvm_crv_uart`.

#### 4. The flag turned into a measurement: real staleness, nil consequence

`examples/phase6_bfm_equivalence` was one of the 44. Re-run today, its **eight
verdicts reproduce line for line** — 7 detected, 0 escaped, 1 void, identical
text. So the staleness was **real** (the inputs had genuinely changed under the
report) and the **consequence was nil**. That is now a stated limit of the
audit:

> **A stale report is UNVERIFIED, not wrong, and this tool cannot tell which
> until the suite is run.**

#### 5. `cmp -s` → declared sites, and a void that is now deliberate

The fourth of the six runners 2026-10-07 found guarding with a bare `cmp -s`.
Both guards are kept, because they ask different questions: `mc_require_sites`
asks of the **original** how many lines the anchor reaches and whether that is
the declared number — which fires when the file changed under the harness even
while the sed still matches *something*, the case `cmp -s` structurally cannot
see; `cmp -s` asks of the **result** whether anything changed at all. All seven
scored rows read `SITES_OK` at their declared counts (6, 2, 1, 1, 1, 1, 1).

And the declaration changed what one row **means**. Row 7,
`stop_bit_delay_dropped`, is a line-oriented sed against a two-line pattern,
kept deliberately to check that an unmatched pattern is voided rather than
scored. Until today its VOID was indistinguishable from an accidental one. It
now declares `sites=0` and the control reads `SITES_OK:0`, so it is an
**expected** void: the row tests the harness on purpose instead of by
coincidence.

#### 6. Three of the audit's own defects, recorded rather than quietly fixed

**(a) The first control asserted the wrong thing and the audit was right.**
C1 required `--asof 2026-09-28` to flag **exactly** the two dead harnesses, and
got four. 2026-10-14 never claimed they were the only two. Asserting "exactly"
would have forced either a loosened detector or a deleted row; the control now
asserts the claim that was actually made and **prints the surplus as a
finding**.

**(b) An incomplete closure under-reports, silently.** The first version
matched path literals only, so the 17 `$HERE/..` strings every mutation runner
builds its paths from resolved to nothing — it omitted
`rtl/uart_controller.v` from the dependency set of the **DUT's own mutation
tests**. Unlike a noisy detector, this one fails quiet.

**(c) A narrowing that keeps everything is not a narrowing.** The first
subject-based narrowing kept every `.sh` **and** `.py` in a directory, which
defeated itself for the python suites where the subject *is* a `.py`. The
directory closure is retained as a declared **upper bound** (52) beside the
tight headline (47), because `examples/phase2` holds six independent exercises
side by side and `alu_if`'s transcript is not invalidated by a later commit to
`alu_sva_checker.sv`.

#### 7. Methodological note

10-14: every guard asks whether a verdict is sound; none asks whether the
harness ran. **10-15: and none asks whether the report in front of you was
produced by the harness in front of you.**

Checkable rule: **a report is evidence only about the version of its inputs
that existed when it was written. Compare its date against the commit date of
every file it depends on before citing it — and prefer the per-suite question
(does this harness have a current report?) to the per-report one, because
keeping history makes the per-report count rise.**

Second rule, from §4: **a stale report is unverified, not wrong.** The one
re-run today reproduced its verdicts exactly. Reporting staleness as a defect
would have been a false DETECTED (10-09) at the level of the audit rather than
the suite.

---

### 2026-10-16 — The exit codes become load-bearing, and the first caller finds three red harnesses

`tools/run_all_harnesses.sh` (new) + `examples/phase6_uvm_crv_uart/run_mutation_tests.sh` (two fixes).

#### 1. The item 10-15 ranked third and fourth, built as one thing

10-15 measured it: **49 committed reports whose runner nothing in this
repository invokes**, six mutation runners referencing each other only in
prose, and a 10-14 failure that took **seventeen sessions** to surface
"because nothing re-runs the scripts". The companion item asked for the
provenance audit to become a test rather than a report. Both are one script:
a caller that runs every harness, reads every exit code, and runs the
provenance audit **first** with its per-suite headline enforced.

> **An exit code nobody reads is not a check. It is a number written to a
> terminal that closed.**

#### 2. Four design decisions, each paying off a fault already paid for

**(a) The manifest must cover the repository, both ways.** Every path the
stated discovery rule finds is declared `HARNESS` or `NOT_A_HARNESS` with a
reason. Undeclared → `MANIFEST_GAP`, fails. Declared but absent →
`STALE_MANIFEST`, fails. **There is no third, silent class**, because a
harness that stops being run without anything saying so is how 2026-09-27
stayed invisible for seventeen sessions. The guard caught **itself** on its
first run — the script was undeclared in its own manifest — which is the
cheapest possible demonstration that it works.

**(b) A missing tool is not a broken harness, and the difference is
declared.** Each `HARNESS` names a `requires` command; absent → `SKIP`,
counted and printed, never folded into `PASS` or `FAIL`. Inferring "tool
absent" from a crash is reading a cause off a symptom.

**(c) A ratchet, not a target.** The provenance headline is 5. Demanding 0
today would make the script fail on arrival and be switched off within a
session, so 5 is a budget that may only go **down** — and coming in *under*
it fails too, with an instruction to lower it, because a ratchet nobody
tightens sits at its starting value forever.

**(d) Deliberately no expected-fail list.** Refused in the file, with the
reason: a "known-red, don't count it" column is a green claim over a red
guard — the thing the sibling graphene repository spent the same day removing
after shipping one for twelve days. **While a harness is red, this script is
red.**

#### 3. What the first run found: 16 PASS, 1 FAIL, 7 SKIP over 24 harnesses

**(i) `phase6_uvm_crv_uart` scored four mutants OK on a toolchain that could
not run the DUT.** With cocotb absent every invocation crashed before the
testbench started, and the suite printed `mechanism: crash or timeout (no
RESULT line)` followed by `VERDICT: OK`, four times.

> **`MECH` was computed, printed, and then ignored by the line that decides
> the verdict. 10-09's rule — a verdict must name the mechanism that produced
> it — was implemented for the REPORT and not for the VERDICT, which is the
> half that counts.** Same shape as the graphene repository's 10-09 finding,
> where a sign was computed and thrown away.

Fixed twice over, because the first fix hides the second here: a mutant
required to FAIL that fails by **crashing** is now **VOID** (not detected, not
escaped, unscored, and it fails the suite) — the three-valued axis carried
open since 09-26; and a **baseline gate** copied in substance from
`phase4_ral`, **which already had one**. Under the identical missing toolchain
`phase4_ral` refused to score anything and this suite scored all four OK:
same fault, sibling suites, opposite behaviour, and the difference was one
gate that one of them happened to have.

**(ii) The declaration that prevents false FAILs would also have hidden
(i).** This bug surfaced only because the suite's prerequisite was initially
**under**-declared, so it ran where it cannot run. Now declared, it `SKIP`s.
Stated rather than smoothed over, and it generalises: **running a mutation
suite with its toolchain deliberately removed is a cheap, sharp test for
false DETECTEDs, and nothing here does that on purpose.**

**(iii) `tools/open_item_staleness_audit.py` is genuinely red** — 10 passed,
2 failed: six top-ranked open items have no adjudication entry on disk, and
six adjudication entries are **orphans** whose items have left the list.
Judgement work on the item list rather than a defect in the audit, and the
single reason the caller exits 1. Ranked first.

**(iv) `phase4_ral`'s health is UNVERIFIED, not good.** It failed on the same
under-declaration and is now a declared cocotb `SKIP`. 10-15's rule — a stale
report is unverified, not wrong — applies verbatim to a skipped one.

#### 4. Methodological note

10-14: every guard asks whether a verdict is sound; none asks whether the
harness ran. 10-15: and none asks whether the report was produced by the
harness beside it. **10-16: and none of it matters while nothing runs the
guards, because a guard that is not run is not a guard.**

Checkable rule: **every runner must have a caller that fails on its exit
code, and every file that looks like a runner must be classified as one or
explicitly not one. A set with a silent default has no members you can name.**

Second rule, from §3(i): **a verdict must be gated on the mechanism it
reports, not merely accompanied by it.** A mutant that "fails" by crashing is
unscored, and reporting it as caught is a false DETECTED with provenance
printed directly above it.

---

### 2026-10-17 — the caller is green, and clearing it found a verdict resolved on spelling

`tools/run_all_harnesses.sh` **exits 0 for the first time**: PASS 17, FAIL 0,
SKIP 7 across both chunks. The single red harness was
`tools/open_item_staleness_audit.py` (10/2), ranked first yesterday, now
**17 passed, 0 failed**.

**What clearing it required.** Six top items adjudicated against evidence —
five OPEN, one STALE (`RAL BASICS, ACTIVE/PASSIVE AGENTS, vplan v2`: RAL done
09-19, active/passive done 09-18, and the plan is at **v13**, so "a v2
revision" is a version that happened; `NO-SUCCESSOR:` all three complete) —
and the six "orphan" entries dispositioned.

**The six orphans were not one phenomenon, and the audit could not say so.**

- **Four were entries whose item left the list with no verdict**, which is
  exactly the loss `tools/open_item_adjudication.md` exists to prevent. All
  four are live work and all four are **restored to the list**, not deleted.
  The worst is the **F7 cross / `0x40` BORDERLINE** conflict, which the 10-03
  entry called "the repository's top item" and which then fell off the list
  **while three vplan revisions were written about it** — worked on
  continuously and untracked, with a reviewer's decision outstanding that
  nothing was reminding anyone to make.
- **Two were not orphans at all.** Their items are on the list under different
  wording, and the check's failure text — *"has lost its item from the list
  entirely"* — is false for both. The matcher is a 0.75 token-containment
  test, so `Wire PayloadAdmissibilityCoverage into the live UVM coverage
  collector` misses the live `(c) PayloadAdmissibilityCoverage wired into the
  live UartCoverage collector` on `wire`/`wired` and `uvm coverage
  collector`/`UartCoverage collector`. **A verdict resolved on spelling** —
  the same class as this repository's 10-01 dead-name loophole. The second
  miss is worse: **the rewording was produced by 10-14's own adjudication**, so
  this file's correct operation is what made the check fail.

`ORPHAN` is now `RETIRED` or `WORDING`, with the matching item printed beside
each `WORDING` row, a disjointness check between the categories, and four
controls — **`W3` being the load-bearing one: the wording-tolerant form must
not rescue an entry whose item is really gone.** *The split must never be able
to turn a FAIL into a PASS; it may only move a row between two reported
categories.* `W4` exists because this change's own first draft folded suffixes
over `tokens()` output, by which time `UartCoverage` is one token and the case
boundary is gone — it fixed `wire`/`wired`, left all six entries RETIRED, and
so **changed nothing the check reported**: half a repair indistinguishable
from a whole one by the check's own output.

**Two things the run found that nobody was looking for.**

1. `tools/mutation_anchor_audit_output.txt` **has been stale since 2026-10-14,
   in the flattering direction** — committed verdicts read
   `A_SKIPPED:unparsable` for `phase6_rx_pin_driver` M3 and omit
   `phase6_crv_uart` M7; both now read OK. Verified reproducible here (two
   runs byte for byte) **before** committing the better numbers, so it is not
   nondeterminism: commit `72add95` converted the RX-pin runner to the
   declared-sites guard, changed the sed expressions the anchor audit parses,
   and did not regenerate the anchor audit's transcript. A repair that changed
   what a second instrument says about the runner it repaired, with the second
   claim left on disk for three days.
2. `tools/open_item_staleness_audit.py` **had no committed transcript at
   all** — the one harness in the manifest with no claim on disk beside it,
   and it was the one gating the caller. A missing transcript is weaker than a
   stale one: nothing to go stale, nothing to compare.

**And a second adjudication pass was needed in the same session**, because
restoring four items moved the ranking head. The adjudication file's own
design note predicted it; 10-03 needed one for the same reason. **Two recorded
instances make it a rule: any session that changes the item list owes the
audit a re-adjudication before the caller can be green.** Of the four newly
top-ranked items, the useful one is `THE ONE REMAINING cmp -s RUNNER`, whose
own **count is unverified** — a plain grep finds `cmp -s` in ten runners,
including the two named as worked references, and nothing here distinguishes
`cmp -s` in a control from `cmp -s` as the verdict.

#### Methodological note

10-14: every guard asks whether a verdict is sound; none asks whether the
harness ran. 10-15: and none asks whether the report was produced by the
harness beside it. 10-16: and none of it matters while nothing runs the
guards. **10-17: and a guard that runs, and fails, can still make a claim its
mechanism does not support.**

Checkable rule: **when a check's failure message names a cause, the cause must
be measured, not inferred from the check firing.** Where two causes produce
the same failure they become two reported categories with a disjointness check
between them, and any tolerance added to tell them apart must be provably
unable to turn a failure into a pass.

### 2026-10-18 — An audit accused eleven harnesses of a fault none of them had, and the cause was a file left in /tmp by the previous session

**Entry point, and it was not the ranked-first item.** 2026-10-17 ranked the
`tx_empty` mutant first. Before taking it, the ranked items were checked
against the tree — the discipline the sibling repository spent this same
session establishing, after finding two of its own standing items asserting the
opposite of what its tree contained. `tx_empty` survived that check (no
committed mutation report mentions it, and the prediction is live in the
scoreboard). But running `tools/run_all_harnesses.sh` first, to establish the
baseline, produced something that outranked it.

**`tools/harness_file_closure_audit.py` reported `21 harness scripts audited,
0 elaborated, 11 FAILED to elaborate`, with its own controls at 2 passed / 2
failed. Every one of those verdicts was false** — and the same caller run
reports eleven of the accused scripts `PASS`, eleven lines further down the
page. Two claims contradicting each other on one screen.

The cause, measured rather than inferred:

```
$ ls -la /tmp/closure_examples_phase1_mutation_run_mutation_tests_py.sim
-rwxr-xr-x 1 nobody nogroup 21099 Oct 17 11:39 ...
$ id -un
rcw-01yjbzptk5n2oaw6cot1pa4j
$ iverilog ... -o /tmp/closure_..._py.sim rtl/... tb/...
/tmp/closure_..._py.sim: Permission denied
error: Code generator failure: -1
```

The `-o` path was a deterministic name in a namespace that outlives the
session. Yesterday's run left those files behind owned by `nobody:nogroup`;
this session could not overwrite them; and the audit reported a file-permission
error as a verdict on Verilog. `iverilog` was fine — the same command with a
fresh `-o` returns 0.

**Two defects, kept apart because they have different fixes.** (a) A
deterministic name in a shared namespace collides by construction, with
yesterday and with any concurrent session: scratch moved to a private
`mkdtemp()`. (b) The audit could not tell *this closure does not elaborate* (a
fact about the repository) from *the audit could not run an elaboration* (a
fact about the machine), so it reported the second as the first. **That is this
repository's own 2026-10-17 rule broken by one of its own tools:** when a
check's failure message names a cause, the cause must be measured, not inferred
from the check firing. Fixing (a) alone would have made the run green and left
(b) for the next environment to trip — the worse outcome, because the audit
would still have been able to make an unfounded accusation and merely would not
have made one today. So the verdict is three-valued — `True` / `False` / `ENV`
— with `ENV` on its own `RESULT` line, never folded into the harness column,
and `_is_env_failure` deliberately conservative: an unmatched message counts as
a *real* failure, so no genuine defect is ever explained away as an environment
problem.

Four new controls, and (5) is the load-bearing one: a closure **known** to
elaborate, sent to a deliberately unwritable output path, must be reported
`ENV` and must not be reported `FAILS`. A three-valued verdict whose third
value is never exercised is a comment, and this is the row that would have
caught today on the day it happened. (6) the same closure with a writable path
still elaborates, so (5) is about the path. (7) `FAILS` and `ENV` are disjoint,
so no future widening of `ENV_MARKERS` can move a real failure into the benign
column. (8) the scratch directory is session-private.

**The property was repository-wide and latent in four more harnesses.**
`tools/shared_scratch_audit.py` (new) sweeps every `.sh`/`.py` for
temp-namespace paths and classifies `PRIVATE` / `SCOPED` / `SHARED`. Against
the pre-session tree it finds **10 `SHARED` rows in 5 files**: the closure
audit's line 187, `phase6_uvm_crv_uart` line 31, `phase4_ral` line 72, and six
lines across `phase5_property_coverage`. All four newly found scripts are in
suites that `SKIP` here — cocotb and sby are both absent — so the fault was
invisible on every run to date, waiting for the first machine where those tools
exist and a previous session had been.

**The two cases needed opposite fixes, which is the part worth keeping.**
`phase6_uvm_crv_uart` and `phase4_ral` had no reason for a stable path; they
were the two mutation harnesses never given `mktemp -d` like their six
siblings, and they get one. `phase5_property_coverage` is the reverse: its
stability is **load-bearing**, because each shell is time-limited and
background jobs do not survive it, so the sweep is resumable by construction
and `run_chunk.sh` must find the same `$RESULTS` next invocation. Randomising
that path would break the feature *and* would still have passed a check that
only tests for `mktemp`. So it is **scoped by uid** — stable within a user,
distinct between users — with the reason stated in the source and *required* by
the audit, and a guard that refuses to run if the work directory exists
unwritable.

Its exposure was the worse of the two, in the direction that matters: `phase()`
begins `rm -rf "$work"`, which **fails** on a directory owned by another user,
and `report.py` then reads `$work/results.txt` — a stale results file from
another session reported as this run's results, with no error raised anywhere.
**The closure audit failed loudly and falsely; this one would have succeeded
quietly and falsely.**

**Four defects in this session's own work, all caught, all one cause.** The
closure-audit fix's first draft printed the `mkdtemp` path verbatim in control
(5)'s detail line — random suffix and all — so the transcript would have
differed on every run, which is exactly what the comment above `elaborate()`
has forbidden since 2026-10-13. Added `_redact()`; two consecutive runs are now
byte-identical, verified by `diff`. The scratch audit's first pattern required a
literal `/tmp/` **with a trailing slash**, so it found the eight `SHARED` rows
in the shell scripts and **zero** in the Python file that caused the incident,
whose spelling is `os.path.join('/tmp', ...)`. A checker that passes on the
broken tree certifies nothing, and that draft would have passed on the exact
breakage it exists for; `/tmp` is now matched as a whole path component, which
also caught `phase4_ral`'s `${TMPDIR:-/tmp}/ral_mutants` — a fourth instance
invisible to the first draft. And the throwaway script written to *verify* the
audit against the pre-fix tree used the **sibling repository's** commit hash,
got empty strings from `git show`, and printed `SHARED pre-fix: 0` for every
file — a vacuous input that read as "the audit does not work". That is the
audit's own `R3` non-vacuity check in miniature.

Across the two repositories that is **four separate instances today of a check
answering a weaker question than the one asked** — and the sibling repository
independently ranked "resolve-on-spelling" as its own dominant failure mode in
the same session.

**The ratchet fired, and the honest response was not to loosen it.**
`run_all_harnesses.sh` went to `ratchet: BROKEN`, 6 suites with a runner and no
current report against a declared budget of 5. The sixth was
`phase5_property_coverage`, which joined because **its runner was edited by
today's repair** and which cannot be re-run here. Raising
`STALE_SUITE_BUDGET` to 6 was rejected — that ratchets backwards. Instead
`phase6_baud_error_coverage`, the one suite in the list that *does* run here,
was re-run and given a current report: **5 detected, 1 expected escape
(M6, stated), 0 unexpected, 0 voided — identical to 2026-10-14**, same
per-mutant error counts (9/1/6/2/5) and same first-failing messages. The value
of that re-run is the confirmation that today's scratch-path repair moved
nothing in the bench. Both chunks of the caller are now green: **18 PASS,
0 FAIL, the 7 known SKIPs, ratchet OK.**

**And the edge that demanded that report is not real**, which is recorded in
the report itself rather than worked around.
`tools/harness_file_closure_audit.py` does not run the baud bench and cannot
change what it produces; it is an auditor that *reads* harness scripts. Two
over-reporting mechanisms put it in the closure: `callers_of()` resolves on
**basename**, so the six harnesses all named `run_mutation_tests.sh` are
reported as each other's callers — visible in the audit's own output — and the
closure treats *names the runner* as *is an input to its results*, so any tool
that enumerates harness scripts marks every harness's report stale when edited,
and adding one new such tool does the same. **Ranked first for the next
session**, with the warning that repairing it *lowers* the stale count, so
`STALE_SUITE_BUDGET` must be lowered in the same commit or the ratchet will
fail *under* budget by design.

**Checklist movement.** No Phase 4 or Phase 6 content box closes today; the
capstone remainder (b) and (c) are untouched and the `tx_empty` mutant remains
the cheapest content item, now verified live rather than assumed. What changed
is the instrument layer the content work runs on: a false accusation withdrawn,
a three-valued verdict where there was a two-valued one, a new repository-wide
guard, four latent collisions closed, and one suite given a current report.

---

## 2026-10-20 — naming is not invoking, and the dependency was a sentence

**The 2026-10-18 item ranked first is closed, and two of its own claims were
wrong.**

`tools/report_provenance_audit.py` carried two defects. The first,
`callers_of()` resolving on **basename**, is repaired by `invocations_of()`,
which requires a real invocation — an exec verb at a statement boundary, a
`path|KIND|…` manifest record (the table that drives every run here), or a
`subprocess` call — and credits a bare basename only when it is unique in the
repository. Six files share `run_mutation_tests.sh`, so a bare reference to it
now becomes a third value, `AMBIGUOUS`: reported, never credited.
`mentions_of()` keeps the old relation as the printed **upper bound**.

The second defect's mechanism was **not** the one 2026-10-18 named. That entry
attributed the false edge to the caller relation leaking into the closure.
Measured, it is simpler: `closure_for()` ran `PATH_RE` over the whole text of
every script in a directory, **comments included**. The edge that forced
2026-10-18 to re-run the baud bench is a *comment* on line 35 of that bench's
runner naming `tools/harness_file_closure_audit.py`. **40 comment-only edges
exist, 17 % of the 235 the audit built closures from.** An edge now has a
class: `CODE` is a dependency, `PROSE` is held in the DIRECTORY closure and
kept out of the tight one — demoted and still printed, never deleted, because
`tools/mutation_controls.sh` names the DUT only in prose and a naive strip
would drop the DUT from the DUT's own mutation tests.

**`STALE_SUITE_BUDGET` is NOT lowered, against the standing item's explicit
instruction.** Stale reports move 49 → 48 and the beside-a-RUNNER figure
48 → 47, but the number the ratchet reads — suites with a runner and no
current report — is **5 before and 5 after, on the same five directories**.
Control `P4` pins that equality against the budget parsed from the caller, so
the two cannot drift. And mechanism (1) turns out to be a **reporting**
defect, not a verdict one: reachability is 15 under both relations and
`AMBIGUOUS` is 0, because every sibling cross-reference here sits in a comment
and the comment fix removes the artefact on its own.

**Controls: 16 passed, 0 failed** (six existing, ten new). **Mutation tested:
6 injected, 6 detected, 0 escaped** — after `M6` escaped twice, once against
the tree and once against control `I6`'s first draft, which planted
`#  bash <runner> --list` and required the comment strip to make a difference
it does not make. The shapes the strip is load-bearing for carry a shell
operator before the verb (`| bash X`, `&& bash X`, `; bash X`), and `I6` now
plants those three *and* requires that all three would be credited unstripped.
A control that asked a weaker question than the one it was written to ask —
inside the repair for that very failure mode.

Also surfaced and left alone: three mutation suites whose closures omit the
DUT or the shared controls, and **all three absences are correct**
(`phase6_bfm_equivalence` mutates the BFM, not the DUT; `phase6_crv_uart` and
`phase6_uvm_crv_uart` carry their own controls). The first draft of control
`P3` asserted that universal and failed on them; it asserts the conditional
now — every edge a script spells in code survives into its closure.

**Checklist movement.** None. No Phase 4 or Phase 6 content box closes: the
capstone remainder (b) and (c) are untouched and the `tx_empty` mutant is
still the cheapest content item. This is the **third consecutive session in
the instrument layer**, stated plainly rather than left to pass — the
ranked-first item has been an instrument item three times running while the
content items age behind it.

---

### 2026-10-21 — the `tx_empty` mutant, and a coverage result that went the wrong way

**Ranked-first item closed, and it was a content item** — the first in four
sessions. The 2026-10-18 entry ranked *a mutant for the `tx_empty` prediction*
first deliberately, on the grounds that the three sessions before it had all
spent their ranked-first item in the instrument layer. That streak ends here.

`examples/phase6_crv_uart/run_tx_empty_mutation_tests.sh` — four mutants, four
seeds, both stimulus modes, with every row adjudicated by **which check failed
first** rather than by PASS/FAIL.

| ID | mutant | `steer=0` | `steer=1` |
|---|---|---|---|
| T1 | STATUS decode: `tx_empty` stuck CLEAR | 4/4 | 4/4 |
| T2 | STATUS decode: `tx_empty` stuck SET | 4/4 | 4/4 |
| T3 | STATUS decode: one entry EARLY | **4/4** | **2/4** |
| T4 | WIRE: one entry early (engine too) | 4/4 | 4/4 |

**Both predictions hold and neither is redundant.** T1 and T2 are caught by
*different* checks — the fill-phase check can only ever see `tx_empty` wrongly
clear, the post-push check only ever wrongly set.

**T3 is the result: the coverage-driven mode detects less than pure random.**
`burst_len` is drawn from [1, 8] at the top of `pick_config_steered` and then
overwritten with 8, 3 or 1 to chase an unhit `cov_txq` bin; the `= 1` branch
is guarded by `cov_txq[0]`, which the fill phase hits on the first burst. So
steering can only **remove** the length-1 bursts T3 needs. The coverage model
bins *empty / partial / full* and cannot see occupancy 1 as distinct from
occupancy 2–7 — **the distinction the prediction depends on is one the
coverage model has no bin for**, so closure is free to walk away from it.

**Attributability is the design, not a flourish.** `tx_empty` is read in three
places in the RTL, so mutating the **wire** (T4) is caught by the data path
and says nothing about the prediction. T1–T3 mutate the **STATUS decode
only**, so a detection is attributable; T4 is retained as the control for the
distinction and is reported NOT ATTRIBUTABLE — detected in both modes by the
burst watchdog. The RTL's own `assert(prdata[1] == tx_empty)` is inside
`ifdef FORMAL` and inert in this flow; stated because it would otherwise be a
silent confound for exactly T1–T3.

**Two defects in this session's own work, both of which would have produced a
green and confident wrong report.** (a) The first draft claimed steering
reached `burst_len = 1` *by construction*, read off the **presence** of a
branch that is guarded by an already-hit bin — *naming is not invoking* from
2026-10-20, one level down. (b) The harness was **first-failure-wins** and ran
`steer=1` only: it would have printed T3 DETECTED and hidden a 50 % escape
rate, inside the file written to measure a prediction's reach. Caught by hand,
not by a control; `run_matrix` now reports per seed and per mode.

**Checklist movement.** Phase 4/6: the `tx_empty` mutant box **closes**. The
capstone remainder (b) SVA protocol checkers and (c) `PayloadAdmissibility
Coverage` are untouched and both still need cocotb. Twelve committed mutation
reports become thirteen, and the new one is the first to carry a
**mode-by-mode** matrix rather than a single verdict.

---

### Session note — 2026-10-22: no mutant moves between modes, and two committed claims had no evidence behind them

**Ranked-first item worked:** *do the other coverage-steered bins suppress
detection too?* — re-run every mutant in `phase6_crv_uart` under both stimulus
modes, since all twelve committed reports were produced in one mode.
`phase6_uvm_crv_uart`, the item's other named suite, still needs cocotb and was
not run.

**The answer is no.** M1–M4 and M7 are 5/5 in both modes; M5 and M6 are 0/5 in
both, as predicted. The committed one-mode scores are **not** mode-conditional,
and `tx_empty`'s T3 remains the only known mode-conditional row.

**The mode comparison has a confound, and it is large.** The run loop stops at
closure, so the modes do not drive the same stimulus: `steer=0` drives **2.1× to
12.0×** more transactions over five seeds. A mutant needing a rare event is then
more likely to be caught under `steer=0` for volume alone. The control is
`+maxtx` — run `steer=0` truncated to `steer=1`'s own transaction count —
adjudicated by **which check failed**, since the truncated arm can never reach
closure and a PASS/FAIL score would mark every row detected. G2 is the positive
control on that classifier.

**Applied where the movement was observed, the 2026-10-21 result survives.** On
**both** seeds where steering escaped T3, pure random still detects it within
steer=1's own budget, caught by *post-push tx_empty agrees with occupancy*.
Volume does not explain the escapes. Not claimed: that the whole aggregate gap
is the coverage model — at equal budget pure random scores 3/4 rather than 4/4,
so the budget alone can cost a detection on a seed where steering did not
escape. The per-seed reading is load-bearing; the aggregate is not.

**M7 has never run.** Its sed carries one backslash too many and emits
`wire tx_full = (tx_cnt >= 4\x27d7);`, which is not Verilog; the runner scores
`COMPILE_ERROR` as `DETECT`. The row has read "predicted DETECT, got DETECT (as
predicted)" since 2026-10-12 with a stated reason naming a check it never
reached. Injected correctly it **is** detected 5/5 in both modes by exactly that
check, and it escapes the pre-repair bench 3/3 — so both halves of the
2026-10-12 claim are **true and were never evidenced by anything committed**.
That is the stable failure mode: a wrong claim gets corrected the next time
someone looks; a right claim with absent evidence survives every review.

**M4's stated reason is false.** It is recorded as "caught by the coverage
criterion, not by any data check"; three data checks fail first. Consequence:
**no mutant in this suite is detected by the coverage criterion alone**, so the
bench's decision to make closure a pass criterion rather than a report line
currently has no mutation evidence behind it, and has been cited as though it
had.

**The structural repair (G3).** The old runner refuses a sed that matched
*nothing* — half the guard. The other half is a sed that matched and emitted
something that is not the language. The complete guard is **the file must
change AND the result must still compile**, and a compile error is an
*injection failure*, never a detection.

**Checklist movement.** Phase 4/6: no content box closes — the mode question was
an audit of existing rows, not new coverage. The Phase 6 DUT-signal-census entry
is **annotated in place** with the M7 finding rather than rewritten. The
capstone remainder (b) SVA protocol checkers and (c) `PayloadAdmissibility
Coverage` are untouched for a fifth session; both still need cocotb. Thirteen
committed mutation reports become fifteen, and the two new ones are the first to
carry an **equal-budget control arm**.
