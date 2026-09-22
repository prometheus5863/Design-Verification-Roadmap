#!/usr/bin/env bash
# examples/phase5_csr_formal/run_reset_formal.sh
#
# Phase 5, day 3 (2026-09-22): RESET-VALUE properties on the UART.
#
# WHY THIS EXISTS. 2026-09-21 proved nine CSR properties and then recorded an
# owed item: the seven reusable CSR obligations include "reads its reset
# value after reset", and that was the one the suite did not check. The
# reason was structural rather than an oversight -- every property in the
# repo is guarded by (f_past_valid && rst_n), i.e. DISABLED during reset,
# which is correct for a steady-state property and fatal for this one.
#
# The fix is the mirror-image guard, (f_past_valid && !$past(rst_n)), and the
# properties live in their own `ifdef FORMAL_CSR_RESET so that the
# 2026-09-20 FIFO jobs (-DFORMAL) and the 2026-09-21 CSR jobs
# (-DFORMAL -DFORMAL_CSR) keep seeing exactly the source they saw then.
#
# VERDICT DISCIPLINE, unchanged since 2026-09-17: sby's exit code is never
# the verdict. This script parses sby's own "DONE (...)" line, requires it
# to exist, and records the exit code beside it. The cover stage additionally
# parses "Reached cover statement in step N" and FAILS any cover reached
# before step 2 -- the standing guard added 2026-09-21 after a cover passed
# by reading pre-reset state through $past().
#
# Stages:
#   1. REGRESSION GUARD -- Phase 4 bench still 60/60 (new block invisible to
#                          Icarus). Claimed-and-checked.
#   2. PROOF            -- reset bmc (depth 12) + reset cover, step-guarded.
#   3. MUTATION         -- six reset defects injected into COPIES; each must
#                          make bmc FAIL.
#   3b. EXPECTED SURVIVAL -- one mutant that MUST SURVIVE, proving the
#                          RX_DATA omission in R2 is deliberate.
#   4. CROSS-CHECK      -- the 2026-09-20 FIFO jobs and the 2026-09-21 CSR
#                          jobs must still pass, unchanged.
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HERE="$ROOT/examples/phase5_csr_formal"
WORK="$(mktemp -d)"
PASS=0; FAIL=0
say() { echo "$@"; }
hdr() { echo; echo "=============================================================="; echo "$@"; echo "=============================================================="; }

command -v sby >/dev/null 2>&1 || { echo "sby not on PATH -- 'source tools/setup_formal.sh' first (do NOT pipe it)"; exit 1; }

# Parse sby's own DONE line. Returns "PASS"/"FAIL"/"NONE".
verdict() {
    local log="$1" d
    d=$(grep -oE 'DONE \([A-Z]+' "$log" | tail -1 | sed 's/DONE (//')
    [ -n "$d" ] && echo "$d" || echo "NONE"
}

run_sby() {   # run_sby <sbyfile> <logfile>
    ( cd "$HERE" && rm -rf "$(basename "$1" .sby)" && sby -f "$1" ) > "$2" 2>&1
    echo $?
}

# ---------------------------------------------------------------- stage 1
hdr "Stage 1: Phase 4 regression guard (FORMAL_CSR_RESET must be invisible)"
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
    say "  SKIP  phase4_rtl_bringup testbench not found"
fi

# ---------------------------------------------------------------- stage 2
hdr "Stage 2: reset-value proof on the real RTL"
rc=$(run_sby uart_reset_bmc.sby "$WORK/rbmc.log"); v=$(verdict "$WORK/rbmc.log")
say "  uart_reset_bmc   : sby DONE=$v  (exit $rc)"
if [ "$v" = "PASS" ]; then say "  PASS  R1-R4 hold to depth 12"; PASS=$((PASS+1));
else say "  FAIL  reset bmc did not pass"; FAIL=$((FAIL+1)); tail -25 "$WORK/rbmc.log" | sed 's/^/     /'; fi

rc=$(run_sby uart_reset_cover.sby "$WORK/rcov.log"); v=$(verdict "$WORK/rcov.log")
say "  uart_reset_cover : sby DONE=$v  (exit $rc)"
if [ "$v" = "PASS" ]; then say "  PASS  every cover reachable"; PASS=$((PASS+1));
else say "  FAIL  cover job did not pass"; FAIL=$((FAIL+1)); fi

# The step guard. A cover reached at step 0 or 1 tells us nothing: the
# environment assumption forces reset at step 0, so !$past(rst_n) is
# satisfiable there for free. Both new covers demand a reset that RETURNS.
say "  cover steps (guard: every cover must be reached at step >= 2):"
bad=0
while read -r ln; do
    st=$(echo "$ln" | sed -n 's/.*step \([0-9]*\)$/\1/p')
    src=$(echo "$ln" | sed -n 's/.*at \(uart_controller\.v:[0-9.-]*\) step.*/\1/p')
    say "    step $st   $src"
    [ -n "$st" ] && [ "$st" -lt 2 ] && bad=$((bad+1))
done < <(grep 'reached cover statement' "$WORK/rcov.log")
if [ "$bad" -eq 0 ]; then say "  PASS  no cover reached before step 2"; PASS=$((PASS+1));
else say "  FAIL  $bad cover(s) reached before step 2 -- see 2026-09-21"; FAIL=$((FAIL+1)); fi

# ---------------------------------------------------------------- stage 3
hdr "Stage 3: mutation -- six reset defects, each must be DETECTED"
mutate() {  # mutate <name> <description> <sed-expr...>
    local name="$1" desc="$2"; shift 2
    local dir="$WORK/mut_$name"; mkdir -p "$dir"
    cp "$ROOT/rtl/uart_controller.v" "$dir/uart_controller.v"
    for e in "$@"; do sed -i "$e" "$dir/uart_controller.v"; done
    if cmp -s "$dir/uart_controller.v" "$ROOT/rtl/uart_controller.v"; then
        say "  $name  FAIL  sed matched nothing -- the mutant is identical to the RTL"
        FAIL=$((FAIL+1)); return
    fi
    sed 's#\.\./\.\./rtl/uart_controller.v#uart_controller.v#' \
        "$HERE/uart_reset_bmc.sby" > "$dir/m.sby"
    ( cd "$dir" && sby -f m.sby ) > "$dir/log" 2>&1
    local v; v=$(verdict "$dir/log")
    if [ "$v" = "FAIL" ]; then say "  $name  DETECTED   ($desc)"; PASS=$((PASS+1));
    else say "  $name  MISSED [$v]  ($desc)  <-- the suite does not cover this"; FAIL=$((FAIL+1)); fi
}

mutate M1 "CTRL not cleared by reset"            "356s/ctrl <= 5'd0;/ctrl <= ctrl;/"
mutate M2 "TX line idles LOW out of reset"       "151s/tx_line <= 1'b1;/tx_line <= 1'b0;/"
mutate M3 "a concurrent bus write beats reset"   "355s/if (!rst_n) begin/if (!rst_n \&\& !wr_en) begin/"
mutate M4 "TX FIFO count resets to 1, so STATUS.tx_empty is wrong" \
                                                 "325s/tx_cnt <= 4'd0;/tx_cnt <= 4'd1;/"
mutate M5 "frame_err sticky bit resets SET"      "243s/frame_err <= 1'b0;/frame_err <= 1'b1;/"
mutate M6 "irq ignores its enable mask (R3 only; R1/R2 untouched)" \
                                                 "390s/(tx_empty \& int_en\[0\])/(tx_empty)/"

# --------------------------------------------------------------- stage 3b
hdr "Stage 3b: one mutant that MUST SURVIVE"
say "  R2 deliberately does not assert a reset value for ADDR_RX_DATA: it"
say "  reads rx_fifo[rx_rptr], and the FIFO array has no reset clause. That"
say "  is a real design decision (8 bytes of storage are unreadable through"
say "  the protocol while rx_cnt == 0), so asserting a value would assert"
say "  something false. M7 corrupts exactly that storage at reset. If M7 is"
say "  DETECTED, the omission is not what this comment claims it is."
dir="$WORK/mut_M7"; mkdir -p "$dir"
cp "$ROOT/rtl/uart_controller.v" "$dir/uart_controller.v"
sed -i "339s/rx_wptr <= 3'd0;/rx_fifo[0] <= 8'hA5; rx_wptr <= 3'd0;/" "$dir/uart_controller.v"
if cmp -s "$dir/uart_controller.v" "$ROOT/rtl/uart_controller.v"; then
    say "  M7  FAIL  sed matched nothing"; FAIL=$((FAIL+1))
else
    sed 's#\.\./\.\./rtl/uart_controller.v#uart_controller.v#' \
        "$HERE/uart_reset_bmc.sby" > "$dir/m.sby"
    ( cd "$dir" && sby -f m.sby ) > "$dir/log" 2>&1
    v=$(verdict "$dir/log")
    if [ "$v" = "PASS" ]; then
        say "  M7  SURVIVED as required  (RX_DATA reset value is out of scope, by design)"
        PASS=$((PASS+1))
    else
        say "  M7  DETECTED [$v] -- UNEXPECTED. Either R2 asserts more than it"
        say "      documents, or the FIFO does have a reset path. Investigate."
        FAIL=$((FAIL+1))
    fi
fi

# ---------------------------------------------------------------- stage 4
hdr "Stage 4: cross-check -- the earlier suites must be undisturbed"
for job in uart_fifo_prove uart_csr_bmc uart_csr_prove uart_csr_cover; do
    f="$HERE/$job.sby"; [ -f "$f" ] || f="$ROOT/examples/phase5_formal_uart/$job.sby"
    if [ ! -f "$f" ]; then say "  SKIP  $job.sby not found"; continue; fi
    d="$(dirname "$f")"
    ( cd "$d" && rm -rf "$job" && sby -f "$job.sby" ) > "$WORK/$job.log" 2>&1
    v=$(verdict "$WORK/$job.log")
    if [ "$v" = "PASS" ]; then say "  PASS  $job still passes"; PASS=$((PASS+1));
    else say "  FAIL  $job now reports $v"; FAIL=$((FAIL+1)); fi
done

# ---------------------------------------------------------------- stage 5
hdr "Stage 5: is every property doing work? (property-redundancy check)"
# 2026-09-21 listed three ways a passing property can mean nothing. This
# stage tests for a FOURTH, which none of those three catches: a property
# that is well-formed, non-vacuous (its cover is reached at step 4) and
# genuinely about the design -- and yet SUBSUMED by another property, so
# that deleting it changes no verdict anywhere in the suite.
#
# Method: build a variant of the RTL with R4 removed and a variant with only
# R4 kept, run M3 (the defect R4 was written for) against each, and compare.
# If both detect M3, R4 earns nothing.
rv="$WORK/redund"; mkdir -p "$rv"
python3 - "$ROOT/rtl/uart_controller.v" "$rv" <<'PYEOF2'
import sys, os
src = open(sys.argv[1]).read(); out = sys.argv[2]
i = src.find('    // ---- R4: reset DOMINATES a concurrent bus write')
j = src.find('    // ---- COVERS: R1-R4 are not vacuous')
a = src.find('    // ---- R1: architectural state is at its reset value')
if min(i, j, a) < 0:
    sys.exit("marker not found -- R1/R4 comment banners changed")
for name, txt in (('noR4', src[:i] + src[j:]), ('onlyR4', src[:a] + src[i:])):
    os.makedirs(os.path.join(out, name), exist_ok=True)
    open(os.path.join(out, name, 'uart_controller.v'), 'w').write(txt)
PYEOF2
if [ -d "$rv/noR4" ]; then
  for v in noR4 onlyR4; do
    sed 's#\.\./\.\./rtl/uart_controller.v#uart_controller.v#' \
        "$HERE/uart_reset_bmc.sby" > "$rv/$v/m.sby"
    cp -r "$rv/$v" "$rv/${v}_M3"
    sed -i "355s/if (!rst_n) begin/if (!rst_n \&\& !wr_en) begin/" "$rv/${v}_M3/uart_controller.v"
    ( cd "$rv/$v"      && sby -f m.sby ) > "$rv/$v.log" 2>&1
    ( cd "$rv/${v}_M3" && sby -f m.sby ) > "$rv/${v}_M3.log" 2>&1
    say "    $v: clean=$(verdict "$rv/$v.log")  with-M3=$(verdict "$rv/${v}_M3.log")"
  done
  if [ "$(verdict "$rv/noR4_M3.log")" = "FAIL" ] && [ "$(verdict "$rv/onlyR4_M3.log")" = "FAIL" ]; then
    say "  MEASURED: R4 is REDUNDANT. R1 alone detects M3, because R1 asserts"
    say "  the reset values unconditionally and so already covers the case"
    say "  where a write is concurrent. R4 is kept and ANNOTATED rather than"
    say "  deleted: it states an intent (reset priority) that R1 only implies,"
    say "  and it would earn its place the moment R1 were narrowed to a quiet"
    say "  bus. This is reported as a finding, not counted as a pass."
  else
    say "  MEASURED: R4 is NOT redundant -- one variant missed M3. Good."
    PASS=$((PASS+1))
  fi
else
  say "  SKIP  could not build the redundancy variants"
fi

hdr "SUMMARY"
say "  checks passed : $PASS"
say "  checks failed : $FAIL"
rm -rf "$WORK"
[ "$FAIL" -eq 0 ] || exit 1
