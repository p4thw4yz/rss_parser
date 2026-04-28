import re
import base64
import logging
import pandas as pd
import feedparser
import requests
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class Article:
    title: str
    link: str
    description: str
    pub_date: Optional[datetime]
    source: str
    category: str
    image: Optional[str] = None


@dataclass
class _FeedConfig:
    name: str
    url: str
    category: str = ""
    description: str = ""
    max_articles: Optional[int] = None
    days_back: Optional[float] = None


def _opt(row, col):
    """Return row[col] or None if the column is missing or NaN."""
    v = row.get(col)
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return v


class RssParser:
    """
    Aggregates multiple RSS/Atom feeds into a single RSS 2.0 feed.

    DataFrame columns (``feeds_df``):
        name          (required) – display name shown as <source> in output
        url           (required) – RSS or Atom feed URL
        category      (optional) – label stored as <category>
        description   (optional) – kept for reference, not in output
        max_articles  (optional, int)   – cap on items taken from this feed
        days_back     (optional, float) – only include items within N days

    Per-feed ``max_articles`` / ``days_back`` override the global defaults.

    Each filter is a dict::

        {"field": "title", "type": "not_contains", "value": "sponsored"}

    ``field`` is any Article attribute; ``type`` is ``contains`` or
    ``not_contains``.
    """

    def __init__(
        self,
        feeds_df: pd.DataFrame,
        output_title: str = "Aggregated RSS Feed",
        output_description: str = "Aggregated from multiple RSS/Atom sources",
        output_link: str = "",
        filters: Optional[list] = None,
        max_workers: int = 10,
        request_timeout: int = 15,
        global_max_articles: Optional[int] = None,
        global_days_back: Optional[float] = None,
    ):
        self._feeds = self._parse_feeds_df(feeds_df)
        self.output_title = output_title
        self.output_description = output_description
        self.output_link = output_link
        self.filters = filters or []
        self.max_workers = max_workers
        self.request_timeout = request_timeout
        self.global_max_articles = global_max_articles
        self.global_days_back = global_days_back
        self._xml: Optional[str] = None

    # ── DataFrame ingestion ───────────────────────────────────────────────────

    @staticmethod
    def _parse_feeds_df(df: pd.DataFrame) -> list:
        missing = {"name", "url"} - set(df.columns)
        if missing:
            raise ValueError(f"DataFrame missing required columns: {missing}")

        feeds = []
        for _, row in df.iterrows():
            ma = _opt(row, "max_articles")
            db = _opt(row, "days_back")
            feeds.append(_FeedConfig(
                name=str(row["name"]),
                url=str(row["url"]),
                category=str(_opt(row, "category") or ""),
                description=str(_opt(row, "description") or ""),
                max_articles=int(ma) if ma is not None else None,
                days_back=float(db) if db is not None else None,
            ))
        return feeds

    # ── Fetching ──────────────────────────────────────────────────────────────

    def _fetch_feed(self, feed: _FeedConfig) -> list:
        try:
            resp = requests.get(
                feed.url,
                timeout=self.request_timeout,
                headers={"User-Agent": "RssParser/1.0"},
            )
            resp.raise_for_status()
            parsed = feedparser.parse(resp.content)
        except Exception as exc:
            logger.warning("Failed to fetch %s (%s): %s", feed.name, feed.url, exc)
            return []

        max_art = feed.max_articles if feed.max_articles is not None else self.global_max_articles
        days    = feed.days_back    if feed.days_back    is not None else self.global_days_back
        cutoff  = datetime.now(timezone.utc) - timedelta(days=days) if days else None

        articles = []
        for entry in parsed.entries:
            pub_date = self._parse_date(entry)
            if cutoff and pub_date and pub_date < cutoff:
                continue
            articles.append(Article(
                title=entry.get("title", "Untitled"),
                link=entry.get("link", ""),
                description=self._get_description(entry),
                pub_date=pub_date,
                source=feed.name,
                category=feed.category,
                image=self._extract_image(entry),
            ))
            if max_art and len(articles) >= max_art:
                break

        logger.debug("Fetched %d articles from %s", len(articles), feed.name)
        return articles

    # ── Parsing helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _parse_date(entry) -> Optional[datetime]:
        for key in ("published_parsed", "updated_parsed"):
            t = entry.get(key)
            if t:
                try:
                    return datetime(*t[:6], tzinfo=timezone.utc)
                except Exception:
                    pass
        return None

    @staticmethod
    def _get_description(entry) -> str:
        for key in ("summary", "content"):
            val = entry.get(key)
            if val:
                if isinstance(val, list) and val:
                    val = val[0].get("value", "")
                if val:
                    return re.sub(r"<[^>]+>", "", str(val)).strip()
        return ""

    @staticmethod
    def _extract_image(entry) -> Optional[str]:
        for media in entry.get("media_content", []):
            if media.get("url"):
                return media["url"]
        for media in entry.get("media_thumbnail", []):
            if media.get("url"):
                return media["url"]
        for enc in entry.get("enclosures", []):
            if enc.get("type", "").startswith("image/") and enc.get("href"):
                return enc["href"]
        for key in ("summary", "content"):
            val = entry.get(key, "")
            if isinstance(val, list):
                val = val[0].get("value", "") if val else ""
            m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', val or "")
            if m:
                return m.group(1)
        return None

    # ── Filtering ─────────────────────────────────────────────────────────────

    def _apply_filters(self, articles: list) -> list:
        if not self.filters:
            return articles

        out = []
        for article in articles:
            keep = True
            for f in self.filters:
                field_val = (getattr(article, f.get("field", ""), "") or "").lower()
                target    = f.get("value", "").lower()
                ftype     = f.get("type", "")
                if ftype == "contains"     and target not in field_val:
                    keep = False
                    break
                if ftype == "not_contains" and target in field_val:
                    keep = False
                    break
            if keep:
                out.append(article)
        return out

    # ── XML generation ────────────────────────────────────────────────────────

    @staticmethod
    def _xt(s: str) -> str:
        """Escape XML text content."""
        return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    @staticmethod
    def _xa(s: str) -> str:
        """Escape XML attribute value."""
        return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

    def _build_rss_xml(self, articles: list) -> str:
        now = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<rss version="2.0"',
            '     xmlns:media="http://search.yahoo.com/mrss/"',
            '     xmlns:atom="http://www.w3.org/2005/Atom">',
            '  <channel>',
            f'    <title>{self._xt(self.output_title)}</title>',
            f'    <description>{self._xt(self.output_description)}</description>',
            f'    <link>{self._xt(self.output_link)}</link>',
            f'    <lastBuildDate>{now}</lastBuildDate>',
            '    <generator>RssParser/1.0</generator>',
        ]

        for art in articles:
            lines += [
                '    <item>',
                f'      <title>{self._xt(art.title)}</title>',
                f'      <link>{self._xt(art.link)}</link>',
                f'      <description>{self._xt(art.description)}</description>',
                f'      <source>{self._xt(art.source)}</source>',
            ]
            if art.category:
                lines.append(f'      <category>{self._xt(art.category)}</category>')
            if art.pub_date:
                lines.append(
                    f'      <pubDate>{art.pub_date.strftime("%a, %d %b %Y %H:%M:%S +0000")}</pubDate>'
                )
            if art.image:
                lines.append(f'      <media:content url="{self._xa(art.image)}" medium="image"/>')
            lines.append('    </item>')

        lines += ['  </channel>', '</rss>']
        return "\n".join(lines) + "\n"

    # ── Public API ────────────────────────────────────────────────────────────

    def process(self) -> str:
        """
        Fetch all configured feeds concurrently, apply filters, sort newest-first,
        and return a combined RSS 2.0 XML string.

        Calling this again re-fetches everything and regenerates the feed.
        """
        logger.info("Processing %d feeds...", len(self._feeds))
        all_articles = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(self._fetch_feed, f): f for f in self._feeds}
            for future in as_completed(futures):
                feed = futures[future]
                try:
                    all_articles.extend(future.result())
                except Exception as exc:
                    logger.error("Unhandled error for %s: %s", feed.name, exc)

        logger.info("Total fetched: %d  —  filtering...", len(all_articles))
        filtered = self._apply_filters(all_articles)
        filtered.sort(
            key=lambda a: a.pub_date or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        logger.info("Building feed with %d articles", len(filtered))
        self._xml = self._build_rss_xml(filtered)
        return self._xml

    def save(self, path: str) -> None:
        """
        Write the generated feed XML to a local file.

        Raises RuntimeError if process() has not been called.
        """
        if self._xml is None:
            raise RuntimeError("Call process() before save()")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(self._xml)
        logger.info("Feed saved to %s", path)

    def push_to_github(
        self,
        token: str,
        repo: str,
        file_path: str = "feed.xml",
        branch: str = "main",
        commit_message: str = "chore: update RSS feed",
    ) -> str:
        """
        Push the generated feed XML to a GitHub repository via the Contents API.

        Args:
            token:          GitHub personal access token with ``repo`` write scope.
            repo:           Repository in ``"owner/repo"`` format.
            file_path:      Path within the repo to write the feed file.
            branch:         Target branch (must already exist).
            commit_message: Git commit message.

        Returns:
            ``raw.githubusercontent.com`` URL of the published file.

        Raises:
            RuntimeError:       If process() has not been called first.
            requests.HTTPError: If the GitHub API call fails.
        """
        if self._xml is None:
            raise RuntimeError("Call process() before push_to_github()")

        headers = {
            "Authorization": f"token {token}",
            "Accept":        "application/vnd.github.v3+json",
        }
        url = f"https://api.github.com/repos/{repo}/contents/{file_path}"

        # Fetch current file SHA so we can update in-place rather than create
        existing_sha = None
        r = requests.get(url, headers=headers, params={"ref": branch})
        if r.status_code == 200:
            existing_sha = r.json().get("sha")

        payload = {
            "message": commit_message,
            "content": base64.b64encode(self._xml.encode()).decode(),
            "branch":  branch,
        }
        if existing_sha:
            payload["sha"] = existing_sha

        r = requests.put(url, headers=headers, json=payload)
        r.raise_for_status()

        owner, repo_name = repo.split("/", 1)
        raw_url = (
            f"https://raw.githubusercontent.com/{owner}/{repo_name}/{branch}/{file_path}"
        )
        logger.info("Feed published to %s", raw_url)
        return raw_url
