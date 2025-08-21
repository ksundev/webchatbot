import requests
from bs4 import BeautifulSoup
import csv
import os
import time
import re
import pandas as pd
import os, shutil
import unicodedata
import fitz  # PyMuPDF
import sys
from pathlib import Path

BASE_URL = "https://www.longtermcare.or.kr"
LIST_URL = BASE_URL + "/npbs/cms/board/board/Board.jsp"

ATTACH_DIR = "attachments1"
PDF_DIR = os.path.join(ATTACH_DIR, "pdf")
HWP_DIR = os.path.join(ATTACH_DIR, "hwp")
XLSX_DIR = os.path.join(ATTACH_DIR, "xlsx")
XLS_DIR  = os.path.join(ATTACH_DIR, "xls")
ZIP_DIR  = os.path.join(ATTACH_DIR, "zip")
PDF_TEXT_DIR = os.path.join(PDF_DIR, "text")
PDF_IMAGE_DIR = os.path.join(PDF_DIR, "image")
os.makedirs(ATTACH_DIR, exist_ok=True)
os.makedirs(PDF_DIR, exist_ok=True)
os.makedirs(HWP_DIR, exist_ok=True)
os.makedirs(XLSX_DIR, exist_ok=True)
os.makedirs(XLS_DIR,  exist_ok=True)
os.makedirs(ZIP_DIR,  exist_ok=True)
os.makedirs(PDF_TEXT_DIR,  exist_ok=True)
os.makedirs(PDF_IMAGE_DIR, exist_ok=True)

EXT_DIRS = {
    ".pdf": PDF_DIR,
    ".hwp": HWP_DIR,
    ".xlsx": XLSX_DIR,
    ".xls": XLS_DIR,
    ".zip": ZIP_DIR,
}
ALLOWED_EXTS = set(EXT_DIRS.keys())

# 폴더 생성
os.makedirs(ATTACH_DIR, exist_ok=True)
for d in EXT_DIRS.values():
    os.makedirs(d, exist_ok=True)

HEADERS = {"User-Agent": "Mozilla/5.0"}

def ensure_unique_path(dirpath: str, filename: str) -> str:
    base, ext = os.path.splitext(filename)
    candidate = os.path.join(dirpath, filename)
    i = 1
    while os.path.exists(candidate):
        candidate = os.path.join(dirpath, f"{base}_{i}{ext}")
        i += 1
    return candidate

def pdf_has_any_image(pdf_path: str) -> bool:
    """페이지 중 하나라도 이미지 XObject가 있으면 True"""
    try:
        with fitz.open(pdf_path) as doc:
            for i, page in enumerate(doc, start=1):
                imgs = page.get_images(full=True)
                # 디버깅
                print(f"   - {os.path.basename(pdf_path)} p{i}: images={len(imgs)}")
                if imgs:
                    return True
    except Exception as e:
        print(f"⚠️ PDF 열기 실패: {os.path.basename(pdf_path)} → {e}")
    return False

def split_pdf_by_content():
    moved = {"image": 0, "text": 0}
    for fname in os.listdir(PDF_DIR):
        src = os.path.join(PDF_DIR, fname)
        if not os.path.isfile(src):
            continue
        if not fname.lower().endswith(".pdf"):
            continue

        # 이미지 여부 판정
        has_img = pdf_has_any_image(src)
        dst_dir = PDF_IMAGE_DIR if has_img else PDF_TEXT_DIR
        
        # 이미 동일한 이름의 파일이 있는지 확인
        dst_file = os.path.join(dst_dir, fname)
        if os.path.exists(dst_file):
            print(f"⏭️ 이미 존재하는 파일 건너뜀: {fname}")
            continue
            
        dst = ensure_unique_path(dst_dir, fname)
        shutil.move(src, dst)
        moved["image" if has_img else "text"] += 1
        print(f"📦 이동: {fname}  →  {os.path.relpath(dst)}")

    print(f"\n✅ 정리 완료: image {moved['image']}개, text {moved['text']}개")

def convert_hwp_to_pdf():
    """다운로드된 HWP 파일들을 PDF로 자동 변환"""
    print("\n🔄 HWP → PDF 변환 시작...")
    
    try:
        import win32com.client as win32
    except Exception:
        print("⚠️ pywin32가 설치되어 있지 않습니다. HWP 변환을 건너뜁니다.")
        print("   설치 방법: pip install pywin32")
        return
    
    SRC = Path(HWP_DIR)
    DST = Path(PDF_DIR)
    PDF_TEXT = Path(PDF_TEXT_DIR)
    PDF_IMAGE = Path(PDF_IMAGE_DIR)
    
    if not SRC.exists():
        print(f"⚠️ HWP 폴더가 없습니다: {SRC}")
        return
    
    # PDF 폴더 생성
    DST.mkdir(parents=True, exist_ok=True)
    
    # HWP 파일 목록
    hwp_files = list(SRC.rglob("*.hwp"))
    if not hwp_files:
        print("📂 변환할 HWP 파일이 없습니다.")
        return
    
    print(f"📋 변환 대상 HWP 파일: {len(hwp_files)}개")
    
    # 기존 변환된 파일 확인 (PDF 폴더 + 하위 폴더 모두 검사)
    existing_pdf_files = set()
    
    # PDF 기본 폴더 확인
    for pdf_file in DST.glob("*.pdf"):
        existing_pdf_files.add(pdf_file.stem)
    
    # PDF 텍스트 폴더 확인
    for pdf_file in PDF_TEXT.glob("*.pdf"):
        existing_pdf_files.add(pdf_file.stem)
    
    # PDF 이미지 폴더 확인
    for pdf_file in PDF_IMAGE.glob("*.pdf"):
        existing_pdf_files.add(pdf_file.stem)
    
    print(f"📋 기존 변환된 PDF 파일: {len(existing_pdf_files)}개")
    
    # 방법 1: 직접 변환
    try:
        print("🔧 Hancom HWP COM 객체 실행...")
        hwp = win32.gencache.EnsureDispatch("HWPFrame.HwpObject")
        
        # 보안 설정 해제 시도
        try:
            hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")
        except Exception:
            pass
        
        try:
            hwp.XHwpWindows.Item(0).Visible = True
        except:
            pass
    except Exception as e:
        print(f"❌ HWP COM 객체 실행 실패: {e}")
        return
    
    total, ok, skip, fail = 0, 0, 0, 0
    
    for src in hwp_files:
        total += 1
        # SRC 기준 상대경로 유지 → DST에 같은 폴더 구조로 저장
        rel = src.relative_to(SRC)
        out = DST / rel.with_suffix(".pdf")
        out.parent.mkdir(parents=True, exist_ok=True)
        
        # 파일명(확장자 제외)이 이미 변환된 파일 목록에 있는지 확인
        if src.stem in existing_pdf_files:
            print(f"⏭️ {src.name} (이미 PDF로 변환된 파일이 존재함)")
            skip += 1
            continue
        
        # 이미 변환된 파일이 있는지 확인 (파일 크기도 체크)
        if out.exists():
            # 파일 크기가 0보다 큰지 확인 (정상적으로 변환된 파일인지)
            if out.stat().st_size > 0:
                print(f"⏭️ {src.name} (이미 변환됨, {out.stat().st_size:,} bytes)")
                skip += 1
                continue
            else:
                print(f"🔄 {out.name} 파일이 비어있어서 다시 변환합니다.")
                out.unlink()  # 빈 파일 삭제
        
        try:
            print(f"🔄 변환 중: {src.name}")
            
            # 절대 경로로 변환
            src_abs = str(src.resolve())
            out_abs = str(out.resolve())
            
            # 파일 열기
            hwp.Open(src_abs)
            
            # 방법 1: 직접 변환 시도
            try:
                hwp.SaveAs(out_abs, "PDF")
                success = True
            except:
                success = False
            
            # 방법 1이 실패하면 방법 2 시도
            if not success or not out.exists() or out.stat().st_size == 0:
                print("  방법 1 실패, 방법 2 시도 중...")
                try:
                    hwp.HAction.GetDefault("FileSaveAsPdf", hwp.HParameterSet.HFileOpenSave.HSet)
                    hwp.HParameterSet.HFileOpenSave.filename = out_abs
                    hwp.HParameterSet.HFileOpenSave.Format = "PDF"
                    hwp.HAction.Execute("FileSaveAsPdf", hwp.HParameterSet.HFileOpenSave.HSet)
                except:
                    pass
            
            # 파일 확인
            if out.exists() and out.stat().st_size > 0:
                print(f"✅ 변환 완료: {src.name} → {out.name} ({out.stat().st_size:,} bytes)")
                # 변환 성공한 파일 목록에 추가
                existing_pdf_files.add(src.stem)
                ok += 1
            else:
                print(f"❌ 변환 실패: {src.name}")
                fail += 1
            
            hwp.Clear(1)  # 현재 문서 닫기
        except Exception as e:
            print(f"❌ 변환 오류 {src.name}: {e}")
            fail += 1
    
    # HWP 종료
    try:
        hwp.Quit()
    except Exception:
        pass
    
    print(f"\n📊 변환 요약: 총 {total}개 / 변환 {ok}개 / 건너뜀 {skip}개 / 실패 {fail}개")
    
    # 결과 확인
    pdf_files = list(DST.rglob("*.pdf"))
    print(f"📂 PDF 폴더 내 총 파일 수: {len(pdf_files)}개")

def sanitize_filename(name: str) -> str:
    # 윈도우 금칙문자 제거 + 앞뒤 공백 정리
    name = unicodedata.normalize("NFC", name)
    name = re.sub(r'[\\/:*?"<>|]', '_', name).strip()
    # 너무 긴 파일명 방지 (확장자 제외 180자 정도로 컷)
    root, ext = os.path.splitext(name)
    if len(root) > 180:
        root = root[:180]
    return root + ext

def extract_reg_date_prefix(soup: BeautifulSoup) -> str:
    """페이지 내 YYYY/MM/DD, YYYY-MM-DD, YYYY.MM.DD → YYYYMMDD로 변환"""
    # 우선 th.tongboard_view에서 직접 찾기 (네가 말한 위치)
    for th in soup.find_all("th", class_="tongboard_view"):
        txt = th.get_text(strip=True)
        m = re.search(r'(20\d{2})[./-](\d{1,2})[./-](\d{1,2})', txt)
        if m:
            y, mo, d = m.group(1), int(m.group(2)), int(m.group(3))
            return f"{y}{mo:02d}{d:02d}"
    # 백업: 페이지 전체에서라도 찾기
    txt_all = soup.get_text(" ", strip=True)
    m = re.search(r'(20\d{2})[./-](\d{1,2})[./-](\d{1,2})', txt_all)
    if m:
        y, mo, d = m.group(1), int(m.group(2)), int(m.group(3))
        return f"{y}{mo:02d}{d:02d}"
    return "00000000"

def get_board_ids(page):
    params = {
        "act": "LIST",
        "communityKey": "B0018",  # 변경된 communityKey
        "pageNum": page,
        "pageSize": 10
    }
    res = requests.get(LIST_URL, params=params, headers=HEADERS)
    soup = BeautifulSoup(res.text, "html.parser")
    board_ids = []
    for tag in soup.select("a[href*='boardId=']"):
        href = tag.get("href")
        if "boardId=" in href:
            board_id = href.split("boardId=")[-1].split("&")[0]
            board_ids.append(board_id)
    return list(set(board_ids))

def download_file(file_url, file_name):
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.longtermcare.or.kr"}

    # "(12345 Bytes)" 꼬리 방어 + 파일명 클린
    file_name = re.sub(r'\s*\(\d+\s*bytes?\)\s*$', '', file_name, flags=re.IGNORECASE).strip()
    file_name = sanitize_filename(file_name)

    ext = os.path.splitext(file_name)[-1].lower()
    target_dir = EXT_DIRS.get(ext, ATTACH_DIR)
    
    save_path = os.path.join(target_dir, file_name)
    
    # PDF 파일인 경우 PDF_TEXT_DIR와 PDF_IMAGE_DIR에도 중복 확인
    if ext == ".pdf":
        # PDF 기본 폴더, 텍스트 폴더, 이미지 폴더 모두 확인
        if (os.path.exists(save_path) or 
            os.path.exists(os.path.join(PDF_TEXT_DIR, file_name)) or 
            os.path.exists(os.path.join(PDF_IMAGE_DIR, file_name))):
            print(f"⏭️ 이미 존재하는 PDF 파일 건너뜀: {file_name}")
            return save_path

    try:
        with requests.get(file_url, headers=headers, allow_redirects=True, timeout=30, stream=True) as r:
            r.raise_for_status()
            total = 0
            # ✅ 항상 덮어쓰기
            with open(save_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=256 * 1024):
                    if chunk:
                        f.write(chunk)
                        total += len(chunk)

        if total < 1024:  # 너무 작으면 실패 처리(옵션)
            print(f"⚠️ 다운로드 의심(너무 작음): {file_name} size={total} bytes")
            try:
                os.remove(save_path)
            except:
                pass
            return None

        print(f"📥 다운로드 성공: {os.path.relpath(save_path)}")
        return save_path

    except Exception as e:
        print(f"❌ 에러 발생: {file_name} → {e}")
        return None


def parse_post(board_id):
    url = f"https://www.longtermcare.or.kr/npbs/cms/board/board/Board.jsp?communityKey=B0018&boardId={board_id}&act=VIEW"
    res = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(res.text, "html.parser")

    # ✅ 제목
    try:
        title = soup.select_one("div.tbl_tit_wrap span.tbl_tit").text.strip()
    except:
        title = "제목 없음"

    # ✅ 본문
    try:
        content_tag = soup.select_one("td#BOARD_CONTENT")
        # CSV 파일에 저장할 때 특수문자 처리를 위해 텍스트 정리
        content = content_tag.get_text(separator="\n").strip()
        # 따옴표나 쉼표 등 CSV 파일에서 문제가 될 수 있는 문자 처리
        content = content.replace('"', '""')  # 큰따옴표 이스케이프
    except:
        content = "본문 없음"

    # ✅ 등록일 프리픽스 (예: 20250430)
    reg_prefix = extract_reg_date_prefix(soup)

    # ✅ 첨부파일
    attachments = []
    file_section = soup.select_one("td.tongboard_view[colspan='3']")
    if file_section:
        for link in file_section.find_all("a", href=True):
            file_url = BASE_URL + link["href"]
            raw_name = link.text.strip()
            # "(12345 Bytes)" 꼬리 제거
            clean_name = re.sub(r'\s*\(\d+\s*Bytes\)\s*$', '', raw_name).strip()
            ext = os.path.splitext(clean_name)[-1].lower()

            if ext in ALLOWED_EXTS:
                final_name = f"{reg_prefix}{clean_name}"   # 날짜 프리픽스 유지
                download_file(file_url, final_name)
                attachments.append(f"{final_name} ({file_url})")

    else:
        print("첨부파일 없음")

    return {
        "title": title,
        "url": url,
        "content": content,
        "reg_date": reg_prefix,                 # ← CSV에도 등록일 넣음
        "attachments": "; ".join(attachments)
    }

def save_to_csv(data, filename="복지용구_법령자료실.csv"):
    try:
        df = pd.DataFrame(data)
        df.to_csv(filename, index=False, encoding="utf-8-sig", quotechar='"', quoting=csv.QUOTE_ALL, escapechar='\\')
        print(f"📊 총 {len(data)}개 데이터가 {filename}에 저장되었습니다.")
    except Exception as e:
        print(f"CSV 저장 중 오류 발생: {e}")
        # 대안으로 JSON으로 저장
        import json
        with open(filename.replace('.csv', '.json'), 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"📊 총 {len(data)}개 데이터가 JSON 파일로 저장되었습니다.")
        
if __name__ == "__main__":
    all_data = []
    for page in range(1, 2):  # 1~5페이지
        board_ids = get_board_ids(page)
        for board_id in board_ids:
            post = parse_post(board_id)
            all_data.append(post)
            print(f"✅ 저장 대상: {post['title']}")
            time.sleep(0.5)

    save_to_csv(all_data)
    print("\n📁 모든 게시물을 CSV 파일로 저장 완료!")
    
    # 🔄 HWP → PDF 자동 변환
    convert_hwp_to_pdf()
    
    # 📂 PDF 자동 분류
    split_pdf_by_content()





