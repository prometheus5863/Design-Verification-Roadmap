#!/usr/bin/env bash
# examples/phase6_divisor_window/run_divisor_window.sh
#
# Builds and runs the divisor/edge-phase window measurement and gates on its
# own RESULT line.
#
# Gate discipline per 2026-09-27 item 1: this script greps ONLY a log it has
# just written itself, to its own private path; an empty or missing log is a
# FAILURE and not a pass; and exactly one RESULT line must be present.
#
# NOTE this suite is EXPECTED to report 3 failing checks.  A2a, P3 and P5 are
# pre-registered predictions that the first run refuted, kept in the suite as
# failing checks rather than deleted (see the file header).  So the gate here
# is on the exact expected tally, not on "zero failures" -- a suite whose
# failures are part of its result needs its result pinned, or the next change
# to it is invisible.
set -u -o pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${HERE}/../.." && pwd)"
LOG="${HERE}/.run_divisor_window.$$.log"
EXPECTED="RESULT 13/16 checks passed, 3 failed"

cleanup() { rm -f "${LOG}" "${HERE}/.sim_divwin.$$"; }
trap cleanup EXIT

# shellcheck disable=SC1091
source "${ROOT}/tools/setup_iverilog.sh" > /dev/null 2>&1 || {
    echo "FAIL: could not set up Icarus Verilog"; exit 1; }

iverilog -g2012 -o "${HERE}/.sim_divwin.$$" \
    "${HERE}/uart_divisor_window_tb.v" \
    "${ROOT}/rtl/uart_controller.v" \
    "${ROOT}/bfm/uart_rx_pin_bfm.v" || {
    echo "FAIL: compile error"; exit 1; }

"${IVERILOG_INSTALL_DIR:-/tmp/iverilog_install}/usr/bin/vvp" \
    -M "${IVERILOG_INSTALL_DIR:-/tmp/iverilog_install}/usr/lib/x86_64-linux-gnu/ivl" \
    "${HERE}/.sim_divwin.$$" > "${LOG}" 2>&1

if [ ! -s "${LOG}" ]; then
    echo "FAIL: simulation produced no output"; exit 1
fi
n_result=$(grep -c '^RESULT ' "${LOG}" || true)
if [ "${n_result}" != "1" ]; then
    echo "FAIL: expected exactly one RESULT line, found ${n_result}"; exit 1
fi
got=$(grep '^RESULT ' "${LOG}")
if [ "${got}" != "${EXPECTED}" ]; then
    echo "FAIL: ${got}"
    echo "      expected: ${EXPECTED}"
    exit 1
fi
echo "PASS: ${got}"
exit 0
