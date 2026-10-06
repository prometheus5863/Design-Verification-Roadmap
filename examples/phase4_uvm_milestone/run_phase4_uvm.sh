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
  test_uart_independent_observer
  test_uart_adaptive_observer
)

cd "${HERE}"
FAILED=0

# ---------------------------------------------------------------------------
# A MODEL CHECK FIRST, because it needs neither Icarus nor uvm-python.
#
# budget_law_exhaustive.py lifts the adaptive observer's decode out of
# uart_uvm_tb.py by source extraction and measures its baud budget for all 256
# bytes.  It is in this runner and not in a notes file because the 2026-09-29
# sign-off criterion (vplan v7) names exactly two bytes out of 256, and a
# criterion that rests on a 5-byte extrapolation is the kind of thing that
# should break a regression when the extrapolation stops holding.
#
# Gated the same way as the simulator tests: a private log, an empty log counts
# as failure, and exactly one RESULT line is required.
echo "################ budget_law_exhaustive (model, no simulator) ################"
MLOG="$(mktemp)"
timeout 170 python3 budget_law_exhaustive.py > "${MLOG}" 2>&1
mrc=$?
tail -32 "${MLOG}"
n="$(grep -cE '^RESULT: ' "${MLOG}")"
if [ ! -s "${MLOG}" ]; then
  echo "** RUNNER ERROR: budget_law_exhaustive produced an empty log -- counting as FAILURE"
  FAILED=1
elif [ "${n}" -ne 1 ]; then
  echo "** RUNNER ERROR: budget_law_exhaustive log has ${n} RESULT lines, expected 1 -- counting as FAILURE"
  FAILED=1
elif [ "${mrc}" -ne 0 ] || ! grep -qE '^RESULT: ALL CHECKS PASS' "${MLOG}"; then
  FAILED=1
fi
rm -f "${MLOG}"
echo

# ---------------------------------------------------------------------------
# A SECOND MODEL CHECK, also simulator-free.
#
# payload_coverage_model.py is the ctz(data) coverpoint vplan v7 made a sign-off
# dependency on 2026-09-29, with the two bytes it must treat as ILLEGAL rather
# than merely count.  It is in the runner and not in a notes file for the same
# reason budget_law_exhaustive.py is: it derives the {0x00, 0x80} and
# {0x40, 0xC0} sign-off sets from the COMMITTED measured CSV, so if that
# measurement is ever re-run and moves, the regression breaks instead of the
# criterion quietly going stale.
#
# Gated identically: private log, empty log counts as failure, exactly one
# RESULT line (the 2026-09-27 item-1 pattern -- never grep a file you did not
# just write).
echo "################ payload_coverage_model (model, no simulator) ################"
CLOG="$(mktemp)"
timeout 170 python3 payload_coverage_model.py > "${CLOG}" 2>&1
crc=$?
tail -34 "${CLOG}"
cn="$(grep -cE '^RESULT: ' "${CLOG}")"
if [ ! -s "${CLOG}" ]; then
  echo "** RUNNER ERROR: payload_coverage_model produced an empty log -- counting as FAILURE"
  FAILED=1
elif [ "${cn}" -ne 1 ]; then
  echo "** RUNNER ERROR: payload_coverage_model log has ${cn} RESULT lines, expected 1 -- counting as FAILURE"
  FAILED=1
elif [ "${crc}" -ne 0 ] || ! grep -qE '^RESULT: ALL CHECKS PASS' "${CLOG}"; then
  FAILED=1
fi
rm -f "${CLOG}"
echo

# ---------------------------------------------------------------------------
# A THIRD MODEL CHECK, also simulator-free, added 2026-10-06.
#
# run_axis_audit.py reads the COMMITTED simulator transcript
# uart_uvm_sim_output_2026-10-06.txt and measures the RUN axis of the live
# UartCoverage collector: which samples closed each cell, and how much
# stimulus diversity is behind each one.  2026-10-05 reported that axis as
# UNMEASURABLE from the committed artefacts; the per-sample witnesses added
# today make it measurable and this is the measurement.
#
# It is in the runner for the same reason the other two model checks are: it
# derives its finding from a committed artefact, so if that artefact is ever
# regenerated and the witness format or the stimulus diversity moves, the
# regression breaks instead of the finding quietly going stale.  In
# particular it re-asserts (R2) that every test's own W-a..W-e audit passed
# in the committed transcript, which is the thing that makes the witness data
# worth reading at all.
#
# Gated identically: private log, empty log counts as failure, exactly one
# RESULT line.
echo "################ run_axis_audit (model, no simulator) ################"
RLOG="$(mktemp)"
timeout 170 python3 run_axis_audit.py > "${RLOG}" 2>&1
rrc=$?
tail -22 "${RLOG}"
rn="$(grep -cE '^RESULT: ' "${RLOG}")"
if [ ! -s "${RLOG}" ]; then
  echo "** RUNNER ERROR: run_axis_audit produced an empty log -- counting as FAILURE"
  FAILED=1
elif [ "${rn}" -ne 1 ]; then
  echo "** RUNNER ERROR: run_axis_audit log has ${rn} RESULT lines, expected 1 -- counting as FAILURE"
  FAILED=1
elif [ "${rrc}" -ne 0 ] || ! grep -qE '^RESULT: ALL CHECKS PASS' "${RLOG}"; then
  FAILED=1
fi
rm -f "${RLOG}"
echo

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
  echo "ALL ${#TESTS[@]} PHASE 4 UVM TESTS PASS, PLUS THE THREE MODEL CHECKS"
else
  echo "AT LEAST ONE PHASE 4 CHECK FAILED (model check or UVM test)"
fi
exit "${FAILED}"
