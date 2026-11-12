#!/usr/bin/env bash
# tools/run_cdc_gate.sh -- 2026-11-12
#
# THE STRUCTURAL CDC CHECKER AS A GATE, NOT A REPORT.
#
# Discharges the item created 2026-11-11: "RUN THE STRUCTURAL CHECKER OVER THE
# UART RTL AS A GATE, NOT A REPORT -- it runs over rtl/uart_controller.v today
# and finds nothing, which is the right answer for a single-clock design; the
# item is to make that a *committed* check so that a future multi-clock change
# cannot land unexamined."
#
# WHAT THE ITEM GOT WRONG, MEASURED BEFORE WRITING THIS FILE
# ----------------------------------------------------------
# The item is phrased as though cdc_structural_check.py had no verdict to
# offer.  It does: main() already ends `return 1 if findings else 0`, so its
# exit code has been load-bearing since the day it was written.  What was
# missing was never the verdict -- it was a CALLER.  Nothing in this
# repository invoked it, and tools/run_all_harnesses.sh could not, because the
# checker takes file arguments and a bare invocation exits 2 (usage).  So this
# file is a caller with arguments, and the manifest entry for it is the actual
# repair.  Same shape as the 2026-10-15 finding that started
# run_all_harnesses.sh: an exit code nobody reads is not a check.
#
# (The mis-reading has a cause worth recording.  The first measurement taken
# today ran `cdc_structural_check.py ... | tail` and read $?, which is tail's
# exit status and not the checker's -- so the checker looked like it always
# exited 0.  This is the same hazard as the logged 2026-09-17 gotcha about
# `source tools/setup_iverilog.sh | tail`: a pipe silently answers a different
# question.  Measured again without the pipe, every mode was already correct.)
#
# FOUR SECTIONS, AND SECTION 3 IS WHY THIS IS NOT AN EXPECTED-FAIL LIST
# --------------------------------------------------------------------
# The whole tree has exactly one finding and it is deliberate: the WRONG
# multi-bit crossing in examples/phase6_cdc_basics/cdc_crossings_tb.v, which
# that example exists in order to be wrong about.  A gate over the whole tree
# would therefore be permanently red, and the obvious fix -- a list of paths
# whose findings do not count -- is the "green claim over a red guard" that
# run_all_harnesses.sh refuses by design.
#
# So the tree is PARTITIONED instead, and both halves are asserted:
#
#   1  the checker's own self-test passes                       (25/25, rc 0)
#   2  GATE: the shipped sources -- rtl/ bfm/ checkers/ -- have
#      ZERO findings, no exceptions, rc 0
#   3  POSITIVE CONTROL: the deliberate crossing STILL FIRES, rc 1.  A gate
#      that cannot fail is not a gate, and if the checker goes blind section 2
#      passes for the wrong reason.  This is the half an expected-fail list
#      throws away.
#   4  the set of files carrying findings over the whole tree is EXACTLY
#      {cdc_crossings_tb.v}.  A new file joining that set fails this script,
#      which is the "cannot land unexamined" the item asked for -- stated as
#      a set identity and not as a count budget, so a finding that MOVES from
#      the demo file to real RTL cannot net out to the same number.
#
# Section 5 pins the exit-code contract itself (0 clean / 1 findings / 2
# usage), because every section above is a claim about an exit code and a
# refactor that made bare mode exit 0 would quietly make this file vacuous.

set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
CHECKER="tools/cdc_structural_check.py"
PY="${PYTHON:-python3}"

PASS=0
FAIL=0
pass() { PASS=$((PASS + 1)); echo "  [PASS] $1"; }
fail() { FAIL=$((FAIL + 1)); echo "  [FAIL] $1"; echo "         $2"; }

echo "======================================================================"
echo "CDC STRUCTURAL GATE -- $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "the first caller of $CHECKER in this repository"
echo "======================================================================"
echo "  repo root : $ROOT"
echo

DEMO="examples/phase6_cdc_basics/cdc_crossings_tb.v"
SHIPPED=$(find rtl bfm checkers -name '*.v' 2>/dev/null | sort)
ALL=$(find . -name '*.v' -not -path './.git/*' | sed 's#^\./##' | sort)
N_SHIPPED=$(printf '%s\n' "$SHIPPED" | grep -c . || true)
N_ALL=$(printf '%s\n' "$ALL" | grep -c . || true)

# --- 1 -------------------------------------------------------------------
echo "----------------------------------------------------------------------"
echo "SECTION 1 -- the checker's own self-test"
echo "----------------------------------------------------------------------"
ST_OUT=$($PY "$CHECKER" --selftest 2>&1); ST_RC=$?
ST_LINE=$(printf '%s\n' "$ST_OUT" | grep -E '^TOTAL:' || echo "no TOTAL line")
if [ "$ST_RC" -eq 0 ]; then
    pass "self-test exits 0 -- $ST_LINE"
else
    fail "self-test exits $ST_RC" "$ST_LINE"
fi
if printf '%s\n' "$ST_OUT" | grep -q 'TOTAL: 25 passed, 0 failed'; then
    pass "and it is still the 25 checks the 2026-11-11 entry committed"
else
    fail "self-test check count moved" \
         "expected 'TOTAL: 25 passed, 0 failed', got: $ST_LINE"
fi

# --- 2 -------------------------------------------------------------------
echo
echo "----------------------------------------------------------------------"
echo "SECTION 2 -- GATE: the shipped sources must have zero findings"
echo "----------------------------------------------------------------------"
echo "  files gated ($N_SHIPPED): $(printf '%s ' $SHIPPED)"
GATE_OUT=$($PY "$CHECKER" $SHIPPED 2>&1); GATE_RC=$?
printf '%s\n' "$GATE_OUT" | sed 's/^/    /'
if [ "$GATE_RC" -eq 0 ]; then
    pass "zero structural CDC findings in rtl/ bfm/ checkers/ (rc 0)"
else
    fail "the shipped sources carry a structural CDC finding (rc $GATE_RC)" \
         "this is the gate; read the finding above.  A genuinely multi-clock
         change needs a synchroniser and a Gray encoder, not an exception here."
fi
if [ "$N_SHIPPED" -ge 4 ]; then
    pass "and the gated set is non-degenerate ($N_SHIPPED files)"
else
    fail "the gated set has collapsed to $N_SHIPPED files" \
         "a gate over nothing passes; expected the 4 of rtl/ bfm/ checkers/"
fi

# --- 3 -------------------------------------------------------------------
echo
echo "----------------------------------------------------------------------"
echo "SECTION 3 -- POSITIVE CONTROL: the deliberate crossing still fires"
echo "----------------------------------------------------------------------"
if [ -f "$DEMO" ]; then
    $PY "$CHECKER" "$DEMO" > /dev/null 2>&1; DEMO_RC=$?
    if [ "$DEMO_RC" -eq 1 ]; then
        pass "$DEMO still exits 1, so section 2's rc 0 means something"
    else
        fail "the deliberate wrong crossing no longer fires (rc $DEMO_RC)" \
             "the checker has gone blind, or the example was repaired without
         repairing this control.  Section 2 cannot be trusted until this is."
    fi
else
    fail "the positive control file is gone" "$DEMO not found"
fi

# --- 4 -------------------------------------------------------------------
echo
echo "----------------------------------------------------------------------"
echo "SECTION 4 -- the finding set over the whole tree is exactly one file"
echo "----------------------------------------------------------------------"
ALL_OUT=$($PY "$CHECKER" $ALL 2>&1); ALL_RC=$?
FOUND_FILES=$(printf '%s\n' "$ALL_OUT" \
    | grep -oE '[A-Za-z0-9_./-]+\.v:[0-9]+' | cut -d: -f1 \
    | xargs -n1 basename 2>/dev/null | sort -u)
EXPECTED_FILES="$(basename "$DEMO")"
echo "  files scanned          : $N_ALL"
echo "  files carrying findings: $(printf '%s ' $FOUND_FILES)"
echo "  expected               : $EXPECTED_FILES"
if [ "$FOUND_FILES" = "$EXPECTED_FILES" ]; then
    pass "exactly {$EXPECTED_FILES} carries findings; no other file does"
else
    fail "the finding set changed" \
         "got {$(printf '%s ' $FOUND_FILES)}, expected {$EXPECTED_FILES}.
         A file JOINING this set is an unexamined crossing.  A file LEAVING it
         means a control stopped working.  Neither is a budget overrun."
fi
if [ "$N_ALL" -ge 40 ]; then
    pass "and the scan still covers the tree ($N_ALL .v files)"
else
    fail "the scanned set shrank to $N_ALL files" "expected >= 40"
fi

# --- 5 -------------------------------------------------------------------
echo
echo "----------------------------------------------------------------------"
echo "SECTION 5 -- the exit-code contract every section above relies on"
echo "----------------------------------------------------------------------"
$PY "$CHECKER" > /dev/null 2>&1; BARE_RC=$?
if [ "$BARE_RC" -eq 2 ]; then
    pass "a bare invocation exits 2 (usage), so it cannot be mistaken for clean"
else
    fail "a bare invocation exits $BARE_RC, not 2" \
         "if it exits 0 then an empty argument list is indistinguishable from
         a clean gate, and sections 2 and 4 become vacuous."
fi
if [ "$ALL_RC" -eq 1 ] && [ "$GATE_RC" -eq 0 ]; then
    pass "findings -> 1 and clean -> 0, measured in this run, not assumed"
else
    fail "the 0/1 contract did not hold in this run" \
         "whole tree rc=$ALL_RC (expected 1), shipped rc=$GATE_RC (expected 0)"
fi

echo
echo "======================================================================"
echo "TOTAL: $PASS passed, $FAIL failed"
echo "======================================================================"
[ "$FAIL" -eq 0 ] || exit 1
exit 0
