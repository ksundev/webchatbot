import fitz  # pymupdf
import os

pdf_dir = "attachments"

for file in os.listdir(pdf_dir):
    if file.lower().endswith(".pdf"):
        path = os.path.join(pdf_dir, file)
        print(f"\n🔍 {file}")
        try:
            doc = fitz.open(path)
            text = ""
            for page in doc:
                text += page.get_text()
            print("📄 추출 길이:", len(text))
        except Exception as e:
            print("❌ 오류:", e)