#!/usr/bin/env bash
# examples/phase6_rx_pin_driver/run_mutation_tests.sh
#
# Mutation-tests the RX-pin bench: inject a defect into a COPY of the RTL and
# require the bench to FAIL.  A self-checking suite that passes against broken
# RTL is not a suite, and on 2026-09-17 this repo had one (55/55 green against
# deliberately broken RTL).
#
# THE ROW THIS SCRIPT EXISTS FOR IS M1.  "BAUD_DIV ignored by the baud
# generator" ESCAPED the 2026-09-24 loopback bench, structurally: in loopback
# the TX and RX engines share one baud generator, so a wrong divisor
# desynchronises nothing.  If M1 escapes here too, the independent timebase
# is not actually independent and this whole directory is decorative.
#
# Guard against the harness itself: a sed that matches nothing leaves the RTL
# intact and the row scores as an escape against CORRECT RTL -- the same class
# of false verdict the mutation test exists to prevent, one level up.  Every
# injection is verified to have changed the file.
#
# STRENGTHENED 2026-10-14 to the DECLARED-SITES form.  "Did the file change at
# all" is the weak guard the 2026-10-07 audit named four runners for, and it
# passes a sed intended to hit one site that hits three.  Each mutant below now
# DECLARES its site count in `sites=()` and a mismatch voids the row as
# INJECTION_FAILED instead of scoring it (tools/mutation_controls.sh,
# mc_require_sites).  Two things change here as a result, both of them facts
# this directory's own committed report did not state:
#
#   * M4 declares 2.  The 2026-10-13 anchor audit reported it as
#     OK_MULTISITE:2 -- a mutant presented in mutation_test_report_2026-09-25
#     as one defect that changes two sites.  Fully injected, so its kill was
#     always real; the kill names the suite's response to a COMPOUND change
#     and the report said "RX parity polarity swapped" as though it were one.
#     Declared, it is legal and stated.
#   * M3's sed is REWRITTEN.  It was `0,/re/s||repl|` -- an address-scoped
#     substitution with an empty pattern reusing the address regex -- which
#     the audit could form no text-level control for at all (A_SKIPPED:
#     unparsable).  The anchor occurs exactly once in the RTL, so the address
#     scoping was never doing anything, and the explicit form produces a
#     BYTE-IDENTICAL mutant (checked).  It now passes the full control set
#     (OK) instead of being uncontrollable.
#
# The declaration also guards the RTL, which is the half that only bites
# later: the anchors live here and the lines live in rtl/uart_controller.v, so
# an RTL edit that duplicates or deletes an anchored line silently changes
# what every mutant built on it injects.  `cmp -s` passes that; a declared
# count stops it.
#
# Usage:  bash examples/phase6_rx_pin_driver/run_mutation_tests.sh
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

# shellcheck disable=SC1091
source tools/setup_iverilog.sh > /dev/null 2>&1
# shellcheck disable=SC1091
source tools/mutation_controls.sh
IVL_BIN="${IVERILOG_INSTALL_DIR:-/tmp/iverilog_install}/usr/bin"
IVL_LIB="${IVERILOG_INSTALL_DIR:-/tmp/iverilog_install}/usr/lib/x86_64-linux-gnu/ivl"
TB=examples/phase6_rx_pin_driver/uart_rx_pin_tb.v
# ADDED 2026-10-14, and the omission is the finding of the session.  On
# 2026-09-27 the RX pin driver was extracted out of this bench into
# bfm/uart_rx_pin_bfm.v and the bench was rewritten to instantiate it.  That
# commit checked both BENCH runners -- run_rx_pin.sh and run_bfm_equiv.sh --
# and reported their outputs reproducing byte for byte.  It did not touch this
# MUTATION runner's compile line, which still named only the RTL and the
# bench.  So since 2026-09-27 this script has failed at elaboration with
# "Unknown module type: uart_rx_pin_bfm", aborted at its own baseline check,
# and reported nothing -- for SEVENTEEN sessions, through every one of which
# mutation_test_report_2026-09-25.txt sat in this directory reading
# "detected 7 escaped 0 voided 0".
#
# The baseline guard worked exactly as designed: it refused to score rows it
# could not trust, and exited 1.  Nothing read the exit code, because nothing
# re-runs this script.  A suite that cannot run is indistinguishable from a
# suite nobody ran -- both produce no new output -- and this repository has
# spent six sessions on guards INSIDE harnesses while a harness sat broken.
BFM=bfm/uart_rx_pin_bfm.v
WORK="$(mktemp -d /tmp/rxmut.XXXXXX)"

names=(
  "M1 BAUD_DIV ignored by the baud generator (the 2026-09-24 loopback ESCAPE)"
  "M2 RX samples at oversample position 7 instead of 8"
  "M3 stop-bit check removed from RX_STOP1"
  "M4 RX parity polarity swapped"
  "M5 start-bit glitch filter removed"
  "M6 overrun OVERWRITES the oldest byte instead of dropping the new one"
  "M7 rx_sync bypassed (receiver samples the pin asynchronously)"
)
seds=(
  "s|else if (baud_cnt == 8'd0) baud_cnt <= baud_div;|else if (baud_cnt == 8'd0) baud_cnt <= 8'd0;|"
  "s|wire rx_mid  = os_tick \& (rx_os == 4'd8);|wire rx_mid  = os_tick \& (rx_os == 4'd7);|"
  "s|if (rx_mid \&\& !rx_sync) frame_err <= 1'b1;  \/\/ stop bit must be 1|if (1'b0) frame_err <= 1'b1;|"
  "s|(cfg_parity == PARITY_EVEN) ? \^rx_shift : ~\^rx_shift|(cfg_parity == PARITY_EVEN) ? ~^rx_shift : ^rx_shift|g"
  "s|if (rx_mid \&\& rx_sync) rx_state <= RX_IDLE;|if (1'b0) rx_state <= RX_IDLE;|"
  "s|if (rx_full) overrun_err <= 1'b1;   \/\/ drop, do not overwrite|if (rx_full) begin overrun_err <= 1'b1; rx_push <= 1'b1; rx_push_data <= rx_shift; end else if (1'b0) overrun_err <= 1'b1;|"
  "s|else        rx_sync <= rx_in;|else        rx_sync <= rx_in;\n    // MUTANT: bypass|"
)
# Declared site count per mutant: how many LINES of rtl/uart_controller.v the
# anchor matches, which is how many substitutions sed will make (no /g => the
# first match on each matching line).  "-" means the row is not a plain sed
# and carries its own structural guard instead; M7 is the only one, and its
# python edit asserts on the index of the block it rewrites.
sites=( 1 1 1 2 1 1 - )

echo "=============================================================="
echo "RX-PIN BENCH MUTATION TEST   date: $(date -u +%F)"
echo "  each mutant is injected into a COPY of rtl/uart_controller.v"
echo "  a mutant that the bench does not fail on is an ESCAPE"
echo "=============================================================="
echo

# Baseline: the bench must PASS against unmodified RTL, or every row below is
# meaningless.
"$IVL_BIN/iverilog" -B "$IVL_LIB" -g2012 -o "$WORK/base" rtl/uart_controller.v "$BFM" "$TB" || exit 1
if timeout 170 "$IVL_BIN/vvp" -M "$IVL_LIB" "$WORK/base" +seed=1 +frames=20 2>&1 \
     | grep -q "RESULT: PASS"; then
    echo "  baseline (unmutated RTL): PASS"
else
    echo "  baseline (unmutated RTL): FAIL -- aborting, the rows below would be noise"
    exit 1
fi
echo

DETECTED=0; ESCAPED=0; BROKEN=0
for i in "${!names[@]}"; do
    SRC="$WORK/mut_$i.v"
    # Cleared every row: otherwise the structural row (M7, which forms no sed)
    # would print the PREVIOUS row's site verdict as though it were its own --
    # a detail string about the wrong thing, which is the 2026-10-05 finding.
    SITEV=""
    if [ "$i" -eq 6 ]; then
        # M7 needs a structural edit rather than a one-liner: make the receiver
        # read the pin directly, removing the one-clk synchroniser delay.
        sed -e "s|wire rx_in = cfg_loopback ? tx_line : rx;|wire rx_in = cfg_loopback ? tx_line : rx;\n    wire rx_async = rx_in;|" \
            -e "s|wire rx_mid  = os_tick \& (rx_os == 4'd8);|wire rx_mid  = os_tick \& (rx_os == 4'd8);\n    // MUTANT M7|" \
            rtl/uart_controller.v > "$SRC"
        # replace every USE of rx_sync inside the RX state machine with rx_in
        python3 - "$SRC" <<'PY'
import sys, re
p = sys.argv[1]
s = open(p).read()
start = s.index("    always @(posedge clk) begin\n        if (!rst_n) begin\n            rx_state <= RX_IDLE;")
body = s[start:]
body_new = body.replace("rx_sync", "rx_in")
open(p, "w").write(s[:start] + body_new)
PY
    else
        # CONTROL C, ENFORCED.  Checked BEFORE the substitution, because the
        # question is about the ORIGINAL: how many sites does this anchor
        # reach?  A row that reaches a number other than its declaration is
        # voided rather than scored.
        if ! SITEV="$(mc_require_sites rtl/uart_controller.v "${seds[$i]}" "${sites[$i]}" 2>/dev/null)"; then
            echo "  !! ${names[$i]}"
            echo "     INJECTION_FAILED -- declared sites ${sites[$i]}, measured $SITEV"
            BROKEN=$((BROKEN+1)); continue
        fi
        sed -e "${seds[$i]}" rtl/uart_controller.v > "$SRC"
    fi

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

    OUT="$(timeout 170 "$IVL_BIN/vvp" -M "$IVL_LIB" "$WORK/sim_$i" +seed=1 +frames=20 2>&1)"
    if grep -q "RESULT: PASS" <<< "$OUT"; then
        echo "  ESCAPED   ${names[$i]}"
        echo "            sites: declared ${sites[$i]}, ${SITEV:-structural guard}"
        ESCAPED=$((ESCAPED+1))
    else
        NERR="$(grep -o "RESULT: FAIL ([0-9]* errors)" <<< "$OUT" | grep -o "[0-9]*" | head -1)"
        FIRST="$(grep -m1 '\*\* FAIL' <<< "$OUT" | sed 's/^ *//' | cut -c1-92)"
        echo "  detected  ${names[$i]}"
        echo "            sites: declared ${sites[$i]}, ${SITEV:-structural guard}"
        echo "            ${NERR:-?} errors; first: ${FIRST:-<no ** FAIL line>}"
        DETECTED=$((DETECTED+1))
    fi
done

echo
echo "  detected $DETECTED   escaped $ESCAPED   voided $BROKEN"
echo
echo "  P6 (pre-registered in the testbench): this bench DETECTS M1, the"
echo "  BAUD_DIV mutant that escaped the 2026-09-24 loopback bench."
rm -rf "$WORK"
[ "$ESCAPED" -eq 0 ] && [ "$BROKEN" -eq 0 ]
