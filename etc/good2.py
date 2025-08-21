import os
import json
import fitz  # PyMuPDF
import pandas as pd
import glob
import zipfile
from PIL import Image
import io
import pytesseract
import re
from pathlib import Path

# Tesseract 경로 설정 (설치된 경우)
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def extract_text_from_pdf(path):
    try:
        doc = fitz.open(path)
        full_text = ""
        
        for page_num, page in enumerate(doc, start=1):
            text = page.get_text()
            
            # 페이지에 텍스트가 적으면 OCR 수행 시도
            # (Tesseract가 설치되어 있는 경우에만 작동)
            if len(text.strip()) < 20:
                try:
                    pix = page.get_pixmap(dpi=300)
                    img = Image.open(io.BytesIO(pix.tobytes("png")))
                    ocr_text = pytesseract.image_to_string(img, lang="kor+eng")
                    text += "\n" + ocr_text
                except Exception as e:
                    print(f"OCR 실패 (페이지 {page_num}): {e}")
            
            full_text += f"\n=== 페이지 {page_num} ===\n{text}"
        
        return full_text
    except Exception as e:
        return f"❌ PDF 오류: {e}"

def extract_text_from_hwp(path):
    try:
        import olefile
        if not olefile.isOleFile(path):
            return "❌ 올바른 HWP 파일이 아닙니다."
        
        ole = olefile.OleFileIO(path)
        text = ""
        
        # PrvText 스트림 확인 (미리보기 텍스트)
        if ole.exists('PrvText'):
            with ole.openstream('PrvText') as stream:
                text = stream.read().decode('utf-16', errors='ignore')
                if text.strip():
                    return text.strip()
        
        # BodyText 스트림 확인 (본문 텍스트)
        for i in range(0, 10):  # 여러 개의 BodyText 섹션이 있을 수 있음
            section_name = f'BodyText/Section{i}'
            if ole.exists(section_name):
                with ole.openstream(section_name) as stream:
                    section_text = stream.read().decode('utf-16', errors='ignore')
                    text += section_text + "\n"
        
        if text.strip():
            return text.strip()
        else:
            return "❌ HWP 파일에서 텍스트를 찾을 수 없습니다."
    except Exception as e:
        return f"❌ HWP 오류: {e}"

def extract_text_from_hwpx(path):
    """HWPX 파일에서 텍스트를 추출합니다."""
    try:
        import lxml.etree as ET
    except ImportError:
        return "❌ lxml 라이브러리가 설치되지 않았습니다. pip install lxml"
    
    try:
        texts = []
        with zipfile.ZipFile(str(path), "r") as zf:
            # 디버깅을 위해 파일 목록 출력
            print(f"HWPX 파일 내부 구조: {zf.namelist()}")
            
            for name in zf.namelist():
                n = name.lower()
                # 'Contents/' 경로에서 XML 파일 찾기 (기존의 'word/' 경로는 잘못된 경로)
                if (n.startswith("contents/") or n.startswith("content/")) and n.endswith(".xml"):
                    try:
                        print(f"XML 파일 분석 중: {name}")
                        with zf.open(name) as f:
                            data = f.read()
                        root = ET.fromstring(data)
                        s = root.xpath("string()")
                        if s and str(s).strip():
                            texts.append(str(s))
                    except Exception as e:
                        print(f"❌ XML 오류 ({name}): {e}")
                        texts.append(f"❌ XML 오류 ({name}): {e}")
        
        if texts:
            return "\n".join(texts)
        else:
            # 다른 경로도 시도해보기
            for name in zf.namelist():
                if name.lower().endswith(".xml"):
                    try:
                        print(f"추가 XML 파일 분석 중: {name}")
                        with zf.open(name) as f:
                            data = f.read()
                        root = ET.fromstring(data)
                        s = root.xpath("string()")
                        if s and str(s).strip():
                            texts.append(str(s))
                    except Exception as e:
                        print(f"❌ 추가 XML 오류 ({name}): {e}")
            
            if texts:
                return "\n".join(texts)
            else:
                return "❌ HWPX 파일에서 텍스트를 찾을 수 없습니다."
    except Exception as e:
        return f"❌ HWPX 오류: {e}"

def find_hwpx_for_hwp(hwp_path):
    """HWP 파일에 대응하는 HWPX 파일을 찾습니다."""
    hwp_path = Path(hwp_path)
    hwpx_name = hwp_path.with_suffix(".hwpx").name
    
    # 1. 같은 폴더에서 찾기
    hwpx_path = hwp_path.with_suffix(".hwpx")
    if hwpx_path.exists():
        return str(hwpx_path)
    
    # 2. attachments/hwpx 폴더에서 찾기
    hwpx_dir = Path("attachments/hwpx")
    if hwpx_dir.exists():
        for file in hwpx_dir.glob("*.hwpx"):
            if file.name == hwpx_name:
                return str(file)
    
    # 3. 파일명 유사성으로 찾기
    if hwpx_dir.exists():
        hwp_stem = hwp_path.stem
        best_match = None
        best_score = 0
        
        for file in hwpx_dir.glob("*.hwpx"):
            # 파일명 유사도 계산
            similarity = sum(1 for a, b in zip(file.stem.lower(), hwp_stem.lower()) if a == b)
            if similarity > best_score:
                best_score = similarity
                best_match = file
        
        # 유사도가 충분히 높은 경우에만 반환
        if best_match and best_score > len(hwp_stem) * 0.7:  # 70% 이상 일치
            return str(best_match)
    
    return None

def find_file_in_subfolders(base_dir, file_name):
    """하위 폴더를 포함하여 파일을 검색합니다."""
    # 1. 정확한 파일명으로 검색
    for root, _, files in os.walk(base_dir):
        if file_name in files:
            return os.path.join(root, file_name)
    
    # 2. 확장자 변경하여 검색 (hwp -> hwpx)
    file_path = Path(file_name)
    if file_path.suffix.lower() == '.hwp':
        hwpx_name = file_path.with_suffix('.hwpx').name
        for root, _, files in os.walk(base_dir):
            if hwpx_name in files:
                print(f"✅ HWPX 파일 찾음: {hwpx_name}")
                return os.path.join(root, hwpx_name)
    
    # 3. 날짜 프리픽스가 있는 경우 (예: 20250730[공고]_2025년...)
    # 파일명에서 날짜 프리픽스를 제거한 부분과 일치하는지 확인
    clean_name = file_name
    if len(file_name) > 8:  # 최소 8자리 이상 (YYYYMMDD)
        # 날짜 프리픽스가 있을 수 있는 파일명에서 날짜 부분 제거
        clean_name = file_name[8:]
    
    # 모든 파일을 검색하여 날짜 프리픽스를 제외한 파일명이 포함되는지 확인
    for root, _, files in os.walk(base_dir):
        for f in files:
            # 날짜 프리픽스(8자리)를 제외한 부분이 일치하는지 확인
            if len(f) > 8 and clean_name in f[8:]:
                print(f"✅ 날짜 프리픽스 포함 파일 찾음: {f}")
                return os.path.join(root, f)
            # 또는 파일명에 clean_name이 포함되는지 확인
            elif clean_name in f:
                print(f"✅ 유사 파일명 찾음: {f}")
                return os.path.join(root, f)
    
    # 4. 확장자만 일치하는 파일 중 가장 유사한 것 찾기
    ext = os.path.splitext(file_name)[1].lower()
    if ext:
        best_match = None
        best_score = 0
        for root, _, files in os.walk(base_dir):
            for f in files:
                f_ext = os.path.splitext(f)[1].lower()
                # 원본이 hwp인 경우 hwpx도 확인
                if (f_ext == ext) or (ext == '.hwp' and f_ext == '.hwpx'):
                    # 간단한 유사도 측정 (공통 부분 문자열 길이)
                    common_chars = sum(1 for a, b in zip(f.lower(), file_name.lower()) if a == b)
                    if common_chars > best_score:
                        best_score = common_chars
                        best_match = os.path.join(root, f)
        
        if best_match and best_score > len(ext) + 2:  # 확장자보다 더 많은 문자가 일치해야 함
            print(f"✅ 유사도 기반 파일 찾음: {os.path.basename(best_match)}")
            return best_match
    
    return None

# 경로
csv_file = "복지용구_자료실.csv"
attachments_dir = "attachments"

# 테스트용 게시물 제목들
selected_titles = [
    "2025년 하반기 복지용구 신규 급여결정신청 공고(고시・고시외품목)"
]

df = pd.read_csv(csv_file)
output = []

for _, row in df.iterrows():
    if row["title"] not in selected_titles:
        continue

    # content 필드가 비어있거나 NaN인 경우 빈 문자열로 처리
    content = ""
    if isinstance(row["content"], str) and row["content"]:
        content = row["content"]  # 전체 내용 사용 (제한 없음)
    
    post = {
        "title": row["title"],
        "url": row["url"],
        "content": content,
        "attachments": []
    }

    # 첨부파일 리스트에서 파일명 추출
    if isinstance(row["attachments"], str):
        for item in row["attachments"].split("; "):
            if "(" in item:
                try:
                    # 파일명에서 URL 부분 제거
                    file_name = item.split(" (")[0].strip()
                    
                    # 하위 폴더를 포함하여 파일 검색
                    file_path = find_file_in_subfolders(attachments_dir, file_name)
                    
                    if not file_path:
                        print(f"⚠️ 파일을 찾을 수 없음: {file_name}")
                        continue
                    
                    print(f"✅ 파일 찾음: {os.path.relpath(file_path)}")
                    
                    ext = os.path.splitext(file_path)[1].lower()
                    if ext == ".pdf":
                        text = extract_text_from_pdf(file_path)
                    elif ext == ".hwp":
                        # HWP 파일인 경우 HWPX 파일이 있는지 확인
                        hwpx_path = find_hwpx_for_hwp(file_path)
                        if hwpx_path:
                            print(f"✅ HWP 대신 HWPX 사용: {os.path.basename(hwpx_path)}")
                            text = extract_text_from_hwpx(hwpx_path)
                        else:
                            text = extract_text_from_hwp(file_path)
                    elif ext == ".hwpx":
                        text = extract_text_from_hwpx(file_path)
                    else:
                        text = f"⚠️ 지원되지 않는 파일 형식: {ext}"
                    
                    post["attachments"].append({
                        "file_name": os.path.basename(file_path),
                        "text": text
                    })
                except Exception as e:
                    print(f"❌ 파일 처리 중 오류: {e}")
    
    output.append(post)

# JSON 저장
with open("rag_input_sample.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print("✅ rag_input_sample.json 생성 완료")