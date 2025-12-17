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

CUISINE_OPTIONS = ["酒吧", "居酒屋", "熱炒", "便利商店", "餐酒館"]
DRINKING_GAME_OPTIONS = {
    "喝一杯":"", 
    "喝半杯":"", 
    "喝一口":"", 
    "和右邊的人，一起喝一口":"",
    "和左邊的人，一起喝一口":"",
    "和對面的人，一起喝一口":"",
    "現場所有人，喝一口":"", 
    "現場所有男生，喝一口":"", 
    "現場所有女生，喝一口":"",
    "PASS！安全下莊，換下一個人轉":"",  
    "跟右邊的人猜拳，輸的喝":"", 
    "跟左邊的人猜拳，贏的喝":"", 
    "禁忌詞":"玩法：選一個詞，接下來每個人都不能講，有講到就要喝", 
    "數字炸彈":"玩法：其中一人在心中想一個數字（例如1到100之間），其他人要猜數字，需要提示大還小，猜到就要喝", 
    "三六九":"從3~9之間許一個數字，順時針從1開始數，數到該數字的倍數要拍手，如果做錯就要喝", 
    "二實一謊":"說出關於自己的三件事，兩個真的，一個假的，大家要猜，有人猜錯就要喝，大家都猜對的話自己要喝", 
    "007":"第一位跟第二位被指到的要說0，第三位要說砰並指出手槍，被指的人要雙手投降，太慢或舉錯都要喝", 
    "你喝":"喊123，跟右邊的人一起，同時指向一個人，如果指到同一個，那個人就要喝",
    "竹筍竹筍蹦蹦出":"大家依序喊1、2、3依此類推，同時喊得跟最後喊得要喝，最後的要喝一大杯", 
    "真心話大冒險":"選擇真心話或大冒險，選擇執行任務或喝", 
    "黑白猜":"先猜拳，然後比上下左右，比到一樣的話，該局猜拳輸的喝"
}

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
        bot_name = "吃吃喝喝小輪盤"
        base_text = f"想喝是嗎?\n找 {bot_name} 就對了"
        try:
            profile = line_bot_api.get_profile(user_id)
            nickname = profile.display_name
            final_welcome_text = f"{nickname} {base_text}"
        except Exception as e:
            app.logger.error(f"Could not get profile for user {user_id}: {e}")
            final_welcome_text = base_text

        message1 = TextMessage(text=final_welcome_text)
        message2_text = "想喝酒尋歡卻沒有想法?\n請點擊 來個有料的\n想喝酒壯膽但場面還太乾?\n請點擊 來點好玩的\n有時候伺服器會睡下去，請稍等1~2分鐘\n\"重新對話請隨意輸入文字\""
        
        # 更新快速回覆按鈕，加入查看清單的選項
        quick_reply_buttons = QuickReply(
            items=[
                QuickReplyItem(action=MessageAction(label="來個有料的", text="來個有料的")),
                QuickReplyItem(action=MessageAction(label="來點好玩的", text="來點好玩的")),
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
            QuickReplyItem(action=MessageAction(label="來個有料的", text="來個有料的")),
            QuickReplyItem(action=MessageAction(label="來點好玩的", text="來點好玩的")),
            QuickReplyItem(action=MessageAction(label="查看吃飯清單", text="查看吃飯清單")),
            QuickReplyItem(action=MessageAction(label="查看喝酒遊戲清單", text="查看喝酒遊戲清單"))
        ]
    )

    reply_message = None

    if text == '來個有料的':
        flex_message_json = {
            "type": "flex", 
            "altText": "找喝酒地點",
            "contents": { 
                "type": "bubble", 
                
                "hero": {
                    "type": "image", 
                    "url": "https://i.imgur.com/hpVYYdq.jpeg", 
                    "size": "full", 
                    "aspectRatio": "20:20", 
                    "aspectMode": "cover"
                }, 
                
                "body": {
                    "type": "box", 
                    "layout": "vertical", 
                    "contents": [
                        {
                            "type": "text", 
                            "text": "來看看有什麼好去處？", 
                            "weight": "bold", 
                            "size": "xl", 
                            "align": "center"
                        }, 
                        {
                            "type": "text", 
                            "text": "讓命運來決定吧！點擊下方按鈕，看看你今天跟什麼店有緣！", 
                            "wrap": True, 
                            "align": "center", 
                            "margin": "md"
                        }
                    ]
                }, 
                
                "footer": {
                    "type": "box", 
                    "layout": "vertical", 
                    "spacing": "sm", 
                    "contents": [
                        {
                            "type": "button", 
                            "style": "primary", 
                            "height": "sm", 
                            "color": "#FF6B6B", 
                            "action": {
                                "type": "postback", 
                                "label": "來個有料的的地方吧Go！🎲", 
                                "data": "action=start_food_roulette"
                            }
                        }
                    ]
                }
            }
        }
        reply_message = FlexMessage.from_dict(flex_message_json)
    elif text == '來點好玩的':
        flex_message_json_drink = {
            "type": "flex", 
            "altText": "找喝酒遊戲",
            "contents": {
                "type": "bubble", 
                
                "hero": {
                    "type": "image", 
                    "url": "https://i.imgur.com/uT9VH9a.gif", 
                    "size": "full", 
                    "aspectRatio": "20:20", 
                    "aspectMode": "cover", 
                    "animated": True  # 這是動態圖片 (GIF) 的設置
                }, 
                
                "body": {
                    "type": "box", 
                    "layout": "vertical", 
                    "contents": [
                        {
                            "type": "text", 
                            "text": "喝吧，不醉不歸!", 
                            "weight": "bold", 
                            "size": "xl", 
                            "align": "center"
                        }, 
                        {
                            "type": "text", 
                            "text": "想躲酒?那你得碰碰運氣了!", 
                            "wrap": True, 
                            "align": "center", 
                            "margin": "md"
                        }
                    ]
                }, 
                
                "footer": {
                    "type": "box", 
                    "layout": "vertical", 
                    "spacing": "sm", 
                    "contents": [
                        {
                            "type": "button", 
                            "style": "primary", 
                            "height": "sm", 
                            "color": "#A16DF9", 
                            "action": {
                                "type": "postback", 
                                "label": "來點好玩的遊戲吧Go！🍻", 
                                "data": "action=start_drinking_game"
                            }
                        }
                    ]
                }
            }
        }
        reply_message = FlexMessage.from_dict(flex_message_json_drink)
    
    elif text == '查看吃飯清單':
        list_text = "目前美食輪盤的選項有：\n\n" + "\n".join([f"🍴 {item}" for item in CUISINE_OPTIONS])
        # 在回覆清單的同時，附上快速回覆按鈕
        reply_message = TextMessage(
            text=list_text, 
            quick_reply=quick_reply_buttons
        )

    elif text == '查看喝酒遊戲清單':
        list_text = "目前喝酒輪盤的選項有：\n\n" + "\n".join([f"🎲 {item}" for item in DRINKING_GAME_OPTIONS])
        # 在回覆清單的同時，附上快速回覆按鈕
        reply_message = TextMessage(
            text=list_text, 
            quick_reply=quick_reply_buttons
        )
        
    else:
        # 「聽不懂」的回覆，也使用共用的按鈕物件
        reply_message = TextMessage(
            text="抱歉，我聽不懂你的指令耶。\n你可以從下方的按鈕開始玩喔！",
            quick_reply=quick_reply_buttons
        )

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token, 
                messages=[reply_message]
            )
        )

@handler.add(PostbackEvent)
def handle_postback(event):
    postback_data = event.postback.data

    # 使用reply_message
    reply_token = event.reply_token
    
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        user_id = event.source.user_id

        if postback_data == 'action=start_food_roulette':

            # 直接使用全域的 CUISINE_OPTIONS
            chosen_cuisine = random.choice(CUISINE_OPTIONS)
            user_states[user_id] = chosen_cuisine

            # 使用push_message會耗掉資源，所以要改用reply_message
            # 倒數計時
            # line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text="3...")]))
            # time.sleep(1)
            # line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text="2...")]))
            # time.sleep(1)
            # line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text="1...")]))
            # time.sleep(1)
            # result_message = TextMessage(
            #     text=f"就是你了！\n\n【{chosen_cuisine}】\n\n現在就傳送你的位置，讓我幫你尋找附近厲害的店家吧！",
            #     quick_reply=QuickReply(items=[QuickReplyItem(action=LocationAction(label="傳送我的位置 📍"))])
            # )
            # line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[result_message]))
            
            # 使用reply_message
            messages_to_send = [
                TextMessage(
                    text=f"就是你了！\n\n【{chosen_cuisine}】\n\n現在就傳送你的位置，讓我幫你尋找附近厲害的店家吧！",
                    quick_reply=QuickReply(items=[QuickReplyItem(action=LocationAction(label="傳送我的位置 📍"))])
                )
            ]

            # 使用 ReplyMessageRequest 一次性回覆
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=messages_to_send
                )
            )
        
        elif postback_data == 'action=start_drinking_game':
            # 直接使用全域的 DRINKING_GAME_OPTIONS
            chosen_action = random.choice(DRINKING_GAME_OPTIONS.keys())
            if DRINKING_GAME_OPTIONS[chosen_action] == "":
                result_message = TextMessage(text=f"輪盤的指令是...\n\n 👉 {chosen_action} 👈")
            else:
                result_message = TextMessage(text=f"輪盤的指令是...\n\n 👉 {chosen_action} 👈 \n{DRINKING_GAME_OPTIONS[chosen_action]}")

            # 使用push_message會耗掉資源，所以要改用reply_message
            # 倒數計時
            # line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text="3...")]))
            # time.sleep(1)
            # line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text="2...")]))
            # time.sleep(1)
            # line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text="1...")]))
            # time.sleep(1)
            # line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[result_message]))
            # time.sleep(3) 

            flex_message_json_drink = {
                "type": "flex", 
                "altText": "再來一輪",
                "contents": {
                    "type": "bubble",     
                    "footer": {
                        "type": "box", 
                        "layout": "vertical", 
                        "spacing": "sm", 
                        "contents": [
                            {
                                "type": "box",
                                "layout": "vertical",
                                "margin": "none",
                                "contents": [
                                    {
                                        "type": "text", 
                                        "text": "再來一輪？Again？", 
                                        "weight": "bold", 
                                        "size": "md", 
                                        "align": "center",
                                        "margin": "none"
                                    },
                                    {
                                        "type": "text", 
                                        "text": "繼續挑戰下一個幸運兒！\nWho is the next lucky guy?", 
                                        "wrap": True, 
                                        "align": "center", 
                                        "size": "sm",
                                        "color": "#aaaaaa",
                                        "margin": "sm"
                                    }
                                ]
                            },
                            {
                                "type": "button", 
                                "style": "primary", 
                                "height": "sm", 
                                "color": "#A16DF9", 
                                "action": {
                                    "type": "postback", 
                                    "label": "啟動喝酒輪盤！Go Go！🍻", 
                                    "data": "action=start_drinking_game"
                                }
                            }
                        ]
                    }
                }
            }
            
            play_again_message = FlexMessage.from_dict(flex_message_json_drink)
            # 使用push_message會耗掉資源，所以要改用reply_message
            # line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[play_again_message]))

            # 使用reply_message
            messages_to_send = [
                result_message,
                play_again_message # FlexMessage 放在最後
            ]
            
            # 使用 ReplyMessageRequest 一次性回覆
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=messages_to_send
                )
            )

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
            if count < 10:
                name = place.get('name')
                rating = place.get('rating', '無評分')
                user_ratings_total = place.get('user_ratings_total', 0)
                place_id = place.get('place_id')
                map_url = f"https://www.google.com/maps/search/?api=1&query=Google&query_place_id={place_id}"
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
            ReplyMessageRequest(
                reply_token=event.reply_token, 
                messages=[TextMessage(text=reply_text)]
            )
        )

if __name__ == "__main__":
    app.run(port=5000)