"""
examples/phase6_uvm_checker_bind/uart_uvm_checker_bind_tb.py

THE PROTOCOL CHECKER, BOUND INTO THE uvm-python ENVIRONMENT.

Closes the item ranked first in the 2026-10-29 log entry: "BIND THE CHECKER
INTO THE uvm-python ENVIRONMENT -- ranked first, the direct continuation,
blocked only on running tools/setup_cocotb.sh".  The blocker was real and is
gone: the stack installed and verified today in a single shell call
(tools/setup_cocotb.sh, RESULT: PASS, 12/12).

===========================================================================
THE ONE DESIGN DECISION THAT MATTERS: THE STIMULUS IS IMPORTED, NOT COPIED
===========================================================================
The constrained-random environment already exists, in
examples/phase6_uvm_crv_uart/uart_uvm_crv_tb.py: a UartCrvSequence on a real
sequencer, a register driver, a bus monitor, a reference-model scoreboard and
a coverage collector, run over N_SEEDS x {steer=0, steer=1} inside one
elaboration.  This file IMPORTS that module and subclasses its test.  It does
not copy it, and the reason is not economy:

  A CHECKER BOUND TO A COPY OF THE STIMULUS CANNOT BE COMPARED WITH THE
  ORIGINAL.  The whole value of binding the checker into the CRV environment
  is the claim "these fifteen rules hold under the constrained-random
  stimulus this repository already runs".  If the stimulus were copied, that
  claim would be about a fork, and the fork would drift -- silently, since
  both would stay green.  Importing makes the claim checkable by
  construction: there is one UartCrvSequence, and if it changes, this bench
  changes with it.

What this file adds to the imported test is exactly one component and one
verdict, described below.

===========================================================================
TWO SCORES, KEPT APART -- THE 2026-10-29 METHODOLOGY, NOW STRUCTURAL
===========================================================================
The 10-29 entry's strongest finding was about scoring: a mutant the testbench
catches and the checker misses says NOTHING about the checker, and M6 was
exactly that case -- CHECKER-MISS with zero TB failures, because the stimulus
never disabled TX while tx was low, so the mutant was equivalent to correct
RTL.  Keeping the two scores apart is what made that visible.

In the standalone Verilog bench that separation was a convention in a
scoring script.  Here it is structural: report_phase prints
UVM_CHECKER_VIOLATIONS and UVM_TB_RESULT as two independent lines, derived
from two independent sources (the bound checker's counters vs. the driver's
and scoreboard's error lists), and asserts on both with a message that names
which one failed.  run_mutation_tests.sh scores on the checker line alone.

===========================================================================
THE LIVENESS GUARD, AND WHY A BINDING NEEDS ONE
===========================================================================
A verdict channel that fails to resolve reports zero violations, and zero
violations is also what success looks like.  That is the "control that cannot
fail" shape this repository has now recorded four sessions running, and a
binding is an unusually easy place to build one: get the hierarchical path
wrong and the bench is green forever.

So the wrapper exports `chk_alive`, a free-running clock counter, and this
bench FAILS if it is zero or missing -- which separates "no violations" from
"read nothing".  CHECKER_UNEXERCISED is reported for the same reason one
level up: fifteen rules at zero violations is only evidence if the rules
evaluated.
"""

import os
import sys

import cocotb
from cocotb.clock import Clock

_HERE = os.path.dirname(os.path.abspath(__file__))
_CRV = os.path.join(os.path.dirname(_HERE), 'phase6_uvm_crv_uart')
if _CRV not in sys.path:
    sys.path.insert(0, _CRV)

# Imported as a MODULE, deliberately, not `from ... import *`.  A star import
# would pull the imported module's own @cocotb.test() object into this
# module's namespace, and cocotb discovers tests by scanning the namespace of
# the modules named in MODULE -- so the CRV test would be collected here as
# well and run twice against a TOPLEVEL it was not pointed at.
import uart_uvm_crv_tb as crv                                    # noqa: E402

from uvm.base.uvm_config_db import UVMConfigDb                   # noqa: E402
from uvm.base.uvm_component import UVMComponent                  # noqa: E402
from uvm.macros import uvm_component_utils                       # noqa: E402

RULE = '-' * 74

# The fifteen rule names, in the checker's own index order.  Duplicated from
# checkers/uart_protocol_checker.v's rule_name() function because a Verilog
# function cannot be called from cocotb -- and because the duplication is
# CHECKED rather than trusted: tools/checker_bind_port_audit.py --rules
# parses the Verilog case statement and fails if this list disagrees with it.
RULE_NAMES = [
    'A1 pready high in access phase',
    'A2 address/data stable in access',
    'A3 penable implies psel',
    'A4 unmapped read is 0x00',
    'A5 prdata stable in read access',
    'R1 tx high in reset',
    'R2 irq low in reset',
    'T1 tx high when disabled',
    'T2 start bit low at centre',
    'T3 parity matches data',
    'T4 stop bits high at centre',
    'T5 transitions on the bit grid',
    'T6 start bit in oversampler window',
    'S1 error bits are read-to-clear',
    'I1 irq low when masked',
]


def _read_int(dut, name):
    """Read an exported wrapper reg as an int, or None if it does not resolve.

    Returns None rather than 0 on a missing or unresolvable handle, because
    the whole point of the liveness guard is that 0 and "absent" must not be
    the same value.  `.value.integer` raises on a vector containing x/z, and
    an unassigned 32-bit reg is x at time 0, so that case is folded into None
    as well.
    """
    try:
        h = getattr(dut, name)
    except (AttributeError, Exception):            # noqa: B014
        return None
    try:
        return int(h.value)
    except Exception:
        return None


class UartProtocolCheckerShim(UVMComponent):
    """The bound checker's presence inside the UVM component tree.

    It drives nothing and samples nothing during the run -- the checker is a
    Verilog module watching the same pins, and duplicating its sampling in
    Python would be a second implementation to keep in step.  What this
    component owns is the VERDICT: reading the exported counters at
    check_phase, and holding the result for the test's report_phase.

    It is a UVMComponent rather than a free function so that the checker
    appears in the component tree at all.  An environment whose checker is
    invisible to `uvm_top.print_topology()` is one where nobody can see that
    the checker is or is not there, which is the reporting half of the same
    problem the liveness guard addresses numerically.
    """

    def __init__(self, name, parent):
        super().__init__(name, parent)
        self.dut = None
        self.alive = None
        self.total = None
        self.stable = None
        self.reconfig = None
        self.frames = None
        self.frames_reconfig = None
        self.rule_viol = None
        self.rule_eval = None
        self.rule_na = None

    def build_phase(self, phase):
        super().build_phase(phase)
        got = []
        if UVMConfigDb.get(self, "", "dut", got):
            self.dut = got[0]

    def sample_now(self):
        d = self.dut
        if d is None:
            return
        self.alive = _read_int(d, 'chk_alive')
        self.total = _read_int(d, 'chk_viol_total')
        self.stable = _read_int(d, 'chk_viol_stable')
        self.reconfig = _read_int(d, 'chk_viol_reconfig')
        self.frames = _read_int(d, 'chk_frames')
        self.frames_reconfig = _read_int(d, 'chk_frames_reconfig')
        self.rule_viol = _read_int(d, 'chk_rule_viol')
        self.rule_eval = _read_int(d, 'chk_rule_eval')
        self.rule_na = _read_int(d, 'chk_rule_na')

    def check_phase(self, phase):
        super().check_phase(phase)
        self.sample_now()

    # ---- the verdict, as data ------------------------------------------
    def resolved(self):
        return None not in (self.alive, self.total, self.stable,
                            self.reconfig, self.frames,
                            self.frames_reconfig, self.rule_viol,
                            self.rule_eval, self.rule_na)

    def live(self):
        return self.alive is not None and self.alive > 0

    def violated_rules(self):
        if self.rule_viol is None:
            return []
        return [i for i in range(len(RULE_NAMES))
                if (self.rule_viol >> i) & 1]

    def unexercised_rules(self):
        if self.rule_eval is None or self.rule_na is None:
            return []
        return [i for i in range(len(RULE_NAMES))
                if not ((self.rule_eval >> i) & 1)
                and not ((self.rule_na >> i) & 1)]

    def na_rules(self):
        if self.rule_na is None:
            return []
        return [i for i in range(len(RULE_NAMES)) if (self.rule_na >> i) & 1]

    def print_report(self):
        print()
        print(RULE)
        print('  BOUND PROTOCOL CHECKER (checkers/uart_protocol_checker.v,')
        print('  instantiated on the DUT pins by uart_checker_bind_top.v)')
        print(RULE)
        if not self.resolved():
            print('  VERDICT CHANNEL DID NOT RESOLVE.  One or more of')
            print('  chk_alive / chk_viol_total / chk_rule_viol /')
            print('  chk_rule_eval / chk_rule_na could not be read from the')
            print('  toplevel.  This is NOT a pass: a channel that reads')
            print('  nothing reports zero violations, which is what success')
            print('  looks like.')
            print('  UVM_CHECKER_ALIVE=%s' % self.alive)
            print('  UVM_CHECKER_VIOLATIONS=UNRESOLVED')
            print('  UVM_CHECKER_RESULT=FAIL')
            print(RULE)
            return
        viol = self.violated_rules()
        unex = self.unexercised_rules()
        na = self.na_rules()
        print('  %-40s %10s %10s' % ('rule', 'evaluated', 'violated'))
        for i, nm in enumerate(RULE_NAMES):
            ev = 'yes' if (self.rule_eval >> i) & 1 else 'NO'
            vi = 'YES' if (self.rule_viol >> i) & 1 else '.'
            tag = '   (N/A in v1 scope)' if i in na else ''
            print('  %-40s %10s %10s%s' % (nm, ev, vi, tag))
        print()
        print('  chk_alive is the wrapper\'s free-running clock-edge count;')
        print('  a zero would mean the channel read nothing rather than that')
        print('  there were no violations.')
        print('  UVM_CHECKER_ALIVE=%d' % self.alive)
        print('  UVM_CHECKER_FRAMES=%d' % self.frames)
        print('  UVM_CHECKER_FRAMES_RECONFIGURED=%d  (%.1f %% of frames: a'
              % (self.frames_reconfig,
                 100.0 * self.frames_reconfig / self.frames
                 if self.frames else 0.0))
        print('  frame during which CTRL or BAUD was written, so T3/T4/T5/T6')
        print('  evaluated against expectations latched from a configuration')
        print('  the DUT no longer had.  Counted and named, never dropped.)')
        print('  UVM_CHECKER_VIOLATIONS_TOTAL=%d' % self.total)
        print('  UVM_CHECKER_VIOLATIONS_RECONFIGURED=%d' % self.reconfig)
        print('  UVM_CHECKER_VIOLATIONS=%d' % self.stable)
        print('  UVM_CHECKER_UNEXERCISED=%d%s'
              % (len(unex),
                 ('  -> %s' % ', '.join(RULE_NAMES[i].split()[0]
                                        for i in unex)) if unex else ''))
        print('  UVM_CHECKER_NA=%d' % len(na))
        print('  (UVM_CHECKER_VIOLATIONS is the STABLE-frame count, which is')
        print('   the verdict: it is the rules\' own domain of validity.  The')
        print('   total and the reconfigured count are printed beside it so')
        print('   the exclusion is visible rather than inferred.)')
        print('  UVM_CHECKER_RESULT=%s'
              % ('PASS' if (not viol and self.live()) else 'FAIL'))
        print(RULE)


uvm_component_utils(UartProtocolCheckerShim)


class UartCheckerBindEnv(crv.UartEnv):
    """The imported environment plus the bound checker's shim."""

    def __init__(self, name, parent):
        super().__init__(name, parent)
        self.chk = None

    def build_phase(self, phase):
        super().build_phase(phase)
        self.chk = UartProtocolCheckerShim.type_id.create("chk", self)


uvm_component_utils(UartCheckerBindEnv)


class UartCheckerBindTest(crv.UartCrvTest):
    """The imported CRV test, with the checker's verdict added to its own.

    report_phase ORDER MATTERS and is not arbitrary.  The imported
    report_phase ends in an assert (via _tail), so anything placed after a
    bare super() call would not run on a testbench failure -- and the
    checker's verdict is most interesting precisely when something has gone
    wrong.  So: the checker reports FIRST and unconditionally, the imported
    report is then run with its assertion caught, and the final assertion
    names which of the two scores failed.  Neither score can mask the other.
    """

    def __init__(self, name="UartCheckerBindTest", parent=None):
        super().__init__(name, parent)

    def build_phase(self, phase):
        # Deliberately NOT super().build_phase(phase): the parent builds
        # crv.UartEnv, and this test needs the subclass that carries the
        # checker shim.  UVMTest.build_phase is reached through the
        # grandparent so the base class still gets its phase.
        crv.UVMTest.build_phase(self, phase)
        self.env = UartCheckerBindEnv.type_id.create("env", self)

    def report_phase(self, phase):
        chk = getattr(self.env, 'chk', None)
        if chk is not None:
            # check_phase has already run by here, but sample again: the
            # second read is free and makes a value that changed between the
            # phases visible rather than silently preferred.
            before = chk.stable
            chk.sample_now()
            if before is not None and chk.stable != before:
                print('  NOTE: checker stable count moved between check_phase '
                      'and report_phase: %s -> %s' % (before, chk.stable))
            chk.print_report()

        tb_error = None
        try:
            super().report_phase(phase)
        except AssertionError as exc:
            tb_error = str(exc) or 'assertion'
        print('  UVM_TB_RESULT=%s' % ('FAIL' if tb_error else 'PASS'))

        reasons = []
        if chk is None:
            reasons.append('the checker shim was not built')
        else:
            if not chk.resolved():
                reasons.append('the checker verdict channel did not resolve')
            elif not chk.live():
                reasons.append('chk_alive == 0: the checker saw no clock '
                               'edges, so a zero violation count is not '
                               'evidence')
            if chk.resolved() and chk.stable:
                reasons.append('%d protocol-checker violation(s) in STABLE '
                               'frames, in rules %s'
                               % (chk.stable,
                                  ', '.join(RULE_NAMES[i].split()[0]
                                            for i in chk.violated_rules())))
        if tb_error:
            reasons.append('testbench: %s' % tb_error)
        print('  UVM_BOUND_RESULT=%s' % ('FAIL' if reasons else 'PASS'))
        print(RULE)
        assert not reasons, '; '.join(reasons)


uvm_component_utils(UartCheckerBindTest)


@cocotb.test()
async def uart_uvm_checker_bind_test(dut):
    """Same clock, same config_db keys, same sequence -- one extra verdict."""
    import random
    run_test = crv.run_test
    cocotb.start_soon(Clock(dut.clk, 2, units="ns").start())
    cov = crv.CovModel()
    UVMConfigDb.set(None, "*", "dut", dut)
    UVMConfigDb.set(None, "*", "cov", cov)
    UVMConfigDb.set(None, "*", "rng", random.Random(1))
    await run_test("UartCheckerBindTest")
