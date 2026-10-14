#!/usr/bin/env bash
# examples/phase6_baud_error_coverage/run_mutation_tests.sh
#
# Mutation-tests the baud-error coverage bench: inject a defect into a COPY of
# the RTL and require the bench to FAIL.  (2026-09-17: this repo once had a
# suite that scored 55/55 green against deliberately broken RTL.)
#
# THIS BENCH IS MOSTLY A MEASUREMENT, NOT A CHECKER, and the mutation test is
# where that distinction gets a number instead of a disclaimer.  Its 11 checks
# are: the four anchored cross-checks of the measured limits against 09-25's
# independently measured values, the pattern-set monotonicity check, the
# T4b frame-error check, the illegal-bin checks, and coverage closure.  So the
# prediction is that mutants which MOVE THE TOLERANCE are detected by the
# cross-check, and a mutant that only removes a behaviour this bench does not
# check is expected to ESCAPE -- which is reported as an expected escape with
# its reason rather than hidden.
#
# Harness guard (09-24): a sed that matches nothing leaves the RTL intact and
# the row scores as an escape against CORRECT RTL.  Every injection is
# verified to have changed the file.
#
# Usage:  bash examples/phase6_baud_error_coverage/run_mutation_tests.sh
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

# shellcheck disable=SC1091
source tools/setup_iverilog.sh > /dev/null 2>&1
# shellcheck disable=SC1091
source tools/mutation_controls.sh
IVL_BIN="${IVERILOG_INSTALL_DIR:-/tmp/iverilog_install}/usr/bin"
IVL_LIB="${IVERILOG_INSTALL_DIR:-/tmp/iverilog_install}/usr/lib/x86_64-linux-gnu/ivl"
TB=examples/phase6_baud_error_coverage/uart_baud_cov_tb.v
# ADDED 2026-10-14.  The SECOND instance of the same omission, found by
# tools/harness_file_closure_audit.py after the first was found by hand in
# examples/phase6_rx_pin_driver.  On 2026-09-27 the RX pin driver was
# extracted into bfm/uart_rx_pin_bfm.v and the commit message reads "BOTH
# benches now drive the pin through the shared BFM ... and BOTH committed
# outputs reproduce byte for byte".  Both BENCHES, both bench runners -- and
# neither of the two MUTATION runners, whose compile lines still named only
# the RTL and the bench.  So this script has also failed at elaboration since
# 2026-09-27 ("Unknown module type: uart_rx_pin_bfm"), aborted at its own
# baseline check, and left mutation_test_report_2026-09-26.txt standing for
# seventeen sessions.
#
# The sibling run_baud_cov.sh DOES name the BFM, which is what makes this a
# refactor that updated some callers and not all of them rather than a
# missing file.
BFM=bfm/uart_rx_pin_bfm.v
WORK="$(mktemp -d /tmp/baudmut.XXXXXX)"

names=(
  "M1 BAUD_DIV ignored by the baud generator (the 2026-09-24 loopback ESCAPE)"
  "M2 RX samples at oversample position 7 instead of 8"
  "M3 RX samples at oversample position 12 (far off mid-bit)"
  "M4 stop-bit check removed from RX_STOP1"
  "M5 RX parity polarity swapped"
  "M6 start-bit glitch filter removed (EXPECTED ESCAPE -- not checked here)"
)
seds=(
  "s|else if (baud_cnt == 8'd0) baud_cnt <= baud_div;|else if (baud_cnt == 8'd0) baud_cnt <= 8'd0;|"
  "s|wire rx_mid  = os_tick \& (rx_os == 4'd8);|wire rx_mid  = os_tick \& (rx_os == 4'd7);|"
  "s|wire rx_mid  = os_tick \& (rx_os == 4'd8);|wire rx_mid  = os_tick \& (rx_os == 4'd12);|"
  "s|if (rx_mid \&\& !rx_sync) frame_err <= 1'b1;  \/\/ stop bit must be 1|if (1'b0) frame_err <= 1'b1;|"
  "s|(cfg_parity == PARITY_EVEN) ? \^rx_shift : ~\^rx_shift|(cfg_parity == PARITY_EVEN) ? ~^rx_shift : ^rx_shift|g"
  "s|if (rx_mid \&\& rx_sync) rx_state <= RX_IDLE;|if (1'b0) rx_state <= RX_IDLE;|"
)
expected_escape=(0 0 0 0 0 1)
# Declared site count per mutant -- control C enforced (2026-10-14).  M5's 2
# is the parity anchor, which occurs on two lines of the RTL; the row is
# described as one defect and changes both, fully injected, so its kill names
# the suite's response to a compound change.  Declared, that is legal and
# stated.  M4's sed is also rewritten here from the address-scoped
# `0,/re/s||repl|` form, which no text-level control can parse, to an explicit
# pattern; the anchor occurs once so the scoping was inert, and the mutant is
# byte-identical.
sites=( 1 1 1 1 2 1 )

echo "=============================================================="
echo "BAUD-ERROR COVERAGE BENCH MUTATION TEST   date: $(date -u +%F)"
echo "  each mutant is injected into a COPY of rtl/uart_controller.v"
echo "  a mutant the bench does not fail on is an ESCAPE unless the"
echo "  row is marked EXPECTED ESCAPE with a stated reason"
echo "=============================================================="
echo

"$IVL_BIN/iverilog" -B "$IVL_LIB" -g2012 -o "$WORK/base" rtl/uart_controller.v "$BFM" "$TB" || exit 1
if timeout 170 "$IVL_BIN/vvp" -M "$IVL_LIB" "$WORK/base" +seed=1 +budget=250 2>&1 \
     | grep -q "RESULT: PASS"; then
    echo "  baseline (unmutated RTL): PASS"
else
    echo "  baseline (unmutated RTL): FAIL -- aborting, the rows below would be noise"
    exit 1
fi
echo

DETECTED=0; ESCAPED=0; BROKEN=0; UNEXPECTED=0
for i in "${!names[@]}"; do
    SRC="$WORK/mut_$i.v"
    # CONTROL C, ENFORCED, before the substitution: the question is about the
    # ORIGINAL -- how many sites does this anchor reach?  A row reaching a
    # number other than its declaration is voided rather than scored, which
    # also makes this a regression guard on the RTL, where the anchored lines
    # actually live.
    if ! SITEV="$(mc_require_sites rtl/uart_controller.v "${seds[$i]}" "${sites[$i]}" 2>/dev/null)"; then
        echo "  !! ${names[$i]}"
        echo "     INJECTION_FAILED -- declared sites ${sites[$i]}, measured $SITEV"
        BROKEN=$((BROKEN+1)); continue
    fi
    sed -e "${seds[$i]}" rtl/uart_controller.v > "$SRC"

    if cmp -s rtl/uart_controller.v "$SRC"; then
        echo "  !! ${names[$i]}"
        echo "     INJECTION MATCHED NOTHING -- row voided (this is the harness guard)"
        BROKEN=$((BROKEN+1)); continue
    fi
    if ! "$IVL_BIN/iverilog" -B "$IVL_LIB" -g2012 -o "$WORK/sim_$i" "$SRC" "$BFM" "$TB" 2> "$WORK/c_$i.log"; then
        echo "  !! ${names[$i]}"
        echo "     mutant does not compile -- row voided"
        BROKEN=$((BROKEN+1)); continue
    fi

    OUT="$(timeout 170 "$IVL_BIN/vvp" -M "$IVL_LIB" "$WORK/sim_$i" +seed=1 +budget=250 2>&1)"
    if grep -q "RESULT: PASS" <<< "$OUT"; then
        if [ "${expected_escape[$i]}" -eq 1 ]; then
            echo "  esc(exp)  ${names[$i]}"
            echo "            expected: no check in this bench observes a runt start pulse"
        else
            echo "  ESCAPED   ${names[$i]}"
            UNEXPECTED=$((UNEXPECTED+1))
        fi
        ESCAPED=$((ESCAPED+1))
    else
        NERR="$(grep -o "errors [0-9]*" <<< "$OUT" | grep -o "[0-9]*" | tail -1)"
        FIRST="$(grep -m1 'ERROR:' <<< "$OUT" | sed 's/^ *//' | cut -c1-88)"
        echo "  detected  ${names[$i]}"
        echo "            sites: declared ${sites[$i]}, $SITEV"
        echo "            ${NERR:-?} errors; first: ${FIRST:-<no ERROR line>}"
        DETECTED=$((DETECTED+1))
    fi
done

echo
echo "  detected $DETECTED   escaped $ESCAPED (unexpected: $UNEXPECTED)   voided $BROKEN"
echo
echo "  The detector in this bench is the ANCHORED CROSS-CHECK of the measured"
echo "  tolerance against 09-25's independently measured values.  A coverage"
echo "  model on its own detects nothing: every mutant below still fills the"
echo "  same bins.  That is the point worth keeping -- coverage records what"
echo "  the stimulus reached, and only a check can say the DUT was right."
rm -rf "$WORK"
[ "$UNEXPECTED" -eq 0 ] && [ "$BROKEN" -eq 0 ]
