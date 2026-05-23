# Facebook Archive Bot

LINE chatbot MVP สำหรับ:
- รับข้อความหรือ URL
- สรุป Topic / Summary / Rewrite
- เก็บข้อมูลลง Google Sheets (ถ้าตั้งค่าไว้)

## ไฟล์สำคัญ
- `app.py` : FastAPI webhook
- `sheets.py` : ตัว append ข้อมูลลง Google Sheets
- `requirements.txt` : dependencies
- `render.yaml` : deploy บน Render
- `.env.example` : ตัวอย่าง environment variables

## ตั้งค่า Environment Variables
ใส่ใน Render หรือ local `.env`

- `LINE_CHANNEL_SECRET`
- `LINE_CHANNEL_ACCESS_TOKEN`
- `GEMINI_API_KEY`
- `GEMINI_MODEL` (optional)
- `SHEETS_SPREADSHEET_ID` (optional)
- `GOOGLE_SERVICE_ACCOUNT_JSON` (optional)

## รันบนเครื่องตัวเอง
```bash
pip install -r requirements.txt
uvicorn app:app --reload
```

## ทดสอบ
- เปิด `http://127.0.0.1:8000/`
- ควรเห็นข้อความว่า bot is running

## หมายเหตุ
- V1 นี้ไม่ได้ดึงรูปภาพ
- ถ้า URL อ่านไม่ได้ ระบบจะยังพยายามตอบจากข้อความที่ส่งเข้ามา
