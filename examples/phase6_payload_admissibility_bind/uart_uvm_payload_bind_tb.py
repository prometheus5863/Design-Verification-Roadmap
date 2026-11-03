"""
uart_uvm_payload_bind_tb.py -- the LIVE half of wiring the payload
admissibility model into the running UVM environment.

The item ranked first on 2026-10-28, 10-29, 10-30 and 11-02.  The STRUCTURAL
half is `payload_admissibility_audit.py` next to this file: it establishes,
over all 256 bytes and without a simulator, which `cp_data` bins have no
admissible witness under which exclusion rule.  This half answers the
question that audit cannot: WHAT DOES THE STIMULUS ACTUALLY DRIVE?

WHAT IS NEW HERE AND WHY IT NEEDED THE SIMULATOR
------------------------------------------------
The structural audit is a statement about the input SPACE.  A coverage model
is closed by the input SEQUENCE, and the two differ whenever the stimulus is
not uniform -- which is exactly what a coverage-STEERED policy is for.  The
11-02 entry wrote the prediction down before it could be tested:

    "The prediction worth testing: steer=1 is materially dirtier than
     steer=0, because the steering map drives 0x00 and 0xFF deliberately
     while the random policy draws them at 1/256 each -- a number that can
     come out wrong."

`uart_uvm_crv_tb.byte_for_class` is `[0x00, 0xFF, 0x08, 0xAA, 0x33, 0x07]`,
and `_steered_item` drives `byte_for_class(k)` for any unhit `cp_data` bin
`k`.  Bin 0 IS `0x00`, which is INADMISSIBLE under both rules, and bin 1 is
`0xFF`, which is admissible under the vplan rule and excluded under v9's.  So
a coverage-driven policy is structurally obliged to drive the very bytes that
cannot carry F7 evidence, because they are the only members of their bins.
That is the 11-02 conflict restated as a property of the STIMULUS rather than
of the coverage model, and it is why "steer closes faster" and "steer
produces interpretable frames" are not the same virtue.

HOW IT IS WIRED, AND WHAT IS NOT RE-TYPED
-----------------------------------------
`PayloadAdmissibilityCoverage` is a THIRD subscriber on `agent.mon.ap`,
alongside the scoreboard and `UartCoverage`.  It samples the same
observation; it does not reach into the driver's copy of what it meant to
send.  That matters here more than usual: the question is what the DUT was
actually shown, and a driver-side census would answer a different question
whenever a push is dropped on `tx_full` (the bench reports a nonzero
`pushes skipped` count, so this is not hypothetical).

Nothing is re-typed.  `classify`, `load_measured` and the class constants are
imported from `payload_coverage_model`; the nine-byte rule from
`reachable_cross_under_per_byte_rule`; `data_class` and `byte_for_class` are
lifted from the live bench's source by the same AST route the structural
audit uses; and the environment, sequence, driver, monitor and coverage model
are the live `uart_uvm_crv_tb` objects, subclassed only to add a subscriber.

ONE POLICY PER INVOCATION, AND WHY
----------------------------------
`uart_uvm_crv_tb` already supports `POLICIES=0` or `POLICIES=1`, and this
bench runs under that knob rather than instrumenting the parent's run loop.
Attributing bytes to a policy from inside a subscriber would mean either
duplicating `UartCrvTest.run_phase` -- the fork this repository keeps
refusing to create -- or reaching into it for a tag it does not publish.
Instead each invocation appends ONE machine-readable row to
`pac_results.csv`, and `summarize_admissibility.py` does the cross-policy
comparison over whatever rows exist.  Same resumable shape as
`closure_results.csv`, for the same reason: shell calls here are time-boxed.

THE EVIDENCE/SURVEY MODE, WHICH IS THE 11-02 DESIGN DECISION
------------------------------------------------------------
`PAC_MODE=survey` (the default) COUNTS inadmissible payloads and never
raises.  `PAC_MODE=evidence` RAISES on the first one.  The distinction is the
one the 11-02 entry settled: a coverage sweep is not F7 evidence, so it must
be allowed to drive `0x00`; an F7 measurement must not.  The positive control
(P5) exercises both halves of that gate deterministically, without the
simulator -- it must raise on `0x00` and must NOT raise on `0x01` -- because
a gate that is only ever observed not firing has not been shown to work.
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_EX = os.path.dirname(_HERE)
for _p in (os.path.join(_EX, 'phase4_uvm_milestone'),
           os.path.join(_EX, 'phase6_uvm_crv_uart'),
           _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import cocotb                                                   # noqa: E402
from cocotb.clock import Clock                                  # noqa: E402

# Same import surface as the live bench, so this file cannot drift from it.
from uvm import (                                                # noqa: E402
    UVMScoreboard, uvm_component_utils, uvm_analysis_imp_decl, run_test,
)
from uvm.base.uvm_config_db import UVMConfigDb                   # noqa: E402
from uvm.base.uvm_object_globals import UVM_LOW                  # noqa: E402

import random                                                    # noqa: E402

import payload_coverage_model as M                               # noqa: E402
import reachable_cross_under_per_byte_rule as R                  # noqa: E402
import uart_uvm_crv_tb as crv                                    # noqa: E402
import payload_admissibility_audit as AUD                        # noqa: E402

UVMAnalysisImpPac = uvm_analysis_imp_decl("_pac")

PAC_MODE = os.environ.get("PAC_MODE", "survey").lower()
PAC_RESULTS = os.environ.get("PAC_RESULTS", "pac_results.csv")

# The uniform-payload predictions this run is measured against.  Both are
# DERIVED below from the imported model, never typed in; the comments record
# what they come out as so a drift is visible in review.
#   vplan 2-byte rule : 2/256 = 0.78 % inadmissible, +2/256 borderline
#                       = 1.56 % not clean F7 evidence
#   v9 nine-byte rule : 9/256 = 3.52 % excluded


class AdmissibilityCensus(object):
    """The measurement itself, with no UVM in it.

    Factored out of the component deliberately.  The first version of this
    file put `sample_byte` on the `UVMScoreboard` subclass and built a second
    instance with `parent=None` for the P5 positive control; uvm-python
    rejects that with ILLCRT ("it is illegal to create a component") and the
    run died in `report_phase`.  The fix is the one worth having anyway: a
    census of 256 byte values has no business being a simulation component,
    and with it separated the evidence gate can be exercised by any plain
    python caller -- which is what makes P5 a real control rather than a
    second simulated run.
    """

    def __init__(self, mode=None):
        self.rows = M.load_measured()
        self.vplan_rule = set(b for b in self.rows
                              if M.classify(b, self.rows) == M.INADMISSIBLE)
        self.nine_rule = set(R.inadmissible_by_closed_form())
        self.data_class, self.byte_for_class = AUD.import_live_functions()
        self.mode = (mode or PAC_MODE)
        self.seen = 0
        self.by_rule = {
            'vplan': {M.ADMISSIBLE: 0, M.BORDERLINE: 0, M.INADMISSIBLE: 0},
            'v9': {M.ADMISSIBLE: 0, M.BORDERLINE: 0, M.INADMISSIBLE: 0},
        }
        self.per_bin = [0] * 6
        self.per_bin_inadm = [0] * 6
        self.byte_hist = {}
        self.raised = 0
        # PER-RUN SEGMENTS.  `UartCrvTest.run_phase` calls `cov.reset()` at
        # the top of every (seed, policy) run, so the live coverage model
        # holds only the LAST run while this census would otherwise
        # accumulate across all of them.  The first version of P1/P2 compared
        # the two directly and FAILED -- correctly, and for exactly that
        # reason.  The counters below are therefore per-segment, `snapshot()`
        # closes one, and `totals()` re-adds them, so the cumulative rates
        # and the exact per-run cross-check are both available and neither is
        # an approximation of the other.
        self.segments = []

    def _zero(self):
        self.seen = 0
        self.by_rule = {
            'vplan': {M.ADMISSIBLE: 0, M.BORDERLINE: 0, M.INADMISSIBLE: 0},
            'v9': {M.ADMISSIBLE: 0, M.BORDERLINE: 0, M.INADMISSIBLE: 0},
        }
        self.per_bin = [0] * 6
        self.per_bin_inadm = [0] * 6

    def snapshot(self):
        """Close the current segment.  Called on every `cov.reset()`."""
        if self.seen == 0:
            return
        self.segments.append(dict(
            seen=self.seen,
            by_rule={r: dict(v) for r, v in self.by_rule.items()},
            per_bin=list(self.per_bin),
            per_bin_inadm=list(self.per_bin_inadm)))
        self._zero()

    def totals(self):
        """Cumulative over every closed segment plus the open one."""
        seen = self.seen
        by_rule = {r: dict(v) for r, v in self.by_rule.items()}
        per_bin = list(self.per_bin)
        per_bin_inadm = list(self.per_bin_inadm)
        for seg in self.segments:
            seen += seg['seen']
            for r in by_rule:
                for k in by_rule[r]:
                    by_rule[r][k] += seg['by_rule'][r][k]
            for i in range(6):
                per_bin[i] += seg['per_bin'][i]
                per_bin_inadm[i] += seg['per_bin_inadm'][i]
        return seen, by_rule, per_bin, per_bin_inadm

    def classify_under(self, byte, rule):
        """INADMISSIBLE if the rule excludes it, else the model's own class.

        Same contract as the structural audit's `census`, and deliberately
        the same wording: a byte the rule excludes is not evidence at all,
        whatever `classify()` would say about it in isolation.
        """
        excl = self.vplan_rule if rule == 'vplan' else self.nine_rule
        if byte in excl:
            return M.INADMISSIBLE
        return M.classify(byte, self.rows)

    def sample_byte(self, byte):
        byte &= 0xFF
        self.seen += 1
        c = self.data_class(byte)
        self.per_bin[c] += 1
        self.byte_hist[byte] = self.byte_hist.get(byte, 0) + 1
        for rule in ('vplan', 'v9'):
            self.by_rule[rule][self.classify_under(byte, rule)] += 1
        if self.classify_under(byte, 'vplan') == M.INADMISSIBLE:
            self.per_bin_inadm[c] += 1
            if self.mode == 'evidence':
                self.raised += 1
                raise M.IllegalPayload(
                    "payload 0x%02X is INADMISSIBLE for F7 under the vplan "
                    "rule and PAC_MODE=evidence: the adaptive observer's "
                    "window does not contain the DUT's, so this frame "
                    "cannot carry F7 evidence" % byte)


class PayloadAdmissibilityCoverage(UVMScoreboard):
    """Third subscriber on `mon.ap`: hands every observed TX_DATA payload to
    an `AdmissibilityCensus`.  The component is the wiring; the census is the
    measurement."""

    def __init__(self, name, parent):
        super().__init__(name, parent)
        self.analysis_export = None
        self.census = AdmissibilityCensus()

    def build_phase(self, phase):
        super().build_phase(phase)
        self.analysis_export = UVMAnalysisImpPac("analysis_export", self)

    def write_pac(self, t):
        if t.write and t.addr == crv.ADDR_TX:
            self.census.sample_byte(t.data)


uvm_component_utils(PayloadAdmissibilityCoverage)


class ObservedCovModel(crv.CovModel):
    """The live coverage model with a reset notification.

    A subclass rather than a patched instance, and defined here rather than
    in `uart_uvm_crv_tb`, so the live bench is untouched and the hook exists
    only for runs that ask for it.  `reset()` is the one public event in the
    parent's run loop that marks a run boundary.
    """

    def __init__(self):
        # Before super().__init__(), which calls reset() itself -- the
        # listener list has to exist by then or the parent's own
        # constructor trips the hook.
        self.on_reset = []
        super().__init__()

    def reset(self):
        for cb in self.on_reset:
            cb()
        super().reset()


class PayloadBindEnv(crv.UartEnv):
    """The live env plus one subscriber.  Nothing else changes."""

    def __init__(self, name, parent):
        super().__init__(name, parent)
        self.pac = None

    def build_phase(self, phase):
        super().build_phase(phase)
        self.pac = PayloadAdmissibilityCoverage.type_id.create("pac", self)

    def connect_phase(self, phase):
        super().connect_phase(phase)
        self.agent.mon.ap.connect(self.pac.analysis_export)


uvm_component_utils(PayloadBindEnv)


class PayloadBindTest(crv.UartCrvTest):
    """`UartCrvTest` with the subscriber env, plus the admissibility report
    and its checks appended after the parent's own report."""

    def build_phase(self, phase):
        # Skip UartCrvTest.build_phase (it creates the plain UartEnv) and go
        # to UVMTest's, so there is exactly one env and it is ours.
        super(crv.UartCrvTest, self).build_phase(phase)
        self.env = PayloadBindEnv.type_id.create("env", self)

    async def run_phase(self, phase):
        # Register the segment hook before the parent's loop starts resetting
        # the model.  `connect_phase` is too early: the test does not hold the
        # CovModel until its own run_phase fetches it from the config db.
        a = []
        if UVMConfigDb.get(self, "", "cov", a) and hasattr(a[0], "on_reset"):
            a[0].on_reset.append(self.env.pac.census.snapshot)
        await super().run_phase(phase)

    # -- the checks ------------------------------------------------------
    def _pac_checks(self, pac):
        p, f = [], []

        def chk(label, ok, detail=""):
            (p if ok else f).append(label)
            print("  [%s] %s" % ("PASS" if ok else "FAIL", label))
            if detail:
                print("         %s" % detail)

        # P1: the subscriber and the coverage collector counted the SAME
        # pushes.  Two independent consumers of one analysis port; an
        # inequality means one of them is missing observations.
        chk("P1 the subscriber's LAST SEGMENT observed exactly as many "
            "TX_DATA pushes as UartCoverage counted",
            pac.seen == self.cov.pushes,
            "segment seen = %d, cov.pushes = %d, over %d runs totalling %d "
            "payloads.  Both are driven only by mon.ap, so a difference is "
            "a dropped observation rather than a disagreement about what a "
            "push is -- and the segmenting is what makes the comparison "
            "well posed at all, since cov is reset once per run."
            % (pac.seen, self.cov.pushes, len(pac.segments) + 1,
               pac.totals()[0]))

        # P2: EXACT, bin by bin, against the live collector's own cp_data
        # bins.  This is the strong one: it says the admissibility census is
        # indexed by the SAME coverpoint the steering reads, not by a lifted
        # copy that has drifted.
        live = list(self.cov.bins["data"])
        chk("P2 the LAST SEGMENT's per-bin payload census equals "
            "UartCoverage's cp_data bins EXACTLY, bin for bin",
            live == pac.per_bin,
            "UartCoverage %s vs subscriber %s.  data_class is lifted from "
            "the live source by AST rather than copied, so this equality is "
            "a check that the lift is of the function actually in use."
            % (live, pac.per_bin))

        # P5: the positive control on the evidence gate, run here so it does
        # not depend on an inadmissible byte happening to appear.
        probe = AdmissibilityCensus(mode='evidence')
        raised_on_00 = False
        try:
            probe.sample_byte(0x00)
        except M.IllegalPayload:
            raised_on_00 = True
        raised_on_01 = False
        try:
            probe.sample_byte(0x01)
        except M.IllegalPayload:
            raised_on_01 = True
        chk("P5 the evidence gate RAISES on 0x00 and does NOT raise on 0x01",
            raised_on_00 and not raised_on_01,
            "0x00 raised: %s; 0x01 raised: %s.  A gate observed only not "
            "firing has not been shown to work, and 0x01 is the byte with "
            "the WIDEST admissible window (g_first = 1, 50 %%), so it is the "
            "strongest available negative control."
            % (raised_on_00, raised_on_01))
        return p, f

    def report_phase(self, phase):
        super().report_phase(phase)
        pac = self.env.pac.census
        rule_pred = {
            'vplan': (len(pac.vplan_rule),
                      len([b for b in pac.rows
                           if M.classify(b, pac.rows) == M.BORDERLINE])),
            'v9': (len(pac.nine_rule), 0),
        }
        print()
        print(crv.RULE)
        print("PAYLOAD ADMISSIBILITY, LIVE -- what the stimulus actually "
              "drove")
        print(crv.RULE)
        print("  policy (POLICIES)        : %s"
              % ",".join(str(x) for x in crv.POLICIES))
        print("  seeds                    : %d (SEED_BASE=%d)"
              % (crv.N_SEEDS, crv.SEED_BASE))
        print("  mode                     : %s" % pac.mode)
        tot_seen, tot_by_rule, tot_per_bin, tot_per_bin_inadm = pac.totals()
        print("  runs (coverage resets)   : %d" % (len(pac.segments) + 1))
        print("  TX_DATA payloads observed: %d  (last run: %d)"
              % (tot_seen, pac.seen))
        print()
        print("  %-14s %-9s %-9s %-11s %-11s %s"
              % ("rule", "adm", "borderline", "inadm", "inadm rate",
                 "uniform prediction"))
        for rule in ('vplan', 'v9'):
            d = tot_by_rule[rule]
            n = max(tot_seen, 1)
            n_inadm, n_bord = rule_pred[rule]
            print("  %-14s %-9d %-9d %-11d %-11s %s"
                  % (rule, d[M.ADMISSIBLE], d[M.BORDERLINE],
                     d[M.INADMISSIBLE],
                     "%.3f %%" % (100.0 * d[M.INADMISSIBLE] / n),
                     "%.3f %% (%d/256)"
                     % (100.0 * n_inadm / 256.0, n_inadm)))
        n = max(tot_seen, 1)
        notclean = (tot_by_rule['vplan'][M.INADMISSIBLE]
                    + tot_by_rule['vplan'][M.BORDERLINE])
        print()
        print("  not clean F7 evidence (vplan: inadm + borderline): "
              "%d / %d = %.3f %%   [uniform: %.3f %%]"
              % (notclean, tot_seen, 100.0 * notclean / n,
                 100.0 * (rule_pred['vplan'][0] + rule_pred['vplan'][1])
                 / 256.0))
        print()
        print("  per cp_data bin: %-28s %s" % ("observed", "of which "
                                               "inadmissible (vplan)"))
        for c in range(6):
            print("    bin %d  %-16s %-12d %d"
                  % (c, AUD.BIN_NAMES[c], tot_per_bin[c],
                     tot_per_bin_inadm[c]))
        print()
        top = sorted(pac.byte_hist.items(), key=lambda kv: -kv[1])[:8]
        print("  most-driven payloads: %s"
              % ", ".join("0x%02X x%d" % (b, k) for b, k in top))
        print()
        pp, ff = self._pac_checks(pac)
        print()
        print("  PAC CHECKS: %d/%d passing" % (len(pp), len(pp) + len(ff)))

        with open(PAC_RESULTS, "a") as fh:
            fh.write("%s,%d,%d,%s,%d,%d,%d,%d,%d,%d,%d,%s\n"
                     % (",".join(str(x) for x in crv.POLICIES),
                        crv.N_SEEDS, crv.SEED_BASE, pac.mode, tot_seen,
                        tot_by_rule['vplan'][M.ADMISSIBLE],
                        tot_by_rule['vplan'][M.BORDERLINE],
                        tot_by_rule['vplan'][M.INADMISSIBLE],
                        tot_by_rule['v9'][M.ADMISSIBLE],
                        tot_by_rule['v9'][M.BORDERLINE],
                        tot_by_rule['v9'][M.INADMISSIBLE],
                        ":".join(str(x) for x in tot_per_bin)))
        print("  appended one row to %s" % PAC_RESULTS)
        if ff:
            self.uvm_report_error("PAC", "payload admissibility checks "
                                  "FAILED: %s" % "; ".join(ff), UVM_LOW)


uvm_component_utils(PayloadBindTest)


@cocotb.test()
async def uart_uvm_payload_bind_test(dut):
    cocotb.start_soon(Clock(dut.clk, 2, units="ns").start())
    cov = ObservedCovModel()
    UVMConfigDb.set(None, "*", "dut", dut)
    UVMConfigDb.set(None, "*", "cov", cov)
    UVMConfigDb.set(None, "*", "rng", random.Random(1))
    await run_test("PayloadBindTest")
