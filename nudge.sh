#!/usr/bin/env bash
# Press the cloud bot's start button if GitHub's own scheduler has not.
#
# GitHub's cron simply does not fire for this brand-new account yet -- zero
# scheduled runs in hours, through a rename and re-push. Trading still happens
# entirely on GitHub with the repository secrets; this only dispatches the
# workflow, so the laptop holds no broker credentials and cannot place an
# order itself. The workflow's concurrency group makes a dispatch landing on
# top of a real scheduled run queue, not overlap.
#
# Skips silently if the last run is fresh, so when GitHub's scheduler wakes up
# this stops doing anything at all.
set -eu
TOKEN_FILE="$HOME/.tradebot/gh_token"
[ -f "$TOKEN_FILE" ] || exit 0
TOKEN=$(cat "$TOKEN_FILE")
REPO="carwash2187-byte/trading-bot-"

# Ask for recent runs and take the newest TRADE run specifically. The naive
# per_page=1 read returns the newest run of ANY workflow -- and the heal job
# fires right after every trade, the report fires daily -- so the trade could
# look permanently fresh off the back of the very jobs that react to it,
# and the nudger would starve the thing it exists to feed.
LAST=$(curl -sf --max-time 15 \
  -H "Authorization: Bearer $TOKEN" \
  "https://api.github.com/repos/$REPO/actions/runs?per_page=15" \
  | /usr/bin/python3 -c "
import json,sys
from datetime import datetime,timezone
runs=[r for r in json.load(sys.stdin).get('workflow_runs',[]) if r['name']=='trade']
if not runs: print(9999); raise SystemExit
t=datetime.fromisoformat(runs[0]['created_at'].replace('Z','+00:00'))
print(int((datetime.now(timezone.utc)-t).total_seconds()//60))") || exit 0

if [ "$LAST" -ge 5 ]; then
  curl -sf --max-time 15 -X POST \
    -H "Authorization: Bearer $TOKEN" \
    -H "Accept: application/vnd.github+json" \
    "https://api.github.com/repos/$REPO/actions/workflows/cycle.yml/dispatches" \
    -d '{"ref":"main"}' && echo "$(date -u +%H:%M) nudged (last run ${LAST}m ago)"
else
  echo "$(date -u +%H:%M) fresh (${LAST}m); no nudge"
fi
