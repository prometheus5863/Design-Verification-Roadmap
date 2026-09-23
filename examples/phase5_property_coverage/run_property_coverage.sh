#!/usr/bin/env bash
# examples/phase5_property_coverage/run_property_coverage.sh
#
# Phase 5, day 4 (2026-09-23): PER-PROPERTY MUTATION COVERAGE.
#
# WHY THIS EXISTS. 2026-09-22 ran a deletion experiment on exactly one
# property (R4) and found it subsumed -- deleting it changed no verdict
# anywhere. The log made "per-property mutation coverage for the whole
# suite" the top open item on the grounds that the question had just been
# shown to have a non-trivial answer and had never been asked of the
# 2026-09-20 FIFO invariants or the 2026-09-21 CSR properties.
#
# THREE PHASES, each answering what the previous one could not:
#   1  drop-one     -- delete each property in turn, re-run every mutant.
#                      Says whether a property ever changes a verdict.
#   2  solo         -- keep each candidate as the ONLY live property.
#                      Splits "changes no verdict" into SHADOWED (it can
#                      detect something, but never alone) and UNEXERCISED
#                      (no mutant in the set is visible to it at all).
#   3  gap-closing  -- inject the defects the UNEXERCISED properties were
#                      written for, and re-measure.
#
# CONTROL. Phase 1 must independently reproduce 2026-09-22's hand-built R4
# result and phase 2 must reproduce its finer form (R4 detects K3 alone but
# never uniquely). A harness that disagrees with the one answer already
# known is not believed about the answers that are new.
#
# RESUMABILITY. Every shell this repo's automation gets is time-limited and
# background jobs do not survive between them, so run_chunk.sh records each
# verdict as it lands and never re-runs a completed variant. Call it until
# it reports all jobs done.
#
# Usage:   source ../../tools/setup_formal.sh    # do NOT pipe it
#          ./run_property_coverage.sh
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
command -v sby >/dev/null 2>&1 || {
    echo "sby not on PATH -- 'source tools/setup_formal.sh' first (do NOT pipe it)"
    exit 1; }

phase() {   # phase <workdir> <build-args...>
    local work="$1"; shift
    rm -rf "$work"; mkdir -p "$work"
    python3 "$HERE/build_variants.py" "$ROOT" "$work" "$@"
    while :; do
        out=$(WORK="$work" DEADLINE="${DEADLINE:-155}" "$HERE/run_chunk.sh")
        echo "$out"
        echo "$out" | head -1 | grep -q "^pending: 0$" && break
    done
}

phase /tmp/pcov
phase /tmp/pcov2 fifo/P3 fifo/P4 csr/C1 csr/C6 csr/C7 csr/C8 reset/R2 reset/R4
phase /tmp/pcov3 --gap

python3 "$HERE/report.py"  /tmp/pcov/results.txt /tmp/pcov2/results.txt
python3 "$HERE/report2.py" /tmp/pcov2/results.txt \
        fifo/P3 fifo/P4 csr/C1 csr/C6 csr/C7 csr/C8 reset/R2 reset/R4
python3 "$HERE/report3.py" /tmp/pcov3/results.txt

