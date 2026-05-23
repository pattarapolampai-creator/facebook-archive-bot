from fastapi import FastAPI, Request

app = FastAPI()

@app.get("/")
def home():
    return {"message": "Facebook Archive Bot is running"}

@app.post("/webhook")
async def webhook(request: Request):
    body = await request.body()

    print("Webhook received:")
    print(body.decode())

    return {"status": "ok"}