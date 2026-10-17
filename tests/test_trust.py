"""Tests for trust.py -- unittest, stdlib only, no network."""

import datetime as dt
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import trust

NOW = dt.datetime(2026, 10, 16, 12, 0)


def mkrow(days_ago, dtype, stake, outcome, hour=9):
    ts = (NOW - dt.timedelta(days=days_ago)).replace(hour=hour, minute=0)
    ts_text = ts.strftime("%Y-%m-%dT%H:%M")
    return trust.Row(ts_text, dtype, stake, outcome,
                     trust.DELTA_TABLE[(outcome, stake)])


class DeltaTableTests(unittest.TestCase):
    def test_delta_table_values(self):
        bands = {"low": (0.01, 0.02), "med": (0.04, 0.05), "high": (0.08, 0.10)}
        for (outcome, stake), delta in trust.DELTA_TABLE.items():
            with self.subTest(outcome=outcome, stake=stake):
                sign = 1 if outcome in ("accepted", "merged") else -1
                lo, hi = bands[stake]
                self.assertEqual(sign, (1 if delta > 0 else -1))
                self.assertTrue(lo <= abs(delta) <= hi,
                                f"|{delta}| outside {stake} band {lo}-{hi}")
        self.assertEqual(trust.DELTA_TABLE[("merged", "high")], 0.10)
        self.assertEqual(trust.DELTA_TABLE[("rejected", "med")], -0.05)
        self.assertEqual(trust.DELTA_TABLE[("reverted", "med")], -0.04)

    def test_delta_for_rejects_bad_arguments(self):
        with self.assertRaises(trust.TrustLedgerError):
            trust.delta_for("close_issue", "huge", "accepted")
        with self.assertRaises(trust.TrustLedgerError):
            trust.delta_for("close_issue", "low", "loved")
        with self.assertRaises(trust.TrustLedgerError):
            trust.delta_for("", "low", "accepted")
        self.assertEqual(trust.delta_for("close_issue", "low", "accepted"), 0.01)


class ScoreTests(unittest.TestCase):
    def test_score_is_rolling_sum(self):
        rows = [mkrow(3, "close_issue", "low", "accepted"),
                mkrow(2, "link_dupes", "low", "merged"),
                mkrow(1, "format_code", "low", "reverted")]
        # +0.01 +0.02 -0.01
        self.assertEqual(trust.autonomy_score(rows, now=NOW), 0.02)

    def test_score_clamps_at_one(self):
        rows = [mkrow(d, "edit_readme", "high", "merged") for d in range(1, 20)]
        self.assertEqual(trust.autonomy_score(rows, now=NOW), 1.0)

    def test_score_clamps_at_zero(self):
        rows = [mkrow(d, "edit_readme", "med", "rejected") for d in range(1, 20)]
        self.assertEqual(trust.autonomy_score(rows, now=NOW), 0.0)

    def test_window_ages_out_old_decisions(self):
        rows = [mkrow(45, "close_issue", "low", "accepted"),
                mkrow(29, "close_issue", "low", "accepted")]
        score = trust.autonomy_score(rows, now=NOW)
        self.assertEqual(score, 0.01)  # the 45-day-old row no longer counts

    def test_window_boundary_is_inclusive(self):
        # exactly 30 days old is still inside the default 30-day window
        boundary = (NOW - dt.timedelta(days=30)).strftime("%Y-%m-%dT%H:%M")
        rows = [trust.Row(boundary, "close_issue", "low", "accepted", 0.01)]
        self.assertEqual(trust.autonomy_score(rows, now=NOW), 0.01)
        older = (NOW - dt.timedelta(days=30, seconds=1)).strftime("%Y-%m-%dT%H:%M")
        rows = [trust.Row(older, "close_issue", "low", "accepted", 0.01)]
        self.assertEqual(trust.autonomy_score(rows, now=NOW), 0.0)


class CeilingGateTests(unittest.TestCase):
    def test_ceiling_values(self):
        self.assertEqual(trust.autonomy_ceiling("low"), 0.2)
        self.assertEqual(trust.autonomy_ceiling("med"), 0.5)
        self.assertEqual(trust.autonomy_ceiling("high"), 0.8)
        with self.assertRaises(trust.TrustLedgerError):
            trust.autonomy_ceiling("extreme")

    def test_may_act_autonomously_gates(self):
        rows = [mkrow(d, "close_issue", "low", "accepted") for d in range(1, 23)]
        # 22 * +0.01 = 0.22: above the low ceiling, below med and high
        self.assertTrue(trust.may_act_autonomously(rows, "low", now=NOW))
        self.assertFalse(trust.may_act_autonomously(rows, "med", now=NOW))
        self.assertFalse(trust.may_act_autonomously(rows, "high", now=NOW))
        empty = trust.autonomy_score([], now=NOW)
        self.assertEqual(empty, 0.0)
        self.assertFalse(trust.may_act_autonomously([], "low", now=NOW))


class AppendTests(unittest.TestCase):
    def test_append_computes_delta_and_writes_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = os.path.join(tmp, "TRUST.md")
            row = trust.append("2026-10-01T09:00", "close_issue", "low", "accepted",
                               ledger=ledger)
            self.assertEqual(row.delta, 0.01)
            text = Path(ledger).read_text()
            self.assertIn("2026-10-01T09:00 | close_issue | low | accepted | +0.01", text)
            # header comments were written for a fresh ledger
            self.assertTrue(text.startswith("#"))
            self.assertEqual(len(trust.load_ledger(ledger)), 1)

    def test_append_now_keyword(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = os.path.join(tmp, "TRUST.md")
            row = trust.append("now", "close_issue", "low", "accepted", ledger=ledger)
            self.assertTrue(re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", row.ts))
            with self.assertRaises(trust.TrustLedgerError):
                trust.append("yesterday-ish", "close_issue", "low", "accepted", ledger=ledger)

    def test_daily_cap_on_positive_deltas(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = os.path.join(tmp, "TRUST.md")
            times = ["09:00", "10:00", "11:00", "12:00", "13:00"]
            deltas = [trust.append(f"2026-10-01T{t}", "close_issue", "low", "accepted",
                                   ledger=ledger).delta for t in times]
            self.assertEqual(deltas, [0.01, 0.01, 0.01, 0.00, 0.00])
            # a different decision_type the same day is unaffected
            d = trust.append("2026-10-01T14:00", "label_issue", "low", "accepted",
                             ledger=ledger).delta
            self.assertEqual(d, 0.01)
            # penalties are never capped
            d = trust.append("2026-10-01T15:00", "close_issue", "low", "reverted",
                             ledger=ledger).delta
            self.assertEqual(d, -0.01)
            # next day the cap resets
            d = trust.append("2026-10-02T09:00", "close_issue", "low", "accepted",
                             ledger=ledger).delta
            self.assertEqual(d, 0.01)


class ParseTests(unittest.TestCase):
    def test_parse_tolerates_comments_and_blank_lines(self):
        text = ("\n"
                "# a comment\n"
                "   \n"
                "2026-10-01T09:00 | close_issue | low | accepted | +0.01\n"
                "# another comment\n"
                "2026-10-01T10:00 | edit_readme | med | reverted | -0.04\n")
        rows = trust.parse_ledger(text)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1].decision_type, "edit_readme")
        self.assertEqual(rows[1].delta, -0.04)

    def test_parse_malformed_lines(self):
        bad_lines = [
            "garbage",                                             # too few fields
            "a | b | c | d | e | f",                               # too many fields
            "2026-13-40T09:00 | close_issue | low | accepted | +0.01",  # bad ts
            "2026-10-01T09:00 | close_issue | huge | accepted | +0.01",  # bad stake
            "2026-10-01T09:00 | close_issue | low | loved | +0.01",   # bad outcome
            "2026-10-01T09:00 | close_issue | low | accepted | 0.01",  # missing sign
            "2026-10-01T09:00 | close_issue | low | accepted | lots",  # not a number
            " | close_issue | low | accepted | +0.01",               # empty ts
        ]
        for line in bad_lines:
            with self.subTest(line=line):
                with self.assertRaises(trust.TrustLedgerError):
                    trust.parse_ledger(line)

    def test_parse_rejects_inconsistent_delta(self):
        with self.assertRaises(trust.TrustLedgerError):
            trust.parse_ledger("2026-10-01T09:00 | close_issue | low | accepted | +0.05")
        with self.assertRaises(trust.TrustLedgerError):
            trust.parse_ledger("2026-10-01T09:00 | close_issue | low | reverted | +0.01")

    def test_parse_accepts_capped_zero_delta(self):
        rows = trust.parse_ledger(
            "2026-10-01T09:00 | close_issue | low | accepted | +0.00")
        self.assertEqual(rows[0].delta, 0.0)

    def test_unparse_roundtrip(self):
        rows = [mkrow(3, "close_issue", "low", "accepted"),
                mkrow(2, "edit_readme", "med", "reverted")]
        again = trust.parse_ledger(trust.unparse_ledger(rows))
        self.assertEqual(again, rows)
        self.assertEqual(trust.format_row(rows[1]),
                         f"{rows[1].ts} | edit_readme | med | reverted | -0.04")


class ExplainTests(unittest.TestCase):
    def test_explain_sanity(self):
        rows = [mkrow(10, "close_issue", "low", "accepted") for _ in range(3)]
        rows += [mkrow(5, "edit_readme", "med", "reverted"),
                 mkrow(1, "link_dupes", "low", "merged")]
        # 3*0.01 - 0.04 + 0.02 = 0.01
        text = trust.explain(rows, now=NOW)
        self.assertIn("autonomy score: 0.01", text)
        self.assertIn("low-stake (ceiling 0.20): may NOT act autonomously", text)
        self.assertIn("med-stake (ceiling 0.50)", text)
        self.assertIn("high-stake (ceiling 0.80)", text)
        self.assertIn("last 5 decisions", text)
        self.assertIn("edit_readme", text)
        self.assertIn("link_dupes", text)
        self.assertIn("most impactful recent decision: edit_readme (med stake, reverted)", text)
        self.assertIn("-0.04", text)

    def test_explain_empty_ledger(self):
        text = trust.explain([], now=NOW)
        self.assertIn("autonomy score: 0.00", text)
        self.assertIn("no decisions recorded yet", text)
        self.assertNotIn("most impactful", text)

    def test_explain_notes_aged_out_rows(self):
        rows = [mkrow(60, "close_issue", "low", "accepted")]
        text = trust.explain(rows, now=NOW)
        self.assertIn("autonomy score: 0.00", text)
        self.assertIn("[aged out of window]", text)


if __name__ == "__main__":
    unittest.main()
