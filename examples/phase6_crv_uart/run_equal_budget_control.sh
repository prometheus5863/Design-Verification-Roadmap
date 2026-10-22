#!/usr/bin/env bash
# examples/phase6_crv_uart/run_equal_budget_control.sh
#
# THE CONTROL FOR THE 2026-10-21 RESULT, RUN WHERE THE MOVEMENT WAS OBSERVED.
#
# 2026-10-21 found mutant T3 (STATUS decode: tx_empty one entry EARLY)
# detected 4/4 under `steer=0` and 2/4 under `steer=1`, and concluded that
# "the coverage-driven mode detects less than pure random", with a mechanism
# read out of `pick_config_steered`: `burst_len` is overwritten to chase an
# unhit `cov_txq` bin, the `burst_len = 1` branch is guarded by a bin the fill
# phase hits first, so steering can only REMOVE the length-1 bursts T3 needs.
#
# That mechanism is still in the code.  The EXPERIMENT, however, could not
# support the conclusion on its own, because the two modes do not drive the
# same amount of stimulus.  The bench's run loop is
#
#     while (total_tx < max_tx && bins_hit() < N_BINS && errors == 0)
#
# so it stops AT CLOSURE, and steering exists to reach closure sooner.
# Measured over five seeds, `steer=0` drives 2.1x to 12.0x more transactions
# before it stops.  A mutant needing a rare event is therefore more likely to
# be caught under `steer=0` FOR VOLUME ALONE -- with nothing implied about the
# coverage model.  Two explanations, one observation.
#
# THE CONTROL.  Run `steer=0` TRUNCATED to `steer=1`'s own transaction count
# for the same seed (+maxtx).  Then:
#
#   detected at equal budget  -> volume does not explain the escape, and the
#                                coverage model does.
#   escaped at equal budget   -> volume is sufficient, and the 2026-10-21
#                                reading is not supported by its experiment.
#
# ADJUDICATION.  The truncated arm cannot reach closure, so it ALWAYS fails
# the bench's closure pass-criterion.  Scoring by RESULT:FAIL would mark every
# row detected, including against unmodified RTL.  So each run is classified
# by WHICH check failed, and G2 below is the positive control on that
# classifier: unmodified RTL, truncated, must come out CLOSURE_ONLY.
#
# Usage:  bash examples/phase6_crv_uart/run_equal_budget_control.sh
# Run from the repo root.

set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

source tools/setup_iverilog.sh > /dev/null 2>&1   # NOT piped -- 2026-09-17
IVL_BIN="${IVERILOG_INSTALL_DIR:-/tmp/iverilog_install}/usr/bin"
IVL_LIB="${IVERILOG_INSTALL_DIR:-/tmp/iverilog_install}/usr/lib/x86_64-linux-gnu/ivl"

WORK="$(mktemp -d /tmp/uart_eqb.XXXXXX)"
TB="examples/phase6_crv_uart/uart_crv_cov_tb.v"
RTL="rtl/uart_controller.v"
SEEDS="1 3 5 7"          # the 2026-10-21 seed set, unchanged on purpose

T3_SED="s/rx_avail, rx_full, tx_empty, tx_full};/rx_avail, rx_full, (tx_cnt <= 4'd1), tx_full};/"

classify () {
    local out="$1"
    if grep -q "RESULT: PASS" <<< "$out"; then echo PASS; return; fi
    if ! grep -q "RESULT: FAIL" <<< "$out"; then echo DIED; return; fi
    if grep "^  FAIL " <<< "$out" \
         | grep -qv "FAIL coverage closure\|FAIL closure counter"; then
        echo DATA
    else
        echo CLOSURE_ONLY
    fi
}
first_data_fail () {
    grep "^  FAIL " <<< "$1" | grep -v "coverage closure\|closure counter" \
        | head -1 | sed 's/^  FAIL //; s/:.*//'
}
run_one () {                        # sim seed steer [maxtx]
    local extra=""; [ $# -ge 4 ] && extra="+maxtx=$4"
    timeout 170 "$IVL_BIN/vvp" -M "$IVL_LIB" "$1" "+seed=$2" "+steer=$3" \
        $extra 2>&1
}
tx_of () { grep -o "transactions driven      : [0-9]*" <<< "$1" \
           | grep -o "[0-9]*$"; }

echo "=============================================================="
echo "EQUAL-BUDGET CONTROL on the 2026-10-21 mode result"
echo "  mutant: T3  STATUS decode: tx_empty one entry EARLY"
echo "  date  : $(date -u +%F)   seeds: $SEEDS"
echo "=============================================================="
echo

"$IVL_BIN/iverilog" -B "$IVL_LIB" -g2012 -o "$WORK/sim_base" "$RTL" "$TB" \
    > "$WORK/c.log" 2>&1 || { echo "BASELINE COMPILE ERROR"; exit 1; }

# G1 -- the mutant must actually change the file, and must still be Verilog.
sed "$T3_SED" "$RTL" > "$WORK/t3.v"
if cmp -s "$RTL" "$WORK/t3.v"; then
    echo "G1  FAIL -- the T3 sed matched nothing.  A no-op injection reports a"
    echo "    perfect escape, which is the most flattering possible failure."
    exit 1
fi
if ! "$IVL_BIN/iverilog" -B "$IVL_LIB" -g2012 -o "$WORK/sim_t3" \
        "$WORK/t3.v" "$TB" > "$WORK/c3.log" 2>&1; then
    echo "G1  FAIL -- T3 does not compile.  A mutant that does not compile has"
    echo "    been tested by nothing; it is an injection failure, not a"
    echo "    detection.  (run_mutation_tests.sh scores COMPILE_ERROR as"
    echo "    DETECT, which is how M7 passed for ten days without running.)"
    head -2 "$WORK/c3.log" | sed 's/^/    /'
    exit 1
fi
echo "G1  T3 changes the RTL and still compiles."
echo

echo "G2  positive control on the classifier: UNMUTATED RTL, truncated to"
echo "    steer=1's budget, must be CLOSURE_ONLY -- never DATA."
declare -A BUDGET
G2_OK=1
for s in $SEEDS; do
    BUDGET[$s]="$(tx_of "$(run_one "$WORK/sim_base" "$s" 1)")"
    ce="$(classify "$(run_one "$WORK/sim_base" "$s" 0 "${BUDGET[$s]}")")"
    printf "    seed %-3s maxtx=%-4s -> %s\n" "$s" "${BUDGET[$s]}" "$ce"
    [ "$ce" = CLOSURE_ONLY ] || G2_OK=0
done
if [ "$G2_OK" -ne 1 ]; then
    echo "    ABORT -- truncation is being scored as detection, so no row below"
    echo "    would mean anything."
    exit 1
fi
echo "    G2 holds."
echo

echo "--------------------------------------------------------------"
printf "%-5s %-7s %-13s %-13s %-14s %s\n" \
       seed budget "A steer=0" "B steer=1" "E equal-budget" "E caught by"
echo "--------------------------------------------------------------"
A=0; B=0; E=0; N=0; FLIPPED=0; AGREE=0
for s in $SEEDS; do
    N=$((N+1))
    oa="$(run_one "$WORK/sim_t3" "$s" 0)"
    ob="$(run_one "$WORK/sim_t3" "$s" 1)"
    oe="$(run_one "$WORK/sim_t3" "$s" 0 "${BUDGET[$s]}")"
    va="$(classify "$oa")"; vb="$(classify "$ob")"; ve="$(classify "$oe")"
    ff="$(first_data_fail "$oe")"
    [ "$va" = DATA ] && A=$((A+1))
    [ "$vb" = DATA ] && B=$((B+1))
    [ "$ve" = DATA ] && E=$((E+1))
    printf "%-5s %-7s %-13s %-13s %-14s %s\n" \
           "$s" "${BUDGET[$s]}" "$va" "$vb" "$ve" "${ff:--}"
    # The seeds that matter are the ones where steering ESCAPED.
    if [ "$vb" = PASS ]; then
        if [ "$ve" = DATA ]; then
            FLIPPED=$((FLIPPED+1))
        else
            AGREE=$((AGREE+1))
        fi
    fi
done
echo "--------------------------------------------------------------"
echo
echo "  detections: A (full steer=0) $A/$N   B (steer=1) $B/$N"
echo "              E (steer=0 at B's budget) $E/$N"
echo
echo "  THE SEEDS THAT DECIDE IT are the ones where steering ESCAPED."
echo "  On those seeds, steer=0 at steer=1's OWN transaction budget:"
echo "      still DETECTED : $FLIPPED"
echo "      also escaped   : $AGREE"
echo
if [ "$FLIPPED" -gt 0 ] && [ "$AGREE" -eq 0 ]; then
  echo "  VERDICT: volume does NOT explain the escapes.  Every seed on which"
  echo "  the coverage-driven mode missed T3 is a seed on which pure random"
  echo "  catches it WITHIN THE SAME NUMBER OF TRANSACTIONS.  The 2026-10-21"
  echo "  conclusion survives the control that could have overturned it, and"
  echo "  its mechanism -- cov_txq has no bin for occupancy 1, so closure is"
  echo "  free to walk away from the burst_len = 1 draws T3 needs -- is the"
  echo "  surviving explanation."
elif [ "$FLIPPED" -eq 0 ] && [ "$AGREE" -gt 0 ]; then
  echo "  VERDICT: volume is SUFFICIENT.  The 2026-10-21 reading is not"
  echo "  supported by its own experiment and the entry should say so."
else
  echo "  VERDICT: MIXED ($FLIPPED detected, $AGREE escaped at equal budget)."
  echo "  Neither explanation is sufficient alone; report per seed."
fi
echo
echo "  NOT CLAIMED: that the aggregate gap is entirely the coverage model."
echo "  At equal budget pure random scores $E/$N rather than $A/$N, so the"
echo "  budget alone can cost a detection on a seed where steering did not"
echo "  escape.  The per-seed reading above is the one that is load-bearing;"
echo "  the aggregate is not."
echo "=============================================================="
rm -rf "$WORK"
