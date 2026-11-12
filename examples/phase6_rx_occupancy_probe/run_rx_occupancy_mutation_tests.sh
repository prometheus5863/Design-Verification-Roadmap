#!/usr/bin/env bash
# examples/phase6_rx_occupancy_probe/run_rx_occupancy_mutation_tests.sh
#
# DISCHARGES "A CHECK THAT OBSERVES rx_cnt DIRECTLY", carried since 2026-11-07.
#
# THE QUESTION, verbatim from rx_avail_mutation_report_2026-11-07.txt:
#
#     "AND R3 AND R4 ARE INDISTINGUISHABLE IN THIS MATRIX.  Both report the
#      same first failing check with the same byte count, because both make
#      the last byte unreadable -- R3 by stopping the bench asking for it, R4
#      by stopping the RTL popping it.  The mechanisms differ and this
#      instrument cannot tell them apart ... Separating them needs a check
#      that observes rx_cnt directly, and that is logged rather than claimed
#      here."
#
# R1-R3 mutate the STATUS DECODE only: rx_pop keeps the true rx_avail, so the
# DUT's datapath is untouched and only a reader of STATUS can be misled.
# R4 mutates the WIRE, which rx_pop gates on, so a read of RX_DATA at
# occupancy 1 pops nothing.  "The sequencing gate lied" versus "the DUT
# changed" -- and an instrument that cannot tell those apart cannot say which
# of its own detections are about the RTL.
#
# WHY A SECOND BENCH AND NOT FOUR MORE ROWS.  The 11-07 adjudication rests on
# the census premise that NO check in uart_crv_cov_tb.v names rx_avail or
# st[3] (its G2).  A check that observes rx_cnt names exactly that, so adding
# one there would silently convert the SYNC_ONLY row it was built to measure
# into a PREDICTED one.  The probe therefore lives in its own bench, and this
# runner reproduces the 11-07 configuration as its own baseline instead of
# asserting agreement with it.
#
# THREE CONFIGURATIONS, and the middle one is the control that makes the
# separation mean something:
#
#   A  +gate=0 +decode=0   STATUS is the gate and nothing checks it.
#                          The 11-07 configuration, rebuilt.
#   B  +gate=1 +decode=0   the PROBE is the gate and nothing checks STATUS.
#                          Decode-only mutants are invisible here BY
#                          CONSTRUCTION, so any arm that still fails is
#                          failing on DUT BEHAVIOUR.
#   C  +gate=1 +decode=1   the probe gates and K5 checks the decode against
#                          it.  Everything is caught; what separates the arms
#                          is WHICH checks fail.
#
# THE VERDICT IS A SET, NOT A FIRST FAILURE.  2026-10-21's lesson from the
# tx_empty runner was that first-failure-wins hides information, and it bites
# again here: in configuration C the mutated wire trips K5 before K2, so R3
# and R4 have the SAME first failing check and DIFFERENT failing sets.  Had
# this runner reported a first failure it would have reproduced the 11-07
# indistinguishability and concluded the probe does not work.
#
# Every mutant is injected into a COPY under $TMPDIR; the repo's RTL is never
# modified.
#
# Usage:  bash examples/phase6_rx_occupancy_probe/run_rx_occupancy_mutation_tests.sh
# Run from the repo root.

set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

export TMPDIR="${TMPDIR_OVERRIDE:-/tmp}"

# shellcheck disable=SC1091
source tools/setup_iverilog.sh > /dev/null 2>&1
# the WRAPPERS in bin/, not the raw binaries in usr/bin: only the wrappers carry
# the TMPDIR fallback added 2026-11-07, and NOTHING in this repository called them
# until 2026-11-12 -- see tools/toolchain_preflight.sh
IVL_BIN="${IVERILOG_INSTALL_DIR:-/tmp/iverilog_install}/bin"
IVL_LIB="${IVERILOG_INSTALL_DIR:-/tmp/iverilog_install}/usr/lib/x86_64-linux-gnu/ivl"

WORK="$(mktemp -d "$TMPDIR/uart_rxocc.XXXXXX")" || {
    echo "ABORT -- cannot create a scratch directory under TMPDIR=$TMPDIR."
    echo "        This is the disk fault G0 exists for, hit before G0 could run."
    exit 1
}
TB="examples/phase6_rx_occupancy_probe/uart_rx_occupancy_tb.v"
RTL="rtl/uart_controller.v"

CFG_A="+gate=0 +decode=0"
CFG_B="+gate=1 +decode=0"
CFG_C="+gate=1 +decode=1"

fail_count=0
note_fail () { fail_count=$((fail_count + 1)); }

# ---------------------------------------------------------------------------
# compile <rtl> <out> -> "OK" | "DISK" | "COMPILE_ERROR"
#
# G0, AND IT IS NOT BOILERPLATE.  Measured today, 2026-11-09, while building
# this bench: with TMPDIR left at its default -- which in this sandbox
# resolves onto a filesystem that has been 100 % full for fifteen sessions --
# iverilog fails with
#
#     ivlpp: No input files given.
#     No top level modules, and no -s option.
#
# on a file list that is perfectly valid.  The preprocessor cannot write the
# temporary file holding that list, and reports the symptom as an ABSENT
# ARGUMENT.  Every mutation runner in this repository would score that as
# COMPILE_ERROR, which each of them defines as an INJECTION FAILURE -- a
# statement about the mutant.  It is not; it is a statement about the disk.
# That is the standing item "RUN A MUTATION SUITE WITH THE TOOLCHAIN BROKEN IN
# A WAY THAT IS NOT THE NETWORK", and it turned up by itself rather than by
# being staged.  So a compile failure here is probed before it is named.
# ---------------------------------------------------------------------------
compile () {
    local rtl="$1" out="$2"
    if "$IVL_BIN/iverilog" -B "$IVL_LIB" -g2012 -o "$out" "$rtl" "$TB" \
            > "$WORK/compile.log" 2>&1; then
        echo "OK"; return
    fi
    # the file list was valid, so ask the disk before blaming the mutant
    if ! ( : > "$WORK/.probe" ) 2>/dev/null; then
        echo "DISK"; return
    fi
    rm -f "$WORK/.probe"
    if grep -q "No input files given" "$WORK/compile.log"; then
        echo "DISK"; return
    fi
    echo "COMPILE_ERROR"
}

# run_set <sim> <cfg> -> "<PASS|FAIL>|<comma-separated failing check set>|<first fail line>"
# The set is what the verdict is read off; the first line is kept only so the
# comparison with the 11-07 report can be made on the 11-07 terms.
run_set () {
    local sim="$1" cfg="$2" out rc=0 set first
    out="$(timeout 90 "$IVL_BIN/vvp" -M "$IVL_LIB" "$sim" $cfg 2>&1)" || rc=1
    first="$(grep -m1 '^  FAIL ' <<< "$out" | sed 's/^  FAIL //; s/: got .*//')"
    set="$(grep '^  FAIL ' <<< "$out" \
           | sed 's/^  FAIL //' \
           | sed -E 's/^(K[0-9]+b?|V[0-9]+b?|burst watchdog).*/\1/' \
           | sort -u | paste -sd, -)"
    if grep -q "RESULT: PASS" <<< "$out"; then
        echo "PASS||"
    else
        echo "FAIL|$set|$first"
    fi
}

mutate () {
    local tag="$1" expr="$2" dst="$WORK/$1.v"
    sed "$expr" "$RTL" > "$dst"
    if cmp -s "$RTL" "$dst"; then echo ""; else echo "$dst"; fi
}

echo "=============================================================="
echo "MUTATION TEST -- the direct rx_cnt occupancy probe"
echo "  bench : $TB"
echo "  date  : $(date -u +%F)"
echo "  discharges: A CHECK THAT OBSERVES rx_cnt DIRECTLY (carried 11-07)"
echo "=============================================================="
echo

echo "G0  the toolchain, and the disk it writes through"
echo "    TMPDIR=$TMPDIR"
df -P "$TMPDIR" | tail -1 | awk '{printf "    %s %s used of %s, %s free (%s)\n",$1,$3,$2,$4,$5}'
if [ -n "${IVERILOG_INSTALL_DIR:-}" ] || [ -x "$IVL_BIN/iverilog" ]; then
    echo "    iverilog: $("$IVL_BIN/iverilog" -V 2>&1 | head -1)"
else
    echo "    ABORT -- no iverilog."
    exit 1
fi
C0="$(compile "$RTL" "$WORK/base.sim")"
case "$C0" in
  OK)   echo "    the unmodified RTL compiles -- so a later failure is about"
        echo "    the mutant or the disk, and G0 can tell those apart." ;;
  DISK) echo "    ABORT -- the toolchain cannot write its own temporary files."
        echo "    This is a DISK fault, not an injection failure, and naming it"
        echo "    correctly is the whole point of this guard."
        exit 1 ;;
  *)    echo "    ABORT -- the unmodified RTL does not compile:"
        sed 's/^/      /' "$WORK/compile.log"
        exit 1 ;;
esac
echo

echo "G1  baseline: the bench must PASS on unmodified RTL in all three"
echo "    configurations, or no row below means anything"
ok=1
for tag in A B C; do
    eval "cfg=\$CFG_$tag"
    R="$(run_set "$WORK/base.sim" "$cfg")"
    printf '    %s  %-20s %s\n' "$tag" "$cfg" "${R%%|*}"
    [ "${R%%|*}" = "PASS" ] || ok=0
done
[ "$ok" -eq 1 ] || { echo "    ABORT -- baseline not clean."; exit 1; }
echo "    OK."
echo

echo "G1b the zero-length limit: a burst of 0 bytes must issue no RX read and"
echo "    leave the probe at exactly 0.  A limit that must give zero, which is"
echo "    the kind of check that caught a real bug on 2026-09-17."
Z="$(run_set "$WORK/base.sim" "$CFG_C +len=0")"
if [ "${Z%%|*}" = "PASS" ]; then echo "    OK -- 0 errors at len=0."
else echo "    FAILED -- ${Z}"; note_fail; fi
echo

echo "G2  THE PREMISE, MEASURED.  The 11-07 adjudication rests on 'no check"
echo "    names rx_avail or st[3]'.  That premise is FALSE of this bench by"
echo "    design, and configuration-dependent, so both halves are checked."
NAMED="$(grep -c 'K5 STATUS.rx_avail agrees with the probe' "$TB")"
if [ "$NAMED" -ge 1 ]; then
    echo "    CONFIRMED -- this bench DOES contain a check naming rx_avail (K5),"
    echo "    which is why it is a separate bench and not four rows added to"
    echo "    uart_crv_cov_tb.v, whose SYNC_ONLY row it would invalidate."
else
    echo "    REFUTED -- K5 is absent; this runner's premise is stale."
    note_fail
fi
if grep -q 'if (want_decode)' "$TB"; then
    echo "    and K5 is gated on +decode, so A and B satisfy the 11-07 premise"
    echo "    in its LITERAL form: no check in them names rx_avail or st[3]."
else
    echo "    ABSENT -- K5 is not gated, so A and B are not the 11-07 premise."
    note_fail
fi
echo "    BUT A IS THE 11-07 GATE, NOT THE 11-07 BENCH, and the difference is"
echo "    stated here rather than discovered later.  K2, V1-V3b read the probe"
echo "    and are active in every configuration, so A has an occupancy"
echo "    observer that uart_crv_cov_tb.v does not have.  That is visible in"
echo "    the matrix below: R2 fails V3b in A -- a conservation identity that"
echo "    names rx_cnt, not rx_avail, catches 'stuck SET' without violating the"
echo "    premise.  FINDING 1 is therefore a reproduction of what the GATE"
echo "    forces, which is all it claims."
echo "    the probe itself reaches into the DUT, as it must:"
grep -n 'dut\.rx_cnt\|dut\.rx_wptr' "$TB" | sed 's/^/      /'
echo

echo "G2b neutrality control: a COMMENT-ONLY edit must compile and ESCAPE in"
echo "    all three configurations"
cp "$RTL" "$WORK/neutral.v"
printf '\n// G2b cosmetic-edit control, injected by run_rx_occupancy_mutation_tests.sh\n' \
    >> "$WORK/neutral.v"
cmp -s "$RTL" "$WORK/neutral.v" && { echo "    ABORT -- neutral control changed nothing."; exit 1; }
CN="$(compile "$WORK/neutral.v" "$WORK/neutral.sim")"
[ "$CN" = "OK" ] || { echo "    ABORT -- the comment-only mutant does not compile ($CN)."; exit 1; }
neu_ok=1
for tag in A B C; do
    eval "cfg=\$CFG_$tag"
    R="$(run_set "$WORK/neutral.sim" "$cfg")"
    printf '    %s  %-20s %s\n' "$tag" "$cfg" "${R%%|*}"
    [ "${R%%|*}" = "PASS" ] || neu_ok=0
done
[ "$neu_ok" -eq 1 ] || { echo "    ABORT -- a comment-only edit was not a clean escape."; exit 1; }
echo "    OK."
echo

declare -A VERD SET FIRST

DESC_R1="STATUS decode: rx_avail stuck CLEAR"
DESC_R2="STATUS decode: rx_avail stuck SET"
DESC_R3="STATUS decode: rx_avail one entry LATE"
DESC_R4="WIRE: rx_avail one entry late (rx_pop too)"
# R5 is a SECOND positive control for K2, by a different mechanism.  R4 makes
# rx_pop late; R5 makes it never fire at all.  Without R5, K2's only evidence
# would be the single mutant it was written against, which is the shape of a
# tripwire rather than of a check.
DESC_R5="WIRE: rx_pop never asserts"

# The four arms are byte-for-byte the sed expressions of
# run_rx_avail_mutation_tests.sh.  Same mutants, different instrument: that is
# what makes the comparison with the 11-07 report a reproduction rather than
# an analogy.
EXPR_R1="s/rx_avail, rx_full, tx_empty, tx_full};/1'b0, rx_full, tx_empty, tx_full};/"
EXPR_R2="s/rx_avail, rx_full, tx_empty, tx_full};/1'b1, rx_full, tx_empty, tx_full};/"
EXPR_R3="s/rx_avail, rx_full, tx_empty, tx_full};/(rx_cnt > 4'd1), rx_full, tx_empty, tx_full};/"
EXPR_R4="s/wire rx_avail = (rx_cnt != 4'd0);/wire rx_avail = (rx_cnt > 4'd1);/"
EXPR_R5="s/wire rx_pop  = rd_en & (paddr == ADDR_RX_DATA) & rx_avail;/wire rx_pop  = 1'b0;/"

echo "G3  every mutant must actually change the file, and compile"
for id in R1 R2 R3 R4 R5; do
    eval "expr=\$EXPR_$id"
    path="$(mutate "$id" "$expr")"
    if [ -z "$path" ]; then
        echo "    $id  NO-OP -- sed changed nothing.  G3 FAILED."
        note_fail
        for tag in A B C; do VERD[$id,$tag]="NOOP"; SET[$id,$tag]=""; FIRST[$id,$tag]=""; done
        continue
    fi
    C="$(compile "$path" "$WORK/$id.sim")"
    if [ "$C" != "OK" ]; then
        echo "    $id  $C -- not a detection.  G3 FAILED."
        note_fail
        for tag in A B C; do VERD[$id,$tag]="$C"; SET[$id,$tag]=""; FIRST[$id,$tag]=""; done
        continue
    fi
    echo "    $id  changed and compiles"
    for tag in A B C; do
        eval "cfg=\$CFG_$tag"
        R="$(run_set "$WORK/$id.sim" "$cfg")"
        VERD[$id,$tag]="${R%%|*}"
        SET[$id,$tag]="$(cut -d'|' -f2 <<< "$R")"
        FIRST[$id,$tag]="$(cut -d'|' -f3 <<< "$R")"
    done
done
echo

echo "--------------------------------------------------------------"
echo "DETECTION MATRIX -- verdict, and the SET of checks that failed"
echo "--------------------------------------------------------------"
echo
printf '  %-4s %-42s %-6s %-6s %-6s\n' "ID" "mutant" "A" "B" "C"
printf '  %-4s %-42s %-6s %-6s %-6s\n' "--" "------" "11-07" "probe" "probe"
printf '  %-4s %-42s %-6s %-6s %-6s\n' "" "" "gate" "only" "+K5"
for id in R1 R2 R3 R4 R5; do
    eval "d=\$DESC_$id"
    printf '  %-4s %-42s %-6s %-6s %-6s\n' "$id" "$d" \
        "${VERD[$id,A]}" "${VERD[$id,B]}" "${VERD[$id,C]}"
done
echo
for id in R1 R2 R3 R4 R5; do
    eval "d=\$DESC_$id"
    echo "  $id  $d"
    for tag in A B C; do
        eval "cfg=\$CFG_$tag"
        printf '      %s %-20s %-5s  failing set: %s\n' "$tag" "$cfg" \
            "${VERD[$id,$tag]}" "${SET[$id,$tag]:-<none>}"
    done
done
echo

echo "--------------------------------------------------------------"
echo "FINDING 1 -- configuration A REPRODUCES the 11-07 indistinguishability"
echo "--------------------------------------------------------------"
echo
echo "  R3 first failing check: ${FIRST[R3,A]}"
echo "  R4 first failing check: ${FIRST[R4,A]}"
if [ "${FIRST[R3,A]}" = "${FIRST[R4,A]}" ] && [ -n "${FIRST[R3,A]}" ]; then
    echo
    echo "  IDENTICAL, including the byte count, in a bench written eight"
    echo "  sessions later with a different stimulus and a different check set."
    echo "  rx_avail_mutation_report_2026-11-07.txt reported"
    echo "  'burst watchdog: 3 of 4 bytes returned' for both arms at len=4;"
    echo "  this bench reports the same shape at len=8.  The 11-07 claim was"
    echo "  not an artefact of that bench -- it is a property of taking the"
    echo "  mutated flag as the SEQUENCING GATE, which is what A does too."
    echo "  This is the overlapping limit, reproduced rather than asserted."
else
    echo
    echo "  NOT REPRODUCED -- the two arms differ in configuration A, which"
    echo "  contradicts rx_avail_mutation_report_2026-11-07.txt.  One of the"
    echo "  two benches is wrong about this and the difference is the finding."
    note_fail
fi
echo

echo "--------------------------------------------------------------"
echo "FINDING 2 -- K2 IS THE DISCRIMINATOR, and it is a set membership"
echo "            question rather than a first-failure one"
echo "--------------------------------------------------------------"
echo
echo "  The claim under test: the pop-effect check K2 fires for BOTH wire"
echo "  mutants -- R4 (rx_pop late) and R5 (rx_pop never) -- and for no"
echo "  decode-only mutant, in both probe configurations."
echo "  Both halves are required.  A check that fires for everything"
echo "  discriminates nothing."
disc_ok=1
for tag in B C; do
    for id in R4 R5; do
        case ",${SET[$id,$tag]}," in
            *,K2,*) echo "  $tag  $id  K2 PRESENT   (a wire mutation changed DUT behaviour)" ;;
            *)      echo "  $tag  $id  K2 ABSENT    -- the discriminator did not fire on an"
                    echo "          arm that changes rx_pop."; disc_ok=0 ;;
        esac
    done
    for id in R1 R2 R3; do
        case ",${SET[$id,$tag]}," in
            *,K2,*) echo "  $tag  $id  K2 PRESENT  -- a decode-only mutant moved the"
                    echo "          pop-effect check.  K2 does not discriminate."; disc_ok=0 ;;
            *)      echo "  $tag  $id  K2 absent    (decode only: the datapath is intact)" ;;
        esac
    done
done
echo
if [ "$disc_ok" -eq 1 ]; then
    echo "  DISCHARGED.  K2 separates 'the sequencing gate lied' from 'the DUT"
    echo "  changed', which is exactly what the 11-07 report said was missing."
    echo
    echo "  TWO mechanisms, not one: R4 delays rx_pop and R5 removes it, and K2"
    echo "  fires for both.  A check with one witness is a tripwire."
    echo
    echo "  AND THE SEPARATION SURVIVES THE ORDERING TRAP.  In configuration C"
    echo "  the mutated wire trips K5 before K2, so R3 and R4 have the SAME"
    echo "  first failing check there -- a first-failure report would have"
    echo "  concluded the probe does not work.  Configuration B is the clean"
    echo "  statement: with nothing checking STATUS at all, the three"
    echo "  decode-only mutants ESCAPE and the wire mutant does not."
else
    echo "  NOT DISCHARGED -- see the lines above."
    note_fail
fi
echo

echo "--------------------------------------------------------------"
echo "WHAT THIS DOES NOT ESTABLISH"
echo "--------------------------------------------------------------"
echo
echo "  * The probe is WHITE-BOX.  K2 reads dut.rx_cnt and dut.rx_wptr, so it"
echo "    is unavailable to any bench restricted to the APB port, and it is"
echo "    not a substitute for the black-box checks -- it is an instrument for"
echo "    attributing their failures."
echo "  * Configuration B's escapes are NOT a defect of the probe.  Nothing in"
echo "    B reads STATUS, so a STATUS-decode mutant has no observer by"
echo "    construction.  B is a negative control, not a coverage claim."
echo "  * One stimulus shape.  This bench runs a single deterministic burst,"
echo "    not the 4-seed x 2-mode matrix of the 11-07 runner, so it measures"
echo "    the DISCRIMINATION and inherits nothing about seed sensitivity."
echo "  * K5's own exercise is counted (V4) but its sampling is still tied to"
echo "    the drain loop's pace; at a wider divisor the FIFO is non-empty for"
echo "    a smaller fraction of the run, and V4 is what would notice."
echo

if [ "$fail_count" -eq 0 ]; then
    echo "RESULT: PASS  (all controls green, item discharged)"
    exit 0
else
    echo "RESULT: FAIL  ($fail_count control(s) failed)"
    exit 1
fi
