"""
Seed PubMed anesthesia and pain-management papers into the local RAG database.

Example:
    cd backend
    python scripts/seed_pubmed_anesthesia.py --limit-per-keyword 10
"""

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.db import get_connection
from app.services.openai_service import create_embedding


ANESTHESIA_KEYWORDS = [
    "postoperative pain multimodal analgesia",
    "opioid sparing postoperative pain",
    "regional anesthesia nerve block",
    "ultrasound guided nerve block",
    "suprainguinal fascia iliaca block",
    "SIFI block anesthesia",
    "fascia iliaca compartment block",
    "hip fracture analgesia nerve block",
    "peripheral nerve block hip surgery",
    "regional anesthesia hip fracture",
    "epidural steroid injection chronic low back pain",
    "neuropathic pain treatment guideline",
    "difficult airway management anesthesia guideline",
    "intraoperative hypotension anesthesia",
    "postoperative nausea vomiting prevention",
    "ICU sedation propofol dexmedetomidine",
    "malignant hyperthermia anesthesia management",
    "anesthesia elderly perioperative risk",
    "pediatric anesthesia safety",
    "obstetric anesthesia spinal general cesarean",
]

EUTILS_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
PUBMED_BASE_URL = "https://pubmed.ncbi.nlm.nih.gov"
REQUEST_TIMEOUT = 30
RESOURCE_TYPE = "paper"
USER_AGENT = "clinical-evidence-platform-anesthesia-seed/1.0"


@dataclass
class PubMedArticle:
    pmid: str
    title: str
    abstract: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed anesthesia-focused PubMed papers into resources/resource_segments."
    )
    parser.add_argument(
        "--limit-per-keyword",
        type=int,
        default=10,
        help="Maximum number of PubMed results to fetch for each keyword.",
    )
    return parser.parse_args()


def build_eutils_params(params: dict[str, str | int]) -> dict[str, str | int]:
    request_params = dict(params)
    request_params["tool"] = os.getenv(
        "NCBI_TOOL",
        "clinical-evidence-platform-anesthesia-seed",
    )

    email = os.getenv("NCBI_EMAIL")
    if email:
        request_params["email"] = email

    api_key = os.getenv("NCBI_API_KEY")
    if api_key:
        request_params["api_key"] = api_key

    return request_params


def request_xml(endpoint: str, params: dict[str, str | int]) -> ET.Element:
    query_string = urlencode(build_eutils_params(params))
    url = f"{EUTILS_BASE_URL}/{endpoint}?{query_string}"
    request = Request(url, headers={"User-Agent": USER_AGENT})

    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            payload = response.read()
    except HTTPError as exc:
        raise RuntimeError(f"PubMed API request failed: {exc.code} {exc.reason}") from exc
    except URLError as exc:
        raise RuntimeError(f"PubMed API connection failed: {exc.reason}") from exc

    try:
        return ET.fromstring(payload)
    except ET.ParseError as exc:
        raise RuntimeError("Failed to parse PubMed XML response") from exc


def search_pubmed_ids(query: str, limit: int) -> list[str]:
    root = request_xml(
        "esearch.fcgi",
        {
            "db": "pubmed",
            "term": query,
            "retmax": limit,
            "sort": "relevance",
        },
    )
    return [node.text.strip() for node in root.findall("./IdList/Id") if node.text]


def fetch_pubmed_articles(pmids: list[str]) -> list[PubMedArticle]:
    if not pmids:
        return []

    root = request_xml(
        "efetch.fcgi",
        {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml",
        },
    )

    articles = []
    for article_node in root.findall("./PubmedArticle"):
        article = parse_pubmed_article(article_node)
        if article:
            articles.append(article)

    return articles


def parse_pubmed_article(article_node: ET.Element) -> PubMedArticle | None:
    medline_citation = article_node.find("./MedlineCitation")
    article = article_node.find("./MedlineCitation/Article")
    if medline_citation is None or article is None:
        return None

    pmid = extract_text(medline_citation.find("./PMID"))
    title = extract_text(article.find("./ArticleTitle"))
    abstract = build_abstract(article.findall("./Abstract/AbstractText"))

    if not pmid or not title or not abstract:
        return None

    return PubMedArticle(pmid=pmid, title=title, abstract=abstract)


def extract_text(node: ET.Element | None) -> str:
    if node is None:
        return ""
    return " ".join("".join(node.itertext()).split())


def build_abstract(nodes: Iterable[ET.Element]) -> str:
    parts: list[str] = []

    for node in nodes:
        text = extract_text(node)
        if not text:
            continue

        label = (node.attrib.get("Label") or node.attrib.get("NlmCategory") or "").strip()
        parts.append(f"{label}: {text}" if label else text)

    return " ".join(parts).strip()


def normalize_title(title: str) -> str:
    return " ".join(title.split()).casefold()


def build_source_url(pmid: str) -> str:
    return f"{PUBMED_BASE_URL}/{pmid}/"


def build_segment_content(title: str, abstract: str) -> str:
    return f"{title}\n\n{abstract}".strip()


def embedding_to_vector(embedding: list[float]) -> str:
    return "[" + ",".join(map(str, embedding)) + "]"


def build_segment_embedding(content: str) -> str:
    embedding = create_embedding(content)
    return embedding_to_vector(embedding)


def load_existing_keys(cursor) -> tuple[set[str], set[str]]:
    cursor.execute(
        """
        SELECT lower(title) AS normalized_title, source_url
        FROM resources
        WHERE title IS NOT NULL OR source_url IS NOT NULL
        """
    )

    seen_titles: set[str] = set()
    seen_urls: set[str] = set()

    for normalized_title, source_url in cursor.fetchall():
        if normalized_title:
            seen_titles.add(normalized_title)
        if source_url:
            seen_urls.add(source_url)

    return seen_titles, seen_urls


def resource_exists(title: str, source_url: str, seen_titles: set[str], seen_urls: set[str]) -> bool:
    return normalize_title(title) in seen_titles or source_url in seen_urls


def insert_resource(cursor, article: PubMedArticle, source_url: str) -> int:
    cursor.execute(
        """
        INSERT INTO resources (title, resource_type, abstract, source_url)
        VALUES (%s, %s, %s, %s)
        RETURNING id
        """,
        (
            article.title,
            RESOURCE_TYPE,
            article.abstract,
            source_url,
        ),
    )
    return cursor.fetchone()[0]


def insert_segment(cursor, resource_id: int, content: str, embedding_vector: str) -> None:
    cursor.execute(
        """
        INSERT INTO resource_segments (resource_id, segment_index, content, embedding)
        VALUES (%s, %s, %s, %s::vector)
        """,
        (resource_id, 0, content, embedding_vector),
    )


def store_article(cursor, article: PubMedArticle, seen_titles: set[str], seen_urls: set[str]) -> bool:
    source_url = build_source_url(article.pmid)

    if resource_exists(article.title, source_url, seen_titles, seen_urls):
        return False

    content = build_segment_content(article.title, article.abstract)
    embedding_vector = build_segment_embedding(content)
    resource_id = insert_resource(cursor, article, source_url)
    insert_segment(cursor, resource_id, content, embedding_vector)
    return True


def seed_keyword(
    session,
    cursor,
    keyword: str,
    limit_per_keyword: int,
    seen_titles: set[str],
    seen_urls: set[str],
) -> dict[str, int]:
    pmids = search_pubmed_ids(keyword, limit_per_keyword)
    articles = fetch_pubmed_articles(pmids)

    stats = {
        "fetched": len(articles),
        "stored": 0,
        "skipped": 0,
        "errors": 0,
    }

    for article in articles:
        try:
            stored = store_article(cursor, article, seen_titles, seen_urls)
            if stored:
                session.commit()
                seen_titles.add(normalize_title(article.title))
                seen_urls.add(build_source_url(article.pmid))
                stats["stored"] += 1
            else:
                stats["skipped"] += 1
        except Exception as exc:
            session.rollback()
            stats["errors"] += 1
            stats["skipped"] += 1
            print(
                f"  - Failed to store PMID {article.pmid} | {article.title}: {exc}",
                file=sys.stderr,
            )

    return stats


def seed_anesthesia_pubmed(limit_per_keyword: int) -> int:
    session = get_connection()
    total_stats = {
        "fetched": 0,
        "stored": 0,
        "skipped": 0,
        "errors": 0,
    }

    try:
        with session.cursor() as cursor:
            seen_titles, seen_urls = load_existing_keys(cursor)

            for keyword in ANESTHESIA_KEYWORDS:
                print(f"\nKeyword: {keyword}")
                keyword_stats = seed_keyword(
                    session=session,
                    cursor=cursor,
                    keyword=keyword,
                    limit_per_keyword=limit_per_keyword,
                    seen_titles=seen_titles,
                    seen_urls=seen_urls,
                )

                total_stats["fetched"] += keyword_stats["fetched"]
                total_stats["stored"] += keyword_stats["stored"]
                total_stats["skipped"] += keyword_stats["skipped"]
                total_stats["errors"] += keyword_stats["errors"]

                print(
                    f"  fetched={keyword_stats['fetched']} "
                    f"stored={keyword_stats['stored']} "
                    f"skipped={keyword_stats['skipped']} "
                    f"errors={keyword_stats['errors']}"
                )
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    print(
        "\nSeed complete | "
        f"fetched={total_stats['fetched']} "
        f"stored={total_stats['stored']} "
        f"skipped={total_stats['skipped']} "
        f"errors={total_stats['errors']}"
    )
    return total_stats["stored"]


def main() -> int:
    args = parse_args()

    if args.limit_per_keyword <= 0:
        print("--limit-per-keyword must be greater than 0.", file=sys.stderr)
        return 1

    try:
        seed_anesthesia_pubmed(limit_per_keyword=args.limit_per_keyword)
    except Exception as exc:
        print(f"Seed failed: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
