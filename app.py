import os
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, ImageSendMessage
import requests
import pandas as pd
from datetime import datetime

app = Flask(__name__)

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

def get_yield_rate(stock_id, current_price):
    url = "https://api.finmindtrade.com/api/v4/data"
    parameter = {
        "dataset": "TaiwanStockDividend",
        "data_id": stock_id,
        "start_date": f"{datetime.now().year - 10}-01-01",
        "token": FINMIND_TOKEN,
    }
    resp = requests.get(url, params=parameter)
    data = resp.json()
    if data['msg'] == 'success' and data['data']:
        df = pd.DataFrame(data['data'])
        df['total_dividend'] = df['CashDividend'] + df['StockDividend']
        avg_dividend = df['total_dividend'].sum() / 10
        yield_rate = (avg_dividend / current_price) * 100
        return yield_rate
    return 0

def get_stock_analysis(stock_id):
    url = "https://api.finmindtrade.com/api/v4/data"
    parameter = {
        "dataset": "TaiwanStockPrice",
        "data_id": stock_id,
        "start_date": "2025-10-01", # 拉長一點確保 MA 計算
        "token": FINMIND_TOKEN,
    }
    resp = requests.get(url, params=parameter)
    data = resp.json()
    if data['msg'] != 'success' or not data['data']:
        return None, f"❌ 找不到股票代碼 {stock_id}"
    
    df = pd.DataFrame(data['data'])
    df['MA5'] = df['close'].rolling(window=5).mean()
    df['MA20'] = df['close'].rolling(window=20).mean()
    latest = df.iloc[-1]
    price = latest['close']
    avg_yield = get_yield_rate(stock_id, price)
    
    status = "🔥 強勢" if price > latest['MA5'] > latest['MA20'] else "⚖️ 穩健" if price > latest['MA20'] else "❄️ 偏弱"
    
    msg = (f"【{stock_id} 分析】\n"
           f"現價: {price}\n"
           f"MA5: {latest['MA5']:.2f}\n"
           f"MA20: {latest['MA20']:.2f}\n"
           f"近10年平均殖利率: {avg_yield:.2f}%\n"
           f"診斷: {status}")
    
    # 更換為 Yahoo Finance 的圖表連結，這對 LINE 較為穩定
    chart_url = f"https://chart.finance.yahoo.com/z?s={stock_id}.TW&t=6m&q=l&l=on&z=m&p=m5,m20"
    
    return chart_url, msg

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
    stock_id = user_msg if user_msg.isdigit() else name_to_id(user_msg)
    
    if stock_id:
        img_url, text_result = get_stock_analysis(stock_id)
        # LINE 規定 ImageSendMessage 的圖片網址必須是 https
        replies = [TextSendMessage(text=text_result)]
        if img_url:
            # 嘗試使用 Yahoo 圖表
            replies.append(ImageSendMessage(
                original_content_url=img_url, 
                preview_image_url=img_url
            ))
        line_bot_api.reply_message(event.reply_token, replies)
    else:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"🤔 找不到「{user_msg}」"))
