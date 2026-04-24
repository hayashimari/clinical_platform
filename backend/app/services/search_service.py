import re

from app.db.db import get_connection
from app.services.openai_service import CHAT_MODEL, create_embedding, get_openai_client


SEARCH_LIMIT = 5
CONTEXT_LIMIT = 4
CONTEXT_CHAR_LIMIT = 1800
SCORE_THRESHOLD = 0.15
TITLE_MATCH_BONUS = 0.2
CONTENT_MATCH_BONUS = 0.1
TITLE_RERANK_BONUS = 0.1
CONTENT_RERANK_BONUS = 0.05
ANSWER_SYSTEM_PROMPT = (
    "You are a clinical evidence assistant. "
    "Answer clearly and concisely using the provided sources."
)


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


def _extract_query_terms(query: str) -> list[str]:
    terms = re.findall(r"\w+", query.lower())
    if not terms and query.strip():
        terms = [query.strip().lower()]

    unique_terms = []
    seen_terms = set()

    for term in terms:
        if term in seen_terms:
            continue
        unique_terms.append(term)
        seen_terms.add(term)

    return unique_terms


def _extract_text_terms(text: str) -> set[str]:
    return set(re.findall(r"\w+", text.lower()))


def _calculate_keyword_score(query_terms: list[str], title: str, content: str) -> float:
    title_lower = title.lower()
    content_lower = content.lower()
    keyword_score = 0.0

    for term in query_terms:
        if term in title_lower:
            keyword_score += TITLE_MATCH_BONUS
        if term in content_lower:
            keyword_score += CONTENT_MATCH_BONUS

    return keyword_score


def _build_results(rows, query: str) -> list[dict]:
    query_terms = _extract_query_terms(query)
    results = []

    for row in rows:
        distance = float(row[6])
        vector_score = _calculate_score(distance)
        keyword_score = _calculate_keyword_score(
            query_terms=query_terms,
            title=row[1] or "",
            content=row[5] or "",
        )
        final_score = vector_score + keyword_score

        results.append(
            {
                "resource_id": row[0],
                "title": row[1],
                "resource_type": row[2],
                "abstract": row[3],
                "source_url": row[4],
                "content": row[5],
                "distance": distance,
                "vector_score": vector_score,
                "keyword_score": keyword_score,
                "final_score": final_score,
                "score": final_score,
            }
        )

    return results


def _sort_results_by_final_score(results: list[dict]) -> list[dict]:
    return sorted(
        results,
        key=lambda item: (-item["final_score"], item["distance"]),
    )


def _calculate_overlap_score(query_terms: list[str], content: str) -> float:
    if not query_terms:
        return 0.0

    content_terms = _extract_text_terms(content)
    overlapping_terms = {term for term in query_terms if term in content_terms}
    return len(overlapping_terms) / len(query_terms)


def rerank_results(query: str, results: list[dict]) -> list[dict]:
    query_terms = _extract_query_terms(query)
    reranked_results = []

    for item in results:
        title = item["title"] or ""
        content = item["content"] or ""
        title_lower = title.lower()
        content_lower = content.lower()
        direct_match_bonus = 0.0

        for term in query_terms:
            if term in title_lower:
                direct_match_bonus += TITLE_RERANK_BONUS
            if term in content_lower:
                direct_match_bonus += CONTENT_RERANK_BONUS

        overlap_score = _calculate_overlap_score(query_terms, content)
        rerank_score = item["final_score"] + overlap_score + direct_match_bonus

        reranked_results.append(
            {
                **item,
                "overlap_score": overlap_score,
                "rerank_score": rerank_score,
            }
        )

    return sorted(
        reranked_results,
        key=lambda item: (
            -item["rerank_score"],
            -item["final_score"],
            item["distance"],
        ),
    )


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
    return [item for item in results if item["final_score"] > SCORE_THRESHOLD]


def _truncate_text(text: str, max_chars: int) -> str:
    normalized_text = " ".join(text.split())

    if max_chars <= 0:
        return ""
    if len(normalized_text) <= max_chars:
        return normalized_text
    if max_chars <= 3:
        return normalized_text[:max_chars]

    return normalized_text[: max_chars - 3].rstrip() + "..."


def _build_context(results: list[dict]) -> str:
    context_blocks = []
    current_length = 0

    for item in results[:CONTEXT_LIMIT]:
        source_index = len(context_blocks) + 1
        title = (item["title"] or "Untitled Source").strip()
        content = (item["content"] or "").strip()
        separator = "\n\n" if context_blocks else ""
        header = f"[Source {source_index}: {title}]\n"
        available_chars = CONTEXT_CHAR_LIMIT - current_length - len(separator) - len(header)

        if available_chars <= 0:
            break

        truncated_content = _truncate_text(content, available_chars)
        if not truncated_content:
            continue

        block = f"{header}{truncated_content}"
        context_blocks.append(f"{separator}{block}" if context_blocks else block)
        current_length += len(context_blocks[-1])

        if current_length >= CONTEXT_CHAR_LIMIT:
            break

    return "".join(context_blocks)


def _generate_answer(query: str, context: str) -> str:
    response = get_openai_client().chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": ANSWER_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Question:\n{query}\n\n"
                    f"Context:\n{context or 'No relevant sources were retrieved.'}\n\n"
                    "Please synthesize the sources when possible. "
                    "If the sources are insufficient, say so instead of guessing."
                ),
            },
        ],
    )

    return response.choices[0].message.content or ""


def _build_citations(results: list[dict]) -> list[dict]:
    return [
        {
            "title": item["title"],
            "resource_type": item["resource_type"],
            "source_url": item["source_url"],
            "content": item["content"],
            "score": item["score"],
            "vector_score": item["vector_score"],
            "keyword_score": item["keyword_score"],
            "overlap_score": item["overlap_score"],
            "rerank_score": item["rerank_score"],
        }
        for item in results
    ]


def search_documents(query: str) -> dict:
    embedding = create_embedding(query)
    rows = _fetch_search_rows(embedding)
    raw_results = _build_results(rows, query)
    hybrid_sorted_results = _sort_results_by_final_score(raw_results)
    reranked_results = rerank_results(query, hybrid_sorted_results)
    deduplicated_results = _deduplicate_results(reranked_results)
    filtered_results = _apply_score_threshold(deduplicated_results)
    context = _build_context(filtered_results)
    answer = _generate_answer(query=query, context=context)

    return {
        "query": query,
        "answer": answer,
        "count": len(filtered_results),
        "citations": _build_citations(filtered_results),
        "results": filtered_results,
    }
