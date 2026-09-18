"""
uart_uvm_tb.py -- Phase 4 milestone: a full UVM environment for the
`uart_controller` DUT, written with uvm-python on cocotb/Icarus.

This is the milestone the roadmap has been working toward since Phase 3:
a real UVM testbench against the DUT specified by
`verification_plans/uart_controller_verification_plan.md` and brought up
(60/60 directed checks) on 2026-09-17 in
`examples/phase4_rtl_bringup/`. The DUT is used UNMODIFIED. Bringing up
a new DUT inside a new environment would make every failure ambiguous
between the two; the RTL was made known-good first, deliberately.

WHAT THIS EXERCISES THAT EARLIER PHASE 4 WORK DID NOT
-----------------------------------------------------
The ALU testbenches (2026-09-06/07) already demonstrated the class
hierarchy, phases, the factory, uvm_config_db, factory overrides, a real
sequencer/driver handshake and an analysis-port broadcast. progress.md
listed four things as still not exercised. Three of them are exercised
here for the first time:

  * ACTIVE vs PASSIVE agents. `UartSerialAgent` is instantiated twice
    from the same class: once ACTIVE on the `rx` line (sequencer +
    driver + monitor) and once PASSIVE on the `tx` line (monitor only,
    no sequencer and no driver built at all). This is not a cosmetic
    flag -- `tx` is a DUT *output*, so an agent on it physically cannot
    be active, which is exactly the situation the active/passive
    distinction exists for.
  * A VIRTUAL SEQUENCER and CONCURRENT SEQUENCES.
    `UartVirtualSequencer` holds handles to the register sequencer and
    the serial sequencer; `UartFullDuplexVSeq` starts a register-side
    TX sequence and a serial-side RX sequence *at the same time* on
    those two sequencers and waits for both. That is genuine full-duplex
    stimulus -- the DUT transmits and receives simultaneously -- not two
    sequences run back to back.
  * A REFERENCE-MODEL SCOREBOARD fed by three analysis ports
    (`uvm_analysis_imp_decl` for _reg, _rx and _tx), which predicts the
    serial output from register writes, predicts register reads from
    serial input, and models the sticky/read-to-clear error bits.

The fourth (RAL) is still not done; the register map here is driven
through an explicit bus agent, which is what RAL would sit on top of.

REFERENCE MODEL AND THE STICKY-ERROR SUBTLETY
----------------------------------------------
The scoreboard models the DUT's error bits as STICKY and READ-TO-CLEAR,
which is the 2026-09-17 bring-up's documented deviation from the
verification plan's "live status" wording (see the IMPLEMENTATION
DECISION comment at the head of rtl/uart_controller.v). Modelling them
as live would make the scoreboard's STATUS prediction wrong in a way no
amount of stimulus could fix -- so this environment is itself a second,
independent confirmation that the vplan v2 revision is needed, now from
the testbench side rather than the RTL side.

TIMING
------
BAUD_DIV = 0, so one bit period is 16*(0+1) = 16 clock cycles. With a
10 ns clock that is a 160 ns bit and a ~1.8 us frame, which keeps the
whole regression inside a few hundred microseconds of simulated time on
the pinned Icarus 10.3 build.

Run with:  make          (see the Makefile beside this file)
"""

import random
from collections import deque

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge, Timer

from uvm import (
    UVMSequenceItem, UVMSequence, UVMSequencer, UVMDriver, UVMMonitor,
    UVMScoreboard, UVMAgent, UVMEnv, UVMTest, UVMComponent, UVMAnalysisPort,
    uvm_object_utils, uvm_component_utils, uvm_analysis_imp_decl, run_test,
    UVM_ERROR, UVM_FATAL,
)
from uvm.base.uvm_config_db import UVMConfigDb
from uvm.base.uvm_coreservice import UVMCoreService

# Three separate imp declarations, the uvm-python equivalent of writing
# `uvm_analysis_imp_decl(_reg)` etc. in SystemVerilog. The scoreboard
# needs three because it subscribes to three different producers and has
# to know which one a transaction came from.
UVMAnalysisImpReg = uvm_analysis_imp_decl("_reg")
UVMAnalysisImpRx = uvm_analysis_imp_decl("_rx")
UVMAnalysisImpTx = uvm_analysis_imp_decl("_tx")

CLK_NS = 10
BAUD_DIV = 0
BIT_CYCLES = 16 * (BAUD_DIV + 1)

ADDR_CTRL, ADDR_STATUS, ADDR_BAUD, ADDR_TX, ADDR_RX, ADDR_INT = range(6)

PARITY_NONE, PARITY_EVEN, PARITY_ODD = 0, 1, 2

# STATUS bit positions (rtl/uart_controller.v status_val)
ST_TX_FULL, ST_TX_EMPTY, ST_RX_FULL, ST_RX_AVAIL = 0, 1, 2, 3
ST_FRAME_ERR, ST_PARITY_ERR, ST_OVERRUN_ERR = 4, 5, 6


class UartCfg:
    """Shared configuration object, published through UVMConfigDb.

    The monitors need the parity/stop-bit settings to decode a frame at
    all, and the scoreboard needs them to predict one. Keeping them in a
    single object that the config sequence updates as it writes the DUT
    keeps the model and the device from drifting apart silently.
    """

    def __init__(self):
        self.parity_mode = PARITY_NONE
        self.two_stop = False
        self.baud_div = BAUD_DIV

    def frame_bits(self):
        return 1 + 8 + (0 if self.parity_mode == PARITY_NONE else 1) + \
            (2 if self.two_stop else 1)

    def expected_parity(self, data):
        ones = bin(data & 0xFF).count("1") % 2
        if self.parity_mode == PARITY_EVEN:
            return ones
        if self.parity_mode == PARITY_ODD:
            return 1 - ones
        return None


# ---------------------------------------------------------------------
# Sequence items
# ---------------------------------------------------------------------
class UartRegItem(UVMSequenceItem):
    """One APB-lite register access."""

    def __init__(self, name="UartRegItem"):
        super().__init__(name)
        self.is_write = True
        self.addr = 0
        self.data = 0
        self.rdata = 0

    def convert2string(self):
        kind = "WR" if self.is_write else "RD"
        val = self.data if self.is_write else self.rdata
        return f"{kind} addr=0x{self.addr:01x} data=0x{val:02x}"


uvm_object_utils(UartRegItem)


class UartFrameItem(UVMSequenceItem):
    """One serial frame, either to be driven on rx or decoded from a line.

    `corrupt` is the deliberate-defect knob used to exercise the DUT's
    error detection: 'parity' inverts the parity bit, 'frame' drives the
    first stop bit low.
    """

    def __init__(self, name="UartFrameItem"):
        super().__init__(name)
        self.data = 0
        self.corrupt = None        # None | 'parity' | 'frame'
        self.parity_bit = None     # as decoded/driven
        self.parity_ok = True
        self.stop_ok = True

    def convert2string(self):
        return (f"frame data=0x{self.data:02x} corrupt={self.corrupt} "
                f"parity_ok={self.parity_ok} stop_ok={self.stop_ok}")


uvm_object_utils(UartFrameItem)


# ---------------------------------------------------------------------
# Register (APB-lite) agent
# ---------------------------------------------------------------------
class UartRegDriver(UVMDriver):
    """Drives the APB-lite setup/access phases for one register access."""

    def __init__(self, name, parent):
        super().__init__(name, parent)
        self.dut = None

    def build_phase(self, phase):
        super().build_phase(phase)
        arr = []
        if not UVMConfigDb.get(self, "", "dut", arr):
            self.uvm_report_fatal("NODUT", "dut handle not in config db")
        self.dut = arr[0]

    async def run_phase(self, phase):
        dut = self.dut
        while True:
            item = await self.seq_item_port.get_next_item()
            # SETUP phase: psel high, penable low.
            await FallingEdge(dut.clk)
            dut.psel.value = 1
            dut.penable.value = 0
            dut.pwrite.value = 1 if item.is_write else 0
            dut.paddr.value = item.addr
            dut.pwdata.value = item.data & 0xFF
            # ACCESS phase: penable high for exactly one clock.
            await FallingEdge(dut.clk)
            dut.penable.value = 1
            # prdata is combinational on paddr, but RX_DATA's read pointer
            # advances on the rising edge that completes the access, so the
            # data must be sampled BEFORE that edge, not after it.
            await Timer(2, units="ns")
            item.rdata = int(dut.prdata.value)
            await FallingEdge(dut.clk)
            dut.psel.value = 0
            dut.penable.value = 0
            self.seq_item_port.item_done()


uvm_component_utils(UartRegDriver)


class UartRegMonitor(UVMMonitor):
    """Observes the bus independently of the driver and broadcasts every
    completed access. The scoreboard is fed from here, never from the
    driver -- a driver that silently did nothing would otherwise still
    'pass', which is the standard reason monitors exist."""

    def __init__(self, name, parent):
        super().__init__(name, parent)
        self.dut = None
        self.ap = UVMAnalysisPort("ap", self)

    def build_phase(self, phase):
        super().build_phase(phase)
        arr = []
        if not UVMConfigDb.get(self, "", "dut", arr):
            self.uvm_report_fatal("NODUT", "dut handle not in config db")
        self.dut = arr[0]

    async def run_phase(self, phase):
        dut = self.dut
        while True:
            await RisingEdge(dut.clk)
            try:
                active = int(dut.psel.value) and int(dut.penable.value)
            except ValueError:
                continue  # X/Z during reset
            if not active:
                continue
            item = UartRegItem("observed")
            item.is_write = bool(int(dut.pwrite.value))
            item.addr = int(dut.paddr.value)
            item.data = int(dut.pwdata.value)
            item.rdata = int(dut.prdata.value)
            self.ap.write(item)


uvm_component_utils(UartRegMonitor)


class UartRegAgent(UVMAgent):
    def __init__(self, name, parent):
        super().__init__(name, parent)
        self.sequencer = None
        self.driver = None
        self.monitor = None
        self.is_active = True

    def build_phase(self, phase):
        super().build_phase(phase)
        arr = []
        if UVMConfigDb.get(self, "", "is_active", arr):
            self.is_active = bool(arr[0])
        self.monitor = UartRegMonitor.type_id.create("monitor", self)
        if self.is_active:
            self.sequencer = UVMSequencer.type_id.create("sequencer", self)
            self.driver = UartRegDriver.type_id.create("driver", self)

    def connect_phase(self, phase):
        super().connect_phase(phase)
        if self.is_active:
            self.driver.seq_item_port.connect(self.sequencer.seq_item_export)


uvm_component_utils(UartRegAgent)


# ---------------------------------------------------------------------
# Serial agent -- ONE class, instantiated active on rx and passive on tx
# ---------------------------------------------------------------------
class UartSerialDriver(UVMDriver):
    """Bit-bangs a frame onto the DUT's `rx` input at the configured baud.

    This is the standalone RX bit-driver the roadmap listed as part of
    the milestone. It deliberately does NOT reuse the DUT's own
    transmitter via loopback: a loopback test cannot distinguish a
    receiver that works from a receiver that happens to agree with the
    transmitter's own idea of the frame format.
    """

    def __init__(self, name, parent):
        super().__init__(name, parent)
        self.dut = None
        self.cfg = None

    def build_phase(self, phase):
        super().build_phase(phase)
        arr = []
        if not UVMConfigDb.get(self, "", "dut", arr):
            self.uvm_report_fatal("NODUT", "dut handle not in config db")
        self.dut = arr[0]
        arr2 = []
        if not UVMConfigDb.get(self, "", "cfg", arr2):
            self.uvm_report_fatal("NOCFG", "cfg not in config db")
        self.cfg = arr2[0]

    async def run_phase(self, phase):
        dut = self.dut
        dut.rx.value = 1
        while True:
            item = await self.seq_item_port.get_next_item()
            bits = [0]                                   # start
            bits += [(item.data >> i) & 1 for i in range(8)]  # LSB first
            par = self.cfg.expected_parity(item.data)
            if par is not None:
                bits.append(par ^ (1 if item.corrupt == "parity" else 0))
            bits.append(0 if item.corrupt == "frame" else 1)   # stop 1
            if self.cfg.two_stop:
                bits.append(1)                                  # stop 2
            for b in bits:
                dut.rx.value = b
                for _ in range(BIT_CYCLES):
                    await RisingEdge(dut.clk)
            dut.rx.value = 1
            # One idle bit between frames so the receiver returns to IDLE
            # before the next start edge.
            for _ in range(BIT_CYCLES):
                await RisingEdge(dut.clk)
            self.seq_item_port.item_done()


uvm_component_utils(UartSerialDriver)


class UartSerialMonitor(UVMMonitor):
    """Decodes frames off a serial line. The line to watch is a config
    field ('rx' or 'tx'), which is what lets one class serve both the
    active rx agent and the passive tx agent."""

    def __init__(self, name, parent):
        super().__init__(name, parent)
        self.dut = None
        self.cfg = None
        self.line = "tx"
        self.ap = UVMAnalysisPort("ap", self)
        self.count = 0

    def build_phase(self, phase):
        super().build_phase(phase)
        arr = []
        if not UVMConfigDb.get(self, "", "dut", arr):
            self.uvm_report_fatal("NODUT", "dut handle not in config db")
        self.dut = arr[0]
        arr2 = []
        if not UVMConfigDb.get(self, "", "cfg", arr2):
            self.uvm_report_fatal("NOCFG", "cfg not in config db")
        self.cfg = arr2[0]
        arr3 = []
        if UVMConfigDb.get(self, "", "line", arr3):
            self.line = arr3[0]

    def _sig(self):
        return getattr(self.dut, self.line)

    async def _cycles(self, n):
        for _ in range(n):
            await RisingEdge(self.dut.clk)

    async def run_phase(self, phase):
        sig = self._sig()
        prev = 1
        while True:
            await RisingEdge(self.dut.clk)
            try:
                cur = int(sig.value)
            except ValueError:
                continue
            if not (prev == 1 and cur == 0):
                prev = cur
                continue
            prev = cur
            # Falling edge = candidate start bit. Move to mid-start-bit
            # and confirm, mirroring the DUT's own glitch rejection.
            await self._cycles(BIT_CYCLES // 2)
            if int(sig.value) != 0:
                continue
            item = UartFrameItem("decoded")
            data = 0
            for i in range(8):
                await self._cycles(BIT_CYCLES)
                data |= (int(sig.value) & 1) << i
            item.data = data
            exp_par = self.cfg.expected_parity(data)
            if exp_par is not None:
                await self._cycles(BIT_CYCLES)
                item.parity_bit = int(sig.value) & 1
                item.parity_ok = (item.parity_bit == exp_par)
            await self._cycles(BIT_CYCLES)
            item.stop_ok = (int(sig.value) & 1) == 1
            if self.cfg.two_stop:
                await self._cycles(BIT_CYCLES)
                item.stop_ok = item.stop_ok and ((int(sig.value) & 1) == 1)
            self.count += 1
            self.ap.write(item)
            prev = 1


uvm_component_utils(UartSerialMonitor)


class UartSerialAgent(UVMAgent):
    """ACTIVE  -> sequencer + driver + monitor (used on the rx input)
       PASSIVE -> monitor only               (used on the tx output)

    The passive instance builds no sequencer and no driver at all; there
    is nothing on a DUT output for a driver to do, and creating one would
    be a contention bug waiting to happen.
    """

    def __init__(self, name, parent):
        super().__init__(name, parent)
        self.sequencer = None
        self.driver = None
        self.monitor = None
        self.is_active = False

    def build_phase(self, phase):
        super().build_phase(phase)
        arr = []
        if UVMConfigDb.get(self, "", "is_active", arr):
            self.is_active = bool(arr[0])
        self.monitor = UartSerialMonitor.type_id.create("monitor", self)
        if self.is_active:
            self.sequencer = UVMSequencer.type_id.create("sequencer", self)
            self.driver = UartSerialDriver.type_id.create("driver", self)

    def connect_phase(self, phase):
        super().connect_phase(phase)
        if self.is_active:
            self.driver.seq_item_port.connect(self.sequencer.seq_item_export)
        else:
            # A runtime assertion, not a comment: prove the passive agent
            # really did not build a driver or sequencer. progress.md has
            # carried "the active/passive distinction itself is not yet
            # exercised" since 2026-09-06 and a flag that is merely set is
            # not an exercise of it.
            assert self.driver is None and self.sequencer is None, \
                "passive agent must not build a driver or sequencer"


uvm_component_utils(UartSerialAgent)


# ---------------------------------------------------------------------
# Reference-model scoreboard
# ---------------------------------------------------------------------
class UartScoreboard(UVMScoreboard):
    """Predicts the DUT from first principles and checks all three views.

    Three prediction paths:
      1. register write to TX_DATA -> a frame must appear on `tx`
         carrying that byte. Checked against the PASSIVE tx agent.
      2. a frame observed on `rx` -> its byte must come back from a
         RX_DATA read, in order. Checked against the register monitor.
      3. a frame observed on `rx` with bad parity or a low stop bit ->
         the corresponding STATUS error bit must be set at the next
         STATUS read, and CLEARED by that read (sticky, read-to-clear).

    Path 3 is the one that matters most for this repo: the verification
    plan calls STATUS "live", the RTL implements the error bits sticky,
    and a scoreboard written to the plan's wording would mispredict every
    STATUS read. This is independent evidence for the vplan v2 revision.
    """

    def __init__(self, name, parent):
        super().__init__(name, parent)
        self.reg_export = UVMAnalysisImpReg("reg_export", self)
        self.rx_export = UVMAnalysisImpRx("rx_export", self)
        self.tx_export = UVMAnalysisImpTx("tx_export", self)
        self.cfg = None
        self.exp_tx = deque()      # bytes written to TX_DATA, awaiting tx
        self.exp_rx = deque()      # bytes seen on rx, awaiting RX_DATA read
        self.pend_parity_err = False
        self.pend_frame_err = False
        self.checks = 0
        self.errors = 0

    def build_phase(self, phase):
        super().build_phase(phase)
        arr = []
        if not UVMConfigDb.get(self, "", "cfg", arr):
            self.uvm_report_fatal("NOCFG", "cfg not in config db")
        self.cfg = arr[0]

    def _check(self, ok, msg):
        self.checks += 1
        if ok:
            self.uvm_report_info("SB_PASS", msg)
        else:
            self.errors += 1
            self.uvm_report_error("SB_FAIL", msg)

    # --- from the register monitor -----------------------------------
    def write_reg(self, item):
        if item.is_write and item.addr == ADDR_TX:
            self.exp_tx.append(item.data & 0xFF)
            return
        if not item.is_write and item.addr == ADDR_RX:
            if not self.exp_rx:
                self._check(False, f"RX_DATA read 0x{item.rdata:02x} with "
                                   f"nothing predicted in the RX FIFO")
                return
            exp = self.exp_rx.popleft()
            self._check(item.rdata == exp,
                        f"RX_DATA read: expected 0x{exp:02x}, "
                        f"got 0x{item.rdata:02x}")
            return
        if not item.is_write and item.addr == ADDR_STATUS:
            got_par = bool((item.rdata >> ST_PARITY_ERR) & 1)
            got_frm = bool((item.rdata >> ST_FRAME_ERR) & 1)
            self._check(got_par == self.pend_parity_err,
                        f"STATUS.parity_err: expected "
                        f"{int(self.pend_parity_err)}, got {int(got_par)}")
            self._check(got_frm == self.pend_frame_err,
                        f"STATUS.frame_err: expected "
                        f"{int(self.pend_frame_err)}, got {int(got_frm)}")
            # Read-to-clear: the model must clear here, or every later
            # STATUS read mispredicts. This line is the vplan v2 issue.
            self.pend_parity_err = False
            self.pend_frame_err = False

    # --- from the ACTIVE rx agent's monitor ---------------------------
    def write_rx(self, item):
        # Every frame is pushed to the RX FIFO by this RTL, error or not
        # (rtl/uart_controller.v: errors are flagged, the byte is still
        # queued unless the FIFO is full).
        self.exp_rx.append(item.data & 0xFF)
        if not item.parity_ok:
            self.pend_parity_err = True
        if not item.stop_ok:
            self.pend_frame_err = True

    # --- from the PASSIVE tx agent's monitor --------------------------
    def write_tx(self, item):
        if not self.exp_tx:
            self._check(False, f"unexpected tx frame 0x{item.data:02x}")
            return
        exp = self.exp_tx.popleft()
        self._check(item.data == exp,
                    f"tx frame: expected 0x{exp:02x}, got 0x{item.data:02x}")
        self._check(item.parity_ok,
                    f"tx frame 0x{item.data:02x} parity bit correct "
                    f"(got {item.parity_bit}, expected "
                    f"{self.cfg.expected_parity(item.data)})")
        self._check(item.stop_ok,
                    f"tx frame 0x{item.data:02x} stop bit high")

    def report_phase(self, phase):
        super().report_phase(phase)
        leftover = len(self.exp_tx) + len(self.exp_rx)
        if leftover:
            self.errors += 1
            self.uvm_report_error(
                "SB_DRAIN",
                f"{len(self.exp_tx)} predicted tx frame(s) and "
                f"{len(self.exp_rx)} predicted rx byte(s) never appeared")
        self.uvm_report_info(
            "SB_SUMMARY",
            f"scoreboard: checks={self.checks} errors={self.errors}")


uvm_component_utils(UartScoreboard)


# ---------------------------------------------------------------------
# Functional coverage collector
# ---------------------------------------------------------------------
class UartCoverage(UVMComponent):
    """Coverpoints and one cross, sampled off the same analysis ports the
    scoreboard uses. Deliberately hand-rolled bins rather than a coverage
    library: the point of the exercise is the features->coverpoints chain
    from the verification plan, and a self-contained implementation is
    also checkable here (report_phase asserts the target)."""

    TARGET = 100.0

    def __init__(self, name, parent):
        super().__init__(name, parent)
        self.reg_export = UVMAnalysisImpReg("cov_reg_export", self)
        self.rx_export = UVMAnalysisImpRx("cov_rx_export", self)
        self.tx_export = UVMAnalysisImpTx("cov_tx_export", self)
        self.cfg = None
        self.bins = {
            "cp_parity_mode": {"none": 0, "even": 0, "odd": 0},
            "cp_stop_bits": {"one": 0, "two": 0},
            "cp_tx_data": {"zero": 0, "low": 0, "mid": 0, "high": 0, "ones": 0},
            "cp_rx_error": {"clean": 0, "parity": 0, "frame": 0},
            "cp_reg_access": {"wr_ctrl": 0, "wr_baud": 0, "wr_int": 0,
                              "wr_txdata": 0, "rd_status": 0, "rd_rxdata": 0},
        }
        self.cross = {}   # (parity_mode, rx_error) -> count

    def build_phase(self, phase):
        super().build_phase(phase)
        arr = []
        if not UVMConfigDb.get(self, "", "cfg", arr):
            self.uvm_report_fatal("NOCFG", "cfg not in config db")
        self.cfg = arr[0]

    @staticmethod
    def _data_bin(d):
        if d == 0x00:
            return "zero"
        if d == 0xFF:
            return "ones"
        if d < 0x40:
            return "low"
        if d < 0xC0:
            return "mid"
        return "high"

    def _parity_name(self):
        return {PARITY_NONE: "none", PARITY_EVEN: "even",
                PARITY_ODD: "odd"}[self.cfg.parity_mode]

    def write_reg(self, item):
        key = None
        if item.is_write:
            key = {ADDR_CTRL: "wr_ctrl", ADDR_BAUD: "wr_baud",
                   ADDR_INT: "wr_int", ADDR_TX: "wr_txdata"}.get(item.addr)
        else:
            key = {ADDR_STATUS: "rd_status",
                   ADDR_RX: "rd_rxdata"}.get(item.addr)
        if key:
            self.bins["cp_reg_access"][key] += 1
        if item.is_write and item.addr == ADDR_CTRL:
            # Sample the configuration actually programmed into the DUT.
            pm = (item.data >> 1) & 0x3
            name = {0: "none", 1: "even", 2: "odd"}.get(pm)
            if name:
                self.bins["cp_parity_mode"][name] += 1
            self.bins["cp_stop_bits"]["two" if (item.data >> 3) & 1
                                      else "one"] += 1
        if item.is_write and item.addr == ADDR_TX:
            self.bins["cp_tx_data"][self._data_bin(item.data & 0xFF)] += 1

    def write_rx(self, item):
        if not item.parity_ok:
            kind = "parity"
        elif not item.stop_ok:
            kind = "frame"
        else:
            kind = "clean"
        self.bins["cp_rx_error"][kind] += 1
        k = (self._parity_name(), kind)
        self.cross[k] = self.cross.get(k, 0) + 1

    def write_tx(self, item):
        pass  # tx frames are checked, not covered; tx_data covers the stimulus

    def coverage_percent(self):
        total = hit = 0
        for cp in self.bins.values():
            for v in cp.values():
                total += 1
                hit += 1 if v else 0
        return 100.0 * hit / total if total else 0.0

    def report_phase(self, phase):
        super().report_phase(phase)
        lines = []
        for cpname, cp in self.bins.items():
            got = sum(1 for v in cp.values() if v)
            lines.append(f"  {cpname:<16} {got}/{len(cp)} bins hit  "
                         + " ".join(f"{k}={v}" for k, v in cp.items()))
        pct = self.coverage_percent()
        crosses = " ".join(f"{a}/{b}={n}" for (a, b), n in
                           sorted(self.cross.items()))
        self.uvm_report_info(
            "COVERAGE",
            "functional coverage\n" + "\n".join(lines)
            + f"\n  cross(parity_mode x rx_error): {crosses}"
            + f"\n  TOTAL bin coverage: {pct:.1f}% (target {self.TARGET:.0f}%)")
        if pct < self.TARGET:
            missing = [f"{cpn}.{b}" for cpn, cp in self.bins.items()
                       for b, v in cp.items() if not v]
            self.uvm_report_error(
                "COV_TARGET",
                f"coverage {pct:.1f}% below target {self.TARGET:.0f}%; "
                f"unhit bins: {', '.join(missing)}")


uvm_component_utils(UartCoverage)


# ---------------------------------------------------------------------
# Sequences
# ---------------------------------------------------------------------
class UartConfigSeq(UVMSequence):
    """Programs BAUD_DIV, INT_EN and CTRL, and updates the shared cfg
    object in lockstep so monitors and scoreboard decode the same frame
    format the DUT is about to use."""

    def __init__(self, name="UartConfigSeq"):
        super().__init__(name)
        self.cfg = None
        self.parity_mode = PARITY_EVEN
        self.two_stop = False

    async def _wr(self, addr, data):
        item = UartRegItem("cfg_wr")
        item.is_write = True
        item.addr = addr
        item.data = data
        await self.start_item(item)
        await self.finish_item(item)

    async def body(self):
        await self._wr(ADDR_BAUD, BAUD_DIV)
        await self._wr(ADDR_INT, 0b011)          # tx_empty + rx_avail enables
        ctrl = 1 | (self.parity_mode << 1) | ((1 if self.two_stop else 0) << 3)
        await self._wr(ADDR_CTRL, ctrl)
        self.cfg.parity_mode = self.parity_mode
        self.cfg.two_stop = self.two_stop


uvm_object_utils(UartConfigSeq)


class UartTxSeq(UVMSequence):
    """Register-side stimulus: write bytes to TX_DATA. Kept at or below
    the 8-entry TX FIFO depth so nothing is dropped -- FIFO-overflow
    behaviour is a separate test, not a silent side effect of this one."""

    def __init__(self, name="UartTxSeq"):
        super().__init__(name)
        self.data_list = [0x00, 0x3C, 0xA5, 0xFF]

    async def body(self):
        for d in self.data_list:
            item = UartRegItem("tx_wr")
            item.is_write = True
            item.addr = ADDR_TX
            item.data = d
            await self.start_item(item)
            await self.finish_item(item)


uvm_object_utils(UartTxSeq)


class UartRxFrameSeq(UVMSequence):
    """Serial-side stimulus: clean frames plus one deliberate parity
    defect and one deliberate framing defect, to prove the error paths
    are actually reachable rather than assumed dead."""

    def __init__(self, name="UartRxFrameSeq"):
        super().__init__(name)
        self.frames = [(0x5A, None), (0x01, None), (0x7E, "parity"),
                       (0xC3, "frame")]

    async def body(self):
        for data, corrupt in self.frames:
            item = UartFrameItem("rx_frame")
            item.data = data
            item.corrupt = corrupt
            await self.start_item(item)
            await self.finish_item(item)


uvm_object_utils(UartRxFrameSeq)


class UartDrainSeq(UVMSequence):
    """Reads the RX FIFO empty, then reads STATUS TWICE.

    The second read is not redundant. The first read checks that the
    error bits were SET; only the second checks that the first read
    CLEARED them. Mutation testing on 2026-09-18 proved the difference is
    real: with a single STATUS read, an RTL mutant with read-to-clear
    deleted entirely SURVIVED the whole regression, because every run
    injects fresh errors before its one STATUS read, so a bit that never
    clears is indistinguishable from one that is re-set. Two reads kill
    that mutant. "The bit is set when it should be" and "the bit is
    cleared when it should be" are two checks, and a sticky register
    needs both.
    """

    def __init__(self, name="UartDrainSeq"):
        super().__init__(name)
        self.n = 4

    async def body(self):
        for _ in range(self.n):
            item = UartRegItem("rx_rd")
            item.is_write = False
            item.addr = ADDR_RX
            await self.start_item(item)
            await self.finish_item(item)
        for tag in ("status_rd_errors", "status_rd_cleared"):
            st = UartRegItem(tag)
            st.is_write = False
            st.addr = ADDR_STATUS
            await self.start_item(st)
            await self.finish_item(st)


uvm_object_utils(UartDrainSeq)


class UartVirtualSequencer(UVMSequencer):
    """Holds handles to the two real sequencers. A virtual sequencer runs
    no items of its own; it exists so one sequence can coordinate
    stimulus across independent agents."""

    def __init__(self, name, parent):
        super().__init__(name, parent)
        self.reg_seqr = None
        self.serial_seqr = None


uvm_component_utils(UartVirtualSequencer)


class UartFullDuplexVSeq(UVMSequence):
    """The virtual sequence: configure, then run register-side TX and
    serial-side RX stimulus CONCURRENTLY on two different sequencers, then
    drain. The concurrency is the point -- the DUT transmits and receives
    at the same time, which back-to-back sequences would never produce."""

    def __init__(self, name="UartFullDuplexVSeq"):
        super().__init__(name)
        self.cfg = None
        self.parity_mode = PARITY_EVEN
        self.two_stop = False
        self.tx_data = [0x00, 0x3C, 0xA5, 0xFF]
        self.rx_frames = [(0x5A, None), (0x01, None), (0x7E, "parity"),
                          (0xC3, "frame")]

    async def body(self):
        # uvm-python names the running sequencer handle `m_sequencer`
        # (the UVM 1.2 field name), reachable via get_sequencer(); there
        # is no `self.sequencer` property as there is in some SV
        # code bases. Going through the accessor is what makes this a
        # real virtual sequence rather than a sequence handed a
        # pre-wired pointer by the test.
        vseqr = self.get_sequencer()
        assert isinstance(vseqr, UartVirtualSequencer), \
            "virtual sequence must be started on the virtual sequencer"
        cfg_seq = UartConfigSeq.type_id.create("cfg_seq")
        cfg_seq.cfg = self.cfg
        cfg_seq.parity_mode = self.parity_mode
        cfg_seq.two_stop = self.two_stop
        await cfg_seq.start(vseqr.reg_seqr)

        tx_seq = UartTxSeq.type_id.create("tx_seq")
        tx_seq.data_list = self.tx_data
        rx_seq = UartRxFrameSeq.type_id.create("rx_seq")
        rx_seq.frames = self.rx_frames

        tx_task = cocotb.start_soon(tx_seq.start(vseqr.reg_seqr))
        rx_task = cocotb.start_soon(rx_seq.start(vseqr.serial_seqr))
        await tx_task
        await rx_task

        # Let the last transmitted frame and the last received frame
        # finish on the wire before draining.
        drain_seq = UartDrainSeq.type_id.create("drain_seq")
        drain_seq.n = len(self.rx_frames)
        await drain_seq.start(vseqr.reg_seqr)


uvm_object_utils(UartFullDuplexVSeq)


# ---------------------------------------------------------------------
# Environment and test
# ---------------------------------------------------------------------
class UartEnv(UVMEnv):
    def __init__(self, name, parent):
        super().__init__(name, parent)
        self.reg_agent = None
        self.rx_agent = None
        self.tx_agent = None
        self.scoreboard = None
        self.coverage = None
        self.vseqr = None

    def build_phase(self, phase):
        super().build_phase(phase)
        # Per-instance configuration: the rx agent is ACTIVE (it drives a
        # DUT input), the tx agent is PASSIVE (tx is a DUT output).
        UVMConfigDb.set(self, "reg_agent", "is_active", 1)
        UVMConfigDb.set(self, "rx_agent", "is_active", 1)
        UVMConfigDb.set(self, "rx_agent*", "line", "rx")
        UVMConfigDb.set(self, "tx_agent", "is_active", 0)
        UVMConfigDb.set(self, "tx_agent*", "line", "tx")

        self.reg_agent = UartRegAgent.type_id.create("reg_agent", self)
        self.rx_agent = UartSerialAgent.type_id.create("rx_agent", self)
        self.tx_agent = UartSerialAgent.type_id.create("tx_agent", self)
        self.scoreboard = UartScoreboard.type_id.create("scoreboard", self)
        self.coverage = UartCoverage.type_id.create("coverage", self)
        self.vseqr = UartVirtualSequencer.type_id.create("vseqr", self)

    def connect_phase(self, phase):
        super().connect_phase(phase)
        self.reg_agent.monitor.ap.connect(self.scoreboard.reg_export)
        self.rx_agent.monitor.ap.connect(self.scoreboard.rx_export)
        self.tx_agent.monitor.ap.connect(self.scoreboard.tx_export)
        self.reg_agent.monitor.ap.connect(self.coverage.reg_export)
        self.rx_agent.monitor.ap.connect(self.coverage.rx_export)
        self.tx_agent.monitor.ap.connect(self.coverage.tx_export)
        # Wire the virtual sequencer to the two real ones.
        self.vseqr.reg_seqr = self.reg_agent.sequencer
        self.vseqr.serial_seqr = self.rx_agent.sequencer
        assert self.vseqr.reg_seqr is not None
        assert self.vseqr.serial_seqr is not None


uvm_component_utils(UartEnv)


class UartMilestoneTest(UVMTest):
    """Runs the full-duplex virtual sequence under three different frame
    formats, which is what drives the parity/stop coverpoints to 100%
    rather than leaving five bins permanently dark."""

    CONFIGS = [
        (PARITY_NONE, False),
        (PARITY_EVEN, False),
        (PARITY_ODD, True),
    ]
    TX_DATA = [0x00, 0x3C, 0xA5, 0xD2, 0xFF]
    RX_FRAMES = [(0x5A, None), (0x01, None), (0x7E, "parity"), (0xC3, "frame")]

    def __init__(self, name="UartMilestoneTest", parent=None):
        super().__init__(name, parent)
        self.env = None
        self.dut = None
        self.cfg = None

    def build_phase(self, phase):
        super().build_phase(phase)
        self.env = UartEnv.type_id.create("env", self)
        arr = []
        if not UVMConfigDb.get(self, "", "dut", arr):
            self.uvm_report_fatal("NODUT", "dut handle not in config db")
        self.dut = arr[0]
        arr2 = []
        UVMConfigDb.get(self, "", "cfg", arr2)
        self.cfg = arr2[0]

    async def run_phase(self, phase):
        phase.raise_objection(self)
        dut = self.dut
        dut.rst_n.value = 0
        dut.psel.value = 0
        dut.penable.value = 0
        dut.pwrite.value = 0
        dut.paddr.value = 0
        dut.pwdata.value = 0
        dut.rx.value = 1
        for _ in range(8):
            await RisingEdge(dut.clk)
        dut.rst_n.value = 1
        await RisingEdge(dut.clk)

        for i, (parity, two_stop) in enumerate(self.CONFIGS):
            self.uvm_report_info(
                "TEST",
                f"--- run {i + 1}/{len(self.CONFIGS)}: parity="
                f"{['none', 'even', 'odd'][parity]} "
                f"stop={'2' if two_stop else '1'} ---")
            vseq = UartFullDuplexVSeq.type_id.create(f"vseq{i}")
            vseq.cfg = self.cfg
            vseq.parity_mode = parity
            vseq.two_stop = two_stop
            vseq.tx_data = list(self.TX_DATA)
            vseq.rx_frames = list(self.RX_FRAMES)
            await vseq.start(self.env.vseqr)
            # Drain the TX side: the register writes finish long before the
            # bytes leave the wire, so the scoreboard's tx predictions are
            # still outstanding here. Wait for the full FIFO to shift out
            # plus margin, otherwise report_phase would flag a false
            # "predicted frame never appeared".
            frames = len(self.TX_DATA) + 2
            for _ in range(frames * self.cfg.frame_bits() * BIT_CYCLES):
                await RisingEdge(dut.clk)

        phase.drop_objection(self)

    def report_phase(self, phase):
        super().report_phase(phase)
        sb = self.env.scoreboard
        cov = self.env.coverage
        rx_seen = self.env.rx_agent.monitor.count
        tx_seen = self.env.tx_agent.monitor.count
        self.uvm_report_info(
            "TEST_SUMMARY",
            f"\n  rx frames decoded : {rx_seen}"
            f"\n  tx frames decoded : {tx_seen}"
            f"\n  scoreboard checks : {sb.checks}"
            f"\n  scoreboard errors : {sb.errors}"
            f"\n  functional cover  : {cov.coverage_percent():.1f}%"
            f"\n  active agents     : reg_agent, rx_agent"
            f"\n  passive agents    : tx_agent (no driver, no sequencer)")
        # Runtime assertions, not log lines: a testbench that ran but
        # observed nothing must fail rather than report a clean pass.
        if rx_seen == 0 or tx_seen == 0:
            self.uvm_report_error("NO_ACTIVITY",
                                  "a monitor decoded zero frames")
        if sb.checks == 0:
            self.uvm_report_error("NO_CHECKS", "scoreboard made no checks")

        # ------------------------------------------------------------------
        # MAKE UVM ERRORS FAIL THE REGRESSION.
        #
        # This is not boilerplate. Without it this testbench reports
        # "TESTS=1 PASS=1 FAIL=0" even while the scoreboard is printing
        # UVM_ERROR lines, because cocotb's pass/fail verdict comes from
        # whether the test coroutine raised -- it has no knowledge of the
        # UVM report server's severity counts. The first mutation test run
        # against this file (2026-09-18) hit exactly that: an RTL mutant
        # with inverted TX parity was correctly DETECTED by the scoreboard
        # and still recorded as a passing regression.
        #
        # This is the same class of defect as the 2026-09-17 finding (a
        # testbench that passed 55/55 against deliberately broken RTL),
        # arriving by a different route: there the checks never ran, here
        # they ran, failed, and the verdict ignored them. A green
        # regression that contains UVM_ERRORs is worse than a red one.
        #
        # report_phase executes bottom-up, so uvm_test_top's runs after
        # every child's -- the scoreboard's and the coverage collector's
        # errors are already counted by the time this line executes.
        # ------------------------------------------------------------------
        svr = UVMCoreService.get().get_report_server()
        n_err = svr.get_severity_count(UVM_ERROR)
        n_fatal = svr.get_severity_count(UVM_FATAL)
        self.uvm_report_info(
            "VERDICT", f"UVM_ERROR={n_err} UVM_FATAL={n_fatal}")
        assert n_err == 0 and n_fatal == 0, (
            f"regression FAILED: {n_err} UVM_ERROR and {n_fatal} UVM_FATAL "
            f"reported (scoreboard errors={sb.errors}); see the log above")


uvm_component_utils(UartMilestoneTest)


@cocotb.test()
async def test_uart_uvm_milestone(dut):
    cocotb.start_soon(Clock(dut.clk, CLK_NS, units="ns").start())
    cfg = UartCfg()
    UVMConfigDb.set(None, "*", "dut", dut)
    UVMConfigDb.set(None, "*", "cfg", cfg)
    await run_test("UartMilestoneTest")
