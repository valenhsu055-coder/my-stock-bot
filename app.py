import os
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import requests
import pandas as pd

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.environ.get('CHANNEL_SECRET')
FINMIND_TOKEN = os.environ.get('FINMIND_TOKEN')

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# 新增：把股名轉成代碼的函數
def name_to_id(stock_name):
    url = "https://api.finmindtrade.com/api/v4/data"
    parameter = {
        "dataset": "TaiwanStockInfo",
        "token": FINMIND_TOKEN,
    }
    resp = requests.get(url, params=parameter)
    data = resp.json()
    if data['msg'] == 'success':
        df = pd.DataFrame(data['data'])
        # 在「stock_name」這一欄找尋符合的名稱
        match = df[df['stock_name'] == stock_name]
        if not match.empty:
            return match.iloc[0]['stock_id']
    return None

def get_stock_analysis(stock_id):
    url = "https://api.finmindtrade.com/api/v4/data"
    parameter = {
        "dataset": "TaiwanStockPrice",
        "data_id": stock_id,
        "start_date": "2025-12-01",
        "token": FINMIND_TOKEN,
    }
    resp = requests.get(url, params=parameter)
    data = resp.json()
    if data['msg'] != 'success' or not data['data']:
        return f"❌ 找不到股票代碼 {stock_id}"
    df = pd.DataFrame(data['data'])
    df['MA5'] = df['close'].rolling(window=5).mean()
    df['MA20'] = df['close'].rolling(window=20).mean()
    latest = df.iloc[-1]
    price, ma5, ma20 = latest['close'], latest['MA5'], latest['MA20']
    status = "🔥 強勢" if price > ma5 > ma20 else "⚖️ 穩健" if price > ma20 else "❄️ 偏弱"
    return f"【{stock_id} 分析】\n現價: {price}\nMA5: {ma5:.2f}\nMA20: {ma20:.2f}\n診斷: {status}"

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_msg = event.message.text.strip()
    
    # 邏輯判斷：如果是數字就直接查；如果是文字就先轉代碼
    if user_msg.isdigit():
        stock_id = user_msg
    else:
        stock_id = name_to_id(user_msg)
    
    if stock_id:
        result = get_stock_analysis(stock_id)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=result))
    else:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"🤔 找不到「{user_msg}」，請輸入正確名稱或4位代碼"))

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
