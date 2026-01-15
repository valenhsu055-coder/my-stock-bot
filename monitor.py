import os
import requests
import pandas as pd
from linebot import LineBotApi
from linebot.models import TextSendMessage
from datetime import datetime

# 設定環境變數
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('CHANNEL_ACCESS_TOKEN')
FINMIND_TOKEN = os.environ.get('FINMIND_TOKEN')
USER_ID = os.environ.get('LINE_USER_ID')
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)

# 監控清單 (你可以隨時修改這裡的代碼)
WATCH_LIST = ['2330', '2317', '2454'] 
LOG_FILE = "notified_log.txt"

def check_stock():
    # 讀取今日已通知清單
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            notified_today = f.read().splitlines()
    else:
        notified_today = []

    today_str = datetime.now().strftime("%Y-%m-%d")
    msg_list = []
    new_notified = []

    for stock_id in WATCH_LIST:
        # 如果這檔股票今天已經通知過了，直接跳過
        if f"{today_str}_{stock_id}" in notified_today:
            continue

        url = "https://api.finmindtrade.com/api/v4/data"
        parameter = {
            "dataset": "TaiwanStockPrice",
            "data_id": stock_id,
            "start_date": "2025-10-01", # 確保有足夠長度計算 60MA
            "token": FINMIND_TOKEN,
        }
        resp = requests.get(url, params=parameter)
        data = resp.json()
        
        if data['msg'] == 'success' and len(data['data']) > 60:
            df = pd.DataFrame(data['data'])
            df['MA60'] = df['close'].rolling(window=60).mean()
            
            yesterday_close = df.iloc[-2]['close']
            yesterday_ma60 = df.iloc[-2]['MA60']
            today_close = df.iloc[-1]['close']
            today_ma60 = df.iloc[-1]['MA60']
            
            # 判斷突破：昨天在線下，今天收盤在線上
            if yesterday_close <= yesterday_ma60 and today_close > today_ma60:
                msg_list.append(f"🚀 {stock_id} 今日首次突破 60MA！\n現價：{today_close}\n60MA：{today_ma60:.2f}")
                new_notified.append(f"{today_str}_{stock_id}")

    if msg_list:
        final_msg = "【突破通知】\n" + "\n---\n".join(msg_list)
        line_bot_api.push_message(USER_ID, TextSendMessage(text=final_msg))
        
        # 紀錄已通知狀態
        with open(LOG_FILE, "a") as f:
            for item in new_notified:
                f.write(item + "\n")
        return True
    return False

if __name__ == "__main__":
    check_stock()
