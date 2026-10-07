#!/usr/bin/env bash
# tools/test_mutation_controls.sh -- self-checking suite for
# tools/mutation_controls.sh.
#
# WHY A SELF-TEST AND NOT A COMMENT.  2026-09-17 found a testbench that
# passed 55/55 against deliberately broken RTL; 2026-09-18 found a regression
# that printed PASS while its log held UVM_ERRORs; 2026-10-06 found a
# witness-kill DETECTOR that misattributed four of five kills.  Three
# separate times in this repository the thing doing the checking was itself
# unchecked.  A control that has never been shown to fail is not a control,
# so every verdict mc_controls_* can return gets a case here that FORCES it,
# and the suite fails if any case returns something else.
#
# The cases are arranged so that each one is the MINIMAL change from the
# clean case that produces its verdict, which is what makes the suite a test
# of the controls rather than a test of bash.
#
# Case 3 is the one this file exists for.  `cmp -s` -- the only injection
# control the existing harnesses have -- PASSES it, because the mutant really
# does differ from the original.  Half the defect is missing anyway.
#
# Run: ./tools/test_mutation_controls.sh      (no simulator needed)

set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
. "$HERE/mutation_controls.sh"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

pass=0; fail=0
LOG=()
say() { local s="${1:-}"; LOG+=("$s"); printf "%s\n" "$s"; }

# expect <case> <wanted> <orig_text> <sed_expr> [note]
expect_sed() {
    local name="$1" want="$2" body="$3" expr="$4" note="${5:-}"
    printf '%s' "$body" > "$WORK/orig.v"
    sed "$expr" "$WORK/orig.v" > "$WORK/mut.v" 2>/dev/null
    local got
    got="$(mc_controls_sed "$WORK/orig.v" "$WORK/mut.v" "$expr" 2>/dev/null)"
    if [ "$got" = "$want" ]; then
        say "  [PASS] $name  -> $got"
        pass=$((pass+1))
    else
        say "  [FAIL] $name  wanted '$want', got '$got'"
        fail=$((fail+1))
    fi
    [ -n "$note" ] && say "         $note"
    return 0
}

say "self-test: tools/mutation_controls.sh"
say "=============================================================================="
say "  Each case is the MINIMAL change from case 1 that forces its verdict."
say

# ---- 1. the clean case ------------------------------------------------------
expect_sed "1  clean single-site substitution" "OK" \
'module m;
  assign y = a & b;
  assign z = c | d;
endmodule
' 's|assign y = a & b;|assign y = a \& ~b;|'

# ---- 2. the anchor does not exist ------------------------------------------
expect_sed "2  anchor matches nothing (cmp catches this one too)" \
"NOT_INJECTED" \
'module m;
  assign y = a & b;
endmodule
' 's|assign y = a \^ b;|assign y = a \& ~b;|'

# ---- 3. THE CASE THIS FILE EXISTS FOR -------------------------------------
# The anchor occurs TWICE ON ONE LINE.  sed without /g replaces only the
# first, so the mutant carries half the defect -- and `cmp -s` passes it,
# because the mutant does differ from the original.
# NOTE, because it is evidence for the distinction this file draws: the FIRST
# attempt at this case used the anchor `en ? ` with the replacement `en ? ~`,
# which occurs twice on one line AND matches its own replacement, so it came
# back B_SELF_MATCHING rather than HALF_INJECTED.  The two faults are easy to
# write by accident in the same breath, which is why the controls tell them
# apart by the occurrence count rather than by presence alone.
expect_sed "3  anchor twice on ONE line: sed replaces only the first" \
"HALF_INJECTED" \
'module m;
  assign y = (sel ? dat_a : dat_b) | (sel ? dat_a : 1'"'"'b0);
endmodule
' 's|dat_a|dat_c|' \
"this is the row cmp -s passes: the mutant DOES differ, and half the defect is missing"

# ---- 4. the anchor is on several lines: sed mutates all of them ------------
expect_sed "4  anchor on TWO lines: all sites mutated, count reported" \
"OK_MULTISITE:2" \
'module m;
  always @(posedge clk) q1 <= d1;
  always @(posedge clk) q2 <= d2;
endmodule
' 's|posedge clk|negedge clk|' \
"not an error -- but a mutant described as one defect that changes two sites is not the experiment the report claims"

# ---- 5. the inserted text was already there -------------------------------
# Control A ("the inserted text is present in the mutant") cannot fail here,
# which is exactly the 2026-10-01 fault.
expect_sed "5  inserted text ALREADY in the original: control A cannot fail" \
"OK_A_VACUOUS" \
'module m;
  assign w = a & b;
  assign y = ~b;
endmodule
' 's|assign w = a \& b;|assign y = ~b;|' \
"an arrival control that cannot fail is not a control (2026-10-01)"

# ---- 6. an anchor that matches its own replacement ------------------------
# A back-referencing RHS is also the easiest way to write an anchor loose
# enough to match what it produces.  Control B is then VACUOUS, not failing,
# and saying so is the point: the repair is a tighter anchor, not a looser
# control.
expect_sed "6  anchor matches its own replacement: B is vacuous, not failing" \
"B_SELF_MATCHING" \
'module m;
  assign y = a & b;
endmodule
' 's|assign y = \(.*\);|assign y = ~(\1);|' \
"told apart from case 3 by whether the occurrence count went DOWN"

# ---- 6b. a back-reference with a TIGHT anchor: A abstains, B applies -----
expect_sed "6b back-reference with a tight anchor: A abstains, B holds" \
"A_SKIPPED:backref" \
'module m;
  wire y_bus = a & b;
endmodule
' 's|wire \(y_bus\) = a \& b;|wire \1 = a \& ~b;|' \
"a control that guesses is worse than one that abstains and says so"

# ---- 7. a deletion ---------------------------------------------------------
expect_sed "7  empty RHS (a deletion): A abstains, B still applies" \
"A_SKIPPED:deletion" \
'module m;
  assign y = a & b;
  assign z = c;
endmodule
' 's|  assign z = c;||'

# ---- 8. an identity substitution -----------------------------------------
expect_sed "8  identity substitution s/x/x/: no change at all" \
"NOT_INJECTED" \
'module m;
  assign y = a & b;
endmodule
' 's|a & b|a \& b|'

# ---- 9/10. the literal-text route, used for multi-line injections --------
say
say "  the mc_controls_text route (multi-line injections done in python):"
printf '%s' 'line one
  if (rd_en) begin
    clear <= 1;
  end
' > "$WORK/orig.v"
printf '%s' 'line one
  if (1'"'"'b0) begin
    clear <= 1;
  end
' > "$WORK/mut.v"
got="$(mc_controls_text "$WORK/orig.v" "$WORK/mut.v" "if (rd_en) begin" "if (1'b0) begin" 2>/dev/null)"
if [ "$got" = "OK" ]; then say "  [PASS] 9  clean multi-line replacement -> OK"; pass=$((pass+1))
else say "  [FAIL] 9  wanted 'OK', got '$got'"; fail=$((fail+1)); fi

# a text mutation that left one copy of the replaced text behind
printf '%s' 'a: if (rd_en) begin end
b: if (rd_en) begin end
' > "$WORK/orig.v"
printf '%s' 'a: if (1'"'"'b0) begin end
b: if (rd_en) begin end
' > "$WORK/mut.v"
got="$(mc_controls_text "$WORK/orig.v" "$WORK/mut.v" "if (rd_en) begin" "if (1'b0) begin" 2>/dev/null)"
if [ "$got" = "HALF_INJECTED" ]; then say "  [PASS] 10 one of two copies replaced -> HALF_INJECTED"; pass=$((pass+1))
else say "  [FAIL] 10 wanted 'HALF_INJECTED', got '$got'"; fail=$((fail+1)); fi

# ---- 11. mc_verdict_usable agrees with the table above -------------------
say
bad=0
for v in OK "OK_MULTISITE:3" OK_A_VACUOUS "A_SKIPPED:backref" "A_SKIPPED:deletion"; do
    mc_verdict_usable "$v" || { say "  [FAIL] 11 mc_verdict_usable rejected usable verdict '$v'"; bad=1; }
done
for v in NOT_INJECTED HALF_INJECTED A_MISSING B_NO_ANCHOR B_SELF_MATCHING; do
    mc_verdict_usable "$v" && { say "  [FAIL] 11 mc_verdict_usable accepted unusable verdict '$v'"; bad=1; }
done
if [ "$bad" -eq 0 ]; then say "  [PASS] 11 mc_verdict_usable partitions the verdict set as documented"; pass=$((pass+1))
else fail=$((fail+1)); fi

say
say "=============================================================================="
say "RESULT: $pass passed, $fail failed"
say "=============================================================================="
say "  Every verdict mc_controls_sed can return is forced by a case above, so"
say "  none of them is an untested branch.  Case 3 is the one that motivates"
say "  the file: the existing harnesses' cmp -s check passes it."
printf '%s\n' "${LOG[@]}" > "$HERE/mutation_controls_selftest_output.txt"
[ "$fail" -eq 0 ]
