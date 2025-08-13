#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HWP → HWPX 변환 상태 확인 스크립트
"""

from pathlib import Path

def check_conversion_status():
    hwp_folder = Path("attachments/hwp")
    hwpx_folder = Path("attachments/hwpx")
    
    print("📂 HWP → HWPX 변환 상태 확인")
    print("=" * 50)
    
    # HWP 파일 목록
    hwp_files = list(hwp_folder.rglob("*.hwp"))
    hwpx_files = list(hwpx_folder.rglob("*.hwpx"))
    
    print(f"📋 HWP 파일: {len(hwp_files)}개")
    print(f"📋 HWPX 파일: {len(hwpx_files)}개")
    print()
    
    # 변환 상태 체크
    converted = set()
    not_converted = []
    
    for hwp_file in hwp_files:
        hwp_name = hwp_file.name
        hwpx_name = hwp_file.stem + ".hwpx"
        hwpx_path = hwpx_folder / hwpx_name
        
        if hwpx_path.exists():
            size = hwpx_path.stat().st_size
            converted.add(hwp_name)
            print(f"✅ {hwp_name} → {hwpx_name} ({size:,} bytes)")
        else:
            not_converted.append(hwp_name)
            print(f"❌ {hwp_name} → 변환 필요")
    
    print("\n📊 요약:")
    print(f"✅ 변환 완료: {len(converted)}개")
    print(f"❌ 변환 필요: {len(not_converted)}개")
    
    if not_converted:
        print(f"\n🔄 변환이 필요한 파일들:")
        for filename in not_converted:
            print(f"  - {filename}")
    else:
        print(f"\n🎉 모든 파일이 변환되었습니다!")

if __name__ == "__main__":
    check_conversion_status()
