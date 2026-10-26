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
# shellcheck disable=SC1091
source "${ROOT}/tools/mutation_controls.sh"
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

# CONVERTED 2026-10-15 from the bare `cmp -s` guard to the declared-sites
# control -- the fourth of the six runners 2026-10-07 found guarding this way,
# and the second-ranked item since 2026-10-13.  Both guards are kept, because
# they ask different questions and the difference is the point:
#
#   mc_require_sites  asks of the ORIGINAL: how many lines does this anchor
#                     reach, and is that the number the row declares?  It
#                     fires when the file changed under the harness even if
#                     the sed still matches SOMETHING -- which `cmp -s` cannot
#                     see, because differing from the original is all `cmp`
#                     requires.
#   cmp -s            asks of the RESULT: did anything change at all?  The
#                     weaker question, retained as the backstop for the one
#                     row whose pattern spans two lines.
#
# AND THE DECLARATION CHANGES WHAT A VOID MEANS.  Row 7 declares sites=0: it
# is a line-oriented sed against a two-line pattern, and it is in the suite
# deliberately, to check that an unmatched pattern is reported void rather
# than scored as a pass.  Until today its VOID was indistinguishable from an
# accidental one.  Declaring 0 makes it an EXPECTED void -- the control passes
# BECAUSE the measurement is zero -- so the row tests the harness on purpose
# instead of by coincidence.
run_case() {
  local name="$1" prog="$2" sites="$3" why="$4"
  local sitev
  n=$((n+1))
  if ! sitev="$(mc_require_sites "${ROOT}/bfm/uart_rx_pin_bfm.v" "${prog}" "${sites}" 2>/dev/null)"; then
    echo "[$n] ${name}: VOID -- declared ${sites} site(s), control says ${sitev}" >> "${report}"
    echo "     The anchor does not reach the number of lines this row declares," >> "${report}"
    echo "     so either the BFM changed under the harness or the declaration is" >> "${report}"
    echo "     wrong.  Both void the row; neither is scored." >> "${report}"
    echo >> "${report}"
    void=$((void+1)); return
  fi
  cp "${WORK}/golden.v" "${WORK}/mut.v"
  if ! sed -i "${prog}" "${WORK}/mut.v" 2>/dev/null; then
    echo "[$n] ${name}: VOID -- sed program rejected" >> "${report}"
    void=$((void+1)); return
  fi
  if cmp -s "${WORK}/golden.v" "${WORK}/mut.v"; then
    echo "[$n] ${name}: VOID -- the sed program matched nothing, so NO defect was" >> "${report}"
    echo "     injected (declared sites ${sites}, control ${sitev}).  Reported as" >> "${report}"
    echo "     void rather than counted as a detection: a" >> "${report}"
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
  echo "     sites: declared ${sites}, control ${sitev}" >> "${report}"
  echo "     why it matters: ${why}" >> "${report}"
  [ -n "${first}" ] && echo "     first failure: ${first}" >> "${report}"
  echo >> "${report}"
  rm -f "${WORK}/mut_sim"
}

# G2b NEUTRALITY CONTROL, added 2026-10-26; this runner had none either.
# Its criterion is errors > 0 => DETECTED, so the neutral copy must come back
# with errors == 0, and the arm asserts that number rather than a verdict
# borrowed from another runner.  Note what is mutated here is the BFM, not the
# RTL -- this is the only one of the three ported today whose target is not
# rtl/uart_controller.v, which is exactly why the shared helper takes a path.
{
  echo "G2b NEUTRALITY CONTROL: a comment-only edit to the BFM must compile"
  echo "and come back with errors == 0.  Without it every DETECTED row below"
  echo "is unattributable: a zero-tolerance picosecond comparison that fires"
  echo "on a change which cannot alter behaviour is measuring itself."
} >> "${report}"
NEU_SRC="${WORK}/golden.v"
NEU_TAG=examples/phase6_bfm_equivalence/run_mutation_tests.sh
# G2b-INJECT -- tools/test_neutrality_controls.py replaces THIS LINE
# with an override of mc_neutral_copy, which is how the arm below is
# mutation-tested without editing the committed runner or the shared
# helper.  A single-line, single-purpose injection point: the 2026-10-25
# selftest could only reach runners whose arm inlined its own `cp`.
if ! mc_neutral_copy "$NEU_SRC" "${WORK}/neutral.v" "$NEU_TAG"; then
  echo "  ABORT -- the neutral copy is byte-identical; it controls nothing." \
      >> "${report}"
  cat "${report}"
  exit 1
fi
( cd "${WORK}" && "${IVERILOG}" -B "${IVL_LIB}" -g2012 -o neutral_sim \
      "${HERE}/bfm_equiv_tb.v" neutral.v \
      "${ROOT}/bfm/uart_rx_pin_legacy_ref.v" ) 2> "${WORK}/neutral_c.log"
if [ ! -f "${WORK}/neutral_sim" ]; then
  {
    echo "  ABORT -- the comment-only mutant DOES NOT COMPILE, so the control"
    echo "  measured nothing.  That is the void branch's failure mode inside"
    echo "  the control written to make the void branch attributable."
    sed 's/^/        /' "${WORK}/neutral_c.log" | head -3
  } >> "${report}"
  cat "${report}"
  exit 1
fi
timeout 170 "${VVP}" -M "${IVL_LIB}" "${WORK}/neutral_sim" \
    > "${WORK}/neutral_out.log" 2>&1
neu_errs="$(grep -oE '^ errors : [0-9]+' "${WORK}/neutral_out.log" \
    | grep -oE '[0-9]+' | tail -1)"
neu_errs="${neu_errs:-missing}"
if [ "${neu_errs}" != "0" ]; then
  {
    echo "  ABORT -- a comment-only edit reported errors = ${neu_errs}, not 0."
    echo "  The equivalence bench is sensitive to a change that cannot alter"
    echo "  behaviour, so no DETECTED row below is attributable to its mutant."
    grep -m1 'FAIL' "${WORK}/neutral_out.log" | sed 's/^/        /'
  } >> "${report}"
  cat "${report}"
  exit 1
fi
{
  echo "  OK -- errors = 0 on the comment-only edit, which is exactly the"
  echo "  number every ESCAPED row below is scored by."
  echo
} >> "${report}"
rm -f "${WORK}/neutral_sim"

run_case "bit_ps_off_by_one_ps" \
  's/#(bit_ps);/#(bit_ps + 1);/g' \
  6 \
  "one picosecond per bit -- 3e-6 of a bit period.  No DUT-level check can see this: it is four orders of magnitude below the 5 bp sweep grid and would never move a measured tolerance limit.  Only a timestamp comparison catches it."

run_case "phase_ignored" \
  's/if (phase_ps != 0) #(phase_ps);/;/g' \
  2 \
  "the initial edge phase silently dropped.  09-25 measured edge phase moving a tolerance limit by 0.69% of eps, so a driver that ignores it reports optimistically biased limits -- the dangerous direction."

run_case "data_msb_first" \
  's/rx = data\[i\];/rx = data[7-i];/g' \
  1 \
  "bit order reversed.  Palindromic bytes (0x00, 0xFF, 0x3C, 0x81) cannot see this at all, so detection depends on the data table containing 0x01, 0x80, 0xAA, 0x55 -- the mutant is a test of the trial set as much as of the checker."

run_case "parity_polarity_swapped" \
  's/p = (par == PAR_EVEN) ? \^data : ~(\^data);/p = (par == PAR_EVEN) ? ~(^data) : ^data;/g' \
  1 \
  "even and odd parity exchanged."

run_case "bad_stop_ignored" \
  's/rx = bad_stop ?/rx = 0 ?/g' \
  1 \
  "the deliberate frame-error injection stops working, so the stop bit is always driven high.  This is a defect that makes benches PASS more often, which is the direction that does not announce itself."

run_case "two_stop_ignored" \
  's/if (two_stop) begin/if (0) begin/g' \
  1 \
  "the second stop bit never driven -- 8x2 frames silently become 8x1."

run_case "stop_bit_delay_dropped" \
  's/rx = bad_stop ? 1.b0 : 1.b1;     \/\/ stop 1\n            #(bit_ps);/XX/g' \
  0 \
  "a structural mutant expected to VOID: sed is line-oriented and this pattern spans two lines, so it matches nothing.  Kept in the suite deliberately as a live check that the harness reports an unmatched pattern as void instead of as a pass."

run_case "idle_return_dropped" \
  's/rx = 1.b1;                       \/\/ return to idle//g' \
  1 \
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
