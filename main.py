"""Example entry point — customise feeds, filters, and GitHub target below."""
import logging
import os
import pandas as pd
from rss_parser import RssParser

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)

# ── Feed list ────────────────────────────────────────────────────────────────
#
# name          – label shown as <source> in the output feed
# url           – RSS or Atom endpoint
# category      – (optional) grouping label
# max_articles  – (optional) cap how many items to take from this feed
# days_back     – (optional) ignore articles older than N days
#
# Omit max_articles / days_back to use the global defaults in RssParser().

FEEDS = pd.DataFrame([
    # ── Technology
    {"name": "Hacker News",           "url": "https://hnrss.org/frontpage",                          "category": "Technology", "max_articles": 20, "days_back": 1},
    {"name": "Ars Technica",          "url": "https://feeds.arstechnica.com/arstechnica/index",       "category": "Technology", "max_articles": 15, "days_back": 3},
    {"name": "MIT Technology Review", "url": "https://www.technologyreview.com/feed/",               "category": "Technology", "max_articles": 10, "days_back": 7},
    # ── AI
    {"name": "OpenAI Blog",           "url": "https://openai.com/news/rss.xml",                      "category": "AI",         "max_articles": 10, "days_back": 30},
    {"name": "DeepMind Blog",         "url": "https://deepmind.google/blog/rss.xml",                 "category": "AI",         "max_articles": 10, "days_back": 30},
    {"name": "The Gradient",          "url": "https://thegradient.pub/rss/",                         "category": "AI",         "max_articles": 10, "days_back": 30},
    # ── Science
    {"name": "NASA News",             "url": "https://www.nasa.gov/news-release/feed/",              "category": "Space",      "max_articles": 10, "days_back": 14},
    {"name": "Science Daily",         "url": "https://www.sciencedaily.com/rss/all.xml",             "category": "Science",    "max_articles": 15, "days_back": 3},
    # ── News
    {"name": "BBC News",              "url": "https://feeds.bbci.co.uk/news/rss.xml",               "category": "News",       "max_articles": 15, "days_back": 1},
    {"name": "The Guardian",          "url": "https://www.theguardian.com/world/rss",                "category": "News",       "max_articles": 15, "days_back": 1},
])

# ── Filters ───────────────────────────────────────────────────────────────
#
# field  – any Article attribute: title, description, source, category
# type   – "contains" or "not_contains"  (case-insensitive)
# value  – string to match

FILTERS = [
    {"field": "title", "type": "not_contains", "value": "sponsored"},
    {"field": "title", "type": "not_contains", "value": "advertisement"},
]

# ── GitHub target ───────────────────────────────────────────────────────
# Change these to match your public GitHub repo.
GITHUB_REPO   = "p4thw4yz/rss_parser"   # owner/repo
GITHUB_BRANCH = "main"
FEED_PATH     = "feed.xml"              # path within the repo

RAW_URL = (
    f"https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}/{FEED_PATH}"
)


def main():
    parser = RssParser(
        feeds_df=FEEDS,
        output_title="My Curated Feed",
        output_description="Tech, AI, science and world news — filtered and sorted.",
        output_link=RAW_URL,
        filters=FILTERS,
        max_workers=8,
        # global_days_back=7,    # fallback for feeds without days_back set
        # global_max_articles=20, # fallback for feeds without max_articles set
    )

    xml = parser.process()
    print(f"Generated {len(xml):,} bytes  ({xml.count('<item>'))} articles)")

    parser.save("feed.xml")
    print("Saved locally → feed.xml")

    token = os.environ.get("GITHUB_TOKEN")
    if token:
        url = parser.push_to_github(
            token=token,
            repo=GITHUB_REPO,
            file_path=FEED_PATH,
            branch=GITHUB_BRANCH,
            commit_message="chore: refresh RSS feed",
        )
        print(f"Published → {url}")
    else:
        print("Tip: set GITHUB_TOKEN to push the feed to GitHub automatically.")


if __name__ == "__main__":
    main()
