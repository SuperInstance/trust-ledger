# trust-ledger

Trust as a computable scalar for an AI agent: every decision the agent
takes is one line in an append-only ledger (`TRUST.md`), and `trust.py`
turns that ledger into an autonomy score with per-stake ceilings and a
line-by-line explanation a human can audit. No magic number stored in a
config — the score is always re-derived from the record, so it decays
unless the agent keeps acting well.

Built for an AI-agent maintainer team: as automated agents take more
routine actions in a repository, you need a mechanical answer to "what is
this agent currently allowed to do on its own?"

## How it works

The ledger is one pipe-separated line per decision:

    ts | decision_type | stake | outcome | autonomy_delta

e.g. `2026-10-17T14:00 | close_issue | low | accepted | +0.01`

- stakes: `low | med | high`; outcomes: `accepted | merged | reverted | rejected`
- blank lines and `#` comments are tolerated; anything else raises a clean error
- the parser also rejects recorded deltas inconsistent with the table
  below (only capped positives, see failure modes, may record `+0.00`)

Each outcome moves the score by a fixed delta — trust compounds on
observed correct **action**, never on wakeups. An agent that skips
opportunities earns nothing; an agent that acts and is confirmed earns a
little each time; an agent that acts wrongly pays.

| outcome \ stake | low    | med    | high    |
|-----------------|--------|--------|---------|
| accepted        | +0.01  | +0.04  | +0.08   |
| merged          | +0.02  | +0.05  | +0.10   |
| reverted        | -0.01  | -0.04  | -0.08   |
| rejected        | -0.02  | -0.05  | -0.10   |

- `merged` beats `accepted`: a human reviewed and merged it — stronger
  confirmation than an action that merely stood.
- `rejected` costs more than `reverted`: a refusal/override is a louder
  "no" than someone quietly undoing the work.
- Magnitude scales with stake: a high-stake call is ~2x a med call and
  4–8x a low call, because being wrong where it matters should hurt.

Score, ceilings, gates:

- `autonomy_score` = sum of deltas in the last 30 days, clamped to
  [0, 1]; decisions older than the window age out (trust decays without
  action).
- ceilings: low 0.2, med 0.5, high 0.8; the agent may act alone at a
  stake level only when score >= that ceiling.
- `explain()` shows the score, each gate verdict, the last 5 decisions,
  and the single most impactful recent decision — so a human can see
  exactly why the agent did or didn't act.

## Quickstart

Python 3, stdlib only — clone and run:

    git clone https://github.com/SuperInstance/trust-ledger
    cd trust-ledger
    python3 -m unittest discover -s tests -v   # 20 tests
    bash scripts/demo.sh                       # reseed + 30-day history + status

The demo reseeds `TRUST.md` with a realistic 30-day history (23
decisions) and prints the full status plus gate checks. Then drive the
CLI yourself:

    python3 trust.py status
    python3 trust.py add now close_issue low accepted
    python3 trust.py may close_issue --stake low   # exit 0 = may act, 1 = ask a human

`--ledger PATH` overrides the default `TRUST.md` in the current
directory.

## Results

Measured run of `bash scripts/demo.sh` on 2026-10-16 (the script
reseeds the ledger, so re-running reproduces this shape with fresh
dates) — full transcript in [RESULTS.md](RESULTS.md):

- autonomy score **0.24** (rolling 30-day sum, 23/23 decisions in window)
- gates: **may act autonomously** at low stake (0.24 >= 0.20); must ask
  a human at med (0.50) and high (0.80)
- most impactful recent decision: a human-merged med-stake test refactor
  (+0.05) — worth more than any five individual issue closes
- test suite: 20 tests, all passing

Interpretation: the score is carried by a steady drip of small confirmed
wins, held back by one reverted reformat and one reverted med-stake
README edit. The cheap-but-confirmed path to med-stake autonomy is
visible in the ledger itself.

## Failure modes and mitigations

- **Score inflation via cheap low-stake wins** (spam `close_issue low
  accepted` all day). Mitigation, implemented in `append()`: at most
  `MAX_POSITIVE_PER_TYPE_PER_DAY = 3` positive entries per
  decision_type per calendar day earn their delta; further same-type
  wins that day are still recorded but earn `+0.00`. Negative deltas
  are never capped.
- **Drift via hand-edited history.** The ledger is append-only by
  convention and the parser validates every recorded delta against the
  table, so a forged `+0.05` on an `accepted/low` line fails loudly.
- **Stale trust.** The rolling window ages everything out after 30 idle
  days; the score falls to 0.00 and the agent must re-earn autonomy.

## The SuperInstance ecosystem

This ledger is one instrument in a small constellation of research
repos around [zero-poc](https://github.com/SuperInstance/zero-poc), a
git-native AI agent:

- [zero-poc](https://github.com/SuperInstance/zero-poc) — the agent this ledger gates
- [decision-ledger](https://github.com/SuperInstance/decision-ledger) — filing every decision-model answer
- [pacemaker](https://github.com/SuperInstance/pacemaker) — circadian heartbeat dispatcher
- [drift-probe](https://github.com/SuperInstance/drift-probe) — repo-drift detection
- [vision](https://github.com/SuperInstance/vision) — the roadmap

## Status and limitations

Proof of concept, not production tooling. Honest limits:

- The delta table and ceilings are hand-tuned heuristics, not fitted
  values; reasonable people will disagree with the exact numbers.
- Outcomes (`accepted`, `merged`, ...) are adjudicated by a human — the
  ledger records judgments, it does not make them.
- Append-only is a convention plus parse-time validation, not a
  cryptographic guarantee; a determined editor can rewrite history.
- Single-ledger, single-agent; no multi-agent or per-repo scoring yet.

## License

MIT — see [LICENSE](LICENSE).
