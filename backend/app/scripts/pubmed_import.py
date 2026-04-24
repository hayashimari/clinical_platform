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


BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.db import get_connection
from app.services.openai_service import create_embedding


EUTILS_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
PUBMED_BASE_URL = "https://pubmed.ncbi.nlm.nih.gov"
REQUEST_TIMEOUT = 30
USER_AGENT = "platform-rag-importer/1.0"


@dataclass
class PubMedArticle:
    pmid: str
    title: str
    abstract: str
    publication_types: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import PubMed abstracts into resources/resource_segments."
    )
    parser.add_argument(
        "--query",
        required=True,
        help='PubMed search query, for example "asthma" or "diabetes".',
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of PubMed records to import.",
    )
    return parser.parse_args()


def build_eutils_params(params: dict[str, str | int]) -> dict[str, str | int]:
    request_params = dict(params)
    request_params["tool"] = os.getenv("NCBI_TOOL", "platform-rag-importer")

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
    return [element.text.strip() for element in root.findall("./IdList/Id") if element.text]


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
    publication_types = [
        extract_text(node)
        for node in article.findall("./PublicationTypeList/PublicationType")
        if extract_text(node)
    ]

    if not title:
        return None

    return PubMedArticle(
        pmid=pmid,
        title=title,
        abstract=abstract,
        publication_types=publication_types,
    )


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
        if label:
            parts.append(f"{label}: {text}")
        else:
            parts.append(text)

    return " ".join(parts).strip()


def infer_resource_type(publication_types: list[str]) -> str:
    normalized_types = [item.lower() for item in publication_types]

    if any("guideline" in item for item in normalized_types):
        return "guideline"
    if any("review" in item for item in normalized_types):
        return "review"

    return "journal_article"


def normalize_title(title: str) -> str:
    return " ".join(title.split()).casefold()


def chunk_abstract(abstract: str) -> list[str]:
    normalized = " ".join(abstract.split())
    if not normalized:
        return []

    sentences = re.split(r"(?<=[.!?])\s+", normalized)
    return [sentence.strip() for sentence in sentences if sentence.strip()]


def embedding_to_vector(embedding: list[float]) -> str:
    return "[" + ",".join(map(str, embedding)) + "]"


def resource_exists(cursor, title: str) -> bool:
    cursor.execute(
        "SELECT 1 FROM resources WHERE lower(title) = lower(%s) LIMIT 1",
        (title,),
    )
    return cursor.fetchone() is not None


def insert_resource(cursor, article: PubMedArticle, resource_type: str) -> int:
    cursor.execute(
        """
        INSERT INTO resources (title, resource_type, abstract, source_url)
        VALUES (%s, %s, %s, %s)
        RETURNING id
        """,
        (
            article.title,
            resource_type,
            article.abstract,
            f"{PUBMED_BASE_URL}/{article.pmid}/" if article.pmid else PUBMED_BASE_URL,
        ),
    )
    return cursor.fetchone()[0]


def insert_segment(cursor, resource_id: int, content: str) -> None:
    embedding = create_embedding(content)
    cursor.execute(
        """
        INSERT INTO resource_segments (resource_id, content, embedding)
        VALUES (%s, %s, %s::vector)
        """,
        (resource_id, content, embedding_to_vector(embedding)),
    )


def import_pubmed_articles(query: str, limit: int) -> dict[str, int]:
    pmids = search_pubmed_ids(query=query, limit=limit)
    articles = fetch_pubmed_articles(pmids)

    stats = {
        "fetched": len(articles),
        "inserted": 0,
        "skipped": 0,
        "segments": 0,
        "errors": 0,
    }

    seen_titles: set[str] = set()
    conn = get_connection()

    try:
        with conn.cursor() as cursor:
            for article in articles:
                title = article.title.strip()
                abstract = article.abstract.strip()

                if not title:
                    stats["skipped"] += 1
                    print("Skipping record without title.")
                    continue

                if not abstract:
                    stats["skipped"] += 1
                    print(f"Skipping '{title}' because abstract is empty.")
                    continue

                normalized_title = normalize_title(title)

                if normalized_title in seen_titles or resource_exists(cursor, title):
                    stats["skipped"] += 1
                    print(f"Skipping duplicate title: {title}")
                    continue

                segments = chunk_abstract(abstract)
                if not segments:
                    stats["skipped"] += 1
                    print(f"Skipping '{title}' because no abstract chunks were created.")
                    continue

                try:
                    resource_type = infer_resource_type(article.publication_types)
                    resource_id = insert_resource(cursor, article, resource_type)

                    for segment in segments:
                        insert_segment(cursor, resource_id, segment)
                        stats["segments"] += 1

                    conn.commit()
                    seen_titles.add(normalized_title)
                    stats["inserted"] += 1
                    print(
                        f"Imported PMID {article.pmid or '-'} | "
                        f"{resource_type} | {title} | {len(segments)} segments"
                    )
                except Exception as exc:
                    conn.rollback()
                    stats["errors"] += 1
                    print(f"Failed to import '{title}': {exc}", file=sys.stderr)
    finally:
        conn.close()

    return stats


def main() -> int:
    args = parse_args()

    if args.limit <= 0:
        print("--limit must be greater than 0.", file=sys.stderr)
        return 1

    try:
        stats = import_pubmed_articles(query=args.query, limit=args.limit)
    except Exception as exc:
        print(f"Import failed: {exc}", file=sys.stderr)
        return 1

    print(
        "\nImport complete | "
        f"fetched={stats['fetched']} "
        f"inserted={stats['inserted']} "
        f"skipped={stats['skipped']} "
        f"segments={stats['segments']} "
        f"errors={stats['errors']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
