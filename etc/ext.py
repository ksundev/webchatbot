import fitz  # PyMuPDF
import os
import olefile

def extract_text_from_pdfs(pdf_dir="attachments"):
    extracted = {}
    for file in os.listdir(pdf_dir):
        if file.lower().endswith(".pdf"):
            path = os.path.join(pdf_dir, file)
            with fitz.open(path) as doc:
                text = ""
                for page in doc:
                    text += page.get_text()
                extracted[file] = text.strip()
    return extracted

def extract_text_from_hwp(filepath):
    try:
        if not olefile.isOleFile(filepath):
            return ""

        ole = olefile.OleFileIO(filepath)
        if not ole.exists("PrvText"):
            return ""

        with ole.openstream("PrvText") as stream:
            text = stream.read().decode("utf-16", errors="ignore")
            return text.strip()
    except Exception as e:
        print(f"❌ HWP 파싱 실패: {filepath} → {e}")
        return ""


hwp_dir = "attachments"
hwp_texts = {}

for file in os.listdir(hwp_dir):
    path = os.path.join(hwp_dir, file)
    if file.lower().endswith(".hwp"):
        hwp_texts[file] = extract_text_from_hwp(path)

pdf_texts = extract_text_from_pdfs(hwp_dir)


if __name__ == "__main__":
    hwp_dir = "attachments"
    hwp_texts = {}

    for file in os.listdir(hwp_dir):
        path = os.path.join(hwp_dir, file)
        if file.lower().endswith(".hwp"):
            hwp_texts[file] = extract_text_from_hwp(path)

    pdf_texts = extract_text_from_pdfs(hwp_dir)

    print("📄 PDF 추출 파일 수:", len(pdf_texts))
    print("📄 HWP 추출 파일 수:", len(hwp_texts))

    # 원한다면 JSON으로 저장
    import json
    with open("extracted_texts.json", "w", encoding="utf-8") as f:
        json.dump({**pdf_texts, **hwp_texts}, f, ensure_ascii=False, indent=2)