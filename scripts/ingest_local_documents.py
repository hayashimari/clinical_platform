"""
Ingest local TXT/PDF documents into resources and resource_segments.

Usage:
    python scripts/ingest_local_documents.py
"""

from __future__ import annotations

import math
import re
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
INPUT_DIR = ROOT_DIR / "data" / "local_documents"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


SUPPORTED_EXTENSIONS = {".txt", ".pdf"}
RESOURCE_TYPE = "local_document"
SOURCE_TYPE = "local_file"
DEFAULT_SPECIALTY = "general"
DEFAULT_LANGUAGE = "ko"
ABSTRACT_LENGTH = 1000
MIN_CHUNK_SIZE = 1000
MAX_CHUNK_SIZE = 1500
TEXT_ENCODINGS = ("utf-8", "utf-8-sig", "cp949")
BOUNDARY_PATTERN = re.compile(r"(?<=[.!?。！？])\s+|\s+")

PdfReader = None
PDF_IMPORT_ERROR: Exception | None = None

try:
    from pypdf import PdfReader  # type: ignore[assignment]
except ImportError:
    try:
        from PyPDF2 import PdfReader  # type: ignore[assignment]
    except ImportError as pypdf2_error:
        PDF_IMPORT_ERROR = pypdf2_error
    else:
        PDF_IMPORT_ERROR = None
else:
    PDF_IMPORT_ERROR = None


def list_input_files() -> list[Path]:
    if not INPUT_DIR.exists():
        return []

    return sorted(
        [
            path
            for path in INPUT_DIR.iterdir()
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
        ],
        key=lambda path: path.name.lower(),
    )


def get_db_connection():
    from app.db.db import get_connection

    return get_connection()


def ensure_resource_columns(cursor) -> None:
    for column_name in ("source_type", "source_file_name", "specialty", "language"):
        cursor.execute(
            f"""
            ALTER TABLE resources
            ADD COLUMN IF NOT EXISTS {column_name} TEXT
            """
        )


def extract_txt_text(path: Path) -> str:
    raw_bytes = path.read_bytes()

    for encoding in TEXT_ENCODINGS:
        try:
            return raw_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue

    return raw_bytes.decode("utf-8", errors="ignore")


def extract_pdf_text(path: Path) -> str:
    if PdfReader is None:
        detail = f": {PDF_IMPORT_ERROR}" if PDF_IMPORT_ERROR else ""
        raise RuntimeError(f"pdf parser unavailable{detail}")

    try:
        reader = PdfReader(str(path))
    except Exception as exc:  # pragma: no cover - depends on external PDF parsing
        raise RuntimeError(f"failed to open pdf: {exc}") from exc

    page_texts: list[str] = []
    for page in reader.pages:
        try:
            page_texts.append(page.extract_text() or "")
        except Exception:
            continue

    return "\n".join(page_texts)


def read_document_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".txt":
        return extract_txt_text(path)
    if suffix == ".pdf":
        return extract_pdf_text(path)
    raise RuntimeError(f"unsupported extension: {suffix}")


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def build_abstract(text: str) -> str:
    return text[:ABSTRACT_LENGTH]


def choose_chunk_boundary(text: str, target_end: int, min_end: int, max_end: int) -> int:
    if max_end >= len(text):
        return len(text)

    search_window = text[min_end:max_end]
    best_boundary: int | None = None
    best_distance: int | None = None

    for match in BOUNDARY_PATTERN.finditer(search_window):
        boundary = min_end + match.end()
        distance = abs(boundary - target_end)
        if best_boundary is None or distance < best_distance:
            best_boundary = boundary
            best_distance = distance

    return best_boundary or max_end


def chunk_text(text: str) -> list[str]:
    normalized = normalize_text(text)
    if not normalized:
        return []

    if len(normalized) <= MAX_CHUNK_SIZE:
        return [normalized]

    chunk_count = math.ceil(len(normalized) / MAX_CHUNK_SIZE)
    target_size = math.ceil(len(normalized) / chunk_count)
    chunks: list[str] = []
    start = 0

    while start < len(normalized):
        remaining = len(normalized) - start
        remaining_chunks = max(1, chunk_count - len(chunks))

        if remaining <= MAX_CHUNK_SIZE or remaining_chunks == 1:
            final_chunk = normalized[start:].strip()
            if final_chunk:
                chunks.append(final_chunk)
            break

        min_end = min(len(normalized), start + MIN_CHUNK_SIZE)
        max_end = min(len(normalized), start + MAX_CHUNK_SIZE)
        target_end = min(max_end, max(min_end, start + target_size))
        end = choose_chunk_boundary(normalized, target_end, min_end, max_end)

        if end <= start:
            end = max_end

        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)

        start = end
        while start < len(normalized) and normalized[start].isspace():
            start += 1

    return chunks


def insert_resource(cursor, title: str, abstract: str, source_file_name: str) -> int:
    cursor.execute(
        """
        INSERT INTO resources (
            title,
            resource_type,
            abstract,
            source_url,
            source_type,
            source_file_name,
            specialty,
            language
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            title,
            RESOURCE_TYPE,
            abstract,
            None,
            SOURCE_TYPE,
            source_file_name,
            DEFAULT_SPECIALTY,
            DEFAULT_LANGUAGE,
        ),
    )
    return cursor.fetchone()[0]


def insert_segments(cursor, resource_id: int, segments: list[str]) -> None:
    for segment_index, content in enumerate(segments):
        cursor.execute(
            """
            INSERT INTO resource_segments (resource_id, segment_index, content, embedding)
            VALUES (%s, %s, %s, %s)
            """,
            (resource_id, segment_index, content, None),
        )


def ingest_file(session, path: Path) -> tuple[str, int | None, int]:
    print(f"[START] filename={path.name}")

    try:
        raw_text = read_document_text(path)
    except RuntimeError as exc:
        return (f"[SKIP] filename={path.name} reason={exc}", None, 0)
    except Exception as exc:
        return (f"[SKIP] filename={path.name} reason=read failed: {exc}", None, 0)

    normalized_text = normalize_text(raw_text)
    if not normalized_text:
        return (f"[SKIP] filename={path.name} reason=no text", None, 0)

    segments = chunk_text(normalized_text)
    if not segments:
        return (f"[SKIP] filename={path.name} reason=no text", None, 0)

    title = path.stem
    abstract = build_abstract(normalized_text)

    try:
        with session.cursor() as cursor:
            resource_id = insert_resource(cursor, title, abstract, path.name)
            insert_segments(cursor, resource_id, segments)
        session.commit()
    except Exception as exc:
        session.rollback()
        return (f"[ERROR] filename={path.name} reason={exc}", None, 0)

    return (f"stored resource_id={resource_id} segments={len(segments)}", resource_id, len(segments))


def main() -> int:
    if not INPUT_DIR.exists():
        print(f"Input directory not found: {INPUT_DIR}", file=sys.stderr)
        return 1

    files = list_input_files()
    if not files:
        print(f"No supported files found in {INPUT_DIR}")
        return 0

    try:
        session = get_db_connection()
    except Exception as exc:
        print(f"Failed to connect to database: {exc}", file=sys.stderr)
        return 1

    stored_count = 0
    skipped_count = 0
    error_count = 0

    try:
        with session.cursor() as cursor:
            ensure_resource_columns(cursor)
        session.commit()

        for path in files:
            message, resource_id, _ = ingest_file(session, path)
            print(message)

            if resource_id is not None:
                stored_count += 1
            elif message.startswith("[ERROR]"):
                error_count += 1
            else:
                skipped_count += 1
    finally:
        session.close()

    print(
        "ingestion complete | "
        f"stored={stored_count} skipped={skipped_count} errors={error_count}"
    )
    return 0 if error_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
