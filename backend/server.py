import os
import json
import sqlite3
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pywebpush import webpush, WebPushException
import uvicorn

load_dotenv()

app = FastAPI()

# CORS для локального тестирования
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Конфигурация VAPID
VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY")
VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY")
VAPID_CLAIMS = {"sub": "mailto:test@example.com"}

# База данных SQLite
DB_PATH = "subscriptions.db"

def init_db():
    """Инициализация базы данных"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            endpoint TEXT UNIQUE,
            auth_key TEXT,
            p256dh_key TEXT,
            user_agent TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

@app.on_event("startup")
async def startup():
    init_db()

@app.get("/api/vapid-public-key")
async def get_vapid_public_key():
    """Отдаем публичный ключ клиенту"""
    return JSONResponse({"publicKey": VAPID_PUBLIC_KEY})

@app.post("/api/subscribe")
async def subscribe(request: Request):
    """Сохранение подписки от браузера"""
    try:
        subscription = await request.json()
        endpoint = subscription.get("endpoint")
        keys = subscription.get("keys", {})
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "INSERT OR REPLACE INTO subscriptions (endpoint, auth_key, p256dh_key) VALUES (?, ?, ?)",
            (endpoint, keys.get("auth"), keys.get("p256dh"))
        )
        conn.commit()
        conn.close()
        
        return JSONResponse({"status": "ok"})
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/send-notification")
async def send_notification(request: Request):
    """Отправка уведомления всем подписчикам"""
    try:
        data = await request.json()
        payload = json.dumps({
            "title": data.get("title", "Тестовое уведомление"),
            "body": data.get("body", "Привет из Python!"),
            "icon": "/icons/icon-192.png",
            "badge": "/icons/badge.png",
            "data": {"url": data.get("url", "/")}
        })
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        subscriptions = c.execute("SELECT endpoint, auth_key, p256dh_key FROM subscriptions").fetchall()
        conn.close()
        
        success_count = 0
        for sub in subscriptions:
            subscription_info = {
                "endpoint": sub[0],
                "keys": {
                    "auth": sub[1],
                    "p256dh": sub[2]
                }
            }
            try:
                webpush(
                    subscription_info=subscription_info,
                    data=payload,
                    vapid_private_key=VAPID_PRIVATE_KEY,
                    vapid_claims=VAPID_CLAIMS
                )
                success_count += 1
            except WebPushException as ex:
                if ex.response and ex.response.status_code == 410:
                    # Удаляем истекшую подписку
                    conn = sqlite3.connect(DB_PATH)
                    c = conn.cursor()
                    c.execute("DELETE FROM subscriptions WHERE endpoint = ?", (sub[0],))
                    conn.commit()
                    conn.close()
                print(f"Ошибка отправки: {ex}")
        
        return JSONResponse({
            "status": "ok",
            "sent": success_count,
            "total": len(subscriptions)
        })
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Раздача статических файлов фронтенда
@app.get("/")
@app.get("/{full_path:path}")
async def serve_frontend(full_path: str = ""):
    frontend_path = Path("../frontend") / full_path
    if frontend_path.exists() and frontend_path.is_file():
        return FileResponse(frontend_path)
    return FileResponse("../frontend/index.html")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)