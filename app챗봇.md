# app.py — 목적과 핵심 구성

## 목적

PDF/크롤링 JSON을 기반으로 한 RAG 챗봇: 사용자의 질문을 받아 벡터스토어(FAISS)에서 관련 문맥을 검색하고, 마크다운 규칙에 맞춘 답변을 생성합니다. 관리자는 로그/피드백을 확인할 수 있습니다.

## 데이터 & 임베딩

**입력 데이터**: `rag_input_sample1.json`(사전 정리된 게시글·첨부 텍스트) → 배치 단위로 Document 생성 → `RecursiveCharacterTextSplitter`(1000/120)로 분할 → `OpenAIEmbeddings` 임베딩 → FAISS에 저장/로드. 최초 없으면 생성, 있으면 로드.

## 검색·리트리버

**retriever**: `vectorstore.as_retriever(search_kwargs={"k": 15})`

**질의 강화 → 컨텍스트 정제**:

- `gpt-3.5`로 질문에서 핵심 키워드 3~5개 추출
- 질문 + 키워드로 재검색
- `filter_relevant_context`: `gpt-3.5`로 각 문서와 질문의 실제 관련성 판정("관련있음"만 채택) → `assign_date_priority`로 날짜 기반 정렬(첨부파일명/제목의 8자리 날짜 추출) → 최대 10개 사용.

## 프롬프트 & 생성

**PromptTemplate**: "최신 정보 우선, 마크다운 규칙(굵게/체크/경고/연락처/번호) 엄수, 어르신 친화 문장, 추측 금지"를 강제.

**LLM**: `ChatOpenAI(model_name="gpt-4o", temperature=0, max_completion_tokens≈2000)`로 안정적, 포맷 고정형 답변.

## 가드레일(Guardrails)

**질문 유효성**: 길이/의미 없음/금지어 필터 + `gpt-3.5`로 복지용구 관련성 판정(YES/NO). 불통과 시 예시 질문 제시.

**분류**: 간단 키워드 매칭으로 카테고리 라벨(신청방법/품목/등급신청조건/본인부담률/자격확인/기타).

**검증 훅(옵션)**: 답변의 명백한 오류 감지 시 재답변 시도 로직 포함.

## 웹 엔드포인트 & 운영

- `/` 사용자 채팅 UI, `/ask` 질문 처리(유효성 검사 → 체인 실행).
- **쿨다운**: 사용자별 5초.
- **타임아웃**: 30초 초과 시 폴백 메시지.
- **로그**: `chat_log.csv`(timestamp, question, answer, status, category).
- `/admin/login|logout|logs`, `/admin/api/logs`, `/admin/api/feedback`: 세션 기반 간이 인증 후 최근 질의/피드백 열람.
- **feedback 엔드포인트**: 좋아요/싫어요 기록(`feedback_log.csv`).

---

# app1.py — app.py 대비 추가/변경 사항

아키텍처는 동일하지만 검색 품질·성능·신뢰성을 높이기 위한 개선이 꽤 들어갔습니다.

## 1) 전역 싱글톤화로 메모리/속도 최적화

- `vectorstore`, `retriever`, `chain`을 전역 싱글톤으로 관리.
- `init_vectorstore()`에서 이미 메모리에 있으면 재사용, 디스크에도 있으면 1회 로드 후 재사용 → 중복 로드 방지, 응답 속도 개선.

## 2) 리트리버 전략 고도화

```python
retriever = vectorstore.as_retriever(
    search_type="mmr", 
    search_kwargs={"k":25, "fetch_k":80, "lambda_mult":0.2}
)
```

→ MMR로 다양성 확보(유사 문서 중복 감소), 검색 폭 확대(k↑, fetch_k↑).

BM25/Ensemble 관련 모듈을 선행 임포트 및 전역 변수 정의(차후 하이브리드 검색 확장 여지). 현재 파일 내에서는 MMR-FAISS를 사용.

## 3) 날짜 우선순위 로직 대폭 강화

`assign_date_priority`가 다양한 날짜 포맷을 파싱:

- `YYYY-MM-DD` / `YYYY.MM.DD` / `YYYY/MM/DD` / `YYYYMMDD`
- `YYYY년 M월 D일`
- 두 자리 연도 표기(`'25.7.1`, `25-07-01`, `25년 7월 1일` 등)까지 지원

문서 메타데이터(`doc_date`), 본문, "첨부파일: …" 라인에서 후보 날짜를 모두 수집 후 최신을 점수화.
→ 최신 지침/공고가 더 앞에 오도록 정렬 품질 개선.

## 4) 문서 메타데이터 확장

`init_vectorstore()`에서 JSON의 날짜 필드를 탐지(`date`/`updated_at`/`publishedAt`/`created_at` 등) → **정규화된 ISO 날짜(`doc_date`)**를 메타데이터에 저장하고 본문에도 기입.
→ 이후 정렬·필터링·출처 표시에 활용 가능.

## 5) 가드레일 우회(안전한 완화)

유효성 검사 불통과여도, `retriever`에서 실제 관련 문서가 히트되면 차단하지 않고 RAG로 진행(운영 중 과차단 완화, 실제 유효 질문 살리기).

히트가 없으면 기존처럼 예시와 함께 차단 응답.

## 6) 타임아웃 여유 증가

`/ask` 처리의 생성 타임아웃을 30초 → 60초로 상향(대형 컨텍스트/혼잡 시 안정성↑).

쿨다운(5초)은 동일.

## 7) 기타

전체 구조(엔드포인트/로그/관리자 UI/가드레일 기본 로직)는 유지하되, 검색·정렬·리소스 관리의 실전성이 강화된 버전.

추후를 위해 `BM25Retriever`, `EnsembleRetriever` 임포트/변수 틀을 잡아둠(실 사용 전환은 간단).

---

# app2.py — "하이브리드 검색 + LLM 없는 빠른 컨텍스트 정제" (app1 대비 추가/변경)

**핵심**: FAISS(의미) + BM25(키워드) 앙상블로 검색 품질을 끌어올리고, LLM을 쓰지 않는 라이트 필터/재정렬로 속도와 안정성을 확보했습니다.

## 하이브리드 리트리버 도입

`init_hybrid_retriever()`에서

- **FAISS**: `search_type="mmr"`, `k=25`, `fetch_k=60`, `lambda_mult=0.3` (다양성 확보)
- **BM25**: `BM25Retriever.from_documents(...)`, `k=30` (정확 키워드 매칭)
- `EnsembleRetriever(weights=[0.45, 0.55])`로 가중 평균 앙상블 → 전역 `retriever` 교체.

→ "키워드가 분명한 질문"과 "의미 유사성이 중요한 질문" 모두 견고하게 커버.

## LLM 없는 컨텍스트 필터 & 재정렬

**`filter_relevant_context(question, retrieved_docs)`**

질문에 `%`/금액/일수 요구가 있으면, 해당 패턴이 문서에 실제로 존재하는 청크만 빠르게 1차 필터.

`generic_rerank()`로 최신 날짜·`%`·금액·일수·대여/구입 언급·예비급여 배제까지 가중치 점수화 → 상위 10개만 전달.
→ LLM 호출 없이 가벼운 정제로 품질/속도 동시 확보.

## 도메인/증거 가드

- **`domain_guard()`**: 질문에 복지 키워드가 없을 경우, 문서 상위 일부라도 복지 키워드가 있어야 통과.
- **`evidence_guard()`**: `%`/금액/일수 등을 묻는 질문에서 실제 증거 패턴이 top 문서 번들에 존재하는지 검증.

→ "문서에 근거가 없는 답변"을 막는 라이트 가드레일.

## 날짜 우선순위 스코어러

`assign_date_priority()`가 다양한 날짜 포맷(`YYYYMMDD`, `YYYY.MM.DD`, `'25-7-1`, 한글 표기 등)을 인식해 최신 문서 가점.
→ 최신 고시/공고가 위로 오도록 정렬 신뢰성↑.

## 보조 유틸

- **`_all_docs_from_faiss()`**: BM25 초기화용 전체 문서 로드.
- **`_needs()`**/`_doc_feats()`**: 질문/문서 특징(퍼센트/금액/일수/대여·구입 등) 추출.

→ 상기 필터·재정렬 로직의 가벼운 특징 엔진.

---

# app3.py — "섹션 인지(ontology) + 청크 번들링 + 리트리버 동적 재빌드" (app2 대비 추가/변경)

**핵심**: 문서 섹션 개념을 인덱스에 태깅하고, 관련 섹션의 이웃 청크를 함께 묶어 문맥 손실을 줄입니다. 또한 BM25/하이브리드 리트리버를 재빌드하는 관리 루틴을 추가해 대규모 데이터 갱신에도 대응합니다.

## 경량 섹션 온톨로지 도입

**`SECTION_PATTERNS` 정의**:

- `ITEM_LIST`(급여 대상 품목/대여·구입 품목)
- `COPAY`(본인부담률/공단부담금)
- `PROCEDURE`(신청/이용/진행 절차·제출/필요 서류)
- `ELIGIBILITY`(대상/요건/등급 기준)
- `LIMITS`(연/월 한도액 등)

`infer_section_ids(text)`로 제목·본문·첨부파일명에서 섹션 힌트 추출 → 문서 메타데이터에 `section_ids` 저장.
→ 질문 의도(예: "본인부담률")와 같은 섹션의 청크가 더 잘 노출됩니다.

## `group_key` + 청크 번들링

인덱싱 시 `group_key = f"{source_file}:{','.join(sorted(section_ids))}"`를 부여.

`bundle_siblings(top_docs, all_docs, max_extra=5)`로 상위 문서와 같은 `group_key`(=같은 파일의 같은 섹션군) 청크를 이웃으로 추가.
→ 한 섹션을 여러 청크로 쪼갤 때 생길 수 있는 문맥 단절을 최소화.

## 메타데이터 확장 & 재정렬 연동

문서 메타에 `section_ids`, `group_key`를 함께 저장하고, `_doc_feats()`에서 이를 노출.

(선택적) `source_file == "noin3_data.json"`에 가점(가이드성 자료 우대) 유지.
→ 섹션/출처 기반 재정렬이 가능해져, "질문 의도 맞춤" 정확도 향상.

## 리트리버 재빌드 유틸

**`rebuild_bm25_and_hybrid()`**: FAISS의 전체 문서를 다시 읽어 BM25를 재생성하고, FAISS MMR와 함께 `EnsembleRetriever`를 재구성 → 전역 `retriever` 갱신.
→ 데이터가 크게 바뀐 뒤에도 별도 서버 재시작 없이 검색 품질을 즉시 유지.

## 기타

app2의 도메인/증거 가드, 날짜 스코어, 라이트 필터/재정렬은 그대로 계승.

인덱서(`init_vectorstore`)에서 문서 본문에 날짜를 기록하고 메타에 `doc_date` 저장하는 흐름 유지.