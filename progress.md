# Progress Checklist

Status legend: `[ ]` not started, `[~]` in progress, `[x]` done.

Last updated: 2026-08-25

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
- [ ] Randomization (`rand`/`randc`, constraints, `randomize()`, `dist`)
- [ ] Functional coverage (`covergroup`/`coverpoint`/`cross`)
- [ ] Basic SVA (`assert property`, immediate vs. concurrent)
- [ ] Milestone: constrained-random SV testbench w/ scoreboard + coverage
      for a small DUT

## Phase 3 — Verification Methodology Fundamentals
- [ ] Layered testbench architecture concepts
- [ ] TLM basics
- [ ] Verification planning (features -> checks -> coverage -> tests)
- [ ] Directed vs. constrained-random vs. coverage-driven trade-offs
- [ ] Milestone: written verification plan for a chosen DUT

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
      - [ ] Verification plan written
      - [ ] Full UVM environment built
      - [ ] SVA protocol checkers added
      - [ ] Functional coverage report + closure target stated
      - [ ] Written summary of methodology/results

## Notes

This checklist is updated by each automated study session as work is
completed. See `AUTOMATION_LOG.md` for the dated narrative log of what
was actually done in each session (more detail than this checklist
alone conveys).
