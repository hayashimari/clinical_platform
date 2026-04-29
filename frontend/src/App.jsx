import { useState } from "react";

const pageStyle = {
  minHeight: "100vh",
  background:
    "linear-gradient(180deg, #eef4f8 0%, #f6f9fc 48%, #eef4f9 100%)",
  color: "#12324a",
  fontFamily:
    '"Segoe UI", "Noto Sans KR", "Apple SD Gothic Neo", sans-serif',
};

const containerStyle = {
  width: "100%",
  maxWidth: "900px",
  margin: "0 auto",
  padding: "24px 16px 56px",
  boxSizing: "border-box",
};

const surfaceStyle = {
  backgroundColor: "#ffffff",
  border: "1px solid #c4d6e2",
  borderRadius: "16px",
  boxShadow: "0 14px 30px rgba(14, 51, 78, 0.08)",
};

const sectionTitleStyle = {
  margin: 0,
  fontSize: "1.08rem",
  fontWeight: 700,
  color: "#12324a",
};

const cardTitleStyle = {
  margin: 0,
  fontSize: "1rem",
  fontWeight: 700,
  color: "#102f46",
  lineHeight: 1.45,
};

const metricStyle = {
  fontSize: "0.8rem",
  color: "#536b7d",
};

const primaryButtonStyle = {
  border: "1px solid #d3ebf5",
  borderRadius: "12px",
  backgroundColor: "#eff9fd",
  color: "#0f4d67",
  padding: "12px 16px",
  fontSize: "0.92rem",
  fontWeight: 700,
  cursor: "pointer",
  whiteSpace: "nowrap",
  boxSizing: "border-box",
};

const linkButtonStyle = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  padding: "9px 12px",
  borderRadius: "10px",
  border: "1px solid #0a5069",
  background: "linear-gradient(180deg, #0f6d8d 0%, #0d5771 100%)",
  color: "#f8fdff",
  fontSize: "0.82rem",
  fontWeight: 700,
  textDecoration: "none",
  boxShadow: "0 10px 18px rgba(12, 88, 114, 0.18)",
  whiteSpace: "nowrap",
};

const badgeStyle = {
  display: "inline-flex",
  alignItems: "center",
  gap: "6px",
  padding: "6px 10px",
  borderRadius: "999px",
  backgroundColor: "#e8f2f8",
  color: "#24475f",
  fontSize: "0.76rem",
  fontWeight: 700,
};

const subtleBadgeStyle = {
  ...badgeStyle,
  backgroundColor: "#f1f7fb",
  color: "#466276",
};

const textButtonStyle = {
  border: "none",
  padding: 0,
  background: "transparent",
  color: "#0c6584",
  fontSize: "0.86rem",
  fontWeight: 700,
  cursor: "pointer",
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
  const [expandedResults, setExpandedResults] = useState({});

  const handleSearch = async () => {
    const trimmedQuery = query.trim();

    if (!trimmedQuery) return;

    setHasSearched(true);
    setLoading(true);
    setError("");

    try {
      const res = await fetch(
        "https://clinical-platform-api-b2wt.onrender.com/api/v1/search",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query: trimmedQuery }),
        }
      );

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
      setError(
        !nextAnswer.trim() && nextResults.length > 0 ? NO_EVIDENCE_MESSAGE : ""
      );
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

    return Array.from(new Set([...SUMMARY_EMPHASIS_TERMS, ...queryTerms])).sort(
      (left, right) => right.length - left.length
    );
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
        <strong key={idx} style={{ color: "#123d5d", fontWeight: 800 }}>
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

    if (resourceType === "all" || matchedItems.length >= minimumVisibleCount) {
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

  const isExpandablePreview = (text) => {
    const safeText = typeof text === "string" ? text : String(text ?? "");
    return safeText.trim().length > 220 || safeText.includes("\n");
  };

  const toggleResultExpansion = (itemKey) => {
    setExpandedResults((prev) => ({
      ...prev,
      [itemKey]: !prev[itemKey],
    }));
  };

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
            padding: "20px",
            marginBottom: "18px",
            background:
              "linear-gradient(180deg, #143f60 0%, #105774 58%, #0f6b89 100%)",
            borderColor: "#2d6f88",
            boxShadow: "0 22px 42px rgba(13, 55, 80, 0.2)",
            color: "#f4fbff",
          }}
        >
          <div style={{ display: "grid", gap: "16px" }}>
            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                gap: "12px",
                justifyContent: "space-between",
                alignItems: "flex-start",
              }}
            >
              <div style={{ flex: "1 1 420px", minWidth: 0 }}>
                <p
                  style={{
                    margin: "0 0 8px",
                    fontSize: "0.76rem",
                    fontWeight: 700,
                    letterSpacing: "0.1em",
                    textTransform: "uppercase",
                    color: "#bddbea",
                  }}
                >
                  Evidence Retrieval
                </p>
                <h1
                  style={{
                    margin: "0 0 8px",
                    fontSize: "clamp(1.35rem, 3vw, 1.72rem)",
                    lineHeight: 1.2,
                  }}
                >
                  Clinical Evidence Search
                </h1>
                <p
                  style={{
                    margin: 0,
                    color: "#dcecf4",
                    lineHeight: 1.55,
                    fontSize: "0.94rem",
                    maxWidth: "680px",
                  }}
                >
                  임상 질문을 입력하면 관련 근거를 검색하고, AI 요약과 원문
                  링크를 한 화면에서 빠르게 확인할 수 있습니다.
                </p>
              </div>

              {searchedQuery && (
                <span
                  style={{
                    ...badgeStyle,
                    backgroundColor: "rgba(244, 251, 255, 0.16)",
                    color: "#eef9ff",
                  }}
                >
                  최근 검색어: {searchedQuery}
                </span>
              )}
            </div>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSearch();
              }}
              style={{
                display: "flex",
                flexWrap: "wrap",
                gap: "10px",
                alignItems: "stretch",
              }}
            >
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="예: postoperative nausea vomiting prevention"
                style={{
                  flex: "1 1 420px",
                  minWidth: 0,
                  padding: "13px 15px",
                  borderRadius: "12px",
                  border: "1px solid rgba(255, 255, 255, 0.22)",
                  backgroundColor: "rgba(255, 255, 255, 0.12)",
                  color: "#ffffff",
                  fontSize: "0.96rem",
                  boxSizing: "border-box",
                }}
              />

              <button
                type="submit"
                disabled={loading}
                style={{
                  ...primaryButtonStyle,
                  flex: "0 0 auto",
                  minWidth: "116px",
                  backgroundColor: loading ? "#a7c3cf" : "#eff9fd",
                  color: loading ? "#355264" : "#0f4d67",
                }}
              >
                {loading ? "검색 중..." : "검색"}
              </button>
            </form>

            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                gap: "10px 14px",
                alignItems: "center",
              }}
            >
              <label
                style={{
                  display: "flex",
                  alignItems: "center",
                  flexWrap: "wrap",
                  gap: "8px",
                  color: "#dcecf4",
                  fontSize: "0.89rem",
                }}
              >
                <span>Resource Type</span>
                <select
                  value={resourceType}
                  onChange={(e) => setResourceType(e.target.value)}
                  style={{
                    minWidth: "150px",
                    padding: "8px 10px",
                    borderRadius: "10px",
                    border: "1px solid rgba(255, 255, 255, 0.2)",
                    backgroundColor: "rgba(255, 255, 255, 0.12)",
                    color: "#ffffff",
                    boxSizing: "border-box",
                  }}
                >
                  <option value="all" style={{ color: "#14344d" }}>
                    All
                  </option>
                  {resourceTypeOptions.map((option) => (
                    <option
                      key={option}
                      value={option}
                      style={{ color: "#14344d" }}
                    >
                      {formatResourceTypeLabel(option)}
                    </option>
                  ))}
                </select>
              </label>

              <span style={{ ...metricStyle, color: "#dcecf4" }}>
                필터를 적용해도 결과가 너무 적으면 상위 근거를 함께 보여줍니다.
              </span>
            </div>
          </div>
        </section>

        {error && (
          <div
            style={{
              ...surfaceStyle,
              padding: "15px 17px",
              marginBottom: "18px",
              borderColor: "#efc4c4",
              backgroundColor: "#fff6f6",
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
              marginBottom: "22px",
              borderColor: "#adc9d8",
              boxShadow: "0 18px 38px rgba(16, 72, 100, 0.12)",
            }}
          >
            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                gap: "12px",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: "16px",
              }}
            >
              <div>
                <p
                  style={{
                    margin: "0 0 6px",
                    fontSize: "0.76rem",
                    fontWeight: 700,
                    letterSpacing: "0.08em",
                    textTransform: "uppercase",
                    color: "#5f7d92",
                  }}
                >
                  AI Summary
                </p>
                <h2 style={{ ...sectionTitleStyle, fontSize: "1.36rem" }}>
                  핵심 임상 요약
                </h2>
              </div>

              <span
                style={{
                  ...badgeStyle,
                  backgroundColor: "#edf7fc",
                  color: "#1b5876",
                }}
              >
                {filteredCitations.length > 0
                  ? `근거 ${filteredCitations.length}건 연결`
                  : "AI 요약"}
              </span>
            </div>

            <div
              style={{
                padding: "18px",
                borderRadius: "16px",
                background:
                  "linear-gradient(180deg, #f8fcff 0%, #eef6fb 100%)",
                border: "1px solid #cfdee8",
              }}
            >
              <div style={{ display: "grid", gap: "12px" }}>
                {buildSummaryBullets(answer).map((bullet, idx) => (
                  <div
                    key={`${bullet}-${idx}`}
                    style={{
                      display: "grid",
                      gridTemplateColumns: "12px 1fr",
                      gap: "12px",
                      alignItems: "flex-start",
                      padding: "12px 14px",
                      borderRadius: "14px",
                      backgroundColor: "#ffffff",
                      border: "1px solid #d7e6ef",
                    }}
                  >
                    <span
                      style={{
                        width: "8px",
                        height: "8px",
                        marginTop: "10px",
                        borderRadius: "999px",
                        backgroundColor: "#0d6786",
                        boxShadow: "0 0 0 4px rgba(13, 103, 134, 0.12)",
                      }}
                    />
                    <div
                      style={{
                        color: "#1a3f5a",
                        lineHeight: 1.82,
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
                  gap: "8px 12px",
                  justifyContent: "space-between",
                  alignItems: "center",
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
                  citation chip을 눌러 원문 링크를 새 탭에서 열 수 있습니다.
                </span>
              </div>

              {filteredCitations.length === 0 ? (
                <div
                  style={{
                    padding: "13px 15px",
                    borderRadius: "14px",
                    border: "1px solid #d9e5ec",
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
                    display: "flex",
                    flexWrap: "wrap",
                    gap: "10px",
                  }}
                >
                  {filteredCitations.map((item, idx) => {
                    const itemKey = getItemKey(item, idx);
                    const isClickable = Boolean(item.source_url);
                    const relevanceLabel =
                      formatRelevance(item.score) ?? "관련도 정보 없음";
                    const chipStyle = {
                      flex: "1 1 220px",
                      minWidth: 0,
                      padding: "12px 14px",
                      borderRadius: "14px",
                      border: "1px solid #d2e1ea",
                      backgroundColor: isClickable ? "#f8fbfd" : "#f2f5f7",
                      color: "#173b54",
                      textDecoration: "none",
                      display: "flex",
                      flexDirection: "column",
                      gap: "8px",
                      cursor: isClickable ? "pointer" : "default",
                      opacity: isClickable ? 1 : 0.72,
                    };

                    const chipContent = (
                      <>
                        <div
                          style={{
                            display: "flex",
                            flexWrap: "wrap",
                            gap: "6px",
                            alignItems: "center",
                          }}
                        >
                          <span style={subtleBadgeStyle}>Source {idx + 1}</span>
                          {item.resource_type && (
                            <span
                              style={{
                                ...subtleBadgeStyle,
                                backgroundColor: "#edf6ef",
                                color: "#2f6b4c",
                              }}
                            >
                              {formatResourceTypeLabel(item.resource_type)}
                            </span>
                          )}
                          <span
                            style={{
                              ...subtleBadgeStyle,
                              backgroundColor: "#edf5fb",
                              color: "#1b5e7d",
                            }}
                          >
                            {relevanceLabel}
                          </span>
                        </div>

                        <div
                          style={{
                            fontSize: "0.88rem",
                            fontWeight: 600,
                            lineHeight: 1.45,
                            color: "#24445d",
                            display: "-webkit-box",
                            WebkitBoxOrient: "vertical",
                            WebkitLineClamp: 2,
                            overflow: "hidden",
                          }}
                        >
                          {item.title || (isClickable ? "원문 링크 열기" : "링크 없음")}
                        </div>
                      </>
                    );

                    if (!isClickable) {
                      return (
                        <div key={itemKey} style={chipStyle} aria-disabled="true">
                          {chipContent}
                        </div>
                      );
                    }

                    return (
                      <a
                        key={itemKey}
                        href={item.source_url}
                        target="_blank"
                        rel="noreferrer"
                        style={chipStyle}
                      >
                        {chipContent}
                      </a>
                    );
                  })}
                </div>
              )}
            </div>
          </section>
        )}

        {answer && (
          <section style={{ marginBottom: "26px" }}>
            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                alignItems: "center",
                justifyContent: "space-between",
                marginBottom: "14px",
                gap: "10px",
              }}
            >
              <h2 style={sectionTitleStyle}>근거 논문</h2>
              <span style={metricStyle}>
                AI 요약에 연결된 주요 citation을 카드 형태로 확인할 수 있습니다.
              </span>
            </div>

            {filteredCitations.length === 0 ? (
              <div
                style={{
                  ...surfaceStyle,
                  padding: "24px",
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
                  gap: "14px",
                }}
              >
                {filteredCitations.map((item, idx) => {
                  const previewText = buildResultPreview(item);

                  return (
                    <article
                      key={getItemKey(item, idx)}
                      style={{
                        ...surfaceStyle,
                        padding: "16px",
                        display: "grid",
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
                        <span style={subtleBadgeStyle}>Source {idx + 1}</span>
                        {item.resource_type && (
                          <span
                            style={{
                              ...subtleBadgeStyle,
                              backgroundColor: "#edf6ef",
                              color: "#2f6b4c",
                            }}
                          >
                            {formatResourceTypeLabel(item.resource_type)}
                          </span>
                        )}
                        {formatRelevance(item.score) && (
                          <span
                            style={{
                              ...subtleBadgeStyle,
                              backgroundColor: "#edf5fb",
                              color: "#1b5e7d",
                            }}
                          >
                            {formatRelevance(item.score)}
                          </span>
                        )}
                      </div>

                      <h3 style={cardTitleStyle}>{item.title}</h3>

                      {previewText && (
                        <div
                          style={{
                            color: "#415f74",
                            lineHeight: 1.68,
                            fontSize: "0.91rem",
                            display: "-webkit-box",
                            WebkitBoxOrient: "vertical",
                            WebkitLineClamp: 3,
                            overflow: "hidden",
                          }}
                        >
                          {renderHighlightedText(previewText)}
                        </div>
                      )}

                      <div
                        style={{
                          display: "flex",
                          flexWrap: "wrap",
                          gap: "8px 12px",
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
                          style={{ ...linkButtonStyle, marginTop: "2px" }}
                        >
                          PubMed 보기
                        </a>
                      )}
                    </article>
                  );
                })}
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
                  "linear-gradient(180deg, #f7fbfe 0%, #eef6fa 100%)",
                borderColor: "#d3e3ec",
                color: "#31556d",
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
            <div style={{ display: "grid", gap: "14px" }}>
              {visibleResults.map((item, idx) => {
                const itemKey = getItemKey(item, idx);
                const previewText = buildResultPreview(item);
                const isExpanded = Boolean(expandedResults[itemKey]);
                const canTogglePreview = isExpandablePreview(previewText);

                return (
                  <article
                    key={itemKey}
                    style={{
                      ...surfaceStyle,
                      padding: "16px 18px",
                      display: "grid",
                      gap: "12px",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        flexWrap: "wrap",
                        gap: "12px",
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
                                backgroundColor: "#e9f3f9",
                                color: "#21506f",
                              }}
                            >
                              {formatResourceTypeLabel(item.resource_type)}
                            </span>
                          )}
                          {formatRelevance(item.score) && (
                            <span
                              style={{
                                ...badgeStyle,
                                backgroundColor: "#eef6f1",
                                color: "#225e3c",
                              }}
                            >
                              {formatRelevance(item.score)}
                            </span>
                          )}
                          <span style={subtleBadgeStyle}>Result {idx + 1}</span>
                        </div>

                        <h3 style={{ ...cardTitleStyle, fontSize: "1.06rem" }}>
                          {item.title}
                        </h3>
                      </div>

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

                    {previewText && (
                      <div
                        style={{
                          padding: "13px 14px",
                          borderRadius: "14px",
                          backgroundColor: "#f6fafc",
                          border: "1px solid #d9e6ee",
                        }}
                      >
                        <div
                          style={{
                            marginBottom: "6px",
                            fontWeight: 700,
                            color: "#1a405b",
                            fontSize: "0.82rem",
                            textTransform: "uppercase",
                            letterSpacing: "0.04em",
                          }}
                        >
                          Abstract / Content
                        </div>
                        <div
                          style={{
                            color: "#324f64",
                            lineHeight: 1.72,
                            fontSize: "0.92rem",
                            display: isExpanded ? "block" : "-webkit-box",
                            WebkitBoxOrient: "vertical",
                            WebkitLineClamp: isExpanded ? "unset" : 3,
                            overflow: "hidden",
                          }}
                        >
                          {renderHighlightedText(previewText)}
                        </div>
                        {canTogglePreview && (
                          <button
                            type="button"
                            onClick={() => toggleResultExpansion(itemKey)}
                            style={{ ...textButtonStyle, marginTop: "10px" }}
                          >
                            {isExpanded ? "접기" : "더보기"}
                          </button>
                        )}
                      </div>
                    )}

                    <div
                      style={{
                        display: "flex",
                        flexWrap: "wrap",
                        gap: "8px 14px",
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
