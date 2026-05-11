"""Backfill missing abstracts for CrossRef-fetched articles.

PubMed E-utilities is the universal primary source (no API key, covers
essentially every major journal). Elsevier Article Retrieval API is the
fallback for 10.1016/ DOIs PubMed hasn't indexed yet (set ELSEVIER_API_KEY).
"""

import os
import re
import time
import sys
import xml.etree.ElementTree as ET
from typing import Iterable

import httpx

PUBMED_ESEARCH  = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_EFETCH   = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
ELSEVIER_BASE   = "https://api.elsevier.com/content/article/doi/"
PUBMED_BATCH    = 50
PUBMED_TIMEOUT  = 30
ELSEVIER_TIMEOUT = 25

_JATS_TAG = re.compile(r"<[^>]+>")


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", _JATS_TAG.sub("", text or "")).strip()


# ── PubMed ───────────────────────────────────────────────────────────────────

def fetch_pubmed_abstracts(dois: Iterable[str]) -> dict[str, str]:
    """Map DOI (lowercased) -> abstract via PubMed E-utilities."""
    dois = [d for d in dois if d]
    if not dois:
        return {}
    out: dict[str, str] = {}
    for i in range(0, len(dois), PUBMED_BATCH):
        chunk = dois[i:i + PUBMED_BATCH]
        term = " OR ".join(f"{d}[AID]" for d in chunk)
        try:
            with httpx.Client(timeout=PUBMED_TIMEOUT) as client:
                resp = client.get(PUBMED_ESEARCH, params={
                    "db": "pubmed", "term": term,
                    "retmax": len(chunk) * 2, "retmode": "json",
                })
                resp.raise_for_status()
                pmids = resp.json().get("esearchresult", {}).get("idlist", [])
                if not pmids:
                    time.sleep(0.4)
                    continue
                resp = client.get(PUBMED_EFETCH, params={
                    "db": "pubmed", "id": ",".join(pmids),
                    "rettype": "abstract", "retmode": "xml",
                })
                resp.raise_for_status()
                xml_text = resp.text
        except Exception as exc:
            print(f"  [WARN] PubMed batch {i // PUBMED_BATCH}: {exc}", file=sys.stderr)
            time.sleep(0.4)
            continue

        try:
            root = ET.fromstring(xml_text)
        except Exception as exc:
            print(f"  [WARN] PubMed XML parse: {exc}", file=sys.stderr)
            time.sleep(0.4)
            continue

        for article in root.findall(".//PubmedArticle"):
            doi = None
            for aid in article.findall(".//ArticleIdList/ArticleId"):
                if aid.get("IdType") == "doi" and aid.text:
                    doi = aid.text.strip().lower()
                    break
            if not doi:
                continue
            parts = []
            for ab in article.findall(".//Abstract/AbstractText"):
                label = ab.get("Label", "")
                text = "".join(ab.itertext()).strip()
                if not text:
                    continue
                parts.append(f"{label}: {text}" if label else text)
            if parts:
                out[doi] = _clean(" ".join(parts))
        time.sleep(0.4)   # NCBI fair-use: 3 req/sec without API key
    return out


# ── Elsevier ─────────────────────────────────────────────────────────────────

def fetch_elsevier_abstract(doi: str, api_key: str) -> str:
    """Fetch abstract for an Elsevier DOI. Returns '' on any failure."""
    try:
        with httpx.Client(timeout=ELSEVIER_TIMEOUT) as client:
            resp = client.get(
                f"{ELSEVIER_BASE}{doi}",
                headers={"X-ELS-APIKey": api_key, "Accept": "application/json"},
            )
            if resp.status_code != 200:
                return ""
            data = resp.json()
    except Exception:
        return ""
    coredata = (data.get("full-text-retrieval-response", {})
                    .get("coredata", {}))
    return _clean(coredata.get("dc:description", "") or "")


# ── Public entry point ───────────────────────────────────────────────────────

def backfill(articles: list) -> tuple[int, int]:
    """Fill empty `.abstract` on each article in *articles* (must have `.doi`
    and `.abstract` attributes). Returns (filled_pubmed, filled_elsevier)."""
    targets = [a for a in articles if not a.abstract and a.doi]
    if not targets:
        return (0, 0)

    # ── PubMed pass ──
    doi_map = fetch_pubmed_abstracts([a.doi for a in targets])
    filled_pm = 0
    for a in targets:
        abstract = doi_map.get(a.doi.strip().lower())
        if abstract:
            a.abstract = abstract
            filled_pm += 1

    # ── Elsevier fallback (only for 10.1016/ DOIs still empty) ──
    key = os.environ.get("ELSEVIER_API_KEY", "")
    filled_el = 0
    if key:
        for a in articles:
            if not a.abstract and a.doi.startswith("10.1016/"):
                abstract = fetch_elsevier_abstract(a.doi, key)
                if abstract:
                    a.abstract = abstract
                    filled_el += 1
                time.sleep(0.3)
    return (filled_pm, filled_el)
