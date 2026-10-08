"""
mutation_test_signatures.py

Mutation harness for the BOUNDED DISTINCT-SIGNATURE mechanism added to
`UartCoverage` in uart_uvm_tb.py on 2026-10-08, in the form this repository
has used since 2026-09-18: inject a defect into a COPY of the testbench,
re-run the simulator against the UNMODIFIED RTL, and require the run to FAIL.

WHY THIS MECHANISM NEEDS A HARNESS, and it is a stronger argument than the
witness log's was.  The witness log's failure mode was that a run-axis audit
would audit a fiction.  The signature set's failure mode is worse, because
the whole purpose of the set is to let a reader STOP labelling diversity
numbers as lower bounds.  A broken signature set does not produce an
obviously wrong number; it produces a number that looks EXACT and is not.
2026-10-03's rule in its sharpest form: a bound that cannot report hitting
itself is not a bound, it is a silent truncation -- and a silent truncation
that prints the word EXACT is the specific artefact this harness has to kill.

THE MUTANTS, each the realistic way this breaks:

  S1  the membership test is dropped, so the "distinct" list collects
      duplicates and every diversity number inflates.  S-b must catch it.
  S2  the signature keeps a per-sample field, so every sample is distinct,
      the set saturates and diversity stops meaning anything.  S-d must
      catch it: the witnesses' own stimuli no longer appear in the set.
  S3  the signature is filed under the WRONG CELL while the counts stay
      correct -- the fault a reader cannot see by inspection.  S-d / S-a.
  S4  sig_overflow stops incrementing.  THIS IS THE IMPORTANT ROW.  Every
      check from S-a to S-e is computed FROM the stored list and all five
      are blind to it: the cell simply prints EXACT while truncating.  S-f,
      which compares the stored accounting against an independent 64-bit
      crc32 mask, exists only for this mutant and must catch it.
  S5  the SIGNATURE_KEEP bound is removed, so the log grows with simulation
      length.  Not a correctness fault -- a log fault, and the reason
      bounded logging gets abandoned.  S-c must catch it.
  S6  the crc32 mask stops being updated, so S-f's own evidence disappears.
      A control that can be disabled without any other check noticing is a
      control with no control, and this row is here to find out which it is.

  B   CONTROL B: the signature built with an f-string instead of
      %-formatting.  Different code, byte-identical output.  MUST SURVIVE.

AN ARRIVAL CONTROL, AND THE RUN THAT FORCED IT
----------------------------------------------
The first run of this harness reported S4 and S5 as SURVIVED, which would
have meant the mechanism does not detect its two most important faults.  It
means nothing of the kind.  Both rows were run against
`test_uart_uvm_milestone`, in which **27 of 27 cells are EXACT**: the
SIGNATURE_KEEP bound never bites there, so `sig_overflow` is never
incremented and the bound is never consulted.  Breaking an overflow counter
that never increments, or removing a cap that is never reached, changes
nothing observable.  **Those mutants did not survive; they never arrived.**

This is 2026-09-29's rule -- a mutation that does not arrive is
indistinguishable from a system that does not respond -- in the one place
this repository had not yet put a control for it, and it was one run away
from being committed as "the mechanism does not detect S4/S5".

Two repairs, both here:

  1. Each row names the TESTCASE it runs under.  S4 and S5 run against
     `test_uart_adaptive_observer`, whose longer run leaves 5 of 11 cells
     BOUNDED, so the bound genuinely bites and both faults are reachable.
     Control A is re-run for every distinct testcase, because a baseline
     from a different stimulus is not a baseline.

  2. An ARRIVAL CONTROL, which is the mechanisable form and does not depend
     on anyone having noticed the above.  For every row, the mutant's own
     COV_SIGNATURE block is compared against control A's block for the SAME
     testcase.  If they are identical, the mutant changed nothing the
     mechanism prints and the row is reported **INERT** -- scored as neither
     killed nor survived, exactly as a voided injection is.  A row can now
     only be called SURVIVED if it is first shown to have DONE something.

A POST-INJECTION CONTROL, IN PYTHON, CLOSING A STANDING ITEM
------------------------------------------------------------
AUTOMATION_LOG 2026-10-07 recorded as an open item that this repository's
python-injected mutants are guarded by `assert old in s`, which is control
B's ANCHOR test and not control B: it checks the text was there BEFORE, not
that it is gone AFTER.  `tools/mutation_controls.sh` grew `mc_controls_text`
for exactly this and nothing called it.  `controls_text()` below is its
python equivalent, it runs on every row here, and a row whose verdict is not
usable is VOIDED -- scored as neither killed nor survived, because a mutant
that did not arrive says nothing about the suite (2026-09-29).

The failure path is exercised rather than argued for: `--selftest` injects a
deliberately HALF_INJECTED row and a deliberately NOT_INJECTED row and
requires the harness to void both.  A control whose failure path never runs
is a control that has never been tested.

Requires the toolchain: `source tools/setup_iverilog.sh` (do NOT pipe it),
`export PATH="$HOME/.local/bin:$PATH"` for cocotb-config, and the uvm-python
stack from notes/2026-09-06-uvm-python-toolchain-resolution.md.

Run:   python3 mutation_test_signatures.py [--selftest]
"""

import datetime
import os
import re
import shutil
import subprocess
import sys
import tempfile

TARGET = "uart_uvm_tb.py"
# The default testcase: the fastest of the five (0.7 s of simulation).  Rows
# whose fault is only reachable once the SIGNATURE_KEEP bound bites name
# test_uart_adaptive_observer instead -- see the docstring.
TESTCASE = "test_uart_uvm_milestone"
BOUNDED_TESTCASE = "test_uart_adaptive_observer"

SIGOF_ORIG = '        return "%s %s" % (src, item.convert2string())'
MEMBER_ORIG = '        if sig not in sigs:'
MASK_ORIG = ('        self.sig_mask[cell] = (self.sig_mask.get(cell, 0)\n'
             '                               | (1 << (zlib.crc32(sig.encode()) & 63)))')

# (tag, description, old, new, must_be_caught, testcase)
MUTANTS = [
    ("S1", "the membership test is dropped: the distinct list collects "
           "duplicates",
     MEMBER_ORIG, '        if True:', True, TESTCASE),

    ("S2", "the signature keeps a per-sample field, so every sample is "
           "distinct",
     SIGOF_ORIG,
     '        return "s%d %s %s" % (id(item) & 0xffff, src, '
     'item.convert2string())', True, TESTCASE),

    ("S3", "the signature is filed under the WRONG CELL (counts stay correct)",
     '        sigs = self.signatures.setdefault(cell, [])',
     '        sigs = self.signatures.setdefault(("bin", "cp_rx_error", '
     '"clean"), [])', True, TESTCASE),

    ("S4", "sig_overflow stops incrementing: a truncating cell prints EXACT. "
           "S-a..S-e are ALL blind to this; S-f exists for it",
     '                self.sig_overflow[cell] += 1',
     '                pass', True, BOUNDED_TESTCASE),

    ("S5", "the SIGNATURE_KEEP bound is removed (the log-growth fault)",
     '            if len(sigs) < self.SIGNATURE_KEEP:',
     '            if True:', True, BOUNDED_TESTCASE),

    ("S6", "the crc32 mask stops being updated, so S-f's own evidence "
           "disappears",
     MASK_ORIG,
     '        self.sig_mask[cell] = self.sig_mask.get(cell, 0)', None,
     BOUNDED_TESTCASE),

    # ---- CONTROL B: different code, identical signature text. MUST SURVIVE.
    ("B", "CONTROL B: the signature built with an f-string instead of "
          "%-formatting (identical output, different code)",
     SIGOF_ORIG, '        return f"{src} {item.convert2string()}"', False,
     TESTCASE),
]

SELFTEST_ROWS = [
    ("MX", "SELFTEST: an anchor whose replacement still CONTAINS it, so the "
           "replaced text survives in the mutant",
     MEMBER_ORIG, MEMBER_ORIG + '  # untouched', None, TESTCASE),
    ("MY", "SELFTEST: a replacement identical to the anchor, so the mutant "
           "is byte-identical to the original",
     SIGOF_ORIG, SIGOF_ORIG, None, TESTCASE),
]


# ---------------------------------------------------------------------
# The post-injection control, in python.  mc_controls_text's semantics.
# ---------------------------------------------------------------------
def controls_text(original, mutant, frm, to):
    """-> (verdict_token, detail).

    Control A: the inserted text is PRESENT in the mutant, and was absent
               from the original -- otherwise the row cannot fail control A
               and certifies nothing (OK_A_VACUOUS).
    Control B: the replaced text is GONE from the mutant.  This is the check
               `assert old in s` does not perform, and the reason this
               function exists.
    """
    if mutant == original:
        return "NOT_INJECTED", "the mutant is byte-identical to the original"
    n_before = original.count(frm)
    if n_before == 0:
        return "B_NO_ANCHOR", "the anchor does not occur in the original"
    n_after = mutant.count(frm)
    if n_after >= n_before:
        return ("B_SELF_MATCHING",
                "the anchor still matches the mutant %d time(s), as often as "
                "it matched the original (%d): it matches its own replacement"
                % (n_after, n_before))
    if n_after > 0:
        return ("HALF_INJECTED",
                "the replaced text still occurs %d time(s) in the mutant, "
                "down from %d -- the substitution took on some sites and not "
                "others, and a plain file-differs check passes this row"
                % (n_after, n_before))
    if to not in mutant:
        return "A_MISSING", "the inserted text is not present in the mutant"
    if to in original:
        return ("OK_A_VACUOUS",
                "control B held so the mutant is complete, but the inserted "
                "text was ALREADY in the original, so control A cannot fail "
                "on this row")
    if n_before > 1:
        return ("OK_MULTISITE:%d" % n_before,
                "controls A and B both hold; the anchor matched %d sites and "
                "all of them were replaced" % n_before)
    return "OK", "controls A and B both hold; one site"


def verdict_usable(tok):
    return (tok == "OK" or tok.startswith("OK_MULTISITE")
            or tok == "OK_A_VACUOUS" or tok.startswith("A_SKIPPED"))


def build_tree(root, src_text):
    """A scratch copy of the tree the Makefile expects.  The RTL is copied
    UNMODIFIED -- only the testbench is mutated, so a failure cannot be a
    broken DUT."""
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


def run(ex, testcase=TESTCASE):
    env = dict(os.environ, TESTCASE=testcase)
    try:
        p = subprocess.run(["make"], cwd=ex, env=env, capture_output=True,
                           text=True, timeout=600)
        return p.returncode, p.stdout + p.stderr
    except subprocess.TimeoutExpired:
        return -1, "TIMEOUT: the mutant did not terminate"


SIGBLOCK_RE = re.compile(
    r"\[COV_SIGNATURE\] distinct stimulus signatures.*?(?=\nUVM_|\Z)",
    re.S)


def signature_block(out):
    """The printed COV_SIGNATURE block, with the UVM timestamp prefix and the
    EXACT/BOUNDED counts included.  This is what the arrival control
    compares: if a mutant leaves it byte-identical to the baseline's, the
    mutant changed nothing this mechanism reports."""
    m = SIGBLOCK_RE.search(out)
    return m.group(0) if m else ""


def killers(out):
    """Why did the run fail?  The S-tag form is anchored on the COLON, for
    the 2026-10-06 reason: the summary line reads 'audit verdict ... over
    checks S-a to S-f' and a bare `S-[a-f] FAILED` would match inside it,
    crediting S-f with detections it never made."""
    reasons = []
    for tag in re.findall(r"(S-[a-f]) FAILED:", out):
        if tag not in reasons:
            reasons.append(tag)
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
    if "Traceback" in out:
        reasons.append("python traceback")
    return reasons


def main(selftest=False):
    here = os.path.dirname(os.path.abspath(__file__))
    today = datetime.date.today().isoformat()
    lines = []

    def say(s=""):
        lines.append(s)
        print(s)

    def write():
        name = ("mutation_report_signatures_selftest_%s.txt" if selftest
                else "mutation_report_signatures_%s.txt") % today
        with open(os.path.join(here, name), "w") as fh:
            fh.write("\n".join(lines) + "\n")

    src = open(os.path.join(here, TARGET)).read()

    say("=" * 78)
    say("MUTATION TEST -- the bounded distinct-signature mechanism (S-a..S-f)")
    say("date: %s%s" % (today, "   MODE: SELFTEST" if selftest else ""))
    say("=" * 78)
    say()

    rows = SELFTEST_ROWS if selftest else MUTANTS

    # Control A once per DISTINCT testcase the rows use.  A baseline taken
    # under a different stimulus is not a baseline: the whole reason S4 and
    # S5 moved to test_uart_adaptive_observer is that the milestone test does
    # not exercise the bound, so comparing them against the milestone
    # baseline would compare two different experiments.
    baselines = {}
    say("CONTROL A -- the UNMUTATED environment, once per testcase")
    for tc in sorted({r[5] for r in rows}):
        root = tempfile.mkdtemp(prefix="sigmut_ctrlA_")
        try:
            rc, out = run(build_tree(root, src), tc)
        finally:
            shutil.rmtree(root, ignore_errors=True)
        why = killers(out)
        blk = signature_block(out)
        baselines[tc] = blk
        nex = re.findall(r"(\d+) of (\d+) cells EXACT", blk)
        say("  %-38s %s  rc=%d  %s  killers=%s"
            % (tc, "PASS" if not why else "FAIL", rc,
               ("%s of %s EXACT" % nex[0]) if nex else "no signature block",
               why or "none"))
        if why or not blk:
            say()
            say("  Control A FAILED for %s, so no mutant verdict under it" % tc)
            say("  would mean anything.  Stopping: a harness whose baseline")
            say("  does not pass cannot attribute a failure to its mutant")
            say("  (2026-09-19), and one with no signature block has nothing")
            say("  for the arrival control to compare against.")
            say("RESULT: ABORTED")
            write()
            return 1
    say()
    say("  %-4s %-9s %-16s %-28s %s"
        % ("tag", "outcome", "control", "testcase", "killers"))
    killed = survived = voided = inert = 0
    details = []
    for tag, desc, old, new, must, tc in rows:
        if old not in src:
            tok, detail = "B_NO_ANCHOR", "the anchor is absent from " + TARGET
            mut = src
        else:
            mut = src.replace(old, new, 1)
            tok, detail = controls_text(src, mut, old, new)
        if not verdict_usable(tok):
            voided += 1
            say("  %-4s %-9s %-16s %-28s %s"
                % (tag, "VOIDED", tok, tc, "-"))
            details.append((tag, desc, tok, detail, None, tc, None))
            continue
        root = tempfile.mkdtemp(prefix="sigmut_%s_" % tag)
        try:
            rc, out = run(build_tree(root, mut), tc)
        finally:
            shutil.rmtree(root, ignore_errors=True)
        why = killers(out)
        blk = signature_block(out)
        arrived = (blk != baselines[tc])
        if why:
            killed += 1
            outcome = "KILLED"
        elif not arrived:
            # The mutant changed nothing this mechanism prints.  It did not
            # survive -- it never arrived (2026-09-29), and calling it
            # SURVIVED would be a claim that the mechanism is blind to a
            # fault it was never shown.
            inert += 1
            outcome = "INERT"
        else:
            survived += 1
            outcome = "SURVIVED"
        say("  %-4s %-9s %-16s %-28s %s"
            % (tag, outcome, tok, tc, ", ".join(why) or "-"))
        details.append((tag, desc, tok, detail, why, tc, arrived))
    say()

    for tag, desc, tok, detail, why, tc, arrived in details:
        say("  %s  %s" % (tag, desc))
        say("      testcase: %s" % tc)
        say("      control:  %s -- %s" % (tok, detail))
        if arrived is not None:
            say("      arrival:  %s"
                % ("the COV_SIGNATURE block DIFFERS from control A's, so the "
                   "mutant reached the mechanism"
                   if arrived else
                   "the COV_SIGNATURE block is BYTE-IDENTICAL to control A's: "
                   "the mutant changed nothing this mechanism prints and is "
                   "scored as neither killed nor survived"))
        if why is not None:
            say("      killers:  %s" % (", ".join(why) or "none"))
    say()

    ok = True
    if selftest:
        say("SELFTEST requires EVERY row to be VOIDED, because both rows are")
        say("deliberately broken injections.  A harness that scored them would")
        say("be scoring mutants that never arrived (2026-09-29).")
        ok = (voided == len(rows) and killed == 0 and survived == 0
              and inert == 0)
        say("  voided=%d of %d, killed=%d, survived=%d  -> %s"
            % (voided, len(rows), killed, survived, "PASS" if ok else "FAIL"))
    else:
        must_kill = [m[0] for m in MUTANTS if m[4] is True]
        must_live = [m[0] for m in MUTANTS if m[4] is False]
        reported = [m[0] for m in MUTANTS if m[4] is None]
        got_killed = [d[0] for d in details if d[4]]
        got_lived = [d[0] for d in details if d[4] == [] and d[6]]
        got_inert = [d[0] for d in details if d[4] == [] and d[6] is False]
        missing = [t for t in must_kill if t not in got_killed]
        wrong = [t for t in must_live if t in got_killed]
        say("EXPECTED: %s killed, %s survive, %s REPORTED either way"
            % ("/".join(must_kill), "/".join(must_live), "/".join(reported)))
        say("GOT:      %s killed, %s survived, %s INERT"
            % ("/".join(got_killed) or "none", "/".join(got_lived) or "none",
               "/".join(got_inert) or "none"))
        real_missing = [t for t in missing if t in got_lived]
        if real_missing:
            ok = False
            say("  FAIL: %s SURVIVED and must not have -- it reached the "
                "mechanism and the mechanism did not react"
                % "/".join(real_missing))
        if [t for t in missing if t in got_inert]:
            ok = False
            say("  FAIL: %s is INERT under its testcase -- the row proves "
                "nothing and the harness needs a stimulus that reaches it, "
                "not a verdict (2026-09-29)"
                % "/".join(t for t in missing if t in got_inert))
        if wrong:
            ok = False
            say("  FAIL: %s was killed and must not have been -- the suite "
                "rejects a correct rewrite" % "/".join(wrong))
        if voided:
            say("  NOTE: %d row(s) VOIDED by the post-injection control and "
                "scored as neither" % voided)
        if inert:
            say("  NOTE: %d row(s) INERT -- they reached the simulator but "
                "left the mechanism's own output byte-identical" % inert)
        if "B" in got_inert:
            say()
            say("  CONTROL B IS INERT, AND THAT IS STRONGER THAN SURVIVED.")
            say("  Control B's entire claim is that a different implementation")
            say("  produces the SAME output.  'SURVIVED' only says the suite")
            say("  did not complain; INERT says the printed signature block is")
            say("  byte-identical to the baseline's, which is the claim itself")
            say("  rather than a weaker proxy for it.  The arrival control was")
            say("  added for S4/S5 and it sharpened control B for free.")
        if "S6" in got_inert:
            say()
            say("  S6 IS INERT, AND THAT IS A LIMITATION OF S-f, MEASURED.")
            say("  Disabling the crc32 mask entirely changes nothing anyone")
            say("  can see: with an empty mask popcount is 0, which is <= any")
            say("  accounting, so S-f passes.  **S-f is ONE-SIDED.**  It can")
            say("  detect an accounting that is too small; it cannot detect")
            say("  its own evidence going missing.  A control with no control")
            say("  is exactly what 2026-10-07's phase4_ral work gave a POSITIVE")
            say("  CONTROL for, and S-f does not have one yet: nothing here")
            say("  requires S-f to FIRE on a case where it should.  Recorded as")
            say("  an open item rather than papered over, and it is the reason")
            say("  this row is in the table at all -- a mutant whose job is to")
            say("  find out which of two things is true has to be run even")
            say("  when its outcome is not required.")
        say()
        say("  S4 IS THE ROW THAT JUSTIFIES S-f.  Every check from S-a to S-e")
        say("  reads the stored signature list, so none of them can see an")
        say("  overflow counter that stopped incrementing: the cell prints")
        say("  EXACT and truncates.  If S4 is killed by S-f and by nothing")
        say("  else, that is the independent 64-bit mask doing the one job it")
        say("  was added for, and the claim is a measurement rather than an")
        say("  argument about code paths.")
        for d in details:
            if d[0] == "S4" and d[4] is not None:
                say("  S4 killers: %s" % (", ".join(d[4]) or "none"))
            if d[0] == "S6" and d[4] is not None:
                say("  S6 killers: %s  -- REPORTED, not required either way: "
                    "whether disabling the mask is itself detectable is a "
                    "fact about this mechanism that nothing here had measured."
                    % (", ".join(d[4]) or "none"))

    say()
    say("=" * 78)
    say("RESULT: %s -- %d killed, %d survived, %d inert, %d voided"
        % ("PASS" if ok else "FAIL", killed, survived, inert, voided))
    say("=" * 78)
    write()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(selftest="--selftest" in sys.argv))
