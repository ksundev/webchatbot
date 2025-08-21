import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import os
import io


# 📌 Tesseract 실행 파일 경로 지정 (윈도우 환경)
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

pdf_dir = "attachments"
output_texts = {}

for file in os.listdir(pdf_dir):
    if file.lower().endswith(".pdf"):
        path = os.path.join(pdf_dir, file)
        print(f"\n📂 처리 중: {file}")

        try:
            doc = fitz.open(path)
            full_text = ""

            for page_num, page in enumerate(doc, start=1):
                text = page.get_text()

                # 페이지에 텍스트가 적으면 OCR 수행
                if len(text.strip()) < 20:
                    print(f"🔍 페이지 {page_num}: 텍스트 적음 → OCR 실행")
                    pix = page.get_pixmap(dpi=300)
                    img = Image.open(io.BytesIO(pix.tobytes("png")))
                    ocr_text = pytesseract.image_to_string(img, lang="kor+eng")
                    text += "\n" + ocr_text

                full_text += f"\n=== 페이지 {page_num} ===\n{text}"

            output_texts[file] = full_text
            print(f"✅ 완료: {file}, 총 길이 {len(full_text)}")

        except Exception as e:
            print(f"❌ 오류({file}): {e}")

# 📌 JSON으로 저장
import json
with open("pdf_texts.json", "w", encoding="utf-8") as f:
    json.dump(output_texts, f, ensure_ascii=False, indent=2)

print("\n📄 전체 PDF 텍스트 저장 완료 → pdf_texts.json")
