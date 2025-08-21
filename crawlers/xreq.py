import requests
from bs4 import BeautifulSoup
import csv
import os
import time

BASE_URL = "https://www.longtermcare.or.kr"
LIST_URL = BASE_URL + "/npbs/cms/board/board/Board.jsp"
ATTACH_DIR = "attachments"
os.makedirs(ATTACH_DIR, exist_ok=True)

HEADERS = {"User-Agent": "Mozilla/5.0"}

def get_board_ids(page):
    params = {
        "act": "LIST",
        "communityKey": "B0022",
        "pageNum": page,
        "pageSize": 10
    }
    res = requests.get(LIST_URL, params=params, headers=HEADERS)
    soup = BeautifulSoup(res.text, "html.parser")
    board_ids = []
    for tag in soup.select("a[href*='boardId=']"):
        href = tag.get("href")
        if "boardId=" in href:
            board_id = href.split("boardId=")[-1].split("&")[0]
            board_ids.append(board_id)
    return list(set(board_ids))

def download_file(file_url, file_name):
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://www.longtermcare.or.kr"
    }
    
    # 파일 크기 정보 제거 (예: "파일명.pdf (400384 Bytes)")
    import re
    if "(" in file_name and "Bytes)" in file_name:
        file_name = re.sub(r'\s*\(\d+\s*Bytes\)', '', file_name).strip()
    
    try:
        res = requests.get(file_url, headers=headers, allow_redirects=True)
        if res.status_code == 200 and len(res.content) > 1000:
            save_path = os.path.join(ATTACH_DIR, file_name)
            with open(save_path, "wb") as f:
                f.write(res.content)
            # 바이트 정보가 제거된 파일명으로 출력
            print(f"📥 다운로드 성공: {file_name}")
            return save_path
        else:
            print(f"⚠️ 다운로드 실패: {file_name} → {res.status_code}")
            return None
    except Exception as e:
        print(f"❌ 에러 발생: {file_name} → {e}")
        return None



def parse_post(board_id):
    url = f"https://www.longtermcare.or.kr/npbs/cms/board/board/Board.jsp?communityKey=B0022&boardId={board_id}&act=VIEW"
    res = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(res.text, "html.parser")

    # ✅ 제목
    try:
        title = soup.select_one("div.tbl_tit_wrap span.tbl_tit").text.strip()
    except:
        title = "제목 없음"

    # ✅ 본문
    try:
        content_tag = soup.select_one("td#BOARD_CONTENT")
        content = content_tag.get_text(separator="\n").strip()
    except:
        content = "본문 없음"

    # ✅ 첨부파일
    attachments = []
    file_section = soup.select_one("td.tongboard_view[colspan='3']")
    if file_section:
        for link in file_section.find_all("a", href=True):
            file_url = BASE_URL + link["href"]
            file_name = link.text.strip()
            ext = os.path.splitext(file_name)[-1].lower()
            if ".hwp" in ext or ".pdf" in ext:
                # 파일 다운로드 (파일명에서 바이트 정보 제거됨)
                clean_path = download_file(file_url, file_name)
                
                # CSV에 저장할 때도 바이트 정보 제거
                clean_name = file_name
                if "(" in clean_name and "Bytes)" in clean_name:
                    clean_name = re.sub(r'\s*\(\d+\s*Bytes\)', '', clean_name).strip()
                
                attachments.append(f"{clean_name} ({file_url})")
    else:
        print("첨부파일 없음")
    return {
        "title": title,
        "url": url,
        "content": content,
        "attachments": "; ".join(attachments)
    }

def save_to_csv(data, filename="복지용구_자료실.csv"):
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["title", "url", "content", "attachments"])
        writer.writeheader()
        for row in data:
            writer.writerow(row)

if __name__ == "__main__":
    all_data = []
    for page in range(1, 22):  # 1~21페이지
        board_ids = get_board_ids(page)
        for board_id in board_ids:
            post = parse_post(board_id)
            all_data.append(post)
            print(f"✅ 저장 대상: {post['title']}")
            time.sleep(0.5)

    save_to_csv(all_data)
    print("\n📁 모든 게시물을 CSV 파일로 저장 완료!")