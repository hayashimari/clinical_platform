from app.db.db import get_connection
from app.services.openai_service import create_chat_completion, create_embedding


SEARCH_LIMIT = 10
CONTEXT_LIMIT = 2
SCORE_THRESHOLD = 0.15


def _embedding_to_vector(embedding: list[float]) -> str:
    return "[" + ",".join(map(str, embedding)) + "]"


def _fetch_search_rows(embedding: list[float]):
    embedding_vector = _embedding_to_vector(embedding)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    r.id,
                    r.title,
                    r.resource_type,
                    r.abstract,
                    r.source_url,
                    rs.content,
                    (rs.embedding <-> %s::vector) AS distance
                FROM resource_segments rs
                JOIN resources r ON rs.resource_id = r.id
                WHERE rs.embedding IS NOT NULL
                ORDER BY distance
                LIMIT %s;
                """,
                (embedding_vector, SEARCH_LIMIT),
            )
            return cur.fetchall()


def _calculate_score(distance: float) -> float:
    return 1 - distance


def _build_results(rows) -> list[dict]:
    return [
        {
            "resource_id": row[0],
            "title": row[1],
            "resource_type": row[2],
            "abstract": row[3],
            "source_url": row[4],
            "content": row[5],
            "score": _calculate_score(row[6]),
        }
        for row in rows
    ]


def _deduplicate_results(results: list[dict]) -> list[dict]:
    seen_resource_ids = set()
    deduplicated = []

    for item in results:
        resource_id = item["resource_id"]
        if resource_id in seen_resource_ids:
            continue

        deduplicated.append(item)
        seen_resource_ids.add(resource_id)

    return deduplicated


def _apply_score_threshold(results: list[dict]) -> list[dict]:
    return [item for item in results if item["score"] > SCORE_THRESHOLD]


def _build_context(rows) -> str:
    top_rows = rows[:CONTEXT_LIMIT]
    return "\n\n".join(row[5] for row in top_rows)


def _build_citations(results: list[dict]) -> list[dict]:
    return [
        {
            "title": item["title"],
            "resource_type": item["resource_type"],
            "source_url": item["source_url"],
            "content": item["content"],
            "score": item["score"],
        }
        for item in results
    ]


def search_documents(db, query: str) -> dict:
    embedding = create_embedding(query)
    rows = _fetch_search_rows(embedding)
    raw_results = _build_results(rows)
    deduplicated_results = _deduplicate_results(raw_results)
    filtered_results = _apply_score_threshold(deduplicated_results)
    context = _build_context(rows)
    answer = create_chat_completion(query=query, context=context)

    return {
        "query": query,
        "answer": answer,
        "count": len(filtered_results),
        "citations": _build_citations(filtered_results),
        "results": filtered_results,
    }
