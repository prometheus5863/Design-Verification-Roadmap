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
# 2026-10-18: was WORK="/tmp/uvm_crv_mut", a FIXED path in a shared namespace.
# Every other mutation harness here already uses `mktemp -d`; this one was the
# outlier.  A fixed name in /tmp is inherited from, and collides with, any other
# session -- which is how tools/harness_file_closure_audit.py came to accuse
# eleven harnesses of failing to elaborate on 2026-10-18 when the real cause
# was a .sim file left by the previous session, owned by another user.  This
# harness has no resumability reason to keep a stable path (contrast
# examples/phase5_property_coverage, where the stable path IS load-bearing and
# is scoped by uid instead of randomised).
WORK="$(mktemp -d /tmp/uvm_crv_mut.XXXXXX)"
trap 'rm -rf "$WORK"' EXIT

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
    # AMENDED 2026-10-16.  The block above computes MECH, prints it, and the
    # verdict below then IGNORED it: a mutant required to FAIL was scored OK
    # whenever the suite failed, by any means at all.  So the 2026-10-09 rule
    # -- a verdict must name the mechanism that produced it -- was implemented
    # for the REPORT and not for the VERDICT, which is the half that counts.
    #
    # Found by tools/run_all_harnesses.sh on its first run, in this
    # environment, with cocotb absent.  Every invocation crashed before the
    # testbench started, and this suite printed:
    #
    #     M1  suite outcome: FAIL  required: FAIL
    #         mechanism: crash or timeout (no RESULT line)
    #         VERDICT: OK                      <-- four times
    #
    # Four mutants "detected" by a toolchain that could not run the DUT at
    # all.  That is a FALSE DETECTED of exactly the kind 2026-10-09 named,
    # and the only thing between this suite and a full card of OK verdicts
    # was the single control row at the top.
    #
    # A mutant that fails by crashing is NOT detected and NOT escaped: it is
    # VOID, the third value this repository has carried as an open item since
    # 2026-09-26 and used deliberately for one row on 2026-10-15.  A void row
    # fails the suite, because an unscoreable mutant is not a passing one.
    if [ "$GOT" = "$WANT" ]; then
        if [ "$WANT" = "FAIL" ] && [ "$MECH" = "crash or timeout (no RESULT line)" ]; then
            echo "  VERDICT: VOID -- the suite failed by CRASHING, which is not"
            echo "           detection.  No checker ran, so this mutant is"
            echo "           unscored rather than caught."
            return 1
        fi
        echo "  VERDICT: OK"
        return 0
    fi
    echo "  VERDICT: UNEXPECTED -- suite $GOT where $WANT was required"
    return 1
}

WHICH=${1:-all}
RC=0

# A BASELINE GATE, 2026-10-16, copied in substance from
# examples/phase4_ral/run_mutation_tests.sh, which already had one.
#
# Those two suites are siblings: both drive the DUT through the uvm-python /
# cocotb stack.  Run with cocotb absent, phase4_ral printed
#
#     BASELINE: *** NORESULT on unmodified RTL -- mutation results are
#               meaningless until this passes.
#
# and scored nothing, while this suite scored all four mutants OK.  Same
# missing toolchain, same class of suite, opposite behaviour -- and the
# difference was one gate that one of them happened to have.  If the control
# row does not pass, nothing downstream of it can be scored, so this suite no
# longer tries.
if [ "$WHICH" = "all" ]; then
    if ! run_one control 0 "" PASS "unmutated DUT -- the suite must PASS" ""; then
        echo "----------------------------------------------------------------"
        echo "BASELINE GATE: the control row did not pass, so the DUT or the"
        echo "    toolchain is not working here and NO mutant can be scored."
        echo "    M1-M4 are VOID by construction and are not run: scoring them"
        echo "    would report four detections from a suite that never"
        echo "    executed a check.  Fix the control first."
        echo "mutation run exit: 1  (baseline gate)"
        exit 1
    fi
    CONTROL_DONE=1
else
    CONTROL_DONE=0
fi

for M in control M1 M2 M3 M4; do
    [ "$WHICH" = "all" ] || [ "$WHICH" = "$M" ] || continue
    case $M in
    control)
        [ "$CONTROL_DONE" = "1" ] && continue
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
