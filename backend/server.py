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

# CORS для локального тестирования и продакшена
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5000",
        "http://127.0.0.1:5000",
        "https://NasedSer.github.io",
        "https://pwa-791i.onrender.com"
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Конфигурация VAPID
VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY")
VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY")
VAPID_CLAIMS = {"sub": "mailto:test@example.com"}

# База данных SQLite
DB_PATH = "subscriptions.db"

def get_db():
    """Получить соединение с БД"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Инициализация базы данных"""
    conn = get_db()
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
    print("✅ База данных SQLite инициализирована")

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
        
        conn = get_db()
        c = conn.cursor()
        
        # Проверяем, существует ли уже такая подписка
        c.execute("SELECT id FROM subscriptions WHERE endpoint = ?", (endpoint,))
        existing = c.fetchone()
        
        if existing:
            # Обновляем существующую
            c.execute(
                "UPDATE subscriptions SET auth_key = ?, p256dh_key = ? WHERE endpoint = ?",
                (keys.get("auth"), keys.get("p256dh"), endpoint)
            )
            print(f"🔄 Обновлена подписка: {endpoint[:50]}...")
        else:
            # Создаем новую
            c.execute(
                "INSERT INTO subscriptions (endpoint, auth_key, p256dh_key, user_agent) VALUES (?, ?, ?, ?)",
                (endpoint, keys.get("auth"), keys.get("p256dh"), request.headers.get('User-Agent', ''))
            )
            print(f"✅ Новая подписка: {endpoint[:50]}...")
        
        conn.commit()
        conn.close()
        
        return JSONResponse({"status": "ok"})
    except Exception as e:
        print(f"❌ Ошибка сохранения: {e}")
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
        
        conn = get_db()
        c = conn.cursor()
        subscriptions = c.execute("SELECT id, endpoint, auth_key, p256dh_key FROM subscriptions").fetchall()
        conn.close()
        
        print(f"\n{'='*60}")
        print(f"📊 Найдено подписок в БД: {len(subscriptions)}")
        
        success_count = 0
        error_count = 0
        deleted_count = 0
        
        for sub in subscriptions:
            # Определяем тип браузера/сервиса по endpoint
            try:
                service = sub['endpoint'].split('/')[2]
            except:
                service = "unknown"
            
            print(f"\n📌 Подписка #{sub['id']} - сервис: {service}")
            print(f"   Endpoint: {sub['endpoint'][:80]}...")
            
            subscription_info = {
                "endpoint": sub['endpoint'],
                "keys": {
                    "auth": sub['auth_key'],
                    "p256dh": sub['p256dh_key']
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
                print(f"   ✅ Успешно отправлено")
                
            except WebPushException as ex:
                error_count += 1
                print(f"   ❌ Ошибка: {ex}")
                
                if ex.response:
                    print(f"      Статус: {ex.response.status_code}")
                    
                    # Если подписка истекла или не найдена - удаляем
                    if ex.response.status_code in [410, 404]:
                        conn = get_db()
                        c = conn.cursor()
                        c.execute("DELETE FROM subscriptions WHERE id = ?", (sub['id'],))
                        conn.commit()
                        conn.close()
                        deleted_count += 1
                        print(f"      🗑️ Подписка удалена из БД")
            
            except Exception as e:
                error_count += 1
                print(f"   ❌ Неизвестная ошибка: {e}")
        
        print(f"\n{'='*60}")
        print(f"📊 ИТОГИ ОТПРАВКИ:")
        print(f"   ✅ Успешно: {success_count}")
        print(f"   ❌ Ошибок: {error_count}")
        print(f"   🗑️ Удалено: {deleted_count}")
        print(f"   📊 Осталось в БД: {len(subscriptions) - deleted_count}")
        
        return JSONResponse({
            "status": "ok",
            "sent": success_count,
            "failed": error_count,
            "deleted": deleted_count,
            "total_original": len(subscriptions),
            "total_remaining": len(subscriptions) - deleted_count
        })
        
    except Exception as e:
        print(f"❌ Критическая ошибка в send_notification: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/debug/subscriptions")
async def debug_subscriptions():
    """Временный эндпоинт для просмотра всех подписок (только для отладки!)"""
    try:
        conn = get_db()
        c = conn.cursor()
        subscriptions = c.execute("SELECT endpoint, auth_key, p256dh_key, created_at FROM subscriptions").fetchall()
        conn.close()
        
        result = []
        for sub in subscriptions:
            short_endpoint = sub['endpoint'][:50] + "..."
            try:
                service = sub['endpoint'].split('/')[2]
            except:
                service = "unknown"
            
            result.append({
                "endpoint_short": short_endpoint,
                "service": service,
                "has_auth": bool(sub['auth_key']),
                "has_p256dh": bool(sub['p256dh_key']),
                "created_at": sub['created_at']
            })
        
        return JSONResponse({
            "total": len(result),
            "subscriptions": result
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/")
@app.get("/{full_path:path}")
async def serve_frontend(full_path: str = ""):
    frontend_path = Path("../frontend") / full_path
    if frontend_path.exists() and frontend_path.is_file():
        return FileResponse(frontend_path)
    return FileResponse("../frontend/index.html")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)