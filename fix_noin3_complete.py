#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import fitz # PyMuPDF
import hashlib
from datetime import datetime

def extract_full_pdf_text(path):
    """PDF의 모든 페이지 텍스트 추출"""
    try:
        doc = fitz.open(path)
        full_text = ""
        for page_num, page in enumerate(doc, start=1):
            text = page.get_text()
            full_text += f"\n=== 페이지 {page_num} ===\n{text}"
        return full_text
    except Exception as e:
        return f"❌ PDF 오류: {e}"

# 기존 JSON 파일 로드
def load_existing_data(file_path):
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    return []

# 백업 및 업데이트
def update_noin3_data():
    json_file = "rag_input_sample.json"
    pdf_file = "noin3.pdf"
    
    print("🔄 noin3.pdf 전체 페이지 다시 처리 시작...")
    
    # 기존 데이터 로드
    data = load_existing_data(json_file)
    print(f"📄 기존 데이터: {len(data)}개 항목")
    
    # noin3 항목 찾기
    noin3_index = -1
    for i, item in enumerate(data):
        if item.get("title") == "noin3":
            noin3_index = i
            break
    
    if noin3_index == -1:
        print("❌ noin3 항목을 찾을 수 없습니다.")
        return
    
    # PDF 전체 텍스트 추출
    if os.path.exists(pdf_file):
        print("📖 noin3.pdf 전체 페이지 텍스트 추출 중...")
        full_text = extract_full_pdf_text(pdf_file)
        
        if full_text and "❌ PDF 오류" not in full_text:
            # 기존 noin3 항목 업데이트
            data[noin3_index]["content"] = full_text
            print("✅ noin3 데이터 업데이트 완료 (전체 23페이지)")
            
            # 백업
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = f"{json_file}.backup_{timestamp}"
            with open(backup_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"💾 백업 완료: {backup_file}")
            
            # 업데이트된 파일 저장
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            print(f"✅ {json_file} 업데이트 완료!")
            print("\n🔄 다음 단계:")
            print("1. 관리자 페이지 → 📚 데이터 관리")
            print("2. 🔄 벡터스토어 재구축 버튼 클릭")
            print("3. 재구축 완료 후 '전동휠체어 대여 조건' 다시 질문")
            
        else:
            print(f"❌ PDF 텍스트 추출 실패: {full_text}")
    else:
        print(f"❌ {pdf_file} 파일을 찾을 수 없습니다.")

if __name__ == "__main__":
    update_noin3_data()



