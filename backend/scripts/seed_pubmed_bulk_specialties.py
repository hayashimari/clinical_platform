"""
Seed up to 10,000 PubMed papers for multiple specialties into resources/resource_segments.

Example:
    cd backend
    python scripts/seed_pubmed_bulk_specialties.py
"""

import math
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


SPECIALTY_QUERIES = {
    "anesthesia": (
        '("Anesthesia"[MeSH Terms] OR "Anesthesia, Conduction"[MeSH Terms] OR '
        '"Perioperative Care"[MeSH Terms] OR "Pain, Postoperative"[MeSH Terms] OR '
        '"anesthesia"[Title/Abstract] OR "perioperative care"[Title/Abstract] OR '
        '"postoperative pain"[Title/Abstract] OR "regional anesthesia"[Title/Abstract])'
    ),
    "internal_medicine": (
        '("Internal Medicine"[MeSH Terms] OR "Diabetes Mellitus"[MeSH Terms] OR '
        '"Hypertension"[MeSH Terms] OR "Heart Failure"[MeSH Terms] OR '
        '"Kidney Failure, Chronic"[MeSH Terms] OR '
        '"internal medicine"[Title/Abstract] OR "diabetes mellitus"[Title/Abstract] OR '
        '"hypertension"[Title/Abstract] OR "heart failure"[Title/Abstract] OR '
        '"chronic kidney disease"[Title/Abstract])'
    ),
    "surgery": (
        '("Surgical Procedures, Operative"[MeSH Terms] OR "Laparoscopy"[MeSH Terms] OR '
        '"Postoperative Complications"[MeSH Terms] OR '
        '"Surgical Wound Infection"[MeSH Terms] OR '
        '"general surgery"[Title/Abstract] OR "laparoscopic surgery"[Title/Abstract] OR '
        '"postoperative complications"[Title/Abstract] OR '
        '"surgical site infection"[Title/Abstract])'
    ),
    "emergency_medicine": (
        '("Emergency Medicine"[MeSH Terms] OR "Wounds and Injuries"[MeSH Terms] OR '
        '"Sepsis"[MeSH Terms] OR "Heart Arrest"[MeSH Terms] OR '
        '"Emergency Service, Hospital"[MeSH Terms] OR '
        '"emergency medicine"[Title/Abstract] OR "trauma"[Title/Abstract] OR '
        '"sepsis"[Title/Abstract] OR "cardiac arrest"[Title/Abstract] OR '
        '"emergency department"[Title/Abstract])'
    ),
    "pediatrics": (
        '("Pediatrics"[MeSH Terms] OR "Child Health Services"[MeSH Terms] OR '
        '"Infant, Newborn"[MeSH Terms] OR '
        '("Communicable Diseases"[MeSH Terms] AND ("Child"[MeSH Terms] OR "Infant"[MeSH Terms])) OR '
        '("Asthma"[MeSH Terms] AND "Child"[MeSH Terms]) OR '
        '"pediatrics"[Title/Abstract] OR "child health"[Title/Abstract] OR '
        '"neonatal care"[Title/Abstract] OR "pediatric infection"[Title/Abstract] OR '
        '"asthma in children"[Title/Abstract])'
    ),
    "psychiatry": (
        '("Psychiatry"[MeSH Terms] OR "Depressive Disorder"[MeSH Terms] OR '
        '"Anxiety Disorders"[MeSH Terms] OR "Schizophrenia"[MeSH Terms] OR '
        '"Bipolar Disorder"[MeSH Terms] OR '
        '"psychiatry"[Title/Abstract] OR "depression"[Title/Abstract] OR '
        '"anxiety disorder"[Title/Abstract] OR "schizophrenia"[Title/Abstract] OR '
        '"bipolar disorder"[Title/Abstract])'
    ),
}
MAX_RESULTS_PER_SPECIALTY = 10_000
ESEARCH_BATCH_SIZE = 1_000
EFETCH_BATCH_SIZE = 100
RESOURCE_TYPE = "paper"
SEGMENT_INDEX = 0
EUTILS_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
PUBMED_BASE_URL = "https://pubmed.ncbi.nlm.nih.gov"
REQUEST_TIMEOUT = 30
USER_AGENT = "clinical-evidence-platform-pubmed-specialties-seed/1.0"


@dataclass
class PubMedArticle:
    pmid: str
    title: str
    abstract: str


def build_eutils_params(params: dict[str, str | int]) -> dict[str, str | int]:
    request_params = dict(params)
    request_params["tool"] = os.getenv(
        "NCBI_TOOL",
        "clinical-evidence-platform-pubmed-specialties-seed",
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
    collected_ids: list[str] = []
    retstart = 0

    while len(collected_ids) < limit:
        batch_size = min(ESEARCH_BATCH_SIZE, limit - len(collected_ids))
        root = request_xml(
            "esearch.fcgi",
            {
                "db": "pubmed",
                "term": query,
                "retmax": batch_size,
                "retstart": retstart,
                "retmode": "xml",
                "sort": "relevance",
            },
        )

        ids = [node.text.strip() for node in root.findall("./IdList/Id") if node.text]
        if not ids:
            break

        collected_ids.extend(ids)

        total_count_text = root.findtext("./Count") or "0"
        total_count = int(total_count_text)
        retstart += len(ids)

        if retstart >= total_count or len(ids) < batch_size:
            break

    return deduplicate_pmids(collected_ids[:limit])


def deduplicate_pmids(pmids: list[str]) -> list[str]:
    seen: set[str] = set()
    unique_pmids: list[str] = []

    for pmid in pmids:
        if pmid in seen:
            continue
        seen.add(pmid)
        unique_pmids.append(pmid)

    return unique_pmids


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

    articles: list[PubMedArticle] = []
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


def build_source_url(pmid: str) -> str:
    return f"{PUBMED_BASE_URL}/{pmid}/"


def extract_pmid_from_source_url(source_url: str | None) -> str | None:
    if not source_url:
        return None

    match = re.search(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)/?", source_url)
    if match is None:
        return None

    return match.group(1)


def build_segment_content(title: str, abstract: str) -> str:
    return f"{title}\n\n{abstract}".strip()


def embedding_to_vector(embedding: list[float]) -> str:
    return "[" + ",".join(map(str, embedding)) + "]"


def build_segment_embedding(content: str) -> str:
    return embedding_to_vector(create_embedding(content))


def load_existing_keys(cursor) -> tuple[set[str], set[str]]:
    cursor.execute(
        """
        SELECT source_url
        FROM resources
        WHERE source_url IS NOT NULL
        """
    )

    seen_urls: set[str] = set()
    seen_pmids: set[str] = set()

    for (source_url,) in cursor.fetchall():
        if not source_url:
            continue

        seen_urls.add(source_url)
        pmid = extract_pmid_from_source_url(source_url)
        if pmid:
            seen_pmids.add(pmid)

    return seen_urls, seen_pmids


def resource_exists(pmid: str, source_url: str, seen_urls: set[str], seen_pmids: set[str]) -> bool:
    return source_url in seen_urls or pmid in seen_pmids


def ensure_specialty_column(cursor) -> None:
    cursor.execute(
        """
        ALTER TABLE resources
        ADD COLUMN IF NOT EXISTS specialty TEXT
        """
    )


def insert_resource(cursor, article: PubMedArticle, source_url: str, specialty: str) -> int:
    cursor.execute(
        """
        INSERT INTO resources (title, resource_type, abstract, source_url, specialty)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            article.title,
            RESOURCE_TYPE,
            article.abstract,
            source_url,
            specialty,
        ),
    )
    return cursor.fetchone()[0]


def insert_segment(cursor, resource_id: int, content: str, embedding_vector: str) -> None:
    cursor.execute(
        """
        INSERT INTO resource_segments (resource_id, segment_index, content, embedding)
        VALUES (%s, %s, %s, %s::vector)
        """,
        (resource_id, SEGMENT_INDEX, content, embedding_vector),
    )


def store_article(
    cursor,
    article: PubMedArticle,
    specialty: str,
    seen_urls: set[str],
    seen_pmids: set[str],
) -> bool:
    source_url = build_source_url(article.pmid)
    if resource_exists(article.pmid, source_url, seen_urls, seen_pmids):
        return False

    content = build_segment_content(article.title, article.abstract)
    embedding_vector = build_segment_embedding(content)
    resource_id = insert_resource(cursor, article, source_url, specialty)
    insert_segment(cursor, resource_id, content, embedding_vector)
    return True


def chunked(items: list[str], size: int) -> Iterable[list[str]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def print_progress(prefix: str, stats: dict[str, int]) -> None:
    print(
        f"{prefix} fetched={stats['fetched']} "
        f"stored={stats['stored']} "
        f"skipped={stats['skipped']} "
        f"errors={stats['errors']}"
    )


def seed_specialty(
    session,
    cursor,
    specialty: str,
    query: str,
    seen_urls: set[str],
    seen_pmids: set[str],
) -> dict[str, int]:
    stats = {
        "fetched": 0,
        "stored": 0,
        "skipped": 0,
        "errors": 0,
    }

    print(f"[START] specialty={specialty}")

    try:
        pmids = search_pubmed_ids(query, MAX_RESULTS_PER_SPECIALTY)
    except Exception as exc:
        stats["errors"] += 1
        print("Collected 0 PubMed IDs")
        print(
            f"Failed to search PubMed for specialty={specialty}: {exc}",
            file=sys.stderr,
        )
        print(f"stored={stats['stored']} skipped={stats['skipped']} errors={stats['errors']}")
        return stats

    print(f"Collected {len(pmids)} PubMed IDs")

    if not pmids:
        print(f"stored={stats['stored']} skipped={stats['skipped']} errors={stats['errors']}")
        print()
        return stats

    total_batches = math.ceil(len(pmids) / EFETCH_BATCH_SIZE)

    for batch_index, batch_pmids in enumerate(chunked(pmids, EFETCH_BATCH_SIZE), start=1):
        print(
            f"  Batch {batch_index}/{total_batches} "
            f"| requesting {len(batch_pmids)} PMIDs"
        )

        try:
            articles = fetch_pubmed_articles(batch_pmids)
        except Exception as exc:
            stats["errors"] += len(batch_pmids)
            stats["skipped"] += len(batch_pmids)
            print(
                f"  Failed to fetch batch starting with PMID {batch_pmids[0]}: {exc}",
                file=sys.stderr,
            )
            print_progress("  Progress |", stats)
            continue

        stats["fetched"] += len(articles)

        fetched_pmids = {article.pmid for article in articles}
        missing_pmids = [pmid for pmid in batch_pmids if pmid not in fetched_pmids]
        if missing_pmids:
            stats["skipped"] += len(missing_pmids)
            print(
                f"  Skipped {len(missing_pmids)} PMIDs with missing title/abstract or invalid XML rows."
            )

        for article in articles:
            try:
                stored = store_article(cursor, article, specialty, seen_urls, seen_pmids)
                if stored:
                    session.commit()
                    seen_urls.add(build_source_url(article.pmid))
                    seen_pmids.add(article.pmid)
                    stats["stored"] += 1
                else:
                    stats["skipped"] += 1
            except Exception as exc:
                session.rollback()
                stats["errors"] += 1
                stats["skipped"] += 1
                print(
                    f"  Failed to store PMID {article.pmid} | {article.title}: {exc}",
                    file=sys.stderr,
                )

        print_progress("  Progress |", stats)

    print(f"stored={stats['stored']} skipped={stats['skipped']} errors={stats['errors']}")
    print()
    return stats


def print_summary(summary: dict[str, dict[str, int]]) -> None:
    print()
    print("[SUMMARY]")

    total_stored = 0
    for specialty, stats in summary.items():
        total_stored += stats["stored"]
        print(f"{specialty}: stored={stats['stored']}")

    print(f"total_stored={total_stored}")


def seed_pubmed_bulk_specialties() -> dict[str, dict[str, int]]:
    summary: dict[str, dict[str, int]] = {}
    session = get_connection()

    try:
        with session.cursor() as cursor:
            ensure_specialty_column(cursor)
            session.commit()
            seen_urls, seen_pmids = load_existing_keys(cursor)

            for specialty, query in SPECIALTY_QUERIES.items():
                summary[specialty] = seed_specialty(
                    session=session,
                    cursor=cursor,
                    specialty=specialty,
                    query=query,
                    seen_urls=seen_urls,
                    seen_pmids=seen_pmids,
                )
    finally:
        session.close()

    print_summary(summary)
    return summary


def main() -> int:
    try:
        seed_pubmed_bulk_specialties()
    except Exception as exc:
        print(f"Seed failed: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
