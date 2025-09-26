# 引用所有需要的工具
from flask import Flask, request, abort
import random
import googlemaps # ★ 新增：引用 Google Maps 工具
import time # ★★★ 確保這裡有 import time ★★★
import os # ★ 記得在最上面加上這行

# (底下 linebot 的 import 維持不變)
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import (MessageEvent, PostbackEvent, TextMessageContent, LocationMessageContent)
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi, ReplyMessageRequest, PushMessageRequest,
    TextMessage, ImageMessage, FlexMessage, QuickReply, QuickReplyItem, LocationAction
)

app = Flask(__name__)

# ...
# =========【金鑰區 - 部署版】=========
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET')
GOOGLE_MAPS_API_KEY = os.environ.get('GOOGLE_MAPS_API_KEY')
# ==================================

# 設定 LINE Bot
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
# ★ 新增：設定 Google Maps Client
gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)

# ★★★【全新增設：Bot 的短期記憶體】★★★
# 建立一個空的字典，用來存放每個使用者的狀態
# 格式會是 { '使用者ID': '選擇的料理類型' }
user_states = {}


@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

# 處理文字訊息 (維持不變)
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    # ... (程式碼完全不變，省略)
    flex_message_json = {
      "type": "flex", "altText": "吃飯選擇障礙輪盤Go",
      "contents": {
        "type": "bubble", "hero": {"type": "image", "url": "https://i.imgur.com/G3Qc0HK.jpeg", "size": "full", "aspectRatio": "20:20", "aspectMode": "cover"},
        "body": {"type": "box", "layout": "vertical", "contents": [{"type": "text", "text": "來看看吃什麼？", "weight": "bold", "size": "xl", "align": "center"}, {"type": "text", "text": "讓命運來決定吧！點擊下方按鈕，看看你今天跟什麼美食有緣！", "wrap": True, "align": "center", "margin": "md"}]},
        "footer": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": [{"type": "button", "style": "primary", "height": "sm", "color": "#FF6B6B", "action": {"type": "postback", "label": "吃飯選擇障礙輪盤Go！🎲", "data": "action=start_food_roulette"}}]}
      }
    }
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(reply_token=event.reply_token, messages=[FlexMessage.from_dict(flex_message_json)])
        )

# ★★★【這是修改重點：用這整段新的函式，取代掉舊的 handle_postback】★★★
@handler.add(PostbackEvent)
def handle_postback(event):
    postback_data = event.postback.data
    
    if postback_data == 'action=start_food_roulette':
        
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            user_id = event.source.user_id # 先取得使用者的 ID

            # 1. 傳送倒數訊息 "3"
            line_bot_api.push_message(PushMessageRequest(
                to=user_id,
                messages=[TextMessage(text="3")]
            ))
            
            # 2. 暫停一秒
            time.sleep(1)

            # 3. 傳送倒數訊息 "2"
            line_bot_api.push_message(PushMessageRequest(
                to=user_id,
                messages=[TextMessage(text="2")]
            ))

            # 4. 暫停一秒
            time.sleep(1)

            # 5. 傳送倒數訊息 "1"
            line_bot_api.push_message(PushMessageRequest(
                to=user_id,
                messages=[TextMessage(text="1")]
            ))

            # 6. 暫停一秒
            time.sleep(1)

            # 7. 進行抽獎並傳送最終結果
            cuisine_options = ["中式料理 🍜", "日式料理 🍣", "義式料理 🍕", "火鍋 🍲", "美式漢堡 🍔", "韓式炸雞 🍗", "健康餐盒 🥗", "什麼都好，隨便！"]
            chosen_cuisine = random.choice(cuisine_options)

            # 將使用者的選擇，「寫入」到我們的記憶體 user_states 裡
            user_states[user_id] = chosen_cuisine
            
            result_message = TextMessage(
                text=f"就是你了！\n\n【{chosen_cuisine}】\n\n現在就傳送你的位置，讓我幫你尋找附近厲害的店家吧！",
                quick_reply=QuickReply(items=[QuickReplyItem(action=LocationAction(label="傳送我的位置 📍"))])
            )

            line_bot_api.push_message(PushMessageRequest(
                to=user_id,
                messages=[result_message]
            ))

# ★★★【程式碼修改重點：處理位置訊息的邏輯】★★★
@handler.add(MessageEvent, message=LocationMessageContent)
def handle_location_message(event):
    latitude = event.message.latitude
    longitude = event.message.longitude
    user_id = event.source.user_id # 取得當前使用者的 ID

    # 從記憶體中，讀取這位使用者之前選擇的料理類型
    # .get() 的好處是，如果找不到這位使用者的紀錄，會使用預設值 '餐廳 美食'，避免程式出錯
    search_keyword = user_states.get(user_id, '餐廳 美食')
    
    # 如果使用者選的是「隨便」，那我們還是搜尋通用關鍵字
    if search_keyword == '什麼都好，隨便！':
        search_keyword = '餐廳 美食'
    
    try:
        # 使用 Google Maps API 進行附近地點搜尋
        # （小提示）一個更進階的 Bot 會記得你之前選的料理類型(例如日式料理)，並把它當作 keyword。
        # 但我們先從簡單的開始，固定搜尋「餐廳」或「美食」。
        places_result = gmaps.places_nearby(
            location=(latitude, longitude),
            radius=1000,  # 搜尋半徑，單位為公尺 (這裡是 1 公里)
            keyword=search_keyword,
            language='zh-TW',  # 回傳結果的語言
            open_now=False # 是否只搜尋正在營業的店家
        )
        
        # 整理搜尋結果
        reply_text = f"為您搜尋「{search_keyword}」的結果如下：\n\n"
        count = 0
        for place in places_result.get('results', []):
            if count < 5: # 只取前 5 筆資料
                name = place.get('name')
                rating = place.get('rating', '無評分') # 如果沒有評分，顯示'無評分'
                user_ratings_total = place.get('user_ratings_total', 0)
                
                # 建立 Google Maps 連結
                place_id = place.get('place_id')
                map_url = f"https://www.google.com/maps/place/?q=place_id:{place_id}"

                reply_text += f"📍 {name}\n⭐ 評分：{rating} ({user_ratings_total} 則評論)\n🗺️ 地圖：{map_url}\n\n"
                count += 1
            else:
                break
        
        if count == 0:
            reply_text = "抱歉，您附近 1 公里內找不到符合的餐廳耶..."

    except Exception as e:
        # 如果 API 呼叫失敗，回傳錯誤訊息
        app.logger.error(f"Google Maps API Error: {e}")
        reply_text = "哎呀！地圖好像壞掉了，請稍後再試一次。"

    # 回傳最後整理好的文字訊息
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text)]
            )
        )

if __name__ == "__main__":
    app.run(port=5000)