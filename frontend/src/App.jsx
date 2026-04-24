import { useState } from "react";

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

  const filteredResults = results.filter(matchesResourceType);
  const filteredCitations = citations.filter(matchesResourceType);
  const showNoSearchResultsMessage =
    hasSearched && !loading && !error && results.length === 0;
  const showNoFilteredResultsMessage =
    hasSearched &&
    !loading &&
    !error &&
    results.length > 0 &&
    filteredResults.length === 0;
  const showNoFilteredCitationsMessage =
    hasSearched &&
    !loading &&
    !error &&
    citations.length > 0 &&
    filteredCitations.length === 0;

  return (
    <div style={{ padding: "40px", fontFamily: "Arial" }}>
      <h1>Clinical Evidence Search</h1>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleSearch();
        }}
      >
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="검색어 입력"
          style={{ width: "420px", padding: "10px", marginRight: "10px" }}
        />

        <button type="submit" disabled={loading}>
          {loading ? "검색 중..." : "검색"}
        </button>
      </form>

      <div style={{ marginTop: "12px" }}>
        <label>
          Resource Type{" "}
          <select
            value={resourceType}
            onChange={(e) => setResourceType(e.target.value)}
            style={{ marginLeft: "8px", padding: "6px" }}
          >
            <option value="all">All</option>
            <option value="guideline">guideline</option>
            <option value="review">review</option>
          </select>
        </label>
      </div>

      {error && <p style={{ color: "red" }}>{error}</p>}

      {answer && (
        <div
          style={{
            marginTop: "30px",
            padding: "20px",
            border: "2px solid #222",
            borderRadius: "8px",
          }}
        >
          <h2>AI Answer</h2>
          <p>{answer}</p>

          <h3>Sources</h3>
          {showNoFilteredCitationsMessage && (
            <p style={{ color: "#666", marginTop: "20px" }}>
              선택한 필터에 해당하는 결과가 없습니다.
            </p>
          )}

          {filteredCitations.map((item, idx) => (
            <div key={idx} style={{ marginBottom: "12px" }}>
              <b>
                [{idx + 1}] {item.title}
              </b>
              <p>{renderHighlightedText(item.content)}</p>
              <p>Score: {item.score.toFixed(3)}</p>
              <a href={item.source_url} target="_blank">
                원문 보기
              </a>
            </div>
          ))}
        </div>
      )}

      <div style={{ marginTop: "30px" }}>
        <h2>Evidence Results</h2>

        {showNoSearchResultsMessage && (
          <p style={{ textAlign: "center", color: "#666", marginTop: "20px" }}>
            관련 근거를 찾을 수 없습니다. 검색어를 변경해보세요.
          </p>
        )}

        {showNoFilteredResultsMessage && (
          <p style={{ textAlign: "center", color: "#666", marginTop: "20px" }}>
            선택한 필터에 해당하는 결과가 없습니다.
          </p>
        )}

        {filteredResults.map((item, idx) => (
          <div
            key={idx}
            style={{
              border: "1px solid #ddd",
              padding: "15px",
              marginBottom: "15px",
              borderRadius: "8px",
            }}
          >
            <h3>{item.title}</h3>
            <p>
              <b>Type:</b> {item.resource_type}
            </p>
            <p>
              <b>Abstract:</b> {item.abstract}
            </p>
            <p>{renderHighlightedText(item.content)}</p>
            <p>
              <b>Score:</b> {item.score.toFixed(3)}
            </p>
            <a href={item.source_url} target="_blank">
              원문 보기
            </a>
          </div>
        ))}
      </div>
    </div>
  );
}

export default App;
