"""
alu_uvm_tb.py -- Phase 4 milestone (partial): a real UVM class hierarchy
running against this repo's existing `alu_dut` (examples/phase2/
alu_if_and_dut.sv), using uvm-python (a Python/cocotb port of SystemVerilog
UVM 1.2, https://github.com/tpoikela/uvm-python) instead of native
SystemVerilog UVM.

WHY THIS FILE EXISTS (see notes/2026-09-06-uvm-python-toolchain-resolution.md
for the full research/decision writeup): every Phase 2/3 session since
2026-08-25 documented the same standing blocker -- this repo's pinned
Icarus Verilog 10.3/12.0 build cannot compile SystemVerilog classes at all
(no `virtual <interface>` class members, no `mailbox`, no class handles as
`input`/`ref` args or in queues/arrays), which makes a *native* SV-UVM
environment impossible on this toolchain. uvm-python sidesteps this
entirely: it reimplements the UVM 1.2 base classes in pure Python (driven
through cocotb's VPI/coroutine layer), so "the driver/monitor/scoreboard
are real class objects with real handles passed around" -- the exact
capability this repo's Icarus build lacked -- is achieved by moving the
*testbench* language to Python while the *DUT* stays exactly the Verilog
already written for Phase 1/2. The DUT itself (`alu_dut`) is reused
unmodified from examples/phase2/alu_if_and_dut.sv.

This demonstrates real (not hand-rolled/manual, unlike every Phase 2
workaround) instances of:
  - a `UVMSequenceItem` transaction class
  - a `UVMSequence` generating randomized transactions
  - a `UVMDriver` / `UVMSequencer` pull-mode handshake
  - a `UVMMonitor` broadcasting sampled DUT activity over a real
    `UVMAnalysisPort` (a genuine TLM analysis port, not the
    `$display`-based scoreboard hookup used in alu_combined_tb.sv)
  - a `UVMScoreboard` receiving via a real analysis export/`write()`
  - `UVMAgent` / `UVMEnv` / `UVMTest` component hierarchy
  - the standard phase methods (`build_phase`, `connect_phase`,
    `run_phase`) and objection-based `run_phase` termination
  - factory registration via `uvm_component_utils`/`uvm_object_utils`
  - `UVMConfigDb` for passing the cocotb DUT handle down into the
    environment

Run with: `make` in this directory (see Makefile). Requires cocotb<2.0
(uvm-python 0.4.0 is not yet compatible with cocotb 2.x -- see the notes
file for the exact failure and the version pin used).
"""

import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge, Timer

from uvm import (
    UVMSequenceItem, UVMSequence, UVMSequencer, UVMDriver, UVMMonitor,
    UVMScoreboard, UVMAgent, UVMEnv, UVMTest, UVMAnalysisPort,
    uvm_object_utils, uvm_component_utils, uvm_analysis_imp_decl, run_test,
)
from uvm.base.uvm_config_db import UVMConfigDb

# Real UVM idiom (mirrors the SV `\`uvm_analysis_imp_decl(_alu)` macro):
# generates a dedicated UVMAnalysisImp_alu port class whose write() calls
# back into this scoreboard's write_alu() -- the actual mechanism a
# uvm_scoreboard uses to receive broadcasts from a monitor's analysis
# port, since UVMScoreboard itself (like uvm_scoreboard in SV) ships with
# no export of its own.
UVMAnalysisImpAlu = uvm_analysis_imp_decl("_alu")

# ALU opcode encoding, matching alu_op_e in alu_if_and_dut.sv exactly
# (ALU_ADD=0, ALU_SUB=1, ALU_AND=2, ALU_OR=3, ALU_XOR=4).
OPS = ["ADD", "SUB", "AND", "OR", "XOR"]
OP_ENCODING = {"ADD": 0, "SUB": 1, "AND": 2, "OR": 3, "XOR": 4}
NUM_TRANSACTIONS = 40


def alu_reference_model(op, a, b):
    """Independent Python re-implementation of alu_dut's combinational
    stage (add_ext/sub_ext/case/flags logic in alu_if_and_dut.sv), used
    by the scoreboard as the expected-value generator. Deliberately
    reimplemented from the spec rather than imported from the DUT, same
    principle as the two independently-formulated checkers in
    examples/phase2_milestone/alu_combined_tb.sv."""
    a &= 0xFF
    b &= 0xFF
    if op == "ADD":
        result = (a + b) & 0xFF
        carry = 1 if (a + b) > 0xFF else 0
        overflow = 1 if (((a >> 7) == (b >> 7)) and ((result >> 7) != (a >> 7))) else 0
    elif op == "SUB":
        raw = a - b
        result = raw & 0xFF
        carry = 1 if raw < 0 else 0
        a_sign, b_sign, r_sign = (a >> 7), (b >> 7), (result >> 7)
        overflow = 1 if (a_sign != b_sign and r_sign != a_sign) else 0
    elif op == "AND":
        result, carry, overflow = (a & b), 0, 0
    elif op == "OR":
        result, carry, overflow = (a | b), 0, 0
    elif op == "XOR":
        result, carry, overflow = (a ^ b), 0, 0
    else:
        raise ValueError(f"unknown op {op}")
    zero = 1 if result == 0 else 0
    return result, zero, carry, overflow


class AluSeqItem(UVMSequenceItem):
    """Transaction: one ALU stimulus vector (op, a, b) plus, once sampled
    back from the DUT, the observed (result, zero, carry, overflow).
    A real uvm_sequence_item subclass -- the thing Icarus 10.3's lack of
    class-handle support made impossible to pass through queues/ports in
    every earlier Phase 2 example."""

    def __init__(self, name="AluSeqItem"):
        super().__init__(name)
        self.op = "ADD"
        self.a = 0
        self.b = 0
        self.result = None
        self.zero = None
        self.carry = None
        self.overflow = None

    def randomize_fields(self):
        self.op = random.choice(OPS)
        self.a = random.randint(0, 255)
        self.b = random.randint(0, 255)

    def convert2string(self):
        return (f"op={self.op} a=0x{self.a:02x} b=0x{self.b:02x} "
                f"result={self.result} zero={self.zero} carry={self.carry} "
                f"overflow={self.overflow}")


uvm_object_utils(AluSeqItem)


class AluRandomSequence(UVMSequence):
    """Generates NUM_TRANSACTIONS randomized AluSeqItems through the
    standard start_item/finish_item handshake with the sequencer -- the
    real UVM sequence/sequencer protocol, not a bare Python generator
    function feeding the driver directly."""

    def __init__(self, name="AluRandomSequence"):
        super().__init__(name)

    async def body(self):
        for i in range(NUM_TRANSACTIONS):
            item = AluSeqItem(f"item_{i}")
            await self.start_item(item)
            item.randomize_fields()
            await self.finish_item(item)


uvm_object_utils(AluRandomSequence)


class AluDriver(UVMDriver):
    """Pulls transactions from the sequencer and drives them onto
    alu_dut's plain (non-interface, per the Icarus tooling limitation
    documented in alu_if_and_dut.sv) ports, one per clock, then waits for
    the DUT's one-cycle registered latency before deasserting valid."""

    def __init__(self, name, parent):
        super().__init__(name, parent)
        self.dut = None
        self.num_driven = 0

    def build_phase(self, phase):
        super().build_phase(phase)
        arr = []
        if not UVMConfigDb.get(self, "", "dut", arr):
            raise Exception("AluDriver: 'dut' not found in config_db")
        self.dut = arr[0]

    async def run_phase(self, phase):
        dut = self.dut
        dut.valid.value = 0
        while True:
            item = await self.seq_item_port.get_next_item()
            # Explicitly synchronize to the *next* FallingEdge before
            # driving, every iteration -- rather than relying on
            # get_next_item() having unblocked at a convenient point in
            # the clock period. Found necessary this session: without
            # this, the very first transaction's valid assertion landed
            # exactly on the same simulation timestep as a RisingEdge
            # (because AluTest.run_phase's reset sequence ends and calls
            # seq.start() in the same delta as that edge), racing the
            # monitor's own RisingEdge-triggered sampling coroutine for
            # scheduling order on that edge and silently dropping
            # transaction 0 about half the time depending on scheduling
            # order (driven=40 but valid_seen=39 in the affected runs --
            # see notes/2026-09-06-uvm-python-toolchain-resolution.md).
            await FallingEdge(dut.clk)
            dut.a.value = item.a
            dut.b.value = item.b
            dut.op.value = OP_ENCODING[item.op]
            dut.valid.value = 1
            await FallingEdge(dut.clk)
            dut.valid.value = 0
            self.num_driven += 1
            self.seq_item_port.item_done()


uvm_component_utils(AluDriver)


class AluMonitor(UVMMonitor):
    """Samples alu_dut's registered outputs every cycle `result_valid` is
    high and broadcasts a populated AluSeqItem over a real
    UVMAnalysisPort -- the genuine TLM broadcast primitive documented as
    conceptually covered but practically undemonstrable in
    notes/2026-08-31-layered-testbench-architecture-and-tlm-basics.md
    (Section 3), since Icarus 10.3 has no `mailbox`/TLM channel type to
    build one on top of."""

    def __init__(self, name, parent):
        super().__init__(name, parent)
        self.dut = None
        self.ap = UVMAnalysisPort("ap", self)
        self.num_sampled = 0
        self.num_valid_seen = 0
        self.num_result_valid_seen = 0

    def build_phase(self, phase):
        super().build_phase(phase)
        arr = []
        if not UVMConfigDb.get(self, "", "dut", arr):
            raise Exception("AluMonitor: 'dut' not found in config_db")
        self.dut = arr[0]

    async def run_phase(self, phase):
        dut = self.dut
        rev_op = {v: k for k, v in OP_ENCODING.items()}
        # alu_dut registers its inputs and result one cycle later (see
        # alu_if_and_dut.sv's header comment), so by the cycle
        # result_valid rises, dut.a/b/op already show the *next*
        # transaction the driver has since put on the bus, not the one
        # that produced this result. A monitor sampling op/a/b and
        # result on the same edge silently pairs every result with the
        # wrong stimulus (found and fixed this session -- see
        # notes/2026-09-06-uvm-python-toolchain-resolution.md for the
        # first (buggy) version and the scoreboard mismatches it
        # produced). The fix: latch (op, a, b) into a FIFO on the same
        # edge `valid` is asserted, and pop it back off on the edge
        # `result_valid` is asserted -- an explicit model of the DUT's
        # pipeline latency, not an assumption that inputs and outputs
        # are sampled in the same cycle.
        pending = []
        while True:
            await RisingEdge(dut.clk)
            if dut.valid.value == 1:
                self.num_valid_seen += 1
                pending.append((rev_op[int(dut.op.value)], int(dut.a.value),
                                 int(dut.b.value)))
            if dut.result_valid.value == 1:
                self.num_result_valid_seen += 1
                op, a, b = pending.pop(0)
                item = AluSeqItem("sampled")
                item.op, item.a, item.b = op, a, b
                item.result = int(dut.result.value)
                flags = int(dut.flags.value)
                # alu_flags_s is {zero, carry, overflow} packed MSB-first
                item.zero = (flags >> 2) & 0x1
                item.carry = (flags >> 1) & 0x1
                item.overflow = flags & 0x1
                self.num_sampled += 1
                self.ap.write(item)


uvm_component_utils(AluMonitor)


class AluScoreboard(UVMScoreboard):
    """Real UVMScoreboard: receives sampled transactions through a
    write() analysis-export callback (registered via
    uvm_analysis_imp_decl in practice; here using the monitor's ap
    connected directly since this environment has exactly one
    consumer) and checks each one against the independent Python
    reference model above."""

    def __init__(self, name, parent):
        super().__init__(name, parent)
        self.item_export = UVMAnalysisImpAlu("item_export", self)
        self.num_checked = 0
        self.num_errors = 0

    def write_alu(self, item):
        exp_result, exp_zero, exp_carry, exp_overflow = alu_reference_model(
            item.op, item.a, item.b)
        self.num_checked += 1
        ok = (item.result == exp_result and item.zero == exp_zero and
              item.carry == exp_carry and item.overflow == exp_overflow)
        if not ok:
            self.num_errors += 1
            self.uvm_report_error(
                "MISMATCH",
                f"{item.convert2string()} != expected "
                f"result={exp_result} zero={exp_zero} carry={exp_carry} "
                f"overflow={exp_overflow}")


uvm_component_utils(AluScoreboard)


class AluAgent(UVMAgent):
    def __init__(self, name, parent):
        super().__init__(name, parent)
        self.sequencer = None
        self.driver = None
        self.monitor = None

    def build_phase(self, phase):
        super().build_phase(phase)
        self.sequencer = UVMSequencer("sequencer", self)
        self.driver = AluDriver("driver", self)
        self.monitor = AluMonitor("monitor", self)

    def connect_phase(self, phase):
        super().connect_phase(phase)
        self.driver.seq_item_port.connect(self.sequencer.seq_item_export)


uvm_component_utils(AluAgent)


class AluEnv(UVMEnv):
    def __init__(self, name, parent):
        super().__init__(name, parent)
        self.agent = None
        self.scoreboard = None

    def build_phase(self, phase):
        super().build_phase(phase)
        self.agent = AluAgent("agent", self)
        self.scoreboard = AluScoreboard("scoreboard", self)

    def connect_phase(self, phase):
        super().connect_phase(phase)
        self.agent.monitor.ap.connect(self.scoreboard.item_export)


uvm_component_utils(AluEnv)


class AluTest(UVMTest):
    """Top-level test. Owns DUT reset: UVM requires run_test() to be
    invoked at simulation time 0 with no prior delays (uvm-python enforces
    this with UVM_FATAL RUNPHSTIME), so unlike a typical cocotb-only
    testbench, reset cannot happen in the plain cocotb test function
    before run_test() -- it has to happen here, inside run_phase, after
    the phase machine has already started."""

    def __init__(self, name="AluTest", parent=None):
        super().__init__(name, parent)
        self.env = None
        self.dut = None

    def build_phase(self, phase):
        super().build_phase(phase)
        self.env = AluEnv("env", self)
        arr = []
        if not UVMConfigDb.get(self, "", "dut", arr):
            raise Exception("AluTest: 'dut' not found in config_db")
        self.dut = arr[0]

    async def run_phase(self, phase):
        phase.raise_objection(self)
        dut = self.dut
        for _ in range(3):
            await RisingEdge(dut.clk)
        dut.rst_n.value = 1
        await RisingEdge(dut.clk)

        seq = AluRandomSequence("seq")
        await seq.start(self.env.agent.sequencer)
        # Let the last transaction's registered output settle before
        # dropping the objection and ending the run phase. Needs at
        # least one full clock period past seq.start()'s return (which
        # happens right after the last item's finish_item/item_done, one
        # cycle before that item's result_valid actually rises) --
        # margin of several cycles kept for safety rather than the bare
        # minimum.
        await Timer(100, units="ns")
        sb = self.env.scoreboard
        drv = self.env.agent.driver
        mon = self.env.agent.monitor
        self.uvm_report_info(
            "SUMMARY",
            f"driven={drv.num_driven} valid_seen={mon.num_valid_seen} "
            f"result_valid_seen={mon.num_result_valid_seen} "
            f"sampled={mon.num_sampled} checked={sb.num_checked} "
            f"errors={sb.num_errors} (expected all == {NUM_TRANSACTIONS})")
        assert sb.num_checked == NUM_TRANSACTIONS, (
            f"scoreboard only saw {sb.num_checked}/{NUM_TRANSACTIONS} "
            f"transactions -- monitor/driver/DUT timing mismatch")
        assert sb.num_errors == 0, f"{sb.num_errors} ALU mismatches found"
        phase.drop_objection(self)


uvm_component_utils(AluTest)


@cocotb.test()
async def test_alu_uvm(dut):
    """cocotb entry point: brings up clock/reset, publishes the DUT
    handle into UVMConfigDb, then hands control to run_test() -- from
    this point on, all stimulus/checking is driven by the UVM phase
    machine (build/connect/run phases), not by this function."""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    dut.rst_n.value = 0
    dut.valid.value = 0
    dut.a.value = 0
    dut.b.value = 0
    dut.op.value = 0

    # run_test() must be called at time 0 with no preceding delay (see
    # AluTest.run_phase's docstring) -- everything above this line is
    # instantaneous signal-value assignment, not a simulation-time delay.
    UVMConfigDb.set(None, "*", "dut", dut)
    await run_test("AluTest")
