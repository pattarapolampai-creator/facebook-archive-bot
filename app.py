import os
import json

from fastapi import FastAPI, Request

from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage
)

import google.generativeai as genai

# =========================
# ENV
# =========================

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# =========================
# GEMINI
# =========================

genai.configure(api_key=GEMINI_API_KEY)

model = genai.GenerativeModel("gemini-2.0-flash")

# =========================
# LINE CONFIG
# =========================

configuration = Configuration(
    access_token=LINE_CHANNEL_ACCESS_TOKEN
)

# =========================
# FASTAPI
# =========================

app = FastAPI()

@app.get("/")
def home():
    return {"message": "Facebook Archive Bot is running"}

@app.post("/webhook")
async def webhook(request: Request):

    body = await request.json()

    print("Webhook received:")
    print(body)

    events = body.get("events", [])

    for event in events:

        if event["type"] == "message":

            user_text = event["message"]["text"]

            reply_token = event["replyToken"]

            prompt = f"""
Analyze this content.

Return:
1. Topic
2. Summary
3. Rewrite in cleaner style

Content:
{user_text}
"""

            response = model.generate_content(prompt)

            ai_reply = response.text

            with ApiClient(configuration) as api_client:

                line_bot_api = MessagingApi(api_client)

                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=reply_token,
                        messages=[
                            TextMessage(text=ai_reply)
                        ]
                    )
                )

    return {"status": "ok"}