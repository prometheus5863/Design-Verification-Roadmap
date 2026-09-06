# 2026-09-06 -- Resolving the Phase 4 UVM toolchain blocker: uvm-python

## 1. The standing blocker

Every session since 2026-08-25 that touched SystemVerilog classes on this
repo's pinned Icarus Verilog build (10.3 originally, 12.0 -- the Ubuntu
`apt` default -- from 2026-08-28 onward once `tools/setup_iverilog.sh`'s
pin stopped being sourced every session) found the same wall:

- No `mailbox` (2026-08-25, `notes/2026-08-25-oop-testbench-components.md`)
- No `virtual <interface>` class member (same date)
- Class handles cannot be passed as `input`/`ref` args, or stored in
  queues/arrays (same date)
- Native `randomize()`/`constraint`/`dist` unavailable (2026-08-26)
- Native `covergroup` unavailable (2026-08-26)
- Native `assert property` (immediate and concurrent) unavailable
  (2026-08-28)

`notes/2026-08-31-layered-testbench-architecture-and-tlm-basics.md`
(Section 4) connected these into one explanation: this Icarus build
cannot express a driver or monitor as a real class object at all, only
as procedural code -- which is exactly what a UVM environment needs
(`uvm_driver`, `uvm_monitor`, `uvm_sequencer`, TLM ports between real
component objects). Every Phase 2/3 "not yet covered" list since then
repeated the same flag: Phase 4 cannot begin on this toolchain without a
resolution, and that resolution should happen *before* Phase 4's coding
milestones, not be discovered mid-Phase-4.

## 2. Options considered

**Web search was available and used this session** (all fetches below
succeeded; no access failures to record, unlike several prior sessions).

1. **A different HDL simulator that supports SV classes/UVM natively.**
   The realistic free/open options are Verilator (no classes at all --
   it's a 2-state synthesizable-subset simulator, worse than Icarus for
   this purpose) or a commercial simulator (Questa/VCS/Xcelium), which
   requires a license this environment doesn't have. Not pursued further
   -- rejected on availability grounds, not evaluated in depth.

2. **cocotb** (https://docs.cocotb.org/en/v1.1/introduction.html) -- a
   mature, real, widely-used-in-industry Python coroutine-based
   verification framework that drives any VPI/VHPI-capable simulator
   (Icarus included) from Python instead of SystemVerilog. This
   completely sidesteps the "Icarus can't compile SV classes" problem,
   since the testbench is plain Python -- but by itself, cocotb is *not*
   UVM: it has no factory, no phasing, no `uvm_component`/`uvm_sequence`
   hierarchy. Using bare cocotb would satisfy "a real class-based
   driver/monitor" but not the actual Phase 4 checklist items (UVM class
   hierarchy, phases, factory pattern, TLM ports/exports specifically in
   the UVM sense).

3. **uvm-python** (https://github.com/tpoikela/uvm-python,
   PyPI `uvm-python`, current release 0.4.0) -- "a Python and cocotb-based
   port of the SystemVerilog Universal Verification Methodology (UVM)
   1.2." This is the actual solution: a from-scratch reimplementation of
   the UVM 1.2 base-class library in pure Python on top of cocotb, with
   an API deliberately mirroring SV-UVM's (`UVMComponent`, `UVMDriver`,
   `UVMMonitor`, `UVMScoreboard`, `UVMAgent`, `UVMEnv`, `UVMTest`,
   `UVMSequence`/`UVMSequenceItem`/`UVMSequencer`, `UVMAnalysisPort`,
   `UVMConfigDb`, the standard 12-phase schedule, and factory
   registration via `uvm_component_utils`/`uvm_object_utils`). Its own
   documentation states Icarus Verilog is "fully supported and
   recommended" (Verilator is supported with some limitations). This
   directly resolves the blocker: it provides genuine UVM semantics
   (phasing, factory, TLM, hierarchy) using a language (Python) that
   *can* express real classes/handles on this exact Icarus build, instead
   of requiring SystemVerilog class support Icarus doesn't have.

Decision: adopt uvm-python for Phase 4, reusing the existing `alu_dut`
(`examples/phase2/alu_if_and_dut.sv`) as the target DUT for this session's
proof-of-concept, exactly as Phase 2/3 reused it repeatedly rather than
introducing a new DUT each time.

## 3. Installation notes (a genuine, reproducible finding)

`pip install uvm-python` fails out of the box in this environment:

```
Building wheel for python-constraint (setup.py) ... error
...
AttributeError: install_layout. Did you mean: 'install_platlib'?
```

This is `python-constraint` (a `cocotb-coverage` dependency) using
`setuptools`'s legacy `distutils`-based `install_lib` command, which
breaks under the modern `setuptools` shipped with this Python 3.11
environment. Fix: install `python-constraint` first with
`pip install python-constraint --use-pep517`, which builds it via its
`pyproject.toml` instead of legacy `setup.py`, then `pip install
uvm-python` succeeds picking up the already-built wheel.

More significantly: uvm-python 0.4.0's own `import uvm` fails against
the *latest* cocotb (2.1.0, what `pip install cocotb` gets by default as
of this session):

```
ImportError: cannot import name 'simulator' from 'cocotb.utils'
```

`cocotb.utils.simulator` was removed in the cocotb 2.x rewrite; uvm-python
0.4.0 (per its PyPI metadata, `cocotb>=1.9.2` with no upper bound) has not
been updated for it. Fix: pin `cocotb<2.0` (this session used 1.9.2, the
last 1.x release). Noting this explicitly since it is exactly the kind of
toolchain-version trap this repo's automation has hit before (the Icarus
10.3-vs-12.0 drift documented across several 2026-08 sessions) and future
sessions re-running `examples/phase4_uvm_python/Makefile` should install
`cocotb<2.0` before `uvm-python`, not just `pip install uvm-python` and
assume it pulls a compatible cocotb. `cocotb-coverage` (a further
uvm-python dependency) in turn wants `cocotb>=2.0` per its own metadata --
a three-way version conflict pip resolves by installing 1.9.2 anyway with
a printed warning; this worked for the scope exercised this session
(no `cocotb-coverage` functional-coverage APIs used yet) but is flagged
as a possible future incompatibility if a later session's Phase 4 work
needs `cocotb-coverage`'s covergroup-equivalent.

## 4. Proof-of-concept: real UVM environment for `alu_dut`

Built in `examples/phase4_uvm_python/` (see `alu_uvm_tb.py`'s module
docstring for the full component-by-component description). Summary of
what is now demonstrably real, not hand-rolled, on this toolchain for the
first time:

- `AluSeqItem(UVMSequenceItem)` -- a genuine transaction class, registered
  with the factory via `uvm_object_utils`
- `AluRandomSequence(UVMSequence)` -- generates 40 randomized transactions
  through the actual `start_item`/`finish_item` sequencer handshake
- `AluDriver(UVMDriver)` / `UVMSequencer` -- real pull-mode
  `seq_item_port.get_next_item()`/`item_done()` protocol driving
  `alu_dut`'s ports
- `AluMonitor(UVMMonitor)` -- samples DUT activity and broadcasts over a
  real `UVMAnalysisPort` (the actual TLM broadcast primitive that
  `notes/2026-08-31-*.md` Section 3 could only describe conceptually,
  for lack of a `mailbox`/TLM channel type on this Icarus build)
- `AluScoreboard(UVMScoreboard)` -- receives via a real analysis
  export/`write_alu()` callback (declared with `uvm_analysis_imp_decl`,
  the same idiom as SV-UVM's `\`uvm_analysis_imp_decl` macro), checking
  against an independently-written Python reference model
- `AluAgent(UVMAgent)` / `AluEnv(UVMEnv)` / `AluTest(UVMTest)` -- real
  component hierarchy, connected in `connect_phase`
- Factory registration throughout via `uvm_component_utils`/
  `uvm_object_utils`
- The standard phase machine (`build_phase`, `connect_phase`, `run_phase`,
  objection-based termination via `phase.raise_objection`/
  `drop_objection`) -- confirmed via the `UVM_INFO ... PH_READY_TO_END`
  trace lines for all 13 phases in the run log

Final result (`alu_uvm_tb_sim_output_2026-09-06.txt`):
`driven=40 valid_seen=40 result_valid_seen=40 sampled=40 checked=40
errors=0` -- all 40 randomized transactions driven, correctly correlated
through the DUT's 1-cycle pipeline latency by the monitor, and checked
against the reference model with zero mismatches. `TESTS=1 PASS=1
FAIL=0`.

### Two genuine bugs found and fixed while building this (kept in the
code's comments, not silently fixed):

1. **UVM run-phase timing constraint.** uvm-python enforces (as real
   SV-UVM does) that `run_test()` must be invoked at simulation time 0
   with no preceding delay -- `UVM_FATAL ... RUNPHSTIME` on the first
   attempt, which had reset/clock bring-up happening in the cocotb test
   function *before* `run_test()`. Fixed by moving DUT reset into
   `AluTest.run_phase` itself (see that class's docstring), since reset
   has to happen after the phase machine has already started, not
   before it.

2. **Driver/monitor edge-alignment race dropping transaction 0.** First
   working version showed `driven=40` but `valid_seen=39`/`sampled=39` --
   one transaction silently vanishing with zero scoreboard errors on the
   rest (so this was a monitor/driver timing bug, not an ALU logic bug).
   Root-caused via added instrumentation (driven/valid_seen/
   result_valid_seen/sampled counters, then per-transaction sim-time
   prints) to: the *first* transaction's `valid` assertion happened to
   land on the exact same simulation timestep as a `RisingEdge`, because
   `AluTest.run_phase`'s reset sequence calls `seq.start()` immediately
   after its last `await RisingEdge`, with no intervening delay. Since
   the monitor's own sampling coroutine is also scheduled on that same
   `RisingEdge`, the two coroutines race for scheduling order on that
   specific edge, and whichever runs first determines whether the
   monitor sees the old (`valid=0`) or new (`valid=1`) value --
   nondeterministically dropping transaction 0. Every subsequent
   transaction was safe because `get_next_item()` for it unblocks at a
   `FallingEdge` instant (the previous transaction's deassertion point),
   half a clock period away from the monitor's `RisingEdge` sampling,
   with no race. Fixed by making the driver explicitly
   `await FallingEdge(dut.clk)` *every* iteration before driving
   (including the first), rather than relying on incidental timing to
   put every assertion a safe half-cycle away from the monitor's sampling
   point. This is a real, generalizable lesson: a cocotb driver that pulls
   its first item immediately upon a reset-sequence's last clock edge
   (rather than synchronizing to its own clean edge first) is not safe
   against a monitor sampling on the opposite edge type, even though
   later back-to-back transactions look safe by construction.

## 5. What this resolves vs. what remains

This resolves the toolchain question raised since 2026-08-25 with a real,
running artifact, not just a decision on paper: Phase 4's UVM class
hierarchy, phasing, and factory-pattern checklist items now have a genuine
demonstration to point to, on the exact simulator (Icarus) this repo has
used throughout.

Not yet covered (left for future sessions, consistent with this repo's
practice of scoping one session's work honestly rather than overclaiming):

- `UVMSequencer`/TLM ports item is only partially exercised here (the
  pull-mode driver/sequencer handshake and one analysis port); virtual
  sequencers and multiple parallel sequences are not yet demonstrated
- `UVMConfigDb`/factory *overrides* (as opposed to plain `set`/`get` and
  default factory registration) are not yet demonstrated
- RAL (register abstraction layer) basics -- uvm-python claims partial
  support (frontdoor read/write; register-layer built-in sequences only
  partially implemented per its own docs) but nothing here exercises it
  yet
- The `cocotb-coverage`/`cocotb>=2.0` version conflict noted in Section 3
  above is unresolved; a future session needing functional-coverage
  primitives under uvm-python should re-check compatibility rather than
  assume the current pin still works
- This proof-of-concept reuses the Phase 2 ALU DUT for continuity with
  existing repo content; the actual Phase 4 milestone (a full UVM
  testbench w/ 2-3 sequences/tests + coverage target, per the README)
  will need a larger DUT and has not been attempted yet
- `alu_dut`'s `flags` packed-struct output is read via raw integer
  bit-slicing in the monitor (`(flags >> 2) & 1` etc.) rather than a
  typed accessor -- cocotb reads Icarus struct ports as flat vectors, so
  this is the correct approach here, but it is worth remembering as a
  pattern (not re-deriving it) for any future struct-typed DUT port

## Sources

- uvm-python (GitHub): https://github.com/tpoikela/uvm-python
- cocotb 1.1 introduction: https://docs.cocotb.org/en/v1.1/introduction.html
- cocotb simulator support matrix (for context on Icarus/Verilator
  support tiers): https://github.com/cocotb/cocotb/blob/v1.8.1/documentation/source/simulator_support.rst
- "Cocotb in modern functional verification" (background on cocotb's role
  vs. SV-UVM in industry): https://wydawnictwo.pan.pl/index.php/ijet/article/download/1135/910
- "Analyzing AES Verification: A Comparative Study of UVM and Cocotb
  Approaches" (IEEE): https://ieeexplore.ieee.org/document/10649439/
