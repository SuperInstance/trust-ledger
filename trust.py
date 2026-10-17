#!/usr/bin/env python3
"""trust.py -- trust as a computable scalar for an AI agent.

TRUST.md is an append-only ledger with one line per decision the agent took:

    ts | decision_type | stake | outcome | autonomy_delta

Every decision moves the agent's autonomy_score: a rolling 30-day sum of
deltas, clamped to [0, 1]. The agent may act autonomously at a stake level
only when its score meets that level's ceiling. The score is never stored;
it is always derived from the ledger, so it is auditable line by line.

Python 3 stdlib only.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import re
import sys
from collections import namedtuple
from pathlib import Path

LEDGER_DEFAULT = "TRUST.md"
WINDOW_DAYS = 30

STAKES = ("low", "med", "high")
OUTCOMES = ("accepted", "merged", "reverted", "rejected")
POSITIVE_OUTCOMES = ("accepted", "merged")

# (outcome, stake) -> autonomy_delta
#
# accepted: the action stood on its own -- the baseline reward.
# merged:   a human reviewed and merged it; stronger confirmation than a
#           mere acceptance, so slightly larger.
# reverted: a human quietly undid the work; an ordinary mistake.
# rejected: the action was refused or overridden -- a louder negative
#           signal than a quiet revert, so slightly larger penalty.
DELTA_TABLE = {
    ("accepted", "low"): +0.01, ("accepted", "med"): +0.04, ("accepted", "high"): +0.08,
    ("merged", "low"): +0.02, ("merged", "med"): +0.05, ("merged", "high"): +0.10,
    ("reverted", "low"): -0.01, ("reverted", "med"): -0.04, ("reverted", "high"): -0.08,
    ("rejected", "low"): -0.02, ("rejected", "med"): -0.05, ("rejected", "high"): -0.10,
}

# Autonomy ceilings: the agent may act alone at a stake level only when
# autonomy_score >= that level's ceiling.
CEILINGS = {"low": 0.2, "med": 0.5, "high": 0.8}

# Anti-inflation cap: at most this many positive entries per decision_type
# per calendar day earn their delta. Further same-type wins that day are
# still recorded but earn +0.00. Negative deltas are never capped.
MAX_POSITIVE_PER_TYPE_PER_DAY = 3

LEDGER_HEADER = "\n".join([
    "# TRUST.md - append-only decision ledger. Never edit history;",
    "#   append only, via: python3 trust.py add <ts> <decision_type> <stake> <outcome>",
    "# format: ts | decision_type | stake | outcome | autonomy_delta",
    f"# stakes: {' | '.join(STAKES)}   outcomes: {' | '.join(OUTCOMES)}",
])

Row = namedtuple("Row", ["ts", "decision_type", "stake", "outcome", "delta"])

_TS_FORMATS = ("%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S")
_DELTA_RE = re.compile(r"[+-]\d+\.\d+")


class TrustLedgerError(Exception):
    """Raised for malformed ledger input or invalid trust.py arguments."""


# --------------------------------------------------------------------------
# timestamps / rows

def _parse_ts(text):
    for fmt in _TS_FORMATS:
        try:
            return _dt.datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise TrustLedgerError(f"bad timestamp {text!r} (want YYYY-MM-DDTHH:MM)")


def row_datetime(row):
    """Return the datetime of a Row."""
    return _parse_ts(row.ts)


def _clamp(value):
    return max(0.0, min(1.0, round(value, 6)))


# --------------------------------------------------------------------------
# delta policy

def delta_for(decision_type, stake, outcome):
    """Return the table delta for a would-be decision, validating arguments."""
    if not decision_type or any(ch in decision_type for ch in "|#\n"):
        raise TrustLedgerError(f"bad decision_type {decision_type!r}")
    if stake not in STAKES:
        raise TrustLedgerError(f"unknown stake {stake!r} (want one of {', '.join(STAKES)})")
    if outcome not in OUTCOMES:
        raise TrustLedgerError(f"unknown outcome {outcome!r} (want one of {', '.join(OUTCOMES)})")
    return DELTA_TABLE[(outcome, stake)]


# --------------------------------------------------------------------------
# ledger parse / unparse

def parse_ledger(text):
    """Parse ledger text into Rows.

    Tolerates blank lines and '#' comments. Raises TrustLedgerError with a
    line number on anything malformed, including a recorded delta that is
    inconsistent with DELTA_TABLE (capped positives of +0.00 are allowed).
    """
    rows = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) != 5:
            raise TrustLedgerError(
                f"line {lineno}: expected 5 '|'-separated fields, got {len(parts)}: {line!r}")
        ts, decision_type, stake, outcome, delta_text = parts
        try:
            _parse_ts(ts)
        except TrustLedgerError:
            raise TrustLedgerError(
                f"line {lineno}: bad timestamp {ts!r} (want YYYY-MM-DDTHH:MM)") from None
        if not decision_type:
            raise TrustLedgerError(f"line {lineno}: empty decision_type")
        if stake not in STAKES:
            raise TrustLedgerError(
                f"line {lineno}: unknown stake {stake!r} (want one of {', '.join(STAKES)})")
        if outcome not in OUTCOMES:
            raise TrustLedgerError(
                f"line {lineno}: unknown outcome {outcome!r} (want one of {', '.join(OUTCOMES)})")
        if not _DELTA_RE.fullmatch(delta_text):
            raise TrustLedgerError(
                f"line {lineno}: bad autonomy_delta {delta_text!r} (want e.g. +0.01)")
        delta = float(delta_text)
        expected = DELTA_TABLE[(outcome, stake)]
        if delta != expected and not (expected > 0 and delta == 0.0):
            raise TrustLedgerError(
                f"line {lineno}: autonomy_delta {delta_text} is inconsistent with the delta "
                f"table ({outcome}/{stake} -> {expected:+.2f}); only capped positives may record +0.00")
        rows.append(Row(ts, decision_type, stake, outcome, delta))
    return rows


def format_row(row):
    """Render one Row as a canonical ledger line."""
    return f"{row.ts} | {row.decision_type} | {row.stake} | {row.outcome} | {row.delta:+.2f}"


def unparse_ledger(rows):
    """Render Rows back to ledger text (data lines only, no header)."""
    return "".join(format_row(r) + "\n" for r in rows)


def load_ledger(ledger=LEDGER_DEFAULT):
    """Load Rows from a ledger file; a missing file is an empty ledger."""
    path = Path(ledger)
    if not path.exists():
        return []
    return parse_ledger(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# append

def append(ts, decision_type, stake, outcome, ledger=LEDGER_DEFAULT):
    """Append one decision to the ledger and return the Row written.

    The autonomy_delta comes from DELTA_TABLE, except that positive deltas
    are capped per decision_type per calendar day (see
    MAX_POSITIVE_PER_TYPE_PER_DAY): beyond the cap the decision is still
    recorded, with delta +0.00.
    """
    if ts == "now":
        ts = _dt.datetime.now().strftime("%Y-%m-%dT%H:%M")
    _parse_ts(ts)  # validate
    base = delta_for(decision_type, stake, outcome)

    path = Path(ledger)
    existed = path.exists()
    rows = load_ledger(path)
    day = ts[:10]
    same_day_positive = sum(
        1 for r in rows
        if r.decision_type == decision_type and r.ts[:10] == day
        and r.outcome in POSITIVE_OUTCOMES
    )
    if base > 0 and same_day_positive >= MAX_POSITIVE_PER_TYPE_PER_DAY:
        delta = 0.0
    else:
        delta = base

    row = Row(ts, decision_type, stake, outcome, delta)
    with path.open("a", encoding="utf-8") as f:
        if not existed:
            f.write(LEDGER_HEADER + "\n\n")
        f.write(format_row(row) + "\n")
    return row


# --------------------------------------------------------------------------
# score, ceilings, gates

def autonomy_score(rows, window_days=WINDOW_DAYS, now=None):
    """Rolling sum of deltas within the window, clamped to [0, 1].

    Decisions older than window_days (measured from now, wall clock by
    default) age out and stop counting: trust decays without observed action.
    """
    now = now or _dt.datetime.now()
    cutoff = now - _dt.timedelta(days=window_days)
    total = sum(r.delta for r in rows if cutoff <= _parse_ts(r.ts) <= now)
    return _clamp(total)


def autonomy_ceiling(stake):
    """Minimum autonomy_score required to act alone at this stake level."""
    try:
        return CEILINGS[stake]
    except KeyError:
        raise TrustLedgerError(
            f"unknown stake {stake!r} (want one of {', '.join(STAKES)})") from None


def may_act_autonomously(rows, stake, window_days=WINDOW_DAYS, now=None):
    """True when the current score meets the ceiling for this stake."""
    return autonomy_score(rows, window_days=window_days, now=now) >= autonomy_ceiling(stake)


# --------------------------------------------------------------------------
# explain

def explain(rows, window_days=WINDOW_DAYS, now=None):
    """Human/agent-readable report: score, gates, recent decisions, impact."""
    now = now or _dt.datetime.now()
    cutoff = now - _dt.timedelta(days=window_days)
    in_window = [r for r in rows if cutoff <= _parse_ts(r.ts) <= now]
    score = _clamp(sum(r.delta for r in in_window))

    lines = []
    lines.append(f"autonomy score: {score:.2f}")
    lines.append(f"  rolling {window_days}-day sum of autonomy_delta, clamped to [0, 1]; "
                 f"{len(in_window)} of {len(rows)} recorded decisions are in the window")
    lines.append("")
    lines.append("may act autonomously? (gate: score >= ceiling)")
    for stake in STAKES:
        ceiling = CEILINGS[stake]
        verdict = ("MAY act autonomously" if score >= ceiling
                   else "may NOT act autonomously (ask a human)")
        lines.append(f"  {stake}-stake (ceiling {ceiling:.2f}): {verdict}")
    lines.append("")

    recent = rows[-5:]
    if recent:
        lines.append(f"last {len(recent)} decisions (newest first):")
        for r in sorted(recent, key=row_datetime, reverse=True):
            aged = "" if cutoff <= _parse_ts(r.ts) else "   [aged out of window]"
            lines.append(f"  {r.ts}  {r.decision_type:<18} {r.stake:<4} {r.outcome:<9} "
                         f"{r.delta:+.2f}{aged}")
    else:
        lines.append("no decisions recorded yet: score is 0.00 and nothing is trusted "
                     "until observed action.")
    if in_window:
        top = max(in_window, key=lambda r: (abs(r.delta), _parse_ts(r.ts)))
        lines.append("")
        lines.append(f"most impactful recent decision: {top.decision_type} "
                     f"({top.stake} stake, {top.outcome}) at {top.ts} -> {top.delta:+.2f}")
    elif rows:
        lines.append("")
        lines.append(f"most impactful recent decision: none -- every recorded decision is "
                     f"older than {window_days} days, so the score has decayed to {score:.2f}.")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# CLI

def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="trust.py",
        description="TRUST.md ledger machinery: append decisions, score autonomy, gate actions.")
    parser.add_argument("--ledger", default=LEDGER_DEFAULT,
                        help="ledger path (default: %(default)s)")
    sub = parser.add_subparsers(dest="command", required=True, metavar="command")

    p_add = sub.add_parser("add", help="append a decision to the ledger")
    p_add.add_argument("ts", help="YYYY-MM-DDTHH:MM, or 'now'")
    p_add.add_argument("decision_type", help="e.g. close_issue, edit_readme")
    p_add.add_argument("stake", choices=STAKES)
    p_add.add_argument("outcome", choices=OUTCOMES)

    sub.add_parser("status", help="print the full explain() report")

    p_may = sub.add_parser("may", help="exit 0 if the agent may act autonomously, else 1")
    p_may.add_argument("decision_type", help="e.g. close_issue")
    p_may.add_argument("--stake", required=True, choices=STAKES)

    args = parser.parse_args(argv)
    try:
        if args.command == "add":
            row = append(args.ts, args.decision_type, args.stake, args.outcome,
                         ledger=args.ledger)
            note = ""
            if row.delta == 0.0 and DELTA_TABLE[(row.outcome, row.stake)] > 0:
                note = "   (capped: daily positive limit for this decision_type reached)"
            print(f"appended: {format_row(row)}{note}")
        elif args.command == "status":
            print(explain(load_ledger(args.ledger)))
        elif args.command == "may":
            rows = load_ledger(args.ledger)
            ceiling = autonomy_ceiling(args.stake)
            score = autonomy_score(rows)
            if may_act_autonomously(rows, args.stake):
                print(f"MAY act autonomously: {args.decision_type} (stake={args.stake}) "
                      f"-- score {score:.2f} >= ceiling {ceiling:.2f}")
                return 0
            print(f"MAY NOT act autonomously: {args.decision_type} (stake={args.stake}) "
                  f"-- score {score:.2f} < ceiling {ceiling:.2f}")
            print("run `python3 trust.py status` for the full explanation")
            return 1
    except TrustLedgerError as exc:
        print(f"trust.py: error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
