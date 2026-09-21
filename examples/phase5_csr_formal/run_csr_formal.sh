#!/usr/bin/env bash
# examples/phase5_csr_formal/run_csr_formal.sh
#
# Phase 5, second milestone (2026-09-21): formal properties on the UART's
# six-register APB map -- the target 2026-09-20 named as next.
#
# WHY THE CSRs. They are the opposite kind of property from the FIFO
# invariants proved on 2026-09-20. Those were UNBOUNDED claims that needed
# k-induction. These are SHALLOW: every one is decided within two cycles,
# which is what BMC is actually good at, and they cross-check parts of the
# design that no single line of RTL can satisfy by construction -- a write
# port against a read port, a status flag against the FIFO that drives it,
# a clear path against the FSM that sets it.
#
# SEPARATE DEFINE. The CSR block is nested under `ifdef FORMAL_CSR inside
# the existing `ifdef FORMAL. The 2026-09-20 FIFO jobs pass -DFORMAL only,
# so they see exactly the source they saw then and their numbers stay
# reproducible. These jobs pass -DFORMAL -DFORMAL_CSR.
#
# VERDICT DISCIPLINE (2026-09-17, -18, -19, -20 all paid for this rule):
# sby's exit code is never the verdict. This script parses sby's own
# "DONE (...)" line, requires that line to exist, and records the exit code
# beside it. Stage 2 goes one step further and parses the per-cover
# "Reached cover statement in step N" lines, because a cover job returns
# PASS only if EVERY cover was reached -- but which step each was reached
# at is the thing that exposed a real bug in this very suite (below).
#
# Stages:
#   1. REGRESSION GUARD  -- the Phase 4 60-check bench must still be 60/60,
#                           proving the new `ifdef block is invisible to
#                           Icarus. Claimed-and-checked.
#   2. PROOF             -- bmc (depth 20), prove (k-induction), cover.
#   3. MUTATION          -- seven CSR defects injected into COPIES. Each
#                           must make bmc return FAIL.
#   4. CROSS-CHECK       -- re-run the 2026-09-20 FIFO jobs with -DFORMAL
#                           only, to show the CSR block did not disturb
#                           them.
set -u
cd "$(dirname "$0")"
ROOT=$(cd ../.. && pwd)
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
PASS=0; FAIL=0

say() { printf '%s\n' "$*"; }
hdr() { say ""; say "=== $* ==="; }

sby_verdict() { # <sbyfile> <srcfile> <tag> -> PASS/FAIL/UNKNOWN/NOSTATUS
    local cfg=$1 src=$2 tag=$3 out rc
    rm -rf "$WORK/$tag"; mkdir -p "$WORK/$tag/in"
    cp "$src" "$WORK/$tag/in/uart_controller.v"
    sed "s|^\.\./\.\./rtl/uart_controller\.v$|$WORK/$tag/in/uart_controller.v|" "$cfg" \
        > "$WORK/$tag/job.sby"
    out=$(cd "$WORK/$tag" && sby -f job.sby 2>&1); rc=$?
    # exit code and log go to FILES: this function is always called inside
    # $( ), so any variable it sets dies with the subshell (2026-09-20).
    printf '%s' "$rc"  > "$WORK/last_rc"
    printf '%s' "$out" > "$WORK/last_log"
    if   grep -q 'DONE (PASS'    <<<"$out"; then echo PASS
    elif grep -q 'DONE (FAIL'    <<<"$out"; then echo FAIL
    elif grep -q 'DONE (UNKNOWN' <<<"$out"; then echo UNKNOWN
    else echo NOSTATUS; fi
}

check() { # <label> <expected> <actual>
    if [ "$2" = "$3" ]; then say "  PASS  $1 (verdict $3)"; PASS=$((PASS+1))
    else say "  FAIL  $1 (expected $2, got $3)"; FAIL=$((FAIL+1)); fi
}

# ---------------------------------------------------------------- stage 1
hdr "Stage 1: Phase 4 regression guard (the FORMAL_CSR block must be invisible)"
if [ -f "$ROOT/examples/phase4_rtl_bringup/uart_controller_tb.v" ]; then
    ( cd "$ROOT" && source tools/setup_iverilog.sh >/dev/null 2>&1
      iverilog -g2012 -o "$WORK/uart_tb.out" rtl/uart_controller.v \
               examples/phase4_rtl_bringup/uart_controller_tb.v 2>&1 | sed 's/^/  iverilog: /'
      /tmp/iverilog_install/usr/bin/vvp \
          -M /tmp/iverilog_install/usr/lib/x86_64-linux-gnu/ivl \
          "$WORK/uart_tb.out" ) > "$WORK/regress.log" 2>&1
    line=$(grep -E '^=== SUMMARY:' "$WORK/regress.log" | tail -1)
    say "  regression reports: ${line:-<no SUMMARY line found>}"
    case "$line" in
        *"60 passed, 0 failed"*) say "  PASS  Phase 4 regression still 60/60"; PASS=$((PASS+1));;
        *) say "  FAIL  Phase 4 regression did not report 60 passed / 0 failed"; FAIL=$((FAIL+1));
           tail -20 "$WORK/regress.log" | sed 's/^/     /';;
    esac
else
    say "  SKIP  examples/phase4_rtl_bringup/uart_controller_tb.v not found"
fi

# ---------------------------------------------------------------- stage 2
hdr "Stage 2: CSR proof on the real RTL"
for job in bmc prove cover; do
    v=$(sby_verdict "uart_csr_$job.sby" "$ROOT/rtl/uart_controller.v" "real_$job")
    check "uart_csr_$job" PASS "$v"
    say "        sby exit code was $(cat "$WORK/last_rc") (recorded, NOT the verdict)"
    if [ "$job" = cover ]; then
        say "        covers, and the step each was reached at:"
        grep -oE 'Reached cover statement in step [0-9]+ at uart_controller: uart_controller\.v:[0-9]+' \
            "$WORK/last_log" | sed 's/.*step \([0-9]*\).*v:\([0-9]*\)/          line \2 -> step \1/' | sort -u
        # THE CHECK THAT FOUND A REAL BUG IN THIS SUITE, 2026-09-21.
        # A cover reached at step < 2 is reached BEFORE the synchronous
        # reset has taken effect, which means $past() inside it read a
        # pre-reset value the design had already discarded. A cover that
        # fires on garbage certifies nothing -- and the cover whose job was
        # to show C6 is not vacuous did exactly that until it was fixed.
        early=$(grep -oE 'Reached cover statement in step [0-9]+' "$WORK/last_log" \
                | awk '{print $NF}' | sort -n | head -1)
        if [ -n "${early:-}" ] && [ "$early" -lt 2 ]; then
            say "  FAIL  a cover was reached at step $early, before reset took effect"
            FAIL=$((FAIL+1))
        else
            say "  PASS  no cover reached before step 2 (earliest was $early)"
            PASS=$((PASS+1))
        fi
    fi
done

# ---------------------------------------------------------------- stage 3
hdr "Stage 3: mutation -- seven CSR defects, each must be DETECTED by bmc"
say "  Detection = bmc returns FAIL, i.e. the solver exhibits a reachable"
say "  counterexample trace. A surviving mutant means the suite does not"
say "  constrain that behaviour, whatever the proof said."
mutate() { # <name> <sed-expr> <description>
    local name=$1 expr=$2 desc=$3
    local f="$WORK/mut_$name.v"
    sed "$expr" "$ROOT/rtl/uart_controller.v" > "$f"
    if cmp -s "$f" "$ROOT/rtl/uart_controller.v"; then
        say "  FAIL  $name: sed matched nothing, mutant identical to original"
        FAIL=$((FAIL+1)); return
    fi
    local vb
    vb=$(sby_verdict uart_csr_bmc.sby "$f" "mut_$name")
    check "$name -- $desc" FAIL "$vb"
    if [ "$vb" = FAIL ]; then
        grep -oE 'Assert failed in uart_controller: uart_controller\.v:[0-9]+' "$WORK/last_log" \
            | sed 's/.*v:/          first failing property at line /' | head -2
    fi
}

mutate N1 's|                ADDR_CTRL:     ctrl     <= pwdata\[4:0\];|                ADDR_CTRL:     ctrl     <= pwdata[4:0];\n                ADDR_STATUS:   ctrl     <= pwdata[4:0];|' \
    "write decode aliases CTRL onto the STATUS address (C2)"
mutate N2 's|            ADDR_CTRL:     prdata = {3.b000, ctrl};|            ADDR_CTRL:     prdata = {3'"'"'b111, ctrl};|' \
    "CTRL reserved bits read as 1 (C3)"
mutate N3 's|            default:       prdata = 8.h00;|            default:       prdata = 8'"'"'hFF;|' \
    "unmapped and write-only addresses read 0xFF (C4)"
mutate N4 's|    wire \[7:0\] status_val = {1.b0, overrun_err, parity_err, frame_err,|    wire [7:0] status_val = {1'"'"'b0, overrun_err, parity_err, frame_err,\n                             rx_avail, rx_full, tx_full, tx_empty}; // MUTANT\n    wire [7:0] status_unused = {1'"'"'b0, overrun_err, parity_err, frame_err,|' \
    "STATUS tx_full/tx_empty bits swapped (C5)"
mutate N6 's|    wire rx_pop  = rd_en \& (paddr == ADDR_RX_DATA) \& rx_avail;|    wire rx_pop  = rd_en \& (paddr == ADDR_RX_DATA);|' \
    "RX_DATA read pops an empty FIFO (C8)"
mutate N7 's|    assign irq = (tx_empty \& int_en\[0\])|    assign irq = (tx_empty)|' \
    "TX-empty interrupt ignores its mask bit (C9)"

# --------------------------------------------------------------- stage 3b
hdr "Stage 3b: a mutant that this suite provably CANNOT catch at this depth"
say "  N5 disables the STATUS read-to-clear path entirely, the defect C6"
say "  exists to catch. It is expected to SURVIVE, and that expectation is"
say "  asserted rather than hoped for."
say ""
say "  Why: after reset the three sticky error bits are 0, and the ONLY way"
say "  to set one is for the RX engine to complete a serial frame -- a start"
say "  bit plus eight data bits plus a stop bit at sixteen oversample ticks"
say "  each, ~145 clocks at the fastest legal baud. bmc runs to depth 20."
say "  C6's antecedent is therefore never satisfiable in the bounded window,"
say "  so C6 is VACUOUSLY TRUE here and no mutation of the clear path can"
say "  break it. The same holds for C7."
say ""
say "  This is the honest form of the statement 'C6 is proved': it is proved"
say "  only over traces the solver can reach, and it is measured here that"
say "  those traces do not include the interesting one. uart_csr_deep_cover.sby"
say "  is the attempt to reach it; see README.md for what that cost."
n5="$WORK/mut_N5.v"
sed 's|            if (rd_en \&\& (paddr == ADDR_STATUS)) begin|            if (1'"'"'b0 \&\& rd_en \&\& (paddr == ADDR_STATUS)) begin|' \
    "$ROOT/rtl/uart_controller.v" > "$n5"
if cmp -s "$n5" "$ROOT/rtl/uart_controller.v"; then
    say "  FAIL  N5: sed matched nothing, mutant identical to original"
    FAIL=$((FAIL+1))
else
    v=$(sby_verdict uart_csr_bmc.sby "$n5" "mut_N5")
    if [ "$v" = PASS ]; then
        say "  PASS  N5 survived, as predicted -- the depth limit is real and measured"
        PASS=$((PASS+1))
    else
        say "  FAIL  N5 returned $v: it was expected to survive at depth 20."
        say "        If bmc genuinely found a counterexample, the reasoning above"
        say "        is wrong and the trace should be read before anything else."
        FAIL=$((FAIL+1))
    fi
fi

# ---------------------------------------------------------------- stage 4
hdr "Stage 4: the 2026-09-20 FIFO jobs must be undisturbed"
say "  Run with -DFORMAL only, i.e. without FORMAL_CSR, so they see exactly"
say "  the source they saw on 2026-09-20."
for job in bmc prove cover; do
    if [ -f "../phase5_formal_uart/uart_fifo_$job.sby" ]; then
        v=$(sby_verdict "../phase5_formal_uart/uart_fifo_$job.sby" \
                        "$ROOT/rtl/uart_controller.v" "fifo_$job")
        check "uart_fifo_$job (2026-09-20 suite)" PASS "$v"
    fi
done

hdr "SUMMARY"
say "  $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
