#!/usr/bin/env bash
# tools/run_all_harnesses.sh -- 2026-10-16
#
# NOTHING IN THIS REPOSITORY READ ANY RUNNER'S EXIT CODE UNTIL THIS FILE
# EXISTED.
#
# The 2026-10-15 provenance audit measured it: 49 committed reports whose
# runner nothing in this repository invokes, and six mutation runners that
# reference each other only in prose.  The 2026-10-14 failure -- two harnesses
# that had not compiled since the 2026-09-27 bfm/ refactor -- took SEVENTEEN
# SESSIONS to surface, and the entry that found it named the cause plainly:
# nothing re-runs the scripts.  An exit code nobody reads is not a check; it
# is a number written to a terminal that closed.
#
# This script is the caller.  It makes every runner's exit code load-bearing
# for the first time, and it calls the provenance audit FIRST, which is the
# 2026-10-15 item "make the provenance audit a test, not a report".
#
# THREE CLASSES, AND THE POINT IS THAT THERE IS NO FOURTH
# -------------------------------------------------------
# Every path the discovery rule finds must appear in the MANIFEST below with
# a kind.  A file that is neither run nor declared a non-harness is a
# MANIFEST_GAP and fails this script.  That is deliberate and it is the whole
# mechanism: the 2026-09-27 refactor was invisible for seventeen sessions
# because a harness can stop being run without anything saying so, and a
# runner added tomorrow must not be able to join that set by default.  (The
# graphene repository reached the same rule from the other side on 2026-10-14:
# an unassigned member of a patch set is refused rather than silently left
# at its shipped object.)
#
#   HARNESS        run it; a nonzero exit fails this script
#   NOT_A_HARNESS  declared, with a reason, and not run
#   (absent)       MANIFEST_GAP -- fails this script
#
# A MISSING TOOL IS NOT A BROKEN HARNESS, AND THE DIFFERENCE IS DECLARED
# ----------------------------------------------------------------------
# Several suites need a toolchain this environment may not have (SymbiYosys
# for the formal suites, cocotb for the uvm-python ones).  Inferring "tool
# absent" from a crash would be guessing at a cause from a symptom, so each
# HARNESS declares a `requires` command.  If that command is absent the suite
# is SKIPPED -- counted, printed, and never silently folded into either PASS
# or FAIL.  A skip whose prerequisite IS present and which still fails is a
# failure, which is the case this file exists to catch.
#
# THERE IS DELIBERATELY NO EXPECTED-FAIL LIST
# ------------------------------------------
# The obvious next feature is a column saying "this one is known-red, do not
# count it", so the script can exit 0 while the repository still has failing
# harnesses.  That is not an oversight.  It is a green claim over a red guard
# -- the exact thing the sibling graphene repository spent 2026-10-16
# removing, after shipping one for twelve days -- and once this script exits 0
# with real failures inside it, its exit code means nothing again and we are
# back where 2026-10-15 found us.  While a harness is red, this script is red.
# The AUTOMATION_LOG entry names the red set and what clears it.
#
# THE RATCHET
# -----------
# The provenance audit's own headline -- suites that have a runner and no
# current report -- is 5 as of 2026-10-15.  Requiring 0 today would make this
# script fail on arrival and be disabled within a session, so it is a BUDGET
# that may only go down (STALE_SUITE_BUDGET).  Exceeding it fails; coming in
# under it fails too, with an instruction to lower the budget, because a
# ratchet nobody tightens is a ratchet at its starting value forever.
#
# Usage:
#   bash tools/run_all_harnesses.sh                 # everything
#   bash tools/run_all_harnesses.sh --list          # the manifest, no runs
#   bash tools/run_all_harnesses.sh --only phase6   # paths matching a regex
#   bash tools/run_all_harnesses.sh --quick         # HARNESSes with budget<=30s
#   bash tools/run_all_harnesses.sh --chunk 1/2     # a reproducible half

set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

STALE_SUITE_BUDGET=5          # 2026-10-15's per-suite headline; lower, never raise
LOGDIR="$(mktemp -d /tmp/run_all_harnesses.XXXXXX)"

# ---------------------------------------------------------------------------
# MANIFEST: path | kind | requires | budget_s | note
# `requires` is a command that must be on PATH, or '-' for none.
# ---------------------------------------------------------------------------
read -r -d '' MANIFEST <<'EOM'
tools/report_provenance_audit.py|HARNESS|-|120|runs FIRST: what re-runs each harness, and is its report about it
tools/harness_file_closure_audit.py|HARNESS|-|120|which files each harness actually reads
tools/shared_scratch_audit.py|HARNESS|-|120|no harness writes scratch to a fixed path another session can own
tools/open_item_staleness_audit.py|HARNESS|-|120|open-item ages across both repositories
tools/scoreboard_dut_signal_census.py|HARNESS|-|120|every DUT signal a checker reads, and in what role
tools/audit_mutation_anchors.sh|HARNESS|-|60|every mutation sed anchor still matches its target
tools/test_mutation_controls.sh|HARNESS|-|120|self-test of the shared mutation-control library
examples/phase1_mutation/run_mutation_tests.py|HARNESS|-|120|Phase 1 mutation suite
examples/phase4_ral/run_mutation_tests.sh|HARNESS|cocotb-config|300|Phase 4 RAL mutation suite; drives the DUT through uvm-python
examples/phase4_uvm_milestone/run_axis_audit.py|HARNESS|-|180|coverage-axis audit of the UVM milestone
examples/phase4_uvm_milestone/run_phase4_uvm.sh|HARNESS|cocotb-config|600|the UVM environment; needs cocotb + uvm-python
examples/phase5_csr_formal/run_csr_formal.sh|HARNESS|sby|600|CSR formal properties
examples/phase5_csr_formal/run_reset_formal.sh|HARNESS|sby|600|reset formal properties
examples/phase5_formal_uart/run_formal.sh|HARNESS|sby|900|UART formal properties
examples/phase5_property_coverage/run_property_coverage.sh|HARNESS|sby|900|per-property coverage sweep
examples/phase6_baud_error_coverage/run_baud_cov.sh|HARNESS|-|300|baud-error coverage bench
examples/phase6_baud_error_coverage/run_mutation_tests.sh|HARNESS|-|300|baud-error mutation suite
examples/phase6_bfm_equivalence/run_bfm_equiv.sh|HARNESS|-|300|BFM-vs-pin equivalence bench
examples/phase6_bfm_equivalence/run_mutation_tests.sh|HARNESS|-|300|BFM equivalence mutation suite
examples/phase6_crv_uart/run_crv_cov.sh|HARNESS|-|300|constrained-random UART coverage bench
examples/phase6_crv_uart/run_mutation_tests.sh|HARNESS|-|300|CRV UART mutation suite
examples/phase6_divisor_window/run_divisor_window.sh|HARNESS|-|180|divisor-window sweep
examples/phase6_rx_pin_driver/run_mutation_tests.sh|HARNESS|-|300|RX-pin driver mutation suite
examples/phase6_rx_pin_driver/run_rx_pin.sh|HARNESS|-|180|RX-pin driver bench over a seed sweep
examples/phase6_uvm_crv_uart/run_mutation_tests.sh|HARNESS|cocotb-config|300|UVM CRV UART mutation suite; drives the DUT through uvm-python
tools/setup_iverilog.sh|NOT_A_HARNESS|-|0|environment setup; defines shell functions and must be SOURCED, not run
tools/setup_formal.sh|NOT_A_HARNESS|-|0|environment setup for yosys/SymbiYosys; sourced, not run
tools/mutation_controls.sh|NOT_A_HARNESS|-|0|library of shared mutation controls; sourced by the mutation runners
examples/phase5_property_coverage/run_one.sh|NOT_A_HARNESS|-|0|inner helper, invoked per property by run_property_coverage.sh
examples/phase5_property_coverage/run_chunk.sh|NOT_A_HARNESS|-|0|inner helper, invoked per chunk by run_property_coverage.sh
tools/run_all_harnesses.sh|NOT_A_HARNESS|-|0|this file: it is the caller, and running it from inside itself would recurse.  Declared rather than special-cased, because the discovery rule found it on its first run and an undeclared exception is the thing this script refuses
EOM

# ---------------------------------------------------------------------------
# DISCOVERY: the rule is stated here and applied by find, so the manifest is
# checked against the repository rather than against itself.
# ---------------------------------------------------------------------------
discover() {
    {
        find . -name '*.sh' -not -path './.git/*'
        find ./tools -name '*.py'
        find ./examples -name 'run*.py'
    } | sed 's#^\./##' | sort -u
}

manifest_paths() { printf '%s\n' "$MANIFEST" | awk -F'|' 'NF>1{print $1}' | sort -u; }

ONLY=''
MODE='run'
QUICK=0
CHUNK_I=0
CHUNK_N=0
while [ $# -gt 0 ]; do
    case "$1" in
        --list)  MODE='list' ;;
        --only)  shift; ONLY="${1:-}" ;;
        --quick) QUICK=1 ;;
        --chunk) shift
                 CHUNK_I="$(printf '%s' "${1:-}" | cut -d/ -f1)"
                 CHUNK_N="$(printf '%s' "${1:-}" | cut -d/ -f2)"
                 case "$CHUNK_I/$CHUNK_N" in
                     [1-9]*/[1-9]*) ;;
                     *) echo "--chunk wants i/n, e.g. 1/2" >&2; exit 2 ;;
                 esac
                 [ "$CHUNK_I" -le "$CHUNK_N" ] || { echo "--chunk i must be <= n" >&2; exit 2; } ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
    shift
done

# --chunk exists for one reason, stated so it is not mistaken for a feature:
# the automation that drives these sessions caps a single shell call at 180
# seconds, and a full run is longer than that.  The partition is the SCRIPT's
# (HARNESS entries in manifest order, round-robin by index) and not an ad-hoc
# regex typed at the prompt, so `--chunk 1/2` and `--chunk 2/2` are a
# reproducible cover of exactly the same set a bare run covers.  Round-robin
# rather than contiguous, so one chunk does not collect every slow suite.
HIDX=0

echo "======================================================================"
echo "RUN ALL HARNESSES -- $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "the first caller in this repository that reads a runner's exit code"
echo "======================================================================"
echo "  repo root : $ROOT"
echo "  logs      : $LOGDIR"
echo

# ---------------------------------------------------------------------------
# Section 1 -- the manifest must cover the repository, in both directions
# ---------------------------------------------------------------------------
echo "----------------------------------------------------------------------"
echo "SECTION 1 -- manifest vs repository"
echo "----------------------------------------------------------------------"
DISCOVERED="$(discover)"
LISTED="$(manifest_paths)"
GAPS="$(comm -23 <(printf '%s\n' "$DISCOVERED") <(printf '%s\n' "$LISTED"))"
GHOSTS="$(comm -13 <(printf '%s\n' "$DISCOVERED") <(printf '%s\n' "$LISTED"))"
N_DISC=$(printf '%s\n' "$DISCOVERED" | grep -c . || true)
N_LIST=$(printf '%s\n' "$LISTED" | grep -c . || true)
echo "  discovered by rule : $N_DISC"
echo "  listed in manifest : $N_LIST"
STRUCT_FAIL=0
if [ -n "$GAPS" ]; then
    echo "  [FAIL] MANIFEST_GAP -- discovered but not declared:"
    printf '           %s\n' $GAPS
    echo "         a runner that is in neither class is exactly how the"
    echo "         2026-09-27 refactor stayed invisible for seventeen sessions."
    STRUCT_FAIL=1
else
    echo "  [PASS] every discovered path is declared HARNESS or NOT_A_HARNESS"
fi
if [ -n "$GHOSTS" ]; then
    echo "  [FAIL] STALE_MANIFEST -- declared but absent from the repository:"
    printf '           %s\n' $GHOSTS
    STRUCT_FAIL=1
else
    echo "  [PASS] every declared path exists"
fi
echo

if [ "$MODE" = 'list' ]; then
    echo "----------------------------------------------------------------------"
    echo "MANIFEST"
    echo "----------------------------------------------------------------------"
    printf '%s\n' "$MANIFEST" | awk -F'|' 'NF>1{printf "  %-14s %-58s req=%-14s %4ss  %s\n",$2,$1,$3,$4,$5}'
    exit $STRUCT_FAIL
fi

# ---------------------------------------------------------------------------
# Section 2 -- run every HARNESS
# ---------------------------------------------------------------------------
echo "----------------------------------------------------------------------"
echo "SECTION 2 -- every HARNESS, with its exit code read"
echo "----------------------------------------------------------------------"
N_PASS=0; N_FAIL=0; N_SKIP=0; N_TMO=0
FAILED_LIST=''
SKIPPED_LIST=''
RESULTS=''

while IFS='|' read -r path kind requires budget note; do
    [ -z "${path:-}" ] && continue
    [ "$kind" != 'HARNESS' ] && continue
    HIDX=$((HIDX+1))
    if [ -n "$ONLY" ] && ! printf '%s' "$path" | grep -Eq "$ONLY"; then continue; fi
    if [ "$QUICK" = '1' ] && [ "$budget" -gt 30 ]; then continue; fi
    if [ "$CHUNK_N" != '0' ] && [ $(( (HIDX - 1) % CHUNK_N + 1 )) != "$CHUNK_I" ]; then continue; fi

    label="$(printf '%s' "$path" | sed 's#^examples/##; s#^tools/#tools: #')"
    if [ "$requires" != '-' ] && ! command -v "$requires" >/dev/null 2>&1; then
        printf '  %-56s SKIP      (requires %s)\n' "$label" "$requires"
        N_SKIP=$((N_SKIP+1)); SKIPPED_LIST="$SKIPPED_LIST $path(needs:$requires)"
        RESULTS="$RESULTS$path|SKIP|-|$requires
"
        continue
    fi

    log="$LOGDIR/$(printf '%s' "$path" | tr '/' '_').log"
    t0=$(date +%s)
    if [ "${path##*.}" = 'py' ]; then
        timeout "$budget" python3 "$path" >"$log" 2>&1; rc=$?
    else
        timeout "$budget" bash "$path" >"$log" 2>&1; rc=$?
    fi
    t1=$(date +%s); dt=$((t1-t0))

    if [ "$rc" = '124' ]; then
        printf '  %-56s TIMEOUT   %4ss (budget %ss)\n' "$label" "$dt" "$budget"
        N_TMO=$((N_TMO+1)); N_FAIL=$((N_FAIL+1)); FAILED_LIST="$FAILED_LIST $path(timeout)"
        RESULTS="$RESULTS$path|TIMEOUT|$dt|-
"
    elif [ "$rc" = '0' ]; then
        printf '  %-56s PASS      %4ss\n' "$label" "$dt"
        N_PASS=$((N_PASS+1))
        RESULTS="$RESULTS$path|PASS|$dt|-
"
    else
        printf '  %-56s FAIL rc=%-3s %4ss\n' "$label" "$rc" "$dt"
        N_FAIL=$((N_FAIL+1)); FAILED_LIST="$FAILED_LIST $path(rc=$rc)"
        RESULTS="$RESULTS$path|FAIL|$dt|rc=$rc
"
        echo "        last 12 lines of output:"
        tail -12 "$log" | sed 's/^/          | /'
    fi
done <<< "$MANIFEST"

# ---------------------------------------------------------------------------
# Section 3 -- the ratchet on the provenance audit's own headline
# ---------------------------------------------------------------------------
echo
echo "----------------------------------------------------------------------"
echo "SECTION 3 -- the provenance audit as a test, not a report"
echo "----------------------------------------------------------------------"
RATCHET_FAIL=0
PROV_LOG="$LOGDIR/tools_report_provenance_audit.py.log"
if [ -f "$PROV_LOG" ]; then
    # The audit prints: "N suite(s) with a runner have NO CURRENT REPORT."
    # Parsed strictly rather than loosely: 2026-10-14 reported modules called
    # `whil` and `fo` off a lenient parser, and an unreadable number here must
    # fail rather than default (2026-10-09's false-fresh inversion).
    STALE_SUITES=$(grep -Eo '[0-9]+ suite\(s\) with a runner have NO CURRENT REPORT' "$PROV_LOG" \
                   | grep -Eo '^[0-9]+' | tail -1)
    if [ -z "${STALE_SUITES:-}" ]; then
        echo "  [FAIL] could not read the per-suite headline out of the audit's output."
        echo "         The ratchet cannot be enforced on a number it cannot find, and"
        echo "         silently passing would be a false fresh -- the inversion this"
        echo "         repository named on 2026-10-09."
        RATCHET_FAIL=1
    else
        echo "  suites with a runner and no current report : $STALE_SUITES"
        echo "  declared budget                            : $STALE_SUITE_BUDGET"
        if [ "$STALE_SUITES" -gt "$STALE_SUITE_BUDGET" ]; then
            echo "  [FAIL] over budget by $((STALE_SUITES-STALE_SUITE_BUDGET))."
            RATCHET_FAIL=1
        elif [ "$STALE_SUITES" -lt "$STALE_SUITE_BUDGET" ]; then
            echo "  [FAIL] UNDER budget -- lower STALE_SUITE_BUDGET to $STALE_SUITES in this file."
            echo "         A ratchet nobody tightens sits at its starting value forever."
            RATCHET_FAIL=1
        else
            echo "  [PASS] at budget."
        fi
    fi
else
    echo "  [SKIP] the provenance audit did not run in this invocation"
    echo "         (--only / --quick selection), so the ratchet is not evaluated."
fi

# ---------------------------------------------------------------------------
echo
echo "======================================================================"
echo "SUMMARY"
echo "======================================================================"
printf '  PASS %d   FAIL %d (of which TIMEOUT %d)   SKIP %d\n' \
       "$N_PASS" "$N_FAIL" "$N_TMO" "$N_SKIP"
[ -n "$SKIPPED_LIST" ] && { echo "  skipped (declared prerequisite absent):"; printf '    %s\n' $SKIPPED_LIST; }
[ -n "$FAILED_LIST" ]  && { echo "  failed:"; printf '    %s\n' $FAILED_LIST; }
echo "  manifest structure : $([ "$STRUCT_FAIL" = 0 ] && echo OK || echo BROKEN)"
echo "  ratchet            : $([ "$RATCHET_FAIL" = 0 ] && echo OK || echo BROKEN)"
echo "  logs kept at       : $LOGDIR"
RC=0
[ "$N_FAIL" -gt 0 ] && RC=1
[ "$STRUCT_FAIL" != 0 ] && RC=1
[ "$RATCHET_FAIL" != 0 ] && RC=1
echo "  exit               : $RC"
echo "======================================================================"
exit $RC
