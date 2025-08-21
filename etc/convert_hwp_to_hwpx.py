# convert_hwp_to_hwpx.py
import sys
import os
from pathlib import Path

SRC = Path("attachments/hwp")   # 원본 HWP 폴더
DST = Path("attachments/hwpx")  # 출력 HWPX 폴더

def main():
    try:
        import win32com.client as win32
    except Exception:
        print("[ERROR] pywin32가 설치되어 있지 않습니다. pip install pywin32")
        sys.exit(1)

    if not SRC.exists():
        print(f"[ERROR] 원본 폴더가 없습니다: {SRC.resolve()}")
        sys.exit(1)
    
    # 폴더가 없으면 생성
    if not DST.exists():
        print(f"[INFO] 출력 폴더 생성: {DST.resolve()}")
    DST.mkdir(parents=True, exist_ok=True)

    print("[INFO] Hancom HWP COM 객체 실행...")
    hwp = win32.gencache.EnsureDispatch("HWPFrame.HwpObject")

    # 일부 환경에서 외부 저장 경로 보안 모듈 필요
    try:
        hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")
    except Exception:
        pass

    # 자동화 보안 설정 해제 시도
    try:
        hwp.XHwpWindows.Item(0).Visible = True
    except:
        pass

    files = list(SRC.rglob("*.hwp"))
    if not files:
        print("[INFO] 변환할 .hwp 파일이 없습니다.")
        return

    # 기존 hwpx 파일 목록 확인
    existing_hwpx = set()
    for hwpx_file in DST.rglob("*.hwpx"):
        hwp_name = hwpx_file.stem + ".hwp"
        existing_hwpx.add(hwp_name)
    
    print(f"[INFO] 기존 변환된 파일: {len(existing_hwpx)}개")
    print(f"[INFO] 변환 대상 HWP 파일: {len(files)}개")

    total, ok, skip, fail = 0, 0, 0, 0
    for src in files:
        total += 1
        # SRC 기준 상대경로 유지 → DST에 같은 폴더 구조로 저장
        rel = src.relative_to(SRC)
        out = DST / rel.with_suffix(".hwpx")
        out.parent.mkdir(parents=True, exist_ok=True)

        # 이미 변환된 파일이 있는지 확인 (파일 크기도 체크)
        if out.exists():
            # 파일 크기가 0보다 큰지 확인 (정상적으로 변환된 파일인지)
            if out.stat().st_size > 0:
                print(f"[SKIP] {src.name} -> {out.relative_to(DST)} (이미 존재, {out.stat().st_size} bytes)")
                skip += 1
                continue
            else:
                print(f"[WARN] {out.name} 파일이 비어있어서 다시 변환합니다.")
                out.unlink()  # 빈 파일 삭제

        try:
            print(f"[CONVERT] {src} -> {out}")
            
            # 절대 경로로 변환
            src_abs = src.resolve()
            out_abs = out.resolve()
            
            # 파일 열기
            hwp.Open(str(src_abs))
            
            # 디버깅 정보
            print(f"[DEBUG] 문서 열림: {hwp.XHwpDocuments.Count} 문서")
            
            # 직접 다른 이름으로 저장 메뉴 사용
            hwp.SaveAs(str(out_abs), "HWPX")
            
            # 파일 확인
            if out.exists():
                print(f"[SUCCESS] 파일 저장됨: {out.stat().st_size} bytes")
                ok += 1
            else:
                print(f"[WARNING] 파일이 저장되지 않음: {out}")
                fail += 1
                
            hwp.Clear(1)  # 현재 문서 닫기
        except Exception as e:
            print(f"[FAIL] {src.name}: {e}")
            fail += 1

    try:
        hwp.Quit()
    except Exception:
        pass

    print(f"[SUMMARY] total={total}, converted={ok}, skipped={skip}, failed={fail}")
    
    # 결과 확인
    hwpx_files = list(DST.rglob("*.hwpx"))
    print(f"[CHECK] HWPX 폴더 내 파일 수: {len(hwpx_files)}")
    if hwpx_files:
        print(f"[CHECK] 첫 번째 HWPX 파일: {hwpx_files[0]}")

if __name__ == "__main__":
    main()