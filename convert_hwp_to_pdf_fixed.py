import os
import sys
import time
import fitz  # PyMuPDF
from pathlib import Path
import shutil

# 경로 설정
ATTACH_DIR = "attachments"
HWP_DIR = os.path.join(ATTACH_DIR, "hwp")
PDF_DIR = os.path.join(ATTACH_DIR, "pdf")
PDF_TEXT_DIR = os.path.join(PDF_DIR, "text")
PDF_IMAGE_DIR = os.path.join(PDF_DIR, "image")

# 폴더 생성
os.makedirs(PDF_DIR, exist_ok=True)
os.makedirs(PDF_TEXT_DIR, exist_ok=True)
os.makedirs(PDF_IMAGE_DIR, exist_ok=True)

def ensure_unique_path(dirpath: str, filename: str) -> str:
    """중복 파일명 처리를 위한 함수"""
    base, ext = os.path.splitext(filename)
    candidate = os.path.join(dirpath, filename)
    i = 1
    while os.path.exists(candidate):
        candidate = os.path.join(dirpath, f"{base}_{i}{ext}")
        i += 1
    return candidate

def pdf_has_any_image(pdf_path: str) -> bool:
    """PDF 파일에 이미지가 포함되어 있는지 확인"""
    try:
        with fitz.open(pdf_path) as doc:
            for i, page in enumerate(doc, start=1):
                imgs = page.get_images(full=True)
                # 디버깅
                print(f"   - {os.path.basename(pdf_path)} p{i}: images={len(imgs)}")
                if imgs:
                    return True
    except Exception as e:
        print(f"⚠️ PDF 열기 실패: {os.path.basename(pdf_path)} → {e}")
    return False

def split_pdf_by_content():
    """PDF 파일을 이미지 포함 여부에 따라 분류"""
    moved = {"image": 0, "text": 0}
    for fname in os.listdir(PDF_DIR):
        src = os.path.join(PDF_DIR, fname)
        if not os.path.isfile(src):
            continue
        if not fname.lower().endswith(".pdf"):
            continue

        # 이미지 여부 판정
        has_img = pdf_has_any_image(src)
        dst_dir = PDF_IMAGE_DIR if has_img else PDF_TEXT_DIR
        dst = ensure_unique_path(dst_dir, fname)
        shutil.move(src, dst)
        moved["image" if has_img else "text"] += 1
        print(f"📦 이동: {fname}  →  {os.path.relpath(dst)}")

    print(f"\n✅ 정리 완료: image {moved['image']}개, text {moved['text']}개")

def convert_hwp_to_pdf_method1():
    """HWP 파일을 PDF로 변환 (방법 1: 직접 변환)"""
    print("\n🔄 HWP → PDF 변환 시작 (방법 1)...")
    
    try:
        import win32com.client as win32
    except Exception:
        print("⚠️ pywin32가 설치되어 있지 않습니다. HWP 변환을 건너뜁니다.")
        print("   설치 방법: pip install pywin32")
        return
    
    SRC = Path(HWP_DIR)
    DST = Path(PDF_DIR)
    
    if not SRC.exists():
        print(f"⚠️ HWP 폴더가 없습니다: {SRC}")
        return
    
    # PDF 폴더 생성
    DST.mkdir(parents=True, exist_ok=True)
    
    # HWP 파일 목록
    hwp_files = list(SRC.rglob("*.hwp"))
    if not hwp_files:
        print("📂 변환할 HWP 파일이 없습니다.")
        return
    
    print(f"📋 변환 대상 HWP 파일: {len(hwp_files)}개")
    
    try:
        print("🔧 Hancom HWP COM 객체 실행...")
        hwp = win32.gencache.EnsureDispatch("HWPFrame.HwpObject")
        
        # 보안 설정 해제 시도
        try:
            hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")
        except Exception:
            pass
        
        try:
            hwp.XHwpWindows.Item(0).Visible = True
        except:
            pass
    except Exception as e:
        print(f"❌ HWP COM 객체 실행 실패: {e}")
        return
    
    total, ok, skip, fail = 0, 0, 0, 0
    
    for src in hwp_files:
        total += 1
        # SRC 기준 상대경로 유지 → DST에 같은 폴더 구조로 저장
        rel = src.relative_to(SRC)
        out = DST / rel.with_suffix(".pdf")
        out.parent.mkdir(parents=True, exist_ok=True)
        
        # 이미 변환된 파일이 있는지 확인 (파일 크기도 체크)
        if out.exists():
            # 파일 크기가 0보다 큰지 확인 (정상적으로 변환된 파일인지)
            if out.stat().st_size > 0:
                print(f"⏭️  {src.name} (이미 변환됨, {out.stat().st_size:,} bytes)")
                skip += 1
                continue
            else:
                print(f"🔄 {out.name} 파일이 비어있어서 다시 변환합니다.")
                out.unlink()  # 빈 파일 삭제
        
        try:
            print(f"🔄 변환 중: {src.name}")
            
            # 절대 경로로 변환
            src_abs = str(src.resolve())
            out_abs = str(out.resolve())
            
            # 파일 열기
            hwp.Open(src_abs)
            
            # 다른 방식으로 PDF 저장 시도
            hwp.SaveAs(out_abs, "PDF")
            
            # 파일 확인
            if out.exists() and out.stat().st_size > 0:
                print(f"✅ 변환 완료: {src.name} → {out.name} ({out.stat().st_size:,} bytes)")
                ok += 1
            else:
                print(f"❌ 변환 실패: {src.name}")
                fail += 1
            
            hwp.Clear(1)  # 현재 문서 닫기
        except Exception as e:
            print(f"❌ 변환 오류 {src.name}: {e}")
            fail += 1
    
    # HWP 종료
    try:
        hwp.Quit()
    except Exception:
        pass
    
    print(f"\n📊 변환 요약: 총 {total}개 / 변환 {ok}개 / 건너뜀 {skip}개 / 실패 {fail}개")
    
    # 결과 확인
    pdf_files = list(DST.rglob("*.pdf"))
    print(f"📂 PDF 폴더 내 총 파일 수: {len(pdf_files)}개")

def convert_hwp_to_pdf_method2():
    """HWP 파일을 PDF로 변환 (방법 2: 인쇄 방식)"""
    print("\n🔄 HWP → PDF 변환 시작 (방법 2)...")
    
    try:
        import win32com.client as win32
    except Exception:
        print("⚠️ pywin32가 설치되어 있지 않습니다. HWP 변환을 건너뜁니다.")
        print("   설치 방법: pip install pywin32")
        return
    
    SRC = Path(HWP_DIR)
    DST = Path(PDF_DIR)
    
    if not SRC.exists():
        print(f"⚠️ HWP 폴더가 없습니다: {SRC}")
        return
    
    # PDF 폴더 생성
    DST.mkdir(parents=True, exist_ok=True)
    
    # HWP 파일 목록
    hwp_files = list(SRC.rglob("*.hwp"))
    if not hwp_files:
        print("📂 변환할 HWP 파일이 없습니다.")
        return
    
    print(f"📋 변환 대상 HWP 파일: {len(hwp_files)}개")
    
    try:
        print("🔧 Hancom HWP COM 객체 실행...")
        hwp = win32.gencache.EnsureDispatch("HWPFrame.HwpObject")
        
        # 보안 설정 해제 시도
        try:
            hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")
        except Exception:
            pass
        
        try:
            hwp.XHwpWindows.Item(0).Visible = False  # 백그라운드 실행
        except:
            pass
    except Exception as e:
        print(f"❌ HWP COM 객체 실행 실패: {e}")
        return
    
    total, ok, skip, fail = 0, 0, 0, 0
    
    for src in hwp_files:
        total += 1
        # SRC 기준 상대경로 유지 → DST에 같은 폴더 구조로 저장
        rel = src.relative_to(SRC)
        out = DST / rel.with_suffix(".pdf")
        out.parent.mkdir(parents=True, exist_ok=True)
        
        # 이미 변환된 파일이 있는지 확인 (파일 크기도 체크)
        if out.exists():
            # 파일 크기가 0보다 큰지 확인 (정상적으로 변환된 파일인지)
            if out.stat().st_size > 0:
                print(f"⏭️  {src.name} (이미 변환됨, {out.stat().st_size:,} bytes)")
                skip += 1
                continue
            else:
                print(f"🔄 {out.name} 파일이 비어있어서 다시 변환합니다.")
                out.unlink()  # 빈 파일 삭제
        
        try:
            print(f"🔄 변환 중: {src.name}")
            
            # 절대 경로로 변환
            src_abs = str(src.resolve())
            out_abs = str(out.resolve())
            
            # 파일 열기
            hwp.Open(src_abs)
            
            # 인쇄 방식으로 PDF 저장
            hwp.HAction.GetDefault("FileSaveAsPdf", hwp.HParameterSet.HFileOpenSave.HSet)
            hwp.HParameterSet.HFileOpenSave.filename = out_abs
            hwp.HParameterSet.HFileOpenSave.Format = "PDF"
            hwp.HAction.Execute("FileSaveAsPdf", hwp.HParameterSet.HFileOpenSave.HSet)
            
            # 파일 확인
            if out.exists() and out.stat().st_size > 0:
                print(f"✅ 변환 완료: {src.name} → {out.name} ({out.stat().st_size:,} bytes)")
                ok += 1
            else:
                print(f"❌ 변환 실패: {src.name}")
                fail += 1
            
            hwp.Clear(1)  # 현재 문서 닫기
        except Exception as e:
            print(f"❌ 변환 오류 {src.name}: {e}")
            fail += 1
    
    # HWP 종료
    try:
        hwp.Quit()
    except Exception:
        pass
    
    print(f"\n📊 변환 요약: 총 {total}개 / 변환 {ok}개 / 건너뜀 {skip}개 / 실패 {fail}개")
    
    # 결과 확인
    pdf_files = list(DST.rglob("*.pdf"))
    print(f"📂 PDF 폴더 내 총 파일 수: {len(pdf_files)}개")

if __name__ == "__main__":
    # 두 가지 방법 모두 시도
    print("방법 1과 방법 2를 순차적으로 시도합니다...")
    
    # 방법 1: 직접 변환
    convert_hwp_to_pdf_method1()
    
    # 방법 2: 인쇄 방식
    convert_hwp_to_pdf_method2()
    
    # PDF 파일 분류 (이미지/텍스트)
    split_pdf_by_content()




