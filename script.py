"""Rank football fixtures using simple Twitter/X and RSS signals.

This is an experimental information summary, not a match prediction or betting advice.
"""

from __future__ import annotations

import argparse
import csv
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any

import feedparser
import pandas as pd
import tweepy
from dotenv import load_dotenv

LOGGER = logging.getLogger("match_scorer")
RSS_FEEDS = {
    "ESPN": "https://www.espn.com/espn/rss/soccer/news",
    "BBC": "https://feeds.bbci.co.uk/sport/football/rss.xml",
}
REQUIRED_COLUMNS = {"league", "home", "away"}
POSITIVE_WORDS = {"win", "goal", "fit", "top"}
NEGATIVE_WORDS = {"injury", "out", "loss", "doubt"}


def load_matches(path: Path) -> list[dict[str, Any]]:
    """Load fixtures from CSV and validate required fields."""
    if not path.is_file():
        raise FileNotFoundError(f"Fixture CSV not found: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        columns = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - columns
        if missing:
            raise ValueError(f"CSV is missing required columns: {', '.join(sorted(missing))}")

        matches = []
        for row_number, row in enumerate(reader, start=2):
            match = {key: (value or "").strip() for key, value in row.items() if key}
            for field in REQUIRED_COLUMNS:
                if not match.get(field):
                    raise ValueError(f"CSV row {row_number}: '{field}' cannot be empty")
            match.setdefault("match_id", f"match-{row_number - 1}")
            match.setdefault("kickoff_wib", "")
            match.setdefault("motivation", "2")
            match.setdefault("lineup_confirmed", "false")
            match.setdefault("injuries", "0")
            matches.append(match)

    if not matches:
        raise ValueError(f"No fixtures found in {path}")
    return matches


def parse_number(match: dict[str, Any], key: str, default: float) -> float:
    value = match.get(key, "")
    if value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Fixture {match.get('match_id')}: '{key}' must be a number") from exc


def parse_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "confirmed"}


def fetch_twitter_sentiment(
    match: dict[str, Any], bearer_token: str, max_tweets: int = 30
) -> dict[str, Any]:
    """Fetch recent public posts when an X API bearer token is configured."""
    if not bearer_token:
        return {"sentiment_score": 0.0, "tweets_analyzed": 0, "status": "disabled"}

    query = f'("{match["home"]}" OR "{match["away"]}") -is:retweet lang:en'
    try:
        client = tweepy.Client(bearer_token=bearer_token, wait_on_rate_limit=True)
        response = client.search_recent_tweets(query=query, max_results=max_tweets)
        tweets = response.data or []
        score = 0
        for tweet in tweets:
            words = set(re.findall(r"[a-z]+", tweet.text.lower()))
            score += bool(words & POSITIVE_WORDS)
            score -= bool(words & NEGATIVE_WORDS)
        average = round(score / len(tweets), 2) if tweets else 0.0
        return {"sentiment_score": average, "tweets_analyzed": len(tweets), "status": "ok"}
    except Exception as exc:  # Network, API-access, and rate-limit errors should not stop RSS processing.
        LOGGER.warning("X API request failed for %s vs %s: %s", match["home"], match["away"], exc)
        return {"sentiment_score": 0.0, "tweets_analyzed": 0, "status": "error"}


def fetch_news(match: dict[str, Any]) -> list[dict[str, str]]:
    """Get up to three RSS headlines mentioning either club."""
    home, away = match["home"].casefold(), match["away"].casefold()
    headlines: list[dict[str, str]] = []
    for source, url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                title = entry.get("title", "").strip()
                summary = entry.get("summary", "")
                if title and (home in f"{title} {summary}".casefold() or away in f"{title} {summary}".casefold()):
                    headlines.append({"title": title, "source": source})
                    if len(headlines) == 3:
                        return headlines
        except Exception as exc:
            LOGGER.warning("RSS request failed for %s: %s", source, exc)
    return headlines


def rank_match(
    match: dict[str, Any], twitter: dict[str, Any], news: list[dict[str, str]]
) -> dict[str, Any]:
    """Calculate a transparent heuristic score from 1 to 10."""
    motivation = parse_number(match, "motivation", 2)
    injuries = parse_number(match, "injuries", 0)
    lineup_confirmed = parse_bool(match.get("lineup_confirmed", "false"))

    score = 5.0 + twitter["sentiment_score"] * 1.2 + motivation * 0.8
    score += 1.0 if lineup_confirmed else 0.0
    score -= injuries * 0.5
    return {
        "match_id": match.get("match_id", ""),
        "league": match["league"],
        "home": match["home"],
        "away": match["away"],
        "kickoff_wib": match.get("kickoff_wib", ""),
        "score": round(min(max(score, 1.0), 10.0), 1),
        "twitter_sentiment": twitter["sentiment_score"],
        "tweets_analyzed": twitter["tweets_analyzed"],
        "twitter_status": twitter["status"],
        "news_headlines": " | ".join(item["title"] for item in news),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Rank fixtures using basic X and RSS signals.")
    parser.add_argument("--matches", type=Path, default=Path("matches.csv"), help="Input fixture CSV")
    parser.add_argument("--output", type=Path, default=Path("picks_today.csv"), help="Output results CSV")
    parser.add_argument("--top", type=int, default=3, help="Maximum number of results to save")
    parser.add_argument("--max-tweets", type=int, default=30, help="Tweets to request per fixture (10-100)")
    args = parser.parse_args()

    if args.top < 1:
        parser.error("--top must be at least 1")
    if not 10 <= args.max_tweets <= 100:
        parser.error("--max-tweets must be between 10 and 100")

    load_dotenv()
    bearer_token = os.getenv("TWITTER_BEARER_TOKEN", "").strip()
    try:
        matches = load_matches(args.matches)
        results = []
        for match in matches:
            LOGGER.info("Analyzing %s vs %s", match["home"], match["away"])
            twitter = fetch_twitter_sentiment(match, bearer_token, args.max_tweets)
            news = fetch_news(match)
            results.append(rank_match(match, twitter, news))

        results.sort(key=lambda result: result["score"], reverse=True)
        dataframe = pd.DataFrame(results[: args.top])
        args.output.parent.mkdir(parents=True, exist_ok=True)
        dataframe.to_csv(args.output, index=False)
        print(dataframe.to_string(index=False))
        print(f"\nSaved {len(dataframe)} result(s) to {args.output}")
        if not bearer_token:
            print("X API disabled: set TWITTER_BEARER_TOKEN in .env to enable live search.")
        return 0
    except (FileNotFoundError, ValueError, OSError) as exc:
        LOGGER.error("%s", exc)
        return 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    sys.exit(main())
