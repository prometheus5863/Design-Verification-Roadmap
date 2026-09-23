#!/usr/bin/env bash
# Run pending variants until DEADLINE seconds have elapsed, then stop.
#
# Each shell this repo's automation gets is time-limited and background jobs
# do not survive between them, so the sweep is RESUMABLE by construction: a
# variant already recorded in $RESULTS is never re-run, and calling this
# script repeatedly finishes the matrix.
DEADLINE="${DEADLINE:-155}"
WORK="${WORK:-/tmp/pcov}"
RESULTS="${RESULTS:-$WORK/results.txt}"
JOBS="${JOBS:-$WORK/jobs.txt}"
touch "$RESULTS"
start=$(date +%s)
awk '{print $1}' "$RESULTS" | sort -u > "$WORK/done.txt"
grep -vxF -f "$WORK/done.txt" "$JOBS" > "$WORK/pending.txt" || true
echo "pending: $(wc -l < "$WORK/pending.txt")"
while read -r d; do
    [ $(( $(date +%s) - start )) -ge "$DEADLINE" ] && break
    ( cd "$d" && rm -rf m && sby -f m.sby ) > "$d/log" 2>&1
    v=$(grep -oE 'DONE \([A-Z]+' "$d/log" | tail -1 | sed 's/DONE (//')
    [ -n "$v" ] || v=NONE
    echo "$d $v" >> "$RESULTS"
done < "$WORK/pending.txt"
echo "done now: $(wc -l < "$RESULTS") / $(wc -l < "$JOBS")"
