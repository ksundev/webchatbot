import os
import json
import fitz # PyMuPDF
import hashlib
from datetime import datetime

# PDF 텍스트 추출 함수 (good1.py에서 가져옴)
def extract_text_from_pdf(path):
    try:
        doc = fitz.open(path)
        full_text = ""
        for page_num, page in enumerate(doc, start=1):
            text = page.get_text()
            full_text += f"\n=== 페이지 {page_num} ===\n{text}"
        return full_text
    except Exception as e:
        return f"❌ PDF 오류: {e}"

# 기존 JSON 파일 로드 및 해시 생성 함수 (good_all.py에서 가져옴)
def load_existing_data(file_path):
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # 각 항목의 해시를 계산하여 중복 체크에 사용
        hashes = {hashlib.md5(json.dumps(item, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest() for item in data}
        return data, hashes
    return [], set()

# JSON 파일 경로
output_json_file = "rag_input_sample.json"
pdf_file_to_add = "noin3.pdf"

print(f"🚀 {pdf_file_to_add} 파일을 {output_json_file}에 통합 시작")

# 기존 데이터 로드
existing_data, existing_hashes = load_existing_data(output_json_file)
print(f"📄 기존 데이터 로드: {len(existing_data)}개 항목")

# PDF 파일 처리
if os.path.exists(pdf_file_to_add):
    pdf_text = extract_text_from_pdf(pdf_file_to_add)
    if pdf_text:
        new_item = {
            "title": os.path.splitext(pdf_file_to_add)[0], # 파일명을 제목으로
            "url": "", # URL은 비워둠
            "content": pdf_text,
            "attachments": []
        }
        # 새 항목의 해시 계산
        new_item_hash = hashlib.md5(json.dumps(new_item, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()

        if new_item_hash not in existing_hashes:
            existing_data.append(new_item)
            print(f"✅ {pdf_file_to_add} 내용 추가 완료 (중복 아님)")
        else:
            print(f"⚠️ {pdf_file_to_add}는 이미 존재하여 추가하지 않습니다.")
    else:
        print(f"❌ {pdf_file_to_add}에서 텍스트를 추출할 수 없습니다.")
else:
    print(f"❌ {pdf_file_to_add} 파일을 찾을 수 없습니다.")

# 업데이트된 데이터를 JSON 파일에 저장 (기존 파일 백업 후)
if os.path.exists(output_json_file):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"{output_json_file}.backup_{timestamp}"
    os.rename(output_json_file, backup_file)
    print(f"💾 기존 {output_json_file} 백업: {backup_file}")

with open(output_json_file, "w", encoding="utf-8") as f:
    json.dump(existing_data, f, ensure_ascii=False, indent=2)

print(f"✅ {output_json_file} 업데이트 완료. 총 {len(existing_data)}개 항목.")
print("\n--- 다음 단계 ---")
print("이제 관리자 페이지에서 '🔄 벡터스토어 재구축' 버튼을 클릭하여 변경사항을 적용하세요.")
print("📍 http://192.168.0.20:5000/admin/logs → 📚 데이터 관리 → 🔄 벡터스토어 재구축")