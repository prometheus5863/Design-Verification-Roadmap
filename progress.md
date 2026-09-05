# Progress Checklist

Status legend: `[ ]` not started, `[~]` in progress, `[x]` done.

Last updated: 2026-09-05

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
- [ ] UVM class hierarchy, phases, factory pattern
- [ ] TLM ports/exports/analysis ports, sequences/sequencers
- [ ] Drivers, monitors, active/passive agents
- [ ] UVM environment, virtual sequencers, scoreboards via analysis ports
- [ ] Configuration (`uvm_config_db`, factory overrides)
- [ ] RAL basics (overview level)
- [ ] Milestone: full UVM testbench w/ 2-3 sequences/tests + coverage target

## Phase 5 — Assertions & Formal Verification
- [ ] SVA in depth (sequences, properties, local variables, assume/assert/cover)
- [ ] Formal verification concepts (model checking, bounded vs. unbounded)
- [ ] Practical formal use cases (connectivity, X-prop, CSR, deadlock)
- [ ] Hands-on SymbiYosys/Yosys exercise
- [ ] Milestone: SVA property suite + one formal property check w/ documented result

## Phase 6 — Industry Flow & Capstone
- [ ] Surrounding flow overview (lint, regression infra, coverage merge,
      waveform debug, bug triage)
- [ ] CDC verification basics
- [ ] Interview-prep pass (common question patterns)
- [ ] Capstone: UVM verification environment for register-mapped
      peripheral (UART/SPI controller with interrupt + FIFO datapath)
      - [~] Verification plan written -- early draft completed in Phase 3
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
