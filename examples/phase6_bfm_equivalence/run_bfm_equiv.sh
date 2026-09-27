#!/usr/bin/env bash
# examples/phase6_bfm_equivalence/run_bfm_equiv.sh
#
# Proves bfm/uart_rx_pin_bfm.v is a pure refactor of the pin driver that
# was duplicated verbatim in the two phase6 benches, by comparing it
# against bfm/uart_rx_pin_legacy_ref.v at PICOSECOND resolution with zero
# tolerance.
#
# Usage:  bash examples/phase6_bfm_equivalence/run_bfm_equiv.sh
#
# NOTE on the two 2026-09-17 gotchas, both of which apply here:
#   * tools/setup_iverilog.sh is SOURCED WITHOUT A PIPE.  Piping it runs it
#     in a subshell and the iverilog/vvp shell functions it defines vanish.
#   * `timeout 170 vvp ...` fails with "No such file or directory" because
#     vvp is a shell function.  The real binary is wrapped instead.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${HERE}/../.." && pwd)"

# shellcheck disable=SC1091
source "${ROOT}/tools/setup_iverilog.sh" > /dev/null
IVL_DIR="${IVERILOG_INSTALL_DIR:-/tmp/iverilog_install}"

cd "${HERE}"
iverilog -g2012 -o equiv_sim \
    bfm_equiv_tb.v \
    "${ROOT}/bfm/uart_rx_pin_bfm.v" \
    "${ROOT}/bfm/uart_rx_pin_legacy_ref.v" || exit 1

timeout 170 "${IVL_DIR}/usr/bin/vvp" \
    -M "${IVL_DIR}/usr/lib/x86_64-linux-gnu/ivl" equiv_sim
rc=$?
rm -f equiv_sim
exit $rc
