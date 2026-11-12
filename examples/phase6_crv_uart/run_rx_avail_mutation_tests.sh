#!/usr/bin/env bash
# examples/phase6_crv_uart/run_rx_avail_mutation_tests.sh
#
# Mutation-tests the census's SYNC_ONLY claim for STATUS.rx_avail (st[3]) in
# examples/phase6_crv_uart/uart_crv_cov_tb.v.
#
# WHY THIS EXISTS.  tools/scoreboard_dut_signal_census.py classifies
# STATUS.rx_avail as SYNC_ONLY -- read to decide WHEN to sample, never checked
# for WHAT it should be -- and records its exposure as an ARGUMENT, not a
# measurement:
#
#     "an rx_avail that never asserts trips the per-burst watchdog, and one
#      that asserts early reads a byte the receiver has not finished, which
#      the data comparison catches.  So the exposure exists, but it is
#      indirect and no mutant has ever been run for it."
#
# It is 1 of only 2 SYNC_ONLY rows of 18 and has been the census's weakest row
# since 2026-10-12, carried on the standing list ever since as the cheapest
# item that adds verification REACH rather than auditing existing reach.
#
# THE ADJUDICATION IS INVERTED RELATIVE TO run_tx_empty_mutation_tests.sh,
# and that is the point of writing a separate runner rather than adding rows.
#
#   For tx_empty there ARE live predictions naming the signal, so that runner
#   asks "detected, or detected BY THE PREDICTION?" and treats a failing check
#   naming tx_empty as the attributable case.
#
#   For rx_avail the census's claim is that NO check names it.  So the
#   attributable case is the OPPOSITE one: a detection is consistent with
#   SYNC_ONLY exactly when the first failing check does NOT name rx_avail --
#   when the bench mis-sequences and some data-path check notices, rather than
#   a status prediction firing.  Three outcomes, three different findings:
#
#     escape in any mode           -> the exposure claim is FALSE; the row is
#                                     weaker than SYNC_ONLY, it is unobserved
#     detected by an rx_avail check-> the row is misclassified; it is
#                                     PREDICTED or TRUSTED, not SYNC_ONLY
#     detected by a data-path check-> SYNC_ONLY confirmed, and the indirect
#                                     exposure is now measured rather than
#                                     argued
#
# G2 checks the census's PREMISE mechanically rather than trusting it: that
# no check_eq in the bench names rx_avail or st[3].  Naming a check in a
# report does not make the bench contain it (2026-10-20); the converse --
# asserting a bench does NOT contain one -- is the same fault reversed, and
# this runner's whole adjudication rests on it.
#
# The RTL's own assertions are inside `ifdef FORMAL and this flow compiles
# without -DFORMAL, so line 576's `assert(prdata[3] == rx_avail)` -- which IS
# an rx_avail prediction -- is inert here and cannot do the detecting.  Stated
# because it would otherwise be a silent confound for exactly R1-R3.
#
# Every mutant is injected into a COPY under /tmp; the repo's RTL is never
# modified.
#
# Usage:  bash examples/phase6_crv_uart/run_rx_avail_mutation_tests.sh
# Run from the repo root.

set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

# TMPDIR, and it is not boilerplate.  2026-11-07: the automation sandbox's
# default TMPDIR resolves onto a filesystem that is 100 % full, and
# setup_iverilog.sh's mktemp landed there, so the install failed with
# "failed to download" -- an ENOSPC misreported as a network fault.  Pinning
# TMPDIR here keeps this runner working regardless of that.
export TMPDIR="${TMPDIR_OVERRIDE:-/tmp}"

# shellcheck disable=SC1091
source tools/setup_iverilog.sh > /dev/null 2>&1
# the WRAPPERS in bin/, not the raw binaries in usr/bin: only the wrappers carry
# the TMPDIR fallback added 2026-11-07, and NOTHING in this repository called them
# until 2026-11-12 -- see tools/toolchain_preflight.sh
IVL_BIN="${IVERILOG_INSTALL_DIR:-/tmp/iverilog_install}/bin"
IVL_LIB="${IVERILOG_INSTALL_DIR:-/tmp/iverilog_install}/usr/lib/x86_64-linux-gnu/ivl"

WORK="$(mktemp -d /tmp/uart_rxa_mut.XXXXXX)"
TB="examples/phase6_crv_uart/uart_crv_cov_tb.v"
RTL="rtl/uart_controller.v"
SEEDS="1 3 5 7"
MODES="0 1"   # 0 = pure constrained-random, 1 = coverage-driven steering

fail_count=0
note_fail () { fail_count=$((fail_count + 1)); }

# run_matrix <rtl> <steer> -> "<n_detected>/<n_seeds>|<first failing check>|<escaped seeds>"
# Per seed, never first-failure-wins: the 2026-10-21 lesson from the tx_empty
# runner, which reported a mutant caught while hiding that half its seeds
# missed it.
run_matrix () {
    local rtl="$1" steer="$2" out rc first="" det=0 n=0 esc=""
    "$IVL_BIN/iverilog" -B "$IVL_LIB" -g2012 -o "$WORK/sim" "$rtl" "$TB" \
        > "$WORK/compile.log" 2>&1 || { echo "COMPILE_ERROR||"; return; }
    for s in $SEEDS; do
        n=$((n + 1))
        rc=0
        out="$(timeout 60 "$IVL_BIN/vvp" -M "$IVL_LIB" "$WORK/sim" \
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

mutate () {
    local tag="$1" expr="$2" dst="$WORK/$1.v"
    sed "$expr" "$RTL" > "$dst"
    if cmp -s "$RTL" "$dst"; then echo ""; else echo "$dst"; fi
}

echo "=============================================================="
echo "MUTATION TEST -- the STATUS.rx_avail SYNC_ONLY classification"
echo "  bench : $TB"
echo "  date  : $(date -u +%F)   seeds: $SEEDS   modes: $MODES (0=random, 1=steered)"
echo "=============================================================="
echo

echo "G1  baseline: the suite must PASS on the unmodified RTL, every seed,"
echo "    every mode"
ok=1
for st in $MODES; do
    BASE="$(run_matrix "$RTL" "$st")"
    echo "    steer=$st  detected ${BASE%%|*}   (0 of N is what a clean baseline means)"
    [ "${BASE%%|*}" = "0/4" ] || ok=0
done
if [ "$ok" -ne 1 ]; then
    echo "    ABORT -- a baseline that does not pass makes every mutant row"
    echo "    meaningless."
    exit 1
fi
echo "    OK -- the unmodified RTL passes all seeds in both modes."
echo

echo "G2  THE CENSUS'S PREMISE, CHECKED RATHER THAN QUOTED: no check in the"
echo "    bench names rx_avail or st[3].  The whole adjudication below rests"
echo "    on this, so it is measured here and not assumed."
NAMED="$(grep -n 'check_eq' "$TB" | grep -Ei 'rx_avail|st\[3\]' || true)"
if [ -z "$NAMED" ]; then
    echo "    CONFIRMED -- 0 of $(grep -c 'check_eq' "$TB") check_eq calls in the bench"
    echo "    mention rx_avail or st[3].  SYNC_ONLY's precondition holds."
else
    echo "    REFUTED -- the bench DOES check rx_avail, so the census row is"
    echo "    misclassified and should read PREDICTED or TRUSTED:"
    echo "$NAMED" | sed 's/^/      /'
    note_fail
fi
echo "    and the sequencing read the census names IS present:"
if grep -qF 'if (st[3]) begin' "$TB"; then
    echo "      PRESENT  \"if (st[3]) begin\"  -- the drain loop's gate"
else
    echo "      ABSENT   -- this runner's premise is stale"
    note_fail
fi
echo

echo "G2b neutrality control: a COMMENT-ONLY edit must compile and ESCAPE"
cp "$RTL" "$WORK/neutral.v"
printf '\n// G2b cosmetic-edit control, injected by run_rx_avail_mutation_tests.sh\n' \
    >> "$WORK/neutral.v"
if cmp -s "$RTL" "$WORK/neutral.v"; then
    echo "    ABORT -- the neutral control did not change the file."
    exit 1
fi
neu_ok=1; neu_built=1
for st in $MODES; do
    NEU="$(run_matrix "$WORK/neutral.v" "$st")"
    echo "    steer=$st  detected ${NEU%%|*}   (must be 0/4)"
    [ "${NEU%%|*}" = "COMPILE_ERROR" ] && neu_built=0
    [ "${NEU%%|*}" = "0/4" ] || neu_ok=0
done
if [ "$neu_built" -ne 1 ]; then
    echo "    ABORT -- the comment-only mutant does not compile."
    exit 1
fi
if [ "$neu_ok" -ne 1 ]; then
    echo "    ABORT -- a comment-only edit was not a clean escape in every mode."
    exit 1
fi
echo "    OK -- a comment-only edit escapes in both modes."
echo

declare -A DET FIRST ESC

row () {
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
        if [ "${DET[$id,$st]}" = "COMPILE_ERROR" ]; then
            echo "  $id  INJECTION FAILED at steer=$st -- the edit applied but"
            echo "      the result does not compile.  G3 FAILED.  A compile"
            echo "      error is an injection failure, never a detection."
            note_fail
        fi
    done
}

echo "G3  every mutant must actually CHANGE the file it claims to change"
echo

# R1-R3: STATUS DECODE ONLY.  rx_pop and the IRQ decode keep the true
# rx_avail, so only a STATUS reader can see these -- which here means only the
# drain loop's sequencing gate.
row R1 "STATUS decode: rx_avail stuck CLEAR" \
    "s/rx_avail, rx_full, tx_empty, tx_full};/1'b0, rx_full, tx_empty, tx_full};/"
row R2 "STATUS decode: rx_avail stuck SET" \
    "s/rx_avail, rx_full, tx_empty, tx_full};/1'b1, rx_full, tx_empty, tx_full};/"
row R3 "STATUS decode: rx_avail one entry LATE" \
    "s/rx_avail, rx_full, tx_empty, tx_full};/(rx_cnt > 4'd1), rx_full, tx_empty, tx_full};/"
# R4: the WIRE.  rx_pop gates on rx_avail, so this changes what the DUT DOES.
# Included as the control for attributability, not as a fourth test.
row R4 "WIRE: rx_avail one entry late (rx_pop too)" \
    "s/wire rx_avail = (rx_cnt != 4'd0);/wire rx_avail = (rx_cnt > 4'd1);/"

DESC_R1="STATUS decode: rx_avail stuck CLEAR"
DESC_R2="STATUS decode: rx_avail stuck SET"
DESC_R3="STATUS decode: rx_avail one entry LATE"
DESC_R4="WIRE: rx_avail one entry late (rx_pop too)"

echo "--------------------------------------------------------------"
echo "DETECTION MATRIX -- seeds $SEEDS, both stimulus modes"
echo "--------------------------------------------------------------"
echo
printf '  %-4s %-44s %-12s %-12s\n' "ID" "mutant" "steer=0" "steer=1"
printf '  %-4s %-44s %-12s %-12s\n' "--" "------" "random" "cov-driven"
for id in R1 R2 R3 R4; do
    eval "d=\$DESC_$id"
    printf '  %-4s %-44s %-12s %-12s\n' "$id" "$d" "${DET[$id,0]}" "${DET[$id,1]}"
done
echo
for id in R1 R2 R3 R4; do
    for st in $MODES; do
        [ -n "${ESC[$id,$st]}" ] && echo "  $id escaped at steer=$st on seed(s): ${ESC[$id,$st]}"
    done
done
echo

echo "--------------------------------------------------------------"
echo "ADJUDICATION -- is SYNC_ONLY the right class?"
echo "  consistent with SYNC_ONLY = detected, by a check that does NOT"
echo "  name rx_avail.  The inverse of the tx_empty runner's test."
echo "--------------------------------------------------------------"
echo

sync_only_holds=1
# CAUGHT BY READING THE FIRST RUN'S OUTPUT, 2026-11-07.  The first draft fed
# ALL FOUR rows into sync_only_holds, R4 included -- so the control that
# exists to sit OUTSIDE the classification verdict was voting on it.  R4
# mutates the wire, which changes what the DUT does; it can neither confirm
# nor refute a claim about what the BENCH reads, and a verdict it can move is
# a verdict answering a weaker question than the one it was written to ask.
# `verdict_bearing` is now an explicit argument, so which rows carry the
# verdict is in the call site rather than implicit in the loop.
adj () {
    local id="$1" verdict_bearing="$2" exp="$3" st v f
    eval "local d=\$DESC_$id"
    echo "  $id  $d        [$( [ "$verdict_bearing" = 1 ] && echo 'VERDICT-BEARING' || echo 'CONTROL -- does not move the verdict')]"
    echo "      $exp"
    for st in $MODES; do
        v="${DET[$id,$st]}"; f="${FIRST[$id,$st]}"
        echo "      steer=$st  detected $v   first failing check: ${f:--}"
        if [ "${v%%/*}" = "0" ]; then
            echo "                 ESCAPED -- the exposure the census ARGUED"
            echo "                 for does not exist in this mode."
            [ "$verdict_bearing" = 1 ] && sync_only_holds=0
        elif grep -qiE 'rx_avail|st\[3\]' <<< "$f"; then
            echo "                 MISCLASSIFIED -- detected by a check that"
            echo "                 names rx_avail, so the row is PREDICTED or"
            echo "                 TRUSTED and not SYNC_ONLY."
            [ "$verdict_bearing" = 1 ] && sync_only_holds=0
        else
            echo "                 CONSISTENT WITH SYNC_ONLY -- the bench"
            echo "                 mis-sequenced and a data-path check noticed."
        fi
    done
    echo
}

adj R1 1 "the census predicts the per-burst WATCHDOG, because a drain loop"
adj R2 1 "the census predicts the DATA COMPARISON: a read with nothing to read"
adj R3 1 "late by one entry is wrong only at occupancy 1, so it needs a burst"
adj R4 0 "the control: rx_pop gates on rx_avail, so this changes DUT behaviour"

echo "--------------------------------------------------------------"
echo "WHAT THIS MEASURES"
echo "--------------------------------------------------------------"
echo
if [ "$sync_only_holds" -eq 1 ]; then
    echo "  SYNC_ONLY is CONFIRMED for STATUS.rx_avail, and the census's"
    echo "  exposure argument is now a measurement.  Every mutant is caught,"
    echo "  none by a check naming the signal -- which is exactly what"
    echo "  'read to sequence, never checked, but not unexposed' means."
else
    echo "  SYNC_ONLY DOES NOT HOLD as written.  See the rows above: either a"
    echo "  mutant escaped, in which case the exposure was argued and is not"
    echo "  there, or a check naming rx_avail did the detecting, in which case"
    echo "  the row belongs in a different class.  The census row needs"
    echo "  amending, and the amendment is a finding and not a correction."
fi
echo
echo "  R4 is deliberately uninformative about the classification.  rx_pop"
echo "  gates on rx_avail, so mutating the WIRE stops the RTL popping the"
echo "  last byte: a detection there is the data path noticing the DUT"
echo "  changed, not the bench noticing its sequencing gate lied.  Had the"
echo "  matrix reported only DETECTED, this row would have read as a fourth"
echo "  success for a claim it never tested."
echo
echo "  AND R3 AND R4 ARE INDISTINGUISHABLE IN THIS MATRIX.  Both report the"
echo "  same first failing check with the same byte count, because both make"
echo "  the last byte unreadable -- R3 by stopping the bench asking for it,"
echo "  R4 by stopping the RTL popping it.  The mechanisms differ and this"
echo "  instrument cannot tell them apart, which bounds what the control"
echo "  establishes: it shows a wire mutation is detected, not that it is"
echo "  detected DIFFERENTLY.  Separating them needs a check that observes"
echo "  rx_cnt directly, and that is logged rather than claimed here."
echo

if [ "$fail_count" -ne 0 ]; then
    echo "RESULT: FAIL  ($fail_count control failure(s))"
    rm -rf "$WORK"
    exit 1
fi
echo "RESULT: PASS  (all controls green)"
rm -rf "$WORK"
