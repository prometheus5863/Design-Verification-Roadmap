"""
alu_uvm_factory_inst_override_tb.py -- companion to
alu_uvm_factory_type_override_tb.py, demonstrating the other factory
override entry point: an *instance* override
(`<T>::type_id::set_inst_override()` in SystemVerilog UVM 1.2 terms,
`UVMComponentRegistry.set_inst_override` here), which targets only one
specific hierarchical path rather than every future instance of a type.

Registers the override against the absolute path
"uvm_test_top.env.scoreboard" -- uvm-python's top-level test instance is
named uvm_test_top by run_test(), matching standard UVM 1.2 convention
(confirmed in this repo's own alu_uvm_tb.py sim output logs, e.g.
"UVM_INFO @ 925.0NS: uvm_test_top [SUMMARY] ...").

With only one AluScoreboard instantiated anywhere in this environment,
this test's *observable* result is identical to
alu_uvm_factory_type_override_tb.py's -- stated here plainly rather than
implied otherwise. The point of this second file is to demonstrate the
distinct set_inst_override API call correctly (a type override and an
instance override are registered differently and resolve differently
when a hierarchy has multiple instances of the same component type;
this repo's single-scoreboard environment doesn't happen to exercise
that difference), not to manufacture a behavioral contrast this
environment doesn't have the structure to show.

Run with: `make -f Makefile.factory_inst_override` in this directory.
"""

import cocotb
from cocotb.clock import Clock
from uvm import run_test, uvm_component_utils
from uvm.base.uvm_config_db import UVMConfigDb

from alu_uvm_tb import AluScoreboard, AluTest
from alu_uvm_factory_override_common import AluScoreboardOpHistogram


class AluTestInstOverride(AluTest):
    """See AluTestTypeOverride's docstring (alu_uvm_factory_type_override_
    tb.py) for why the verification runs in connect_phase rather than
    right after super().build_phase() in build_phase: self.env.scoreboard
    is still None at that point in the topdown build traversal."""

    def build_phase(self, phase):
        AluScoreboard.type_id.set_inst_override(
            AluScoreboardOpHistogram.type_id.get(),
            "uvm_test_top.env.scoreboard")
        super().build_phase(phase)

    def connect_phase(self, phase):
        super().connect_phase(phase)
        actual_type = type(self.env.scoreboard).__name__
        assert actual_type == "AluScoreboardOpHistogram", (
            f"factory instance override did not take effect: "
            f"self.env.scoreboard is a {actual_type}, expected "
            f"AluScoreboardOpHistogram")
        self.uvm_report_info(
            "OVERRIDE_CHECK",
            f"factory instance override confirmed: env.scoreboard is a "
            f"{actual_type}")


uvm_component_utils(AluTestInstOverride)


@cocotb.test()
async def test_alu_uvm_inst_override(dut):
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    dut.rst_n.value = 0
    dut.valid.value = 0
    dut.a.value = 0
    dut.b.value = 0
    dut.op.value = 0
    UVMConfigDb.set(None, "*", "dut", dut)
    await run_test("AluTestInstOverride")
