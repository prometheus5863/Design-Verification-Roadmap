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
            **(a)** constrained-random rather than directed stimulus
            inside the UVM environment (the CRV machinery exists in
            `examples/phase6_crv_uart/` in plain Verilog and has never
            been driven from a UVM sequence);
            **(b)** the SVA protocol checkers of the next box, bound into
            that environment rather than standing alone;
            **(c)** `PayloadAdmissibilityCoverage` wired into the live
            `UartCoverage` collector (its own open item since 09-30);
            **(d)** the written methodology summary of the last box.
            Each is separately unchecked, so this box is a ROLL-UP of
            them and should be checked last, not first
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
            this repository** -- created 2026-10-03. Today's audit covers
            F7's three coverpoints only. The fourth quadrant,
            abundant-and-unsound, is empty in F7's data and is **not**
            claimed impossible: it needs a bin all of whose many
            witnesses are borderline, and F7's population has only two
            borderline bytes. A model with a wider borderline band would
            have one, **and no scarcity scan at any threshold would find
            it** -- so this is not subsumed by the witness-count item
      - [ ] **Give the BORDERLINE case a mechanism, as `illegal_bins`
            gives the inadmissible case one** -- created 2026-10-03.
            v8's `illegal_bins` raises on an inadmissible witness; there
            is nothing that reports a bin whose only witnesses are
            borderline, which is why bin 7 stayed invisible for four
            revisions while the mechanism for its sibling bins worked
      - [ ] **`payload_coverage_model.py`'s `classify()` still implements
            the TWO-byte rule** -- created 2026-10-02, and the live half
            of the item just closed. The model raises `IllegalPayload` on
            `0x00` and `0x80` and silently admits the other seven, so the
            live coverage model and vplan v10 disagree about which
            payloads may carry F7 evidence. Deliberately not touched in
            the same session: that file carries roughly thirty committed
            validations and several quote the superseded 0.78% figure, so
            rewiring it means re-deriving those too. The exact set, the
            exact goals and the closure evidence it needs are now
            committed
      - [ ] **A coverage model that reports SCARCITY as well as
            cardinality** -- created 2026-10-02, **narrowed 2026-10-03**
            rather than closed. Today's instrument computes witness
            counts for F7's three coverpoints, so the question is
            answered there; no live coverage model in this repository
            *reports* either scarcity or soundness, which is the half
            that remains
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
      - [ ] **Every mutant in this repository needs control B** -- created
            2026-10-01, and it is a correction to the 09-30 rule rather
            than an addition. 09-30 required a positive control that the
            mutation ARRIVED, implemented as a grep for the INSERTED
            text. This file's own first M3 passed that control while
            being semantically inert, and was wrongly filed as a suite
            weakness. Control B -- the REPLACED text must be ABSENT from
            the mutant -- catches it instantly and is a property of the
            diff rather than of the run. The existing mutation harnesses
            (`phase4_ral`, `phase4_rtl_bringup`, `phase4_uvm_milestone`,
            `phase6_bfm_equivalence`) have control A only
      - [ ] Apply the three-valued outcome axis to `phase6_crv_uart`'s
            crosses -- created 2026-09-26. Those 30 bins are all
            stimulus-side; today's cross shows the reachability structure
            lives on the OUTCOME axis, where 7 of 15 cells turned out
            unreachable because the axes are causally linked. The question
            is how many of the CRV bench's cells are illegal bins in
            disguise

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
