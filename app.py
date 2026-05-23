import logging
import os

import google.generativeai as genai
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhook import WebhookHandler
from linebot.v3.webhooks import MessageEvent, TextMessageContent

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("facebook-archive-bot")

LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")

app = FastAPI(title="Facebook Archive Bot")

configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN or None)
handler = WebhookHandler(LINE_CHANNEL_SECRET or "")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(GEMINI_MODEL)
else:
    model = None


@app.get("/")
def home():
    return {
        "message": "Facebook Archive Bot is running",
        "status": "ok",
        "model": GEMINI_MODEL,
    }


def build_prompt(user_text: str) -> str:
    return f"""You are a helpful assistant for a LINE chatbot named Facebook Archive.

Task:
- Analyze the input text
- Return exactly 3 sections:
  1. Topic
  2. Summary
  3. Rewrite

Rules:
- Keep the Topic short.
- Keep the Summary concise and clear.
- Rewrite the content in clean, readable English.
- Do not add any extra sections.
- If the input is in Thai, keep the Topic in English and rewrite in natural Thai.

Input:
{user_text}
"""


def generate_reply(user_text: str) -> str:
    if model is None:
        return (
            "📌 Topic: Demo Mode\n"
            "💡 Summary: GEMINI_API_KEY is not set yet.\n"
            "✍️ Rewrite: Please add your Gemini API key in Render Environment Variables."
        )

    try:
        response = model.generate_content(build_prompt(user_text))
        text = getattr(response, "text", None)
        if text and text.strip():
            return text.strip()
    except Exception as exc:
        logger.exception("Gemini generation failed: %s", exc)

    return (
        "📌 Topic: Error\n"
        "💡 Summary: I could not generate a response right now.\n"
        "✍️ Rewrite: Please check the Render logs and environment variables."
    )


@app.post("/webhook")
async def webhook(request: Request):
    signature = request.headers.get("X-Line-Signature", "")
    body = await request.body()
    body_text = body.decode("utf-8")

    try:
        handler.handle(body_text, signature)
    except Exception as exc:
        logger.exception("LINE webhook handling failed: %s", exc)
        return JSONResponse(
            status_code=400,
            content={
                "status": "bad request",
                "detail": "Invalid LINE signature or payload",
            },
        )

    return {"status": "ok"}


@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event: MessageEvent):
    user_text = event.message.text
    reply_text = generate_reply(user_text)

    if not LINE_CHANNEL_ACCESS_TOKEN:
        logger.error("LINE_CHANNEL_ACCESS_TOKEN is missing")
        return

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text)],
            )
        )
