#!/usr/bin/env bash
# examples/phase6_crv_uart/run_mutation_tests.sh
#
# Mutation-tests the constrained-random / coverage-driven UART suite.
#
# Every mutant is injected into a COPY of rtl/uart_controller.v under
# /tmp; the repo's RTL is never modified. A mutant is DETECTED when the
# suite prints "RESULT: FAIL" (or dies) and ESCAPED when it still prints
# "RESULT: PASS".
#
# This exists because on 2026-09-17 a testbench in this repo passed 55/55
# against deliberately broken RTL. A suite that has not been mutation-tested
# has an unmeasured verdict.
#
# Escapes are reported WITH THEIR REASON rather than treated as a score to
# be maximised: an escape whose cause is understood is a statement about the
# suite's reach, and two of the escapes below are the most useful output of
# this script.
#
# REPAIRED 2026-10-24.  This script was the last of the four mutation runners
# in this repository still defective on both questions the 2026-10-23
# compile-error audit asks.  Three faults, all now fixed and all now carrying
# a control:
#
#   (i)  It scored COMPILE_ERROR as DETECT.  A mutant that does not compile
#        has not been tested by anything, so that turned a malformed
#        injection into a reported success FOR THE SUITE.  Compile failure is
#        now a third outcome, BADINJ, which is never a detection and never a
#        pass -- the vocabulary run_mutation_tests_bimodal.sh already uses.
#   (ii) Its committed M7 sed emitted the literal text 4\x27d7 -- a double
#        backslash inside single quotes, where every other row has one -- so
#        M7 has NEVER been injected.  Every "M7: predicted DETECT, got
#        DETECT" this script has ever printed was fault (i) reading fault
#        (ii).  The escaping is fixed and M7's verdict is now measured.
#   (iii) The run exited 0 regardless.  It now exits non-zero if any
#        injection failed, which is the half the 2026-10-23 session found
#        missing from its OWN new runner as well.
#
# M4's stated reason was replaced: it was measured false on 2026-10-22.
#
# Two preflight controls were added beside the baseline, because the audit
# that found (i) had no positive control of its own:
#
#   G2  a COMMENT-ONLY edit must compile and must ESCAPE.  A runner that
#       cried detect on a neutral change would be useless, and nothing here
#       had ever checked that.  (The standing "cosmetic-edit positive
#       control in every runner that compares transcripts" item, 2026-10-13.)
#   G3  a deliberately NON-COMPILING edit must be classified BADINJ.  This is
#       the positive control for fault (i): it fails loudly if the repair is
#       ever undone.
#
# Usage:  bash examples/phase6_crv_uart/run_mutation_tests.sh
# Run from the repo root.

set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

# shellcheck disable=SC1091
source tools/setup_iverilog.sh > /dev/null 2>&1
IVL_BIN="${IVERILOG_INSTALL_DIR:-/tmp/iverilog_install}/usr/bin"
IVL_LIB="${IVERILOG_INSTALL_DIR:-/tmp/iverilog_install}/usr/lib/x86_64-linux-gnu/ivl"

WORK="$(mktemp -d /tmp/uart_mut.XXXXXX)"
TB="examples/phase6_crv_uart/uart_crv_cov_tb.v"
RTL="rtl/uart_controller.v"
SEEDS="1 3 5"

# Three outcomes, not two.  BADINJ is returned when the mutant does not
# compile and is scored as NEITHER a detection nor a pass.
run_suite () {                      # $1 = rtl file
    local rtl="$1" out rc=0
    "$IVL_BIN/iverilog" -B "$IVL_LIB" -g2012 -o "$WORK/sim" "$rtl" "$TB" \
        > "$WORK/compile.log" 2>&1 || { echo "BADINJ"; return; }
    for s in $SEEDS; do
        out="$(timeout 170 "$IVL_BIN/vvp" -M "$IVL_LIB" "$WORK/sim" \
               "+seed=$s" "+steer=1" 2>&1)" || rc=1
        if ! grep -q "RESULT: PASS" <<< "$out"; then echo "FAIL"; return; fi
    done
    echo "PASS"
}

echo "=============================================================="
echo "MUTATION TEST -- examples/phase6_crv_uart/uart_crv_cov_tb.v"
echo "date: $(date -u +%F)   seeds: $SEEDS   mode: steer=1"
echo "=============================================================="
echo

echo "G1  baseline: the suite must PASS on the unmodified RTL"
BASE="$(run_suite "$RTL")"
echo "    baseline verdict: $BASE"
if [ "$BASE" != "PASS" ]; then
    echo "    ABORT -- a baseline that does not pass makes every mutant row meaningless."
    exit 1
fi
echo

echo "G2  neutrality control: a COMMENT-ONLY edit must compile and ESCAPE"
cp "$RTL" "$WORK/neutral.v"
printf '\n// G2 cosmetic-edit control, injected by run_mutation_tests.sh\n' \
    >> "$WORK/neutral.v"
if cmp -s "$RTL" "$WORK/neutral.v"; then
    echo "    ABORT -- the neutral control did not change the file, so it"
    echo "    controls nothing."
    exit 1
fi
NEUTRAL="$(run_suite "$WORK/neutral.v")"
echo "    neutral verdict: $NEUTRAL"
if [ "$NEUTRAL" != "PASS" ]; then
    echo "    ABORT -- a comment-only edit was not an escape. Every DETECT"
    echo "    below would then be unattributable: this runner cries defect on"
    echo "    a change that cannot alter behaviour."
    exit 1
fi
echo

echo "G3  injection-failure control: a NON-COMPILING edit must score BADINJ"
cp "$RTL" "$WORK/broken.v"
printf '\nthis is not verilog and must not compile\n' >> "$WORK/broken.v"
BROKEN="$(run_suite "$WORK/broken.v")"
echo "    non-compiling verdict: $BROKEN"
if [ "$BROKEN" != "BADINJ" ]; then
    echo "    ABORT -- a mutant that does not compile was classified"
    echo "    '$BROKEN'. Until 2026-10-24 this script called it DETECT, which"
    echo "    is how its M7 row scored as a detection for twelve days without"
    echo "    M7 ever having been injected."
    exit 1
fi
echo "    (positive control for the 2026-10-24 repair -- fails loudly if the"
echo "    COMPILE_ERROR-as-DETECT scoring is ever restored)"
echo

# name | sed expression | expectation | why
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
  's/frame_err <= 1.b0; parity_err <= 1.b0; overrun_err <= 1.b0;\n            end\n\n            if (!cfg_en)/XXX/'
  's/wire tx_full  = (tx_cnt == 4.d8);/wire tx_full  = (tx_cnt >= 4\x27d7);/'
)
MUT_EXPECT=(
  "DETECT"
  "DETECT"
  "DETECT"
  "DETECT"
  "ESCAPE"
  "ESCAPE"
  "DETECT"
)
MUT_WHY=(
  "the RX parity check must disagree and set STATUS.parity_err, which every status read asserts is clear"
  "every received byte must mismatch the reference model"
  "a two-stop-bit frame becomes one bit short, so the next frame's start bit lands inside the previous frame's stop window"
  "CORRECTED 2026-10-24. The committed reason said 'caught by the coverage criterion, not by any data check'; classifying by FIRST FAILING CHECK on 2026-10-22 showed three data checks fire first -- post-push tx_empty, post-push tx_full, the burst watchdog -- and closure does fail but is not the catching mechanism. M4 was this repository's only worked example of a coverage-caught mutant, so NO mutant in this suite is detected by the coverage criterion alone, and 'coverage closure is a pass criterion, not a report line' is unevidenced rather than wrong"
  "PREDICTED ESCAPE: in loopback the TX and RX engines share one baud generator, so a wrong divisor desynchronises nothing. A loopback bench is structurally blind to baud-rate errors"
  "PREDICTED ESCAPE: no error is ever injected in a clean loopback burst, so a bit that fails to CLEAR is never observed set in the first place"
  "added 2026-10-12 by the DUT-signal census. It ESCAPED this suite on all three seeds before that day's repair -- the driver read tx_full to decide whether its own push was accepted, so an early tx_full corrupted the DUT's gating and the reference model identically. Now DETECTED by the predicted-occupancy check, which names the occupancy. ANNOTATED 2026-10-24: this row was never actually injected here until today -- the sed emitted literal 4\\x27d7 and the resulting compile error was scored as a detection -- so every 'got DETECT' this runner printed for M7 between 2026-10-12 and 2026-10-23 was one fault reading another. Injected correctly it IS detected on all three seeds, agreeing with the bimodal runner's 5/5 in both modes. The conclusion was right; the evidence for it did not exist"
)

DETECTED=0; ESCAPED=0; AS_PREDICTED=0; SURPRISES=0; BADINJ=0
for idx in "${!MUT_NAMES[@]}"; do
    cp "$RTL" "$WORK/mut.v"
    if [ "$idx" -eq 5 ]; then
        # M6 spans lines; do it with python rather than a fragile multiline sed
        python3 - "$WORK/mut.v" <<'PYEOF'
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
        [ $? -ne 0 ] && { echo "  ${MUT_NAMES[$idx]}"; echo "    INJECTION FAILED"; continue; }
    else
        sed -i "${MUT_SEDS[$idx]}" "$WORK/mut.v"
        if cmp -s "$RTL" "$WORK/mut.v"; then
            echo "  ${MUT_NAMES[$idx]}"
            echo "    INJECTION FAILED -- the sed matched nothing, so this row would"
            echo "    otherwise have scored as an escape against UNMODIFIED RTL."
            SURPRISES=$((SURPRISES+1))
            continue
        fi
    fi

    V="$(run_suite "$WORK/mut.v")"
    if [ "$V" = "BADINJ" ]; then
        # NEVER a detection and never a pass.  `cmp -s` above catches a sed
        # that matched NOTHING; it cannot catch a sed that matched and
        # emitted garbage, which is exactly what M7's did.  The complete
        # guard is both: the file must change AND still be Verilog.
        echo "  ${MUT_NAMES[$idx]}"
        echo "    *** INJECTION FAILED -- DOES NOT COMPILE (not a detection) ***"
        head -2 "$WORK/compile.log" | sed 's/^/        /'
        BADINJ=$((BADINJ+1))
        SURPRISES=$((SURPRISES+1))
        echo
        continue
    fi
    if [ "$V" = "FAIL" ]; then
        GOT="DETECT"; DETECTED=$((DETECTED+1))
    else
        GOT="ESCAPE"; ESCAPED=$((ESCAPED+1))
    fi
    if [ "$GOT" = "${MUT_EXPECT[$idx]}" ]; then
        AS_PREDICTED=$((AS_PREDICTED+1)); MARK="as predicted"
    else
        SURPRISES=$((SURPRISES+1));       MARK="*** NOT AS PREDICTED ***"
    fi
    echo "  ${MUT_NAMES[$idx]}"
    echo "    predicted ${MUT_EXPECT[$idx]}, got $GOT   ($MARK)"
    echo "    why: ${MUT_WHY[$idx]}"
    echo
done

echo "=============================================================="
echo "  mutants injected      : ${#MUT_NAMES[@]}"
echo "  detected              : $DETECTED"
echo "  escaped               : $ESCAPED"
echo "  verdict as predicted  : $AS_PREDICTED / ${#MUT_NAMES[@]}"
echo "  injections that failed: $BADINJ   (never scored as detections)"
echo "  surprises             : $SURPRISES"
echo
echo "  A predicted escape is a measured statement about the suite's reach."
echo "  M5 is the important one: loopback shares one baud generator between"
echo "  TX and RX, so no loopback bench of any sophistication can detect a"
echo "  baud-rate error. That is an argument for the standalone RX bit-driver"
echo "  the Phase 4 milestone still has open, not for more stimulus here."
echo "=============================================================="
rm -rf "$WORK"

# The exit path, which is the second half of the 2026-10-23 audit's question.
# BADINJ is counted into SURPRISES as well, so an injection failure cannot
# leave this script green even if a future edit drops this block.
if [ "$BADINJ" -ne 0 ]; then
    echo
    echo "RESULT: FAIL  ($BADINJ injection(s) did not compile -- those mutants"
    echo "              were never tested, so this run measures nothing about"
    echo "              them.  A compile error is an injection failure, never"
    echo "              a detection and never a pass.)"
    exit 1
fi
if [ "$SURPRISES" -ne 0 ]; then
    echo
    echo "RESULT: FAIL  ($SURPRISES row(s) did not match the stated prediction.)"
    exit 1
fi
echo
echo "RESULT: PASS  (every injection compiled, G2 and G3 green, and every"
echo "              row matched its stated prediction)"
