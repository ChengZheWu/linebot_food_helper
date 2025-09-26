from flask import Flask, request, abort
import random
import googlemaps
import time
import os

from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import (
    MessageEvent,
    PostbackEvent,
    FollowEvent,
    TextMessageContent,
    LocationMessageContent
)
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    PushMessageRequest,
    TextMessage,
    ImageMessage,
    FlexMessage,
    QuickReply,
    QuickReplyItem,
    LocationAction,
    Emoji,
    MessageAction
)

app = Flask(__name__)

# 金鑰區
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET')
GOOGLE_MAPS_API_KEY = os.environ.get('GOOGLE_MAPS_API_KEY')

# 設定區
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)
user_states = {}

CUISINE_OPTIONS = ["中式料理", "日式料理", "義式料理", "火鍋", "美式漢堡", "韓式炸雞", "健康餐盒", "隨便"]
DRINKING_GAME_OPTIONS = [
    "喝一杯", "喝半杯", "把這杯乾了！", "SHOT 一杯", "淺嚐一口", "再倒一杯放著",
    "左邊的人，喝一杯", "右邊的人，喝一杯", "對面的人，喝半杯", "左邊的人，SHOT 一杯", "和右邊的人，一起喝一杯",
    "左右護法 (左&右)，各喝一杯", "現場所有人，喝一杯！", "現場所有男生，喝半杯", "現場所有女生，喝半杯",
    "指定在場一個人喝一杯", "指定一個人，陪你喝一杯", "隨便找個人喝交杯酒", "PASS！安全下莊，換下一個人轉",
    "天使卡：獲得免死金牌一張", "猜拳卡：跟右邊的人猜拳，輸的喝一杯"
]

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

# health check 函式給部署用
@app.route("/health", methods=['GET'])
def health_check():
    return 'OK', 200

@handler.add(FollowEvent)
def handle_follow(event):
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        user_id = event.source.user_id
        bot_name = "你的吃飯小助理Andy"
        base_text = f"你好啊！\n找 {bot_name} 就對了"
        try:
            profile = line_bot_api.get_profile(user_id)
            nickname = profile.display_name
            final_welcome_text = f"{nickname} {base_text}"
        except Exception as e:
            app.logger.error(f"Could not get profile for user {user_id}: {e}")
            final_welcome_text = base_text

        message1 = TextMessage(text=final_welcome_text)
        message2_text = "請問是吃飯有選擇障礙還是要玩喝酒遊戲呢?\n想吃飯請打\"吃\"\n想玩喝酒遊戲請打\"喝\"\n也可以直接從下面選單選擇\n重新對話請隨意輸入文字"
        
        # 更新快速回覆按鈕，加入查看清單的選項
        quick_reply_buttons = QuickReply(
            items=[
                QuickReplyItem(action=MessageAction(label="想吃飯 🍚", text="吃")),
                QuickReplyItem(action=MessageAction(label="想玩喝酒遊戲 🍻", text="喝")),
                QuickReplyItem(action=MessageAction(label="查看吃飯清單", text="查看吃飯清單")),
                QuickReplyItem(action=MessageAction(label="查看喝酒遊戲清單", text="查看喝酒遊戲清單"))
            ]
        )
        message2 = TextMessage(text=message2_text, quick_reply=quick_reply_buttons)

        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[message1, message2]
            )
        )

# 處理指令
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    text = event.message.text
    
    # 將 QuickReply 按鈕的定義，統一放在函式開頭，方便共用
    quick_reply_buttons = QuickReply(
        items=[
            QuickReplyItem(action=MessageAction(label="想吃飯 🍚", text="吃")),
            QuickReplyItem(action=MessageAction(label="想玩喝酒遊戲 🍻", text="喝")),
            QuickReplyItem(action=MessageAction(label="查看吃飯清單", text="查看吃飯清單")),
            QuickReplyItem(action=MessageAction(label="查看喝酒遊戲清單", text="查看喝酒遊戲清單"))
        ]
    )

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        reply_message = None

        if text == '吃':
            flex_message_json = {
              "type": "flex", "altText": "吃飯選擇障礙輪盤Go",
              "contents": { "type": "bubble", "hero": {"type": "image", "url": "https://i.imgur.com/G3Qc0HK.jpeg", "size": "full", "aspectRatio": "20:20", "aspectMode": "cover"}, "body": {"type": "box", "layout": "vertical", "contents": [{"type": "text", "text": "來看看吃什麼？", "weight": "bold", "size": "xl", "align": "center"}, {"type": "text", "text": "讓命運來決定吧！點擊下方按鈕，看看你今天跟什麼美食有緣！", "wrap": True, "align": "center", "margin": "md"}]}, "footer": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": [{"type": "button", "style": "primary", "height": "sm", "color": "#FF6B6B", "action": {"type": "postback", "label": "吃飯選擇障礙輪盤Go！🎲", "data": "action=start_food_roulette"}}]}}}
            reply_message = FlexMessage.from_dict(flex_message_json)
        elif text == '喝':
            flex_message_json_drink = {
                "type": "flex", "altText": "啟動喝酒輪盤",
                "contents": {"type": "bubble", "hero": {"type": "image", "url": "https://i.imgur.com/uT9VH9a.gif", "size": "full", "aspectRatio": "20:20", "aspectMode": "cover", "animated": True}, "body": {"type": "box", "layout": "vertical", "contents": [{"type": "text", "text": "喝吧，不醉不歸!", "weight": "bold", "size": "xl", "align": "center"}, {"type": "text", "text": "讓命運來決定吧！點擊下方按鈕，看看你今天要喝多少！", "wrap": True, "align": "center", "margin": "md"}]}, "footer": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": [{"type": "button", "style": "primary", "height": "sm", "color": "#A16DF9", "action": {"type": "postback", "label": "啟動喝酒輪盤！🍻", "data": "action=start_drinking_game"}}]}}}
            reply_message = FlexMessage.from_dict(flex_message_json_drink)
        
        elif text == '查看吃飯清單':
            list_text = "目前美食輪盤的選項有：\n\n" + "\n".join([f"🍴 {item}" for item in CUISINE_OPTIONS])
            # 在回覆清單的同時，附上快速回覆按鈕
            reply_message = TextMessage(text=list_text, quick_reply=quick_reply_buttons)

        elif text == '查看喝酒遊戲清單':
            list_text = "目前喝酒輪盤的選項有：\n\n" + "\n".join([f"🎲 {item}" for item in DRINKING_GAME_OPTIONS])
            # 在回覆清單的同時，附上快速回覆按鈕
            reply_message = TextMessage(text=list_text, quick_reply=quick_reply_buttons)
            
        else:
            # 「聽不懂」的回覆，也使用共用的按鈕物件
            reply_message = TextMessage(
                text="抱歉，我聽不懂你的指令耶。\n你可以從下方的按鈕開始玩喔！",
                quick_reply=quick_reply_buttons
            )
        
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(reply_token=event.reply_token, messages=[reply_message])
        )

@handler.add(PostbackEvent)
def handle_postback(event):
    postback_data = event.postback.data
    
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        user_id = event.source.user_id

        if postback_data == 'action=start_food_roulette':
            # 倒數計時.
            line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text="3...")]))
            time.sleep(1)
            line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text="2...")]))
            time.sleep(1)
            line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text="1...")]))
            time.sleep(1)

            # 直接使用全域的 CUISINE_OPTIONS
            chosen_cuisine = random.choice(CUISINE_OPTIONS)
            user_states[user_id] = chosen_cuisine
            result_message = TextMessage(
                text=f"就是你了！\n\n【{chosen_cuisine}】\n\n現在就傳送你的位置，讓我幫你尋找附近厲害的店家吧！",
                quick_reply=QuickReply(items=[QuickReplyItem(action=LocationAction(label="傳送我的位置 📍"))])
            )
            line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[result_message]))
        
        elif postback_data == 'action=start_drinking_game':
            # 倒數計時
            line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text="3...")]))
            time.sleep(1)
            line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text="2...")]))
            time.sleep(1)
            line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text="1...")]))
            time.sleep(1)
            
            # 直接使用全域的 DRINKING_GAME_OPTIONS
            chosen_action = random.choice(DRINKING_GAME_OPTIONS)
            result_message = TextMessage(text=f"輪盤的指令是...\n\n 👉 {chosen_action} 👈")
            line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[result_message]))

            time.sleep(3) 

            flex_message_json_drink = {
                "type": "flex", "altText": "啟動喝酒輪盤",
                "contents": {"type": "bubble", "hero": {"type": "image", "url": "https://i.imgur.com/uT9VH9a.gif", "size": "full", "aspectRatio": "20:20", "aspectMode": "cover", "animated": True}, "body": {"type": "box", "layout": "vertical", "contents": [{"type": "text", "text": "再來一輪？", "weight": "bold", "size": "xl", "align": "center"}, {"type": "text", "text": "點擊按鈕，繼續挑戰下一個幸運兒！", "wrap": True, "align": "center", "margin": "md"}]}, "footer": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": [{"type": "button", "style": "primary", "height": "sm", "color": "#A16DF9", "action": {"type": "postback", "label": "啟動喝酒輪盤！🍻", "data": "action=start_drinking_game"}}]}}}
            
            play_again_message = FlexMessage.from_dict(flex_message_json_drink)
            line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[play_again_message]))

@handler.add(MessageEvent, message=LocationMessageContent)
def handle_location_message(event):
    latitude = event.message.latitude
    longitude = event.message.longitude
    user_id = event.source.user_id
    search_keyword = user_states.get(user_id, '餐廳 美食')
    if search_keyword == '隨便':
        search_keyword = '餐廳 美食'
    try:
        places_result = gmaps.places_nearby(location=(latitude, longitude), radius=1000, keyword=search_keyword, language='zh-TW', open_now=False)
        reply_text = f"為您搜尋「{search_keyword}」的結果如下：\n\n"
        count = 0
        for place in places_result.get('results', []):
            if count < 5:
                name = place.get('name')
                rating = place.get('rating', '無評分')
                user_ratings_total = place.get('user_ratings_total', 0)
                place_id = place.get('place_id')
                map_url = f"https://www.google.com/maps/place/?q=place_id:{place_id}"
                reply_text += f"📍 {name}\n⭐ 評分：{rating} ({user_ratings_total} 則評論)\n🗺️ 地圖：{map_url}\n\n"
                count += 1
            else:
                break
        if count == 0:
            reply_text = f"抱歉，您附近 1 公里內找不到符合「{search_keyword}」的餐廳耶..."
    except Exception as e:
        app.logger.error(f"Google Maps API Error: {e}")
        reply_text = "哎呀！地圖好像壞掉了，請稍後再試一次。"
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=reply_text)])
        )

if __name__ == "__main__":
    app.run(port=5000)