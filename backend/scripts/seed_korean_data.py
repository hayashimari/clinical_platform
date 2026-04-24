"""
Seed Korean clinical evidence data into the local RAG database.

Examples:
    cd backend
    python scripts/seed_korean_data.py
    python scripts/seed_korean_data.py --json-path ./data/korean_resources.json
"""

import argparse
import json
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.db import SessionLocal
from app.services.openai_service import create_embedding


DEFAULT_ABSTRACT_LENGTH = 500
DEFAULT_SEGMENT_INDEX = 0
DEFAULT_RESOURCE_TYPE = "korean_paper"

SAMPLE_KOREAN_DATA = [
    {
        "title": "수술 후 통증 조절을 위한 다중모드 진통 전략의 국내 적용",
        "resource_type": "korean_paper",
        "abstract": (
            "수술 후 통증 조절에서 비마약성 진통제, 국소마취 기법, 환자 맞춤형 "
            "opioid 사용을 병합하는 다중모드 진통 전략은 통증 점수를 낮추고 "
            "조기 보행을 촉진하는 것으로 보고되었다."
        ),
        "source_url": "https://example.kr/korean-paper/postoperative-multimodal-analgesia",
    },
    {
        "title": "초음파 유도하 말초신경차단의 임상적 안전성과 성공률 분석",
        "resource_type": "korean_paper",
        "abstract": (
            "초음파 유도하 말초신경차단은 해부학적 구조를 실시간으로 확인할 수 있어 "
            "차단 성공률을 높이고 혈관 천자 및 국소마취제 관련 합병증을 줄이는 데 "
            "도움이 된다."
        ),
        "source_url": "https://example.kr/korean-paper/ultrasound-guided-nerve-block",
    },
    {
        "title": "만성 요통 환자에서 경막외 스테로이드 주사의 단기 통증 완화 효과",
        "resource_type": "korean_paper",
        "abstract": (
            "만성 요통 환자에서 경막외 스테로이드 주사는 단기 통증 완화와 기능 개선에 "
            "유의한 이점을 보였으나, 반복 시술 여부는 영상 소견과 신경학적 증상을 "
            "함께 고려해야 한다."
        ),
        "source_url": "https://example.kr/korean-paper/epidural-steroid-low-back-pain",
    },
    {
        "title": "신경병증성 통증 약물치료에 대한 국내 전문가 합의 권고안",
        "resource_type": "guideline",
        "abstract": (
            "신경병증성 통증 환자에서는 pregabalin, gabapentin, duloxetine, "
            "삼환계 항우울제를 우선 고려하고, 동반 질환과 부작용 위험을 반영해 "
            "개별화 치료를 시행할 것을 권고한다."
        ),
        "source_url": "https://example.kr/guideline/neuropathic-pain-consensus",
    },
    {
        "title": "어려운 기도 환자에서 국내 마취 전 평가와 기도 확보 알고리즘",
        "resource_type": "guideline",
        "abstract": (
            "어려운 기도 환자에서는 Mallampati 분류, 경부 가동성, 개구 범위를 포함한 "
            "사전 평가와 함께 video laryngoscope, awake intubation, "
            "surgical airway 준비를 포함한 단계별 알고리즘 적용이 필요하다."
        ),
        "source_url": "https://example.kr/guideline/difficult-airway-management",
    },
    {
        "title": "수술 후 오심구토 예방을 위한 한국형 위험도 기반 접근",
        "resource_type": "guideline",
        "content": (
            "수술 후 오심구토 예방에서는 여성, 비흡연, 과거 오심구토 병력, "
            "마약성 진통제 사용 여부를 기준으로 위험도를 평가하고, 중등도 이상 위험군은 "
            "두 가지 이상의 예방 약제를 병합하는 전략이 권장된다. 마취 유지 기법, "
            "수액 전략, 회복실 모니터링도 함께 고려해야 한다."
        ),
        "source_url": "https://example.kr/guideline/ponv-risk-based-prevention",
    },
    {
        "title": "고령 수술 환자의 주술기 위험평가와 마취 전략",
        "resource_type": "korean_paper",
        "abstract": (
            "고령 수술 환자에서는 frailty, 심폐기능, 섬망 위험, 다약제 복용 여부를 "
            "통합 평가해야 하며, 저혈압 예방과 조기 회복을 목표로 한 마취 계획 수립이 "
            "예후 개선에 중요하다."
        ),
        "source_url": "https://example.kr/korean-paper/elderly-perioperative-risk",
    },
    {
        "title": "중환자실 진정에서 프로포폴과 덱스메데토미딘 사용 비교",
        "resource_type": "korean_paper",
        "content": (
            "중환자실 진정 치료에서 프로포폴은 빠른 진정 깊이 조절에 유리하고, "
            "덱스메데토미딘은 자발 호흡 유지와 섬망 감소 가능성에서 장점을 보인다. "
            "환자의 혈역학 상태와 목표 진정 수준에 따라 약제를 선택해야 한다."
        ),
        "source_url": "https://example.kr/korean-paper/icu-sedation-propofol-dexmedetomidine",
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed Korean clinical resources into resources/resource_segments."
    )
    parser.add_argument(
        "--json-path",
        help="Optional JSON file path containing a list of Korean resources.",
    )
    return parser.parse_args()


def normalize_title(title: str) -> str:
    return " ".join((title or "").split()).casefold()


def normalize_text(text: str) -> str:
    return " ".join((text or "").split()).strip()


def derive_abstract(record: dict) -> str:
    abstract = normalize_text(record.get("abstract"))
    if abstract:
        return abstract

    content = normalize_text(record.get("content"))
    if not content:
        return ""

    if len(content) <= DEFAULT_ABSTRACT_LENGTH:
        return content

    return content[:DEFAULT_ABSTRACT_LENGTH].rstrip() + "..."


def build_segment_content(title: str, abstract: str) -> str:
    return f"{normalize_text(title)}\n\n{normalize_text(abstract)}".strip()


def embedding_to_vector(embedding: list[float]) -> str:
    return "[" + ",".join(map(str, embedding)) + "]"


def build_segment_embedding(content: str) -> str:
    embedding = create_embedding(content)
    return embedding_to_vector(embedding)


def load_records_from_json(json_path: str) -> list[dict]:
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("JSON root must be a list of resource objects.")

    return data


def load_seed_records(json_path: str | None) -> list[dict]:
    if json_path:
        return load_records_from_json(json_path)
    return SAMPLE_KOREAN_DATA


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


def record_exists(title: str, source_url: str, seen_titles: set[str], seen_urls: set[str]) -> bool:
    return normalize_title(title) in seen_titles or source_url in seen_urls


def validate_record(record: dict) -> dict | None:
    title = normalize_text(record.get("title"))
    source_url = normalize_text(record.get("source_url"))
    resource_type = normalize_text(record.get("resource_type")) or DEFAULT_RESOURCE_TYPE
    abstract = derive_abstract(record)

    if not title or not source_url or not abstract:
        return None

    return {
        "title": title,
        "resource_type": resource_type,
        "abstract": abstract,
        "source_url": source_url,
    }


def insert_resource(cursor, resource: dict) -> int:
    cursor.execute(
        """
        INSERT INTO resources (title, resource_type, abstract, source_url)
        VALUES (%s, %s, %s, %s)
        RETURNING id
        """,
        (
            resource["title"],
            resource["resource_type"],
            resource["abstract"],
            resource["source_url"],
        ),
    )
    return cursor.fetchone()[0]


def insert_segment(cursor, resource_id: int, content: str, embedding_vector: str) -> None:
    cursor.execute(
        """
        INSERT INTO resource_segments (resource_id, segment_index, content, embedding)
        VALUES (%s, %s, %s, %s::vector)
        """,
        (resource_id, DEFAULT_SEGMENT_INDEX, content, embedding_vector),
    )


def store_resource(cursor, resource: dict, seen_titles: set[str], seen_urls: set[str]) -> bool:
    if record_exists(resource["title"], resource["source_url"], seen_titles, seen_urls):
        return False

    segment_content = build_segment_content(resource["title"], resource["abstract"])
    embedding_vector = build_segment_embedding(segment_content)
    resource_id = insert_resource(cursor, resource)
    insert_segment(cursor, resource_id, segment_content, embedding_vector)
    return True


def seed_korean_data(records: list[dict]) -> dict[str, int]:
    session = SessionLocal()
    stats = {
        "input": len(records),
        "stored": 0,
        "skipped": 0,
        "errors": 0,
    }

    try:
        with session.cursor() as cursor:
            seen_titles, seen_urls = load_existing_keys(cursor)

            for idx, raw_record in enumerate(records, start=1):
                resource = validate_record(raw_record)
                if resource is None:
                    stats["skipped"] += 1
                    print(f"Skipping invalid record #{idx}")
                    continue

                try:
                    stored = store_resource(cursor, resource, seen_titles, seen_urls)
                    if stored:
                        session.commit()
                        seen_titles.add(normalize_title(resource["title"]))
                        seen_urls.add(resource["source_url"])
                        stats["stored"] += 1
                        print(
                            f"Stored #{idx} | {resource['resource_type']} | {resource['title']}"
                        )
                    else:
                        stats["skipped"] += 1
                        print(f"Skipped duplicate #{idx} | {resource['title']}")
                except Exception as exc:
                    session.rollback()
                    stats["errors"] += 1
                    stats["skipped"] += 1
                    print(
                        f"Failed to store #{idx} | {resource['title']}: {exc}",
                        file=sys.stderr,
                    )
    finally:
        session.close()

    return stats


def main() -> int:
    args = parse_args()

    try:
        records = load_seed_records(args.json_path)
        stats = seed_korean_data(records)
    except Exception as exc:
        print(f"Seed failed: {exc}", file=sys.stderr)
        return 1

    print(
        "\nKorean seed complete | "
        f"input={stats['input']} "
        f"stored={stats['stored']} "
        f"skipped={stats['skipped']} "
        f"errors={stats['errors']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
