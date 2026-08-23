#!/bin/bash
# Kuraka liveness watcher — replaces the manual "poll the files, not the clock"
# protocol (kuraka-policies §Agent liveness) with a streaming signal.
#
# Usage (orchestrator, via the Monitor tool or a background Bash task):
#   bash .claude/hooks/liveness_watch.sh <authorized-path> [more-paths...]
#
# Prints one line whenever the MOST RECENTLY modified file under the watched
# paths advances; prints a heartbeat with the age of the newest change when
# nothing moved for a full interval. Interpretation stays the policy's:
# activity = healthy (never gate a held tree); prolonged silence across >= 2
# intervals = consider intervention, snapshot first.
#
# KURAKA_LIVENESS_INTERVAL (seconds, default 60) controls the poll cadence.
set -u
[ $# -ge 1 ] || { echo "usage: liveness_watch.sh <path> [path...]" >&2; exit 1; }
INTERVAL="${KURAKA_LIVENESS_INTERVAL:-60}"

newest() {
    # newest mtime (epoch) + file across the watched paths; portable macOS/Linux
    find "$@" -type f -not -name '.*' -print0 2>/dev/null |
    xargs -0 stat -f '%m %N' 2>/dev/null ||
    find "$@" -type f -not -name '.*' -printf '%T@ %p\n' 2>/dev/null
}

last=0
while true; do
    line=$(newest "$@" | sort -rn | head -1)
    ts=${line%% *}; ts=${ts%.*}; file=${line#* }
    if [ -n "${ts:-}" ] && [ "${ts:-0}" -gt "$last" ] 2>/dev/null; then
        last="$ts"
        echo "[liveness $(date +%H:%M:%S)] activity: ${file}"
    else
        age=$(( $(date +%s) - ${last:-0} ))
        [ "$last" -eq 0 ] && msg="no files yet" || msg="quiet for ${age}s (last: ${file:-n/a})"
        echo "[liveness $(date +%H:%M:%S)] ${msg}"
    fi
    sleep "$INTERVAL"
done
