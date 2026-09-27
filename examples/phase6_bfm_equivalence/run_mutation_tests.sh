#!/usr/bin/env bash
# examples/phase6_bfm_equivalence/run_mutation_tests.sh
#
# Mutation-tests the equivalence bench: inject a defect into a COPY of
# bfm/uart_rx_pin_bfm.v and require bfm_equiv_tb.v to FAIL.  The real BFM
# is never touched.
#
# WHY THIS RUN IS WORTH COMPARING AGAINST 2026-09-26's
# ----------------------------------------------------
# On 2026-09-26 a mutation test of examples/phase6_baud_error_coverage/
# found that the COVERAGE MODEL detected none of five mutants -- every
# mutant filled exactly the same bins -- and that all five detections came
# from an anchored cross-check against an independently measured value.
# This bench is the opposite extreme: its checker has ZERO tolerance and
# compares against an independent implementation.  If the 09-26 reading is
# right, this suite should detect everything, including a one-picosecond
# timebase error, which no DUT-level check could possibly see.
#
# A note on the mutants' shape: none of the sed programs below contains a
# Verilog sized literal such as 1'b0, because an apostrophe inside a
# double-quoted bash array element inside a heredoc is a quoting trap that
# cost this session one run.  `rx = bad_stop ?` -> `rx = 0 ?` injects
# exactly the intended defect without one.
#
# Usage:  bash examples/phase6_bfm_equivalence/run_mutation_tests.sh
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${HERE}/../.." && pwd)"
# shellcheck disable=SC1091
source "${ROOT}/tools/setup_iverilog.sh" > /dev/null 2>&1
IVL_DIR="${IVERILOG_INSTALL_DIR:-/tmp/iverilog_install}"
IVERILOG="${IVL_DIR}/usr/bin/iverilog"
VVP="${IVL_DIR}/usr/bin/vvp"
IVL_LIB="${IVL_DIR}/usr/lib/x86_64-linux-gnu/ivl"

WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT
cp "${ROOT}/bfm/uart_rx_pin_bfm.v" "${WORK}/golden.v"

report="${HERE}/mutation_test_report_$(date -u +%F).txt"
{
  echo "========================================================================"
  echo " Mutation test: examples/phase6_bfm_equivalence/bfm_equiv_tb.v"
  echo " Target: bfm/uart_rx_pin_bfm.v (a COPY is mutated; the real file is not)"
  echo " Date (UTC): $(date -u +%F)"
  echo "========================================================================"
  echo
  echo "A mutant is DETECTED when the equivalence bench reports errors > 0."
  echo "The checker compares transition timestamps against an independent"
  echo "implementation at picosecond resolution with ZERO tolerance, so there"
  echo "is no slack for a mutant to hide in.  Compare with the 2026-09-26 run"
  echo "in examples/phase6_baud_error_coverage/, where the coverage model"
  echo "detected 0 of 5 and every detection came from a check instead."
  echo
} > "${report}"

det=0; esc=0; void=0; n=0

run_case() {
  local name="$1" prog="$2" why="$3"
  n=$((n+1))
  cp "${WORK}/golden.v" "${WORK}/mut.v"
  if ! sed -i "${prog}" "${WORK}/mut.v" 2>/dev/null; then
    echo "[$n] ${name}: VOID -- sed program rejected" >> "${report}"
    void=$((void+1)); return
  fi
  if cmp -s "${WORK}/golden.v" "${WORK}/mut.v"; then
    echo "[$n] ${name}: VOID -- the sed program matched nothing, so NO defect was" >> "${report}"
    echo "     injected.  Reported as void rather than counted as a detection: a" >> "${report}"
    echo "     mutation harness whose unmatched patterns score as passes is the" >> "${report}"
    echo "     same failure mode as a testbench that passes against broken RTL." >> "${report}"
    echo >> "${report}"
    void=$((void+1)); return
  fi
  ( cd "${WORK}" && "${IVERILOG}" -B "${IVL_LIB}" -g2012 -o mut_sim \
        "${HERE}/bfm_equiv_tb.v" mut.v \
        "${ROOT}/bfm/uart_rx_pin_legacy_ref.v" ) 2> "${WORK}/compile.log"
  if [ ! -f "${WORK}/mut_sim" ]; then
    echo "[$n] ${name}: VOID -- the mutant does not compile" >> "${report}"
    sed 's/^/       /' "${WORK}/compile.log" | head -3 >> "${report}"
    echo >> "${report}"
    void=$((void+1)); return
  fi
  timeout 170 "${VVP}" -M "${IVL_LIB}" "${WORK}/mut_sim" > "${WORK}/out.log" 2>&1
  local errs first
  errs="$(grep -oE '^ errors : [0-9]+' "${WORK}/out.log" | grep -oE '[0-9]+' | tail -1)"
  errs="${errs:-0}"
  first="$(grep -m1 'FAIL' "${WORK}/out.log" | sed 's/^[[:space:]]*//' | cut -c1-140)"
  if [ "${errs}" -gt 0 ]; then
    echo "[$n] ${name}: DETECTED (${errs} errors)" >> "${report}"
    det=$((det+1))
  else
    echo "[$n] ${name}: ESCAPED" >> "${report}"
    esc=$((esc+1))
  fi
  echo "     why it matters: ${why}" >> "${report}"
  [ -n "${first}" ] && echo "     first failure: ${first}" >> "${report}"
  echo >> "${report}"
  rm -f "${WORK}/mut_sim"
}

run_case "bit_ps_off_by_one_ps" \
  's/#(bit_ps);/#(bit_ps + 1);/g' \
  "one picosecond per bit -- 3e-6 of a bit period.  No DUT-level check can see this: it is four orders of magnitude below the 5 bp sweep grid and would never move a measured tolerance limit.  Only a timestamp comparison catches it."

run_case "phase_ignored" \
  's/if (phase_ps != 0) #(phase_ps);/;/g' \
  "the initial edge phase silently dropped.  09-25 measured edge phase moving a tolerance limit by 0.69% of eps, so a driver that ignores it reports optimistically biased limits -- the dangerous direction."

run_case "data_msb_first" \
  's/rx = data\[i\];/rx = data[7-i];/g' \
  "bit order reversed.  Palindromic bytes (0x00, 0xFF, 0x3C, 0x81) cannot see this at all, so detection depends on the data table containing 0x01, 0x80, 0xAA, 0x55 -- the mutant is a test of the trial set as much as of the checker."

run_case "parity_polarity_swapped" \
  's/p = (par == PAR_EVEN) ? \^data : ~(\^data);/p = (par == PAR_EVEN) ? ~(^data) : ^data;/g' \
  "even and odd parity exchanged."

run_case "bad_stop_ignored" \
  's/rx = bad_stop ?/rx = 0 ?/g' \
  "the deliberate frame-error injection stops working, so the stop bit is always driven high.  This is a defect that makes benches PASS more often, which is the direction that does not announce itself."

run_case "two_stop_ignored" \
  's/if (two_stop) begin/if (0) begin/g' \
  "the second stop bit never driven -- 8x2 frames silently become 8x1."

run_case "stop_bit_delay_dropped" \
  's/rx = bad_stop ? 1.b0 : 1.b1;     \/\/ stop 1\n            #(bit_ps);/XX/g' \
  "a structural mutant expected to VOID: sed is line-oriented and this pattern spans two lines, so it matches nothing.  Kept in the suite deliberately as a live check that the harness reports an unmatched pattern as void instead of as a pass."

run_case "idle_return_dropped" \
  's/rx = 1.b1;                       \/\/ return to idle//g' \
  "the pin left at the stop-bit value instead of being returned to idle.  Harmless when the stop bit was high, a stuck-low line when bad_stop was set -- so detection depends on the trial set exercising bad_stop, which T1 does across 12 of its 24 configs."

{
  echo "------------------------------------------------------------------------"
  echo " mutants attempted : ${n}"
  echo " detected          : ${det}"
  echo " escaped           : ${esc}"
  echo " void              : ${void}"
  echo "------------------------------------------------------------------------"
} >> "${report}"

cat "${report}"
