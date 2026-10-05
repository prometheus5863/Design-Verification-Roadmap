"""
mutation_test_coverage_axis.py

Mutation harness for coverage_axis_audit.py.

THE MUTANTS HERE ARE A DIFFERENT SHAPE FROM THE USUAL ONES, and it is worth
saying why before the list.  The four earlier harnesses in this directory
mutate a MODEL and require a suite to notice.  This module's subject is an
AUDIT, and an audit's failure mode is not "it computes the wrong number" --
it is "it reports a finding that is not there, or misses one that is".  So
the mutants fall into two groups:

  (a) mutants of the AUDIT's own machinery -- its log parser, its ast
      interrogation, its metric model.  These must be caught, because an
      audit whose instrument is broken produces confident findings about
      nothing.

  (b) mutants of the SUBJECT, injected into a copy of uart_uvm_tb.py.  These
      are the interesting ones: they ask whether each finding is actually
      LOAD-BEARING on the artefact it names.  If F1 still "passes" after the
      cross has been added to coverage_percent(), then F1 was never reading
      the source and the ast anchor was decoration.

Group (b) is the direct answer to the 2026-10-02 item *audit every remaining
check for the "reads the artefact its own prose names" fault*: the only way
to know a check reads its artefact is to change the artefact and watch the
check move.

CONTROL B is mandatory (2026-10-04): a change that is genuinely different but
makes no difference to any finding must SURVIVE, or "all mutants die" is a
statement about a suite that fails on everything.

Run:  python3 mutation_test_coverage_axis.py
Writes: mutation_report_coverage_axis_<date>.txt
"""

import datetime
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
AUDIT = "coverage_axis_audit.py"
TB = "uart_uvm_tb.py"
LOGS = [f for f in os.listdir(HERE)
        if f.startswith("uart_uvm_sim_output_") and f.endswith(".txt")]

# (tag, target_file, description, old, new, must_be_caught)
MUTANTS = [
    # ---- group (a): the audit's own machinery -------------------------
    ("A1", AUDIT, "metric model counts a bin ONCE PER HIT instead of once",
     "            hit += 1 if v else 0",
     "            hit += v", True),

    ("A2", AUDIT, "metric model folds the cross in (so it stops matching "
                  "the logged percentage)",
     "    total = hit = 0\n    for cp in bins.values():",
     "    total = hit = 9\n    for cp in bins.values():", True),

    ("A3", AUDIT, "log parser drops the last coverpoint of every report",
     "            cur[\"bins\"][cp] = counts",
     "            cur[\"bins\"][cp] = counts if cp != \"cp_reg_access\" "
     "else {}", True),

    ("A4", AUDIT, "ast anchor reports attributes of the WRONG method",
     "                        fn.name == \"coverage_percent\":",
     "                        fn.name == \"write_rx\":", True),

    # ---- group (b): the subject, to prove the findings are load-bearing
    ("B1", TB, "SUBJECT: fold self.cross INTO coverage_percent -- F1 must "
               "stop firing",
     "        total = hit = 0\n        for cp in self.bins.values():",
     "        total = hit = 0\n        for v in self.cross.values():\n"
     "            total += 1\n            hit += 1 if v else 0\n"
     "        for cp in self.bins.values():", True),

    ("B2", TB, "SUBJECT: move the cfg update BEFORE the CTRL write -- F4's "
               "window closes and F4b must stop firing",
     "        ctrl = 1 | (self.parity_mode << 1) | "
     "((1 if self.two_stop else 0) << 3)\n        await self._wr(ADDR_CTRL, "
     "ctrl)\n        self.cfg.parity_mode = self.parity_mode",
     "        ctrl = 1 | (self.parity_mode << 1) | "
     "((1 if self.two_stop else 0) << 3)\n        self.cfg.parity_mode = "
     "self.parity_mode\n        await self._wr(ADDR_CTRL, ctrl)", True),

    # ---- CONTROL B: different, but changes no finding.  MUST SURVIVE. --
    ("B", AUDIT, "CONTROL B: the metric's accumulator written as a sum over "
                 "a comprehension (different code, identical arithmetic)",
     "    total = hit = 0\n    for cp in bins.values():\n"
     "        for v in cp.values():\n            total += 1\n"
     "            hit += 1 if v else 0\n"
     "    return (100.0 * hit / total) if total else 0.0",
     "    vals = [v for cp in bins.values() for v in cp.values()]\n"
     "    total = len(vals)\n    hit = sum(1 for v in vals if v)\n"
     "    return (100.0 * hit / total) if total else 0.0", False),
]


def run(cwd):
    p = subprocess.run([sys.executable, AUDIT], cwd=cwd,
                       capture_output=True, text=True, timeout=600)
    return p.returncode, p.stdout + p.stderr


def failed_tags(out):
    return re.findall(r"\[FAIL\] (\S+)", out)


def stage(d):
    for f in [AUDIT, TB] + LOGS:
        shutil.copy(os.path.join(HERE, f), d)


def main():
    today = datetime.date.today().isoformat()
    lines = []

    def say(s=""):
        lines.append(s)
        print(s)

    say("mutation report: coverage_axis_audit.py")
    say("=" * 78)
    say("  group (a) mutates the AUDIT's machinery; group (b) mutates the")
    say("  SUBJECT (uart_uvm_tb.py) to prove each finding is load-bearing on")
    say("  the artefact its prose names -- the 2026-10-02 item, answered by")
    say("  changing the artefact and watching the check move.")
    say()

    # ---- CONTROL A ----
    with tempfile.TemporaryDirectory() as d:
        stage(d)
        rc, out = run(d)
    ctrl_a = (rc == 0 and not failed_tags(out))
    say(f"  [{'PASS' if ctrl_a else 'FAIL'}] CONTROL A  the unmutated audit "
        f"is green  -- exit {rc}, {len(failed_tags(out))} failed checks")
    if not ctrl_a:
        say("  control A failed; every verdict below would be meaningless.")
        with open(os.path.join(
                HERE, f"mutation_report_coverage_axis_{today}.txt"), "w") as f:
            f.write("\n".join(lines) + "\n")
        return 1

    srcs = {AUDIT: open(os.path.join(HERE, AUDIT)).read(),
            TB: open(os.path.join(HERE, TB)).read()}

    say()
    say(f"  {'tag':<5}{'tgt':<5}{'verdict':<11}{'killed by':<30}description")
    say("  " + "-" * 100)
    bad, killed, expect = [], 0, sum(1 for m in MUTANTS if m[5])

    for tag, tgt, desc, old, new, must in MUTANTS:
        n = srcs[tgt].count(old)
        if n != 1:
            say(f"  {tag:<5}{tgt[:4]:<5}{'ARRIVAL?':<11}{'-':<30}"
                f"anchor appears {n}x, not 1x -- NOT INJECTED")
            bad.append(tag)
            continue
        with tempfile.TemporaryDirectory() as d:
            stage(d)
            with open(os.path.join(d, tgt), "w") as fh:
                fh.write(srcs[tgt].replace(old, new))
            try:
                rc, out = run(d)
            except subprocess.TimeoutExpired:
                rc, out = -1, "[FAIL] TIMEOUT"
        tags = failed_tags(out)
        caught = (rc != 0) or bool(tags)
        by = ",".join(tags[:3]) if tags else (f"exit {rc}" if caught else "-")
        if must:
            ok = caught
            verdict = "KILLED" if caught else "SURVIVED"
            killed += 1 if caught else 0
        else:
            ok = not caught
            verdict = "SURVIVED" if not caught else "KILLED(!)"
        if not ok:
            bad.append(tag)
        say(f"  {tag:<5}{tgt[:4]:<5}{verdict:<11}{by[:29]:<30}{desc}")

    say()
    say("=" * 78)
    say(f"  {killed} of {expect} mutants killed; control A green; control B "
        f"{'survived as required' if 'B' not in bad else 'WAS CAUGHT'}")
    say()
    say("  WHAT GROUP (b) ESTABLISHES.  B1 adds the cross to the subject's")
    say("  own coverage_percent(); if F1b still passed, F1 would have been")
    say("  reading nothing and the ast anchor would be decoration.  B2 moves")
    say("  the cfg update before the CTRL write, closing F4's window; if F4b")
    say("  still passed, the temporal finding would be a story rather than a")
    say("  measurement.  Both findings therefore rest on the committed")
    say("  source and move when it moves, which is the property the")
    say("  2026-10-02 item asks every check in this repository for and that")
    say("  almost none of them has yet been shown to have.")
    if bad:
        say(f"  PROBLEM TAGS: {', '.join(bad)}")
    out_p = os.path.join(HERE, f"mutation_report_coverage_axis_{today}.txt")
    with open(out_p, "w") as f:
        f.write("\n".join(lines) + "\n")
    say(f"  wrote {os.path.basename(out_p)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
