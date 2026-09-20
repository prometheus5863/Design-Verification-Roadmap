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
- [~] Practical formal use cases (connectivity, X-prop, CSR, deadlock)
      -- surveyed 2026-09-20 with a verdict on each for this DUT (notes
      Section 5). **CSR properties on the six-register map are the named
      next target**; X-prop and liveness are out of scope for this
      toolchain, connectivity is not applicable to a single peripheral
- [x] Hands-on SymbiYosys/Yosys exercise -- **done 2026-09-20**.
      `tools/setup_formal.sh` installs Yosys 0.69 + SymbiYosys + z3 without
      root via the YoWASP WASM builds; `examples/phase5_formal_uart/`
      runs bmc / prove / cover plus a ten-run mutation stage
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
      - [ ] Functional coverage report + closure target stated
      - [ ] Written summary of methodology/results

## Notes

This checklist is updated by each automated study session as work is
completed. See `AUTOMATION_LOG.md` for the dated narrative log of what
was actually done in each session (more detail than this checklist
alone conveys).
