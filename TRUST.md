# TRUST.md - append-only decision ledger. Never edit history;
#   append only, via: python3 trust.py add <ts> <decision_type> <stake> <outcome>
# format: ts | decision_type | stake | outcome | autonomy_delta
# stakes: low | med | high   outcomes: accepted | merged | reverted | rejected
2026-09-17T10:00 | close_issue | low | accepted | +0.01
2026-09-19T10:00 | label_issue | low | accepted | +0.01
2026-09-20T11:00 | close_issue | low | accepted | +0.01
2026-09-21T15:00 | link_dupes | low | merged | +0.02
2026-09-22T10:00 | close_issue | low | accepted | +0.01
2026-09-24T09:00 | close_issue | low | accepted | +0.01
2026-09-25T16:00 | format_code | low | reverted | -0.01
2026-09-26T10:00 | label_issue | low | accepted | +0.01
2026-09-27T11:00 | close_issue | low | accepted | +0.01
2026-09-28T14:00 | summarize_thread | low | merged | +0.02
2026-09-30T16:00 | edit_readme | med | reverted | -0.04
2026-10-01T10:00 | close_issue | low | accepted | +0.01
2026-10-03T09:00 | close_issue | low | accepted | +0.01
2026-10-04T15:00 | pin_issue | low | merged | +0.02
2026-10-05T10:00 | close_issue | low | accepted | +0.01
2026-10-07T11:00 | label_issue | low | accepted | +0.01
2026-10-08T10:00 | close_issue | low | accepted | +0.01
2026-10-09T13:00 | refactor_tests | med | merged | +0.05
2026-10-10T10:00 | close_issue | low | accepted | +0.01
2026-10-12T09:00 | close_issue | low | accepted | +0.01
2026-10-13T15:00 | link_dupes | low | merged | +0.02
2026-10-14T10:00 | close_issue | low | accepted | +0.01
2026-10-15T11:00 | close_issue | low | accepted | +0.01
