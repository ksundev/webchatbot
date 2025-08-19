import os
import json
import fitz  # PyMuPDF
import pandas as pd
import glob
from PIL import Image
import io
import pytesseract
import hashlib
from datetime import datetime
                    
# Tesseract 경로 설정 (설치된 경우)
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def extract_text_from_pdf(path):
    try:
        doc = fitz.open(path)
        full_text = ""
        
        for page_num, page in enumerate(doc, start=1):
            text = page.get_text()
            
            # 페이지에 텍스트가 적으면 OCR 수행 시도
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

def find_pdf_version(base_dir, pdf_name):
    """PDF 폴더에서 PDF 버전의 파일을 찾습니다."""
    # PDF 폴더 내에서 직접 검색
    pdf_dir = os.path.join(base_dir, "pdf")
    if os.path.exists(pdf_dir):
        # 정확한 이름으로 검색
        pdf_path = os.path.join(pdf_dir, pdf_name)
        if os.path.exists(pdf_path):
            return pdf_path
        
        # text/image 하위 폴더에서 검색
        for subdir in ["text", "image"]:
            subdir_path = os.path.join(pdf_dir, subdir)
            if os.path.exists(subdir_path):
                pdf_path = os.path.join(subdir_path, pdf_name)
                if os.path.exists(pdf_path):
                    return pdf_path
        
        # 파일명 일부로 검색
        clean_name = pdf_name
        if len(pdf_name) > 8:  # 날짜 프리픽스 제거
            clean_name = pdf_name[8:]
            
        for root, _, files in os.walk(pdf_dir):
            for f in files:
                if f.endswith('.pdf') and (clean_name in f or pdf_name in f):
                    return os.path.join(root, f)
    
    return None

def find_file_in_subfolders(base_dir, file_name):
    """하위 폴더를 포함하여 파일을 검색합니다."""
    # 0. PDF 버전이 있는지 먼저 확인 (HWP 파일인 경우)
    if file_name.lower().endswith('.hwp'):
        pdf_name = file_name.replace('.hwp', '.pdf').replace('.HWP', '.pdf')
        pdf_path = find_pdf_version(base_dir, pdf_name)
        if pdf_path:
            print(f"✅ HWP 대신 PDF 버전 찾음: {os.path.basename(pdf_path)}")
            return pdf_path
    
    # 1. 정확한 파일명으로 검색
    for root, _, files in os.walk(base_dir):
        if file_name in files:
            return os.path.join(root, file_name)
    
    # 2. 날짜 프리픽스가 있는 경우 (예: 20250730[공고]_2025년...)
    clean_name = file_name
    if len(file_name) > 8:  # 최소 8자리 이상 (YYYYMMDD)
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
    
    # 3. 확장자만 일치하는 파일 중 가장 유사한 것 찾기
    ext = os.path.splitext(file_name)[1].lower()
    if ext:
        best_match = None
        best_score = 0
        for root, _, files in os.walk(base_dir):
            for f in files:
                if f.lower().endswith(ext):
                    # 간단한 유사도 측정 (공통 부분 문자열 길이)
                    common_chars = sum(1 for a, b in zip(f.lower(), file_name.lower()) if a == b)
                    if common_chars > best_score:
                        best_score = common_chars
                        best_match = os.path.join(root, f)
        
        if best_match and best_score > len(ext) + 2:  # 확장자보다 더 많은 문자가 일치해야 함
            print(f"✅ 유사도 기반 파일 찾음: {os.path.basename(best_match)}")
            return best_match
    
    return None

def create_content_hash(title, content, attachments):
    """게시물의 고유 해시값을 생성하여 중복 확인용으로 사용"""
    # 제목, 내용, 첨부파일명들을 합쳐서 해시 생성
    attachment_names = [att.get('file_name', '') for att in attachments] if attachments else []
    combined_content = f"{title}|{content}|{'|'.join(sorted(attachment_names))}"
    return hashlib.md5(combined_content.encode('utf-8')).hexdigest()

def load_existing_data(json_file):
    """기존 JSON 파일을 로드하고 해시값들을 반환"""
    if not os.path.exists(json_file):
        return [], set()
    
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            existing_data = json.load(f)
        
        # 기존 데이터의 해시값들 생성
        existing_hashes = set()
        for item in existing_data:
            content_hash = create_content_hash(
                item.get('title', ''),
                item.get('content', ''),
                item.get('attachments', [])
            )
            existing_hashes.add(content_hash)
        
        print(f"📄 기존 데이터 로드: {len(existing_data)}개 항목")
        return existing_data, existing_hashes
    except Exception as e:
        print(f"❌ 기존 데이터 로드 실패: {e}")
        return [], set()

def save_data_with_backup(data, json_file):
    """백업을 만들고 새 데이터를 저장"""
    # 백업 파일 생성
    if os.path.exists(json_file):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"{json_file}.backup_{timestamp}"
        try:
            import shutil
            shutil.copy2(json_file, backup_file)
            print(f"📁 백업 파일 생성: {backup_file}")
        except Exception as e:
            print(f"⚠️ 백업 생성 실패: {e}")
    
    # 새 데이터 저장
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# 경로
csv_file = "복지용구_자료실.csv"
attachments_dir = "attachments"
output_file = "rag_input_sample.json"

print("🚀 복지용구 자료실 전체 데이터 처리 시작")

# 기존 데이터 로드
existing_data, existing_hashes = load_existing_data(output_file)

# CSV 파일 로드
df = pd.read_csv(csv_file)
print(f"📊 CSV에서 {len(df)}개 게시물 발견")

# 새로 추가될 데이터
new_data = []
duplicate_count = 0
error_count = 0
processed_count = 0

# 모든 게시물 처리
for idx, row in df.iterrows():
    processed_count += 1
    print(f"\n📝 처리 중 ({processed_count}/{len(df)}): {row['title'][:50]}...")
    
    # content 필드가 비어있거나 NaN인 경우 빈 문자열로 처리
    content = ""
    if isinstance(row["content"], str) and row["content"]:
        content = row["content"]
    
    # 임시 게시물 객체 생성 (중복 확인용)
    temp_post = {
        "title": row["title"],
        "url": row["url"],
        "content": content,
        "attachments": []
    }
    
    # 첨부파일 처리
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
                        # HWP 파일인 경우 PDF 버전이 있는지 확인
                        pdf_path = file_path.replace(".hwp", ".pdf")
                        if os.path.exists(pdf_path):
                            print(f"✅ HWP 대신 PDF 버전 사용: {os.path.basename(pdf_path)}")
                            text = extract_text_from_pdf(pdf_path)
                        else:
                            # PDF 폴더에서 동일한 이름의 PDF 파일 찾기 시도
                            pdf_dir = os.path.join(attachments_dir, "pdf")
                            pdf_filename = os.path.basename(file_path).replace(".hwp", ".pdf")
                            pdf_path_in_dir = os.path.join(pdf_dir, pdf_filename)
                            
                            if os.path.exists(pdf_path_in_dir):
                                print(f"✅ PDF 폴더에서 대체 파일 찾음: {pdf_filename}")
                                text = extract_text_from_pdf(pdf_path_in_dir)
                            else:
                                text = extract_text_from_hwp(file_path)
                    else:
                        text = f"⚠️ 지원되지 않는 파일 형식: {ext}"
                    
                    temp_post["attachments"].append({
                        "file_name": os.path.basename(file_path),
                        "text": text
                    })
                except Exception as e:
                    print(f"❌ 파일 처리 중 오류: {e}")
                    error_count += 1
    
    # 중복 확인
    content_hash = create_content_hash(
        temp_post["title"],
        temp_post["content"],
        temp_post["attachments"]
    )
    
    if content_hash in existing_hashes:
        print(f"🔄 중복 데이터 스킵: {temp_post['title'][:30]}...")
        duplicate_count += 1
        continue
    
    # 새 데이터에 추가
    new_data.append(temp_post)
    existing_hashes.add(content_hash)  # 이후 중복 확인을 위해 추가
    print(f"✅ 새 데이터 추가: {temp_post['title'][:30]}...")

# 기존 데이터와 새 데이터 합치기
final_data = existing_data + new_data

# 데이터 저장
save_data_with_backup(final_data, output_file)

print(f"\n🎉 처리 완료!")
print(f"📊 전체 게시물: {len(df)}개")
print(f"✅ 새로 추가: {len(new_data)}개")
print(f"🔄 중복 스킵: {duplicate_count}개")
print(f"❌ 오류 발생: {error_count}개")
print(f"📁 최종 데이터: {len(final_data)}개")
print(f"💾 저장 완료: {output_file}")

# 첨부파일 통계
total_attachments = sum(len(item.get('attachments', [])) for item in final_data)
print(f"📎 총 첨부파일: {total_attachments}개")

