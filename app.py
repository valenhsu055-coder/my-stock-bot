import os
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import yfinance as yf
import pandas as pd
from openai import OpenAI

app = Flask(__name__)

# LINE 金鑰
LINE_CHANNEL_ACCESS_TOKEN = "Ey3boIZIsQfoUy2xzPs3vpj3vF76X/7mZRIzIJFES+C8B5L9uuGfpuK6Yvub1yW7wx5ZruiK1KXsLk3wPe1pkeKRrbx+UQe+Gw2vkwyQC0pPASu2koBaDhrs/UfmKn/GA/zFvrGkp2SHCrZMCGnslQdB04t89/1O/w1cDnyilFU="
LINE_CHANNEL_SECRET = "64b3bbb5f0fb6e94de8e02665087570c"

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# 初始化 OpenAI 客戶端
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

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
    
    name_to_code = {
        "瑞儀": "6176.TW", "美律": "2439.TW", "華新科": "2492.TW",
        "台積電": "2330.TW", "鴻海": "2317.TW", "聯發科": "2454.TW",
        "長榮": "2603.TW", "聯電": "2303.TW", "廣達": "2382.TW",
        "晶采": "8049.TW", "鈊象": "3293.TW", "國巨": "2327.TW",
    }
    
    if user_message in name_to_code:
        ticker_symbol = name_to_code[user_message]
        display_name = user_message
    elif user_message.isdigit():
        ticker_symbol = user_message + ".TW"
        display_name = user_message
    else:
        ticker_symbol = user_message.upper()
        display_name = user_message
    
    try:
        stock = yf.Ticker(ticker_symbol)
        # 抓取較長時間以便計算 20 日均線 (MA20)
        df = stock.history(period="6mo")
        
        if not df.empty:
            current_price = round(df['Close'].iloc[-1], 2)
            
            # 取最近 3 個月資料計算高低點與成交量
            df_3mo = df.tail(60)
            recent_high = round(df_3mo['High'].max(), 2)
            recent_low = round(df_3mo['Low'].min(), 2)
            
            support = round(recent_low * 1.01, 2)
            resistance = round(recent_high * 0.99, 2)
            
            # 計算技術指標：20日均線 (MA20) 與 5日均量
            df['MA20'] = df['Close'].rolling(window=20).mean()
            ma20_val = round(df['MA20'].iloc[-1], 2)
            
            df['Vol5'] = df['Volume'].rolling(window=5).mean()
            current_vol = df['Volume'].iloc[-1]
            vol5_val = df['Vol5'].iloc[-1]
            
            # 趨勢與量能狀態判斷
            trend_status = "多頭排列 (站上月線)" if current_price >= ma20_val else "空頭或盤整 (跌破月線)"
            vol_status = "近期量能放大 (帶量)" if current_vol >= vol5_val else "近期量能萎縮 (量縮)"
            
            # 呼叫 OpenAI 產生更具實戰價值的分析
            prompt = (
                f"你是一位專業的台股操盤手與量化交易專家。請根據以下數據，撰寫一段精簡、專業的技術分析短評（控制在 150 字以內）：\n"
                f"• 標的：{display_name} ({ticker_symbol})\n"
                f"• 現價：{current_price} 元\n"
                f"• 20日均線(月線)：{ma20_val} 元（狀態：{trend_status}）\n"
                f"• 3個月支撐區：{support} 元\n"
                f"• 3個月壓力區：{resistance} 元\n"
                f"• 量能狀況：{vol_status}\n"
                f"請針對勝率與進出場防守點給予專業建議。"
            )
            
            ai_response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=250,
                temperature=0.7
            )
            ai_comment = ai_response.choices[0].message.content.strip()
            
            reply_text = (
                f"📊 【{display_name} 智能實戰分析】\n"
                f"----------------------------------\n"
                f"• 現價參考：{current_price} 元\n"
                f"• 月線(MA20)：{ma20_val} 元 ({trend_status})\n"
                f"• 支撐地板：約 {support} 元\n"
                f"• 壓力天花板：約 {resistance} 元\n"
                f"• 量能狀態：{vol_status}\n\n"
                f"🤖 **AI 實戰操盤觀點**：\n{ai_comment}\n\n"
                f"🎯 【高勝率紀律規劃】\n"
                f"• 低接守則：限「站上月線」時於 {support}~{support+3} 元低接。\n"
                f"• 突破守則：限「帶量」突破 {resistance} 元方可追價。\n"
                f"• 嚴格停損：若有效跌破支撐或月線即退場。\n"
                f"----------------------------------\n"
                f"⚠️ 註：投資有賺有賠，嚴控資金水位。"
            )
        else:
            reply_text = f"抱歉，找不到「{user_message}」的資料，請確認代號或名稱是否正確。"
    except Exception as e:
        reply_text = f"查詢時發生錯誤或 AI 連線異常，請稍後再試。"

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )

if __name__ == "__main__":
    app.run(port=5000)
