# UVM factory overrides: closing the Phase 4 Configuration checklist item

**Date:** 2026-09-07
**Purpose:** design notes for demonstrating real UVM factory overrides
(type and instance) on top of this repo's uvm-python toolchain, closing
the remaining half of the Phase 4 checklist item "Configuration
(`uvm_config_db`, factory overrides)" -- `progress.md` already marked
plain `UVMConfigDb.set`/`get` as demonstrated (2026-09-06, passing the
cocotb DUT handle into the environment); factory overrides specifically
were flagged as not yet demonstrated.

## 1. What a factory override is and why it matters

The UVM factory pattern's whole point is: testbench hierarchy code
(`AluEnv`, `AluAgent` in this repo) is written once, naming only base/
default component types, and a *test* can later substitute a different
concrete class for one of those types -- injecting a fault, adding
instrumentation, or swapping in an alternate implementation -- without
touching the environment/agent source at all. This is what lets one
verification environment support many different tests (error-injection
tests, coverage-focused tests, performance tests) that each need
slightly different component behavior.

UVM 1.2 (and uvm-python's port of it) exposes two override entry points:

- **Type override** (`<T>::type_id::set_type_override()` in
  SystemVerilog; `UVMComponentRegistry.set_type_override()` here):
  every future factory request for type `T`, anywhere in the hierarchy,
  is redirected to the override type.
- **Instance override** (`<T>::type_id::set_inst_override()`;
  `UVMComponentRegistry.set_inst_override()` here): only requests whose
  hierarchical instance path matches a given pattern are redirected;
  other instances of the same type elsewhere in a larger environment are
  unaffected.

## 2. A real gap found while implementing this: overrides need `create()`

Both override mechanisms only work if component creation is actually
routed through the factory -- i.e. `<Class>.type_id.create(name,
parent)` -- rather than calling the Python constructor directly
(`<Class>(name, parent)`). This repo's existing `alu_uvm_tb.py`
(2026-09-06) called constructors directly throughout `AluAgent.
build_phase` and `AluEnv.build_phase`. That was not a bug for
2026-09-06's purposes (no override was in use, so it made no observable
difference), but it would have silently defeated today's override work:
registering an override against `AluScoreboard`'s type_id would have
succeeded with no error, and then simply never been consulted, because
`AluEnv.build_phase` was never asking the factory for anything in the
first place.

**Fix (in `alu_uvm_tb.py`, applied today):** `AluAgent.build_phase` and
`AluEnv.build_phase` now create every child (`sequencer`, `driver`,
`monitor`, `agent`, `scoreboard`) via `<Class>.type_id.create(name,
parent)`. Verified this is behavior-preserving for the existing
(no-override) test: `alu_uvm_tb_sim_output_2026-09-06.txt`'s
`driven=40 valid_seen=40 result_valid_seen=40 sampled=40 checked=40
errors=0` result reproduces identically after the change (re-run this
session, not re-committed since the output is byte-for-byte the same).

This is exactly the kind of thing that trips people up in real
SystemVerilog UVM codebases too -- a factory-utils-registered class
whose containing environment never actually calls `create()` on it looks
completely correct until someone tries to override it.

## 3. Verification-timing subtlety found while writing the override tests

The first version of each override test asserted `type(self.env.
scoreboard).__name__ == "AluScoreboardOpHistogram"` immediately after
calling `super().build_phase(phase)` inside the test's own `build_phase`
override. Both failed with `self.env.scoreboard is a NoneType`, not
`AluScoreboard` -- i.e. not "the override didn't take," but "the
scoreboard doesn't exist yet at this point in the phase machine."

Root cause: UVM's build phase is a topdown traversal. A component's
`build_phase()` *constructs* its children (`self.env = AluEnv("env",
self)` inside `AluTest.build_phase`, itself calling `AluEnv.type_id.
create(...)` today); the newly constructed child's *own* `build_phase()`
(the thing that actually calls `AluScoreboard.type_id.create(...)` down
in `AluEnv.build_phase`) is invoked afterwards, when the phase machine's
topdown walk reaches that new child -- not synchronously inside the
parent's `build_phase()` call. So `self.env` exists by the time
`AluTest.build_phase` returns, but `self.env.scoreboard` does not yet.

**Fix:** moved the verification (`assert` + `uvm_report_info`) into
`connect_phase` instead, which UVM guarantees runs only after the
*entire* tree's build phase has completed (build is topdown, connect is
bottom-up, and UVM does not begin any component's connect_phase until
build_phase has finished everywhere). Both override tests pass with this
fix; the assertion is a genuine check on the override having worked, not
just an inline comment claiming it did.

## 4. Design: two override tests, not one, and why the results look identical

`alu_uvm_factory_override_common.py` defines one shared drop-in
replacement, `AluScoreboardOpHistogram(AluScoreboard)`, which delegates
all checking to the base class via `super().write_alu(item)` and adds a
per-opcode pass/fail histogram reported through a `report_phase`
override (a UVM phase not otherwise used anywhere in this repo).

Two separate test files each register one override mechanism against
this same replacement class:
`alu_uvm_factory_type_override_tb.py` (`set_type_override`, global) and
`alu_uvm_factory_inst_override_tb.py` (`set_inst_override`, path
`"uvm_test_top.env.scoreboard"`). These are two separate cocotb test
*modules* (and two separate Makefiles, each with its own `SIM_BUILD`
directory), not two `@cocotb.test()` functions in one module: `AluTest`'s
own docstring (`alu_uvm_tb.py`, 2026-09-06) already establishes that
uvm-python's `run_test()` must be called at simulation time 0, so two
independent `run_test()` calls need two independent simulation
invocations.

With only one `AluScoreboard` instance anywhere in this environment, the
two tests' *observable* results (histogram, pass/fail counts, the
confirmed override type) are identical -- stated plainly in both files'
docstrings rather than implied otherwise. The reason to include both is
to demonstrate the two distinct factory API calls correctly, which is
this session's actual checklist item; a behavioral contrast between type
and instance overrides would need a second `AluScoreboard` instance
elsewhere in a larger environment to be observable at all, which this
repo's single-scoreboard ALU testbench does not have.

## 5. Toolchain note

This session ran in a fresh container with none of 2026-09-06's
toolchain installed. Reinstalled via the exact sequence documented in
`notes/2026-09-06-uvm-python-toolchain-resolution.md`: `apt-get install
iverilog` (Icarus 12.0, vs. 2026-09-06's 10.3/12.0 -- no compatibility
issues observed), `pip install --use-pep517 python-constraint`, then
`pip install uvm-python` (which pulls in `cocotb>=2.0`), then `pip
install "cocotb<2.0"` again afterward to re-pin it (uvm-python 0.4.0 is
still incompatible with cocotb 2.x's removed `cocotb.utils.simulator`,
confirmed unchanged since 2026-09-06). Re-running the existing
(unmodified-behavior) `alu_uvm_tb.py` test first, before writing any new
code, reproduced 2026-09-06's exact result
(`driven=40 sampled=40 checked=40 errors=0`), confirming the
reinstalled toolchain matches.

## 6. Web search availability

Not needed this session -- today's work is a toolchain-internal
UVM/factory-API investigation (reading uvm-python's own installed
source, e.g. `uvm/base/uvm_registry.py`, `uvm/base/uvm_factory.py`) and
hands-on debugging, not a literature review.
