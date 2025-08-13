import os, re, json, zipfile, sys
from pathlib import Path
from typing import List, Dict, Any

CSV_PATH = Path("복지용구_자료실.csv")
ATTACH_ROOT = Path("attachments")
OUTPUT_JSON = Path("rag_input.json")

def _lazy_imports():
    mods = {}
    try:
        import pandas as pd
        mods["pd"] = pd
    except Exception:
        mods["pd"] = None
    try:
        import lxml.etree as ET
        mods["ET"] = ET
    except Exception:
        mods["ET"] = None
    return mods

MODS = _lazy_imports()

def norm_filename(name: str) -> str:
    name = (name or "").strip()
    name = re.sub(r"\s*\(\d+\s*Bytes\)\s*$", "", name).strip()
    return name

def find_file_anywhere(base_name: str) -> Path:
    """Exact name match under ATTACH_ROOT (case-insensitive), else stem match."""
    target_lc = base_name.lower()
    for p in ATTACH_ROOT.rglob("*"):
        if p.is_file() and p.name.lower() == target_lc:
            return p
    stem_target = Path(base_name).stem.replace(" ", "").lower()
    ext_target = Path(base_name).suffix.lower()
    for p in ATTACH_ROOT.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() != ext_target:
            continue
        stem_p = p.stem.replace(" ", "").lower()
        if stem_p == stem_target:
            return p
    return None

def prefer_hwpx_from_name(name: str) -> Path:
    """If name is .hwp and corresponding .hwpx exists anywhere, return it.
       Else, try to find the name as-is."""
    p = Path(name)
    if p.suffix.lower() == ".hwp":
        # Look for .hwpx with same stem
        target_hwpx = p.with_suffix(".hwpx").name
        found = find_file_anywhere(target_hwpx)
        if found:
            return found
    # otherwise resolve the original name
    return find_file_anywhere(name)

def extract_hwpx_text(path: Path) -> str:
    ET = MODS["ET"]
    if ET is None:
        return "[ERROR] lxml not installed"
    try:
        texts: List[str] = []
        with zipfile.ZipFile(str(path), "r") as zf:
            for name in zf.namelist():
                if not name.lower().startswith("word/"):
                    continue
                if not name.lower().endswith(".xml"):
                    continue
                try:
                    with zf.open(name) as f:
                        data = f.read()
                    root = ET.fromstring(data)
                    s = root.xpath("string()")  # gather visible text
                    if s and s.strip():
                        texts.append(str(s))
                except Exception as e:
                    texts.append(f"[XML ERROR in {name}: {e}]")
        if not texts:
            return "[INFO] No text found in HWPX (word/*.xml)."
        return "\n".join(texts)
    except Exception as e:
        return f"[ERROR] HWPX parse failed: {e}"

def extract_hwp_preview_text(path: Path) -> str:
    """Fallback minimal extractor: HWP preview text via olefile if available."""
    try:
        import olefile
    except Exception:
        return "[INFO] HWP preview requires 'olefile'. pip install olefile"
    try:
        ole = olefile.OleFileIO(str(path))
        if ole.exists("PrvText"):
            with ole.openstream("PrvText") as s:
                raw = s.read()
            for enc in ("utf-16", "cp949", "utf-8", "latin1"):
                try:
                    return raw.decode(enc, errors="ignore")
                except Exception:
                    continue
            return raw.decode("latin1", errors="ignore")
        return "[INFO] HWP preview text not found. Consider converting to HWPX for full text."
    except Exception as e:
        return f"[ERROR] HWP extract failed: {e}"

def extract_text_for_attachment(p: Path, original_name: str) -> str:
    suffix = p.suffix.lower()
    if suffix == ".hwpx":
        return extract_hwpx_text(p)
    if suffix == ".hwp":
        sib = prefer_hwpx_from_name(Path(original_name).with_suffix(".hwpx").name)
        if sib and sib.suffix.lower() == ".hwpx":
            return extract_hwpx_text(sib)
        return extract_hwp_preview_text(p)
    return f"[SKIPPED] Unsupported extension: {suffix}"

def build_rag_items(csv_path: Path) -> List[Dict[str, Any]]:
    pd = MODS["pd"]
    if pd is None:
        raise RuntimeError("pandas not installed. pip install pandas")
    df = pd.read_csv(csv_path, encoding="utf-8")
    colmap = {c.strip().lower(): c for c in df.columns}
    for k in ["title", "url", "content", "attachments"]:
        if k not in colmap:
            raise RuntimeError(f"CSV missing required column: {k}")

    out: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        title = str(row[colmap["title"]]) if not pd.isna(row[colmap["title"]]) else ""
        url = str(row[colmap["url"]]) if not pd.isna(row[colmap["url"]]) else ""
        content = str(row[colmap["content"]]) if not pd.isna(row[colmap["content"]]) else ""
        attachments_raw = str(row[colmap["attachments"]]) if not pd.isna(row[colmap["attachments"]]) else ""
        names = [norm_filename(x) for x in re.split(r"[;,]", attachments_raw) if norm_filename(x)]
        att_list = []
        for name in names:
            p = prefer_hwpx_from_name(name)
            if not p:
                att_list.append({"file_name": name, "text": f"[MISSING] {name} not found under {ATTACH_ROOT}"})
                continue
            text = extract_text_for_attachment(p, original_name=name)
            att_list.append({"file_name": p.name, "text": text})
        out.append({
            "title": title,
            "url": url,
            "content": content,
            "attachments": att_list
        })
    return out

def main():
    if not CSV_PATH.exists():
        print(f"[ERROR] CSV not found: {CSV_PATH}")
        sys.exit(1)
    if not ATTACH_ROOT.exists():
        print(f"[ERROR] Attachments root not found: {ATTACH_ROOT}")
        sys.exit(1)
    items = build_rag_items(CSV_PATH)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    print(f"[DONE] Saved: {OUTPUT_JSON.resolve()} (posts: {len(items)})")

if __name__ == "__main__":
    main()
