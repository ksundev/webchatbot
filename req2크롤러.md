# req2.py — "복지용구 공지사항" 크롤러

**커뮤니티 키**: `B0022`, **첨부 루트**: `attachments`

## 목적

장기요양보험 홈페이지(공지사항) 게시글을 페이지 단위로 순회하며 제목/본문/등록일/첨부파일을 수집합니다.

첨부파일(PDF/HWP/XLS/XLSX/ZIP)을 종류별 폴더로 저장하고, HWP는 자동 PDF 변환, PDF는 텍스트형/이미지형 분류까지 수행합니다.

수집 결과를 **CSV(복지용구_자료실.csv)**로 내보내 RAG 파이프라인의 임베딩 입력으로 활용할 수 있게 합니다.

## 핵심 동작 흐름

### 1. 목록 크롤링 → boardId 수집

`LIST_URL`에 `communityKey=B0022`로 요청, 목록 HTML에서 `boardId`를 파싱합니다.

### 2. 상세 페이지 파싱

`boardId`별 상세(뷰) 페이지 요청 →

- **제목**: `.tbl_tit_wrap .tbl_tit`
- **본문**: `td#BOARD_CONTENT` 텍스트(CSV 안전을 위해 `"` 이스케이프)
- **등록일 프리픽스(YYYYMMDD)**: 페이지 상단 테이블의 날짜 패턴을 정규식으로 추출(없으면 `00000000`)
- **첨부**: `td.tongboard_view[colspan='3']` 영역의 `<a>`들에서 파일 URL·이름 추출 → 파일명 앞에 등록일 프리픽스 부여 후 다운로드.

### 3. 첨부파일 다운로드 & 정리

확장자에 따라 `attachments/pdf|hwp|xlsx|xls|zip`로 저장.

- PDF는 중복 검사를 `pdf` 기본 폴더뿐 아니라 `pdf/text`, `pdf/image` 폴더까지 삼중 확인하여 중복 다운로드 방지.
- 스트리밍 다운로드(256KB 청크) + 1KB 미만 파일은 의심으로 간주해 제거.

### 4. HWP → PDF 자동 변환 (Windows/한컴 설치 필요)

`pywin32`로 HWP COM 객체 구동, `SaveAs(...,"PDF")` 또는 `HAction.Execute("FileSaveAsPdf", ...)` 이중 시도.

이미 변환된 항목(파일명 중복/크기 0 방지)은 건너뛰고, 성공/건너뜀/실패 개수 요약 출력.

### 5. PDF 텍스트/이미지형 분류

`PyMuPDF`로 페이지별 XObject 이미지 존재 여부를 확인 → 있으면 `image`, 없으면 `text` 폴더로 이동.

OCR 파이프라인 분기 등에 활용 가능.

### 6. CSV 저장

`title`, `url`, `content`, `reg_date`, `attachments` 컬럼으로 `복지용구_자료실.csv` 생성(문제 시 JSON 대안 저장).

## 폴더/파일 구조

```
attachments/
├── pdf/        (원본 PDF 임시 수신)
│   ├── text/     (텍스트형 PDF)
│   └── image/    (스캔/이미지형 PDF)
├── hwp/
├── xlsx/
├── xls/
└── zip/
```

**파일명 규칙**: `YYYYMMDD원본파일명.확장자` (등록일 프리픽스) → 정렬/최신순 관리에 유리.

## 중복·오류 방지 장치

- **파일명 sanitize**: 금칙문자 제거·너무 긴 이름 180자 컷.
- **PDF 중복 검사**: 기본/pdf/text/pdf/image 전역 확인.
- **다운로드 크기 검증**: 1KB 미만은 실패로 간주.
- **HWP 변환 재시도**: 두 가지 변환 경로.

## 실행 구간(현재 설정 주의)

메인 루프가 `for page in range(2, 3)`로 되어 있어 현재는 2페이지만 수집합니다(예: 테스트용). 운영 시 `range(1, 22)`처럼 조정하세요.