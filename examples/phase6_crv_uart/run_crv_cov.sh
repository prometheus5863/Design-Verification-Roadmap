#!/usr/bin/env bash
# examples/phase6_crv_uart/run_crv_cov.sh
#
# Compiles and runs the constrained-random / coverage-driven UART suite and
# measures TRANSACTIONS TO CLOSURE in both modes over a seed sweep.
#
# The point of the sweep is that a single seed cannot separate "steering
# helps" from "that seed was lucky". Eight seeds can.
#
# Usage:  bash examples/phase6_crv_uart/run_crv_cov.sh [n_seeds]
# Run from the repo root.

set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
N="${1:-8}"

# shellcheck disable=SC1091
source tools/setup_iverilog.sh > /dev/null 2>&1
IVL_BIN="${IVERILOG_INSTALL_DIR:-/tmp/iverilog_install}/usr/bin"
IVL_LIB="${IVERILOG_INSTALL_DIR:-/tmp/iverilog_install}/usr/lib/x86_64-linux-gnu/ivl"

SIM="$(mktemp -u /tmp/crv_sim.XXXXXX)"
"$IVL_BIN/iverilog" -B "$IVL_LIB" -g2012 -o "$SIM" \
    rtl/uart_controller.v examples/phase6_crv_uart/uart_crv_cov_tb.v || exit 1

echo "=============================================================="
echo "CRV / COVERAGE-DRIVEN CLOSURE SWEEP   date: $(date -u +%F)"
echo "  $N seeds, both modes, identical constraints and identical seeds"
echo "=============================================================="
echo
printf "  %-6s %-14s %-14s %s\n" seed "random" "steered" "ratio"
FAILED=0
SUM_R=0; SUM_S=0; MAX_R=0; MAX_S=0; MIN_R=999999; MIN_S=999999
for s in $(seq 1 "$N"); do
    for m in 0 1; do
        OUT="$(timeout 170 "$IVL_BIN/vvp" -M "$IVL_LIB" "$SIM" "+seed=$s" "+steer=$m" 2>&1)"
        grep -q "RESULT: PASS" <<< "$OUT" || { echo "  seed=$s steer=$m DID NOT PASS"; FAILED=1; }
        V="$(grep "TRANSACTIONS TO CLOSURE" <<< "$OUT" | sed 's/[^0-9]*\([0-9]*\).*/\1/')"
        if [ "$m" -eq 0 ]; then R="$V"; else S="$V"; fi
    done
    printf "  %-6s %-14s %-14s %s\n" "$s" "$R" "$S" "$(awk "BEGIN{printf \"%.1fx\", $R/$S}")"
    SUM_R=$((SUM_R+R)); SUM_S=$((SUM_S+S))
    [ "$R" -gt "$MAX_R" ] && MAX_R=$R; [ "$S" -gt "$MAX_S" ] && MAX_S=$S
    [ "$R" -lt "$MIN_R" ] && MIN_R=$R; [ "$S" -lt "$MIN_S" ] && MIN_S=$S
done
echo
echo "  mean    random $(awk "BEGIN{printf \"%.1f\", $SUM_R/$N}")   steered $(awk "BEGIN{printf \"%.1f\", $SUM_S/$N}")   ratio $(awk "BEGIN{printf \"%.1fx\", ($SUM_R/$N)/($SUM_S/$N)}")"
echo "  worst   random $MAX_R   steered $MAX_S   ratio $(awk "BEGIN{printf \"%.1fx\", $MAX_R/$MAX_S}")"
echo "  best    random $MIN_R   steered $MIN_S   ratio $(awk "BEGIN{printf \"%.1fx\", $MIN_R/$MIN_S}")"
echo "  spread  random $(awk "BEGIN{printf \"%.1fx\", $MAX_R/$MIN_R}")   steered $(awk "BEGIN{printf \"%.1fx\", $MAX_S/$MIN_S}")"
echo
echo "  READ THE SPREAD, NOT ONLY THE MEAN. Steering improves the worst case"
echo "  far more than the best, which is the honest form of the claim: a"
echo "  coverage-driven flow buys PREDICTABILITY of closure more than speed."
echo "=============================================================="
rm -f "$SIM"
exit $FAILED
