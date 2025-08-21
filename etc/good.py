import os
import json
import fitz  # PyMuPDF
import pandas as pd

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
                    from PIL import Image
                    import io
                    import pytesseract
                    
                    #Tesseract 경로 설정 (설치된 경우)
                    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

                    
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
        content = row["content"][:1000] + "..." if len(row["content"]) > 1000 else row["content"]
    
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
                    # 파일명에서 (숫자 Bytes) 부분 제거
                    file_name = item.split(" (")[0].strip()
                    
                    # 파일 경로 확인
                    file_path = os.path.join(attachments_dir, file_name)
                    
                    # 파일이 존재하는지 확인
                    if not os.path.exists(file_path):
                        # 파일 목록 확인
                        dir_files = os.listdir(attachments_dir)
                        found = False
                        
                        # 파일명에서 (Bytes) 부분을 제거한 파일 찾기
                        base_name = file_name.split(" (")[0] if " (" in file_name else file_name
                        
                        # 디버그 출력
                        print(f"🔍 찾는 파일: {base_name}")
                        
                        for dir_file in dir_files:
                            # 특수문자 처리를 위해 정확한 파일명 비교
                            if base_name == dir_file or base_name in dir_file:
                                file_name = dir_file
                                file_path = os.path.join(attachments_dir, file_name)
                                print(f"✅ 파일 찾음: {file_name}")
                                found = True
                                break
                        
                        if not found:
                            print(f"⚠️ 파일을 찾을 수 없음: {file_path}")
                            continue
                    
                    ext = os.path.splitext(file_name)[-1].lower()
                    if ext == ".pdf":
                        text = extract_text_from_pdf(file_path)
                    elif ext == ".hwp":
                        text = extract_text_from_hwp(file_path)
                    else:
                        text = ""
                    post["attachments"].append({
                        "file_name": file_name,
                        "text": text
                    })
                except Exception as e:
                    print(f"❌ 파일 처리 중 오류: {e}")
    output.append(post)

# JSON 저장
with open("rag_input_sample.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print("✅ rag_input_sample.json 생성 완료")
