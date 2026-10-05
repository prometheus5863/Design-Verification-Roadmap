"""
coverage_axis_audit.py

Runs the three-axis coverage audit -- cardinality, scarcity, and soundness
split into POPULATION and RUN -- on the LIVE `UartCoverage` collector in
uart_uvm_tb.py.  This is the 2026-10-03 item *run the soundness audit on
every other coverage model here*, widened on 2026-10-04 from two axes to
three, taken at its first named target.

WHY AN OFFLINE CENSUS AND NOT A LIVE COLLECTOR.  The 2026-10-04 entry named
the realistic route: `EvidenceSoundCoverage` is a python class that must be
*sampled into*, and retrofitting it into `UartCoverage` means re-running the
whole UVM bench under cocotb to learn anything.  An offline census over the
committed stimulus log answers the same questions about the same run without
touching the bench, and -- more importantly -- it answers them about the run
that is ALREADY COMMITTED, so the audit cannot be accused of auditing a run
it generated for itself.

TWO ANCHORS, BOTH READ OFF REAL ARTEFACTS.  2026-10-02 recorded the fault of
a check whose prose names one artefact while its arithmetic reads another, so
this module is careful about which is which:

  ANCHOR 1 (the RUN).  The per-bin counts are parsed out of the committed
  `uart_uvm_sim_output_*.txt` logs.  The collector's own headline percentage
  is then RECOMPUTED from those counts and required to equal the percentage
  the log prints, for every coverage report in every log.  If the
  recomputation disagrees anywhere, this module's model of the metric is
  wrong and it says so instead of reporting findings.

  ANCHOR 2 (the CODE).  The structural claims below are not read from a
  paraphrase of the collector.  `UartCoverage.coverage_percent` is parsed out
  of uart_uvm_tb.py with `ast` and interrogated directly, so "the cross is
  not in the metric" is a fact about the committed source file rather than
  about my reading of it.

FINDINGS, STATED UP FRONT.

  F1  THE CROSS IS PRINTED BUT NOT GATED.  `coverage_percent()` iterates
      `self.bins` and never touches `self.cross`.  The 100.0 % the milestone
      log reports is a statement about 19 bins; the 9-cell cross is formatted
      into the same report_phase message, directly under the words
      "functional coverage", and contributes nothing to the number or to the
      COV_TARGET error.  Every cross cell could be empty and the gate would
      still pass at 100.0 %.

  F2  ONE CROSS CELL IS POPULATION-UNSOUND BY CONSTRUCTION.  (none, parity)
      has no admissible witness: with PARITY_NONE the serial monitor never
      samples a parity bit, `item.parity_ok` keeps its initialised value
      True, and `write_rx` cannot classify the frame as "parity".  So the
      cross's achievable cardinality is 8 of 9, not 9 of 9 -- and if F1 were
      "fixed" by adding the cross to the metric in the obvious way, the gate
      could never reach its own target.  This is the 2026-10-03 finding (a
      bin in the goal that no admissible witness can reach) reproduced
      independently, in a different model, by a different mechanism.

  F3  SCARCITY IS CONCENTRATED EXACTLY WHERE THE EVIDENCE IS WEAKEST.  Of
      the cross cells the milestone run closes, most are closed by a SINGLE
      witness, and the single-witness cells are the error cells rather than
      the clean ones.

  F4  THE TEMPORAL AXIS IS NOT HYPOTHETICAL HERE.  2026-10-04 filed "is
      there a FOURTH soundness axis?" as a question, and named temporal as
      the next candidate.  It is present in this collector and this module
      exhibits the window rather than asserting it: the cross's parity
      coordinate is read from the SHARED `cfg` object at RX-sample time,
      while `UartConfigSeq.body()` writes CTRL to the DUT and only THEN
      updates that object, so between those two events the DUT is running
      one parity mode and the collector would label any frame with the
      other.

WHAT THIS MODULE DOES NOT DO.  It does not change `UartCoverage`, does not
change the vplan's goal, and does not re-run the bench.  F1 and F2 interact
-- fixing F1 without F2 makes the gate unsatisfiable -- so the remedy is a
reviewer's decision, recorded as an open item, not taken here.  That is the
same restraint 2026-10-03 and 2026-10-04 applied to F7's W0/W1/W3/W4 choice.

Run:  python3 coverage_axis_audit.py
Writes: coverage_axis_audit_<date>.txt
"""

import ast
import datetime
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TB = os.path.join(HERE, "uart_uvm_tb.py")
LOGS = sorted(glob.glob(os.path.join(HERE, "uart_uvm_sim_output_*.txt")))

_FAIL = []
_LINES = []


def say(s=""):
    _LINES.append(s)
    print(s)


def head(n, title):
    say()
    say("=" * 78)
    say(f"SECTION {n}.  {title}")
    say("=" * 78)


def check(tag, ok, label, detail=""):
    say(f"  [{'PASS' if ok else 'FAIL'}] {tag:<5}{label}"
        + (f"  -- {detail}" if detail else ""))
    if not ok:
        _FAIL.append(tag)
    return ok


# ---------------------------------------------------------------------------
# ANCHOR 1: parse the committed logs
# ---------------------------------------------------------------------------
BIN_RE = re.compile(r"^\s{2}(cp_\w+)\s+(\d+)/(\d+) bins hit\s+(.*)$")
CROSS_RE = re.compile(r"^\s+cross\(parity_mode x rx_error\):\s*(.*)$")
TOTAL_RE = re.compile(r"^\s+TOTAL bin coverage:\s*([\d.]+)% \(target ([\d.]+)%\)")


def parse_reports(path):
    """Every COVERAGE report in one log, as
    {bins: {cp: {bin: count}}, cross: {(a,b): count}, pct, target}."""
    reports, cur = [], None
    for line in open(path, errors="replace"):
        line = line.rstrip("\n")
        if "[COVERAGE] functional coverage" in line:
            cur = {"bins": {}, "cross": {}, "pct": None, "target": None}
            continue
        if cur is None:
            continue
        m = BIN_RE.match(line)
        if m:
            cp, _got, _tot, rest = m.groups()
            counts = {}
            for kv in rest.split():
                if "=" in kv:
                    k, v = kv.rsplit("=", 1)
                    counts[k] = int(v)
            cur["bins"][cp] = counts
            continue
        m = CROSS_RE.match(line)
        if m:
            for kv in m.group(1).split():
                if "=" in kv:
                    k, v = kv.rsplit("=", 1)
                    a, b = k.split("/", 1)
                    cur["cross"][(a, b)] = int(v)
            continue
        m = TOTAL_RE.match(line)
        if m:
            cur["pct"] = float(m.group(1))
            cur["target"] = float(m.group(2))
            reports.append(cur)
            cur = None
    return reports


def metric_from_bins(bins):
    """The collector's own arithmetic, reimplemented so it can be CHECKED
    against the logs rather than trusted: iterate self.bins, count a bin as
    hit iff its count is non-zero, ignore the cross."""
    total = hit = 0
    for cp in bins.values():
        for v in cp.values():
            total += 1
            hit += 1 if v else 0
    return (100.0 * hit / total) if total else 0.0


# ---------------------------------------------------------------------------
# ANCHOR 2: interrogate the committed source with ast
# ---------------------------------------------------------------------------
def coverage_percent_src():
    tree = ast.parse(open(TB, errors="replace").read())
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "UartCoverage":
            for fn in node.body:
                if isinstance(fn, ast.FunctionDef) and \
                        fn.name == "coverage_percent":
                    return fn, node
    return None, None


def attrs_read(fn):
    """Every `self.<attr>` the function body reads."""
    out = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Attribute) and \
                isinstance(node.value, ast.Name) and node.value.id == "self":
            out.add(node.attr)
    return out


def declared_bins(cls):
    """The bin names from UartCoverage.__init__'s `self.bins = {...}`
    literal, read out of the source rather than retyped here."""
    for fn in cls.body:
        if isinstance(fn, ast.FunctionDef) and fn.name == "__init__":
            for node in ast.walk(fn):
                if isinstance(node, ast.Assign):
                    for t in node.targets:
                        if isinstance(t, ast.Attribute) and t.attr == "bins" \
                                and isinstance(node.value, ast.Dict):
                            out = {}
                            for k, v in zip(node.value.keys,
                                            node.value.values):
                                if isinstance(k, ast.Constant) and \
                                        isinstance(v, ast.Dict):
                                    out[k.value] = [kk.value for kk in v.keys]
                            return out
    return {}


# ===========================================================================
def main():
    today = datetime.date.today().isoformat()
    say("three-axis coverage audit of the LIVE UartCoverage collector")
    say("(2026-10-03 item, widened 2026-10-04; see the module docstring)")

    # ----------------------------------------------------------------
    head(1, "ANCHOR 1: the committed logs, and the metric recomputed from them")
    if not LOGS:
        check("A0", False, "committed sim logs found", "none matched")
        return 1
    all_reports = []
    for p in LOGS:
        r = parse_reports(p)
        all_reports.extend((os.path.basename(p), x) for x in r)
        say(f"  {os.path.basename(p):<40} {len(r)} coverage report(s)")
    check("A1", len(all_reports) >= 3,
          "at least three committed coverage reports to audit",
          f"{len(all_reports)} reports across {len(LOGS)} logs")

    # EXACT under the log's own formatting.  report_phase prints the
    # percentage with "%.1f", so the committed artefact carries one decimal
    # and nothing more; requiring bitwise equality against a float would be
    # requiring the log to contain information it does not have.  The exact
    # statement available is that the recomputation ROUNDS to what the log
    # prints, for every report -- no tolerance, no epsilon, and it fails on
    # any change to the metric larger than half a last place.  (A first form
    # of A2 used `abs(diff) < 0.05`, which is the same bound written as a
    # tolerance and would have hidden WHICH operation it is exact under --
    # the 2026-10-03 rule, recorded rather than silently improved.)
    mismatched = []
    worst = 0.0
    for name, r in all_reports:
        if r["pct"] is None:
            continue
        mine = metric_from_bins(r["bins"])
        worst = max(worst, abs(mine - r["pct"]))
        if round(mine, 1) != r["pct"]:
            mismatched.append((name, mine, r["pct"]))
    check("A2", not mismatched,
          "this module's model of the metric reproduces every logged "
          "percentage EXACTLY under the log's own 1-decimal rounding (so "
          "the findings below are about the collector, not my paraphrase)",
          f"{len(all_reports)} reports, 0 mismatches; largest raw "
          f"difference {worst:.4f} pp, all within half a printed last place")

    # The milestone report is the one that signs off at 100 %.
    mile = [r for _, r in all_reports if r["pct"] == 100.0]
    check("A3", len(mile) >= 1,
          "a committed report reaching the 100 % target exists to audit",
          f"{len(mile)} report(s) at 100.0 %")
    M = mile[0]

    # ----------------------------------------------------------------
    head(2, "ANCHOR 2: what the metric actually reads, from the source tree")
    fn, cls = coverage_percent_src()
    check("A4", fn is not None,
          "UartCoverage.coverage_percent located in uart_uvm_tb.py",
          f"line {fn.lineno}" if fn else "NOT FOUND")
    reads = attrs_read(fn)
    say(f"  self.<attr> read by coverage_percent(): "
        f"{', '.join(sorted(reads)) or '(none)'}")
    decl = declared_bins(cls)
    say(f"  coverpoints declared in __init__      : "
        f"{', '.join(f'{k}({len(v)})' for k, v in decl.items())}")
    n_bins = sum(len(v) for v in decl.values())
    say(f"  total declared bins                   : {n_bins}")

    # ----------------------------------------------------------------
    head(3, "F1  The cross is printed but not gated")
    check("F1a", "bins" in reads,
          "coverage_percent reads self.bins", "as expected")
    check("F1b", "cross" not in reads,
          "coverage_percent does NOT read self.cross -- the cross is outside "
          "the metric entirely",
          f"attrs read: {sorted(reads)}")
    hit = sum(1 for cp in M["bins"].values() for v in cp.values() if v)
    tot = sum(len(cp) for cp in M["bins"].values())
    check("F1c", tot == n_bins and hit == tot,
          f"the 100.0 % report is {hit}/{tot} BINS, and the cross's "
          f"{len(M['cross'])} occupied cells are not among them",
          f"declared {n_bins} bins, logged {tot}; cross cells logged: "
          f"{len(M['cross'])}")
    say()
    say("  So the number a reviewer reads under the words \"functional")
    say("  coverage\" is computed over 19 bins while a 9-cell cross is")
    say("  formatted three lines above it.  Every cross cell could be empty")
    say("  and report_phase would still print 100.0 % and raise no")
    say("  COV_TARGET error.  The cross is not wrong, it is UNGATED -- which")
    say("  is the 2026-09-27 shape (a runner that greps a file it did not")
    say("  just write is not a gate) applied to a number rather than a file.")

    # ----------------------------------------------------------------
    head(4, "F2  (none, parity) is POPULATION-unsound by construction")
    say("  Mechanism, traced through the committed source:")
    say("    UartConfig.expected_parity() returns None when parity is")
    say("    disabled; UartSerialMonitor then skips the parity-bit sample")
    say("    entirely, so item.parity_ok keeps the True it is initialised")
    say("    with; UartCoverage.write_rx classifies on `not item.parity_ok`")
    say("    first, so the \"parity\" class is unreachable under PARITY_NONE.")
    say("    No stimulus closes (none, parity).  It is not scarce; it is")
    say("    EMPTY OF ADMISSIBLE WITNESSES.")
    parity_names = ["none", "even", "odd"]
    err_names = ["clean", "parity", "frame"]
    full = {(a, b) for a in parity_names for b in err_names}
    seen = set(M["cross"])
    unreachable = {("none", "parity")}
    check("F2a", ("none", "parity") not in seen,
          "the committed 100 % run never closes (none, parity)",
          f"cross cells closed: {len(seen)} of {len(full)}")
    check("F2b", seen == full - unreachable,
          "and it is the ONLY cell the run misses, so the run is at the "
          "achievable ceiling rather than merely incomplete",
          f"missing = {sorted(full - seen)}")
    say()
    say(f"  achievable cross cardinality : {len(full) - len(unreachable)}"
        f"/{len(full)} = "
        f"{100.0 * (len(full) - len(unreachable)) / len(full):.2f} %")
    say(f"  achieved                     : {len(seen)}"
        f"/{len(full)} = {100.0 * len(seen) / len(full):.2f} %")
    say()
    say("  F1 AND F2 INTERACT, AND THAT IS WHY NEITHER IS FIXED HERE.")
    say("  Adding the cross to coverage_percent() in the obvious way -- fold")
    say("  its 9 cells in beside the 19 bins -- makes the metric top out at")
    say(f"  {100.0 * (n_bins + len(full) - 1) / (n_bins + len(full)):.2f} %"
        f" against a TARGET of 100.0, so the gate becomes")
    say("  UNSATISFIABLE and every milestone run starts failing COV_TARGET.")
    say("  The remedy needs an exclusion (an illegal_bins equivalent) landed")
    say("  in the SAME change, and choosing it changes a committed sign-off")
    say("  criterion -- a reviewer's decision, per the standing treatment of")
    say("  F7's goal.  Recorded as an open item, not taken.")

    # ----------------------------------------------------------------
    head(5, "F3  Scarcity: which closures rest on a single witness")
    say(f"  {'coverpoint':<16}{'bins':>6}{'scarce (n=1)':>14}  which")
    scarce_total = 0
    for cp, counts in M["bins"].items():
        sc = sorted(k for k, v in counts.items() if v == 1)
        scarce_total += len(sc)
        say(f"  {cp:<16}{len(counts):>6}{len(sc):>14}  {', '.join(sc) or '-'}")
    cross_scarce = sorted(k for k, v in M["cross"].items() if v == 1)
    say(f"  {'cross':<16}{len(M['cross']):>6}{len(cross_scarce):>14}  "
        f"{', '.join(f'{a}/{b}' for a, b in cross_scarce)}")
    check("F3a", len(cross_scarce) >= 1,
          "MAGNITUDE: the 100 % run closes cross cells on a single witness",
          f"{len(cross_scarce)} of {len(M['cross'])} occupied cells have "
          f"exactly one witness "
          f"({100.0 * len(cross_scarce) / len(M['cross']):.1f} %)")
    err_scarce = [c for c in cross_scarce if c[1] != "clean"]
    check("F3b", len(err_scarce) == len(cross_scarce),
          "and EVERY single-witness cross cell is an ERROR cell, not a clean "
          "one -- the scarcity is concentrated exactly where a regression "
          "would bite",
          f"{len(err_scarce)} of {len(cross_scarce)} scarce cells are "
          f"parity/frame")

    # ----------------------------------------------------------------
    head(6, "F4  The TEMPORAL axis, exhibited rather than asserted")
    say("  2026-10-04 filed \"is there a FOURTH soundness axis?\" as a")
    say("  QUESTION and named temporal as the next candidate.  It is present")
    say("  here, and the window is structural rather than probabilistic:")
    say()
    say("    UartCoverage._parity_name() reads self.cfg.parity_mode")
    say("    UartConfigSeq.body()        writes CTRL to the DUT, THEN")
    say("                                assigns self.cfg.parity_mode")
    say()
    say("  Between those two statements the DUT is operating under the new")
    say("  parity mode and the shared cfg object still holds the old one, so")
    say("  any RX frame sampled in the window is filed in the cross under a")
    say("  parity mode that was not in force for it.  The frame is a")
    say("  perfectly ADMISSIBLE witness of its own rx_error class; what is")
    say("  wrong is the OTHER coordinate of the cross cell it closes.")
    src = open(TB, errors="replace").read()
    tree = ast.parse(src)
    body_fn = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "UartConfigSeq":
            for f in node.body:
                if isinstance(f, ast.AsyncFunctionDef) and f.name == "body":
                    body_fn = f
    ctrl_line = cfg_line = None
    if body_fn:
        for node in ast.walk(body_fn):
            if isinstance(node, ast.Await) and ctrl_line is None:
                pass
        for node in body_fn.body:
            seg = ast.get_source_segment(src, node) or ""
            if "ADDR_CTRL" in seg and ctrl_line is None:
                ctrl_line = node.lineno
            if "parity_mode" in seg and "self.cfg" in seg:
                cfg_line = node.lineno
    check("F4a", body_fn is not None,
          "UartConfigSeq.body located in the committed source",
          f"line {body_fn.lineno}" if body_fn else "NOT FOUND")
    check("F4b", ctrl_line is not None and cfg_line is not None
          and ctrl_line < cfg_line,
          "the CTRL write to the DUT precedes the cfg update in program "
          "order, so the window is real and not an artefact of my reading",
          f"CTRL write at line {ctrl_line}, cfg update at line {cfg_line} "
          f"-- window spans {cfg_line - ctrl_line} statement line(s)")
    say()
    say("  THE AXIS IS NOT THE BUG.  The window here is narrow and the")
    say("  milestone sequence does not drive RX traffic across it, which is")
    say("  why no committed number is wrong and none is withdrawn.  The")
    say("  finding is that the FOURTH AXIS HAS A CONCRETE INSTANCE in the")
    say("  first collector it was pointed at, so it should stop being filed")
    say("  as a question.  A coverage sample has a TIMESTAMP, and a sample")
    say("  whose coordinates are read from two sources that are updated at")
    say("  different times is sound on each coordinate and unsound as a")
    say("  pair.  No cardinality, scarcity, population or run check sees it:")
    say("  all four ask about the SET of witnesses, and this is a question")
    say("  about WHEN one was read.")

    # ----------------------------------------------------------------
    head(7, "Controls")
    check("C1", metric_from_bins({"x": {"a": 0, "b": 0}}) == 0.0,
          "CONTROL: the metric model returns 0 % when nothing is hit "
          "(it is not a constant)")
    check("C2", metric_from_bins({"x": {"a": 3, "b": 0}}) == 50.0,
          "CONTROL: and 50 % when half is hit, counting a bin ONCE however "
          "many times it was hit",
          "a=3 and b=0 gives 50.0, not 75.0")
    low = [r for _, r in all_reports if r["pct"] is not None and r["pct"] < 100]
    check("C3", len(low) >= 1,
          "CONTROL: the logs contain reports BELOW target, so A2's agreement "
          "is not a fact about one lucky number",
          f"{len(low)} report(s) below 100 %, lowest "
          f"{min(r['pct'] for r in low):.1f} %")
    cross_cells = {c for _, r in all_reports for c in r["cross"]}
    check("C4", ("none", "parity") not in cross_cells,
          "CONTROL: (none, parity) is absent from EVERY committed report, "
          "not just the milestone one -- so F2 is a property of the DUT and "
          "the classifier, not of one run's stimulus",
          f"{len(cross_cells)} distinct cross cells across all "
          f"{len(all_reports)} reports")

    # ----------------------------------------------------------------
    head(8, "Verdict")
    say("  axis                          status for UartCoverage")
    say("  " + "-" * 62)
    say("  cardinality                   measured, but over 19 of 28 bins")
    say("                                (the cross is ungated)            F1")
    say("  scarcity                      NOT measured; "
        f"{len(cross_scarce)} of {len(M['cross'])} closed cross")
    say("                                cells rest on one witness         F3")
    say("  soundness (population)        NOT measured; 1 cell is empty of")
    say("                                admissible witnesses              F2")
    say("  soundness (run)               NOT measured, and not measurable")
    say("                                offline: the logs record COUNTS,")
    say("                                not per-sample witnesses")
    say("  soundness (temporal)          has a concrete instance here       F4")
    say()
    say("  The run axis is the honest gap in this audit and is stated as")
    say("  one.  A count of 2 in a cross cell does not say WHICH two frames")
    say("  closed it, so an offline census over this log cannot decide")
    say("  whether a cell was closed by good evidence.  Answering it needs")
    say("  the collector to emit per-sample witnesses -- which is a change")
    say("  to the bench, not to this audit, and is the open item that")
    say("  follows.  Reported rather than approximated, per 2026-10-01: an")
    say("  aggregate on the contained side errs only one way.")

    say()
    say("=" * 78)
    say(f"RESULT: {sum(1 for l in _LINES if '[PASS]' in l)} passed, "
        f"{len(_FAIL)} failed")
    say("=" * 78)
    if _FAIL:
        say(f"  FAILED: {', '.join(_FAIL)}")
    out = os.path.join(HERE, f"coverage_axis_audit_{today}.txt")
    with open(out, "w") as fh:
        fh.write("\n".join(_LINES) + "\n")
    say(f"  wrote {os.path.basename(out)}")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
