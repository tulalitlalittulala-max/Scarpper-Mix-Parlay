# Scarpper-Mix-Parlay

A small Python tool that reads football fixtures from CSV, optionally checks public posts through the X API, scans ESPN/BBC football RSS feeds for headlines, and writes a ranked CSV summary.

> **Disclaimer:** Scores are a simple, configurable heuristic—not match probabilities, guaranteed predictions, or betting advice. The sample fixture list and signal values are examples; keep them up to date yourself.

## Requirements

- Python 3.10 or newer
- Internet access for RSS feeds
- An X API bearer token only if you want live X search. X API access and endpoint availability depend on your account/plan.

## Install

```bash
python -m venv .venv
```

Activate the virtual environment:

- macOS/Linux: `source .venv/bin/activate`
- Windows PowerShell: `.venv\\Scripts\\Activate.ps1`

Then install dependencies:

```bash
python -m pip install -r requirements.txt
```

## Configure live X API (optional)

Copy `.env.example` to `.env` and add your bearer token:

```dotenv
TWITTER_BEARER_TOKEN=your_token_here
```

Do not commit `.env` or share your token. `.gitignore` excludes it. If the token is absent, the program still runs, but X sentiment is disabled and set to zero. API errors are logged and do not stop RSS processing.

## Enter fixtures

Edit `matches.csv`. Required columns are `league`, `home`, and `away`; the other columns are optional:

- `match_id`: fixture identifier
- `kickoff_wib`: kickoff time label
- `motivation`: numeric heuristic input (default 2)
- `lineup_confirmed`: `true`/`false` (default false)
- `injuries`: numeric heuristic input (default 0)

Example:

```csv
match_id,league,home,away,kickoff_wib,motivation,lineup_confirmed,injuries
m1,Premier League,Arsenal,Chelsea,21:00,2,false,0
```

These signal values are supplied by you; the script does not independently verify lineups, motivation, or injuries.

## Run

```bash
python script.py
```

By default, the script reads `matches.csv`, ranks at most three fixtures, prints the results, and writes `picks_today.csv`.

Options:

```bash
python script.py --matches my_fixtures.csv --output output/results.csv --top 5 --max-tweets 30
```

`--max-tweets` must be between 10 and 100. RSS headlines are best-effort and may be empty when feeds are unavailable or no team is mentioned.
