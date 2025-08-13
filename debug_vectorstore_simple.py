#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os

# 1. JSON 파일 확인
print("📋 noin3_data.json 로드 테스트:")
with open('noin3_data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
    content = data[0]['content']
    
print(f"✅ JSON 로드 성공 - 전체 글자수: {len(content)}")

# 전동휠체어 관련 키워드 검색
keywords = ["전동휠체어", "급여 조건", "MMSE", "근력검사", "평지 100m"]
for keyword in keywords:
    if keyword in content:
        print(f"✅ '{keyword}' 발견됨")
    else:
        print(f"❌ '{keyword}' 없음")

# 2. 벡터스토어 파일 확인
print(f"\n🗂️ 벡터스토어 파일 상태:")
vectorstore_files = ['vectorstore/index.faiss', 'vectorstore/index.pkl']
for file in vectorstore_files:
    if os.path.exists(file):
        size = os.path.getsize(file)
        print(f"✅ {file} 존재 - 크기: {size:,} bytes")
    else:
        print(f"❌ {file} 없음")

# 3. 앱에서 실제 검색 테스트
try:
    from app import init_vectorstore
    print(f"\n🔍 벡터스토어 검색 테스트:")
    vectorstore = init_vectorstore()
    
    question = "전동휠체어 급여 조건"
    docs = vectorstore.similarity_search(question, k=5)
    
    print(f"📋 '{question}' 검색결과 ({len(docs)}개):")
    for i, doc in enumerate(docs, 1):
        source = doc.metadata.get('source', 'Unknown')
        content_preview = doc.page_content[:200].replace('\n', ' ')
        print(f"{i}. 출처: {source}")
        print(f"   내용: {content_preview}...")
        print()
        
except Exception as e:
    print(f"❌ 벡터스토어 테스트 실패: {e}")

