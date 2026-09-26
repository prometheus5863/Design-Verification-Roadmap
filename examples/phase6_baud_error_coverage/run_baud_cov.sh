#!/usr/bin/env bash
# examples/phase6_baud_error_coverage/run_baud_cov.sh
#
# Compiles and runs the baud-error coverage-model bench over a seed sweep.
#
# Usage:  bash examples/phase6_baud_error_coverage/run_baud_cov.sh [n_seeds] [budget]

set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
N="${1:-2}"
BUDGET="${2:-400}"

# NOTE: source it WITHOUT a pipe -- piping runs it in a subshell and the
# iverilog/vvp shell functions it defines vanish.  (Logged 2026-09-17.)
# shellcheck disable=SC1091
source tools/setup_iverilog.sh > /dev/null 2>&1
IVL_BIN="${IVERILOG_INSTALL_DIR:-/tmp/iverilog_install}/usr/bin"
IVL_LIB="${IVERILOG_INSTALL_DIR:-/tmp/iverilog_install}/usr/lib/x86_64-linux-gnu/ivl"

SIM="$(mktemp -u /tmp/baudcov_sim.XXXXXX)"
"$IVL_BIN/iverilog" -B "$IVL_LIB" -g2012 -o "$SIM" \
    rtl/uart_controller.v examples/phase6_baud_error_coverage/uart_baud_cov_tb.v || exit 1

FAILED=0
for s in $(seq 1 "$N"); do
    echo "################ seed $s ################"
    # vvp is a shell FUNCTION, not a binary, so `timeout vvp ...` fails with
    # "No such file or directory" -- call the real binary.  (2026-09-17.)
    timeout 170 "$IVL_BIN/vvp" -M "$IVL_LIB" "$SIM" "+seed=$s" "+budget=$BUDGET" 2>&1 \
        | tee /tmp/baudcov_seed_$s.log
    grep -q "RESULT: PASS" /tmp/baudcov_seed_$s.log || FAILED=1
done

echo
if [ "$FAILED" -eq 0 ]; then echo "ALL $N SEEDS PASS"; else echo "AT LEAST ONE SEED FAILED"; fi
rm -f "$SIM"
exit $FAILED
