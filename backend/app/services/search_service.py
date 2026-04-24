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
DEFAULT_ANSWER_MODE = "clinical_summary"
PAPER_PRESENTATION_MODE = "paper_presentation"
SUPPORTED_ANSWER_MODES = {DEFAULT_ANSWER_MODE, PAPER_PRESENTATION_MODE}
CLINICAL_SUMMARY_SYSTEM_PROMPT = (
    "You are a clinical evidence assistant. "
    "Use only the provided sources. "
    "Do not add unsupported facts, recommendations, methods, or outcomes. "
    "If the sources are insufficient, say so clearly and briefly."
)
PAPER_PRESENTATION_SYSTEM_PROMPT = (
    "You are helping a first-year anesthesiology and pain medicine resident prepare a paper presentation. "
    "Use only the provided sources. "
    "Do not invent missing sections, methods, or results. "
    "If the retrieved text does not contain enough detail, say so explicitly."
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


def _is_korean_query(text: str) -> bool:
    return bool(re.search(r"[가-힣]", text))


def _normalize_answer_mode(answer_mode: str | None) -> str:
    normalized = (answer_mode or DEFAULT_ANSWER_MODE).strip().lower()
    if normalized in SUPPORTED_ANSWER_MODES:
        return normalized
    return DEFAULT_ANSWER_MODE


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


def _build_clinical_summary_user_prompt(query: str, context: str, is_korean: bool) -> str:
    if is_korean:
        return (
            f"Question:\n{query}\n\n"
            f"Context:\n{context or '제공된 검색 결과가 없습니다.'}\n\n"
            "지시사항:\n"
            "- 한국어로 답변하세요.\n"
            "- 제공된 검색 결과에 근거한 내용만 사용하세요.\n"
            "- 근거 없는 내용은 생성하지 마세요.\n"
            "- 전체 답변은 최대 10~15줄 이내로 간결하게 작성하세요.\n"
            "- clinical / professional tone을 유지하세요.\n"
            "- 아래 형식을 그대로 사용하세요.\n\n"
            "[요약]\n"
            "핵심 결론 2~3줄\n\n"
            "[권장 전략]\n"
            "- actionable recommendation 위주\n\n"
            "[근거]\n"
            "- citation 기반 요약\n\n"
            "[주의사항]\n"
            "- complication / limitation\n\n"
            "근거가 부족한 경우에는 부족하다고 명확히 쓰세요."
        )

    return (
        f"Question:\n{query}\n\n"
        f"Context:\n{context or 'No relevant sources were retrieved.'}\n\n"
        "Instructions:\n"
        "- Answer in English.\n"
        "- Use only the provided search results.\n"
        "- Do not generate unsupported claims.\n"
        "- Keep the whole answer within about 10-15 lines.\n"
        "- Maintain a clinical, professional tone.\n"
        "- Use this exact structure.\n\n"
        "[Summary]\n"
        "Core conclusion in 2-3 lines\n\n"
        "[Recommended Strategy]\n"
        "- Actionable recommendations only\n\n"
        "[Evidence]\n"
        "- Citation-based summary\n\n"
        "[Cautions]\n"
        "- Complications / limitations\n\n"
        "If the evidence is insufficient, state that clearly."
    )


def _build_paper_presentation_user_prompt(query: str, context: str, is_korean: bool) -> str:
    if is_korean:
        return (
            f"Question:\n{query}\n\n"
            f"Context:\n{context or '제공된 검색 결과가 없습니다.'}\n\n"
            "상황:\n"
            "나는 한국의 마취통증의학과 1년차 전공의이며, 이 논문을 교수님과 선배 전공의들 앞에서 "
            "발표할 파워포인트를 준비해야 합니다.\n\n"
            "지시사항:\n"
            "- 한국어로 답변하세요.\n"
            "- 제공된 검색 결과 또는 paper content에 근거한 내용만 사용하세요.\n"
            "- Feynman technique처럼 쉽게 풀어서, 그러나 충분히 깊이 있게 설명하세요.\n"
            "- section by section 형식으로 설명하세요.\n"
            "- 먼저 clinical background와 이 논문이 왜 중요한지 설명하세요.\n"
            "- 어려운 용어는 쉽게 정의하세요.\n"
            "- methodology는 plain language로 설명하세요.\n"
            "- key findings를 정리하세요.\n"
            "- 마취통증의학과 관점의 clinical implications를 설명하세요.\n"
            "- limitations를 짚어주세요.\n"
            "- 교수님/선배가 물어볼 수 있는 질문을 제안하세요.\n"
            "- 마지막에는 slide-by-slide PowerPoint outline으로 끝내세요.\n"
            "- 검색 결과에 없는 section, methodology, result는 추정하지 말고 "
            "'제공된 검색 결과만으로는 확인되지 않습니다'라고 쓰세요."
        )

    return (
        f"Question:\n{query}\n\n"
        f"Context:\n{context or 'No relevant sources were retrieved.'}\n\n"
        "I’m a first-year anesthesiology and pain medicine resident in Korea. "
        "I need to prepare a PowerPoint presentation that summarizes this paper "
        "section-by-section and present it to faculty and senior residents in my department.\n\n"
        "Please explain this paper using the Feynman technique, in as much detail as possible, "
        "as if you were the author, and help me understand it deeply.\n\n"
        "Requirements:\n"
        "- Explain section by section.\n"
        "- Start with clinical background and why this paper matters.\n"
        "- Define difficult terms simply.\n"
        "- Explain methodology in plain language.\n"
        "- Summarize key findings.\n"
        "- Explain clinical implications for anesthesiology and pain medicine.\n"
        "- Point out limitations.\n"
        "- Suggest possible faculty/senior resident questions.\n"
        "- End with a slide-by-slide PowerPoint outline.\n"
        "- Use only the provided search results or paper content.\n"
        "- If a section is not supported by the provided text, say it is not available in the retrieved sources."
    )


def _build_answer_messages(query: str, context: str, answer_mode: str):
    is_korean = _is_korean_query(query)

    if answer_mode == PAPER_PRESENTATION_MODE:
        return [
            {"role": "system", "content": PAPER_PRESENTATION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": _build_paper_presentation_user_prompt(
                    query=query,
                    context=context,
                    is_korean=is_korean,
                ),
            },
        ]

    return [
        {"role": "system", "content": CLINICAL_SUMMARY_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": _build_clinical_summary_user_prompt(
                query=query,
                context=context,
                is_korean=is_korean,
            ),
        },
    ]


def _generate_answer(query: str, context: str, answer_mode: str) -> str:
    response = get_openai_client().chat.completions.create(
        model=CHAT_MODEL,
        messages=_build_answer_messages(
            query=query,
            context=context,
            answer_mode=answer_mode,
        ),
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


def search_documents(query: str, answer_mode: str = DEFAULT_ANSWER_MODE) -> dict:
    normalized_answer_mode = _normalize_answer_mode(answer_mode)
    embedding = create_embedding(query)
    rows = _fetch_search_rows(embedding)
    raw_results = _build_results(rows, query)
    hybrid_sorted_results = _sort_results_by_final_score(raw_results)
    reranked_results = rerank_results(query, hybrid_sorted_results)
    deduplicated_results = _deduplicate_results(reranked_results)
    filtered_results = _apply_score_threshold(deduplicated_results)
    context = _build_context(filtered_results)
    answer = _generate_answer(
        query=query,
        context=context,
        answer_mode=normalized_answer_mode,
    )

    return {
        "query": query,
        "answer": answer,
        "count": len(filtered_results),
        "citations": _build_citations(filtered_results),
        "results": filtered_results,
    }
