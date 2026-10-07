#!/usr/bin/env bash
# tools/mutation_controls.sh -- shared injection controls for the sed-based
# mutation harnesses in this repository.  SOURCE it; do not execute it.
#
# ----------------------------------------------------------------------------
# WHY THIS EXISTS
# ----------------------------------------------------------------------------
# 2026-09-30 required a positive control that a mutation ARRIVED, because a
# mutation that does not arrive is indistinguishable from a system that does
# not respond: both produce a passing suite.  2026-10-01 corrected that rule
# rather than extending it.  This repository's own first M3 passed an
# arrival control (a grep for the INSERTED text) while being semantically
# inert, and was wrongly filed as a suite weakness.  The correction:
#
#   CONTROL A (arrival)      the INSERTED text is PRESENT in the mutant,
#                            and ABSENT from the original.
#   CONTROL B (completeness) the REPLACED pattern is ABSENT from the mutant,
#                            and PRESENT in the original.
#
# Control B is the one the existing harnesses lack.  They use `cmp -s mutant
# original`, which catches only the case where sed matched NOTHING at all.
# It cannot see the case that matters more:
#
#     sed 's|A|B|'   replaces the FIRST match ON EACH LINE.
#
# So if the anchor occurs TWICE ON ONE LINE, exactly one of them is replaced
# and the mutant carries HALF the defect.  `cmp` reports a difference, the
# harness scores the row, and whatever verdict comes back is a verdict about
# a half-mutant.  That is the same shape as the graphene repository's
# 2026-10-06 "coherence trap", where a counterfactual arrived at one of the
# two places its quantity entered and answered with the OPPOSITE SIGN.
#
# CONTROL C (site count) is reported, not enforced: the number of lines the
# anchor matches in the original.  More than one is not wrong -- sed will
# mutate all of them -- but a mutant DESCRIBED as one defect that changes
# three sites is not the experiment the report claims, so the count is
# printed and the caller decides.
#
# ----------------------------------------------------------------------------
# WHAT THIS DELIBERATELY DOES NOT DO
# ----------------------------------------------------------------------------
# It does not try to recover a LITERAL string from the left-hand side of a sed
# expression.  Those left-hand sides are POSIX BREs and several in this
# repository use `.` as a wildcard for a quote character (`2.b10` for
# `2'b10`), so there is no literal to recover.  Control B therefore applies
# the BRE itself with `grep`, whose BRE dialect is the same POSIX one sed
# uses.  Control A does need a literal, and when the right-hand side contains
# an unescaped `&` (the whole-match reference) or a `\1`-style back-reference
# the literal does not exist either -- in that case control A reports
# A_SKIPPED rather than guessing.  A control that guesses is worse than one
# that abstains and says so.
#
# ----------------------------------------------------------------------------
# USAGE
# ----------------------------------------------------------------------------
#   source tools/mutation_controls.sh
#
#   mc_controls_sed  <original> <mutant> <sed_expr>
#   mc_controls_text <original> <mutant> <from_literal> <to_literal>
#
# Both echo ONE verdict token on stdout and a human-readable detail line on
# stderr.  Verdicts:
#
#   OK              controls A and B both hold; one site
#   OK_MULTISITE:n  A and B hold, but the anchor matched n > 1 lines
#   NOT_INJECTED    the mutant is byte-identical to the original
#   HALF_INJECTED   the replaced pattern is STILL PRESENT in the mutant
#   OK_A_VACUOUS    control B held, so the mutant is complete -- but the
#                   inserted text was ALREADY in the original, so control A
#                   cannot fail on this row and certifies nothing.  Usable,
#                   and the reason control B is not optional.
#   A_MISSING       the inserted text is not in the mutant
#   B_NO_ANCHOR     the pattern does not match the ORIGINAL at all
#   B_SELF_MATCHING the pattern still matches the MUTANT as often as it
#                   matched the original, i.e. it matches its own
#                   replacement.  Control B is then vacuous rather than
#                   failing, and the repair is a tighter anchor.
#   A_SKIPPED:...   control A could not be formed (back-reference in the RHS);
#                   control B still applied and held
#
# OK, OK_MULTISITE, OK_A_VACUOUS and A_SKIPPED mean "this row's verdict is
# about a WHOLE mutant"; the rest do not.  mc_verdict_usable is that split.

mc__detail() { printf '%s\n' "$*" >&2; }

# Split 's<d>LHS<d>RHS<d>flags' on its own delimiter, honouring backslash
# escaping of the delimiter.  Sets MC_LHS, MC_RHS, MC_FLAGS.
mc__split_sed() {
    local expr="$1" d body i ch prev field=0
    case "$expr" in
        s?*) : ;;
        *) return 1 ;;
    esac
    d="${expr:1:1}"
    body="${expr:2}"
    MC_LHS=""; MC_RHS=""; MC_FLAGS=""
    prev=""
    for (( i=0; i<${#body}; i++ )); do
        ch="${body:i:1}"
        if [ "$ch" = "$d" ] && [ "$prev" != "\\" ]; then
            field=$((field+1))
            prev="$ch"
            continue
        fi
        case $field in
            0) MC_LHS+="$ch" ;;
            1) MC_RHS+="$ch" ;;
            *) MC_FLAGS+="$ch" ;;
        esac
        prev="$ch"
    done
    [ "$field" -ge 2 ] || return 1
    return 0
}

# Turn a sed RHS into the literal text it inserts, or fail if it cannot be
# one.  Handles the two escapes this repository's harnesses actually use:
# \x27 for a single quote and \& for a literal ampersand.
mc__rhs_literal() {
    local rhs="$1" out="" i ch nxt
    for (( i=0; i<${#rhs}; i++ )); do
        ch="${rhs:i:1}"
        if [ "$ch" = "\\" ]; then
            nxt="${rhs:i+1:1}"
            case "$nxt" in
                x)  # \xHH
                    local hex="${rhs:i+2:2}"
                    out+=$(printf "\\x$hex")
                    i=$((i+3)); continue ;;
                [0-9]) return 1 ;;   # back-reference: no literal exists
                n|t)   return 1 ;;   # inserted newline/tab: not a flat literal
                *)  out+="$nxt"; i=$((i+1)); continue ;;
            esac
        fi
        if [ "$ch" = "&" ]; then
            return 1                 # whole-match reference
        fi
        out+="$ch"
    done
    printf '%s' "$out"
    return 0
}

# LINES matched (= the number of substitutions sed will make, since sed
# without /g replaces the first match on each line) and OCCURRENCES matched
# (which can exceed it).  Both are needed: the difference between them is
# exactly the half-injection control B exists to catch.
mc__lines_bre()  { grep -c -e "$1" -- "$2" 2>/dev/null || true; }
mc__occ_bre()    { grep -o -e "$1" -- "$2" 2>/dev/null | wc -l | tr -d " "; }
mc__lines_fixed(){ grep -c -F -e "$1" -- "$2" 2>/dev/null || true; }
mc__occ_fixed()  { grep -o -F -e "$1" -- "$2" 2>/dev/null | wc -l | tr -d " "; }

# mc_controls_sed <original> <mutant> <sed_expr>
mc_controls_sed() {
    local orig="$1" mut="$2" expr="$3"

    if cmp -s "$orig" "$mut"; then
        mc__detail "NOT_INJECTED: the mutant is byte-identical to the original."
        echo NOT_INJECTED; return 1
    fi
    if ! mc__split_sed "$expr"; then
        mc__detail "could not parse the sed expression; controls not applied."
        echo A_SKIPPED:unparsable; return 1
    fi

    # ---- CONTROL B, on the pattern itself ---------------------------------
    local b_orig o_orig o_mut
    b_orig=$(mc__lines_bre "$MC_LHS" "$orig")   # substitutions sed will make
    o_orig=$(mc__occ_bre  "$MC_LHS" "$orig")    # occurrences present
    o_mut=$(mc__occ_bre   "$MC_LHS" "$mut")
    if [ "${b_orig:-0}" -eq 0 ]; then
        mc__detail "B_NO_ANCHOR: the pattern matches 0 lines of the ORIGINAL."
        echo B_NO_ANCHOR; return 1
    fi
    if [ "${o_mut:-0}" -ne 0 ]; then
        # Two different faults share this symptom, and they are told apart by
        # whether the count went DOWN.  A half-injection leaves FEWER
        # occurrences (sed replaced one per line and others remained); a
        # pattern that matches its own replacement leaves as many or more, and
        # then control B is vacuous rather than failing.
        if [ "${o_mut}" -ge "${o_orig:-0}" ]; then
            # Two reasons the pattern can match its own output, and they are
            # told apart by asking whether the REPLACEMENT ITSELF matches the
            # pattern.  If it does, the expression INSERTS rather than
            # replaces -- a deliberate annotation, or an anchor so loose it
            # survives its own substitution -- and control B is inapplicable
            # by construction rather than failing.
            local rhs_text byconstruction=no
            rhs_text=$(printf '%b' "$MC_RHS" 2>/dev/null || printf '%s' "$MC_RHS")
            if printf '%s\n' "$rhs_text" | grep -q -e "$MC_LHS" 2>/dev/null; then
                byconstruction=yes
            fi
            if [ "$byconstruction" = yes ]; then
                mc__detail "B_SELF_MATCHING: the REPLACEMENT itself matches the pattern, so this expression INSERTS around the anchor rather than replacing it. Control B is inapplicable by construction, not failing. Either the row's real injection happens elsewhere (an annotation marker) or the anchor is too loose to control."
            else
                mc__detail "B_SELF_MATCHING: the pattern still matches ${o_mut} occurrence(s) of the mutant against ${o_orig} in the original, so it matches its own replacement. Control B cannot be applied to an anchor this loose, and the repair is a tighter anchor -- not a looser control."
            fi
            echo B_SELF_MATCHING; return 1
        fi
        mc__detail "HALF_INJECTED: the replaced pattern still occurs ${o_mut} time(s) in the mutant, down from ${o_orig} -- sed made ${b_orig} substitution(s), one per matching line, and the rest of the occurrences survived. The mutant carries PART of the defect. cmp -s passes this row."
        echo HALF_INJECTED; return 1
    fi

    # ---- CONTROL A, on the inserted literal -------------------------------
    local to_lit a_orig a_mut
    if ! to_lit=$(mc__rhs_literal "$MC_RHS"); then
        mc__detail "A_SKIPPED: the replacement contains a back-reference or an inserted newline, so there is no literal to grep for. Control B held (anchor present in original: ${b_orig} line(s), absent from mutant)."
        if [ "${b_orig}" -gt 1 ]; then echo "A_SKIPPED:backref_multisite:${b_orig}"; else echo "A_SKIPPED:backref"; fi
        return 0
    fi
    if [ -z "$to_lit" ]; then
        mc__detail "A_SKIPPED: the replacement is empty (a deletion), so there is no inserted text. Control B held."
        echo A_SKIPPED:deletion; return 0
    fi
    a_mut=$(mc__lines_fixed "$to_lit" "$mut")
    a_orig=$(mc__lines_fixed "$to_lit" "$orig")
    if [ "${a_mut:-0}" -eq 0 ]; then
        mc__detail "A_MISSING: the inserted text is not present in the mutant."
        echo A_MISSING; return 1
    fi
    if [ "${a_orig:-0}" -ne 0 ]; then
        # Control B has already passed at this point, so the mutant IS
        # complete.  What has failed is control A: the inserted text was
        # already in the original, so grepping for it in the mutant cannot
        # fail and certifies nothing.  That distinction is the whole of the
        # 2026-10-01 lesson, so the verdict says "usable, and A was vacuous"
        # rather than "broken".
        mc__detail "OK_A_VACUOUS: control B held (the replaced pattern is gone), so the mutant is COMPLETE -- but the inserted text was ALREADY present in the original on ${a_orig} line(s), so control A cannot fail on this row and certifies nothing. A harness with control A only could not have verified this mutant."
        echo OK_A_VACUOUS; return 0
    fi

    if [ "${b_orig}" -gt 1 ]; then
        mc__detail "OK, but CONTROL C: the anchor matched ${b_orig} lines of the original, so this mutant changes ${b_orig} sites while being described as one defect."
        echo "OK_MULTISITE:${b_orig}"; return 0
    fi
    mc__detail "OK: inserted text present in mutant and absent from original; replaced pattern absent from mutant; one site."
    echo OK; return 0
}

# mc_controls_text <original> <mutant> <from_literal> <to_literal>
# For the multi-line injections this repository does with python instead of
# sed.  Both sides are FIXED strings here, so all three controls are exact.
mc_controls_text() {
    local orig="$1" mut="$2" from="$3" to="$4"
    if cmp -s "$orig" "$mut"; then
        mc__detail "NOT_INJECTED: the mutant is byte-identical to the original."
        echo NOT_INJECTED; return 1
    fi
    local f_orig f_mut t_orig t_mut l_orig
    l_orig=$(mc__lines_fixed "$from" "$orig")
    f_orig=$(mc__occ_fixed "$from" "$orig")
    f_mut=$(mc__occ_fixed "$from" "$mut")
    t_orig=$(mc__lines_fixed "$to" "$orig")
    t_mut=$(mc__lines_fixed "$to" "$mut")
    if [ "${l_orig:-0}" -eq 0 ]; then
        mc__detail "B_NO_ANCHOR: the replaced text is not in the original."
        echo B_NO_ANCHOR; return 1
    fi
    if [ "${f_mut:-0}" -ne 0 ]; then
        mc__detail "HALF_INJECTED: the replaced text still appears ${f_mut} time(s) in the mutant, down from ${f_orig}."
        echo HALF_INJECTED; return 1
    fi
    if [ "${t_mut:-0}" -eq 0 ]; then
        mc__detail "A_MISSING: the inserted text is not in the mutant."
        echo A_MISSING; return 1
    fi
    if [ "${t_orig:-0}" -ne 0 ]; then
        mc__detail "OK_A_VACUOUS: control B held, so the mutant is complete, but the inserted text was already in the original and control A certifies nothing here."
        echo OK_A_VACUOUS; return 0
    fi
    if [ "${l_orig}" -gt 1 ]; then
        mc__detail "OK, but CONTROL C: the replaced text occurred on ${l_orig} lines."
        echo "OK_MULTISITE:${l_orig}"; return 0
    fi
    mc__detail "OK: all three controls hold; one site."
    echo OK; return 0
}

# True only for verdicts that mean "the row below is about a whole mutant".
mc_verdict_usable() {
    case "$1" in
        OK|OK_MULTISITE:*|OK_A_VACUOUS|A_SKIPPED:*) return 0 ;;
        *) return 1 ;;
    esac
}
