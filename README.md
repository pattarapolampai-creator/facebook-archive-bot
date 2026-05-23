# Facebook Archive Bot

LINE chatbot starter for:
- receive text from LINE
- summarize / rewrite with Gemini 3.1 Flash-Lite
- reply back to LINE

## Files
- `app.py` — FastAPI webhook and LINE reply
- `requirements.txt` — dependencies
- `render.yaml` — Render deploy config
- `.env.example` — local environment template

## Local environment variables
Copy `.env.example` to `.env` and fill in:

```env
LINE_CHANNEL_SECRET=
LINE_CHANNEL_ACCESS_TOKEN=
GEMINI_API_KEY=
GEMINI_MODEL=gemini-3.1-flash-lite
```

Optional later:
```env
SHEETS_SPREADSHEET_ID=
GOOGLE_SERVICE_ACCOUNT_JSON=
```

## Deploy to Render
1. Push this repo to GitHub
2. Create a new Web Service on Render from that repo
3. Set environment variables in Render
4. Render will use `render.yaml`

## Notes
- This version does **not** collect images.
- Google Sheets is reserved for the next version.
- If `GEMINI_API_KEY` is missing, the bot returns a demo message.
