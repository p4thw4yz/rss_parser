# rss_parser

A class-based Python RSS aggregator that fetches multiple RSS/Atom feeds
concurrently, filters and sorts articles, and publishes a combined feed to
GitHub so any RSS reader can subscribe to it.

## Quick start

```bash
pip install -r requirements.txt
export GITHUB_TOKEN=ghp_your_token_here
python main.py
```

This generates `feed.xml` locally **and** pushes it to GitHub.  
Subscribe readers to the raw URL:

```
https://raw.githubusercontent.com/YOUR_USER/YOUR_REPO/main/feed.xml
```

## Usage

```python
import pandas as pd
from rss_parser import RssParser

feeds = pd.DataFrame([
    {"name": "Hacker News", "url": "https://hnrss.org/frontpage",
     "category": "Tech", "max_articles": 20, "days_back": 1},
    {"name": "NASA News",   "url": "https://www.nasa.gov/news-release/feed/",
     "category": "Space",  "max_articles": 10, "days_back": 14},
])

parser = RssParser(
    feeds_df=feeds,
    output_title="My Feed",
    output_description="Curated tech & space articles",
    filters=[
        {"field": "title", "type": "not_contains", "value": "sponsored"},
    ],
)

xml = parser.process()          # fetch, filter, sort, generate XML
parser.save("feed.xml")         # write to disk

raw_url = parser.push_to_github(
    token="ghp_...",
    repo="you/your-repo",
    file_path="feed.xml",
)
print(raw_url)
# https://raw.githubusercontent.com/you/your-repo/main/feed.xml
```

## DataFrame columns

| Column         | Required | Type  | Description                                        |
|----------------|----------|-------|----------------------------------------------------|
| `name`         | yes      | str   | Display name — appears as `<source>` in the feed   |
| `url`          | yes      | str   | RSS or Atom feed URL                               |
| `category`     | no       | str   | Grouping label stored as `<category>`              |
| `description`  | no       | str   | Source description (not written to output)         |
| `max_articles` | no       | int   | Cap on items taken from this feed                  |
| `days_back`    | no       | float | Only include items published within the last N days|

Per-feed values override the `global_max_articles` / `global_days_back`
constructor args.

## Filters

```python
filters = [
    {"field": "title",       "type": "not_contains", "value": "sponsored"},
    {"field": "description", "type": "contains",     "value": "python"},
    {"field": "category",    "type": "contains",     "value": "AI"},
]
```

Supported `field` values: any `Article` attribute (`title`, `description`,
`source`, `category`).  
Supported `type` values: `contains`, `not_contains`.

## Automated updates (GitHub Actions)

The included `.github/workflows/update_feed.yml` runs `main.py` every hour
using the built-in `GITHUB_TOKEN` — no secrets to configure.  Enable it by
pushing this repo to GitHub with Actions enabled.

To push to a **different** repo, store a PAT as a repository secret called
`PERSONAL_ACCESS_TOKEN` and update the workflow env accordingly.
