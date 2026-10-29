#!/usr/bin/env bash
# examples/phase6_protocol_checker/mutate.sh
#
# MUTATION TEST FOR THE PROTOCOL CHECKER.
#
# A green self-checking suite proves nothing about detection power -- the
# 2026-09-17 session found a testbench that passed 55/55 against deliberately
# broken RTL.  This script injects defects into a COPY of rtl/uart_controller.v
# (never the tree's copy), rebuilds, and requires THE CHECKER to fire, naming
# which rule caught each defect.
#
# The distinction that matters here: the testbench has its own self-checks, so
# a defect could be caught by the TB and not by the checker, which would prove
# nothing about the checker.  Every mutant below is therefore scored on the
# CHECKER_VIOLATIONS line alone.  A mutant that only the TB catches is reported
# as CHECKER-MISS, honestly, rather than counted as a kill.
#
# Usage:  source ../../tools/setup_iverilog.sh   (NOT piped -- it defines
#         shell functions, and piping runs it in a subshell where they vanish)
#         bash examples/phase6_protocol_checker/mutate.sh
set -u

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
WORK="${TMPDIR:-/tmp}/pchk_mut.$$"
IVL_BIN=/tmp/iverilog_install/usr/bin
IVL_LIB=/tmp/iverilog_install/usr/lib/x86_64-linux-gnu/ivl
mkdir -p "$WORK"

CHK="$REPO/checkers/uart_protocol_checker.v"
TB="$REPO/examples/phase6_protocol_checker/uart_protocol_checker_tb.v"
RTL="$REPO/rtl/uart_controller.v"

# name|expected rule|sed expression
MUTANTS=(
"M1 pready tied low|A1|s/assign pready = 1'b1;/assign pready = 1'b0;/"
"M2 TX parity inverted|T3|s/(cfg_parity == PARITY_EVEN) ?  \^tx_fifo\[tx_rptr\]/(cfg_parity == PARITY_EVEN) ? ~^tx_fifo[tx_rptr]/"
"M3 first stop bit driven low|T4|s/if (tx_bit_done) tx_state <= cfg_two_stop ? TX_STOP2 : TX_IDLE;/if (tx_bit_done) tx_state <= cfg_two_stop ? TX_STOP2 : TX_IDLE; else tx_line <= 1'b0;/"
"M4 unmapped read returns 0xFF|A4|s/default:       prdata = 8'h00;/default:       prdata = 8'hFF;/"
"M5 baud reload off by one|T6|s/baud_cnt <= baud_div;/baud_cnt <= baud_div + 8'd1;/"
"M6 tx not forced high when disabled|T1|s/tx_state <= TX_IDLE; tx_line <= 1'b1; tx_os <= 4'd0;/tx_state <= TX_IDLE; tx_os <= 4'd0;/"
)

printf 'MUTATION TEST -- protocol checker detection power\n'
printf 'date: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf '%s\n' '--------------------------------------------------------------------'

# baseline: unmutated RTL must give zero checker violations
"$IVL_BIN/iverilog" -B "$IVL_LIB" -g2005 -o "$WORK/base.vvp" \
    -s uart_protocol_checker_tb "$RTL" "$CHK" "$TB" 2>"$WORK/base.cerr"
if [ -s "$WORK/base.cerr" ]; then
    printf 'BASELINE COMPILE ERRORS:\n'; cat "$WORK/base.cerr"
fi
( cd "$WORK" && "$IVL_BIN/vvp" -M "$IVL_LIB" "$WORK/base.vvp" > "$WORK/base.log" 2>&1 )
BASE_V=$(grep -o 'CHECKER_VIOLATIONS=[0-9]*' "$WORK/base.log" | tail -1 | cut -d= -f2)
BASE_R=$(grep -o 'RESULT=[A-Z]*' "$WORK/base.log" | tail -1 | cut -d= -f2)
printf 'baseline (unmutated): RESULT=%s  CHECKER_VIOLATIONS=%s\n' "${BASE_R:-?}" "${BASE_V:-?}"
printf '%s\n' '--------------------------------------------------------------------'

KILLED=0; MISSED=0; NOTAPPLIED=0
for entry in "${MUTANTS[@]}"; do
    NAME="${entry%%|*}"
    REST="${entry#*|}"
    RULE="${REST%%|*}"
    EXPR="${REST#*|}"

    MUT="$WORK/mut_uart.v"
    sed "$EXPR" "$RTL" > "$MUT"
    if cmp -s "$MUT" "$RTL"; then
        printf '%-38s %-4s NOT-APPLIED (sed anchor did not match)\n' "$NAME" "$RULE"
        NOTAPPLIED=$((NOTAPPLIED+1))
        continue
    fi

    "$IVL_BIN/iverilog" -B "$IVL_LIB" -g2005 -o "$WORK/mut.vvp" \
        -s uart_protocol_checker_tb "$MUT" "$CHK" "$TB" 2>"$WORK/mut.cerr"
    if [ ! -f "$WORK/mut.vvp" ]; then
        printf '%-38s %-4s NOT-APPLIED (mutant does not compile)\n' "$NAME" "$RULE"
        NOTAPPLIED=$((NOTAPPLIED+1))
        continue
    fi
    ( cd "$WORK" && timeout 160 "$IVL_BIN/vvp" -M "$IVL_LIB" "$WORK/mut.vvp" \
        > "$WORK/mut.log" 2>&1 )
    V=$(grep -o 'CHECKER_VIOLATIONS=[0-9]*' "$WORK/mut.log" | tail -1 | cut -d= -f2)
    V="${V:-0}"
    # which rules fired, by number, from the violation lines
    RULES_FIRED=$(grep -o 'rule [0-9]*:\|rule I1:' "$WORK/mut.log" \
                   | tr -d ':' | sort -u | tr '\n' ' ')
    TBF=$(grep -c '  FAIL ' "$WORK/mut.log")
    if [ "$V" -gt 0 ]; then
        printf '%-38s %-4s KILLED   checker=%-4s tb_fails=%-3s fired: %s\n' \
            "$NAME" "$RULE" "$V" "$TBF" "$RULES_FIRED"
        KILLED=$((KILLED+1))
    else
        printf '%-38s %-4s CHECKER-MISS  checker=0  tb_fails=%s\n' \
            "$NAME" "$RULE" "$TBF"
        MISSED=$((MISSED+1))
    fi
    rm -f "$WORK/mut.vvp"
done

printf '%s\n' '--------------------------------------------------------------------'
printf 'mutants killed BY THE CHECKER: %d   checker-missed: %d   not applied: %d\n' \
    "$KILLED" "$MISSED" "$NOTAPPLIED"
printf 'NOTE: rules 1 (A2) and 4 (A5) appear in EVERY row because the testbench\n'
printf 'ends with a planted control that fires them on purpose, to show they can\n'
printf 'fire at all -- they are unexercisable by legal stimulus against a DUT with\n'
printf 'pready tied high.  That control runs AFTER the counted total is taken, so\n'
printf 'it does not contribute to the checker= column; it only shows up in fired:.\n'
printf 'rule numbers in the fired column map to the table in\n'
printf 'checkers/uart_protocol_checker.v rule_name(): 0=A1 1=A2 2=A3 3=A4 4=A5\n'
printf '5=R1 6=R2 7=T1 8=T2 9=T3 10=T4 11=T5 12=T6 13=S1, plus "rule I1".\n'
rm -rf "$WORK"
