import os
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import requests
import pandas as pd
from datetime import datetime, timedelta

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

def get_stock_analysis(stock_id):
    url = "https://api.finmindtrade.com/api/v4/data"
    parameter = {
        "dataset": "TaiwanStockPrice",
        "data_id": stock_id,
        "start_date": (datetime.now() - timedelta(days=120)).strftime('%Y-%m-%d'), 
        "token": FINMIND_TOKEN,
    }
    resp = requests.get(url, params=parameter)
    data = resp.json()
    
    if data['msg'] != 'success' or not data['data']:
        return f"❌ 找不到股票代碼 {stock_id}"
    
    df = pd.DataFrame(data['data'])
    df['MA5'] = df['close'].rolling(window=5).mean()
    df['MA20'] = df['close'].rolling(window=20).mean()
    df['MA60'] = df['close'].rolling(window=60).mean()
    
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    price = latest['close']
    
    def get_arrow(curr, prev_val):
        return "⬆️" if curr > prev_val else "⬇️"

    ma5_arrow = get_arrow(latest['MA5'], prev['MA5'])
    ma20_arrow = get_arrow(latest['MA20'], prev['MA20'])
    ma60_arrow = get_arrow(latest['MA60'], prev['MA60'])
    
    # 診斷
    if price > latest['MA5'] > latest['MA20'] > latest['MA60']:
        status = "🚀 超級強勢 (多頭排列)"
    elif price > latest['MA20'] > latest['MA60']:
        status = "🔥 強勢波段"
    elif price > latest['MA60']:
        status = "⚖️ 中期穩健"
    else:
        status = "❄️ 走勢偏弱"
    
    # 生成 Yahoo 連結
    yahoo_base = f"https://tw.stock.yahoo.com/quote/{stock_id}.TW"
    
    # 建立近五年的年份提示
    this_year = datetime.now().year
    years_info = f"{this_year-1} | {this_year-2} | {this_year-3} | {this_year-4} | {this_year-5}"

    return (f"【{stock_id} 趨勢與殖利率分析】\n"
            f"💰 現價: {price}\n"
            f"📊 MA5:  {latest['MA5']:.2f} {ma5_arrow}\n"
            f"📉 MA20: {latest['MA20']:.2f} {ma20_arrow}\n"
            f"🧬 MA60: {latest['MA60']:.2f} {ma60_arrow}\n"
            f"🌡️ 診斷: {status}\n\n"
            f"📅 歷年殖利率表現 (近5年)：\n"
            f"({years_info})\n"
            f"👇 請點擊下方連結查看詳細配息表：\n"
            f"{yahoo_base}/dividend\n\n"
            f"📈 即時 K 線圖 (技術分析)：\n"
            f"{yahoo_base}/technical-analysis\n\n"
            f"🏢 營收財務狀況：\n"
            f"{yahoo_base}/revenue")

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Signature') or request.headers.get('X-Line-Signature')
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
