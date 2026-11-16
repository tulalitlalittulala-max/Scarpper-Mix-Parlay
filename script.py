from datetime import datetime
import os
import tweepy
import feedparser
import pandas as pd

# ==========================================
# KONFIGURASI & KREDENSIAL
# ==========================================
TOP_N_MATCHES = 3
OUTPUT_CSV = True

# Ambil token dari environment variable/GitHub Secret.
# Jangan tulis token langsung di file atau unggah ke GitHub.
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN", "")

NEWS_RSS_FEEDS = {
    "ESPN": "https://www.espn.com/espn/rss/soccer/news",
    "BBC": "https://feeds.bbci.co.uk/sport/football/rss.xml",
}

matches = [
    {
        "match_id": "m1",
        "league": "Premier League",
        "home": "Arsenal",
        "away": "Chelsea",
        "kickoff_wib": "21:00",
    },
    {
        "match_id": "m2",
        "league": "La Liga",
        "home": "Real Madrid",
        "away": "Barcelona",
        "kickoff_wib": "02:00",
    },
    {
        "match_id": "m3",
        "league": "Serie A",
        "home": "Inter Milan",
        "away": "AC Milan",
        "kickoff_wib": "23:45",
    },
]


def fetch_twitter_sentiment_for_match(match, max_tweets=30):
    """Ambil sentimen dari Twitter/X API, atau gunakan data simulasi tanpa token."""
    if not TWITTER_BEARER_TOKEN:
        print(
            f"[Info] Token Twitter kosong untuk {match['home']} vs {match['away']}; "
            "menggunakan data simulasi."
        )
        return {"sentiment_score": 1.5, "tweets_analyzed": max_tweets}

    try:
        client = tweepy.Client(bearer_token=TWITTER_BEARER_TOKEN)
        query = f"({match['home']} OR {match['away']}) -is:retweet lang:en"
        response = client.search_recent_tweets(query=query, max_results=max_tweets)

        score = 0
        count = 0
        if response.data:
            for tweet in response.data:
                count += 1
                text = tweet.text.lower()
                if any(word in text for word in ["win", "goal", "fit", "top"]):
                    score += 1
                if any(word in text for word in ["injury", "out", "loss", "doubt"]):
                    score -= 1

        avg_score = round(score / count, 2) if count > 0 else 0.0
        return {"sentiment_score": avg_score, "tweets_analyzed": count}
    except Exception as exc:
        print(f"Error Twitter API: {exc}")
        return {"sentiment_score": 0.0, "tweets_analyzed": 0}


def fetch_news_for_match(match, rss_feeds):
    """Ambil berita terkini dari RSS feed yang menyebut salah satu tim."""
    home = match["home"].lower()
    away = match["away"].lower()
    matched = []

    for source, url in rss_feeds.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                blob = f"{entry.get('title', '')} {entry.get('summary', '')}".lower()
                if home in blob or away in blob:
                    matched.append({"title": entry.get("title", ""), "source": source})
                    if len(matched) >= 3:
                        break
        except Exception as exc:
            print(f"Error RSS {source}: {exc}")
        if len(matched) >= 3:
            break

    if not matched:
        matched = [
            {"title": f"Pratinjau pertandingan {match['home']} vs {match['away']}."}
        ]
    return matched


def simple_rank_match(data):
    score = 5.0
    score += data.get("twitter_sentiment", 0) * 1.2
    score += data.get("motivation", 0) * 0.8
    if data.get("lineup_confirmed"):
        score += 1.0
    score -= data.get("injuries", 0) * 0.5
    return round(min(max(score, 1.0), 10.0), 1)


def main():
    results = []
    for match in matches:
        signals = {
            "injuries": 0,
            "lineup_confirmed": True,
            "motivation": 2,
            "recent_form": 2,
        }

        print(f"Menganalisis: {match['home']} vs {match['away']}...")
        twitter_data = fetch_twitter_sentiment_for_match(match)
        news_data = fetch_news_for_match(match, NEWS_RSS_FEEDS)

        score = simple_rank_match(
            {
                "twitter_sentiment": twitter_data.get("sentiment_score", 0),
                "lineup_confirmed": signals["lineup_confirmed"],
                "motivation": signals["motivation"],
                "injuries": signals["injuries"],
            }
        )

        results.append(
            {
                "league": match["league"],
                "home": match["home"],
                "away": match["away"],
                "kickoff_wib": match["kickoff_wib"],
                "score": score,
                "twitter_sentiment": twitter_data.get("sentiment_score", 0),
                "news_headlines": " | ".join(
                    headline["title"] for headline in news_data[:3]
                ),
            }
        )

    results_sorted = sorted(results, key=lambda result: result["score"], reverse=True)
    top_matches = results_sorted[:TOP_N_MATCHES]
    dataframe = pd.DataFrame(top_matches)

    print("\n--- Hasil Ringkasan Pilihan Hari Ini ---")
    print(dataframe.to_string(index=False))

    if OUTPUT_CSV:
        dataframe.to_csv("picks_today.csv", index=False)
        print("\nHasil berhasil disimpan ke picks_today.csv")


if __name__ == "__main__":
    main()
