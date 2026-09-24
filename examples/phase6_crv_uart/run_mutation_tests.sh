#!/usr/bin/env bash
# examples/phase6_crv_uart/run_mutation_tests.sh
#
# Mutation-tests the constrained-random / coverage-driven UART suite.
#
# Every mutant is injected into a COPY of rtl/uart_controller.v under
# /tmp; the repo's RTL is never modified. A mutant is DETECTED when the
# suite prints "RESULT: FAIL" (or dies) and ESCAPED when it still prints
# "RESULT: PASS".
#
# This exists because on 2026-09-17 a testbench in this repo passed 55/55
# against deliberately broken RTL. A suite that has not been mutation-tested
# has an unmeasured verdict.
#
# Escapes are reported WITH THEIR REASON rather than treated as a score to
# be maximised: an escape whose cause is understood is a statement about the
# suite's reach, and two of the escapes below are the most useful output of
# this script.
#
# Usage:  bash examples/phase6_crv_uart/run_mutation_tests.sh
# Run from the repo root.

set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

# shellcheck disable=SC1091
source tools/setup_iverilog.sh > /dev/null 2>&1
IVL_BIN="${IVERILOG_INSTALL_DIR:-/tmp/iverilog_install}/usr/bin"
IVL_LIB="${IVERILOG_INSTALL_DIR:-/tmp/iverilog_install}/usr/lib/x86_64-linux-gnu/ivl"

WORK="$(mktemp -d /tmp/uart_mut.XXXXXX)"
TB="examples/phase6_crv_uart/uart_crv_cov_tb.v"
RTL="rtl/uart_controller.v"
SEEDS="1 3 5"

run_suite () {                      # $1 = rtl file
    local rtl="$1" out rc=0
    "$IVL_BIN/iverilog" -B "$IVL_LIB" -g2012 -o "$WORK/sim" "$rtl" "$TB" \
        > "$WORK/compile.log" 2>&1 || { echo "COMPILE_ERROR"; return; }
    for s in $SEEDS; do
        out="$(timeout 170 "$IVL_BIN/vvp" -M "$IVL_LIB" "$WORK/sim" \
               "+seed=$s" "+steer=1" 2>&1)" || rc=1
        if ! grep -q "RESULT: PASS" <<< "$out"; then echo "FAIL"; return; fi
    done
    echo "PASS"
}

echo "=============================================================="
echo "MUTATION TEST -- examples/phase6_crv_uart/uart_crv_cov_tb.v"
echo "date: $(date -u +%F)   seeds: $SEEDS   mode: steer=1"
echo "=============================================================="
echo

echo "G1  baseline: the suite must PASS on the unmodified RTL"
BASE="$(run_suite "$RTL")"
echo "    baseline verdict: $BASE"
if [ "$BASE" != "PASS" ]; then
    echo "    ABORT -- a baseline that does not pass makes every mutant row meaningless."
    exit 1
fi
echo

# name | sed expression | expectation | why
MUT_NAMES=(
  "M1 TX parity polarity swapped (even<->odd)"
  "M2 RX data bit inverted at the mid-bit sample"
  "M3 CTRL.stop_bits ignored by TX (always one stop bit)"
  "M4 TX FIFO count never increments on a lone push"
  "M5 BAUD_DIV ignored by the baud generator (always divide-by-1)"
  "M6 STATUS read no longer clears the sticky error bits"
)
MUT_SEDS=(
  's/tx_par_bit <= (cfg_parity == PARITY_EVEN) ?  ^tx_fifo\[tx_rptr\] :/tx_par_bit <= (cfg_parity == PARITY_EVEN) ?  ~^tx_fifo[tx_rptr] :/'
  's/if (rx_mid) rx_shift\[rx_bit\] <= rx_sync;/if (rx_mid) rx_shift[rx_bit] <= ~rx_sync;/'
  's/if (tx_bit_done) tx_state <= cfg_two_stop ? TX_STOP2 : TX_IDLE;/if (tx_bit_done) tx_state <= TX_IDLE;/'
  's/2.b10: tx_cnt <= tx_cnt + 4.d1;/2\x27b10: tx_cnt <= tx_cnt;/'
  's/else if (baud_cnt == 8.d0) baud_cnt <= baud_div;/else if (baud_cnt == 8\x27d0) baud_cnt <= 8\x27d0;/'
  's/frame_err <= 1.b0; parity_err <= 1.b0; overrun_err <= 1.b0;\n            end\n\n            if (!cfg_en)/XXX/'
)
MUT_EXPECT=(
  "DETECT"
  "DETECT"
  "DETECT"
  "DETECT"
  "ESCAPE"
  "ESCAPE"
)
MUT_WHY=(
  "the RX parity check must disagree and set STATUS.parity_err, which every status read asserts is clear"
  "every received byte must mismatch the reference model"
  "a two-stop-bit frame becomes one bit short, so the next frame's start bit lands inside the previous frame's stop window"
  "tx_full can then never assert, so coverage bin cp_txq.full is unreachable and CLOSURE fails -- this mutant is caught by the coverage criterion, not by any data check"
  "PREDICTED ESCAPE: in loopback the TX and RX engines share one baud generator, so a wrong divisor desynchronises nothing. A loopback bench is structurally blind to baud-rate errors"
  "PREDICTED ESCAPE: no error is ever injected in a clean loopback burst, so a bit that fails to CLEAR is never observed set in the first place"
)

DETECTED=0; ESCAPED=0; AS_PREDICTED=0; SURPRISES=0
for idx in "${!MUT_NAMES[@]}"; do
    cp "$RTL" "$WORK/mut.v"
    if [ "$idx" -eq 5 ]; then
        # M6 spans lines; do it with python rather than a fragile multiline sed
        python3 - "$WORK/mut.v" <<'PYEOF'
import sys
p = sys.argv[1]
s = open(p).read()
old = """            if (rd_en && (paddr == ADDR_STATUS)) begin
                frame_err <= 1'b0; parity_err <= 1'b0; overrun_err <= 1'b0;
            end"""
new = """            if (1'b0) begin
                frame_err <= 1'b0; parity_err <= 1'b0; overrun_err <= 1'b0;
            end"""
assert old in s, "M6 anchor not found"
open(p, "w").write(s.replace(old, new, 1))
PYEOF
        [ $? -ne 0 ] && { echo "  ${MUT_NAMES[$idx]}"; echo "    INJECTION FAILED"; continue; }
    else
        sed -i "${MUT_SEDS[$idx]}" "$WORK/mut.v"
        if cmp -s "$RTL" "$WORK/mut.v"; then
            echo "  ${MUT_NAMES[$idx]}"
            echo "    INJECTION FAILED -- the sed matched nothing, so this row would"
            echo "    otherwise have scored as an escape against UNMODIFIED RTL."
            SURPRISES=$((SURPRISES+1))
            continue
        fi
    fi

    V="$(run_suite "$WORK/mut.v")"
    if [ "$V" = "FAIL" ] || [ "$V" = "COMPILE_ERROR" ]; then
        GOT="DETECT"; DETECTED=$((DETECTED+1))
    else
        GOT="ESCAPE"; ESCAPED=$((ESCAPED+1))
    fi
    if [ "$GOT" = "${MUT_EXPECT[$idx]}" ]; then
        AS_PREDICTED=$((AS_PREDICTED+1)); MARK="as predicted"
    else
        SURPRISES=$((SURPRISES+1));       MARK="*** NOT AS PREDICTED ***"
    fi
    echo "  ${MUT_NAMES[$idx]}"
    echo "    predicted ${MUT_EXPECT[$idx]}, got $GOT   ($MARK)"
    echo "    why: ${MUT_WHY[$idx]}"
    echo
done

echo "=============================================================="
echo "  mutants injected      : ${#MUT_NAMES[@]}"
echo "  detected              : $DETECTED"
echo "  escaped               : $ESCAPED"
echo "  verdict as predicted  : $AS_PREDICTED / ${#MUT_NAMES[@]}"
echo "  surprises             : $SURPRISES"
echo
echo "  A predicted escape is a measured statement about the suite's reach."
echo "  M5 is the important one: loopback shares one baud generator between"
echo "  TX and RX, so no loopback bench of any sophistication can detect a"
echo "  baud-rate error. That is an argument for the standalone RX bit-driver"
echo "  the Phase 4 milestone still has open, not for more stimulus here."
echo "=============================================================="
rm -rf "$WORK"
[ "$SURPRISES" -eq 0 ] || exit 1
