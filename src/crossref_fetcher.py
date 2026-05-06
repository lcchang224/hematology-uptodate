"""Fetch recent journal articles from CrossRef API and pre-screen for hematology relevance."""

import asyncio
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

import httpx

from . import config

JATS_TAG = re.compile(r"<[^>]+>")


@dataclass
class JournalArticle:
    title: str
    doi: str
    journal: str
    authors: list[str]
    published: Optional[str]
    abstract: str
    abstract_digest: str
    tags: list[str] = field(default_factory=list)
    url: str = ""


def _clean_abstract(raw: str) -> str:
    return re.sub(r"\s+", " ", JATS_TAG.sub("", raw)).strip()


def _digest_abstract(abstract: str, max_chars: int = 400) -> str:
    if not abstract:
        return ""
    signal_words = [
        "significantly", "improved", "reduced", "increased", "demonstrated",
        "showed", "resulted", "HR ", "hazard ratio", "OS ", "PFS ", "ORR",
        "p=", "p<", "p >", "95% CI", "median", "months", "year",
        "approved", "primary endpoint", "statistically",
    ]
    sentences = re.split(r"(?<=[.!?])\s+", abstract)
    scored = sorted(
        ((sum(1 for w in signal_words if w.lower() in s.lower()), s) for s in sentences),
        key=lambda x: -x[0],
    )
    parts, total = [], 0
    for _, s in scored:
        if total + len(s) > max_chars:
            break
        parts.append(s)
        total += len(s)
    return " ".join(parts).strip() if parts else abstract[:max_chars]


def _extract_tags(text: str) -> list[str]:
    tl = text.lower()
    return list(dict.fromkeys(k for k in config.keywords() if k.lower() in tl))


def _passes_prescreen(text: str) -> bool:
    """Return True if the text matches at least one configured hematology keyword."""
    tl = text.lower()
    return any(kw.lower() in tl for kw in config.keywords())


def _pub_date(item: dict) -> Optional[str]:
    parts = (
        item.get("published", {}).get("date-parts")
        or item.get("published-print", {}).get("date-parts")
        or item.get("published-online", {}).get("date-parts")
        or [[]]
    )
    dp = (parts or [[]])[0]
    if len(dp) >= 3:
        return f"{dp[0]:04d}-{dp[1]:02d}-{dp[2]:02d}"
    if len(dp) == 2:
        return f"{dp[0]:04d}-{dp[1]:02d}"
    if len(dp) == 1:
        return f"{dp[0]:04d}"
    return None


# ── CrossRef fetch ─────────────────────────────────────────────────────────────

async def _fetch_journal(
    client: httpx.AsyncClient,
    journal: dict,
    email: str,
) -> list[JournalArticle]:
    issn = journal["issn"]
    days_back = journal.get("days_back", 14)
    max_items = journal.get("max_items", 30)
    kw_filter = journal.get("bc_filter", True)   # field kept as bc_filter for YAML compat
    from_date = (date.today() - timedelta(days=days_back)).isoformat()

    params = {
        "filter": f"issn:{issn},from-pub-date:{from_date}",
        "rows": max_items,
        "sort": "published",
        "order": "desc",
        "select": "DOI,title,author,abstract,published,published-print,published-online,URL,container-title",
    }
    try:
        r = await client.get(
            "https://api.crossref.org/works",
            params=params,
            headers={"User-Agent": f"hematology-uptodate/1.0 (mailto:{email})"},
            timeout=25,
        )
        r.raise_for_status()
    except Exception:
        return []

    articles = []
    for item in r.json().get("message", {}).get("items", []):
        title = (item.get("title") or [""])[0]
        if not title or len(title) < 10:
            continue
        abstract = _clean_abstract(item.get("abstract", ""))

        if kw_filter and not _passes_prescreen(title + " " + abstract):
            continue

        authors_raw = item.get("author", [])
        authors = [
            f"{a.get('family', '')} {a.get('given', '')[:1]}".strip()
            for a in authors_raw[:4]
        ]
        if len(authors_raw) > 4:
            authors.append("et al.")

        doi = item.get("DOI", "")
        journal_name = (item.get("container-title") or [journal.get("full_name", issn)])[0]

        articles.append(JournalArticle(
            title=title,
            doi=doi,
            journal=journal_name,
            authors=authors,
            published=_pub_date(item),
            abstract=abstract,
            abstract_digest=_digest_abstract(abstract),
            tags=_extract_tags(title + " " + abstract),
            url=f"https://doi.org/{doi}" if doi else item.get("URL", ""),
        ))

    return articles


async def fetch_all() -> dict[str, list[JournalArticle]]:
    journals = config.journals()
    email = config.crossref_email()
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(*[_fetch_journal(client, j, email) for j in journals])
    return {j["name"]: arts for j, arts in zip(journals, results)}


def format_articles_md(results: dict[str, list[JournalArticle]]) -> str:
    if not any(results.values()):
        return ""

    lines = ["\n## Journal Literature — CrossRef\n"]
    lines.append("> Source: CrossRef API · keyword pre-screened; confirm relevance when writing report\n")

    for journal_name, articles in results.items():
        if not articles:
            lines.append(f"\n### {journal_name}\n\n_No relevant articles retrieved this week_\n")
            continue

        with_abstract = [a for a in articles if a.abstract_digest]
        without = [a for a in articles if not a.abstract_digest]

        lines.append(f"\n### {journal_name} ({len(articles)} candidates)\n")

        for a in with_abstract[:10]:
            lines.append(f"#### [{a.title}]({a.url})")
            lines.append(f"_{', '.join(a.authors)}_ · {a.published or '—'} · {a.journal}")
            lines.append("")
            lines.append(f"> {a.abstract_digest}")
            if a.tags:
                lines.append(f"\n`{'` `'.join(a.tags[:5])}`")
            lines.append("")

        if without:
            lines.append("**No abstract available:**\n")
            for a in without[:8]:
                lines.append(f"- [{a.title}]({a.url}) — _{', '.join(a.authors)}_ ({a.published or '—'})")
            lines.append("")

    return "\n".join(lines)
