"""
alu_uvm_factory_override_common.py -- shared scoreboard subclass used by
both alu_uvm_factory_type_override_tb.py and
alu_uvm_factory_inst_override_tb.py (see the module docstring in the
former for why these are two separate cocotb test modules/simulation
runs rather than two `@cocotb.test()` functions sharing one: uvm-python's
`run_test()` must be called at simulation time 0, per AluTest's own
docstring in alu_uvm_tb.py, so two independent run_test() calls need two
independent simulation invocations, not two tests in one).

AluScoreboardOpHistogram is a drop-in AluScoreboard replacement: identical
checking behavior (write_alu delegates to the base class via super()),
plus a per-opcode pass/fail histogram reported at the end of the test via
a real report_phase override -- a UVM phase not otherwise used anywhere
in this repo yet. It exists specifically to give the factory overrides in
the two test files something observably different to substitute in, so
"the override worked" is a checked fact (the runtime type of
self.env.scoreboard, and the histogram output), not an assumption.
"""

from uvm import uvm_component_utils

from alu_uvm_tb import AluScoreboard, OPS


class AluScoreboardOpHistogram(AluScoreboard):
    def __init__(self, name, parent):
        super().__init__(name, parent)
        self.op_pass = {op: 0 for op in OPS}
        self.op_fail = {op: 0 for op in OPS}

    def write_alu(self, item):
        errors_before = self.num_errors
        super().write_alu(item)
        if self.num_errors > errors_before:
            self.op_fail[item.op] += 1
        else:
            self.op_pass[item.op] += 1

    def report_phase(self, phase):
        super().report_phase(phase)
        total = sum(self.op_pass.values()) + sum(self.op_fail.values())
        lines = [f"Per-opcode histogram ({total} total transactions):"]
        for op in OPS:
            lines.append(f"  {op:4s} pass={self.op_pass[op]:3d} "
                          f"fail={self.op_fail[op]:3d}")
        self.uvm_report_info("OPHIST", "\n".join(lines))


uvm_component_utils(AluScoreboardOpHistogram)
