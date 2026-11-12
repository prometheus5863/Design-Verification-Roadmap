#!/usr/bin/env python3
"""tools/run_cdc_gate_mutation.py -- 2026-11-12

MUTATION TEST OF tools/run_cdc_gate.sh.

run_cdc_gate.sh reports 9/9 on the repository as it stands.  So did an
earlier version of the Phase 4 UART testbench, at 55/55, against RTL that
had been deliberately broken -- which is the 2026-09-17 finding this
repository has repeated as a rule ever since: a suite that has only ever
been run against a correct subject has not been tested, it has been
exercised.

The subject here is a GATE, so the thing to mutate is not only the design
it guards but the gate's own decision structure.  Each mutant below names
the SECTION of run_cdc_gate.sh that must go red, and the requirement is
that the named section fails -- not merely that the script exits nonzero.
A mutant detected by the wrong section means that section's name is a
description and not a mechanism, which is a weaker result and is reported
as such rather than folded into a pass.

THREE-VALUED, FOR THE SAME REASON THE OTHER HARNESSES ARE
---------------------------------------------------------
  DETECTED-AS-PREDICTED  the named section failed
  DETECTED-ELSEWHERE     the gate went red, but not where the mutant aimed
  UNDETECTED             the gate stayed green: a real hole

HOW THE SUBJECT IS BUILT
------------------------
Each mutant runs against a COPY of this repository's .v files plus the two
tools, laid out at the same relative paths so that run_cdc_gate.sh's own
root discovery works unchanged.  Nothing in the real tree is written to;
the mutation lives only in the copy.  The copy is verified green BEFORE
mutating -- a baseline that is already red would make every verdict below
meaningless, exactly as the CDC checker's own mutation harness says of its
--root flag.
"""

import os
import re
import hashlib
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GATE_REL = "tools/run_cdc_gate.sh"
CHECKER_REL = "tools/cdc_structural_check.py"

# A genuinely unsynchronised multi-clock crossing: a second clock domain
# whose register is read directly by the existing one.  This is the change
# the 2026-11-11 item said "cannot land unexamined".
BAD_CROSSING = """
// ---- injected by run_cdc_gate_mutation.py: a real CDC defect ----
module injected_two_domain_bug (
    input  wire clk_a,
    input  wire clk_b,
    input  wire rst_n,
    input  wire [7:0] din,
    output reg  [7:0] dout
);
    reg [7:0] stage_a;
    always @(posedge clk_a or negedge rst_n) begin
        if (!rst_n) stage_a <= 8'h00;
        else        stage_a <= din;
    end
    always @(posedge clk_b or negedge rst_n) begin
        if (!rst_n) dout <= 8'h00;
        else        dout <= stage_a;   // no synchroniser, no Gray encoding
    end
endmodule
"""


def build_copy(dst):
    """The .v files at their real relative paths, plus the two tools."""
    for rel in (GATE_REL, CHECKER_REL):
        d = os.path.join(dst, os.path.dirname(rel))
        os.makedirs(d, exist_ok=True)
        shutil.copy2(os.path.join(ROOT, rel), os.path.join(dst, rel))
    os.chmod(os.path.join(dst, GATE_REL), 0o755)
    n = 0
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [x for x in dirnames if x != ".git"]
        for fn in filenames:
            if not fn.endswith(".v"):
                continue
            src = os.path.join(dirpath, fn)
            rel = os.path.relpath(src, ROOT)
            out = os.path.join(dst, rel)
            os.makedirs(os.path.dirname(out), exist_ok=True)
            shutil.copy2(src, out)
            n += 1
    return n


def _digest(tree):
    """A content digest of every file in the copy.

    Added after D2 was reported UNDETECTED for having changed nothing.  A
    mutant that does not alter the subject is a defect in this harness, and
    reporting it as a hole in the thing under test is worse than not running
    it: it is a false negative wearing the costume of a finding.
    """
    h = hashlib.sha256()
    for dirpath, dirnames, filenames in os.walk(tree):
        dirnames[:] = sorted(dirnames)
        for fn in sorted(filenames):
            fp = os.path.join(dirpath, fn)
            h.update(os.path.relpath(fp, tree).encode())
            with open(fp, "rb") as fh:
                h.update(fh.read())
    return h.hexdigest()


def run_gate(tree):
    p = subprocess.run(["bash", os.path.join(tree, GATE_REL)],
                       cwd=tree, capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def failing_sections(out):
    """Which SECTION headings own a [FAIL] line, in order."""
    section, bad = None, []
    for line in out.splitlines():
        m = re.match(r"SECTION (\d+)", line.strip())
        if m:
            section = int(m.group(1))
        elif "[FAIL]" in line and section is not None:
            if section not in bad:
                bad.append(section)
    return bad


# --- the mutants -----------------------------------------------------------
def m1_real_crossing(tree):
    """A true unsynchronised crossing added to the gated RTL."""
    p = os.path.join(tree, "rtl", "uart_controller.v")
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(BAD_CROSSING)


def m2_repair_the_control(tree):
    """The deliberate wrong crossing of the CDC example, silently repaired.

    THIS MUTANT WAS A NO-OP ON ITS FIRST RUN AND WAS REPORTED UNDETECTED,
    which looked like a hole in section 3 of the gate and was not.  The
    anchor was written as `.d(bin_skewed)`; the port is actually
    `.d_src(bin_skewed)`, so the primary replacement matched nothing, and
    the regex fallback then renamed the first two occurrences of the net --
    its declaration and its no-skew alias -- while leaving the synchroniser
    instance reading the old name.  The deliberate finding went on firing,
    the gate stayed green, and the harness blamed the gate.

    An unanchored mutation is indistinguishable from a gate that cannot see
    it.  The anchor is now asserted here, and the runner additionally
    verifies that every mutant changed the tree at all -- see _digest().
    This is the same failure mode tools/audit_mutation_anchors.sh exists to
    catch in the shell harnesses, arriving in a Python one.
    """
    p = os.path.join(tree, "examples", "phase6_cdc_basics",
                     "cdc_crossings_tb.v")
    src = open(p, encoding="utf-8").read()
    old = ".d_src(bin_skewed), .q_dst(sync_bin)"
    assert old in src, "u_sync_bin port anchor moved; fix this mutant"
    open(p, "w", encoding="utf-8").write(
        src.replace(old, ".d_src(gray_skewed), .q_dst(sync_bin)"))


def m3_crossing_in_a_new_file(tree):
    """The same defect, in a NEW .v file outside the gated directories.

    This is the mutant a count budget cannot catch: the tree's finding total
    goes 1 -> 2, but a gate that only compared COUNTS against the shipped
    set would still see rtl/ bfm/ checkers/ clean and pass.
    """
    d = os.path.join(tree, "examples", "phase6_cdc_basics")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "injected_extra_crossing.v"), "w",
              encoding="utf-8") as fh:
        fh.write(BAD_CROSSING)


def m4_blind_the_checker(tree):
    """The checker can no longer recognise a synchroniser by name."""
    p = os.path.join(tree, CHECKER_REL)
    src = open(p, encoding="utf-8").read()
    old = 'SYNC_MODULE_RE = re.compile(r"(?:^|_)sync(?:_|$)|synchron", re.IGNORECASE)'
    assert old in src, "SYNC_MODULE_RE anchor moved; fix this mutant"
    open(p, "w", encoding="utf-8").write(
        src.replace(old, 'SYNC_MODULE_RE = re.compile(r"$^")'))


def m5_bare_mode_exits_clean(tree):
    """A bare invocation returns 0, so an empty file list looks clean."""
    p = os.path.join(tree, CHECKER_REL)
    src = open(p, encoding="utf-8").read()
    old = """        print(__doc__.strip().split("Usage:")[-1].strip())
        return 2"""
    assert old in src, "usage-path anchor moved; fix this mutant"
    open(p, "w", encoding="utf-8").write(
        src.replace(old, """        print(__doc__.strip().split("Usage:")[-1].strip())
        return 0"""))


MUTANTS = (
    ("D1 a real unsynchronised two-domain crossing in the gated RTL",
     m1_real_crossing, 2),
    ("D2 the deliberate wrong crossing repaired, leaving the positive "
     "control with nothing to detect", m2_repair_the_control, 3),
    ("D3 the same defect in a NEW file outside the gated directories -- the "
     "mutant a count budget cannot catch", m3_crossing_in_a_new_file, 4),
    ("D4 the checker blinded: it can no longer recognise a synchroniser",
     m4_blind_the_checker, 1),
    ("D5 a bare invocation of the checker exits 0 instead of 2",
     m5_bare_mode_exits_clean, 5),
)


def main():
    print("=" * 74)
    print("MUTATION TEST OF tools/run_cdc_gate.sh")
    print("=" * 74)

    base = tempfile.mkdtemp(prefix="cdc_gate_baseline.")
    try:
        n_v = build_copy(base)
        rc, out = run_gate(base)
        print("\nBASELINE (unmutated copy, %d .v files)" % n_v)
        total = [l for l in out.splitlines() if l.startswith("TOTAL:")]
        print("  rc = %d   %s" % (rc, total[0] if total else "no TOTAL line"))
        if rc != 0:
            print("\n  BASELINE IS RED.  Every verdict below would be")
            print("  meaningless, so the run stops here.")
            print(out)
            return 1
        print("  baseline green, so a red result below is the mutant's doing")
    finally:
        shutil.rmtree(base, ignore_errors=True)

    rows = []
    for name, apply_mut, predicted in MUTANTS:
        tree = tempfile.mkdtemp(prefix="cdc_gate_mut.")
        try:
            build_copy(tree)
            before = _digest(tree)
            apply_mut(tree)
            if _digest(tree) == before:
                rows.append((name, predicted, [], -1, "NO-OP MUTANT"))
                continue
            rc, out = run_gate(tree)
            bad = failing_sections(out)
            if rc == 0 and not bad:
                verdict = "UNDETECTED"
            elif predicted in bad:
                verdict = "DETECTED-AS-PREDICTED"
            else:
                verdict = "DETECTED-ELSEWHERE"
            rows.append((name, predicted, bad, rc, verdict))
        finally:
            shutil.rmtree(tree, ignore_errors=True)

    print("\n" + "-" * 74)
    print("RESULTS")
    print("-" * 74)
    for name, predicted, bad, rc, verdict in rows:
        print("  %-22s rc=%d  predicted S%d  failed %-12s  %s"
              % (verdict, rc, predicted,
                 ",".join("S%d" % b for b in bad) or "none", name[:40]))

    noop = sum(1 for r in rows if r[4] == "NO-OP MUTANT")
    det = sum(1 for r in rows if r[4] not in ("UNDETECTED", "NO-OP MUTANT"))
    pred = sum(1 for r in rows if r[4] == "DETECTED-AS-PREDICTED")
    print("\n  %d/%d detected, %d by the predicted section, %d no-op"
          % (det, len(rows), pred, noop))
    if noop:
        print("  a NO-OP MUTANT is a defect in THIS FILE, not in the gate:")
        print("  its anchor no longer matches.  It is never counted as a")
        print("  hole in the subject.")

    print("\n" + "=" * 74)
    if det == len(rows) and pred == len(rows) and not noop:
        print("TOTAL: %d/%d mutants detected, all by the predicted section"
              % (det, len(rows)))
        print("=" * 74)
        return 0
    print("TOTAL: %d/%d detected, %d as predicted -- SEE ABOVE"
          % (det, len(rows), pred))
    print("=" * 74)
    return 1


if __name__ == "__main__":
    sys.exit(main())
