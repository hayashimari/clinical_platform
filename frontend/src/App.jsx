import { useState } from "react";

const pageStyle = {
  minHeight: "100vh",
  background:
    "linear-gradient(180deg, #f3f8fb 0%, #eef4f8 22%, #f8fbfd 100%)",
  color: "#102c44",
  fontFamily:
    '"Segoe UI", "Noto Sans KR", "Apple SD Gothic Neo", sans-serif',
};

const containerStyle = {
  width: "min(900px, calc(100% - 32px))",
  margin: "0 auto",
  padding: "32px 0 64px",
};

const surfaceStyle = {
  backgroundColor: "#ffffff",
  border: "1px solid #c8dae5",
  borderRadius: "18px",
  boxShadow: "0 16px 32px rgba(16, 61, 92, 0.1)",
};

const sectionTitleStyle = {
  margin: 0,
  fontSize: "1.15rem",
  fontWeight: 700,
  color: "#0f2e46",
};

const cardTitleStyle = {
  margin: 0,
  fontSize: "1rem",
  fontWeight: 700,
  color: "#0f2f48",
  lineHeight: 1.45,
};

const metricStyle = {
  fontSize: "0.78rem",
  color: "#4f677a",
};

const primaryButtonStyle = {
  border: "none",
  borderRadius: "12px",
  backgroundColor: "#0c5f7e",
  color: "#ffffff",
  padding: "12px 18px",
  fontSize: "0.95rem",
  fontWeight: 600,
  cursor: "pointer",
};

const linkButtonStyle = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  padding: "10px 16px",
  borderRadius: "12px",
  background: "linear-gradient(135deg, #0d6686 0%, #0b84ad 100%)",
  color: "#f8fdff",
  fontSize: "0.88rem",
  fontWeight: 700,
  textDecoration: "none",
  boxShadow: "0 10px 20px rgba(11, 105, 136, 0.22)",
};

const badgeStyle = {
  display: "inline-flex",
  alignItems: "center",
  padding: "6px 10px",
  borderRadius: "999px",
  backgroundColor: "#e6f1f7",
  color: "#35546a",
  fontSize: "0.78rem",
  fontWeight: 700,
};

const NO_EVIDENCE_MESSAGE =
  "관련 근거를 찾지 못했습니다. 다른 키워드로 검색해 주세요.";
const MIN_VISIBLE_RESULTS = 5;
const SUMMARY_EMPHASIS_TERMS = [
  "regional anesthesia",
  "postoperative pain",
  "pain management",
  "perioperative care",
  "postoperative nausea vomiting",
  "analgesia",
  "anesthesia",
  "anaesthesia",
  "nausea",
  "vomiting",
  "PONV",
  "오심",
  "구토",
  "통증",
  "마취",
];

function App() {
  const [query, setQuery] = useState("");
  const [searchedQuery, setSearchedQuery] = useState("");
  const [resourceType, setResourceType] = useState("all");
  const [answer, setAnswer] = useState("");
  const [citations, setCitations] = useState([]);
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [hasSearched, setHasSearched] = useState(false);

  const handleSearch = async () => {
    const trimmedQuery = query.trim();

    if (!trimmedQuery) return;

    setHasSearched(true);
    setLoading(true);
    setError("");

    try {
      const res = await fetch("https://clinical-platform-api-b2wt.onrender.com/api/v1/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: trimmedQuery }),
      });

      if (!res.ok) {
        throw new Error("검색 요청 실패");
      }

      const data = await res.json();
      const nextAnswer = data.answer || "";
      const nextCitations = data.citations || [];
      const nextResults = data.results || [];

      setSearchedQuery(trimmedQuery);
      setResourceType("all");
      setAnswer(nextAnswer);
      setCitations(nextCitations);
      setResults(nextResults);
      setError(!nextAnswer.trim() && nextResults.length > 0 ? NO_EVIDENCE_MESSAGE : "");
    } catch {
      setAnswer("");
      setCitations([]);
      setResults([]);
      setError(NO_EVIDENCE_MESSAGE);
    } finally {
      setLoading(false);
    }
  };

  const renderHighlightedText = (text) => {
    const safeText = typeof text === "string" ? text : String(text ?? "");
    const normalizedQuery = searchedQuery.trim();

    if (!normalizedQuery) {
      return safeText;
    }

    const escapedQuery = normalizedQuery.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const parts = safeText.split(new RegExp(`(${escapedQuery})`, "gi"));

    return parts.map((part, idx) =>
      part.toLowerCase() === normalizedQuery.toLowerCase() ? (
        <mark key={idx}>{part}</mark>
      ) : (
        part
      )
    );
  };

  const buildEmphasisTerms = () => {
    const queryTerms = searchedQuery
      .split(/\s+/)
      .map((term) => term.replace(/[^\p{L}\p{N}-]/gu, "").trim())
      .filter((term) => term.length > 1);

    return Array.from(
      new Set([...SUMMARY_EMPHASIS_TERMS, ...queryTerms])
    ).sort((left, right) => right.length - left.length);
  };

  const renderEmphasizedText = (text) => {
    const safeText = typeof text === "string" ? text : String(text ?? "");
    const emphasisTerms = buildEmphasisTerms();

    if (!safeText || emphasisTerms.length === 0) {
      return safeText;
    }

    const escapedTerms = emphasisTerms.map((term) =>
      term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
    );
    const emphasisRegex = new RegExp(`(${escapedTerms.join("|")})`, "gi");
    const normalizedTerms = new Set(
      emphasisTerms.map((term) => term.toLowerCase())
    );

    return safeText.split(emphasisRegex).map((part, idx) =>
      normalizedTerms.has(part.toLowerCase()) ? (
        <strong key={idx} style={{ color: "#0f3552", fontWeight: 800 }}>
          {part}
        </strong>
      ) : (
        part
      )
    );
  };

  const normalizeResourceType = (value) =>
    String(value ?? "").trim().toLowerCase();

  const formatResourceTypeLabel = (value) =>
    normalizeResourceType(value).replace(/_/g, " ");

  const matchesResourceType = (item) => {
    if (resourceType === "all") {
      return true;
    }

    return normalizeResourceType(item?.resource_type) === resourceType;
  };

  const buildVisibleResults = (items) => {
    const matchedItems = items.filter(matchesResourceType);
    const minimumVisibleCount = Math.min(MIN_VISIBLE_RESULTS, items.length);

    if (
      resourceType === "all" ||
      matchedItems.length >= minimumVisibleCount
    ) {
      return {
        items: matchedItems,
        matchedCount: matchedItems.length,
        isSupplemented: false,
      };
    }

    const supplementalItems = items.filter((item) => !matchesResourceType(item));

    return {
      items: [...matchedItems, ...supplementalItems].slice(0, minimumVisibleCount),
      matchedCount: matchedItems.length,
      isSupplemented: true,
    };
  };

  const getItemKey = (item, idx) =>
    item?.resource_id ?? item?.source_url ?? `${item?.title ?? "item"}-${idx}`;

  const formatScore = (value) =>
    typeof value === "number" ? value.toFixed(3) : null;

  const formatRelevance = (value) => {
    if (typeof value !== "number") {
      return null;
    }

    const normalizedValue = Math.max(0, Math.min(100, Math.round(value * 100)));
    return `관련도 ${normalizedValue}%`;
  };

  const buildSummaryBullets = (text) => {
    const safeText = typeof text === "string" ? text : String(text ?? "");
    const normalizedText = safeText.trim();

    if (!normalizedText) {
      return [];
    }

    const lines = normalizedText
      .split(/\n+/)
      .flatMap((line) => line.split(/(?<=[.!?])\s+/))
      .map((line) => line.replace(/^[\u2022\-*\d.)\s]+/, "").trim())
      .filter(Boolean);

    return lines.length > 0 ? lines : [normalizedText];
  };

  const buildResultPreview = (item) =>
    typeof item?.abstract === "string" && item.abstract.trim()
      ? item.abstract.trim()
      : String(item?.content ?? "").trim();

  const resourceTypeOptions = Array.from(
    new Set(
      [...results, ...citations]
        .map((item) => normalizeResourceType(item?.resource_type))
        .filter(Boolean)
    )
  );
  const filteredCitations = citations.filter(matchesResourceType);
  const {
    items: visibleResults,
    matchedCount: matchedResultCount,
    isSupplemented: isResultListSupplemented,
  } = buildVisibleResults(results);
  const showNoResultsMessage =
    hasSearched && !loading && !error && visibleResults.length === 0;

  return (
    <div style={pageStyle}>
      <div style={containerStyle}>
        <section
          style={{
            ...surfaceStyle,
            padding: "24px",
            marginBottom: "24px",
            background:
              "linear-gradient(145deg, #0f5e7c 0%, #13506f 58%, #183c5a 100%)",
            color: "#f6fbff",
          }}
        >
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: "20px",
              alignItems: "flex-end",
              justifyContent: "space-between",
            }}
          >
            <div style={{ flex: "1 1 320px" }}>
              <p
                style={{
                  margin: "0 0 10px",
                  fontSize: "0.82rem",
                  fontWeight: 700,
                  letterSpacing: "0.08em",
                  textTransform: "uppercase",
                  color: "#b7d9e7",
                }}
              >
                Clinical Evidence Search
              </p>
              <h1
                style={{
                  margin: "0 0 12px",
                  fontSize: "clamp(1.8rem, 4vw, 2.8rem)",
                  lineHeight: 1.15,
                }}
              >
                PubMed 근거 기반 임상 검색
              </h1>
              <p
                style={{
                  margin: 0,
                  color: "#dcecf3",
                  lineHeight: 1.7,
                  maxWidth: "760px",
                }}
              >
                임상 질문을 입력하면 관련 근거를 검색하고, AI가 핵심 내용을
                요약해 드립니다. 근거 논문과 검색 결과를 함께 확인할 수
                있습니다.
              </p>
            </div>
          </div>

          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSearch();
            }}
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: "12px",
              marginTop: "24px",
            }}
          >
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="예: postoperative nausea vomiting prevention"
              style={{
                flex: "1 1 360px",
                minWidth: 0,
                padding: "14px 16px",
                borderRadius: "14px",
                border: "1px solid rgba(255, 255, 255, 0.24)",
                backgroundColor: "rgba(255, 255, 255, 0.12)",
                color: "#ffffff",
                fontSize: "1rem",
              }}
            />

            <button
              type="submit"
              disabled={loading}
              style={{
                ...primaryButtonStyle,
                minWidth: "132px",
                backgroundColor: loading ? "#86a8b8" : "#f0fbff",
                color: "#0e4f6a",
              }}
            >
              {loading ? "검색 중..." : "검색"}
            </button>
          </form>

          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: "10px",
              alignItems: "center",
              marginTop: "14px",
            }}
          >
            <label
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                color: "#dcecf3",
                fontSize: "0.92rem",
              }}
            >
              <span>Resource Type</span>
              <select
                value={resourceType}
                onChange={(e) => setResourceType(e.target.value)}
                style={{
                  padding: "8px 10px",
                  borderRadius: "10px",
                  border: "1px solid rgba(255, 255, 255, 0.24)",
                  backgroundColor: "rgba(255, 255, 255, 0.12)",
                  color: "#ffffff",
                }}
              >
                <option value="all" style={{ color: "#153047" }}>
                  All
                </option>
                {resourceTypeOptions.map((option) => (
                  <option key={option} value={option} style={{ color: "#153047" }}>
                    {option}
                  </option>
                ))}
              </select>
            </label>

            {searchedQuery && (
              <span
                style={{
                  ...badgeStyle,
                  backgroundColor: "rgba(255, 255, 255, 0.12)",
                  color: "#eaf8ff",
                }}
              >
                최근 검색어: {searchedQuery}
              </span>
            )}
          </div>
        </section>

        {error && (
          <div
            style={{
              ...surfaceStyle,
              padding: "16px 18px",
              marginBottom: "20px",
              borderColor: "#f0c6c6",
              backgroundColor: "#fff5f5",
              color: "#b42318",
            }}
          >
            {error}
          </div>
        )}

        {answer && (
          <section
            style={{
              ...surfaceStyle,
              padding: "22px",
              marginBottom: "20px",
            }}
          >
            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                gap: "12px",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: "14px",
              }}
            >
              <div>
                <p
                  style={{
                    margin: "0 0 6px",
                    fontSize: "0.78rem",
                    fontWeight: 700,
                    letterSpacing: "0.08em",
                    textTransform: "uppercase",
                    color: "#6e8798",
                  }}
                >
                  AI Summary
                </p>
                <h2 style={{ ...sectionTitleStyle, fontSize: "1.3rem" }}>
                  임상 근거 요약
                </h2>
              </div>

              {filteredCitations.length > 0 && (
                <span style={badgeStyle}>
                  근거 논문 {filteredCitations.length}건
                </span>
              )}
            </div>

            <div
              style={{
                padding: "18px",
                borderRadius: "16px",
                background:
                  "linear-gradient(180deg, #f8fcfe 0%, #eaf3f8 100%)",
                border: "1px solid #cddfe9",
              }}
            >
              <div style={{ display: "grid", gap: "10px" }}>
                {buildSummaryBullets(answer).map((bullet, idx) => (
                  <div
                    key={`${bullet}-${idx}`}
                    style={{
                      display: "grid",
                      gridTemplateColumns: "16px 1fr",
                      gap: "10px",
                      alignItems: "flex-start",
                      padding: "10px 12px",
                      borderRadius: "12px",
                      backgroundColor: "#ffffff",
                      border: "1px solid #d9e7ef",
                    }}
                  >
                    <span
                      style={{
                        fontSize: "1rem",
                        lineHeight: 1.5,
                        color: "#0f6787",
                        fontWeight: 900,
                      }}
                    >
                      •
                    </span>
                    <div
                      style={{
                        lineHeight: 1.7,
                        color: "#1d405b",
                        fontSize: "0.97rem",
                      }}
                    >
                      {renderEmphasizedText(bullet)}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div style={{ marginTop: "18px" }}>
              <div
                style={{
                  display: "flex",
                  flexWrap: "wrap",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: "10px",
                  marginBottom: "12px",
                }}
              >
                <h3
                  style={{
                    margin: 0,
                    fontSize: "0.98rem",
                    fontWeight: 700,
                    color: "#163852",
                  }}
                >
                  사용된 근거
                </h3>
                <span style={metricStyle}>
                  요약에 연결된 citation을 바로 확인할 수 있습니다.
                </span>
              </div>

              {filteredCitations.length === 0 ? (
                <div
                  style={{
                    padding: "14px 16px",
                    borderRadius: "14px",
                    border: "1px solid #d8e5ec",
                    backgroundColor: "#f7fbfd",
                    color: "#6a7f90",
                    fontSize: "0.9rem",
                  }}
                >
                  표시할 근거가 없습니다.
                </div>
              ) : (
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
                    gap: "12px",
                  }}
                >
                  {filteredCitations.map((item, idx) => {
                    const isClickable = Boolean(item.source_url);

                    const citationCardStyle = {
                      padding: "14px 16px",
                      borderRadius: "16px",
                      border: "1px solid #d8e5ec",
                      background:
                        "linear-gradient(180deg, #fbfdfe 0%, #f1f7fa 100%)",
                      color: "#1f425d",
                      textDecoration: "none",
                      display: "flex",
                      flexDirection: "column",
                      gap: "10px",
                      minHeight: "138px",
                      cursor: isClickable ? "pointer" : "not-allowed",
                      opacity: isClickable ? 1 : 0.68,
                    };

                    const citationCardContent = (
                      <>
                        <div
                          style={{
                            display: "flex",
                            flexWrap: "wrap",
                            gap: "8px",
                            alignItems: "center",
                          }}
                        >
                          <span style={badgeStyle}>Source {idx + 1}</span>
                          {item.resource_type && (
                            <span
                              style={{
                                ...badgeStyle,
                                backgroundColor: "#eff7f1",
                                color: "#397153",
                              }}
                            >
                              {item.resource_type}
                            </span>
                          )}
                        </div>

                        <div
                          style={{
                            fontSize: "0.94rem",
                            fontWeight: 700,
                            color: "#163852",
                            lineHeight: 1.5,
                          }}
                        >
                          {item.title}
                        </div>

                        <div
                          style={{
                            display: "flex",
                            flexWrap: "wrap",
                            gap: "8px 12px",
                            marginTop: "auto",
                          }}
                        >
                          {formatScore(item.score) && (
                            <span style={metricStyle}>
                              score {formatScore(item.score)}
                            </span>
                          )}
                          <span
                            style={{
                              ...metricStyle,
                              color: isClickable ? "#0b6988" : "#7b8d9b",
                            }}
                          >
                            {isClickable ? "새 탭으로 열기" : "링크 없음"}
                          </span>
                        </div>
                      </>
                    );

                    if (!isClickable) {
                      return (
                        <div
                          key={getItemKey(item, idx)}
                          style={citationCardStyle}
                          aria-disabled="true"
                        >
                          {citationCardContent}
                        </div>
                      );
                    }

                    return (
                      <a
                        key={getItemKey(item, idx)}
                        href={item.source_url}
                        target="_blank"
                        rel="noreferrer"
                        style={citationCardStyle}
                      >
                        {citationCardContent}
                      </a>
                    );
                  })}
                </div>
              )}
            </div>
          </section>
        )}

        {answer && (
          <section style={{ marginBottom: "28px" }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                marginBottom: "14px",
              }}
            >
              <h2 style={sectionTitleStyle}>근거 논문</h2>
              <span style={metricStyle}>
                AI 요약에 사용된 citations를 확인할 수 있습니다.
              </span>
            </div>

            {filteredCitations.length === 0 ? (
              <div
                style={{
                  ...surfaceStyle,
                  padding: "26px",
                  textAlign: "center",
                  color: "#6a7f90",
                }}
              >
                표시할 근거 논문이 없습니다.
              </div>
            ) : (
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
                  gap: "16px",
                }}
              >
                {filteredCitations.map((item, idx) => (
                  <article
                    key={getItemKey(item, idx)}
                    style={{
                      ...surfaceStyle,
                      padding: "16px",
                      display: "flex",
                      flexDirection: "column",
                      gap: "10px",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        flexWrap: "wrap",
                        gap: "8px",
                        alignItems: "center",
                      }}
                    >
                      <span style={badgeStyle}>Source {idx + 1}</span>
                      {item.resource_type && (
                        <span
                          style={{
                            ...badgeStyle,
                            backgroundColor: "#eff7f1",
                            color: "#397153",
                          }}
                        >
                          {item.resource_type}
                        </span>
                      )}
                    </div>

                    <h3 style={cardTitleStyle}>{item.title}</h3>

                    {item.content && (
                      <p
                        style={{
                          margin: 0,
                          color: "#466073",
                          lineHeight: 1.7,
                          fontSize: "0.92rem",
                        }}
                      >
                        {renderHighlightedText(item.content)}
                      </p>
                    )}

                    <div
                      style={{
                        display: "flex",
                        flexWrap: "wrap",
                        gap: "8px 10px",
                      }}
                    >
                      {formatScore(item.score) && (
                        <span style={metricStyle}>score {formatScore(item.score)}</span>
                      )}
                      {formatScore(item.vector_score) && (
                        <span style={metricStyle}>
                          vector {formatScore(item.vector_score)}
                        </span>
                      )}
                      {formatScore(item.keyword_score) && (
                        <span style={metricStyle}>
                          keyword {formatScore(item.keyword_score)}
                        </span>
                      )}
                    </div>

                    {item.source_url && (
                      <a
                        href={item.source_url}
                        target="_blank"
                        rel="noreferrer"
                        style={{ ...linkButtonStyle, marginTop: "auto" }}
                      >
                        PubMed 보기
                      </a>
                    )}
                  </article>
                ))}
              </div>
            )}
          </section>
        )}

        <section>
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: "14px",
              gap: "12px",
            }}
          >
            <h2 style={sectionTitleStyle}>검색 결과</h2>
            <span style={metricStyle}>
              hybrid ranking과 reranking 이후의 상위 근거입니다.
            </span>
          </div>

        {isResultListSupplemented && (
          <div
            style={{
              ...surfaceStyle,
              padding: "14px 16px",
              marginBottom: "14px",
              background:
                "linear-gradient(180deg, #f8fcfe 0%, #eef6fa 100%)",
              borderColor: "#d6e6ee",
              color: "#30566f",
            }}
          >
            <strong style={{ color: "#153047" }}>{resourceType}</strong> 결과가{" "}
            {matchedResultCount}건이라, 검색 결과가 너무 적지 않도록 상위 전체
            결과를 함께 보여드리고 있습니다.
          </div>
        )}

        {showNoResultsMessage && (
          <div
            style={{
              ...surfaceStyle,
              padding: "24px",
              textAlign: "center",
              color: "#657b8c",
            }}
          >
              {NO_EVIDENCE_MESSAGE}
          </div>
        )}

          {!showNoResultsMessage && (
            <div style={{ display: "grid", gap: "16px" }}>
              {visibleResults.map((item, idx) => {
                const itemKey = getItemKey(item, idx);
                const previewText = buildResultPreview(item);

                return (
                  <article
                    key={itemKey}
                    style={{
                      ...surfaceStyle,
                      padding: "16px 18px",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        flexWrap: "wrap",
                        gap: "10px",
                        justifyContent: "space-between",
                        alignItems: "flex-start",
                      }}
                    >
                      <div style={{ flex: "1 1 420px", minWidth: 0 }}>
                        <div
                          style={{
                            display: "flex",
                            flexWrap: "wrap",
                            gap: "8px",
                            alignItems: "center",
                            marginBottom: "8px",
                          }}
                        >
                          {item.resource_type && (
                            <span
                              style={{
                                ...badgeStyle,
                                backgroundColor: "#dfeef8",
                                color: "#214e72",
                              }}
                            >
                              {formatResourceTypeLabel(item.resource_type)}
                            </span>
                          )}
                          <span style={{ ...metricStyle, fontWeight: 700 }}>
                            Result {idx + 1}
                          </span>
                        </div>

                        <h3 style={{ ...cardTitleStyle, fontSize: "1.18rem" }}>
                          {item.title}
                        </h3>
                      </div>

                      <div
                        style={{
                          display: "flex",
                          flexDirection: "column",
                          gap: "10px",
                          alignItems: "flex-end",
                        }}
                      >
                        {formatRelevance(item.score) && (
                          <span
                            style={{
                              ...badgeStyle,
                              backgroundColor: "#e7f4ea",
                              color: "#185e3b",
                            }}
                          >
                            {formatRelevance(item.score)}
                          </span>
                        )}
                        {item.source_url && (
                          <a
                            href={item.source_url}
                            target="_blank"
                            rel="noreferrer"
                            style={linkButtonStyle}
                          >
                            PubMed 보기
                          </a>
                        )}
                      </div>
                    </div>

                    {formatScore(item.score) && (
                      <div
                        style={{
                          marginTop: "10px",
                          color: "#587083",
                          fontSize: "0.82rem",
                          fontWeight: 600,
                        }}
                      >
                        score {formatScore(item.score)}
                      </div>
                    )}

                    {item.source_url && (
                      <div
                        style={{
                          marginTop: "8px",
                          color: "#486578",
                          fontSize: "0.8rem",
                          wordBreak: "break-all",
                        }}
                      >
                        {item.source_url}
                      </div>
                    )}

                    {previewText && (
                      <div
                        style={{
                          marginTop: "12px",
                          padding: "12px 14px",
                          borderRadius: "14px",
                          backgroundColor: "#f5fafc",
                          border: "1px solid #dce8ef",
                        }}
                      >
                        <p
                          style={{
                            margin: "0 0 6px",
                            fontWeight: 700,
                            color: "#1a405b",
                            fontSize: "0.86rem",
                          }}
                        >
                          핵심 요약
                        </p>
                        <div
                          style={{
                            margin: 0,
                            color: "#304d63",
                            lineHeight: 1.65,
                            fontSize: "0.92rem",
                            display: "-webkit-box",
                            WebkitBoxOrient: "vertical",
                            WebkitLineClamp: 2,
                            overflow: "hidden",
                          }}
                        >
                          {renderHighlightedText(previewText)}
                        </div>
                      </div>
                    )}
                  </article>
                );
              })}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

export default App;
