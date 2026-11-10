#!/usr/bin/env bash
# examples/phase6_cdc_basics/run_cdc_sim.sh
#
# Runs the CDC basics bench in BOTH skew modes and writes one transcript.
#
# BOTH modes are required, and that is the point of the example rather than
# a convenience: a single run can only ever show half of the finding. The
# zero-skew run shows that a broken multi-bit crossing simulates CLEAN; the
# skewed run shows the same crossing breaking while the Gray-coded one does
# not. Either run alone is misleading.
#
# Exits non-zero if either mode fails a check, if either mode fails to
# compile, or if either mode does not print its result line at all (a
# simulation that dies silently must not read as a pass -- the repository
# has been bitten by exactly that, see AUTOMATION_LOG.md 2026-10-23).

set -u
cd "$(dirname "$0")"
REPO_ROOT="$(cd ../.. && pwd)"

export IVERILOG_INSTALL_DIR="${IVERILOG_INSTALL_DIR:-/tmp/iverilog_install}"
# Sourced WITHOUT a pipe: piping runs it in a subshell and the iverilog/vvp
# shell functions it defines vanish (AUTOMATION_LOG.md 2026-09-17).
source "$REPO_ROOT/tools/setup_iverilog.sh" > /tmp/cdc_setup.log 2>&1 || {
    echo "SETUP FAILED -- see /tmp/cdc_setup.log"; exit 3; }

# iverilog/vvp are shell FUNCTIONS, not binaries, so `timeout vvp ...` fails
# with "No such file or directory". Call the real binary to wrap it.
VVP_BIN="$IVERILOG_INSTALL_DIR/usr/bin/vvp"
VVP_M="$IVERILOG_INSTALL_DIR/usr/lib/x86_64-linux-gnu/ivl"

RC=0
for SK in 0 1; do
    echo "########################################################"
    echo "# SKEW_UNIT_NS=$SK"
    echo "########################################################"
    SIM="/tmp/cdc_sim_skew$SK"
    if ! iverilog -g2012 -DSKEW_UNIT_NS=$SK -o "$SIM" \
            cdc_crossings.v cdc_crossings_tb.v 2>&1; then
        echo "COMPILE FAILED at SKEW_UNIT_NS=$SK"
        RC=1
        continue
    fi
    OUT=$(timeout 150 "$VVP_BIN" -M "$VVP_M" "$SIM" 2>&1)
    echo "$OUT"
    printf '%s\n' "$OUT" > "/tmp/cdc_mode$SK.txt"
    if ! grep -q "CDC_TB_RESULT:" <<< "$OUT"; then
        echo "NO RESULT LINE at SKEW_UNIT_NS=$SK -- the simulation did not"
        echo "reach its own report, which is a FAILURE and not a pass."
        RC=1
    elif ! grep -q "CDC_TB_RESULT: ALL_PASS" <<< "$OUT"; then
        echo "CHECK FAILURES at SKEW_UNIT_NS=$SK"
        RC=1
    fi
    echo ""
done

# ---------------------------------------------------------------------
# THE CROSS-MODE CHECK.  No single simulation can state the finding, so
# it is checked here, over both transcripts, and it is a CHECK with an
# exit code rather than a paragraph of prose.  X1/X2 would both have
# fired on the -P no-op that produced two identical zero-skew runs.
# ---------------------------------------------------------------------
echo "########################################################"
echo "# CROSS-MODE CHECKS"
echo "########################################################"
X=0
if grep -q "\[PASS\] B1 " /tmp/cdc_mode0.txt 2>/dev/null; then
    echo "  [PASS] X1 the zero-skew run reports B1: the BROKEN crossing simulates clean"
else
    echo "  [FAIL] X1 the zero-skew run did not report B1"; X=1
fi
if grep -q "\[PASS\] B2 " /tmp/cdc_mode1.txt 2>/dev/null \
   && grep -q "\[PASS\] B3 " /tmp/cdc_mode1.txt 2>/dev/null; then
    echo "  [PASS] X2 the skewed run reports B2 and B3: it breaks, and Gray does not"
else
    echo "  [FAIL] X2 the skewed run did not report both B2 and B3"; X=1
fi
if grep -q "\[PASS\] B1 " /tmp/cdc_mode1.txt 2>/dev/null; then
    echo "  [FAIL] X3 the skewed run reported B1, so the skew knob did nothing"
    X=1
else
    echo "  [PASS] X3 the two modes are genuinely different runs, not one run twice"
fi
[ $X -ne 0 ] && RC=1

if [ $RC -eq 0 ]; then
    echo "RUNNER_RESULT: ALL_MODES_PASS"
else
    echo "RUNNER_RESULT: FAILURES"
fi
exit $RC
