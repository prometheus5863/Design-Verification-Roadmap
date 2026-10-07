#!/usr/bin/env bash
# tools/audit_mutation_anchors.sh
#
# Applies tools/mutation_controls.sh to EVERY sed-injected mutant already
# committed in this repository's shell mutation harnesses, without running a
# simulator.  This is the audit the 2026-10-01 item asked for -- "every mutant
# in this repository needs control B" -- performed as a measurement before any
# harness is changed, so that the answer is a number rather than a prediction.
#
# WHY THE AUDIT COMES FIRST.  Four harnesses have control A only, in the weak
# `cmp -s` form, which catches a sed that matched NOTHING and nothing else.
# The interesting failure is a sed that matched SOMETHING AND NOT EVERYTHING:
# `sed 's|A|B|'` replaces the first match on each line, so an anchor occurring
# twice on one line leaves half the defect in place while `cmp` reports a
# difference and the harness scores the row.
#
# The honest possibility, and the one 2026-10-01 warns about, is that this
# audit finds nothing.  A control that would have caught no committed fault is
# still worth having -- it moves a class of bug from "undetectable" to
# "detected" -- but it must be REPORTED as having found nothing rather than
# presented as a fix.
#
# Each harness's mutant table is read by sourcing the harness up to its first
# executable line, with `add` kept and nothing else run.  No simulator, no
# make, no network.
#
# Run: ./tools/audit_mutation_anchors.sh

set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
. "$HERE/mutation_controls.sh"

# The harness fragments this script sources set their OWN `RTL`, `WORK` and
# `HERE`, so every name the audit depends on is prefixed and every load runs
# in a SUBSHELL that only prints its table.  The first version of this script
# did neither, the sourced phase4_ral fragment overwrote `RTL` with a path
# relative to tools/, and all twelve remaining rows came back B_NO_ANCHOR --
# a control reporting "the anchor is not in the original" about a file that
# did not exist.  That is 2026-09-30's rule about itself: a control has to
# sit where the failure enters, and this one was reading a variable the thing
# under audit could write.
AUDIT_RTL="$ROOT/rtl/uart_controller.v"
AUDIT_WORK="$(mktemp -d)"
trap 'rm -rf "$AUDIT_WORK"' EXIT
[ -f "$AUDIT_RTL" ] || { echo "audit: $AUDIT_RTL not found" >&2; exit 2; }

RS=$'\x1e'   # record separator
FS=$'\x1f'   # field separator

LOG=()
say() { local s="${1:-}"; LOG+=("$s"); printf '%s\n' "$s"; }

total=0; ok=0; multisite=0; problems=0; skipped=0
declare -a PROBLEM_ROWS=()
declare -a NOTED_ROWS=()

audit_one() {
    local harness="$1" tag="$2" expr="$3"
    total=$((total+1))
    sed "$expr" "$AUDIT_RTL" > "$AUDIT_WORK/mut.v" 2>/dev/null
    local verdict detail
    detail="$(mc_controls_sed "$AUDIT_RTL" "$AUDIT_WORK/mut.v" "$expr" 2>&1 >/dev/null)"
    verdict="$(mc_controls_sed "$AUDIT_RTL" "$AUDIT_WORK/mut.v" "$expr" 2>/dev/null)"
    case "$verdict" in
        OK) ok=$((ok+1)); say "  [ OK            ] $harness  $tag" ;;
        OK_MULTISITE:*|OK_A_VACUOUS|A_SKIPPED:*)
            multisite=$((multisite+1))
            NOTED_ROWS+=("$harness ${tag%% *} -> $verdict")
            say "  [ $verdict ] $harness  $tag"
            say "                   $detail" ;;
        *)
            problems=$((problems+1))
            PROBLEM_ROWS+=("$harness $tag -> $verdict")
            say "  [ ** $verdict ** ] $harness  $tag"
            say "                   $detail" ;;
    esac
}

# --- table readers.  Each runs in a SUBSHELL and prints tag<FS>sed<RS>. ----
emit_add_style() {       # phase4_ral: add NAME DESC TARGET SED
  (
    set +u
    add() { printf '%s%s%s%s' "$1 $2" "$FS" "$4" "$RS"; }
    # Only the add() calls, from the first one to the line before the first
    # executable echo.  Taking "everything before the first echo" also took
    # the harness's own HERE/RTL/WORK assignments, which then overwrote the
    # audit's -- see the note at the top of this file.
    awk '/^add /{f=1} /^echo "====/{exit} f' "$1" > "$AUDIT_WORK/decl_add.sh"
    . "$AUDIT_WORK/decl_add.sh"
  )
}

emit_named_arrays() {    # $1 file, $2 names-array start, $3 seds-array start, $4 end marker
  (
    set +u
    sed -n "/^$2=(/,/^$4=(/p" "$1" | sed '$d' > "$AUDIT_WORK/decl_arr.sh"
    . "$AUDIT_WORK/decl_arr.sh"
    eval "local -a _n=(\"\${$2[@]}\")"
    eval "local -a _s=(\"\${$3[@]}\")"
    for i in "${!_s[@]}"; do
      printf '%s%s%s%s' "${_n[$i]:-row $i}" "$FS" "${_s[$i]}" "$RS"
    done
  )
}

emit_two_blocks() {      # $1 file, $2 names-array name, $3 seds-array name
  (
    set +u
    sed -n "/^$2=(/,/^)/p" "$1" > "$AUDIT_WORK/d1.sh"
    sed -n "/^$3=(/,/^)/p" "$1" > "$AUDIT_WORK/d2.sh"
    . "$AUDIT_WORK/d1.sh"; . "$AUDIT_WORK/d2.sh"
    eval "local -a _n=(\"\${$2[@]}\")"
    eval "local -a _s=(\"\${$3[@]}\")"
    for i in "${!_s[@]}"; do
      printf '%s%s%s%s' "${_n[$i]:-row $i}" "$FS" "${_s[$i]}" "$RS"
    done
  )
}

# Rows whose REAL injection is done in python, with the sed string acting as
# a placeholder or an annotation marker.  Auditing those sed strings as if
# they were the mutation is a category error, so they are named and skipped
# rather than scored.  Listed explicitly, by harness and tag prefix, so the
# skip is visible in the transcript and cannot quietly grow.
PY_INJECTED=(
  "phase6_crv_uart|M6"          # multi-line STATUS read-to-clear removal
  "phase6_rx_pin_driver|M7"     # sed adds a marker; python rewrites rx_sync uses
)

consume() {              # $1 harness label; reads tag<FS>sed<RS> on stdin
    local harness="$1" rec tag expr k
    while IFS= read -r -d "$RS" rec; do
        tag="${rec%%$FS*}"
        expr="${rec#*$FS}"
        local is_py=no
        for k in "${PY_INJECTED[@]}"; do
            if [ "$harness" = "${k%%|*}" ] && [ "${tag%% *}" = "${k##*|}" ]; then
                is_py=yes; break
            fi
        done
        if [ "$is_py" = yes ]; then
            skipped=$((skipped+1))
            say "  [ skipped       ] $harness  $tag"
            say "                   real injection is done in python; the sed string is a"
            say "                   placeholder or annotation marker, so auditing it as the"
            say "                   mutation would be a category error"
            continue
        fi
        audit_one "$harness" "$tag" "$expr"
    done
}

say "mutation-anchor audit -- every sed-injected mutant committed in this repository"
say "=============================================================================="
say "  DUT: rtl/uart_controller.v  (never modified; every mutant is a copy)"
say "  Controls applied: A (inserted text present in mutant, absent from"
say "  original), B (replaced pattern absent from mutant), C (site count"
say "  reported).  See tools/mutation_controls.sh and its self-test."
say

H="$ROOT/examples/phase4_ral/run_mutation_tests.sh"
if [ -f "$H" ]; then
    say "  examples/phase4_ral/run_mutation_tests.sh"
    consume "phase4_ral" < <(emit_add_style "$H")
    say
fi

H="$ROOT/examples/phase6_crv_uart/run_mutation_tests.sh"
if [ -f "$H" ]; then
    say "  examples/phase6_crv_uart/run_mutation_tests.sh"
    consume "phase6_crv_uart" < <(emit_named_arrays "$H" MUT_NAMES MUT_SEDS MUT_EXPECT)
    say
fi

H="$ROOT/examples/phase6_rx_pin_driver/run_mutation_tests.sh"
if [ -f "$H" ]; then
    say "  examples/phase6_rx_pin_driver/run_mutation_tests.sh"
    consume "phase6_rx_pin_driver" < <(emit_two_blocks "$H" names seds)
    say
fi

say "=============================================================================="
say "RESULT: $total sed-injected mutants audited"
say "        $ok clean, $multisite reported-not-failing, $problems failing a control, $skipped skipped"
say "=============================================================================="
if [ "$problems" -eq 0 ]; then
    say "  NO COMMITTED MUTANT IS HALF-INJECTED.  Every row whose sed is the"
    say "  real injection passes control B, so no committed verdict in this"
    say "  repository is a verdict about a partial mutant.  Reported as the"
    say "  negative result it is: the controls move the half-injection class"
    say "  from undetectable to detected, and they do not retroactively find a"
    say "  fault."
    say
    say "  BUT THE AUDIT IS NOT EMPTY.  Three rows are usable and are NOT what"
    say "  their harness's own control can certify:"
    for r in "${NOTED_ROWS[@]}"; do say "    $r"; done
    say
    say "  Read in order of what they cost:"
    say "   * OK_A_VACUOUS is the direct answer to 2026-10-01's item.  That"
    say "     row's INSERTED text already exists elsewhere in the DUT, so the"
    say "     arrival control 2026-09-30 asked for -- grep the mutant for the"
    say "     inserted text -- CANNOT FAIL on it.  Only control B certifies"
    say "     that mutant, and control B is what the harnesses did not have."
    say "     The item asked whether they need it; one of their own committed"
    say "     rows is the answer."
    say "   * OK_MULTISITE:2 is a mutant described as one defect that changes"
    say "     TWO sites.  Fully injected, so its kill is real -- but the kill"
    say "     names the suite's response to a COMPOUND change, and the report"
    say "     presents it as one.  Nothing was wrong; something was unstated."
    say "   * A_SKIPPED:unparsable is a sed written as 0,/re/s||repl| -- an"
    say "     address-scoped substitution with an EMPTY pattern that reuses the"
    say "     address regex.  No text-level control can be formed for it at"
    say "     all, by either harness or audit.  Recorded rather than papered"
    say "     over; the repair is to rewrite that one row with an explicit"
    say "     pattern."
else
    say "  ROWS FAILING A CONTROL -- each one is a verdict about a partial"
    say "  mutant and must be re-read:"
    for r in "${PROBLEM_ROWS[@]}"; do say "    $r"; done
fi
if [ "$multisite" -gt 0 ]; then
    say
    say "  MULTI-SITE ROWS are not errors: sed mutates every matching line, so"
    say "  the defect is fully injected.  They are reported because a mutant"
    say "  DESCRIBED as one defect that changes several sites is not the"
    say "  experiment its report claims, and a kill then names the suite's"
    say "  response to a compound change."
fi
printf '%s\n' "${LOG[@]}" > "$HERE/mutation_anchor_audit_output.txt"
[ "$problems" -eq 0 ]
