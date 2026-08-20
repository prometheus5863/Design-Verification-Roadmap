# Design & Functional Verification Roadmap

A self-study roadmap to build the skills needed for a design/functional
verification engineering role in the semiconductor industry — Verilog /
SystemVerilog, UVM-based testbenches, assertions and formal verification,
and the surrounding industry-standard digital design and verification flow.

**Owner:** Harsh Vardhan (IIT BHU, Physics — transitioning toward
semiconductor device/verification roles)
**Started:** 2026-08-21

This repo tracks daily/weekly study progress: notes, small worked examples
(HDL/SystemVerilog snippets with explanation), and a running checklist in
[`progress.md`](progress.md). [`AUTOMATION_LOG.md`](AUTOMATION_LOG.md) records
what was actually done on each automated study session.

## Why verification (not just design)

Verification engineers now significantly outnumber design engineers on most
digital ASIC/SoC teams (commonly cited ratios are 2:1 to 3:1), because
functional bugs are far more expensive to find in silicon than in
simulation. Verification is also a strong entry point for someone with a
strong physics/simulation background: it rewards precise, systematic
thinking about correctness and coverage, and — unlike layout/fab-process
roles — the whole flow (RTL, testbench, simulator) can be practiced with
free and open-source tools on a laptop, without access to a fab or
expensive commercial licenses (Icarus Verilog, Verilator, cocotb, and
student/free tiers of simulators like Questa/VCS are all viable starting
points).

## Roadmap Structure

The roadmap is organized into six phases, intended to run over roughly
5-7 months at a sustained but part-time study pace. Phases are sequential
in dependency (each builds on the previous) but phase 5 (formal) and
phase 6 (capstone) can partially overlap with the tail of phase 4.

---

### Phase 1 — Digital Logic & HDL Fundamentals (Weeks 1-4)

Goal: be fluent in combinational/sequential digital design and able to
read and write synthesizable Verilog for small blocks.

Topics:
- Number representation, Boolean algebra, combinational logic (muxes,
  encoders, adders, ALUs)
- Sequential logic: latches vs. flip-flops, FSMs (Moore/Mealy), timing
  basics (setup/hold, clock domains at a conceptual level)
- Verilog-2001 fundamentals: modules, always blocks (blocking vs.
  non-blocking assignment — a classic interview topic), synthesizable
  coding style, testbench basics (`initial`, `$monitor`, simple
  self-checking testbenches)
- Simple synchronous design exercises: counters, shift registers, a
  simple FIFO, a basic FSM (e.g. traffic light controller or UART framer)

Resources:
- Harris & Harris, *Digital Design and Computer Architecture* — chapters
  on combinational/sequential logic and HDLs (widely used undergrad text)
- Sutherland, *Verilog HDL Coding Styles* / Sunburst Design papers on
  blocking vs. non-blocking assignment pitfalls
- ASIC World Verilog tutorial (asic-world.com) — free, example-heavy
- Tool: Icarus Verilog + GTKWave for simulation/waveform viewing (free,
  installable locally)

Milestone deliverable: a small synchronous FIFO or FSM design in Verilog
with a hand-written directed testbench, simulated in Icarus Verilog with
a waveform dump reviewed in GTKWave.

---

### Phase 2 — SystemVerilog for Verification (Weeks 5-9)

Goal: move from plain Verilog to SystemVerilog's verification-specific
constructs — the language a modern testbench is actually written in.

Topics:
- SystemVerilog data types (`logic`, 2-state types, packed/unpacked
  arrays, structs, enums) and their use in testbenches vs. RTL
- Interfaces and modports (cleaning up DUT-testbench connections)
- Classes, object-oriented testbench components (transaction objects,
  generators, drivers, monitors, scoreboards) — the building blocks UVM
  is built on top of
- Randomization: `rand`/`randc`, constraint blocks, `randomize()`,
  weighted distributions (`dist`) — the core of constrained-random
  verification
- Functional coverage: `covergroup`/`coverpoint`/`cross`, coverage-driven
  verification methodology
- Basic SystemVerilog Assertions (SVA): `assert property`, immediate vs.
  concurrent assertions, simple sequence/property syntax

Resources:
- Sutherland, Bergeron, Spear et al. — "SystemVerilog for Verification"
  papers and Chris Spear's *SystemVerilog for Verification* (Springer) —
  the standard reference text for this exact transition
  (design->verification SV usage)
- ChipVerify.com — free, example-driven SystemVerilog and UVM tutorials,
  good for quick concept lookups
- IEEE 1800-2017 LRM (SystemVerilog language reference manual) as a
  precise-syntax reference once fundamentals are in place

Milestone deliverable: a self-checking, constrained-random SystemVerilog
testbench (no UVM yet) for a small DUT (e.g. a synchronous FIFO or a
simple ALU), including a scoreboard and a functional coverage model with
a coverage report.

---

### Phase 3 — Verification Methodology Fundamentals (Weeks 10-12)

Goal: understand *why* testbenches are structured the way they are before
adopting UVM's specific class library — this phase is deliberately
inserted before UVM so UVM's structure doesn't feel like arbitrary
boilerplate.

Topics:
- Layered testbench architecture: transactors, drivers, monitors,
  agents, scoreboards, environment, test — and why each layer exists
  (reuse, encapsulation of protocol knowledge, separation of stimulus
  from checking)
- TLM (transaction-level modeling) basics: why testbenches communicate
  via transactions rather than pins/cycles at the top level
- The verification plan: mapping DUT features -> checks -> coverage
  goals -> test scenarios (a real verification plan document, not just
  code)
- Directed vs. constrained-random vs. coverage-driven verification —
  trade-offs and when each is used in practice

Resources:
- Bergeron, *Writing Testbenches using SystemVerilog* — canonical text on
  testbench architecture and methodology reasoning
- Accellera UVM/VMM methodology whitepapers (background on why the
  industry converged on a layered, transaction-based methodology)

Milestone deliverable: a written verification plan (markdown, in this
repo) for a moderately complex DUT (e.g. a simple APB/AHB-lite
peripheral or a UART), listing features, checks, and coverage goals —
used directly as the spec for the Phase 4 UVM testbench.

---

### Phase 4 — UVM (Universal Verification Methodology) (Weeks 13-20)

Goal: build a working UVM testbench for a non-trivial DUT, the single
most industry-standard skill for a verification engineer job.

Topics:
- UVM class hierarchy: `uvm_object`, `uvm_component`, phases
  (build/connect/run/etc.), the factory pattern and why it matters for
  test reuse
- UVM TLM ports/exports/analysis ports, sequences and sequencers
  (`uvm_sequence`, `uvm_sequence_item`), drivers, monitors, agents
  (active/passive)
- The UVM environment, virtual sequences/sequencers for multi-interface
  DUTs, scoreboards using TLM analysis ports
- Configuration: `uvm_config_db`, factory overrides, building
  test-specific variants without duplicating environment code
- Register Abstraction Layer (RAL) basics — enough to understand what
  it's for, even if not deeply mastered in this pass

Resources:
- Accellera UVM 1.2/2.0 User Guide and Class Reference (the official
  spec — dense but authoritative)
- ChipVerify UVM tutorial series (practical, incremental UVM examples)
- Ray Salemi, *A Practical Guide to Adopting the Universal Verification
  Methodology (UVM)* — a widely recommended hands-on UVM book
- Open-source UVM-1.2 library (Accellera) for simulation with
  Verilator/Questa student edition or a free simulator with UVM support

Milestone deliverable: a full UVM testbench (agent, sequencer, driver,
monitor, scoreboard, coverage model, at least 2-3 sequences/tests) for
the DUT verification-planned in Phase 3, run to a stated functional
coverage target.

---

### Phase 5 — Assertions & Formal Verification (Weeks 21-24, overlaps Phase 4 tail)

Goal: understand assertion-based verification (ABV) and formal property
verification as a complement to simulation-based UVM testing — an area
increasingly expected of verification engineers, not just a specialist
niche.

Topics:
- SVA in depth: sequences, properties, local variables in sequences,
  `assume`/`assert`/`cover`, and how assertions get reused between
  simulation and formal
- Formal verification concepts: model checking basics, bounded vs.
  unbounded proofs, state-space explosion and why formal doesn't scale to
  full-chip
- Practical formal use cases: connectivity checking, X-propagation
  checking, CSR (control/status register) verification, deadlock/livelock
  checking — the use cases formal is actually deployed for in industry,
  as opposed to full-design equivalence proofs
- Hands-on with a free/open formal tool (e.g. SymbiYosys with Yosys, for
  small-scale formal property checking) to get real signal on how a
  formal flow runs, even though industry formal tools (JasperGold, VC
  Formal) are proprietary

Resources:
- Accellera SVA-based Assertion-Based Verification whitepapers
- SymbiYosys documentation/tutorials (open-source formal flow)
- Foster, Krolnik, Lacey, *Assertion-Based Design* — reference text on ABV

Milestone deliverable: an SVA property suite for the Phase 4 DUT (e.g.
protocol-compliance assertions), plus one small formal property check
run through SymbiYosys with a documented result (pass/counterexample).

---

### Phase 6 — Industry Flow & Capstone Project (Weeks 25-28+)

Goal: consolidate everything into one substantial, portfolio-quality
project that demonstrates the full flow end-to-end, plus exposure to
the surrounding industry toolchain/flow context.

Topics:
- Overview of the surrounding flow a verification engineer touches:
  linting (design/CDC lint), simulation regression infrastructure,
  coverage closure/merge across regressions, waveform debug workflow,
  bug tracking/triage process
- Clock-domain-crossing (CDC) verification basics — a common
  interview/job topic even for functional verification roles
- Interview-prep pass: common verification interview question patterns
  (blocking vs non-blocking, FIFO/CDC design, coverage vs. assertions,
  "how would you verify X" open-ended design questions)

Capstone project (concrete idea): a full UVM-based verification
environment for a small but "real" DUT with multiple interacting
interfaces — e.g. **an AXI-Lite (or APB) register-mapped peripheral with
an interrupt and a simple FIFO-buffered data path** (concretely: a UART
or SPI controller wrapped with a register interface). This is
deliberately chosen to be complex enough to need a virtual
sequencer/multiple agents and a real verification plan, but scoped small
enough to actually finish. Deliverables: verification plan, full UVM
environment, SVA protocol checkers, functional coverage report with a
stated closure target, and a short written summary of methodology
choices and results (suitable to show in interviews/portfolio).

---

## Progress Tracking

See [`progress.md`](progress.md) for the live checklist of milestone
status. [`AUTOMATION_LOG.md`](AUTOMATION_LOG.md) has a dated log of what
was actually studied/built in each automated session, so future sessions
(with no memory of prior ones) can pick up in the right place.

## Tools used in this roadmap (all free/open where possible)

- **Icarus Verilog** + **GTKWave** — Verilog/SystemVerilog simulation and
  waveform viewing (Phases 1-2)
- **Verilator** — fast open-source simulator, useful for larger testbenches
- **cocotb** — optional Python-based testbench alternative for quick
  experimentation outside SV/UVM
- **Accellera UVM 1.2 library** — the open-source UVM class library
  (Phase 4+)
- **SymbiYosys / Yosys** — open-source formal verification flow (Phase 5)
