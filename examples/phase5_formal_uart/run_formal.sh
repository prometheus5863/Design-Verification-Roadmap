#!/usr/bin/env bash
# examples/phase5_formal_uart/run_formal.sh
#
# Phase 5 milestone runner. Four stages, in order:
#
#   1. REGRESSION GUARD. Re-run the Phase 4 60-check regression and require
#      60/60, proving the `ifdef FORMAL block added to rtl/uart_controller.v
#      is invisible to Icarus. Claimed-and-checked, not claimed.
#   2. PROOF. bmc (depth 24), prove (k-induction) and cover on the real RTL.
#      cover is not optional: a property suite that passes on a design which
#      can never fill its FIFO proves nothing, so the solver is made to
#      EXHIBIT a full FIFO and a wrapped pointer.
#   3. MUTATION. Five defects injected into COPIES of the RTL. Each must
#      make the proof FAIL. A mutant that survives means the property suite
#      does not constrain that behaviour.
#   4. INVARIANT EXPERIMENT. Re-prove P2 with P1 deleted, to find out
#      whether P2 is inductive on its own or needs P1 as a strengthening
#      invariant. Recorded whichever way it comes out.
#
# VERDICT DISCIPLINE (the rule three sessions in a row have paid for --
# 2026-09-17, 09-18, 09-19): this script NEVER uses sby's exit code as the
# verdict. It parses sby's own "DONE (PASS...)" / "DONE (FAIL...)" line and
# requires that the line exist. Stage 2 below also *measures* whether sby's
# exit code happens to agree, and reports the answer rather than assuming
# it.
set -u
cd "$(dirname "$0")"
ROOT=$(cd ../.. && pwd)
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
PASS=0; FAIL=0

say() { printf '%s\n' "$*"; }
hdr() { say ""; say "=== $* ==="; }

# sby_verdict <sbyfile> <srcfile> -> prints "PASS"/"FAIL"/"NOSTATUS", sets RC
sby_verdict() {
    local cfg=$1 src=$2 tag=$3 out rc
    rm -rf "$WORK/$tag"; mkdir -p "$WORK/$tag/in"
    cp "$src" "$WORK/$tag/in/uart_controller.v"
    sed "s|^\.\./\.\./rtl/uart_controller\.v$|$WORK/$tag/in/uart_controller.v|" "$cfg" \
        > "$WORK/$tag/job.sby"
    out=$(cd "$WORK/$tag" && sby -f job.sby 2>&1); rc=$?
    # RC and the log are written to FILES, not shell variables: sby_verdict
    # is always called inside $( ), so any variable it sets dies with the
    # subshell. That is how a runner ends up silently reporting a stale
    # exit code -- the same verdict-vs-checking shape as 2026-09-17/18/19.
    printf '%s' "$rc" > "$WORK/last_rc"
    printf '%s' "$out" > "$WORK/last_log"
    if   grep -q 'DONE (PASS'  <<<"$out"; then echo PASS
    elif grep -q 'DONE (FAIL'  <<<"$out"; then echo FAIL
    elif grep -q 'DONE (UNKNOWN' <<<"$out"; then echo UNKNOWN
    else echo NOSTATUS; fi
}

check() { # <label> <expected> <actual>
    if [ "$2" = "$3" ]; then say "  PASS  $1 (verdict $3)"; PASS=$((PASS+1))
    else say "  FAIL  $1 (expected $2, got $3)"; FAIL=$((FAIL+1)); fi
}

# ---------------------------------------------------------------- stage 1
hdr "Stage 1: Phase 4 regression guard (the FORMAL block must be invisible)"
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
hdr "Stage 2: proof on the real RTL"
for job in bmc prove cover; do
    v=$(sby_verdict "uart_fifo_$job.sby" "$ROOT/rtl/uart_controller.v" "real_$job")
    check "uart_fifo_$job" PASS "$v"
    say "        sby exit code was $(cat "$WORK/last_rc") (recorded, NOT used as the verdict)"
done

# ---------------------------------------------------------------- stage 3
hdr "Stage 3: mutation -- each defect must be DETECTED, and by the right mode"
say "  A mutant is DETECTED when bmc returns FAIL, i.e. the solver exhibits a"
say "  reachable trace violating a property. The prove verdict is recorded"
say "  alongside but is NOT the detection criterion -- see M1."
mutate() { # <name> <sed-expr> <description>
    local name=$1 expr=$2 desc=$3
    local f="$WORK/mut_$name.v"
    sed "$expr" "$ROOT/rtl/uart_controller.v" > "$f"
    if cmp -s "$f" "$ROOT/rtl/uart_controller.v"; then
        say "  FAIL  $name: sed matched nothing, mutant identical to original"
        FAIL=$((FAIL+1)); return
    fi
    local vb vp
    vb=$(sby_verdict uart_fifo_bmc.sby   "$f" "mutb_$name")
    vp=$(sby_verdict uart_fifo_prove.sby "$f" "mutp_$name")
    check "$name -- $desc" FAIL "$vb"
    say "        prove mode said: $vp"
    if [ "$vp" = "UNKNOWN" ]; then
        say "        ^ NOT a detection. prove mode passed its basecase and"
        say "          FAILED INDUCTION, which means only that the property is"
        say "          not k-inductive for this design -- the induction"
        say "          counterexample starts in a possibly-unreachable state."
        say "          A harness that scored prove-mode UNKNOWN as a kill would"
        say "          be claiming a bug the tool never found."
    fi
}
mutate M1 's|wire tx_push = wr_en \& (paddr == ADDR_TX_DATA) \& ~tx_full;|wire tx_push = wr_en \& (paddr == ADDR_TX_DATA);|' \
    "TX push no longer guarded by ~tx_full (overflow)"
mutate M2 's|wire rx_pop  = rd_en \& (paddr == ADDR_RX_DATA) \& rx_avail;|wire rx_pop  = rd_en \& (paddr == ADDR_RX_DATA);|' \
    "RX pop no longer guarded by rx_avail (underflow)"
mutate M3 's|2.b10: tx_cnt <= tx_cnt + 4.d1;|2'"'"'b10: tx_cnt <= tx_cnt + 4'"'"'d2;|' \
    "TX count increments by 2 per push"
mutate M4 's|if (tx_push) begin tx_fifo\[tx_wptr\] <= pwdata; tx_wptr <= tx_wptr + 3.d1; end|if (tx_push) begin tx_fifo[tx_wptr] <= pwdata; tx_wptr <= tx_wptr + 3'"'"'d2; end|' \
    "TX write pointer advances by 2 (breaks P2 only, P1 untouched)"
mutate M5 's|2.b01: tx_cnt <= tx_cnt - 4.d1;|2'"'"'b01: tx_cnt <= tx_cnt - 4'"'"'d1; 2'"'"'b11: tx_cnt <= tx_cnt - 4'"'"'d1;|' \
    "simultaneous push+pop wrongly decrements the count"

# ---------------------------------------------------------------- stage 4
hdr "Stage 4: is P2 inductive without P1?"
strip="$WORK/no_p1.v"
python3 - "$ROOT/rtl/uart_controller.v" "$strip" <<'PY'
import sys, re
src, dst = sys.argv[1], sys.argv[2]
s = open(src).read()
a = s.index("    // ---- P1:")
b = s.index("    // ---- P2:")
open(dst, "w").write(s[:a] + s[b:])
PY
v=$(sby_verdict uart_fifo_prove.sby "$strip" "no_p1")
say "  P2 alone, k-induction verdict: $v"
if [ "$v" = "PASS" ]; then
    say "  -> P2 is inductive on its own; P1 is not needed as a strengthening"
    say "     invariant. Recorded as measured."
    PASS=$((PASS+1))
else
    say "  -> P2 is NOT inductive alone: induction finds an unreachable state"
    say "     satisfying P2 whose successor violates it, and P1 is the"
    say "     strengthening invariant that rules it out. This is the classic"
    say "     induction-failure / invariant-strengthening result."
    grep -E 'Assert failed|induction|Status' "$WORK/last_log" | tail -6 | sed 's/^/     /'
    PASS=$((PASS+1))
fi

hdr "SUMMARY"
say "  $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
