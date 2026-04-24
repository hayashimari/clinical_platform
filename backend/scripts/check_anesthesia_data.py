"""
Inspect anesthesia-focused PubMed records already stored in the local database.

Example:
    cd backend
    python scripts/check_anesthesia_data.py --limit 30
"""

import argparse
import re
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.db import SessionLocal


ANESTHESIA_KEYWORDS = [
    "postoperative pain multimodal analgesia",
    "opioid sparing postoperative pain",
    "regional anesthesia nerve block",
    "ultrasound guided nerve block",
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check anesthesia-focused PubMed data stored in resources."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of matching rows to print.",
    )
    return parser.parse_args()


def normalize_terms(text: str) -> set[str]:
    return set(re.findall(r"\w+", text.lower()))


def best_matching_keyword(text: str) -> tuple[str, float]:
    text_lower = text.lower()
    text_terms = normalize_terms(text)
    best_keyword = "unmatched"
    best_score = 0.0

    for keyword in ANESTHESIA_KEYWORDS:
        keyword_terms = normalize_terms(keyword)
        if not keyword_terms:
            continue

        phrase_bonus = 1.0 if keyword.lower() in text_lower else 0.0
        overlap_score = len(keyword_terms & text_terms) / len(keyword_terms)
        score = phrase_bonus + overlap_score

        if score > best_score:
            best_keyword = keyword
            best_score = score

    return best_keyword, best_score


def check_anesthesia_data(limit: int) -> None:
    session = SessionLocal()

    try:
        with session.cursor() as cursor:
            cursor.execute(
                """
                SELECT title, abstract, source_url
                FROM resources
                WHERE resource_type = %s
                  AND source_url LIKE %s
                ORDER BY id DESC
                """,
                ("paper", "https://pubmed.ncbi.nlm.nih.gov/%"),
            )
            rows = cursor.fetchall()
    finally:
        session.close()

    matched_rows = []
    keyword_counts = {keyword: 0 for keyword in ANESTHESIA_KEYWORDS}

    for title, abstract, source_url in rows:
        combined_text = f"{title or ''}\n{abstract or ''}".strip()
        keyword, score = best_matching_keyword(combined_text)

        if keyword == "unmatched" or score <= 0:
            continue

        keyword_counts[keyword] += 1
        matched_rows.append((keyword, title or "", source_url or ""))

    print(f"Anesthesia PubMed resources found: {len(matched_rows)}")
    print("\nCounts by keyword:")
    for keyword in ANESTHESIA_KEYWORDS:
        print(f"- {keyword}: {keyword_counts[keyword]}")

    print("\nSample rows:")
    for keyword, title, source_url in matched_rows[:limit]:
        preview = title if len(title) <= 100 else title[:97] + "..."
        print(f"- [{keyword}] {preview}")
        print(f"  {source_url}")


def main() -> int:
    args = parse_args()

    if args.limit <= 0:
        print("--limit must be greater than 0.", file=sys.stderr)
        return 1

    try:
        check_anesthesia_data(limit=args.limit)
    except Exception as exc:
        print(f"Check failed: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
