# RESULTS

Measured run of `bash scripts/demo.sh` on 2026-10-16 (the script reseeds
TRUST.md, so re-running it reproduces this shape with fresh dates):

```text
seeded 23 decisions into TRUST.md

autonomy score: 0.24
  rolling 30-day sum of autonomy_delta, clamped to [0, 1]; 23 of 23 recorded decisions are in the window

may act autonomously? (gate: score >= ceiling)
  low-stake (ceiling 0.20): MAY act autonomously
  med-stake (ceiling 0.50): may NOT act autonomously (ask a human)
  high-stake (ceiling 0.80): may NOT act autonomously (ask a human)

last 5 decisions (newest first):
  2026-10-15T11:00  close_issue        low  accepted  +0.01
  2026-10-14T10:00  close_issue        low  accepted  +0.01
  2026-10-13T15:00  link_dupes         low  merged    +0.02
  2026-10-12T09:00  close_issue        low  accepted  +0.01
  2026-10-10T10:00  close_issue        low  accepted  +0.01

most impactful recent decision: refactor_tests (med stake, merged) at 2026-10-09T13:00 -> +0.05

--- gate checks ---
MAY act autonomously: close_issue (stake=low) -- score 0.24 >= ceiling 0.20
MAY NOT act autonomously: edit_readme (stake=med) -- score 0.24 < ceiling 0.50
run `python3 trust.py status` for the full explanation
```

Test suite: `python3 -m unittest discover -s tests` — 20 tests, all passing.

## Interpretation

With a score of 0.24 the agent is currently allowed to act autonomously only
on low-stake decisions (score >= 0.20) such as closing issues and labeling,
while every medium- or high-stake action (edit_readme included) must go to a
human because it would need 0.50 or 0.80. The score is carried by a steady
drip of small confirmed wins (a month of accepted issue closes plus a few
merged cleanups) held back by one reverted low-stake reformat and the
reverted medium-stake README edit. The single most impactful recent decision
is the human-merged medium-stake test refactor (+0.05), which is doing more
for the agent's trust than any five individual issue closes and shows the
cheap-but-confirmed path to earning med-stake autonomy.
