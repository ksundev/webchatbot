import json
import os
import sys
from pathlib import Path

def split_json_file(input_file, output_prefix, items_per_file=5):
    """
    JSON 파일을 여러 작은 파일로 분할합니다.
    
    Args:
        input_file (str): 분할할 JSON 파일 경로
        output_prefix (str): 출력 파일의 접두사
        items_per_file (int): 각 파일당 항목 수
    """
    # 입력 파일 읽기
    print(f"📂 {input_file} 파일 읽는 중...")
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 데이터 크기 확인
    total_items = len(data)
    print(f"📊 총 {total_items}개 항목 발견")
    
    # 각 항목의 문자 수 계산
    char_counts = [len(str(item)) for item in data]
    total_chars = sum(char_counts)
    print(f"📊 총 문자 수: {total_chars:,}")
    
    # 파일 수 계산
    num_files = (total_items + items_per_file - 1) // items_per_file
    print(f"📄 {num_files}개 파일로 분할 예정 (파일당 {items_per_file}개 항목)")
    
    # 출력 디렉토리 생성
    output_dir = os.path.dirname(output_prefix)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # 데이터 분할 및 저장
    for i in range(0, total_items, items_per_file):
        batch = data[i:i+items_per_file]
        batch_num = i // items_per_file + 1
        
        # 배치의 문자 수 계산
        batch_chars = sum(len(str(item)) for item in batch)
        
        output_file = f"{output_prefix}_{batch_num}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(batch, f, ensure_ascii=False, indent=2)
        
        print(f"✅ {output_file} 저장 완료 ({len(batch)}개 항목, {batch_chars:,} 문자)")
    
    print(f"\n🎉 분할 완료! {num_files}개 파일로 분할되었습니다.")

def split_json_by_tokens(input_file, output_prefix, max_tokens_per_file=200000):
    """
    JSON 파일을 토큰 수 기준으로 여러 작은 파일로 분할합니다.
    
    Args:
        input_file (str): 분할할 JSON 파일 경로
        output_prefix (str): 출력 파일의 접두사
        max_tokens_per_file (int): 각 파일당 최대 토큰 수 (문자 수의 약 1/4)
    """
    # 입력 파일 읽기
    print(f"📂 {input_file} 파일 읽는 중...")
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 데이터 크기 확인
    total_items = len(data)
    print(f"📊 총 {total_items}개 항목 발견")
    
    # 출력 디렉토리 생성
    output_dir = os.path.dirname(output_prefix)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # 토큰 수 기준으로 데이터 분할
    current_batch = []
    current_tokens = 0
    batch_num = 1
    
    for item in data:
        # 각 항목의 문자 수 계산 (토큰 수는 문자 수의 약 1/4)
        item_chars = len(str(item))
        item_tokens = item_chars // 4
        
        # 현재 배치에 항목을 추가하면 토큰 제한을 초과하는지 확인
        if current_tokens + item_tokens > max_tokens_per_file and current_batch:
            # 현재 배치 저장
            output_file = f"{output_prefix}_{batch_num}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(current_batch, f, ensure_ascii=False, indent=2)
            
            print(f"✅ {output_file} 저장 완료 ({len(current_batch)}개 항목, 약 {current_tokens:,} 토큰)")
            
            # 새 배치 시작
            current_batch = [item]
            current_tokens = item_tokens
            batch_num += 1
        else:
            # 현재 배치에 항목 추가
            current_batch.append(item)
            current_tokens += item_tokens
    
    # 마지막 배치 저장
    if current_batch:
        output_file = f"{output_prefix}_{batch_num}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(current_batch, f, ensure_ascii=False, indent=2)
        
        print(f"✅ {output_file} 저장 완료 ({len(current_batch)}개 항목, 약 {current_tokens:,} 토큰)")
    
    print(f"\n🎉 분할 완료! {batch_num}개 파일로 분할되었습니다.")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("사용법: python split_json_data.py <입력_파일> <출력_접두사> [항목당_최대_토큰수]")
        print("예시: python split_json_data.py rag_input_sample.json ./split/data")
        print("예시: python split_json_data.py rag_input_sample.json ./split/data 200000")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_prefix = sys.argv[2]
    
    if len(sys.argv) >= 4:
        max_tokens = int(sys.argv[3])
        split_json_by_tokens(input_file, output_prefix, max_tokens)
    else:
        # 기본값으로 토큰 기준 분할 사용
        split_json_by_tokens(input_file, output_prefix)






