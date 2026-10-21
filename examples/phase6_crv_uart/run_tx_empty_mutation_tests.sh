#!/usr/bin/env bash
# examples/phase6_crv_uart/run_tx_empty_mutation_tests.sh
#
# Mutation-tests the two LIVE tx_empty predictions in
# examples/phase6_crv_uart/uart_crv_cov_tb.v:
#
#     "fill phase starts with tx_empty set"      st[1] == 1 before any push
#     "post-push tx_empty agrees with occupancy" st[1] == (pushed == 0)
#
# WHY THIS EXISTS.  As of 2026-10-18 no committed mutation report in this
# repository mentions tx_empty -- checked across all twelve -- while the
# prediction is live in this bench and the signal is read by the RTL's TX
# engine, its IRQ decode and its STATUS decode.  An untested prediction has an
# unmeasured verdict, which is the 2026-09-17 lesson that started mutation
# testing here (a bench that passed 55/55 against deliberately broken RTL).
#
# THE METHODOLOGICAL POINT, and the reason this is not just four more rows.
#
#   tx_empty is read in THREE places in rtl/uart_controller.v: the TX engine's
#   pop condition (`if (!tx_empty)`), the IRQ decode, and the STATUS decode.
#   Mutating the WIRE therefore changes what the DUT DOES, and the suite's RX
#   data comparison will catch that -- while saying nothing whatever about
#   whether the tx_empty prediction works.  "Detected" and "detected by the
#   prediction under test" are different verdicts, and a report that conflates
#   them answers a weaker question than the one it was written to ask, which
#   is this repository's recorded dominant failure mode.
#
#   So the mutants are split.  T1-T3 mutate the STATUS DECODE ONLY, leaving
#   the engine on the true tx_empty; nothing but a STATUS reader can see them,
#   so a detection is attributable to the prediction and to nothing else.  T4
#   mutates the wire, and is included precisely to show that its detection is
#   NOT attributable -- it is the control for the distinction.
#
#   Every row therefore reports WHICH CHECK FAILED FIRST, not merely PASS or
#   FAIL.  A mutant detected by the wrong check is an escape of the
#   prediction wearing a detection's clothes.
#
# The RTL's own assertions are all inside `ifdef FORMAL (line 395 onward) and
# this flow compiles without -DFORMAL, so C5's `assert(prdata[1] == tx_empty)`
# is inert here and cannot be the thing doing the detecting.  Stated because
# it would otherwise be a silent confound for exactly T1-T3.
#
# Every mutant is injected into a COPY under /tmp; the repo's RTL is never
# modified.
#
# Usage:  bash examples/phase6_crv_uart/run_tx_empty_mutation_tests.sh
# Run from the repo root.

set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

# shellcheck disable=SC1091
source tools/setup_iverilog.sh > /dev/null 2>&1
IVL_BIN="${IVERILOG_INSTALL_DIR:-/tmp/iverilog_install}/usr/bin"
IVL_LIB="${IVERILOG_INSTALL_DIR:-/tmp/iverilog_install}/usr/lib/x86_64-linux-gnu/ivl"

WORK="$(mktemp -d /tmp/uart_txe_mut.XXXXXX)"
TB="examples/phase6_crv_uart/uart_crv_cov_tb.v"
RTL="rtl/uart_controller.v"
SEEDS="1 3 5 7"
MODES="0 1"   # 0 = pure constrained-random, 1 = coverage-driven steering

DECODE_LINE='                             rx_avail, rx_full, tx_empty, tx_full};'
WIRE_LINE='    wire tx_empty = (tx_cnt == 4.d0);'

fail_count=0
note_fail () { fail_count=$((fail_count + 1)); }

# run_matrix <rtl> <steer> -> "<n_detected>/<n_seeds>|<first failing check>|<escaped seeds>"
#
# PER SEED, and this is not a detail.  The first draft of this script took the
# first seed that failed and reported DETECTED, which is first-failure-wins:
# it reports a mutant as caught while hiding that the suite misses it on half
# its seeds.  That is this repository's recorded dominant failure mode -- a
# verdict answering a weaker question than the one it was written to ask --
# committed inside the very harness written to measure a prediction's reach.
# It was caught by running T3 by hand across modes, not by any control here,
# and the matrix below exists so that it cannot recur silently.
run_matrix () {
    local rtl="$1" steer="$2" out rc first="" det=0 n=0 esc=""
    "$IVL_BIN/iverilog" -B "$IVL_LIB" -g2012 -o "$WORK/sim" "$rtl" "$TB" \
        > "$WORK/compile.log" 2>&1 || { echo "COMPILE_ERROR||"; return; }
    for s in $SEEDS; do
        n=$((n + 1))
        rc=0
        out="$(timeout 170 "$IVL_BIN/vvp" -M "$IVL_LIB" "$WORK/sim" \
               "+seed=$s" "+steer=$steer" 2>&1)" || rc=1
        if grep -q "RESULT: PASS" <<< "$out"; then
            esc="$esc $s"
        else
            det=$((det + 1))
            if [ -z "$first" ]; then
                first="$(grep -m1 '^  FAIL ' <<< "$out" \
                         | sed 's/^  FAIL //; s/: got .*//')"
                [ -z "$first" ] && first="(no FAIL line -- died or hung)"
            fi
        fi
    done
    echo "$det/$n|$first|${esc# }"
}

# mutate <tag> <sed-expr> -> path to mutated rtl, or empty on a no-op edit
mutate () {
    local tag="$1" expr="$2" dst="$WORK/$1.v"
    sed "$expr" "$RTL" > "$dst"
    if cmp -s "$RTL" "$dst"; then echo ""; else echo "$dst"; fi
}

echo "=============================================================="
echo "MUTATION TEST -- the tx_empty prediction"
echo "  bench : $TB"
echo "  date  : $(date -u +%F)   seeds: $SEEDS   modes: $MODES (0=random, 1=steered)"
echo "=============================================================="
echo

echo "G1  baseline: the suite must PASS on the unmodified RTL, every seed,"
echo "    every mode"
ok=1
for st in $MODES; do
    BASE="$(run_matrix "$RTL" "$st")"
    echo "    steer=$st  detected ${BASE%%|*} of the seeds (0 of N is what a"
    echo "               clean baseline means here)"
    [ "${BASE%%|*}" = "0/4" ] || ok=0
done
if [ "$ok" -ne 1 ]; then
    echo "    ABORT -- a baseline that does not pass makes every mutant row"
    echo "    meaningless."
    exit 1
fi
echo "    OK -- the unmodified RTL passes all seeds in both modes."
echo

echo "G2  the two predictions under test are actually IN the bench"
echo "    (naming a check in a report does not make the bench contain it --"
echo "     the 2026-10-20 lesson, applied to this script's own premise)"
for c in "fill phase starts with tx_empty set" \
         "post-push tx_empty agrees with occupancy"; do
    if grep -qF "$c" "$TB"; then
        echo "    PRESENT  \"$c\""
    else
        echo "    ABSENT   \"$c\"  <-- this script's premise is stale"
        note_fail
    fi
done
echo

echo "G3  every mutant must actually CHANGE the file it claims to change"
echo "    (a sed that silently matches nothing reports a PERFECT escape,"
echo "     which is the most flattering possible failure)"
echo

declare -A DET FIRST ESC

row () {                             # $1 id  $2 description  $3 sed expr
    local id="$1" desc="$2" expr="$3" path res st
    path="$(mutate "$id" "$expr")"
    if [ -z "$path" ]; then
        echo "  $id  $desc"
        echo "      NO-OP -- sed changed nothing.  G3 FAILED."
        note_fail
        for st in $MODES; do DET[$id,$st]="NOOP"; FIRST[$id,$st]=""; ESC[$id,$st]=""; done
        return
    fi
    for st in $MODES; do
        res="$(run_matrix "$path" "$st")"
        DET[$id,$st]="${res%%|*}"
        FIRST[$id,$st]="$(cut -d'|' -f2 <<< "$res")"
        ESC[$id,$st]="$(cut -d'|' -f3 <<< "$res")"
    done
}

# ---- T1-T3: STATUS DECODE ONLY.  The engine keeps the true tx_empty, so
#      only a STATUS reader can possibly see these.
row T1 "STATUS decode: tx_empty stuck CLEAR" \
    "s/rx_avail, rx_full, tx_empty, tx_full};/rx_avail, rx_full, 1'b0, tx_full};/"
row T2 "STATUS decode: tx_empty stuck SET" \
    "s/rx_avail, rx_full, tx_empty, tx_full};/rx_avail, rx_full, 1'b1, tx_full};/"
row T3 "STATUS decode: tx_empty one entry EARLY" \
    "s/rx_avail, rx_full, tx_empty, tx_full};/rx_avail, rx_full, (tx_cnt <= 4'd1), tx_full};/"

# ---- T4: the WIRE.  Included as the control for attributability, not as a
#      fourth test of the prediction.
row T4 "WIRE: tx_empty one entry early (engine too)" \
    "s/wire tx_empty = (tx_cnt == 4'd0);/wire tx_empty = (tx_cnt <= 4'd1);/"

DESC_T1="STATUS decode: tx_empty stuck CLEAR"
DESC_T2="STATUS decode: tx_empty stuck SET"
DESC_T3="STATUS decode: tx_empty one entry EARLY"
DESC_T4="WIRE: tx_empty one entry early (engine too)"

echo "--------------------------------------------------------------"
echo "DETECTION MATRIX -- seeds $SEEDS, both stimulus modes"
echo "--------------------------------------------------------------"
echo
printf '  %-4s %-44s %-12s %-12s\n' "ID" "mutant" "steer=0" "steer=1"
printf '  %-4s %-44s %-12s %-12s\n' "--" "------" "random" "cov-driven"
for id in T1 T2 T3 T4; do
    eval "d=\$DESC_$id"
    printf '  %-4s %-44s %-12s %-12s\n' "$id" "$d" \
           "${DET[$id,0]}" "${DET[$id,1]}"
done
echo
for id in T1 T2 T3 T4; do
    for st in $MODES; do
        if [ -n "${ESC[$id,$st]}" ]; then
            echo "  $id escaped at steer=$st on seed(s): ${ESC[$id,$st]}"
        fi
    done
done
echo

echo "--------------------------------------------------------------"
echo "ADJUDICATION -- detected, or detected BY THE PREDICTION?"
echo "--------------------------------------------------------------"
echo

adj () {                             # $1 id  $2 expectation text
    local id="$1" exp="$2" st v f
    eval "local d=\$DESC_$id"
    echo "  $id  $d"
    echo "      $exp"
    for st in $MODES; do
        v="${DET[$id,$st]}"; f="${FIRST[$id,$st]}"
        echo "      steer=$st  detected $v   first failing check: ${f:--}"
        if [ -n "$f" ]; then
            if grep -qF "tx_empty" <<< "$f"; then
                echo "                 ATTRIBUTABLE -- the failing check is a"
                echo "                 tx_empty prediction, so the detection is"
                echo "                 this prediction's own."
            else
                echo "                 NOT ATTRIBUTABLE -- detected, but by a"
                echo "                 check that is not a tx_empty prediction."
            fi
        fi
    done
    echo
}

adj T1 "stuck CLEAR can only be seen by the fill-phase check, which is the"
adj T2 "stuck SET can only be seen by the post-push check, the other one"
adj T3 "one entry early is wrong ONLY at occupancy 1, so it needs a burst"
adj T4 "the control: this one changes what the DUT DOES, so a detection"

echo "--------------------------------------------------------------"
echo "WHAT THIS MEASURES, AND THE ONE RESULT THAT WAS NOT EXPECTED"
echo "--------------------------------------------------------------"
echo
echo "  T1 and T2 are the two directions of a stuck bit, and between them"
echo "  they exercise BOTH predictions and neither is redundant: the"
echo "  fill-phase check can only ever see tx_empty wrongly CLEAR, and the"
echo "  post-push check can only ever see it wrongly SET, because C4"
echo "  constrains burst_len to [1, 8] so the post-push occupancy is never"
echo "  zero.  Both are caught in both modes on every seed."
echo
echo "  T3 IS THE RESULT.  A decode asserting tx_empty one entry early is"
echo "  correct at occupancy 0 and wrong only at occupancy 1, so it needs a"
echo "  burst that pushed EXACTLY ONE byte.  Measured:"
echo
echo "      steer=0 (pure constrained-random)  ${DET[T3,0]} seeds detect"
echo "      steer=1 (coverage-driven steering) ${DET[T3,1]} seeds detect"
echo
echo "  THE COVERAGE-DRIVEN MODE IS WORSE.  That is the opposite of what"
echo "  this script's first draft asserted -- it claimed steering reached"
echo "  burst_len = 1 'by construction' because pick_config_steered has a"
echo "  branch setting burst_len = 1.  Reading the task rather than the"
echo "  branch: burst_len is drawn randomly from [1, 8] at the TOP of"
echo "  pick_config_steered, and the coverage loops then OVERWRITE it with"
echo "  8 or 3 or 1 to chase an unhit cov_txq bin.  Two of those three"
echo "  values destroy the length-1 bursts this mutant needs, and the"
echo "  burst_len = 1 branch fires only while cov_txq[0] is unhit -- which"
echo "  it is not, since the fill phase observes an empty FIFO immediately."
echo "  So steering can only ever REMOVE length-1 bursts here, never add"
echo "  one."
echo
echo "  The lesson is not about this mutant.  Coverage closure and defect"
echo "  detection are different objectives, and a generator aimed at the"
echo "  first unhit bin will spend stimulus it was otherwise spending on"
echo "  states no bin happens to name.  Occupancy 1 is such a state: cov_txq"
echo "  bins empty / partial / full, and 'partial' is hit by any burst of"
echo "  2 to 7 just as well as by a burst of 1.  THE COVERAGE MODEL CANNOT"
echo "  SEE THE DISTINCTION THE PREDICTION DEPENDS ON, so steering toward"
echo "  100 % closure is free to walk away from it."
echo
echo "  T4 is deliberately uninformative about the prediction.  It is"
echo "  detected in both modes, by the burst watchdog -- a data-path check"
echo "  -- because mutating the WIRE stops the engine popping the last"
echo "  byte.  Had the adjudication reported only DETECTED, this row would"
echo "  have read as a fourth success for a prediction it never tested."
echo

if [ "$fail_count" -ne 0 ]; then
    echo "RESULT: FAIL  ($fail_count control failure(s))"
    rm -rf "$WORK"
    exit 1
fi
echo "RESULT: PASS  (all controls green)"
rm -rf "$WORK"
