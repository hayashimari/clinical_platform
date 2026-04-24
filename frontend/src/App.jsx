import { useState } from "react";

const pageStyle = {
  minHeight: "100vh",
  background:
    "linear-gradient(180deg, #f3f8fb 0%, #eef4f8 22%, #f8fbfd 100%)",
  color: "#153047",
  fontFamily:
    '"Segoe UI", "Noto Sans KR", "Apple SD Gothic Neo", sans-serif',
};

const containerStyle = {
  width: "min(1120px, calc(100% - 32px))",
  margin: "0 auto",
  padding: "40px 0 72px",
};

const surfaceStyle = {
  backgroundColor: "#ffffff",
  border: "1px solid #dbe7ee",
  borderRadius: "20px",
  boxShadow: "0 18px 40px rgba(16, 61, 92, 0.08)",
};

const sectionTitleStyle = {
  margin: 0,
  fontSize: "1.15rem",
  fontWeight: 700,
  color: "#12324a",
};

const cardTitleStyle = {
  margin: 0,
  fontSize: "1rem",
  fontWeight: 700,
  color: "#163852",
  lineHeight: 1.45,
};

const metricStyle = {
  fontSize: "0.78rem",
  color: "#5f7485",
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
  padding: "10px 14px",
  borderRadius: "10px",
  backgroundColor: "#e9f5fa",
  color: "#0b6988",
  fontSize: "0.88rem",
  fontWeight: 700,
  textDecoration: "none",
};

const badgeStyle = {
  display: "inline-flex",
  alignItems: "center",
  padding: "6px 10px",
  borderRadius: "999px",
  backgroundColor: "#eef6fa",
  color: "#486476",
  fontSize: "0.78rem",
  fontWeight: 600,
};

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
      const res = await fetch("http://localhost:8002/api/v1/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: trimmedQuery }),
      });

      if (!res.ok) {
        throw new Error("검색 요청 실패");
      }

      const data = await res.json();
      setSearchedQuery(trimmedQuery);
      setExpandedResults({});
      setAnswer(data.answer || "");
      setCitations(data.citations || []);
      setResults(data.results || []);
    } catch (err) {
      setError(err.message);
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

  const matchesResourceType = (item) => {
    if (resourceType === "all") {
      return true;
    }

    return String(item?.resource_type ?? "").toLowerCase() === resourceType;
  };

  const getItemKey = (item, idx) =>
    item?.resource_id ?? item?.source_url ?? `${item?.title ?? "item"}-${idx}`;

  const toggleExpanded = (itemKey) => {
    setExpandedResults((prev) => ({
      ...prev,
      [itemKey]: !prev[itemKey],
    }));
  };

  const getClampStyle = (isExpanded) => ({
    margin: 0,
    color: "#395568",
    lineHeight: 1.75,
    fontSize: "0.94rem",
    ...(isExpanded
      ? {}
      : {
          display: "-webkit-box",
          WebkitBoxOrient: "vertical",
          WebkitLineClamp: 3,
          overflow: "hidden",
        }),
  });

  const shouldShowExpand = (text) =>
    typeof text === "string" && text.trim().length > 180;

  const formatScore = (value) =>
    typeof value === "number" ? value.toFixed(3) : null;

  const filteredResults = results.filter(matchesResourceType);
  const filteredCitations = citations.filter(matchesResourceType);
  const showNoResultsMessage =
    hasSearched && !loading && !error && filteredResults.length === 0;

  return (
    <div style={pageStyle}>
      <div style={containerStyle}>
        <section
          style={{
            ...surfaceStyle,
            padding: "28px",
            marginBottom: "28px",
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
                <option value="guideline" style={{ color: "#153047" }}>
                  guideline
                </option>
                <option value="review" style={{ color: "#153047" }}>
                  review
                </option>
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
              padding: "26px",
              marginBottom: "24px",
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
                  "linear-gradient(180deg, #f8fcfe 0%, #eef6fa 100%)",
                border: "1px solid #d6e6ee",
              }}
            >
              <p
                style={{
                  margin: 0,
                  lineHeight: 1.9,
                  color: "#28485e",
                  fontSize: "1rem",
                  whiteSpace: "pre-wrap",
                }}
              >
                {answer}
              </p>
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
                      padding: "18px",
                      display: "flex",
                      flexDirection: "column",
                      gap: "12px",
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

          {showNoResultsMessage && (
            <div
              style={{
                ...surfaceStyle,
                padding: "28px",
                textAlign: "center",
                color: "#657b8c",
              }}
            >
              검색 결과가 없습니다
            </div>
          )}

          {!showNoResultsMessage && (
            <div style={{ display: "grid", gap: "16px" }}>
              {filteredResults.map((item, idx) => {
                const itemKey = getItemKey(item, idx);
                const isExpanded = Boolean(expandedResults[itemKey]);
                const showExpandButton =
                  shouldShowExpand(item.abstract) || shouldShowExpand(item.content);

                return (
                  <article
                    key={itemKey}
                    style={{
                      ...surfaceStyle,
                      padding: "22px",
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
                            marginBottom: "10px",
                          }}
                        >
                          <span style={badgeStyle}>Result {idx + 1}</span>
                          {item.resource_type && (
                            <span
                              style={{
                                ...badgeStyle,
                                backgroundColor: "#edf5ff",
                                color: "#305b85",
                              }}
                            >
                              {item.resource_type}
                            </span>
                          )}
                        </div>

                        <h3 style={{ ...cardTitleStyle, fontSize: "1.08rem" }}>
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

                    <div
                      style={{
                        display: "flex",
                        flexWrap: "wrap",
                        gap: "10px 14px",
                        marginTop: "14px",
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

                    {item.abstract && (
                      <div style={{ marginTop: "16px" }}>
                        <p
                          style={{
                            margin: "0 0 8px",
                            fontWeight: 700,
                            color: "#1e425d",
                            fontSize: "0.9rem",
                          }}
                        >
                          Abstract
                        </p>
                        <div style={getClampStyle(isExpanded)}>
                          {renderHighlightedText(item.abstract)}
                        </div>
                      </div>
                    )}

                    {item.content && (
                      <div style={{ marginTop: "14px" }}>
                        <p
                          style={{
                            margin: "0 0 8px",
                            fontWeight: 700,
                            color: "#1e425d",
                            fontSize: "0.9rem",
                          }}
                        >
                          Matched Content
                        </p>
                        <div style={getClampStyle(isExpanded)}>
                          {renderHighlightedText(item.content)}
                        </div>
                      </div>
                    )}

                    {showExpandButton && (
                      <button
                        type="button"
                        onClick={() => toggleExpanded(itemKey)}
                        style={{
                          marginTop: "14px",
                          padding: 0,
                          border: "none",
                          background: "none",
                          color: "#0b6988",
                          fontWeight: 700,
                          cursor: "pointer",
                        }}
                      >
                        {isExpanded ? "접기" : "더보기"}
                      </button>
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
