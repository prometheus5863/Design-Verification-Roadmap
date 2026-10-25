#!/usr/bin/env bash
# examples/phase6_crv_uart/run_mutation_tests_bimodal.sh
#
# Re-runs every mutant of run_mutation_tests.sh in BOTH stimulus modes, per
# seed, and adds the control that the mode comparison needs.
#
# WHY THIS EXISTS
#
# 2026-10-21 mutation-tested the `tx_empty` prediction and found one mutant
# detected 4/4 under `steer=0` and only 2/4 under `steer=1`, concluding that
# the coverage-driven mode "detects less than pure random".  The 2026-10-21
# entry then ranked first the question of whether the other mutants move too,
# because all twelve committed reports in this repository were produced in ONE
# mode and have been read as statements about the suite.
#
# Running that question turned up a confound in the 2026-10-21 result itself.
# The bench's run loop is
#
#     while (total_tx < max_tx && bins_hit() < N_BINS && errors == 0)
#
# so it stops AT CLOSURE.  The two modes therefore do not drive the same
# amount of stimulus -- that is the point of the TRANSACTIONS TO CLOSURE
# figure the bench exists to report -- and measured over five seeds `steer=0`
# drives 2.1x to 12.0x more transactions than `steer=1` before it stops:
#
#     seed  steer=0   steer=1   ratio
#        1      648        54    12.0x
#        3      258        49     5.3x
#        5      110        53     2.1x
#        7      360        52     6.9x
#        9      457        40    11.4x
#
# A mutant that needs a rare event is then more likely to be caught under
# `steer=0` FOR VOLUME ALONE, with no statement about the coverage model
# implied.  2026-10-21 gave a specific mechanism for its escape -- the
# `burst_len = 1` branch is guarded by a bin the fill phase hits first -- and
# that mechanism is still in the code; but the EXPERIMENT as run cannot
# separate it from "steer=1 simply stopped eleven times earlier".
#
# THE THREE ARMS
#
#   A  steer=0, each mutant, 5 seeds, per-seed verdict.
#   B  steer=1, likewise.
#   E  steer=0 TRUNCATED to arm B's transaction count for the same seed
#      (+maxtx), which is the equal-budget control.  If a mutant that arm B
#      misses is still caught by arm E, volume does not explain the miss and
#      the coverage model does.  If arm E misses it too, volume is sufficient
#      and the 2026-10-21 reading is not supported by its own experiment.
#
# ADJUDICATION, AND WHY IT CANNOT BE PASS/FAIL
#
# Arm E cannot reach closure by construction, so it ALWAYS fails the bench's
# closure pass-criterion.  Scoring it by RESULT:FAIL would mark every mutant
# detected, including against unmodified RTL.  So every run is classified by
# WHICH check failed:
#
#   PASS          RESULT: PASS
#   CLOSURE_ONLY  the only failures are the closure criterion and the
#                 closure-counter consistency check -- not a detection
#   DATA          at least one other failing check -- a detection
#   DIED          no RESULT line at all (timeout or $fatal before the report)
#
# G2 below is the positive control on that adjudication: unmodified RTL under
# arm E must come out CLOSURE_ONLY on every seed.  If it ever comes out DATA,
# the classifier is broken and no arm-E row means anything.
#
# M4 WAS EXPECTED TO BE UNREADABLE IN ARM E, AND IS NOT.  run_mutation_tests.sh
# records that M4 is caught BY THE COVERAGE CRITERION -- "tx_full can then never
# assert, so cp_txq.full is unreachable and CLOSURE fails -- this mutant is
# caught by the coverage criterion, not by any data check" -- and arm E forces a
# closure failure for every row, so arm E should not have been able to tell M4's
# detection from its own truncation.  Classifying by WHICH check failed shows the
# committed claim is FALSE: three data checks fail before closure is even
# evaluated (post-push tx_empty, the burst watchdog, and the reference-queue
# drain).  M4 is scored in arm E like any other row, and the CATCHING CHECK
# column below is what settles it.  Consequence worth stating: no mutant in this
# suite is detected by the coverage criterion ALONE, so the bench's decision to
# make closure a pass criterion rather than a report line currently has no
# mutation evidence behind it.
#
# Usage:  bash examples/phase6_crv_uart/run_mutation_tests_bimodal.sh
# Run from the repo root.

set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

# NOT piped: sourcing this through a pipe runs it in a subshell and the
# iverilog/vvp shell functions it defines vanish (logged 2026-09-17).
source tools/setup_iverilog.sh > /dev/null 2>&1
IVL_BIN="${IVERILOG_INSTALL_DIR:-/tmp/iverilog_install}/usr/bin"
IVL_LIB="${IVERILOG_INSTALL_DIR:-/tmp/iverilog_install}/usr/lib/x86_64-linux-gnu/ivl"

WORK="$(mktemp -d /tmp/uart_bimut.XXXXXX)"
TB="examples/phase6_crv_uart/uart_crv_cov_tb.v"
RTL="rtl/uart_controller.v"
SEEDS="1 3 5 7 9"

compile () {                        # $1 = rtl file, $2 = out
    "$IVL_BIN/iverilog" -B "$IVL_LIB" -g2012 -o "$2" "$1" "$TB" \
        > "$WORK/compile.log" 2>&1
}

# classify <simout>  ->  PASS | CLOSURE_ONLY | DATA | DIED
classify () {
    local out="$1"
    if grep -q "RESULT: PASS" <<< "$out"; then echo PASS; return; fi
    if ! grep -q "RESULT: FAIL" <<< "$out"; then echo DIED; return; fi
    # Every failing check the bench prints starts with "  FAIL ".
    if grep "^  FAIL " <<< "$out" \
         | grep -qv "FAIL coverage closure\|FAIL closure counter"; then
        echo DATA
    else
        echo CLOSURE_ONLY
    fi
}

# The FIRST failing check, which is what makes a detection attributable to a
# checker rather than merely recorded.  2026-10-21 built its tx_empty matrix on
# this and it is what shows, below, that M4's committed reason is wrong.
first_fail () { grep "^  FAIL " <<< "$1" | head -1 | sed 's/^  FAIL //; s/:.*//'; }

run_one () {                        # $1=sim $2=seed $3=steer [$4=maxtx]
    local extra=""
    [ $# -ge 4 ] && extra="+maxtx=$4"
    timeout 170 "$IVL_BIN/vvp" -M "$IVL_LIB" "$1" \
        "+seed=$2" "+steer=$3" $extra 2>&1
}

closure_of () { grep -o "TRANSACTIONS TO CLOSURE  : [0-9]*" <<< "$1" \
                | grep -o "[0-9]*$"; }
total_of ()   { grep -o "transactions driven      : [0-9]*" <<< "$1" \
                | grep -o "[0-9]*$"; }

echo "=============================================================="
echo "BIMODAL MUTATION TEST -- examples/phase6_crv_uart/uart_crv_cov_tb.v"
echo "date: $(date -u +%F)   seeds: $SEEDS"
echo "arms: A steer=0 | B steer=1 | E steer=0 truncated to B's budget"
echo "=============================================================="
echo

compile "$RTL" "$WORK/sim_base" || { echo "BASELINE COMPILE ERROR"; exit 1; }

echo "G1  baseline: the suite must PASS on unmodified RTL in BOTH modes"
declare -A BUDGET
BASE_OK=1
printf "    %-6s %-14s %-14s %-12s\n" seed "A steer=0" "B steer=1" "B budget"
for s in $SEEDS; do
    oa="$(run_one "$WORK/sim_base" "$s" 0)"
    ob="$(run_one "$WORK/sim_base" "$s" 1)"
    ca="$(classify "$oa")"; cb="$(classify "$ob")"
    ta="$(total_of "$oa")"; tb="$(total_of "$ob")"
    BUDGET[$s]="$tb"
    printf "    %-6s %-14s %-14s %-12s\n" "$s" "$ca ($ta tx)" "$cb ($tb tx)" "$tb"
    [ "$ca" = PASS ] && [ "$cb" = PASS ] || BASE_OK=0
done
if [ "$BASE_OK" -ne 1 ]; then
    echo "    ABORT -- a baseline that does not pass makes every row meaningless."
    exit 1
fi
echo "    baseline verdict: PASS in both modes on all seeds"
echo

echo "G2  positive control on the arm-E classifier: unmodified RTL,"
echo "    truncated to arm B's budget, must be CLOSURE_ONLY -- never DATA."
G2_OK=1
for s in $SEEDS; do
    oe="$(run_one "$WORK/sim_base" "$s" 0 "${BUDGET[$s]}")"
    ce="$(classify "$oe")"
    printf "    seed %-4s maxtx=%-5s -> %s\n" "$s" "${BUDGET[$s]}" "$ce"
    [ "$ce" = CLOSURE_ONLY ] || G2_OK=0
done
if [ "$G2_OK" -ne 1 ]; then
    echo "    ABORT -- the classifier cannot tell truncation from detection,"
    echo "    so no arm-E row below would mean anything."
    exit 1
fi
echo "    G2 holds: truncation alone is never scored as a detection."
echo

echo "G2b neutrality control: a COMMENT-ONLY edit must compile and PASS in"
echo "    BOTH modes.  (Ported from run_mutation_tests.sh's G2, 2026-10-24."
echo "     G2 above controls the arm-E CLASSIFIER; nothing here had ever"
echo "     controlled the runner's attributability -- that a detection is"
echo "     caused by the mutant and not by the act of editing the file.)"
cp "$RTL" "$WORK/neutral.v"
printf '\n// G2b cosmetic-edit control, injected by run_mutation_tests_bimodal.sh\n' \
    >> "$WORK/neutral.v"
if cmp -s "$RTL" "$WORK/neutral.v"; then
    echo "    ABORT -- the neutral control did not change the file, so it"
    echo "    controls nothing."
    exit 1
fi
if ! compile "$WORK/neutral.v" "$WORK/sim_neutral"; then
    echo "    ABORT -- the comment-only mutant does not COMPILE, so the"
    echo "    control measured nothing.  This is G3's failure mode inside"
    echo "    the control that exists to make G3's verdicts attributable."
    head -2 "$WORK/compile.log" | sed 's/^/        /'
    exit 1
fi
G2B_OK=1
for s in $SEEDS; do
    cna="$(classify "$(run_one "$WORK/sim_neutral" "$s" 0)")"
    cnb="$(classify "$(run_one "$WORK/sim_neutral" "$s" 1)")"
    printf "    seed %-4s A steer=0 -> %-13s B steer=1 -> %s\n" \
           "$s" "$cna" "$cnb"
    [ "$cna" = PASS ] && [ "$cnb" = PASS ] || G2B_OK=0
done
if [ "$G2B_OK" -ne 1 ]; then
    echo "    ABORT -- a comment-only edit was not a clean PASS in both"
    echo "    modes, so every DETECT below is unattributable: it could be"
    echo "    caused by the mutant or by the editing."
    exit 1
fi
echo "    G2b holds: a change that cannot alter behaviour is never scored"
echo "    as a detection in either mode."
echo

MUT_NAMES=(
  "M1 TX parity polarity swapped (even<->odd)"
  "M2 RX data bit inverted at the mid-bit sample"
  "M3 CTRL.stop_bits ignored by TX (always one stop bit)"
  "M4 TX FIFO count never increments on a lone push"
  "M5 BAUD_DIV ignored by the baud generator (always divide-by-1)"
  "M6 STATUS read no longer clears the sticky error bits"
  "M7 tx_full asserts one entry early (tx_cnt >= 7)"
)
MUT_SEDS=(
  's/tx_par_bit <= (cfg_parity == PARITY_EVEN) ?  ^tx_fifo\[tx_rptr\] :/tx_par_bit <= (cfg_parity == PARITY_EVEN) ?  ~^tx_fifo[tx_rptr] :/'
  's/if (rx_mid) rx_shift\[rx_bit\] <= rx_sync;/if (rx_mid) rx_shift[rx_bit] <= ~rx_sync;/'
  's/if (tx_bit_done) tx_state <= cfg_two_stop ? TX_STOP2 : TX_IDLE;/if (tx_bit_done) tx_state <= TX_IDLE;/'
  's/2.b10: tx_cnt <= tx_cnt + 4.d1;/2\x27b10: tx_cnt <= tx_cnt;/'
  's/else if (baud_cnt == 8.d0) baud_cnt <= baud_div;/else if (baud_cnt == 8\x27d0) baud_cnt <= 8\x27d0;/'
  'PYTHON_M6'
  'PYTHON_M7'
)
# Arm E cannot speak about a mutant whose only detection route is the
# closure criterion, because arm E fails closure by construction.
MUT_E_READABLE=( yes yes yes yes yes yes yes )

inject () {                         # $1 = idx, $2 = dest
    cp "$RTL" "$2"
    if [ "$1" -eq 6 ]; then
        # M7 is injected by anchor, NOT by the committed sed.  The committed
        # sed carries one backslash too many -- 4\\x27d7 -- and sed turns the
        # doubled backslash into a literal one, emitting
        #     wire tx_full  = (tx_cnt >= 4\x27d7);
        # which is not Verilog.  See the M7 section at the end of this script.
        python3 - "$2" <<'PYM7'
import sys
p = sys.argv[1]
s = open(p).read()
old = "wire tx_full  = (tx_cnt == 4'd8);"
new = "wire tx_full  = (tx_cnt >= 4'd7);"
assert old in s, "M7 anchor not found"
open(p, "w").write(s.replace(old, new, 1))
PYM7
        return $?
    fi
    if [ "$1" -eq 5 ]; then
        python3 - "$2" <<'PYEOF'
import sys
p = sys.argv[1]
s = open(p).read()
old = """            if (rd_en && (paddr == ADDR_STATUS)) begin
                frame_err <= 1'b0; parity_err <= 1'b0; overrun_err <= 1'b0;
            end"""
new = """            if (1'b0) begin
                frame_err <= 1'b0; parity_err <= 1'b0; overrun_err <= 1'b0;
            end"""
assert old in s, "M6 anchor not found"
open(p, "w").write(s.replace(old, new, 1))
PYEOF
        return $?
    fi
    sed -i "${MUT_SEDS[$1]}" "$2"
    ! cmp -s "$RTL" "$2"
}

printf "%-52s %-9s %-9s %-9s\n" "mutant" "A st=0" "B st=1" "E equal"
printf "%-52s %-9s %-9s %-9s\n" "----------------------------------------------------" \
       "-------" "-------" "-------"
MOVERS=0
BADINJ=0
for idx in "${!MUT_NAMES[@]}"; do
    if ! inject "$idx" "$WORK/mut.v"; then
        printf "%-52s %s\n" "${MUT_NAMES[$idx]:0:52}" "INJECTION FAILED"
        continue
    fi
    # G3.  A mutant that does not COMPILE has not been tested by anything.
    # run_mutation_tests.sh scores COMPILE_ERROR as DETECT, which turns a
    # malformed injection into a reported success for the suite; its only
    # injection guard is `cmp -s`, which catches a sed that matched NOTHING
    # and not a sed that matched and emitted garbage.  The complete guard is
    # both: the file must change AND the result must still be Verilog.
    if ! compile "$WORK/mut.v" "$WORK/sim_mut"; then
        printf "%-52s %s\n" "${MUT_NAMES[$idx]:0:52}" \
               "*** INJECTION FAILED -- DOES NOT COMPILE (not a detection) ***"
        head -2 "$WORK/compile.log" | sed 's/^/        /'
        BADINJ=$((BADINJ+1))
        continue
    fi
    da=0; db=0; de=0; rowa=""; rowb=""; rowe=""; catch=""
    for s in $SEEDS; do
        oa="$(run_one "$WORK/sim_mut" "$s" 0)"
        va="$(classify "$oa")"
        vb="$(classify "$(run_one "$WORK/sim_mut" "$s" 1)")"
        ve="$(classify "$(run_one "$WORK/sim_mut" "$s" 0 "${BUDGET[$s]}")")"
        f="$(first_fail "$oa")"
        [ -n "$f" ] && catch="$catch$f\n"
        [ "$va" = DATA ] || [ "$va" = DIED ] || [ "$va" = CLOSURE_ONLY ] && da=$((da+1))
        [ "$vb" = DATA ] || [ "$vb" = DIED ] || [ "$vb" = CLOSURE_ONLY ] && db=$((db+1))
        [ "$ve" = DATA ] || [ "$ve" = DIED ] && de=$((de+1))
        rowa="$rowa ${va:0:1}"; rowb="$rowb ${vb:0:1}"; rowe="$rowe ${ve:0:1}"
    done
    n=$(wc -w <<< "$SEEDS")
    if [ "${MUT_E_READABLE[$idx]}" = "yes" ]; then
        estr="$de/$n"
    else
        estr="n/a"
    fi
    printf "%-52s %-9s %-9s %-9s\n" "${MUT_NAMES[$idx]:0:52}" \
           "$da/$n" "$db/$n" "$estr"
    printf "%-52s %-9s %-9s %-9s\n" "   per seed ($SEEDS)" "$rowa" "$rowb" "$rowe"
    if [ -n "$catch" ]; then
        echo "   caught first by (arm A, distinct over seeds):"
        printf "$catch" | sort -u | sed 's/^/       /'
    fi
    if [ "$da" -ne "$db" ]; then
        MOVERS=$((MOVERS+1))
        echo "   *** MOVES BETWEEN MODES: $da/$n under steer=0 vs $db/$n under steer=1"
        if [ "${MUT_E_READABLE[$idx]}" = "yes" ]; then
            if [ "$de" -gt "$db" ]; then
                echo "   *** AND SURVIVES THE EQUAL-BUDGET CONTROL ($de/$n at steer=1's"
                echo "       own transaction count), so VOLUME DOES NOT EXPLAIN IT."
            else
                echo "   *** BUT DOES NOT SURVIVE THE EQUAL-BUDGET CONTROL ($de/$n),"
                echo "       so volume is sufficient and the mode comparison says"
                echo "       nothing about the coverage model."
            fi
        fi
    fi
    echo
done

echo "=============================================================="
echo "  mutants injected          : ${#MUT_NAMES[@]}"
echo "  injections that failed    : $BADINJ   (G3; never scored as detections)"
echo "  mutants whose detection   : $MOVERS"
echo "    count differs by mode"
echo
echo "  KEY  P=PASS (escaped)  D=DATA check failed  C=closure only  X=died"
echo "  Arm A/B count C as a detection, since closure IS a pass criterion of"
echo "  this bench.  Arm E does NOT, because arm E fails closure by"
echo "  construction -- see G2."
echo "=============================================================="
echo
echo "=============================================================="
echo "M7 AS THE COMMITTED RUNNER INJECTS IT"
echo "=============================================================="
echo
echo "  run_mutation_tests.sh injects M7 with"
echo "      s/.../wire tx_full  = (tx_cnt >= 4\\\\x27d7);/"
echo "  One backslash too many: sed turns the doubled backslash into a"
echo "  literal one and emits"
cp "$RTL" "$WORK/m7_committed.v"
sed -i 's/wire tx_full  = (tx_cnt == 4.d8);/wire tx_full  = (tx_cnt >= 4\\x27d7);/' \
    "$WORK/m7_committed.v"
echo "      $(grep 'wire tx_full' "$WORK/m7_committed.v" | sed 's/^ *//')"
echo "  which is not Verilog:"
compile "$WORK/m7_committed.v" "$WORK/sim_bad" \
    || head -2 "$WORK/compile.log" | sed 's/^/      /'
echo
echo "  That runner scores COMPILE_ERROR as DETECT, so this row has read"
echo "  \"predicted DETECT, got DETECT (as predicted)\" in every committed"
echo "  report since 2026-10-12, with a stated reason naming a check"
echo "  (\"the predicted-occupancy check, which names the occupancy\") that"
echo "  this mutant has never reached.  Injected correctly, M7 IS detected"
echo "  5/5 in both modes AND by exactly that check -- see the M7 row above."
echo "  The conclusion was right; the evidence for it did not exist."
echo "=============================================================="
rm -rf "$WORK"

# G3, second half (2026-10-23).  BADINJ was incremented, printed in the
# summary as "injections that failed", and then never consulted: this
# script's last statement was the rm above, so it exited 0.  The session
# that discovered COMPILE_ERROR-scored-as-DETECT built a runner that
# refused to score it (Q1, correct) and still reported the run as green
# (Q2).  Measured on 2026-10-23 by injecting a non-compiling mutant.
if [ "$BADINJ" -ne 0 ]; then
    echo
    echo "RESULT: FAIL  ($BADINJ injection(s) did not compile -- those mutants"
    echo "              were never tested, so this run measures nothing about"
    echo "              them.  A compile error is an injection failure, never"
    echo "              a detection and never a pass.)"
    exit 1
fi
echo
echo "RESULT: PASS  (every injection compiled; G3 green)"
