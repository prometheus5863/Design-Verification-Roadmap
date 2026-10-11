#!/bin/sh
# run_mutation_tests.sh -- mutation test for uart_uvm_crv_tb.py.
#
# A suite that passes proves nothing about its ability to fail, and this
# repository has caught a bench passing 55/55 against deliberately broken RTL
# (2026-09-17) and a suite printing PASS over its own errors (2026-09-18).  So
# every self-checking suite here gets injected defects and is required to fail.
#
# Each mutant is applied to a COPY of rtl/uart_controller.v and the UNMODIFIED
# testbench is pointed at it through the Makefile's RTL variable; nothing under
# rtl/ is ever edited.
#
# INJECTION GUARD, and why it counts sites rather than comparing files.
# 2026-10-07 found three harnesses in this repo guarding with `cmp -s`, which
# answers "did the file change" and not "did the change I specified land".  A
# sed expression that matches two sites when one was intended, or zero because
# the source was reformatted, both pass `cmp`.  Every mutant below therefore
# declares EXPECTED_SITES and the run aborts if the count differs.
#
# Mutants run with POLICIES=1 N_SEEDS=1 (the steered policy closes in ~46
# pushes against the pure-random median of 275), and RESULTS_FILE is pointed
# at a scratch path so a mutation run never appends to the closure
# distribution in closure_results.csv.
#
# Usage:  sh run_mutation_tests.sh [control|M1|M2|M3|M4|all]

set -u
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)
SRC="$ROOT/rtl/uart_controller.v"
WORK="/tmp/uvm_crv_mut"
mkdir -p "$WORK"

run_one() {
    NAME="$1"; SITES="$2"; EXPR="$3"; WANT="$4"; DESC="$5"
    MUT="$WORK/uart_controller_$NAME.v"
    cp "$SRC" "$MUT"
    if [ "$NAME" = "control" ]; then
        GOT_SITES=0
    else
        GOT_SITES=$(grep -c -- "$6" "$MUT")
        sed -i "$EXPR" "$MUT"
    fi
    echo "----------------------------------------------------------------"
    echo "MUTANT $NAME  ($DESC)"
    echo "  expected sites: $SITES   found: $GOT_SITES"
    if [ "$GOT_SITES" != "$SITES" ]; then
        echo "  INJECTION GUARD FAILED: the pattern matched $GOT_SITES sites,"
        echo "  not $SITES.  The mutant was NOT applied as specified, so the"
        echo "  run below would measure nothing.  ABORT."
        echo "  VERDICT: GUARD_FAIL"
        return 2
    fi
    if [ "$NAME" != "control" ] && cmp -s "$SRC" "$MUT"; then
        echo "  INJECTION GUARD FAILED: the copy is identical to the source."
        echo "  VERDICT: GUARD_FAIL"
        return 2
    fi
    rm -rf "$HERE/sim_build"
    ( cd "$HERE" && RTL="$MUT" POLICIES=1 N_SEEDS=1 \
        RESULTS_FILE="$WORK/mutation_scratch.csv" make ) \
        > "$WORK/$NAME.log" 2>&1
    if grep -q "RESULT: PASS" "$WORK/$NAME.log"; then
        GOT=PASS
    else
        GOT=FAIL
    fi
    echo "  suite outcome: $GOT   required: $WANT"
    # Provenance, 2026-10-09's rule: a verdict must name the mechanism that
    # produced it.  A mutant "detected" by a crash is a different fact from
    # one detected by a failing check, and the two were 3-of-6 apart in
    # mutation_test_reachable_cross.py.
    if [ "$GOT" = "FAIL" ]; then
        if grep -q "FIRST .* FAILURES:" "$WORK/$NAME.log"; then
            MECH="failing check"
            echo "  first failure: $(grep -A1 'FIRST .* FAILURES:' "$WORK/$NAME.log" | tail -1 | sed 's/^ *//')"
        elif grep -q "RESULT: FAIL" "$WORK/$NAME.log"; then
            MECH="suite verdict with no listed failure"
        else
            MECH="crash or timeout (no RESULT line)"
        fi
        echo "  mechanism: $MECH"
    else
        MECH="n/a"
    fi
    if [ "$GOT" = "$WANT" ]; then
        echo "  VERDICT: OK"
        return 0
    fi
    echo "  VERDICT: UNEXPECTED -- suite $GOT where $WANT was required"
    return 1
}

WHICH=${1:-all}
RC=0
for M in control M1 M2 M3 M4; do
    [ "$WHICH" = "all" ] || [ "$WHICH" = "$M" ] || continue
    case $M in
    control)
        run_one control 0 "" PASS "unmutated DUT -- the suite must PASS" "" || RC=1 ;;
    M1)
        run_one M1 1 \
            's|wire rx_in = cfg_loopback ? tx_line : rx;|wire rx_in = rx;|' \
            FAIL "loopback mux removed: RX never sees TX" \
            'wire rx_in = cfg_loopback ? tx_line : rx;' || RC=1 ;;
    M2)
        run_one M2 1 \
            's|(cfg_parity == PARITY_EVEN) ?  \^tx_fifo\[tx_rptr\] :|(cfg_parity == PARITY_EVEN) ? ~^tx_fifo[tx_rptr] :|' \
            FAIL "TX even-parity bit inverted: RX must flag parity_err" \
            '(cfg_parity == PARITY_EVEN) ?  \^tx_fifo\[tx_rptr\] :' || RC=1 ;;
    M3)
        run_one M3 1 \
            's|ADDR_RX_DATA:  prdata = rx_fifo\[rx_rptr\];|ADDR_RX_DATA:  prdata = rx_fifo[~rx_rptr];|' \
            FAIL "RX_DATA reads the wrong FIFO slot: bytes out of order" \
            'ADDR_RX_DATA:  prdata = rx_fifo\[rx_rptr\];' || RC=1 ;;
    M4)
        run_one M4 1 \
            "s|wire tx_full  = (tx_cnt == 4'd8);|wire tx_full  = (tx_cnt == 4'd7);|" \
            FAIL "tx_full asserts one entry early" \
            "wire tx_full  = (tx_cnt == 4'd8);" || RC=1 ;;
    esac
done
echo "----------------------------------------------------------------"
echo "mutation run exit: $RC  (0 = every mutant behaved as required)"
exit $RC
