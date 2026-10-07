#!/usr/bin/env bash
# Mutation test for the Phase 4 RAL bench.
#
# WHY THIS EXISTS. A passing testbench proves nothing about the testbench.
# 2026-09-17 found a suite that passed 55/55 against deliberately broken
# RTL; 2026-09-18 found a regression that printed PASS while the log held
# UVM_ERRORs. Both were caught by mutation testing and by nothing else.
# So: inject a defect into a COPY of the RTL (rtl/uart_controller.v is
# never touched) and REQUIRE the bench to fail. A surviving mutant is a
# hole in the bench, not a success.
#
# Each mutant here targets a DIFFERENT check, so a survivor names the
# check that is missing rather than just saying "something is weak".
#
# GOTCHA, FOUND BY THIS SCRIPT'S OWN FIRST RUN (2026-09-19). With
# cocotb 1.9.2 + Icarus 10.3, `make` EXITS 0 EVEN WHEN THE TEST FAILS:
#
#     $ make RTL_SRC=.../uart_controller_M3.v ; echo $?
#     ** TESTS=1 PASS=0 FAIL=1 SKIP=0 **
#     0
#
# So a mutation harness that trusts `make`'s exit status reports every
# mutant as SURVIVED -- which is what the first run of this script did,
# 0 killed out of 5, while every one of the five logs contained the
# correct FAIL. That is the THIRD appearance in this repo of one defect
# class: the subsystem reporting the verdict was not the subsystem doing
# the checking (2026-09-17: checks never ran; 2026-09-18: UVM_ERRORs
# ignored by cocotb's PASS line; today: cocotb's FAIL ignored by make's
# exit code). The harness whose job is to catch that bug had the bug.
#
# The verdict therefore comes from parsing cocotb's own results line, and
# `assert_verdict` refuses to guess when it cannot find one.
#
# INJECTION CONTROLS, ADDED 2026-10-07.  This script's only injection guard
# was `cmp -s mutant RTL`, which catches a sed that matched NOTHING and
# nothing else.  It cannot see a sed that matched SOMETHING AND NOT
# EVERYTHING: `sed 's|A|B|'` replaces the first match on each line, so an
# anchor occurring twice on one line leaves HALF the defect in place while
# cmp reports a difference and the row below gets scored anyway.  The three
# controls now come from tools/mutation_controls.sh, which has its own
# self-test (tools/test_mutation_controls.sh, 12 cases).  A row whose
# controls do not hold is VOIDED and counted separately -- never as a kill
# and never as a survivor, because it is a verdict about a partial mutant.
#
# The audit that preceded this change (tools/audit_mutation_anchors.sh) found
# that none of this script's five mutants is half-injected, so no committed
# number here changes.  The controls are here for the mutants nobody has
# written yet, and for one property this script could not previously state:
# that each of its rows is about a WHOLE mutant.
#
# Usage:  source ../../tools/setup_iverilog.sh   # SOURCE it, do not pipe
#         ./run_mutation_tests.sh
set -u

# Echoes PASS / FAIL / NORESULT for a cocotb run log. NORESULT means the
# run did not get far enough to print a verdict (compile error, crash) --
# reported separately, never silently counted as a kill.
verdict_of() {
    local log="$1" line
    line="$(grep -oE 'TESTS=[0-9]+ PASS=[0-9]+ FAIL=[0-9]+ SKIP=[0-9]+' "$log" | tail -1)"
    if [ -z "$line" ]; then echo "NORESULT"; return; fi
    case "$line" in
        *"FAIL=0"*) echo "PASS" ;;
        *)          echo "FAIL" ;;
    esac
}

HERE="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
. "$HERE/../../tools/mutation_controls.sh"
RTL="$HERE/../../rtl/uart_controller.v"
WORK="${TMPDIR:-/tmp}/ral_mutants"
mkdir -p "$WORK"

declare -a NAMES DESCS TARGETS SEDS
add() { NAMES+=("$1"); DESCS+=("$2"); TARGETS+=("$3"); SEDS+=("$4"); }

add "M1" \
    "CTRL reserved bit 5 reads back as 1 instead of 0" \
    "UVMRegBitBashSeq / UVMRegHWResetSeq (RO field must not read 1)" \
    "s|ADDR_CTRL:     prdata = {3'b000, ctrl};|ADDR_CTRL:     prdata = {3'b001, ctrl};|"

add "M2" \
    "BAUD_DIV comes out of reset as 0x01 instead of 0x00" \
    "UVMRegHWResetSeq (reset value of a non-volatile RW register)" \
    "s|ctrl <= 5'd0; baud_div <= 8'd0;|ctrl <= 5'd0; baud_div <= 8'd1;|"

add "M3" \
    "STATUS read-to-clear removed: the sticky error bits never clear" \
    "CHECK 6, the RC access policy (second STATUS read)" \
    "s|if (rd_en \&\& (paddr == ADDR_STATUS)) begin|if (1'b0 \&\& (paddr == ADDR_STATUS)) begin|"

add "M4" \
    "STATUS tx_full and tx_empty swapped" \
    "CHECK 4, the explicit STATUS-at-reset value the hw_reset seq skips" \
    "s|rx_avail, rx_full, tx_empty, tx_full};|rx_avail, rx_full, tx_full, tx_empty};|"

add "M5" \
    "BAUD_DIV writes are dropped" \
    "CHECK 3 (RAL write reaches the DUT) and UVMRegBitBashSeq" \
    "s|ADDR_BAUD_DIV: baud_div <= pwdata;|ADDR_BAUD_DIV: baud_div <= baud_div;|"

# POSITIVE CONTROL FOR THE CONTROLS THEMSELVES, run with MC_SELFTEST=1.
# A guard that has never been seen to fire is not a guard -- this repository
# has found that three times (09-17, 09-18, 10-06).  MX's anchor
# `err <= 1'b0;` occurs THREE times on each of two lines of the DUT, so sed
# without /g replaces one per line and leaves four behind: the mutant carries
# part of the defect, and `cmp -s` -- the guard this script used until today
# -- passes it.  Control B must VOID it.  With MC_SELFTEST=1 the run requires
# exactly one voided row; without it, zero.
if [ "${MC_SELFTEST:-0}" = "1" ]; then
    add "MX" \
        "SELFTEST: a deliberately HALF-INJECTED mutant (anchor occurs 3x on each of 2 lines)" \
        "the injection controls themselves -- must be VOIDED, never scored" \
        "s|err <= 1'b0;|err <= 1'b1;|"
fi

echo "================================================================"
echo "Phase 4 RAL mutation test -- $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "DUT: $RTL (never modified; every mutant is a copy)"
echo "================================================================"

# Baseline: the bench must PASS on the unmodified RTL, or nothing below
# means anything.
rm -rf "$HERE/sim_build"
(cd "$HERE" && make RTL_SRC="$RTL" > "$WORK/baseline.log" 2>&1)
base_v="$(verdict_of "$WORK/baseline.log")"
if [ "$base_v" = "PASS" ]; then
    echo "BASELINE: PASS on unmodified RTL  (required)"
else
    echo "BASELINE: *** $base_v on unmodified RTL -- mutation results are"
    echo "          meaningless until this passes. See $WORK/baseline.log"
    exit 1
fi

killed=0; survived=0; noresult=0; voided=0
for i in "${!NAMES[@]}"; do
    n="${NAMES[$i]}"
    mut="$WORK/uart_controller_$n.v"
    sed "${SEDS[$i]}" "$RTL" > "$mut"
    # Controls A, B and C.  Replaces the old `cmp -s` guard, which was
    # control A in its weakest form; the detail line is kept whatever the
    # verdict, so a clean row still says WHY it is clean.
    mc_detail="$(mc_controls_sed "$RTL" "$mut" "${SEDS[$i]}" 2>&1 >/dev/null)"
    mc_verdict="$(mc_controls_sed "$RTL" "$mut" "${SEDS[$i]}" 2>/dev/null)"
    if ! mc_verdict_usable "$mc_verdict"; then
        echo ""
        echo "$n  VOIDED  ($mc_verdict)"
        echo "    defect : ${DESCS[$i]}"
        echo "    $mc_detail"
        echo "    *** NOT a surviving mutant and NOT a kill: any verdict from"
        echo "    *** this row would be a verdict about a partial mutant."
        voided=$((voided+1))
        continue
    fi
    rm -rf "$HERE/sim_build"
    (cd "$HERE" && make RTL_SRC="$mut" > "$WORK/$n.log" 2>&1)
    # NOT $? -- see the GOTCHA at the top of this file.
    case "$(verdict_of "$WORK/$n.log")" in
        FAIL)     res="KILLED";   killed=$((killed+1)) ;;
        PASS)     res="SURVIVED"; survived=$((survived+1)) ;;
        *)        res="NORESULT"; noresult=$((noresult+1)) ;;
    esac
    echo ""
    echo "$n  $res"
    echo "    defect : ${DESCS[$i]}"
    echo "    target : ${TARGETS[$i]}"
    echo "    inject : $mc_verdict -- $mc_detail"
    case "$res" in
        KILLED)
            grep -E "^  FAIL:|AssertionError: " "$WORK/$n.log" \
                | head -3 | sed 's/^/    killed by: /' ;;
        SURVIVED)
            echo "    *** NO CHECK DETECTED THIS. The bench has a hole here." ;;
        NORESULT)
            echo "    *** THE RUN PRODUCED NO VERDICT (compile error or crash)."
            echo "    *** This is NOT a kill. See $WORK/$n.log"
            tail -3 "$WORK/$n.log" | sed 's/^/    /' ;;
    esac
done

rm -rf "$HERE/sim_build"
echo ""
echo "================================================================"
echo "RESULT: $killed killed, $survived survived, $noresult no-verdict,"
echo "        $voided voided by the injection controls, out of ${#NAMES[@]}"
echo "================================================================"
if [ "${MC_SELFTEST:-0}" = "1" ]; then
    echo "  SELFTEST MODE: requiring exactly 1 voided row (MX)."
    [ "$survived" -eq 0 ] && [ "$noresult" -eq 0 ] && [ "$voided" -eq 1 ]
else
    [ "$survived" -eq 0 ] && [ "$noresult" -eq 0 ] && [ "$voided" -eq 0 ]
fi
