import os
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import requests
import pandas as pd
from datetime import datetime

app = Flask(__name__)

# 環境變數
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.environ.get('CHANNEL_SECRET')
FINMIND_TOKEN = os.environ.get('FINMIND_TOKEN')

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

def name_to_id(stock_name):
    url = "https://api.finmindtrade.com/api/v4/data"
    parameter = {"dataset": "TaiwanStockInfo", "token": FINMIND_TOKEN}
    resp = requests.get(url, params=parameter)
    data = resp.json()
    if data['msg'] == 'success':
        df = pd.DataFrame(data['data'])
        match = df[df['stock_name'] == stock_name]
        if not match.empty:
            return match.iloc[0]['stock_id']
    return None

def get_yield_rate(stock_id):
    url = "https://api.finmindtrade.com/api/v4/data"
    # 抓取近 5 年配息
    parameter = {
        "dataset": "TaiwanStockDividend",
        "data_id": stock_id,
        "start_date": f"{datetime.now().year - 5}-01-01",
        "token": FINMIND_TOKEN,
    }
    resp = requests.get(url, params=parameter)
    data = resp.json()
    if data['msg'] == 'success' and data.get('data'):
        df = pd.DataFrame(data['data'])
        cash = df['CashDividend'] if 'CashDividend' in df.columns else 0
        stock = df['StockDividend'] if 'StockDividend' in df.columns else 0
        df['total'] = cash + stock
        return df['total'].sum() / 5
    return 0

def get_stock_analysis(stock_id):
    url = "https://api.finmindtrade.com/api/v4/data"
    parameter = {
        "dataset": "TaiwanStockPrice",
        "data_id": stock_id,
        "start_date": "2025-10-01", 
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
    price = latest['close']
    
    avg_div = get_yield_rate(stock_id)
    final_yield = (avg_div / price) * 100 if avg_div > 0 else 0
    
    status = "🔥 強勢" if price > latest['MA5'] > latest['MA20'] else "⚖️ 穩健" if price > latest['MA20'] else "❄️ 偏弱"
    yahoo_url = f"https://tw.stock.yahoo.com/quote/{stock_id}.TW/chart"
    
    return (f"【{stock_id} 分析】\n"
            f"現價: {price}\n"
            f"MA5: {latest['MA5']:.2f}\n"
            f"MA20: {latest['MA20']:.2f}\n"
            f"近5年平均殖利率: {final_yield:.2f}%\n"
            f"診斷: {status}\n\n"
            f"📈 查看 K 線圖：\n{yahoo_url}")

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_msg = event.message.text.strip()
    stock_id = user_msg if user_msg.isdigit() else name_to_id(user_msg)
    if stock_id:
        result_msg = get_stock_analysis(stock_id)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=result_msg))
    else:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"🤔 找不到「{user_msg}」"))

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
