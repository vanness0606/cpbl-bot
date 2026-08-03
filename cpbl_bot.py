import requests
from bs4 import BeautifulSoup
import time
import json
import os
from datetime import datetime
from collections import defaultdict

# ========== 設定區 ==========
WEBHOOK_URL = "你的Discord_Webhook網址"        # ← 必填
CHECK_INTERVAL = 300                           # 每幾秒檢查一次
STATE_FILE = "cpbl_trans_state.json"

# 只通知這些球隊（留空 [] 就通知全部球隊）
WATCH_TEAMS = [
    "富邦悍將",
    #"統一7-ELEVEn獅",
    # "樂天桃猿",
    # "台鋼雄鷹",
    # "中信兄弟",
    # "味全龍",
]
# ============================

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

def get_transactions():
    """抓取目前球員異動資料"""
    url = "https://www.cpbl.com.tw/player/trans"
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")

    table = soup.find("table")
    if not table:
        return []

    rows = table.find_all("tr")[1:]
    data = []
    current_date = None

    for row in rows:
        cols = row.find_all("td")
        if not cols:
            continue

        if len(cols) >= 4:
            date = cols[0].get_text(strip=True)
            player = cols[1].get_text(strip=True)
            team = cols[2].get_text(strip=True)
            reason = cols[3].get_text(strip=True)
            current_date = date
        elif len(cols) == 3 and current_date:
            player = cols[0].get_text(strip=True)
            team = cols[1].get_text(strip=True)
            reason = cols[2].get_text(strip=True)
        else:
            continue

        key = f"{current_date}|{player}|{team}|{reason}"
        data.append({
            "key": key,
            "date": current_date,
            "player": player,
            "team": team,
            "reason": reason
        })

    return data

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_state(keys):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(list(keys), f, ensure_ascii=False)

def send_discord(new_items):
    if not new_items:
        return

    groups = defaultdict(list)
    for item in new_items:
        groups[item["date"]].append(item)

    embeds = []
    for date, items in groups.items():
        description = ""
        for i in items:
            description += f"**{i['player']}**（{i['team']}）→ {i['reason']}\n"

        embeds.append({
            "title": f"中職球員異動 - {date}",
            "description": description.strip(),
            "color": 0x1E90FF,
            "footer": {"text": "CPBL 球員異動監控"},
            "timestamp": datetime.utcnow().isoformat()
        })

    # 一次最多送 10 個 embed
    for i in range(0, len(embeds), 10):
        payload = {"embeds": embeds[i:i+10]}
        try:
            requests.post(WEBHOOK_URL, json=payload, timeout=10)
        except Exception as e:
            print(f"發送 Discord 失敗：{e}")

def main():
    print("=" * 50)
    print("CPBL 球員異動監控已啟動")
    if WATCH_TEAMS:
        print(f"只監控球隊：{', '.join(WATCH_TEAMS)}")
    else:
        print("監控全部球隊")
    print(f"檢查間隔：{CHECK_INTERVAL} 秒")
    print("=" * 50)

    known = load_state()

    while True:
        try:
            current = get_transactions()
            current_keys = {item["key"] for item in current}

            # 找出新的異動
            new_keys = current_keys - known
            if new_keys:
                new_items = [item for item in current if item["key"] in new_keys]

                # ===== 特定球隊過濾 =====
                if WATCH_TEAMS:
                    new_items = [
                        item for item in new_items
                        if any(team in item["team"] for team in WATCH_TEAMS)
                    ]
                # ========================

                if new_items:
                    new_items.sort(key=lambda x: x["date"], reverse=True)
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] 發現 {len(new_items)} 筆符合條件的新異動")
                    send_discord(new_items)
                else:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] 有新異動，但都不在監控球隊內")

                # 不管有沒有過濾，都要更新狀態，避免重複判斷
                known = current_keys
                save_state(known)
            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 沒有新異動")

        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 發生錯誤：{e}")

        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
