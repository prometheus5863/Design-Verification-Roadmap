#!/usr/bin/env bash
# repo_freshness.sh -- is the GitHub commits API a freshness oracle?  No.
#
# WHY THIS EXISTS.  On 2026-10-27 two sessions ran against this repository
# on the same day.  The second one checked whether the day's work was
# already done by reading
#
#     https://api.github.com/repos/<owner>/<repo>/commits
#
# and that endpoint still reported 2026-10-26T11:06:52Z as the tip of main
# at 10:45 UTC -- ELEVEN MINUTES after the first session had pushed e82d79b.
# So the duplicate-work guard was defeated by API caching, and the overlap
# was caught by reasoning afterwards rather than by the check.  The 10-27
# addendum recorded the fix as "read the git refs directly".
#
# This script does not merely switch to the refs.  It reads BOTH and prints
# whether they agree, because a claim that one endpoint lags another is
# worth an instrument rather than a sentence in a log: a future session
# that sees DISAGREE has measured the lag, and one that sees AGREE has
# measured that the lag was not present then.  Switching silently would
# have thrown that away.
#
# The refs path is the authority.  `git ls-remote` reads the repository's
# refs over the smart-HTTP transport and is not served from the API's cache
# layer; the commits API is a JSON view that can be stale.
#
# Usage:   tools/repo_freshness.sh <owner>/<repo> [branch]
#          GH_TOKEN=... tools/repo_freshness.sh ...   (private repos)
# Exit:    0 = the two agree.  2 = they disagree (the API is stale: trust
#          the refs).  1 = could not determine (network, bad arguments).
#
# It makes no claim about the WORKING TREE.  "Has today's work been done"
# is then one more question, answered against the authoritative sha.
set -u

usage() { sed -n '2,30p' "$0"; exit 1; }
[ $# -ge 1 ] || usage
SLUG="$1"
BRANCH="${2:-main}"

case "$SLUG" in
  */*) : ;;
  *) echo "FRESHNESS: bad slug '$SLUG' (want owner/repo)" >&2; exit 1 ;;
esac

echo "=============================================================="
echo "REPO FRESHNESS -- refs vs commits API"
echo "  repo   : $SLUG"
echo "  branch : $BRANCH"
echo "  at     : $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "=============================================================="

REF_SHA="$(git ls-remote "https://github.com/${SLUG}.git" \
           "refs/heads/${BRANCH}" 2>/dev/null | awk '{print $1}' | head -1)"
if [ -z "${REF_SHA:-}" ]; then
  echo "  refs   : UNAVAILABLE (git ls-remote failed)"
  echo "FRESHNESS: INDETERMINATE -- cannot proceed without the refs"
  exit 1
fi
echo "  refs   : $REF_SHA   <-- authoritative"

AUTH=()
if [ -n "${GH_TOKEN:-}" ]; then AUTH=(-H "Authorization: Bearer ${GH_TOKEN}"); fi
API_JSON="$(curl -sS "${AUTH[@]}" \
  "https://api.github.com/repos/${SLUG}/commits?sha=${BRANCH}&per_page=1" \
  2>/dev/null || true)"
API_SHA="$(printf '%s' "$API_JSON" \
  | tr ',' '\n' | grep -m1 '"sha"' | sed 's/.*"sha" *: *"\([0-9a-f]*\)".*/\1/')"

if [ -z "${API_SHA:-}" ]; then
  echo "  API    : UNAVAILABLE (no sha parsed)"
  echo "FRESHNESS: refs only.  Use $REF_SHA."
  exit 0
fi
echo "  API    : $API_SHA"

if [ "$REF_SHA" = "$API_SHA" ]; then
  echo "FRESHNESS: AGREE.  The API was not stale at this moment -- which is"
  echo "  a measurement, not a guarantee for the next one."
  exit 0
fi
echo "FRESHNESS: DISAGREE.  The commits API is STALE; the refs are right."
echo "  This is the 2026-10-27 condition, measured rather than inferred."
echo "  Any duplicate-work guard reading the API would now be wrong."
exit 2
