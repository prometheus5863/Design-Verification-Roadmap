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
    rtl/uart_controller.v bfm/uart_rx_pin_bfm.v examples/phase6_baud_error_coverage/uart_baud_cov_tb.v || exit 1

FAILED=0
for s in $(seq 1 "$N"); do
    echo "################ seed $s ################"
    # The gate must read the log it JUST wrote, and must not be satisfiable by
    # a log it did not write.  Until 2026-09-27 this was a FIXED path under
    # /tmp, and the automation sandbox reuses /tmp across sessions with
    # different uid mappings: yesterday's file was owned by another uid, `tee`
    # failed to open it with "Permission denied", and `grep` then read
    # YESTERDAY'S log -- which said PASS.  Demonstrated on 2026-09-27: a bench
    # deliberately made to print "RESULT: FAIL" was reported by this script as
    # "ALL 1 SEEDS PASS", exit code 0.  Three defences, each counting as
    # FAILURE rather than as success:
    #   * a private mktemp log, so no stale file can be read at all;
    #   * an empty log means tee failed, which is a failure, not a pass;
    #   * exactly one RESULT line is required, so a concatenated, partial or
    #     doubled log cannot satisfy the gate either.
    # NOTE: vvp is a shell FUNCTION here, not a binary, so `timeout vvp ...`
    # fails with "No such file or directory" -- call the real binary.
    # (Logged 2026-09-17; still true.)
    LOG="$(mktemp)"
    timeout 170 "$IVL_BIN/vvp" -M "$IVL_LIB" "$SIM" "+seed=$s" "+budget=$BUDGET" 2>&1 | tee "$LOG"
    n_result="$(grep -c '^RESULT:' "$LOG")"
    if [ ! -s "$LOG" ]; then
        echo "** RUNNER ERROR: seed $s produced an empty log (tee failed?) -- counting as FAILURE"
        FAILED=1
    elif [ "$n_result" -ne 1 ]; then
        echo "** RUNNER ERROR: seed $s log has $n_result RESULT lines, expected exactly 1 -- counting as FAILURE"
        FAILED=1
    elif ! grep -q '^RESULT: PASS' "$LOG"; then
        FAILED=1
    fi
    rm -f "$LOG"
done

echo
if [ "$FAILED" -eq 0 ]; then echo "ALL $N SEEDS PASS"; else echo "AT LEAST ONE SEED FAILED"; fi
rm -f "$SIM"
exit $FAILED
