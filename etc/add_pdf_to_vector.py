import fitz  # PyMuPDF
import json
import os

def extract_pdf_text(pdf_path):
    """PDF에서 텍스트 추출"""
    try:
        doc = fitz.open(pdf_path)
        full_text = ""
        
        for page_num, page in enumerate(doc, start=1):
            text = page.get_text()
            full_text += f"\n=== 페이지 {page_num} ===\n{text}"
        
        doc.close()
        return full_text
    except Exception as e:
        return f"❌ PDF 텍스트 추출 오류: {e}"

def create_json_for_pdf(pdf_path, title, url=""):
    """PDF를 JSON 형식으로 변환"""
    text = extract_pdf_text(pdf_path)
    
    # JSON 데이터 구조 생성
    data = [{
        "title": title,
        "url": url,
        "content": text[:1000] if text else "",  # 첫 1000자를 content로
        "attachments": [{
            "file_name": os.path.basename(pdf_path),
            "text": text
        }]
    }]
    
    return data

# noin3.pdf 처리
if __name__ == "__main__":
    pdf_file = "noin3.pdf"
    
    if os.path.exists(pdf_file):
        # PDF 텍스트 추출
        json_data = create_json_for_pdf(
            pdf_file, 
            title="noin3 문서",  # 원하는 제목으로 변경
            url=""  # 관련 URL이 있다면 입력
        )
        
        # JSON 파일로 저장
        output_file = "noin3_data.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ {output_file} 생성 완료!")
        print("📝 다음 단계:")
        print("1. 관리자 페이지 → 📚 데이터 관리")
        print("2. JSON 파일로 데이터 추가 섹션")
        print(f"3. 파일명: {output_file}")
        print("4. 📁 JSON 파일 추가 버튼 클릭")
    else:
        print(f"❌ {pdf_file} 파일을 찾을 수 없습니다.")



