#!/usr/bin/env bash
# Seed TRUST.md with a realistic 30-day history, then print the agent's status.
#
# History shape: steady small low-stake wins, one small mistake (a reverted
# low-stake reformat), one reverted medium-stake README edit, and one solid
# medium-stake win late in the month. Reseeding resets TRUST.md, so this
# script is idempotent.
set -euo pipefail
cd "$(dirname "$0")/.."

python3 - <<'PY'
import datetime as dt
from pathlib import Path

import trust

Path(trust.LEDGER_DEFAULT).write_text(
    trust.LEDGER_HEADER + "\n", encoding="utf-8")

now = dt.datetime.now()

# (days_ago, hour, decision_type, stake, outcome), oldest first
history = [
    (29, 10, "close_issue",     "low", "accepted"),
    (27, 10, "label_issue",     "low", "accepted"),
    (26, 11, "close_issue",     "low", "accepted"),
    (25, 15, "link_dupes",      "low", "merged"),
    (24, 10, "close_issue",     "low", "accepted"),
    (22,  9, "close_issue",     "low", "accepted"),
    (21, 16, "format_code",     "low", "reverted"),   # the one small mistake
    (20, 10, "label_issue",     "low", "accepted"),
    (19, 11, "close_issue",     "low", "accepted"),
    (18, 14, "summarize_thread", "low", "merged"),
    (16, 16, "edit_readme",     "med", "reverted"),   # the reverted med-stake edit
    (15, 10, "close_issue",     "low", "accepted"),
    (13,  9, "close_issue",     "low", "accepted"),
    (12, 15, "pin_issue",       "low", "merged"),
    (11, 10, "close_issue",     "low", "accepted"),
    ( 9, 11, "label_issue",     "low", "accepted"),
    ( 8, 10, "close_issue",     "low", "accepted"),
    ( 7, 13, "refactor_tests",  "med", "merged"),     # a solid med-stake win
    ( 6, 10, "close_issue",     "low", "accepted"),
    ( 4,  9, "close_issue",     "low", "accepted"),
    ( 3, 15, "link_dupes",      "low", "merged"),
    ( 2, 10, "close_issue",     "low", "accepted"),
    ( 1, 11, "close_issue",     "low", "accepted"),
]

for days_ago, hour, dtype, stake, outcome in history:
    ts = (now - dt.timedelta(days=days_ago)).replace(
        hour=hour, minute=0, second=0, microsecond=0)
    trust.append(ts.strftime("%Y-%m-%dT%H:%M"), dtype, stake, outcome)

print(f"seeded {len(history)} decisions into {trust.LEDGER_DEFAULT}\n")
PY

python3 trust.py status

echo
echo "--- gate checks ---"
python3 trust.py may close_issue --stake low
python3 trust.py may edit_readme --stake med || true
