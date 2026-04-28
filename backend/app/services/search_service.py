from app.db.db import get_connection
from app.services.openai_service import create_chat_completion, create_embedding


SEARCH_LIMIT = 10
SCORE_THRESHOLD = 0.47
TITLE_KEYWORD_BOOST = 0.5
CONTENT_KEYWORD_BOOST = 0.2
FALLBACK_RESULT_LIMIT = 3
QUERY_EXPANSION_RULES = (
    (("오심", "구토"), "nausea vomiting PONV"),
    (("통증",), "pain analgesia"),
    (("마취",), "anesthesia anesthesia-related"),
)


def _embedding_to_vector(embedding: list[float]) -> str:
    return "[" + ",".join(map(str, embedding)) + "]"


def expand_query(query: str) -> str:
    normalized_query = query.strip()
    if not normalized_query:
        return query

    expansions = []

    for keywords, expanded_terms in QUERY_EXPANSION_RULES:
        if any(keyword in normalized_query for keyword in keywords):
            expansions.append(expanded_terms)

    if not expansions:
        return normalized_query

    return " ".join([normalized_query, *dict.fromkeys(expansions)])


def _build_keyword_pattern(query: str) -> str | None:
    normalized_query = query.strip()
    if not normalized_query:
        return None

    escaped_query = (
        normalized_query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    )
    return f"%{escaped_query}%"


def _fetch_search_rows(embedding: list[float], query: str):
    embedding_vector = _embedding_to_vector(embedding)
    keyword_pattern = _build_keyword_pattern(query)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    r.id,
                    r.title,
                    r.resource_type,
                    r.abstract,
                    r.source_url,
                    rs.content,
                    (rs.embedding <-> %s::vector) AS distance,
                    (
                        CASE
                            WHEN r.title ILIKE %s ESCAPE '\\' THEN {TITLE_KEYWORD_BOOST}
                            ELSE 0.0
                        END
                        +
                        CASE
                            WHEN rs.content ILIKE %s ESCAPE '\\' THEN {CONTENT_KEYWORD_BOOST}
                            ELSE 0.0
                        END
                    ) AS keyword_boost
                FROM resource_segments rs
                JOIN resources r ON rs.resource_id = r.id
                WHERE rs.embedding IS NOT NULL
                ORDER BY
                    (rs.embedding <-> %s::vector)
                    -
                    (
                        CASE
                            WHEN r.title ILIKE %s ESCAPE '\\' THEN {TITLE_KEYWORD_BOOST}
                            ELSE 0.0
                        END
                        +
                        CASE
                            WHEN rs.content ILIKE %s ESCAPE '\\' THEN {CONTENT_KEYWORD_BOOST}
                            ELSE 0.0
                        END
                    ),
                    (rs.embedding <-> %s::vector)
                LIMIT %s;
                """,
                (
                    embedding_vector,
                    keyword_pattern,
                    keyword_pattern,
                    embedding_vector,
                    keyword_pattern,
                    keyword_pattern,
                    embedding_vector,
                    SEARCH_LIMIT,
                ),
            )
            return cur.fetchall()


def _calculate_score(distance: float, keyword_boost: float) -> float:
    distance_value = float(distance)
    keyword_boost_value = float(keyword_boost)
    return round((1 / (1 + distance_value)) + keyword_boost_value, 4)


def _build_results(rows) -> list[dict]:
    return [
        {
            "resource_id": row[0],
            "title": row[1],
            "resource_type": row[2],
            "abstract": row[3],
            "source_url": row[4],
            "content": row[5],
            "score": _calculate_score(row[6], row[7]),
        }
        for row in rows
    ]


def _sort_results_by_score(results: list[dict]) -> list[dict]:
    return sorted(results, key=lambda item: item["score"], reverse=True)


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
    return [item for item in results if item["score"] >= SCORE_THRESHOLD]


def _apply_result_fallback(results: list[dict]) -> list[dict]:
    filtered_results = _apply_score_threshold(results)
    if filtered_results:
        return filtered_results

    return results[:FALLBACK_RESULT_LIMIT]


def _build_context(results: list[dict]) -> str:
    top_results = results[:2]
    return "\n\n".join(
        f"{item['title']}\n{item['content']}" for item in top_results
    )


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
    expanded_query = expand_query(query)
    embedding = create_embedding(expanded_query)
    rows = _fetch_search_rows(embedding, query)
    raw_results = _build_results(rows)
    sorted_results = _sort_results_by_score(raw_results)
    deduplicated_results = _deduplicate_results(sorted_results)
    filtered_results = _apply_result_fallback(deduplicated_results)
    context = _build_context(filtered_results)
    answer = create_chat_completion(query=query, context=context)

    return {
        "query": query,
        "answer": answer,
        "count": len(filtered_results),
        "citations": _build_citations(filtered_results),
        "results": filtered_results,
    }
