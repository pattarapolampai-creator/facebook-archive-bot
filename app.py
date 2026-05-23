import base64
import csv
import hmac
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from google import genai

try:
    from sheets import GoogleSheetsLogger
except Exception:
    GoogleSheetsLogger = None  # type: ignore


APP_NAME = "Facebook Archive Bot"
THAI_TZ = ZoneInfo("Asia/Bangkok")

LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

app = FastAPI(title=APP_NAME)

gemini_client: Optional[genai.Client] = None
sheets_logger = None


def _init_services() -> None:
    global gemini_client, sheets_logger
    if GEMINI_API_KEY and gemini_client is None:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)

    if GoogleSheetsLogger is not None and sheets_logger is None:
        spreadsheet_id = os.getenv("SHEETS_SPREADSHEET_ID", "").strip()
        service_account_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
        if spreadsheet_id and service_account_json:
            try:
                sheets_logger = GoogleSheetsLogger(
                    spreadsheet_id=spreadsheet_id,
                    service_account_json=service_account_json,
                )
            except Exception as exc:
                print(f"[WARN] Google Sheets logger disabled: {exc}")


@app.on_event("startup")
def startup_event() -> None:
    _init_services()


@app.get("/")
def home() -> Dict[str, str]:
    return {"message": f"{APP_NAME} is running"}


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/webhook")
async def webhook(request: Request) -> JSONResponse:
    raw_body = await request.body()
    signature = request.headers.get("x-line-signature", "")

    if not _verify_line_signature(raw_body, signature):
        raise HTTPException(status_code=401, detail="Invalid LINE signature")

    payload = json.loads(raw_body.decode("utf-8"))
    events = payload.get("events", [])

    for event in events:
        await _handle_event(event)

    return JSONResponse({"status": "ok"})


async def _handle_event(event: Dict[str, Any]) -> None:
    event_type = event.get("type")
    reply_token = event.get("replyToken")
    source = event.get("source", {})
    user_id = source.get("userId", "unknown")

    if not reply_token:
        return

    if event_type == "message":
        message = event.get("message", {})
        if message.get("type") != "text":
            await _reply_text(
                reply_token,
                "ตอนนี้ V1 รับเฉพาะข้อความตัวอักษรนะครับ\n"
                "ส่งข้อความโพสต์ที่ต้องการสรุปมาได้เลย"
            )
            return

        user_text = (message.get("text") or "").strip()
        result = process_input(user_text)

        await _reply_text(
            reply_token,
            format_reply(result)
        )

        await _save_record(
            user_id=user_id,
            input_text=user_text,
            input_type=result["input_type"],
            source_link=result.get("source_link", ""),
            topic=result["topic"],
            summary=result["summary"],
            rewrite=result["rewrite"],
        )
        return

    if event_type == "follow":
        await _reply_text(
            reply_token,
            "สวัสดีครับ 👋\nส่งข้อความหรือ Facebook link มาได้เลย เดี๋ยวฉันช่วยสรุปให้"
        )
        return


def process_input(text: str) -> Dict[str, str]:
    text = text.strip()
    source_link = ""
    input_type = "text"
    content = text

    maybe_url = _find_first_url(text)
    if maybe_url:
        input_type = "url"
        source_link = maybe_url
        fetched = _extract_text_from_url(maybe_url)
        if fetched:
            content = fetched
        else:
            # Keep the original text if we cannot fetch the page.
            content = text

    if not content:
        content = text

    ai_result = _summarize_and_rewrite(content)

    return {
        "input_type": input_type,
        "source_link": source_link,
        "topic": ai_result.get("topic", ""),
        "summary": ai_result.get("summary", ""),
        "rewrite": ai_result.get("rewrite", ""),
    }


def _summarize_and_rewrite(content: str) -> Dict[str, str]:
    if not GEMINI_API_KEY:
        return {
            "topic": "API key missing",
            "summary": "ตั้งค่า GEMINI_API_KEY ก่อน แล้วระบบจะสรุปข้อความให้",
            "rewrite": "ยังไม่ได้เปิดใช้งาน AI API",
        }

    _init_services()
    assert gemini_client is not None

    prompt = f"""
คุณคือผู้ช่วยสรุปข้อความภาษาไทย/อังกฤษสำหรับบันทึกโพสต์ในแชท LINE

งานของคุณ:
1) ตั้งชื่อหัวข้อสั้น ๆ
2) สรุปใจความสำคัญ
3) เขียน rewrite ใหม่ให้กระชับ อ่านง่าย

กติกา:
- ตอบกลับเป็น JSON เท่านั้น
- ใช้ key: topic, summary, rewrite
- ห้ามมี markdown
- ถ้าข้อความยาว ให้ย่อสาระสำคัญ
- ถ้ามีลิงก์หรือข้อความอื่นปนอยู่ ให้โฟกัสเนื้อหาหลัก

ข้อความ:
{content}
""".strip()

    try:
        response = gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
        raw_text = (getattr(response, "text", "") or "").strip()
        parsed = _safe_json_loads(raw_text)
        if parsed:
            return {
                "topic": str(parsed.get("topic", "")).strip(),
                "summary": str(parsed.get("summary", "")).strip(),
                "rewrite": str(parsed.get("rewrite", "")).strip(),
            }

        # fallback if model didn't return pure JSON
        return {
            "topic": "สรุปโพสต์",
            "summary": raw_text[:1000],
            "rewrite": raw_text,
        }
    except Exception as exc:
        return {
            "topic": "AI error",
            "summary": f"เกิดข้อผิดพลาดตอนเรียก AI: {exc}",
            "rewrite": "ลองอีกครั้งภายหลัง",
        }


def format_reply(result: Dict[str, str]) -> str:
    lines = [
        f"📌 Topic: {result.get('topic', '').strip()}",
        "",
        f"💡 Summary: {result.get('summary', '').strip()}",
        "",
        f"✍️ Rewrite: {result.get('rewrite', '').strip()}",
    ]
    source_link = result.get("source_link", "").strip()
    if source_link:
        lines += ["", f"🔗 Link: {source_link}"]
    return "\n".join(lines).strip()


def _verify_line_signature(body: bytes, signature: str) -> bool:
    if not LINE_CHANNEL_SECRET:
        return False
    expected = base64.b64encode(
        hmac.new(LINE_CHANNEL_SECRET.encode("utf-8"), body, hashlib.sha256).digest()
    ).decode("utf-8")
    return hmac.compare_digest(expected, signature)


def _find_first_url(text: str) -> str:
    for token in text.split():
        if token.startswith("http://") or token.startswith("https://"):
            return token.rstrip(").,，；;]}")
    return ""


def _extract_text_from_url(url: str) -> str:
    try:
        response = requests.get(
            url,
            timeout=12,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                )
            },
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        parts: List[str] = []

        title = soup.title.get_text(" ", strip=True) if soup.title else ""
        if title:
            parts.append(title)

        for meta_name in ("description", "og:title", "og:description"):
            meta = soup.find("meta", attrs={"name": meta_name}) or soup.find("meta", attrs={"property": meta_name})
            if meta and meta.get("content"):
                content = str(meta.get("content")).strip()
                if content and content not in parts:
                    parts.append(content)

        article_text = " ".join(soup.stripped_strings)
        if article_text:
            parts.append(article_text[:4000])

        combined = "\n".join(dict.fromkeys([p for p in parts if p]))
        return combined.strip()
    except Exception:
        return ""


def _safe_json_loads(text: str) -> Dict[str, Any]:
    if not text:
        return {}
    candidate = text.strip()

    # Try direct JSON first
    try:
        data = json.loads(candidate)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    # Try to extract JSON block
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start != -1 and end != -1 and end > start:
        snippet = candidate[start : end + 1]
        try:
            data = json.loads(snippet)
            if isinstance(data, dict):
                return data
        except Exception:
            pass

    return {}


async def _reply_text(reply_token: str, text: str) -> None:
    if not LINE_CHANNEL_ACCESS_TOKEN:
        raise HTTPException(status_code=500, detail="LINE_CHANNEL_ACCESS_TOKEN is missing")

    url = "https://api.line.me/v2/bot/message/reply"
    payload = {
        "replyToken": reply_token,
        "messages": [{"type": "text", "text": text[:4900]}],
    }
    headers = {
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    response = requests.post(url, headers=headers, json=payload, timeout=12)
    response.raise_for_status()


async def _save_record(
    user_id: str,
    input_text: str,
    input_type: str,
    source_link: str,
    topic: str,
    summary: str,
    rewrite: str,
) -> None:
    timestamp = datetime.now(THAI_TZ).isoformat(timespec="seconds")
    row = {
        "timestamp": timestamp,
        "user_id": user_id,
        "input_type": input_type,
        "original_input": input_text,
        "source_link": source_link,
        "topic": topic,
        "summary": summary,
        "rewrite": rewrite,
    }

    if sheets_logger is not None:
        try:
            sheets_logger.append_row(row)
            return
        except Exception as exc:
            print(f"[WARN] Google Sheets append failed: {exc}")

    # Fallback local CSV for debugging only.
    fallback_csv = Path("archive_fallback.csv")
    write_header = not fallback_csv.exists()
    with fallback_csv.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        if write_header:
            writer.writeheader()
        writer.writerow(row)
