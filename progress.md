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
      - [ ] Full UVM environment built
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
      - [ ] A coverpoint on the driven baud ERROR -- created 2026-09-25 by
            the v3 plan revision. `cp_baud_div`'s corner bins measure the
            divisor REGISTER, not the tolerance; F7 needs bins on
            {0, within +/-2%, within +/-4%, beyond the limit} and a
            closure criterion over them. The stimulus now exists; the
            coverage model does not
      - [ ] Fold the independent-timebase driver into the Phase 4 UVM
            environment as a real `uvm_driver` -- created 2026-09-25. The
            serial agent there drives RX at the DUT's own rate, so the UVM
            environment still cannot reach what this bench reaches

## Notes

This checklist is updated by each automated study session as work is
completed. See `AUTOMATION_LOG.md` for the dated narrative log of what
was actually done in each session (more detail than this checklist
alone conveys).

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
