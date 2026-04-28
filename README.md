# rss_parser

A class-based Python RSS aggregator. Define multiple output feeds in
`feeds_config.json`; running `main.py` fetches all sources concurrently,
applies filters, and publishes every feed as a separate XML file in a
`feeds/` directory — all in a single GitHub commit.

## Quick start

```bash
pip install -r requirements.txt
export GITHUB_TOKEN=ghp_your_token_here
python main.py
```

Subscribe any RSS reader to a raw URL like:

```
https://raw.githubusercontent.com/YOUR_USER/YOUR_REPO/main/feeds/tech.xml
https://raw.githubusercontent.com/YOUR_USER/YOUR_REPO/main/feeds/ai.xml
```

## Config format (`feeds_config.json`)

```json
[
  {
    "name": "tech",
    "output_title": "Tech & Dev",
    "output_description": "Technology and developer news",
    "global_days_back": 7,
    "global_max_articles": 15,
    "sources": [
      {
        "name": "Hacker News",
        "url": "https://hnrss.org/frontpage",
        "category": "Technology",
        "max_articles": 20,
        "days_back": 1
      }
    ],
    "filters": [
      {"field": "title", "type": "not_contains", "value": "sponsored"}
    ]
  }
]
```

### Config keys

| Key                   | Required | Description                                              |
|-----------------------|----------|----------------------------------------------------------|
| `name`                | yes      | Becomes the output filename: `feeds/{name}.xml`          |
| `sources`             | yes      | List of source objects (see table below)                 |
| `output_title`        | no       | `<title>` in the generated feed (defaults to `name`)     |
| `output_description`  | no       | `<description>` in the generated feed                   |
| `output_link`         | no       | `<link>` in the generated feed                           |
| `global_days_back`    | no       | Default age cutoff for this feed’s sources               |
| `global_max_articles` | no       | Default article cap for this feed’s sources              |
| `filters`             | no       | List of filter objects (see below)                       |

### Source keys

| Key            | Required | Description                                            |
|----------------|----------|--------------------------------------------------------|
| `name`         | yes      | Display name — appears as `<source>` in the output     |
| `url`          | yes      | RSS or Atom feed URL                                   |
| `category`     | no       | Stored as `<category>` in output items                 |
| `max_articles` | no       | Overrides `global_max_articles` for this source        |
| `days_back`    | no       | Overrides `global_days_back` for this source           |

### Filter keys

```json
{"field": "title", "type": "not_contains", "value": "sponsored"}
```

`field`: any Article attribute — `title`, `description`, `source`, `category`  
`type`: `contains` or `not_contains` (case-insensitive)

## Python API

```python
from rss_parser import RssParser, push_feeds_to_github

# From a config dict (used by main.py)
parser = RssParser.from_config(config)
xml    = parser.process()
parser.save("feeds/tech.xml")

# Or construct directly from a DataFrame
import pandas as pd
parser = RssParser(
    feeds_df=pd.DataFrame([{"name": "HN", "url": "https://hnrss.org/frontpage"}]),
    output_title="My Feed",
)

# Batch-push multiple feeds in one commit
urls = push_feeds_to_github(
    feeds={"feeds/tech.xml": tech_xml, "feeds/ai.xml": ai_xml},
    token="ghp_...",
    repo="you/your-repo",
)
```

## Automated updates (GitHub Actions)

`.github/workflows/update_feed.yml` runs `main.py` every hour using the
built-in `GITHUB_TOKEN` — no extra secrets needed, just merge and enable
Actions.
