import os
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import yfinance as yf
import pandas as pd

app = Flask(__name__)

# 請確認你的真實金鑰已經填在這裡
LINE_CHANNEL_ACCESS_TOKEN = "Ey3boIZIsQfoUy2xzPs3vpj3vF76X/7mZRIzIJFES+C8B5L9uuGfpuK6Yvub1yW7wx5ZruiK1KXsLk3wPe1pkeKRrbx+UQe+Gw2vkwyQC0pPASu2koBaDhrs/UfmKn/GA/zFvrGkp2SHCrZMCGnslQdB04t89/1O/w1cDnyilFU="
LINE_CHANNEL_SECRET = "64b3bbb5f0fb6e94de8e02665087570c"

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

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
    user_message = event.message.text.strip()
    
    # 支援查詢的股票清單與代號
    stock_mapping = {
        "瑞儀": "6176.TW", "6176": "6176.TW",
        "美律": "2439.TW", "2439": "2439.TW",
        "華新科": "2492.TW", "2492": "2492.TW"
    }
    
    ticker_symbol = stock_mapping.get(user_message)
    
    if ticker_symbol:
        stock = yf.Ticker(ticker_symbol)
        df = stock.history(period="3mo")
        
        if not df.empty:
            current_price = round(df['Close'].iloc[-1], 2)
            recent_high = round(df['High'].max(), 2)
            recent_low = round(df['Low'].min(), 2)
            
            support = round(recent_low * 1.01, 2)
            resistance = round(recent_high * 0.99, 2)
            
            reply_text = (
                f"📊 【{user_message} 智能技術分析報告】\n"
                f"----------------------------------\n"
                f"• 現價參考：{current_price} 元\n"
                f"• 近期支撐區 (地板)：約 {support} 元\n"
                f"• 近期壓力區 (天花板)：約 {resistance} 元\n\n"
                f"🎯 【建議進出場規劃】\n"
                f"1. 回測低接規劃 (防禦佔60%)：\n"
                f"   • 建議在 {support} ~ {support+3} 元附近分批低接。\n"
                f"   • 停損點：有效跌破 {round(support*0.97, 2)} 元。\n\n"
                f"2. 突破追價規劃 (進攻佔40%)：\n"
                f"   • 若帶量突破 {resistance} 元可順勢追價。\n"
                f"   • 停損點：突破後若 3 天內跌回 {resistance} 以下則退場。\n"
                f"----------------------------------\n"
                f"⚠️ 註：程式自動化計算，非絕對投資建議。"
            )
        else:
            reply_text = f"抱歉，無法取得 {user_message} 的即時數據。"
    else:
        reply_text = "請輸入正確的台股代號或名稱（例如：6176、瑞儀、2439、美律、2492、華新科）。"

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )

if __name__ == "__main__":
    app.run(port=5000)
