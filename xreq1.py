import requests
from bs4 import BeautifulSoup
import csv
import os
import time
import re
import pandas as pd
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
    file_name = re.sub(r'\s*\(\d+\s*Bytes\)', '', file_name)
    
    
    try:
        res = requests.get(file_url, headers=headers, allow_redirects=True)
        if res.status_code == 200 and len(res.content) > 1000:
            save_path = os.path.join(ATTACH_DIR, file_name)
            with open(save_path, "wb") as f:
                f.write(res.content)
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
        # CSV 파일에 저장할 때 특수문자 처리를 위해 텍스트 정리
        content = content_tag.get_text(separator="\n").strip()
        # 따옴표나 쉼표 등 CSV 파일에서 문제가 될 수 있는 문자 처리
        content = content.replace('"', '""')  # 큰따옴표 이스케이프
    except:
        content = "본문 없음"

    # ✅ 첨부파일
    attachments = []
    file_section = soup.select_one("td.tongboard_view[colspan='3']")
    if file_section:
        for link in file_section.find_all("a", href=True):
            file_url = BASE_URL + link["href"]
            file_name = link.text.strip()
                   # 괄호 안의 Bytes 정보 제거하고 확장자까지 포함된 파일명만 추출
             #match = re.match(r"(.+\.(pdf|hwp))\s*\(.*?\)", raw_file_name, re.IGNORECASE)
            #if match:
            #    file_name = match.group(1).strip()
            #else:
            #    file_name = raw_file_name.strip()  # 예외 상황 대비 백업
            file_name = re.sub(r'\s*\(\d+\s*Bytes\)', '', file_name)
            ext = os.path.splitext(file_name)[-1].lower()
            if ".hwp" in ext or ".pdf" in ext:
                download_file(file_url, file_name)
                attachments.append(f"{file_name} ({file_url})")
    else:
        print("첨부파일 없음")
    return {
        "title": title,
        "url": url,
        "content": content,
        "attachments": "; ".join(attachments)
    }

def save_to_csv(data, filename="복지용구_자료실.csv"):
    try:
        df = pd.DataFrame(data)
        df.to_csv(filename, index=False, encoding="utf-8-sig", quotechar='"', quoting=csv.QUOTE_ALL, escapechar='\\')
        print(f"📊 총 {len(data)}개 데이터가 {filename}에 저장되었습니다.")
    except Exception as e:
        print(f"CSV 저장 중 오류 발생: {e}")
        # 대안으로 JSON으로 저장
        import json
        with open(filename.replace('.csv', '.json'), 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"📊 총 {len(data)}개 데이터가 JSON 파일로 저장되었습니다.")
if __name__ == "__main__":
    all_data = []
    for page in range(21, 22):  # 1~21페이지
        board_ids = get_board_ids(page)
        for board_id in board_ids:
            post = parse_post(board_id)
            all_data.append(post)
            print(f"✅ 저장 대상: {post['title']}")
            time.sleep(0.5)

    save_to_csv(all_data)
    print("\n📁 모든 게시물을 CSV 파일로 저장 완료!")
