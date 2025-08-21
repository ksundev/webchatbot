# 무엇을 만들까 (입·출력)

## 입력

- **복지용구_자료실.csv** (제목/URL/본문/첨부 목록)(원하는 이름으로 변경 가능)
- **attachments/** 디렉터리(하위에 `pdf/`, `pdf/text/`, `pdf/image/`, `hwp/`, `xlsx/`, …)

## 출력

**rag_input_sample.json** (누적 저장; 실행 시 기존 파일을 읽어 증분 반영 + 백업 생성)(원하는 이름으로 변경 가능)

**파일별 상세 설명**:
- **rag_input_sample.json**: `req2.py`를 통해 가져온 공지사항 내용을 `good_all.py`를 통해 텍스트화한 파일
- **rag_input_sample1.json**: `req3.py`를 통해 가져온 법령자료실 내용을 `good_all.py`를 통해 텍스트화한 파일  
- **noin3_data.json**: `noin3.pdf`를 텍스트화한 파일

**JSON의 각 항목 구조**:

```json
{
  "title": "...",
  "url": "...",
  "content": "...",
  "attachments": [
    {"file_name": "YYYYMMDD원본.pdf", "text": "첨부 텍스트(페이지/ OCR 포함)"},
    ...
  ]
}
```

# 전체 파이프라인 (한 눈에)

## 1. 기존 JSON 불러오기 & 해시셋 구축

`rag_input_sample.json`을 로드 → 각 항목에 대해 `title + content + 첨부파일명`들을 합쳐 MD5 해시 생성 → 중복 판정에 사용.

## 2. CSV 로딩 & 행 순회

`복지용구_자료실.csv`를 읽고 각 게시물(row) 처리.

## 3. 첨부파일 문자열 파싱 & 파일 경로 찾기

`attachments` 컬럼을 `"; "`로 분할 → `"파일명 (URL)"` 포맷에서 파일명만 추출

**실제 경로 탐색**:
- 동일 이름 우선 → 날짜 프리픽스(`YYYYMMDD`) 제거한 이름으로 재탐색 →
- 그래도 못 찾으면 확장자 기준 간이 유사도 매칭으로 베스트 후보 선택.
- **HWP라면** 동일 이름의 PDF 버전을 `pdf/`, `pdf/text/`, `pdf/image/`에서 먼저 찾아 대체.

## 4. 텍스트 추출(중요!)

- **PDF**: `PyMuPDF`로 `get_text()` → 페이지당 텍스트가 20자 미만이면 OCR 시도
  - 페이지를 300dpi 이미지로 렌더 → `pytesseract`(한/영)로 인식 → 페이지별 구분 헤더(`=== 페이지 N ===`) 포함.
- **HWP**: `olefile`로 `PrvText` 또는 `BodyText/Section*` 스트림을 디코딩(UTF-16)해 텍스트 추출.
  - PDF 버전을 찾으면 PDF쪽 추출을 우선.
- **그 외 확장자**: "지원되지 않는 형식" 표시.

## 5. 첨부 텍스트 묶기 & 게시물 오브젝트 구성

`attachments` 배열에 `{file_name, text}`로 누적.

## 6. 중복 판정 & 증분 추가

`title + content + 첨부파일명`들 기반 해시로 완전 동일 항목은 스킵.

새 항목만 `existing_data` 뒤에 이어붙임.

## 7. 백업 후 저장

기존 JSON이 있으면 `rag_input_sample.json.backup_YYYYMMDD_HHMMSS`로 백업 생성

새 JSON을 예쁘게(`indent=2`) 저장.

콘솔에 총계(신규/중복/오류/첨부 수) 출력.

# 주요 함수 설명

## 1) `extract_text_from_pdf(path)`

- `PyMuPDF`로 페이지 순회 → `page.get_text()` 사용.
- 텍스트가 거의 없으면 OCR fallback: 300dpi로 렌더한 이미지를 `Tesseract`(`kor+eng`)로 인식.
- 각 페이지 앞에 `=== 페이지 N ===` 머리말을 붙여 원문 페이지 경계 유지.
- **참고**: Windows 기준 `pytesseract.pytesseract.tesseract_cmd` 경로를 상단에서 고정. (다른 OS면 경로 수정 필요)

## 2) `extract_text_from_hwp(path)`

- `olefile`로 구형 HWP(OLE) 스트림을 직접 열어 텍스트 추출.
- `PrvText`(미리보기) 우선 → 없으면 `BodyText/Section0..9`를 순회.
- **HWPX**(신규 포맷)는 미대응이므로 별도 처리 필요(추가 개선 포인트).

## 3) `find_pdf_version(base_dir, pdf_name)`

- HWP의 대체 텍스트 소스로 동일 이름의 PDF를 `pdf/`, `pdf/text/`, `pdf/image/`에서 탐색.
- 파일명 앞의 날짜 프리픽스(8자리)를 제외한 이름으로도 검색하여, 실제 저장명 변형에 대응.

## 4) `find_file_in_subfolders(base_dir, file_name)`

- 전체 하위 폴더를 돌며 **정확 일치** → **날짜 프리픽스 제거 후 부분 일치** → **간단 유사도**(동일 위치 동일 문자 수) 순으로 가장 그럴듯한 파일을 찾음.
- HWP는 먼저 `find_pdf_version` 호출로 PDF 우선 처리.

## 5) `create_content_hash(title, content, attachments)`

- **중복 제거 핵심**: 제목/본문/첨부파일명(정렬)으로 문자열을 만들고 MD5 해시.
- 첨부 텍스트 내용이 조금 달라도 파일명 구성이 같고 제목/본문이 같다면 중복으로 보도록 설계 → 빠르고 실용적인 증분 처리.

## 6) `load_existing_data(json_file)` / `save_data_with_backup(data, json_file)`

- 기존 JSON을 로드하고, 그로부터 해시 셋을 재구성.
- 저장 전에 타임스탬프 백업 생성(파일 파손/롤백 대비).

# 로그·통계 & 실행 흐름

- 진행 상황을 콘솔 로그로 자세히 출력(처리 N/M, 파일 경로 탐색 성공/실패, OCR 실패 메시지 등).
- 마지막에 총계(**전체/신규/중복/오류/최종 데이터/총 첨부**)를 정리 출력.

**기본 경로/파일명**:
- `csv_file = "복지용구_자료실.csv"`
- `attachments_dir = "attachments"`
- `output_file = "rag_input_sample.json"`

# 실전 팁 (RAG 연결/운영)

## 메타데이터 강화
JSON 항목에 `reg_date`, `source`(공지/법령), `file_types` 등을 추가해 검색 필터/가중치로 활용하세요.

## 대용량 최적화

- 페이지가 많은 PDF는 300dpi 렌더가 무겁습니다 → 텍스트 유무 판정 임계값(**20자**)를 조정하거나, 첫 페이지만 검사 후 전역 OCR 여부 결정 같은 최적화를 고려하세요.
- 파일별 캐시(해시→텍스트)를 두면 재실행 시 빠릅니다.

## 다국어/OCR 정확도
`lang="kor+eng"` 외에 필요한 언어 데이터 설치.

## 신규 HWPX 대응
HWPX는 ZIP/XML 포맷 → 별도 파서 적용을 검토.

## CSV 스키마 차이
법령자료실 CSV(`복지용구_법령자료실.csv`)도 처리하려면 `csv_file` 변수를 바꾸거나 두 CSV를 합쳐 순회하도록 확장하세요.