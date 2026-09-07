"""
alu_uvm_factory_type_override_tb.py -- Phase 4 checklist item:
"Configuration (uvm_config_db, factory overrides)". alu_uvm_tb.py
(2026-09-06) already demonstrated plain UVMConfigDb.set/get (passing the
cocotb DUT handle into the environment); factory *overrides* specifically
were flagged there as not yet demonstrated. This file (together with
alu_uvm_factory_inst_override_tb.py) closes that gap.

Demonstrates a *type* override: `<T>::type_id::set_type_override()` in
SystemVerilog UVM 1.2 terms, `UVMComponentRegistry.set_type_override`
here. Every future request the factory receives to create an
AluScoreboard, anywhere in the hierarchy, is redirected to
AluScoreboardOpHistogram (alu_uvm_factory_override_common.py) instead --
registered in AluTestTypeOverride.build_phase *before* calling
super().build_phase(), which is what actually constructs
AluEnv -> AluScoreboard.type_id.create(...).

This relies on a prerequisite fix made in alu_uvm_tb.py today:
AluAgent.build_phase/AluEnv.build_phase now create their children via
`<Class>.type_id.create(name, parent)` instead of calling the Python
constructor directly. A direct constructor call bypasses the factory
entirely and makes any registered override silently do nothing -- see
that file's build_phase comments for the full explanation. Neither
AluEnv nor AluAgent's source is touched by this file at all; the
substitution happens purely through the override registration below,
which is the entire point of the factory pattern.

Run with: `make -f Makefile.factory_type_override` in this directory.
"""

import cocotb
from cocotb.clock import Clock
from uvm import run_test, uvm_component_utils
from uvm.base.uvm_config_db import UVMConfigDb

from alu_uvm_tb import AluScoreboard, AluTest
from alu_uvm_factory_override_common import AluScoreboardOpHistogram


class AluTestTypeOverride(AluTest):
    """Registers the type override in build_phase (before
    super().build_phase() constructs self.env, which is what actually
    triggers AluScoreboard.type_id.create() down in AluEnv.build_phase),
    then verifies -- in connect_phase, not build_phase -- that it really
    took effect.

    The verification is deliberately NOT done immediately after
    super().build_phase() returns in build_phase itself: UVM's build
    phase is a topdown traversal where a component's build_phase() only
    *constructs* its children (self.env = AluEnv(...) inside AluTest);
    the newly-constructed child's own build_phase() (the thing that
    actually creates self.env.scoreboard) is invoked afterwards, by the
    phase machine continuing its topdown walk into that new child -- not
    synchronously inside the parent's build_phase call. Checking
    self.env.scoreboard right after super().build_phase() returns here
    found self.env.scoreboard still None the first time this test was
    run (AssertionError: ... is a NoneType), which is exactly this
    ordering, not a broken override. connect_phase is a safe place to
    check because UVM guarantees the entire tree's build_phase completes
    (bottom of the topdown traversal reached everywhere) before any
    component's connect_phase (a bottom-up phase) begins."""

    def build_phase(self, phase):
        AluScoreboard.type_id.set_type_override(
            AluScoreboardOpHistogram.type_id.get())
        super().build_phase(phase)

    def connect_phase(self, phase):
        super().connect_phase(phase)
        actual_type = type(self.env.scoreboard).__name__
        assert actual_type == "AluScoreboardOpHistogram", (
            f"factory type override did not take effect: "
            f"self.env.scoreboard is a {actual_type}, expected "
            f"AluScoreboardOpHistogram")
        self.uvm_report_info(
            "OVERRIDE_CHECK",
            f"factory type override confirmed: env.scoreboard is a "
            f"{actual_type}")


uvm_component_utils(AluTestTypeOverride)


@cocotb.test()
async def test_alu_uvm_type_override(dut):
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    dut.rst_n.value = 0
    dut.valid.value = 0
    dut.a.value = 0
    dut.b.value = 0
    dut.op.value = 0
    UVMConfigDb.set(None, "*", "dut", dut)
    await run_test("AluTestTypeOverride")
