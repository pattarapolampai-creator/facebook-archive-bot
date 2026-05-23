import os
from fastapi import FastAPI, Request

from linebot.v3 import WebhookHandler
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage
)

from linebot.v3.webhooks import MessageEvent, TextMessageContent

import google.generativeai as genai

# =========================
# ENV VARIABLES
# =========================

LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# =========================
# GEMINI SETUP
# =========================

genai.configure(api_key=GEMINI_API_KEY)

model = genai.GenerativeModel("gemini-2.0-flash")

# =========================
# LINE SETUP
# =========================

configuration = Configuration(
    access_token=LINE_CHANNEL_ACCESS_TOKEN
)

handler = WebhookHandler(LINE_CHANNEL_SECRET)

# =========================
# FASTAPI
# =========================

app = FastAPI()

@app.get("/")
def home():
    return {"message": "Facebook Archive Bot is running"}

@app.post("/webhook")
async def webhook(request: Request):

    signature = request.headers.get("X-Line-Signature")

    body = await request.body()
    body_text = body.decode()

    handler.handle(body_text, signature)

    return "OK"

# =========================
# MESSAGE EVENT
# =========================

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):

    user_text = event.message.text

    prompt = f"""
You are an AI assistant.

Analyze this content carefully.

Return in this format:

📌 Topic:
(short topic)

💡 Summary:
(short summary)

✍️ Rewrite:
(clean rewritten version)

Content:
{user_text}
"""

    response = model.generate_content(prompt)

    ai_reply = response.text

    with ApiClient(configuration) as api_client:

        line_bot_api = MessagingApi(api_client)

        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[
                    TextMessage(text=ai_reply)
                ]
            )
        )