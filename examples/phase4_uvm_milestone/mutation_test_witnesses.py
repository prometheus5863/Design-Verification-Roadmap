"""
mutation_test_witnesses.py

Mutation harness for the PER-SAMPLE WITNESS mechanism added to
`UartCoverage` in uart_uvm_tb.py on 2026-10-06, in the form this repository
has used since 2026-09-18: inject a defect into a COPY of the testbench,
re-run the simulator against the unmodified RTL, and require the run to
FAIL.  Control A (the unmutated environment passes) and control B (a
correct-but-different rewrite survives) bracket the claim from both sides.

WHY THIS NEEDS A HARNESS AT ALL, and the 2026-09-17 precedent is the whole
argument.  A witness log that silently disagrees with the counts printed
beside it is WORSE than no witness log, because the run-axis audit it
unblocks would then be auditing a fiction.  On 2026-09-17 a testbench passed
55/55 against deliberately broken RTL; the lesson was that a self-checking
suite has to be shown to fail.  Here the thing that must be shown to fail is
the audit W-a..W-e, and the mutants are chosen so that each one is the
realistic way this mechanism breaks:

  N1  a coverage bin is incremented WITHOUT going through _hit(), which is
      the only way a future edit breaks this by accident.  W-c must catch it.
  N2  the witness string drops its ordinal and timestamp, keeping only the
      item text.  Three of this environment's cells are closed by the SAME
      byte every time (cp_rx_error.frame by 0xc3, cp_rx_error.parity by
      0x7e), so the witnesses collapse to duplicates and stop answering
      "which frames closed this cell".  W-d must catch it.
  N3  witness_total stops accumulating.  W-c must catch it.
  N4  the witness is filed under the WRONG CELL.  This is the fault that
      would corrupt a run-axis audit while leaving every count correct, and
      it is the one a reader cannot see by inspection.  W-b and/or W-c must
      catch it.
  N5  the WITNESS_KEEP bound is removed.  Not a correctness fault -- a log
      fault, and the reason witness logging usually gets abandoned.  W-e
      exists only for this and must catch it.

Each mutant runs only `test_uart_uvm_milestone`, the fastest of the five
tests (0.7 s of simulation), because the audit is a report_phase property
and does not need the long timebase sweeps to exercise it.

Requires the toolchain: `source tools/setup_iverilog.sh` (do NOT pipe it)
and the uvm-python stack of
notes/2026-09-06-uvm-python-toolchain-resolution.md.

Run:    python3 mutation_test_witnesses.py
Writes: mutation_report_witnesses_<date>.txt
"""

import datetime
import os
import re
import shutil
import subprocess
import sys
import tempfile

TARGET = "uart_uvm_tb.py"
TESTCASE = "test_uart_uvm_milestone"

# (tag, description, old, new, must_be_caught)
MUTANTS = [
    ("N1", "a bin is incremented WITHOUT going through _hit() "
           "(the accidental-edit fault)",
     '        self._hit("cp_rx_error", kind, "rx", item)',
     '        self.bins["cp_rx_error"][kind] += 1', True),

    ("N2", "the witness string drops its ordinal and timestamp",
     '            lst.append("#%d t=%dps %s %s"\n'
     '                       % (self.n_samples, get_sim_time("ps"), src,\n'
     '                          item.convert2string()))',
     '            lst.append("%s %s" % (src, item.convert2string()))', True),

    ("N3", "witness_total stops accumulating",
     '        self.witness_total[cell] = self.witness_total.get(cell, 0) + 1',
     '        self.witness_total[cell] = 1', True),

    ("N4", "the witness is filed under the WRONG CELL (counts stay correct)",
     '        self.bins[cpname][binname] += 1\n'
     '        self._record(("bin", cpname, binname), src, item)',
     '        self.bins[cpname][binname] += 1\n'
     '        self._record(("bin", cpname, "clean"), src, item)', True),

    ("N5", "the WITNESS_KEEP bound is removed (the log-growth fault)",
     '        if len(lst) < self.WITNESS_KEEP:',
     '        if True:', True),

    # ---- CONTROL B: different code, identical witness text.  MUST SURVIVE.
    ("B", "CONTROL B: the witness string built with an f-string instead of "
          "%-formatting (identical output, different code)",
     '            lst.append("#%d t=%dps %s %s"\n'
     '                       % (self.n_samples, get_sim_time("ps"), src,\n'
     '                          item.convert2string()))',
     '            lst.append(f"#{self.n_samples} t={get_sim_time(\'ps\')}ps "\n'
     '                       f"{src} {item.convert2string()}")', False),
]


def build_tree(root, src_text):
    """A scratch copy of the tree the Makefile expects: rtl/ and bfm/ two
    levels above the example directory, which is how VERILOG_SOURCES is
    written.  The RTL is copied UNMODIFIED -- only the testbench is
    mutated, so a failure cannot be a broken DUT."""
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.abspath(os.path.join(here, "..", ".."))
    ex = os.path.join(root, "examples", "phase4_uvm_milestone")
    os.makedirs(ex)
    shutil.copytree(os.path.join(repo, "rtl"), os.path.join(root, "rtl"))
    shutil.copytree(os.path.join(repo, "bfm"), os.path.join(root, "bfm"))
    for f in ("Makefile", "uart_uvm_top.v"):
        shutil.copy(os.path.join(here, f), ex)
    with open(os.path.join(ex, TARGET), "w") as fh:
        fh.write(src_text)
    return ex


def run(ex):
    env = dict(os.environ, TESTCASE=TESTCASE)
    try:
        p = subprocess.run(["make"], cwd=ex, env=env, capture_output=True,
                           text=True, timeout=600)
        return p.returncode, p.stdout + p.stderr
    except subprocess.TimeoutExpired:
        return -1, "TIMEOUT: the mutant did not terminate"


def verdict(out):
    """Did the run FAIL?  Three independent signals, because a uvm-python
    run can fail in three different layers and only the first is about the
    audit: a COV_WITNESS ... FAILED line, a nonzero UVM_ERROR count, or
    cocotb's own FAIL count."""
    reasons = []
    # ANCHORED ON THE COLON, and the reason is a false positive this harness
    # produced on its own first run.  The audit's summary line read
    # "W-a..W-e FAILED", a bare `(W-[a-e]) FAILED` matched "W-e FAILED"
    # inside it, and all five mutants came back with W-e in their killer
    # column -- crediting the one check that detects a log-growth fault with
    # four detections of correctness faults it is blind to.  N1's UVM_ERROR=2
    # beside three W-tags is what gave it away: the counts did not agree.
    # The error form always has a colon ("W-c FAILED: cells where ..."); the
    # summary never does, and has since been reworded as well, so the fix is
    # in both places.
    for tag in re.findall(r"(W-[a-e]) FAILED:", out):
        if tag not in reasons:
            reasons.append(tag)
    m = re.search(r"UVM_ERROR=(\d+)", out)
    if m and int(m.group(1)) > 0:
        reasons.append("UVM_ERROR=%s" % m.group(1))
    if re.search(r"FAIL=[1-9]", out):
        reasons.append("cocotb FAIL")
    if "TIMEOUT" in out:
        reasons.append("TIMEOUT")
    return reasons


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    today = datetime.date.today().isoformat()
    lines = []

    def say(s=""):
        lines.append(s)
        print(s)
        sys.stdout.flush()

    def write():
        with open(os.path.join(
                here, "mutation_report_witnesses_%s.txt" % today), "w") as fh:
            fh.write("\n".join(lines) + "\n")

    say("mutation report: the per-sample witness mechanism in UartCoverage")
    say("=" * 78)
    say("  target   : %s (%s only)" % (TARGET, TESTCASE))
    say("  RTL      : rtl/uart_controller.v, copied UNMODIFIED into every")
    say("             scratch tree, so no verdict below can be a broken DUT.")
    say("  date     : %s" % today)

    src = open(os.path.join(here, TARGET)).read()

    # ---------------- CONTROL A ----------------
    with tempfile.TemporaryDirectory() as d:
        ex = build_tree(d, src)
        rc, out = run(ex)
    a_reasons = verdict(out)
    ctrl_a = (rc == 0 and not a_reasons)
    say("  [%s] CONTROL A  the unmutated environment passes  -- exit %d%s"
        % ("PASS" if ctrl_a else "FAIL", rc,
           "" if ctrl_a else ", reasons: " + ", ".join(a_reasons)))
    if not ctrl_a:
        say("  control A failed; every mutant verdict below would be "
            "meaningless.  Stopping.")
        for l in out.strip().splitlines()[-30:]:
            say("  " + l)
        write()
        return 1

    killed = 0
    expected = sum(1 for m in MUTANTS if m[4])
    bad = []
    say()
    say("  %-5s%-11s%-26s%s" % ("tag", "verdict", "killed by", "description"))
    say("  " + "-" * 102)

    for tag, desc, old, new, must in MUTANTS:
        if src.count(old) != 1:
            say("  %-5s%-11s%-26sanchor appears %dx, not 1x -- NOT INJECTED"
                % (tag, "ARRIVAL?", "-", src.count(old)))
            bad.append(tag)
            continue
        with tempfile.TemporaryDirectory() as d:
            ex = build_tree(d, src.replace(old, new))
            rc, out = run(ex)
        reasons = verdict(out)
        caught = bool(reasons) or rc != 0
        by = ",".join(reasons[:4]) if reasons else ("exit %d" % rc if caught
                                                    else "-")
        if must:
            ok = caught
            killed += 1 if caught else 0
            v = "KILLED" if caught else "SURVIVED"
        else:
            ok = not caught
            v = "SURVIVED" if not caught else "KILLED(!)"
        if not ok:
            bad.append(tag)
        say("  %-5s%-11s%-26s%s" % (tag, v, by[:25], desc))

    say()
    say("=" * 78)
    say("  %d of %d mutants killed; control A passed; control B %s"
        % (killed, expected,
           "survived as required" if "B" not in bad
           else "WAS CAUGHT -- the audit fails on a correct rewrite"))
    say()
    say("  WHAT TO READ IN THE KILLER COLUMN.  Each mutant should be killed")
    say("  by the ONE check written for it, and if a mutant is killed by")
    say("  UVM_ERROR alone -- with no W-x tag -- then the audit did not")
    say("  detect it and something downstream did, which is a weaker")
    say("  detection and is worth the same scepticism 2026-10-04 applied to")
    say("  a crash as a detector.  N1 and N3 are both W-c, deliberately:")
    say("  they are the same fault reached from the two sides of the")
    say("  equality W-c asserts, and a harness in which only one of them")
    say("  dies would mean W-c is comparing a quantity with itself.")
    say()
    say("  A FALSE POSITIVE IN THIS HARNESS'S OWN DETECTOR, on its first")
    say("  run, recorded because it is the more useful half of today's")
    say("  result.  verdict() originally matched `(W-[a-e]) FAILED`, and the")
    say("  audit's summary line read \"W-a..W-e FAILED\" -- so the regex")
    say("  matched \"W-e FAILED\" inside the summary and EVERY mutant came")
    say("  back with W-e in its killer column.  W-e detects a log-growth")
    say("  fault and is blind to all four correctness faults, so it was")
    say("  credited with four detections it did not make.  Nothing in the")
    say("  pass/fail result was wrong -- 5 of 5 were genuinely killed -- and")
    say("  the ATTRIBUTION was wrong for four of them, which is exactly the")
    say("  quantity this harness exists to report.  What gave it away was an")
    say("  arithmetic disagreement inside one row: N1 showed three W-tags")
    say("  beside UVM_ERROR=2.  Fixed in two places: the regex is anchored")
    say("  on the colon the error form always has, and the summary line no")
    say("  longer contains a W-x token.  The rule, which is new: a summary")
    say("  line must not be parseable as one of the things it summarises.")
    say()
    say("  WHAT N2 IS REALLY MEASURING, and it is a property of this")
    say("  environment rather than of the code.  N2 strips the ordinal and")
    say("  the timestamp from the witness, leaving the item text.  It is")
    say("  only caught because several cells here are closed by the SAME")
    say("  payload every time -- cp_rx_error.frame by 0xc3 and")
    say("  cp_rx_error.parity by 0x7e, three and two times respectively.")
    say("  In an environment with constrained-random payloads the item text")
    say("  would differ and N2 would SURVIVE, so W-d's strength depends on")
    say("  the stimulus it is run against.  That is recorded here rather")
    say("  than claimed away: W-d is sound (the ordinal makes duplicates")
    say("  impossible by construction) but its mutation-detection power is")
    say("  stimulus-dependent, which is the 2026-09-28 observer item in a")
    say("  new place.")

    if bad:
        say("  PROBLEM TAGS: %s" % ", ".join(bad))
    write()
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
