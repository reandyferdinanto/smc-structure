from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from dataclasses import dataclass

import httpx

from ..utils.log import get_logger

log = get_logger("macro.news")

GDELT_URL = (
    "https://api.gdeltproject.org/api/v2/doc/doc"
    "?query=(gold%20OR%20XAUUSD%20OR%20%22real%20yield%22%20OR%20FOMC)"
    "%20sourcelang:english&mode=artlist&maxrecords=50&format=json&timespan=24h"
)
NEWS_RSS = (
    "https://news.google.com/rss/search?q=gold+price+fed&hl=en-US&gl=US&ceid=US:en"
)

BULLISH_TERMS = [
    "rate cut",
    "dovish",
    "safe haven",
    "central bank buying",
    "etf inflow",
    "war",
    "sanctions",
    "recession",
    "stimulus",
    "weak dollar",
    "risk aversion",
]
BEARISH_TERMS = [
    "rate hike",
    "hawkish",
    "strong dollar",
    "etf outflow",
    "profit taking",
    "risk-on",
    "yields rise",
    "tapering",
    "inflation cools",
]


@dataclass(frozen=True)
class Headline:
    title: str
    url: str
    domain: str

    @property
    def key(self) -> str:
        normalized = " ".join(self.title.lower().split())
        return hashlib.sha1(normalized.encode()).hexdigest()


def headline_score(title: str) -> int:
    text = title.lower()
    bullish = sum(1 for term in BULLISH_TERMS if term in text)
    bearish = sum(1 for term in BEARISH_TERMS if term in text)
    return max(-1, min(1, bullish - bearish))


def fetch_gdelt(timeout: float = 15.0) -> list[Headline]:
    response = httpx.get(GDELT_URL, timeout=timeout)
    response.raise_for_status()
    articles = response.json().get("articles", [])
    return [
        Headline(
            title=str(item.get("title", "")),
            url=str(item.get("url", "")),
            domain=str(item.get("domain", "")),
        )
        for item in articles
    ]


def fetch_google_news(timeout: float = 15.0) -> list[Headline]:
    response = httpx.get(NEWS_RSS, timeout=timeout)
    response.raise_for_status()
    root = ET.fromstring(response.content)
    headlines: list[Headline] = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        if title:
            headlines.append(Headline(title=title, url=link, domain="news.google.com"))
    return headlines


def aggregate_score(headlines: list[Headline]) -> tuple[int, int]:
    seen: set[str] = set()
    total = 0
    count = 0
    for headline in headlines:
        if headline.key in seen:
            continue
        seen.add(headline.key)
        total += headline_score(headline.title)
        count += 1
    return total, count
