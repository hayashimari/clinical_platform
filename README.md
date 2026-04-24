# PubMed Clinical Evidence RAG MVP

PubMed 기반 clinical evidence RAG search MVP입니다.  
React 프론트엔드, FastAPI 백엔드, Postgres + pgvector 저장소를 사용하며, OpenAI embedding과 answer generation을 통해 PubMed 논문 abstract를 검색하고 요약 답변을 제공합니다.

## 프로젝트 개요

- Frontend: React + Vite
- Backend: FastAPI
- Database: Postgres + pgvector
- LLM: OpenAI embeddings + chat completion
- Data source: PubMed API

이 프로젝트는 PubMed 논문을 수집해 `resources` / `resource_segments` 테이블에 저장하고, 사용자의 clinical query에 대해 다음 흐름으로 검색합니다.

1. query embedding 생성
2. pgvector 기반 vector search
3. keyword match score를 포함한 hybrid ranking
4. overlap 기반 reranking
5. 상위 chunk를 구조화된 context로 구성
6. OpenAI를 이용한 evidence-grounded answer 생성

## 주요 기능

- PubMed import
  - PubMed API에서 논문 검색
  - `title`, `abstract` 수집
  - 동일 title 중복 방지
- Chunking
  - abstract를 문장 단위로 분리
  - 각 문장을 하나의 segment로 저장
- Embedding 저장
  - OpenAI embedding API를 사용해 chunk별 embedding 생성
  - `resource_segments.embedding`에 저장
- Vector search
  - pgvector distance 기반 후보 검색
- Hybrid ranking
  - `vector_score + keyword_score` 조합
  - title/content 직접 포함 여부를 반영
- Reranking
  - overlap score와 direct match bonus를 추가해 상위 chunk 재정렬
- Citations
  - title, source_url, content, score 정보를 함께 반환
- Frontend search UI
  - 검색 입력 및 엔터 검색
  - answer / citations / evidence results 표시
  - query highlight
  - resource type filter
  - 빈 결과 안내 메시지

## 실행 방법

### 1. Docker 실행

루트 디렉터리에서 Postgres와 Redis를 실행합니다.

```bash
docker compose up -d
```

현재 MVP에서 핵심적으로 사용하는 것은 Postgres입니다. Redis 컨테이너도 함께 올라오지만, 현재 검색 흐름의 핵심 경로에는 직접 사용되지 않습니다.

### 2. Backend 실행

권장: Python 가상환경을 사용합니다.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install fastapi "uvicorn[standard]" openai python-dotenv psycopg2-binary
uvicorn app.main:app --reload --port 8002
```

백엔드는 `http://localhost:8002` 에서 실행됩니다.

### 3. Frontend 실행

```bash
cd frontend
npm install
npm run dev
```

프론트엔드는 기본적으로 `http://localhost:5173` 에서 실행됩니다.

### 4. PubMed import 실행

루트 또는 `backend` 디렉터리 기준으로 실행할 수 있습니다.

루트에서 실행:

```bash
python backend/app/scripts/pubmed_import.py --query "asthma" --limit 20
```

`backend` 디렉터리에서 실행:

```bash
cd backend
python app/scripts/pubmed_import.py --query "asthma" --limit 20
```

예시:

```bash
python backend/app/scripts/pubmed_import.py --query "diabetes" --limit 20
```

### 5. Search API 테스트 (`curl`)

```bash
curl -X POST http://localhost:8002/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query":"asthma guideline"}'
```

예상 응답에는 아래 정보가 포함됩니다.

- `answer`
- `count`
- `citations`
- `results`
- `vector_score`
- `keyword_score`
- `overlap_score`
- `rerank_score`

## 환경변수

최소 필수 환경변수:

```bash
OPENAI_API_KEY=your_openai_api_key
```

이 값은 아래 기능에 사용됩니다.

- query embedding 생성
- PubMed chunk embedding 생성
- 최종 answer generation

프로젝트는 루트의 `.env` 파일을 읽도록 구성되어 있습니다.

## DB 테이블 설명

현재 검색/수집 흐름은 아래 두 테이블을 기준으로 동작합니다.

### `resources`

논문 또는 문서 단위 메타데이터를 저장합니다.

주요 컬럼:

- `id`: resource primary key
- `title`: 논문 제목
- `resource_type`: 문서 유형 (`guideline`, `review`, `journal_article` 등)
- `abstract`: 원문 abstract
- `source_url`: 원문 링크

### `resource_segments`

검색 단위 chunk를 저장합니다.

주요 컬럼:

- `id`: segment primary key
- `resource_id`: `resources.id` 참조
- `content`: 문장 단위 chunk 텍스트
- `embedding`: pgvector embedding

검색은 `resource_segments.embedding` 을 기준으로 vector search를 수행하고, 최종 응답에는 연결된 `resources` 메타데이터를 함께 반환합니다.

## 검색 파이프라인 요약

1. 사용자가 query를 입력합니다.
2. backend가 query embedding을 생성합니다.
3. pgvector distance 기준으로 후보 chunk를 가져옵니다.
4. keyword score를 더해 hybrid ranking을 계산합니다.
5. overlap score 기반 reranking으로 상위 chunk를 다시 정렬합니다.
6. threshold filtering과 dedup을 적용합니다.
7. 상위 chunk를 아래 구조의 context로 변환합니다.

```text
[Source 1: Title]
chunk content

[Source 2: Title]
chunk content
```

8. OpenAI가 structured context를 사용해 clinical evidence answer를 생성합니다.

## 현재 한계

- Local prototype
  - 로컬 개발과 MVP 검증 중심 구조입니다.
- Auth 없음
  - 사용자 인증/권한 관리가 없습니다.
- Production deployment 미완성
  - 운영 배포 파이프라인, 모니터링, 스케일링 구성이 없습니다.
- Medical validation 필요
  - 실제 의료 의사결정에 사용하기 전 임상적 검증과 전문가 리뷰가 필요합니다.

## 참고

- Backend API entrypoint: `backend/app/main.py`
- Search service: `backend/app/services/search_service.py`
- PubMed import script: `backend/app/scripts/pubmed_import.py`
- Frontend UI: `frontend/src/App.jsx`
