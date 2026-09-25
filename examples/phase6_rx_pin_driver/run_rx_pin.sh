#!/usr/bin/env bash
# examples/phase6_rx_pin_driver/run_rx_pin.sh
#
# Compiles and runs the RX-pin driver bench over a seed sweep.
#
# Usage:  bash examples/phase6_rx_pin_driver/run_rx_pin.sh [n_seeds] [frames]
# Run from anywhere; the script locates the repo root itself.

set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
N="${1:-4}"
FRAMES="${2:-40}"

# shellcheck disable=SC1091
source tools/setup_iverilog.sh > /dev/null 2>&1
IVL_BIN="${IVERILOG_INSTALL_DIR:-/tmp/iverilog_install}/usr/bin"
IVL_LIB="${IVERILOG_INSTALL_DIR:-/tmp/iverilog_install}/usr/lib/x86_64-linux-gnu/ivl"

SIM="$(mktemp -u /tmp/rxpin_sim.XXXXXX)"
"$IVL_BIN/iverilog" -B "$IVL_LIB" -g2012 -o "$SIM" \
    rtl/uart_controller.v examples/phase6_rx_pin_driver/uart_rx_pin_tb.v || exit 1

FAILED=0
for s in $(seq 1 "$N"); do
    echo "################ seed $s ################"
    # NOTE: vvp is a shell FUNCTION here, not a binary, so `timeout vvp ...`
    # fails with "No such file or directory" -- call the real binary.
    # (Logged 2026-09-17; still true.)
    timeout 170 "$IVL_BIN/vvp" -M "$IVL_LIB" "$SIM" "+seed=$s" "+frames=$FRAMES" 2>&1 \
        | tee /tmp/rxpin_seed_$s.log
    grep -q "RESULT: PASS" /tmp/rxpin_seed_$s.log || FAILED=1
done

echo
if [ "$FAILED" -eq 0 ]; then echo "ALL $N SEEDS PASS"; else echo "AT LEAST ONE SEED FAILED"; fi
rm -f "$SIM"
exit $FAILED
