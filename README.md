# trust-ledger (PoC)

Trust as a computable scalar for an AI agent. `TRUST.md` is an append-only
ledger with one line per decision the agent took, and `trust.py` turns that
ledger into an autonomy score, per-stake ceilings, and an explanation a human
(Casey) can audit line by line. Python 3 stdlib only.

## Why

Trust compounds on observed correct ACTION, not on wakeups. An agent that
skips opportunities earns nothing: skips are invisible and compound nothing.
An agent that acts and is confirmed earns a little each time; an agent that
acts wrongly pays. The score is never stored — it is always re-derived from
the ledger, so it decays as decisions age out of a 30-day window unless the
agent keeps acting well.

## Ledger schema (TRUST.md)

    ts | decision_type | stake | outcome | autonomy_delta

e.g. `2026-10-17T14:00 | close_issue | low | accepted | +0.01`

- stakes: `low | med | high`; outcomes: `accepted | merged | reverted | rejected`
- blank lines and `#` comments are tolerated; anything else raises a clean error
- the parser also rejects recorded deltas inconsistent with the table below
  (only capped positives, see failure modes, may record `+0.00`)

## Delta table and rationale

| outcome \ stake | low    | med    | high    |
|-----------------|--------|--------|---------|
| accepted        | +0.01  | +0.04  | +0.08   |
| merged          | +0.02  | +0.05  | +0.10   |
| reverted        | -0.01  | -0.04  | -0.08   |
| rejected        | -0.02  | -0.05  | -0.10   |

- `merged` beats `accepted`: a human reviewed and merged it — stronger
  confirmation than an action that merely stood.
- `rejected` costs more than `reverted`: a refusal/override is a louder "no"
  than someone quietly undoing the work.
- Magnitude scales with stake: a high-stake call is ~2x a med call and
  4–8x a low call, because being wrong where it matters should hurt.

## Score, ceilings, gates

- `autonomy_score` = sum of deltas in the last 30 days, clamped to [0, 1];
  decisions older than the window age out (trust decays without action).
- ceilings: low 0.2, med 0.5, high 0.8; the agent may act alone at a stake
  level only when score >= that ceiling.
- `explain()` shows the score, each gate verdict, the last 5 decisions, and
  the single most impactful recent decision — so a human can see exactly why
  the agent did or didn't act.

## Failure modes and mitigations

- **Score inflation via cheap low-stake wins** (spam `close_issue low
  accepted` all day). Mitigation, implemented in `append()`: at most
  `MAX_POSITIVE_PER_TYPE_PER_DAY = 3` positive entries per decision_type per
  calendar day earn their delta; further same-type wins that day are still
  recorded but earn `+0.00`. Negative deltas are never capped.
- **Drift via hand-edited history.** The ledger is append-only by convention
  and the parser validates every recorded delta against the table, so a
  forged `+0.05` on an `accepted/low` line fails loudly.
- **Stale trust.** The rolling window ages everything out after 30 idle
  days; the score falls to 0.00 and the agent must re-earn autonomy.

## How to run

    python3 trust.py add 2026-10-17T14:00 close_issue low accepted
    python3 trust.py add now edit_readme med merged
    python3 trust.py status
    python3 trust.py may close_issue --stake low   # exit 0 = may act, 1 = ask a human

    python3 -m unittest discover -s tests -v       # 20 tests
    bash scripts/demo.sh                           # reseed + 30-day history + status

`--ledger PATH` overrides the default `TRUST.md` in the current directory.
See RESULTS.md for a measured demo run and what the agent is allowed to do.
