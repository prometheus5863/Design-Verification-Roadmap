#!/usr/bin/env python3
"""
examples/phase6_cdc_basics/cdc_mutation_test.py

Mutation test for the Phase 6 CDC basics bench.

Why this exists at all: on 2026-09-17 this repository committed a bench
that passed 55/55 against deliberately broken RTL, and the standing rule
since then is that a self-checking suite which has never been shown to
FAIL is a suite of unknown value.  That rule bites harder here than
anywhere else in the repo, because this example's headline finding IS that
a broken crossing can simulate clean -- a suite which cannot tell broken
from fixed would be demonstrating the finding by accident.

Each mutant edits a COPY of the RTL (never the tracked file), runs the
bench in both skew modes, and is DETECTED if either mode goes red, fails
to compile, or dies without printing its result line.

Mutants are also required to be detected by the SPECIFIC check named
below.  A mutant caught by the wrong check is reported as a PARTIAL: it
means the suite noticed something, but not the thing the check claims to
be measuring, and that distinction is the whole content of a control.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
IV_DIR = os.environ.get("IVERILOG_INSTALL_DIR", "/tmp/iverilog_install")
IVERILOG = os.path.join(IV_DIR, "usr", "bin", "iverilog")
VVP = os.path.join(IV_DIR, "usr", "bin", "vvp")
IVL = os.path.join(IV_DIR, "usr", "lib", "x86_64-linux-gnu", "ivl")

RTL = "cdc_crossings.v"
TB = "cdc_crossings_tb.v"

# (label, file, old, new, check id expected to fail, which skew modes)
# ---------------------------------------------------------------------
# EXPECTED SURVIVORS.  Pinned as a MEMBERSHIP, not a count, so that a new
# survivor is a diff rather than an unchanged total -- the repository has
# already been bitten by a count that hid a new member.
#
# Two-sided: a survivor outside this set is a failure, AND an entry in
# this set that starts being DETECTED is also a failure, because that
# would mean the suite gained a power nobody recorded and the recorded
# reason below has gone stale.
# ---------------------------------------------------------------------
EXPECTED_SURVIVORS = {
    "C7": (
        "This mutant compares a SYNCHRONISED signal against the "
        "UNSYNCHRONISED source, which is a real and serious CDC defect -- "
        "it puts a metastable node straight into the destination's "
        "combinational logic. The bench cannot see it, and that is this "
        "example's own thesis arriving from a second direction: the bench "
        "measures FUNCTIONAL coherency and pulse accounting, and this "
        "defect is neither. It changes WHICH flop can go metastable, and "
        "no amount of zero-delay (or skew-modelled) simulation represents "
        "metastability at all. The pulse width it produces is also "
        "harmless to the counters here because source pulses are 160 ns "
        "apart against a 34 ns destination clock. A structural CDC "
        "checker catches this in one pass by noticing that toggle_src "
        "feeds destination logic on an unsynchronised path -- which is "
        "the argument for owning such a tool, made by a defect rather "
        "than by assertion."
    ),
}

MUTANTS = [
    ("C1 the 2FF synchroniser becomes a 1FF (ff2 takes d_src directly)",
     RTL, "            ff2 <= ff1;", "            ff2 <= d_src;",
     "L1", (0, 1)),
    ("C2 Gray encoder shifts by 2 instead of 1 (no longer a Gray code)",
     RTL, "assign gray = bin ^ (bin >> 1);", "assign gray = bin ^ (bin >> 2);",
     "G1", (1,)),
    ("C3 Gray decoder drops the running XOR (b[i] = gray[i])",
     RTL, "            b[i] = b[i+1] ^ gray[i];", "            b[i] = gray[i];",
     "G1", (0, 1)),
    ("C4 Gray encoder becomes the identity (a plain binary crossing "
     "wearing the Gray path's name)",
     RTL, "assign gray = bin ^ (bin >> 1);", "assign gray = bin;",
     "G1", (1,)),
    ("C5 the pulse toggle latches high instead of toggling",
     RTL, "        else if (pulse_src)  toggle_src <= ~toggle_src;",
     "        else if (pulse_src)  toggle_src <= 1'b1;",
     "P2", (0, 1)),
    ("C6 the destination edge detector sees only RISING toggle edges",
     RTL, "    assign pulse_dst = sync_q ^ sync_q_d;",
     "    assign pulse_dst = sync_q & ~sync_q_d;",
     "P2", (0, 1)),
    ("C7 the pulse synchroniser is bypassed (toggle used combinationally)",
     RTL, "        else        sync_q_d <= sync_q;",
     "        else        sync_q_d <= toggle_src;",
     "P2", (0, 1)),
]


def _env():
    """iverilog's preprocessor writes a temp file and fails with the
    misleading 'ivlpp: No input files given' if TMPDIR is not writable.
    In this environment the session filesystem can be full, so TMPDIR is
    pinned to a directory known to have space.  tools/setup_iverilog.sh
    does the same thing via its ivl_tmpdir helper; this script cannot
    source that file (it is a bash function), so it repeats the one fact
    it needs.  Diagnosed 2026-11-10: the first run of this harness
    reported COMPILE_ERROR on the UNMUTATED baseline for this reason, and
    the message named neither TMPDIR nor disk space."""
    env = dict(os.environ)
    env["TMPDIR"] = os.environ.get("IVL_TMPDIR", "/tmp")
    return env


def run_mode(workdir, skew):
    sim = os.path.join(workdir, "sim%d" % skew)
    c = subprocess.run([IVERILOG, "-g2012", "-DSKEW_UNIT_NS=%d" % skew,
                        "-B", IVL, "-o", sim, RTL, TB],
                       cwd=workdir, capture_output=True, text=True,
                       env=_env())
    if c.returncode != 0:
        return "COMPILE_ERROR", c.stdout + c.stderr
    try:
        r = subprocess.run([VVP, "-M", IVL, sim], cwd=workdir,
                           capture_output=True, text=True, timeout=200,
                           env=_env())
    except subprocess.TimeoutExpired:
        return "TIMEOUT", ""
    out = r.stdout + r.stderr
    if "CDC_TB_RESULT:" not in out:
        return "NO_RESULT_LINE", out
    if "CDC_TB_RESULT: ALL_PASS" in out:
        return "PASS", out
    return "FAIL", out


def failed_checks(out):
    return set(re.findall(r"\[FAIL\] (\w+) ", out))


def main():
    print("=" * 74)
    print("MUTATION TEST -- examples/phase6_cdc_basics")
    print("=" * 74)

    for tool in (IVERILOG, VVP):
        if not os.path.exists(tool):
            print("\nTOOLCHAIN MISSING: %s" % tool)
            print("Run:  source tools/setup_iverilog.sh   (do NOT pipe it)")
            return 3

    # Baseline. If the unmutated bench is not green in both modes, nothing
    # below means anything, and that is an error rather than a note.
    with tempfile.TemporaryDirectory() as d:
        for f in (RTL, TB):
            shutil.copy(os.path.join(HERE, f), d)
        base = {sk: run_mode(d, sk) for sk in (0, 1)}
    print("\nBASELINE (unmutated)")
    for sk in (0, 1):
        print("  SKEW_UNIT_NS=%d : %s" % (sk, base[sk][0]))
    if any(base[sk][0] != "PASS" for sk in (0, 1)):
        print("\nBASELINE IS NOT GREEN IN BOTH MODES -- aborting.")
        return 1

    detected, partial, survived = [], [], []
    expected_survived, stale_expectations = [], []
    print("\n%-58s %s" % ("mutant", "verdict"))
    print("-" * 74)
    for label, fname, old, new, expect, modes in MUTANTS:
        with tempfile.TemporaryDirectory() as d:
            for f in (RTL, TB):
                shutil.copy(os.path.join(HERE, f), d)
            path = os.path.join(d, fname)
            src = open(path, encoding="utf-8").read()
            if src.count(old) != 1:
                print("%-58s ANCHOR x%d" % (label[:58], src.count(old)))
                survived.append((label, expect,
                                 "anchor occurs %d times" % src.count(old)))
                continue
            open(path, "w", encoding="utf-8").write(src.replace(old, new))
            results = {sk: run_mode(d, sk) for sk in modes}

        mid = label.split()[0]
        caught_modes = [sk for sk in modes if results[sk][0] != "PASS"]
        if not caught_modes:
            if mid in EXPECTED_SURVIVORS:
                print("%-58s EXPECTED SURVIVOR" % label[:58])
                expected_survived.append((mid, label))
            else:
                print("%-58s *** SURVIVED ***" % label[:58])
                survived.append((label, expect,
                                 "green in modes %s" % (modes,)))
            continue
        if mid in EXPECTED_SURVIVORS:
            # Detected when it was pinned as a survivor: news, and a
            # failure, because the recorded reason is now wrong.
            print("%-58s *** UNEXPECTEDLY DETECTED ***" % label[:58])
            stale_expectations.append((mid, label))
            continue
        hit_expected = any(expect in failed_checks(results[sk][1])
                           for sk in caught_modes)
        states = ",".join("%d:%s" % (sk, results[sk][0]) for sk in modes)
        if hit_expected:
            print("%-58s DETECTED by %s (%s)" % (label[:58], expect, states))
            detected.append((label, expect))
        else:
            got = sorted(set().union(*[failed_checks(results[sk][1])
                                       for sk in caught_modes]) or {"-"})
            print("%-58s PARTIAL: %s not %s" % (label[:58],
                                                ",".join(got), expect))
            partial.append((label, expect, ",".join(got), states))

    print("-" * 74)
    print("%d detected by the named check, %d partial, %d expected "
          "survivors, %d unexpected survivors, %d stale expectations, "
          "of %d"
          % (len(detected), len(partial), len(expected_survived),
             len(survived), len(stale_expectations), len(MUTANTS)))

    if expected_survived:
        print("\nEXPECTED SURVIVORS -- pinned, with the reason recorded, "
              "NOT silently tolerated:")
        for mid, label in expected_survived:
            print("  - %s" % label)
            reason = EXPECTED_SURVIVORS[mid]
            line = "      "
            for word in reason.split():
                if len(line) + len(word) + 1 > 74:
                    print(line)
                    line = "      "
                line += word + " "
            print(line.rstrip())

    if stale_expectations:
        print("\nSTALE EXPECTATIONS -- these were pinned as survivors and "
              "were DETECTED. That is news and a failure: the recorded "
              "reason is now wrong and must be rewritten or removed.")
        for mid, label in stale_expectations:
            print("  - %s" % label)

    if partial:
        print("\nPARTIAL -- the suite noticed, but not via the check whose")
        print("job it was. Reported because a control that fires for the")
        print("wrong reason is not a control:")
        for label, expect, got, states in partial:
            print("  - %s" % label)
            print("      expected %s, got %s  [%s]" % (expect, got, states))
    if survived:
        print("\nSURVIVORS -- GAPS IN THE SUITE, reported not dropped:")
        for label, expect, why in survived:
            print("  - %s" % label)
            print("      expected to be caught by %s; %s" % (expect, why))

    clean = not partial and not survived and not stale_expectations
    print("\nMUTATION_RESULT: %s"
          % ("AS_PINNED (%d detected by the named check, %d expected "
             "survivor%s)" % (len(detected), len(expected_survived),
                              "" if len(expected_survived) == 1 else "s")
             if clean else "INCOMPLETE"))
    return 0 if clean else 2


if __name__ == "__main__":
    sys.exit(main())
