#!/usr/bin/env bash
# run one variant dir; append "<dir> <verdict>" to $RESULTS
d="$1"
( cd "$d" && rm -rf m && sby -f m.sby ) > "$d/log" 2>&1
v=$(grep -oE 'DONE \([A-Z]+' "$d/log" | tail -1 | sed 's/DONE (//')
[ -n "$v" ] || v=NONE
echo "$d $v" >> "$RESULTS"
