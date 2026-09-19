"""
Phase 4, RAL: a register abstraction layer for rtl/uart_controller.v.

This closes the LAST remaining Phase 4 topic. AUTOMATION_LOG.md 2026-09-18
listed it as "the obvious next session", and it is, because the pieces it
needs already exist: the UART has a real six-register map, and the
APB-lite bus agent built for the 2026-09-18 milestone is exactly the thing
a RAL model sits on top of.

WHAT A RAL ACTUALLY IS, IN ONE PARAGRAPH
----------------------------------------
Everything up to now addressed registers by number: `write(ADDR_CTRL,
0x0B)`. A RAL replaces the number with an object -- `regmodel.CTRL.write(
status, 0x0B)` -- and, far more importantly, keeps a MIRROR: a model of
what the hardware should currently hold. Four pieces make that work:

  uvm_reg_block   the map as a whole (here: UartRegModel)
  uvm_reg         one register, holding uvm_reg_fields with access
                  policies (RW / RO / WO / RC ...) and reset values
  uvm_reg_adapter translates a generic uvm_reg_item into the bus agent's
                  own UartRegItem, and back
  uvm_reg_predictor  watches the bus MONITOR and updates the mirror from
                  what was actually observed

The payoff is not notation. It is that (a) generic sequences written
against any register model -- hw_reset, bit-bash -- become available for
free, and (b) the mirror gives a reference model of the register file that
nobody had to write by hand.

EXPLICIT vs IMPLICIT PREDICTION, AND WHY THIS USES EXPLICIT
-----------------------------------------------------------
A RAL can update its mirror in two ways. IMPLICIT (auto-predict): the
register object updates the mirror itself whenever someone calls
.write()/.read() on it. EXPLICIT: the mirror is only ever updated by a
predictor fed from the bus monitor.

uvm-python, like UVM, defaults to auto_predict = OFF, and this bench keeps
it off deliberately. Auto-predict believes the write happened because the
sequence asked for it. Explicit prediction believes it only if the monitor
saw it on the wire. That is the same distinction that produced the
2026-09-17 and 2026-09-18 findings in this repo -- never let the thing
that decides correctness be the thing that did the work -- and here it is
free, because the monitor already exists.

It also means the mirror tracks bus traffic that did NOT come from the
RAL at all. `test_backdoor_free_prediction` below exercises exactly that:
a raw UartRegItem is pushed through the bus sequencer, and the mirror
updates anyway.

WHAT THIS UART BREAKS, AND THAT IS THE INTERESTING PART
--------------------------------------------------------
Two of the six registers cannot be honestly described by any uvm_reg
access policy, and pretending otherwise would be the real mistake:

  RX_DATA  reading it POPS the RX FIFO. No access policy expresses "this
           read has a side effect on a queue elsewhere in the design".
           The register model can describe the byte-wide read port; it
           cannot describe the FIFO. Tagged NO_REG_TESTS -- a bit-bash
           here would drain the FIFO and a hw_reset read would consume a
           byte the scoreboard was waiting for.

  STATUS   mixes FOUR volatile live-status bits with THREE sticky
           read-to-clear error bits in one 8-bit register. RC models the
           error bits correctly. The live bits are marked volatile, which
           in UVM means they are not compared -- so a hw_reset sweep over
           STATUS checks nothing at all, silently. That is why this bench
           adds its own explicit STATUS reset check rather than trusting
           the built-in sequence to have covered it.

That STATUS finding is the third independent confirmation of the vplan's
"live status" defect: the RTL bring-up found it (2026-09-17), the UVM
environment's read-to-clear check found it (2026-09-18), and now the
register model cannot express it in one policy.

Run with:  make          (see the Makefile beside this file)
Requires the toolchain from tools/setup_iverilog.sh (SOURCE it, do not
pipe it) plus the uvm-python stack -- see
notes/2026-09-06-uvm-python-toolchain-resolution.md.
"""

import os
import sys

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

from uvm import (
    UVMEnv, UVMTest, UVMSequence, uvm_component_utils, uvm_object_utils,
    run_test, UVM_ERROR, UVM_FATAL, UVM_LOW,
)
from uvm.macros import uvm_info, uvm_error
from uvm.base.uvm_config_db import UVMConfigDb
from uvm.base.uvm_coreservice import UVMCoreService
from uvm.base.uvm_resource_db import UVMResourceDb
from uvm.reg.uvm_reg_block import UVMRegBlock
from uvm.reg.uvm_reg import UVMReg
from uvm.reg.uvm_reg_field import UVMRegField
from uvm.reg.uvm_reg_adapter import UVMRegAdapter
from uvm.reg.uvm_reg_predictor import UVMRegPredictor
from uvm.reg.uvm_reg_model import (
    UVM_LITTLE_ENDIAN, UVM_IS_OK, UVM_FRONTDOOR, UVM_CHECK, UVM_NO_CHECK,
)
from uvm.reg.sequences.uvm_reg_hw_reset_seq import UVMRegHWResetSeq
from uvm.reg.sequences.uvm_reg_bit_bash_seq import UVMRegBitBashSeq

# The bus agent is REUSED, not reimplemented. That reuse is the whole
# argument for a layered testbench: the RAL is a new layer on top of the
# 2026-09-18 agent, and the agent needs no change at all to support it.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "phase4_uvm_milestone"))
from uart_uvm_tb import (                                   # noqa: E402
    UartRegItem, UartRegAgent,
    ADDR_CTRL, ADDR_STATUS, ADDR_BAUD, ADDR_TX, ADDR_RX, ADDR_INT,
    CLK_NS,
)

ADDR_OF = {
    "CTRL": ADDR_CTRL, "STATUS": ADDR_STATUS, "BAUD_DIV": ADDR_BAUD,
    "TX_DATA": ADDR_TX, "RX_DATA": ADDR_RX, "INT_EN": ADDR_INT,
}

# STATUS at reset: tx_empty = 1, everything else 0.
STATUS_RESET = 0x02


# =====================================================================
# The register model
# =====================================================================
class RegCTRL(UVMReg):
    """CTRL @0x0: five RW config bits, three reserved bits that read 0.

    The reserved field is modelled explicitly as RO rather than left out.
    Leaving it out would make the bit-bash sequence skip bits 7:5
    entirely; modelling them RO makes bit-bash actively check that
    writing them does not stick, which is a real requirement (the RTL
    stores only pwdata[4:0]).
    """

    def __init__(self, name="CTRL"):
        super().__init__(name, 8, UVM_NO_CHECK)
        self.en = None
        self.parity_mode = None
        self.stop_bits = None
        self.loopback_en = None
        self.rsvd = None

    def build(self):
        self.en = UVMRegField.type_id.create("en")
        self.parity_mode = UVMRegField.type_id.create("parity_mode")
        self.stop_bits = UVMRegField.type_id.create("stop_bits")
        self.loopback_en = UVMRegField.type_id.create("loopback_en")
        self.rsvd = UVMRegField.type_id.create("rsvd")
        #             parent, size, lsb, access, volatile, reset, has_reset, rand, indiv
        self.en.configure(self, 1, 0, "RW", 0, 0, 1, 1, 0)
        self.parity_mode.configure(self, 2, 1, "RW", 0, 0, 1, 1, 0)
        self.stop_bits.configure(self, 1, 3, "RW", 0, 0, 1, 1, 0)
        self.loopback_en.configure(self, 1, 4, "RW", 0, 0, 1, 1, 0)
        self.rsvd.configure(self, 3, 5, "RO", 0, 0, 1, 0, 0)


uvm_object_utils(RegCTRL)


class RegSTATUS(UVMReg):
    """STATUS @0x1: four volatile live bits + three sticky RC error bits.

    See the module docstring: this register is the reason the vplan's
    "live status" wording cannot hold, and the reason a hw_reset sweep
    over it silently checks nothing.
    """

    def __init__(self, name="STATUS"):
        super().__init__(name, 8, UVM_NO_CHECK)
        self.tx_full = None
        self.tx_empty = None
        self.rx_full = None
        self.rx_avail = None
        self.frame_err = None
        self.parity_err = None
        self.overrun_err = None
        self.rsvd = None

    def build(self):
        for f in ("tx_full", "tx_empty", "rx_full", "rx_avail",
                  "frame_err", "parity_err", "overrun_err", "rsvd"):
            setattr(self, f, UVMRegField.type_id.create(f))
        # Live status: RO and VOLATILE (volatile => UVM will not compare it)
        self.tx_full.configure(self, 1, 0, "RO", 1, 0, 1, 0, 0)
        self.tx_empty.configure(self, 1, 1, "RO", 1, 1, 1, 0, 0)
        self.rx_full.configure(self, 1, 2, "RO", 1, 0, 1, 0, 0)
        self.rx_avail.configure(self, 1, 3, "RO", 1, 0, 1, 0, 0)
        # Sticky error bits: RC == read clears. Volatile, because hardware
        # sets them asynchronously to any bus access.
        self.frame_err.configure(self, 1, 4, "RC", 1, 0, 1, 0, 0)
        self.parity_err.configure(self, 1, 5, "RC", 1, 0, 1, 0, 0)
        self.overrun_err.configure(self, 1, 6, "RC", 1, 0, 1, 0, 0)
        self.rsvd.configure(self, 1, 7, "RO", 0, 0, 1, 0, 0)


uvm_object_utils(RegSTATUS)


class RegBAUD(UVMReg):
    def __init__(self, name="BAUD_DIV"):
        super().__init__(name, 8, UVM_NO_CHECK)
        self.div = None

    def build(self):
        self.div = UVMRegField.type_id.create("div")
        self.div.configure(self, 8, 0, "RW", 0, 0, 1, 1, 0)


uvm_object_utils(RegBAUD)


class RegTXDATA(UVMReg):
    """TX_DATA @0x3: write-only. Reads return 0 (the RTL's default case)."""

    def __init__(self, name="TX_DATA"):
        super().__init__(name, 8, UVM_NO_CHECK)
        self.data = None

    def build(self):
        self.data = UVMRegField.type_id.create("data")
        self.data.configure(self, 8, 0, "WO", 0, 0, 1, 1, 0)


uvm_object_utils(RegTXDATA)


class RegRXDATA(UVMReg):
    """RX_DATA @0x4: RO, volatile, and READING IT POPS A FIFO.

    No uvm_reg access policy can express the pop. Tagged NO_REG_TESTS in
    the model build, because any generic sequence that reads it is
    silently modifying design state.
    """

    def __init__(self, name="RX_DATA"):
        super().__init__(name, 8, UVM_NO_CHECK)
        self.data = None

    def build(self):
        self.data = UVMRegField.type_id.create("data")
        self.data.configure(self, 8, 0, "RO", 1, 0, 1, 0, 0)


uvm_object_utils(RegRXDATA)


class RegINTEN(UVMReg):
    def __init__(self, name="INT_EN"):
        super().__init__(name, 8, UVM_NO_CHECK)
        self.tx_empty_en = None
        self.rx_avail_en = None
        self.err_en = None
        self.rsvd = None

    def build(self):
        for f in ("tx_empty_en", "rx_avail_en", "err_en", "rsvd"):
            setattr(self, f, UVMRegField.type_id.create(f))
        self.tx_empty_en.configure(self, 1, 0, "RW", 0, 0, 1, 1, 0)
        self.rx_avail_en.configure(self, 1, 1, "RW", 0, 0, 1, 1, 0)
        self.err_en.configure(self, 1, 2, "RW", 0, 0, 1, 1, 0)
        self.rsvd.configure(self, 5, 3, "RO", 0, 0, 1, 0, 0)


uvm_object_utils(RegINTEN)


class UartRegModel(UVMRegBlock):
    """The six-register map of rtl/uart_controller.v."""

    def __init__(self, name="UartRegModel"):
        super().__init__(name)
        self.CTRL = None
        self.STATUS = None
        self.BAUD_DIV = None
        self.TX_DATA = None
        self.RX_DATA = None
        self.INT_EN = None

    def build(self):
        self.default_map = self.create_map("default_map", 0, 1,
                                           UVM_LITTLE_ENDIAN, True)
        spec = [("CTRL", RegCTRL, "RW"), ("STATUS", RegSTATUS, "RO"),
                ("BAUD_DIV", RegBAUD, "RW"), ("TX_DATA", RegTXDATA, "WO"),
                ("RX_DATA", RegRXDATA, "RO"), ("INT_EN", RegINTEN, "RW")]
        for name, cls, rights in spec:
            rg = cls.type_id.create(name)
            rg.configure(self, None, "")
            rg.build()
            setattr(self, name, rg)
            self.default_map.add_reg(rg, ADDR_OF[name], rights)

        # Exclusions, each for a stated reason -- not to make tests pass.
        #  RX_DATA : reading pops the RX FIFO (a side effect no policy models)
        #  TX_DATA : write-only; a generic read-compare is meaningless
        #  STATUS  : bit-bash would try to WRITE a read-only status register
        #            hundreds of times; the RC semantics are checked
        #            explicitly by UartRalChecksTest instead
        for reg_name in ("RX_DATA", "TX_DATA"):
            UVMResourceDb.set("REG::" + self.get_full_name() + "." + reg_name,
                              "NO_REG_TESTS", 1, self)
        UVMResourceDb.set("REG::" + self.get_full_name() + ".STATUS",
                          "NO_REG_BIT_BASH_TEST", 1, self)
        self.lock_model()


uvm_object_utils(UartRegModel)


# =====================================================================
# Adapter: uvm_reg_item <-> UartRegItem
# =====================================================================
class UartRegAdapter(UVMRegAdapter):
    """Eighteen lines, and the only code that knows both worlds."""

    def __init__(self, name="UartRegAdapter"):
        super().__init__(name)
        self.supports_byte_enable = False
        self.provides_responses = False

    def reg2bus(self, rw):
        item = UartRegItem.type_id.create("ral_item")
        item.is_write = (rw.kind == 1)      # UVM_WRITE == 1
        item.addr = rw.addr & 0xF
        item.data = rw.data & 0xFF
        return item

    def bus2reg(self, bus_item, rw):
        if not isinstance(bus_item, UartRegItem):
            self.uvm_report_error("BAD_ITEM",
                                  "bus2reg got a non-UartRegItem")
            return
        rw.kind = 1 if bus_item.is_write else 2   # UVM_WRITE / UVM_READ
        rw.addr = bus_item.addr
        rw.data = bus_item.data if bus_item.is_write else bus_item.rdata
        rw.status = UVM_IS_OK


uvm_object_utils(UartRegAdapter)


# =====================================================================
# Targeted checks the built-in sequences cannot express
# =====================================================================
class UartRalChecksSeq(UVMSequence):
    """Every RAL access lives inside a sequence, because it has to.

    `uvm_reg.write()/read()/mirror()` take a `parent` that must be a
    SEQUENCE: internally the map does `rw.parent.start_item(bus_req)` to
    push the translated item at the sequencer. Passing the test component
    raises `AttributeError: 'UartRalChecksTest' object has no attribute
    'start_item'`, which is what the first run of this bench did. The
    register layer is not a shortcut around the sequence layer; it sits
    on top of it.
    """

    def __init__(self, name="UartRalChecksSeq"):
        super().__init__(name)
        self.regmodel = None
        self.dut = None
        self.n_checks = 0
        self.n_fail = 0
        self.log = []

    def _check(self, ok, msg):
        self.n_checks += 1
        tag = "PASS" if ok else "FAIL"
        if not ok:
            self.n_fail += 1
        self.log.append(f"{tag}: {msg}")
        if ok:
            uvm_info("RALCHK", "PASS: " + msg, UVM_LOW)
        else:
            uvm_error("RALCHK", "FAIL: " + msg)

    async def _raw(self, is_write, addr, data=0):
        """A raw bus access that bypasses the RAL entirely.

        Used to prove the mirror is moved by the PREDICTOR watching the
        monitor, not by the register object congratulating itself.
        """
        item = UartRegItem.type_id.create("raw")
        item.is_write = is_write
        item.addr = addr
        item.data = data
        await self.start_item(item)
        await self.finish_item(item)
        return item.rdata

    async def _run_builtin(self, label, seq):
        """Run a built-in register sequence and CHECK it, rather than
        merely running it.

        The 2026-09-18 finding was a regression that went green while the
        log contained UVM_ERRORs, because the thing reporting the verdict
        was not the thing doing the checking. A built-in sequence reports
        failures only by calling uvm_error, so 'we ran UVMRegBitBashSeq'
        is not a check. Snapshotting the report server's error count
        around the call turns it into one, and makes a mutation report
        able to say WHICH sequence killed a given mutant.
        """
        svr = UVMCoreService.get().get_report_server()
        before = svr.get_severity_count(UVM_ERROR)
        await seq.start(self.m_sequencer, self)
        after = svr.get_severity_count(UVM_ERROR)
        self._check(after == before,
                    f"{label} completed with no new UVM_ERROR "
                    f"({after - before} raised)")

    async def _reset(self):
        dut = self.dut
        dut.rst_n.value = 0
        for _ in range(5):
            await RisingEdge(dut.clk)
        dut.rst_n.value = 1
        for _ in range(5):
            await RisingEdge(dut.clk)

    async def _send_bad_frame(self):
        """One frame with the stop bit driven low -> frame_err."""
        dut = self.dut
        bit_cycles = 16          # BAUD_DIV = 0 -> 16 clocks per bit

        async def bit(v):
            dut.rx.value = v
            for _ in range(bit_cycles):
                await RisingEdge(dut.clk)

        await bit(0)                         # start
        for i in range(8):                   # data 0xA5, LSB first
            await bit((0xA5 >> i) & 1)
        await bit(0)                         # STOP DRIVEN LOW -> frame error
        await bit(1)                         # return to idle
        for _ in range(bit_cycles * 2):
            await RisingEdge(dut.clk)

    async def body(self):
        dut = self.dut
        await self._reset()
        self.regmodel.reset()          # mirror -> reset values

        # -- CHECK 1: explicit prediction, and RO enforcement in one shot.
        #    A RAW bus write of 0xFB, never touching the register object,
        #    must still move the mirror -- and must move it to 0x1B, because
        #    CTRL bits 7:5 are reserved/RO and the RTL stores pwdata[4:0].
        await self._raw(True, ADDR_CTRL, 0xFB)
        await RisingEdge(dut.clk)
        mirrored = self.regmodel.CTRL.get_mirrored_value()
        self._check(mirrored == 0x1B,
                    f"raw bus write 0xFB to CTRL moved the mirror to "
                    f"0x{mirrored:02x} via the predictor (expected 0x1b: "
                    f"bits 7:5 are RO, so 0xFB & 0x1F). Nothing called "
                    f"CTRL.write(); auto_predict is off")

        # -- CHECK 2: the mirror as a reference model. Read back through
        #    the RAL with UVM_CHECK and let the RAL do the comparison.
        status = []
        await self.regmodel.CTRL.mirror(status, UVM_CHECK, UVM_FRONTDOOR,
                                        None, self)
        self._check(status[0] == UVM_IS_OK,
                    "CTRL mirror(UVM_CHECK) after a raw write agrees with "
                    "the hardware")

        # -- CHECK 3: a RAL write, read back by RAW bus access. The reverse
        #    direction: the adapter's reg2bus must produce a real APB
        #    access, not just update a model.
        wstat = []
        await self.regmodel.BAUD_DIV.write(wstat, 0x5A, UVM_FRONTDOOR, None,
                                           self)
        got = await self._raw(False, ADDR_BAUD)
        self._check(wstat[0] == UVM_IS_OK and got == 0x5A,
                    f"RAL BAUD_DIV.write(0x5A) reached the DUT: a raw read "
                    f"returns 0x{got:02x}")

        # -- CHECK 4: STATUS at reset. The built-in hw_reset sequence
        #    CANNOT check this: every meaningful bit is volatile, and UVM
        #    does not compare volatile fields. So check it by hand.
        await self._reset()
        self.regmodel.reset()
        st = await self._raw(False, ADDR_STATUS)
        self._check(st == STATUS_RESET,
                    f"STATUS reads 0x{st:02x} with the UART idle after reset "
                    f"(expected 0x{STATUS_RESET:02x}: tx_empty set, all error "
                    f"bits clear) -- a check the hw_reset sequence silently "
                    f"skips, because volatile fields are not compared")

        # -- CHECK 5: the RC access policy. Provoke a frame error, then read
        #    STATUS TWICE: set on the first read, cleared BY that read.
        #    This is the 2026-09-18 lesson encoded in the register model
        #    instead of in a hand-written scoreboard.
        await self._raw(True, ADDR_CTRL, 0x01)      # enable, no parity
        await self._send_bad_frame()
        st1 = await self._raw(False, ADDR_STATUS)
        st2 = await self._raw(False, ADDR_STATUS)
        self._check((st1 >> 4) & 0x1 == 1,
                    f"frame_err is set after a corrupted stop bit "
                    f"(STATUS=0x{st1:02x})")
        self._check((st2 >> 4) & 0x1 == 0,
                    f"frame_err was CLEARED by the first STATUS read "
                    f"(second read 0x{st2:02x}) -- the RC policy, and the "
                    f"reason the vplan's 'live status' wording is wrong")

        # -- CHECK 7: the built-in hw_reset sequence over the whole block.
        await self._raw(True, ADDR_CTRL, 0x00)
        await self._reset()
        hw = UVMRegHWResetSeq.type_id.create("hw_reset_seq")
        hw.model = self.regmodel
        await self._run_builtin("UVMRegHWResetSeq", hw)

        # -- CHECK 8: the built-in bit-bash sequence. This is the one that
        #    earns the RAL its keep: it walks EVERY bit of every register,
        #    writing 1 and 0 and reading back, and it checks that RO bits
        #    do NOT stick. Nobody wrote it for this UART.
        bb = UVMRegBitBashSeq.type_id.create("bit_bash_seq")
        bb.model = self.regmodel
        await self._run_builtin("UVMRegBitBashSeq", bb)

        for _ in range(10):
            await RisingEdge(dut.clk)


uvm_object_utils(UartRalChecksSeq)


class UartRalChecksTest(UVMTest):
    """Builds the RAL, wires the predictor, and runs the checks."""

    def __init__(self, name="UartRalChecksTest", parent=None):
        super().__init__(name, parent)
        self.regmodel = None
        self.agent = None
        self.predictor = None
        self.adapter = None
        self.dut = None
        self.seq = None

    def build_phase(self, phase):
        super().build_phase(phase)
        arr = []
        if not UVMConfigDb.get(self, "", "dut", arr):
            self.uvm_report_fatal("NODUT", "dut handle not in config db")
        self.dut = arr[0]
        UVMConfigDb.set(self, "agent*", "dut", self.dut)

        self.agent = UartRegAgent.type_id.create("agent", self)
        self.regmodel = UartRegModel.type_id.create("regmodel")
        self.regmodel.build()
        self.adapter = UartRegAdapter.type_id.create("adapter")
        self.predictor = UVMRegPredictor.type_id.create("predictor", self)

    def connect_phase(self, phase):
        super().connect_phase(phase)
        # The map needs a sequencer + adapter to reach the bus...
        self.regmodel.default_map.set_sequencer(self.agent.sequencer,
                                                self.adapter)
        # ...and auto-predict stays OFF, so the mirror can only be updated
        # by the predictor, which is fed from the MONITOR.
        self.regmodel.default_map.set_auto_predict(False)
        self.predictor.map = self.regmodel.default_map
        self.predictor.adapter = self.adapter
        self.agent.monitor.ap.connect(self.predictor.bus_in)

    async def run_phase(self, phase):
        phase.raise_objection(self)
        dut = self.dut
        cocotb.start_soon(Clock(dut.clk, CLK_NS, units="ns").start())
        dut.rst_n.value = 0
        dut.psel.value = 0
        dut.penable.value = 0
        dut.pwrite.value = 0
        dut.paddr.value = 0
        dut.pwdata.value = 0
        dut.rx.value = 1
        for _ in range(5):
            await RisingEdge(dut.clk)

        self.seq = UartRalChecksSeq.type_id.create("ral_checks")
        self.seq.regmodel = self.regmodel
        self.seq.dut = dut
        await self.seq.start(self.agent.sequencer)

        phase.drop_objection(self)

    def report_phase(self, phase):
        super().report_phase(phase)
        svr = UVMCoreService.get().get_report_server()
        n_err = svr.get_severity_count(UVM_ERROR)
        n_fatal = svr.get_severity_count(UVM_FATAL)
        n_checks = self.seq.n_checks if self.seq else 0
        n_fail = self.seq.n_fail if self.seq else 1
        print("")
        print("=" * 68)
        print("Phase 4 RAL summary")
        print("=" * 68)
        for line in (self.seq.log if self.seq else []):
            print("  " + line)
        print("-" * 68)
        print(f"  targeted RAL checks : {n_checks - n_fail}/{n_checks} passed")
        print(f"  UVM_ERROR count     : {n_err}")
        print(f"  UVM_FATAL count     : {n_fatal}")
        # The 2026-09-18 lesson, applied again: cocotb's PASS/FAIL comes
        # from whether the coroutine raised, and knows nothing about the
        # UVM report server. Wire the two together explicitly, or a
        # regression goes green with errors in the log.
        assert n_err == 0, f"{n_err} UVM_ERROR(s) -- see the log above"
        assert n_fatal == 0, f"{n_fatal} UVM_FATAL(s)"
        assert n_fail == 0, f"{n_fail} targeted RAL check(s) failed"
        assert n_checks >= 8, f"only {n_checks} checks ran; the sequence " \
                              f"did not complete"
        print("  RESULT              : PASS")
        print("=" * 68)


uvm_component_utils(UartRalChecksTest)


@cocotb.test()
async def run_uart_ral_test(dut):
    UVMConfigDb.set(None, "*", "dut", dut)
    await run_test("UartRalChecksTest")
