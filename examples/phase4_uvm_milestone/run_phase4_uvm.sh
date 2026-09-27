#!/usr/bin/env bash
# examples/phase4_uvm_milestone/run_phase4_uvm.sh
#
# Runs the Phase 4 UVM environment's three tests, EACH IN ITS OWN SIMULATOR
# INVOCATION.
#
# WHY THREE INVOCATIONS AND NOT ONE
# ---------------------------------
# uvm-python's `run_test()` can be called at most ONCE per simulator process:
# the second call reports
#
#   UVM_FATAL [TTINST] An uvm_test_top already exists via a previous call to
#   run_test
#
# and the test fails with a UVMFinishError. Three `@cocotb.test()` coroutines
# in one file therefore cannot each call run_test() in a single run -- which is
# how this was found on 2026-09-27, with TESTS=3 PASS=1 FAIL=2 where the two
# failures were both this fatal and neither was about the DUT. cocotb's
# TESTCASE variable selects one test per invocation, so the split is a runner
# concern rather than a testbench one.
#
# This joins the other two uvm-python constraints already recorded in
# notes/2026-09-06-uvm-python-toolchain-resolution.md; it is a property of the
# library, not of this environment.
#
# Usage:  bash examples/phase4_uvm_milestone/run_phase4_uvm.sh
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${HERE}/../.." && pwd)"

# shellcheck disable=SC1091
source "${ROOT}/tools/setup_iverilog.sh" > /dev/null 2>&1
export PATH="${HOME}/.local/bin:${PATH}"

TESTS=(
  test_uart_uvm_milestone
  test_uart_baud_tolerance
  test_uart_scoreboard_timebase_assumption
)

cd "${HERE}"
FAILED=0
for t in "${TESTS[@]}"; do
  echo "################ ${t} ################"
  # Each invocation is a fresh process, so a fresh uvm_test_top.
  LOG="$(mktemp)"
  timeout 170 make -s TESTCASE="${t}" 2>&1 | tee "${LOG}"
  # Same gate discipline as the phase6 runners after the 2026-09-27 fix: a
  # private log, an empty log counts as failure, and exactly one verdict line
  # is required so a partial log cannot satisfy the gate.
  # NOT anchored at ^: cocotb pads its summary line with leading spaces.
  # The first version of this gate anchored it and reported FAILURE for three
  # tests that had all passed -- which is the correct direction for a gate to
  # fail in, and is the 2026-09-27 phase6 runner fix proving itself on the
  # same day it was written.
  n="$(grep -cE '\*\* TESTS=' "${LOG}")"
  if [ ! -s "${LOG}" ]; then
    echo "** RUNNER ERROR: ${t} produced an empty log -- counting as FAILURE"
    FAILED=1
  elif [ "${n}" -ne 1 ]; then
    echo "** RUNNER ERROR: ${t} log has ${n} cocotb summary lines, expected 1 -- counting as FAILURE"
    FAILED=1
  elif ! grep -qE '\*\* TESTS=1 PASS=1 FAIL=0' "${LOG}"; then
    FAILED=1
  fi
  rm -f "${LOG}"
  echo
done

if [ "${FAILED}" -eq 0 ]; then
  echo "ALL ${#TESTS[@]} PHASE 4 UVM TESTS PASS"
else
  echo "AT LEAST ONE PHASE 4 UVM TEST FAILED"
fi
exit "${FAILED}"
