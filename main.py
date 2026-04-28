"""Generate one XML per entry in feeds_config.json and push all in a single commit."""
import json
import logging
import os
from pathlib import Path
from rss_parser import RssParser, push_feeds_to_github

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)

GITHUB_REPO   = "p4thw4yz/rss_parser"
GITHUB_BRANCH = "main"
FEEDS_DIR     = "feeds"
CONFIG_FILE   = "feeds_config.json"


def main():
    with open(CONFIG_FILE) as f:
        configs = json.load(f)

    Path(FEEDS_DIR).mkdir(exist_ok=True)

    generated: dict[str, str] = {}  # {repo-relative path: xml string}

    for config in configs:
        name = config["name"]
        log  = logging.getLogger(name)
        try:
            parser   = RssParser.from_config(config)
            xml      = parser.process()
            local    = f"{FEEDS_DIR}/{name}.xml"
            parser.save(local)
            generated[local] = xml
            log.info("%d articles  →  %s", xml.count("<item>"), local)
        except Exception as exc:
            log.error("Skipped: %s", exc)

    if not generated:
        logging.warning("No feeds generated — nothing to push.")
        return

    token = os.environ.get("GITHUB_TOKEN")
    if token:
        urls = push_feeds_to_github(
            feeds=generated,
            token=token,
            repo=GITHUB_REPO,
            branch=GITHUB_BRANCH,
            commit_message=f"chore: refresh {len(generated)} feed(s)",
        )
        print("\nPublished:")
        for path, url in urls.items():
            print(f"  {url}")
    else:
        print(f"\nSaved {len(generated)} feed(s) to {FEEDS_DIR}/.")
        print("Set GITHUB_TOKEN to push them to GitHub.")


if __name__ == "__main__":
    main()
