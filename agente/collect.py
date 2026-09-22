"""Coleta de itens das fontes (RSS e páginas sem RSS)."""
import hashlib
import logging
import re
import time
import warnings
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse, urlunparse

import feedparser
import requests
from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)

log = logging.getLogger(__name__)
UA = "Mozilla/5.0 (compatible; AgenteTechCITi/1.0; +https://github.com)"
TIMEOUT = 20


def norm_url(url: str) -> str:
    p = urlparse(url.strip())
    return urlunparse((p.scheme, p.netloc.lower(), p.path.rstrip("/"), "", p.query if "news.google" in p.netloc else "", ""))


def item_id(url: str, title: str) -> str:
    return hashlib.sha1(f"{norm_url(url)}|{title.strip().lower()}".encode()).hexdigest()[:16]


def _clean(text: str, limit: int = 400) -> str:
    text = BeautifulSoup(text or "", "html.parser").get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text)[:limit]


def fetch_rss(src: dict) -> list[dict]:
    resp = requests.get(src["url"], headers={"User-Agent": UA}, timeout=TIMEOUT)
    resp.raise_for_status()
    feed = feedparser.parse(resp.content)
    items = []
    for e in feed.entries[:40]:
        title = _clean(e.get("title", ""), 250)
        link = e.get("link", "")
        if not title or not link:
            continue
        ts = e.get("published_parsed") or e.get("updated_parsed")
        published = datetime.fromtimestamp(time.mktime(ts), tz=timezone.utc) if ts else None
        items.append({
            "id": item_id(link, title), "title": title, "url": link,
            "summary": _clean(e.get("summary", "")), "published": published,
            "source": src["name"], "group": src["group"],
        })
    return items


def fetch_page(src: dict) -> list[dict]:
    """Para sites sem RSS: pega links que casam com link_pattern."""
    resp = requests.get(src["url"], headers={"User-Agent": UA}, timeout=TIMEOUT)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    pattern = re.compile(src["link_pattern"])
    seen, items = set(), []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        path = urlparse(href).path if href.startswith("http") else href
        if not pattern.match(path):
            continue
        url = urljoin(src["url"], href)
        if url in seen:
            continue
        seen.add(url)
        heading = a.find(["h1", "h2", "h3", "h4"])
        title = _clean(heading.get_text(" ") if heading else a.get_text(" "), 250)
        if len(title) < 8:
            title = path.rsplit("/", 1)[-1].replace("-", " ").strip().capitalize()
        # id baseado só na URL: o texto do card pode mudar (data, categoria)
        items.append({
            "id": item_id(url, ""), "title": title, "url": url, "summary": "",
            "published": None, "source": src["name"], "group": src["group"],
        })
    return items[:40]


def fetch_source(src: dict) -> tuple[dict, list[dict], str | None]:
    try:
        fn = fetch_page if src["kind"] == "page" else fetch_rss
        return src, fn(src), None
    except Exception as exc:  # uma fonte fora do ar não derruba o agente
        return src, [], f"{type(exc).__name__}: {exc}"


def collect_all(sources: list[dict]) -> tuple[dict[str, list[dict]], dict[str, str]]:
    results, errors = {}, {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        for src, items, err in pool.map(fetch_source, sources):
            results[src["name"]] = items
            if err:
                errors[src["name"]] = err
                log.warning("Fonte com erro: %s -> %s", src["name"], err)
            else:
                log.info("%-32s %3d itens", src["name"], len(items))
    return results, errors
