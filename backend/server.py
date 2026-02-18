import os
import json
import sqlite3
from pathlib import Path
from urllib.parse import urlparse
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
    
    # Таблица для типов подписок
    c.execute('''
        CREATE TABLE IF NOT EXISTS subscription_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type_key TEXT UNIQUE NOT NULL,
            type_name TEXT NOT NULL,
            type_description TEXT,
            type_color TEXT DEFAULT '#e2e3e5',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Добавляем начальные типы, если таблица пуста
    c.execute("SELECT COUNT(*) as count FROM subscription_types")
    if c.fetchone()['count'] == 0:
        initial_types = [
            ('general', 'Общие уведомления', 'Обычные уведомления для всех', '#e2e3e5'),
            ('news', 'Новости', 'Новости и обновления', '#cce5ff'),
            ('promo', 'Акции и скидки', 'Специальные предложения', '#d4edda'),
            ('urgent', 'Срочные уведомления', 'Важные сообщения', '#f8d7da')
        ]
        c.executemany(
            "INSERT INTO subscription_types (type_key, type_name, type_description, type_color) VALUES (?, ?, ?, ?)",
            initial_types
        )
        print("✅ Добавлены начальные типы подписок")
    
    # Таблица для подписок пользователей
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
    
    # Проверяем, есть ли колонка subscription_type
    c.execute("PRAGMA table_info(subscriptions)")
    columns = [column[1] for column in c.fetchall()]
    
    if 'subscription_type' not in columns:
        print("🔄 Добавляем колонку subscription_type в таблицу subscriptions...")
        try:
            c.execute("ALTER TABLE subscriptions ADD COLUMN subscription_type TEXT DEFAULT 'general'")
            print("✅ Колонка subscription_type успешно добавлена")
        except Exception as e:
            print(f"⚠️ Ошибка при добавлении колонки: {e}")
    
    # Проверяем, есть ли внешний ключ (опционально)
    if 'subscription_type' in columns:
        # Обновляем существующие записи, у которых тип не указан
        c.execute("UPDATE subscriptions SET subscription_type = 'general' WHERE subscription_type IS NULL")
        print("🔄 Обновлены существующие подписки, установлен тип 'general'")
    
    conn.commit()
    conn.close()
    print("✅ База данных SQLite инициализирована")


@app.post("/api/debug/reset-db")
async def reset_db():
    """Полностью пересоздать таблицы (только для отладки!)"""
    try:
        conn = get_db()
        c = conn.cursor()
        
        # Удаляем существующие таблицы
        c.execute("DROP TABLE IF EXISTS subscriptions")
        c.execute("DROP TABLE IF EXISTS subscription_types")
        conn.commit()
        conn.close()
        
        # Переинициализируем БД
        init_db()
        
        return JSONResponse({"status": "database reset successfully"})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    

@app.on_event("startup")
async def startup():
    init_db()

# ========== Эндпоинты для управления типами подписок ==========

@app.get("/api/types")
async def get_subscription_types():
    """Получить все типы подписок"""
    try:
        conn = get_db()
        c = conn.cursor()
        types = c.execute("SELECT type_key, type_name, type_description, type_color FROM subscription_types ORDER BY id").fetchall()
        conn.close()
        
        return JSONResponse({
            "types": [dict(t) for t in types]
        })
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/types")
async def create_subscription_type(request: Request):
    """Создать новый тип подписки"""
    try:
        data = await request.json()
        type_key = data.get("type_key", "").strip().lower().replace(" ", "_")
        type_name = data.get("type_name", "").strip()
        type_description = data.get("type_description", "")
        type_color = data.get("type_color", "#e2e3e5")
        
        if not type_key or not type_name:
            raise HTTPException(status_code=400, detail="type_key и type_name обязательны")
        
        conn = get_db()
        c = conn.cursor()
        c.execute(
            "INSERT INTO subscription_types (type_key, type_name, type_description, type_color) VALUES (?, ?, ?, ?)",
            (type_key, type_name, type_description, type_color)
        )
        conn.commit()
        conn.close()
        
        return JSONResponse({"status": "ok", "type_key": type_key})
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Тип с таким ключом уже существует")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.put("/api/types/{type_key}")
async def update_subscription_type(type_key: str, request: Request):
    """Обновить тип подписки"""
    try:
        data = await request.json()
        type_name = data.get("type_name")
        type_description = data.get("type_description")
        type_color = data.get("type_color")
        
        conn = get_db()
        c = conn.cursor()
        
        updates = []
        values = []
        if type_name:
            updates.append("type_name = ?")
            values.append(type_name)
        if type_description is not None:
            updates.append("type_description = ?")
            values.append(type_description)
        if type_color:
            updates.append("type_color = ?")
            values.append(type_color)
        
        if updates:
            values.append(type_key)
            c.execute(
                f"UPDATE subscription_types SET {', '.join(updates)} WHERE type_key = ?",
                values
            )
            conn.commit()
        
        conn.close()
        return JSONResponse({"status": "ok"})
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/types/{type_key}")
async def delete_subscription_type(type_key: str):
    """Удалить тип подписки"""
    try:
        conn = get_db()
        c = conn.cursor()
        
        # Проверяем, есть ли подписки этого типа
        c.execute("SELECT COUNT(*) as count FROM subscriptions WHERE subscription_type = ?", (type_key,))
        if c.fetchone()['count'] > 0:
            conn.close()
            raise HTTPException(status_code=400, detail="Нельзя удалить тип, у которого есть подписчики")
        
        c.execute("DELETE FROM subscription_types WHERE type_key = ?", (type_key,))
        conn.commit()
        conn.close()
        
        return JSONResponse({"status": "ok"})
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/types/stats")
async def get_subscription_stats():
    """Получить статистику по типам подписок"""
    try:
        conn = get_db()
        c = conn.cursor()
        
        # Общая статистика
        types = c.execute("""
            SELECT 
                st.type_key,
                st.type_name,
                st.type_color,
                COUNT(s.id) as subscriber_count
            FROM subscription_types st
            LEFT JOIN subscriptions s ON st.type_key = s.subscription_type
            GROUP BY st.type_key, st.type_name, st.type_color
            ORDER BY st.id
        """).fetchall()
        
        # Общее количество подписок
        total = c.execute("SELECT COUNT(*) as count FROM subscriptions").fetchone()['count']
        
        conn.close()
        
        return JSONResponse({
            "total": total,
            "types": [dict(t) for t in types]
        })
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ========== Основные эндпоинты для PWA ==========

@app.get("/api/vapid-public-key")
async def get_vapid_public_key():
    """Отдаем публичный ключ клиенту"""
    return JSONResponse({"publicKey": VAPID_PUBLIC_KEY})

@app.post("/api/subscribe")
async def subscribe(request: Request):
    """Сохранение подписки от браузера с типом"""
    try:
        # Получаем данные запроса
        body = await request.body()
        print(f"📥 Получен запрос на подписку, тело: {body[:200]}...")
        
        subscription = await request.json()
        print(f"📦 Данные подписки: {json.dumps(subscription, indent=2)[:500]}")
        
        endpoint = subscription.get("endpoint")
        keys = subscription.get("keys", {})
        subscription_type = subscription.get("type", "general")
        
        if not endpoint:
            raise HTTPException(status_code=400, detail="endpoint is required")
        
        if not keys.get("auth") or not keys.get("p256dh"):
            raise HTTPException(status_code=400, detail="auth and p256dh keys are required")
        
        conn = get_db()
        c = conn.cursor()
        
        # Проверяем, существует ли такой тип
        c.execute("SELECT type_key FROM subscription_types WHERE type_key = ?", (subscription_type,))
        type_exists = c.fetchone()
        if not type_exists:
            print(f"⚠️ Тип {subscription_type} не найден, используем 'general'")
            subscription_type = "general"  # fallback на general
        
        # Проверяем, существует ли уже такая подписка
        c.execute("SELECT id FROM subscriptions WHERE endpoint = ?", (endpoint,))
        existing = c.fetchone()
        
        if existing:
            # Обновляем существующую
            c.execute(
                "UPDATE subscriptions SET auth_key = ?, p256dh_key = ?, subscription_type = ? WHERE endpoint = ?",
                (keys.get("auth"), keys.get("p256dh"), subscription_type, endpoint)
            )
            print(f"🔄 Обновлена подписка (тип: {subscription_type}): {endpoint[:50]}...")
        else:
            # Создаем новую
            c.execute(
                """INSERT INTO subscriptions 
                   (endpoint, auth_key, p256dh_key, user_agent, subscription_type) 
                   VALUES (?, ?, ?, ?, ?)""",
                (endpoint, keys.get("auth"), keys.get("p256dh"), 
                 request.headers.get('User-Agent', ''), subscription_type)
            )
            print(f"✅ Новая подписка (тип: {subscription_type}): {endpoint[:50]}...")
        
        conn.commit()
        conn.close()
        
        return JSONResponse({"status": "ok", "type": subscription_type})
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Ошибка сохранения: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/send-notification")
async def send_notification(request: Request):
    """Отправка уведомления с фильтром по типу подписки"""
    try:
        data = await request.json()
        target_type = data.get("targetType", "all")
        message_title = data.get("title", "Уведомление")
        message_body = data.get("body", "")
        
        payload = json.dumps({
            "title": message_title,
            "body": message_body,
            "icon": "/icons/icon-192.png",
            "badge": "/icons/badge.png",
            "data": {"url": data.get("url", "/")}
        })
        
        conn = get_db()
        c = conn.cursor()
        
        # Формируем запрос в зависимости от целевой аудитории
        if target_type == "all":
            subscriptions = c.execute(
                "SELECT id, endpoint, auth_key, p256dh_key, subscription_type FROM subscriptions"
            ).fetchall()
            print(f"📊 Отправка ВСЕМ подписчикам")
        else:
            subscriptions = c.execute(
                "SELECT id, endpoint, auth_key, p256dh_key, subscription_type FROM subscriptions WHERE subscription_type = ?",
                (target_type,)
            ).fetchall()
            
            # Получаем название типа для вывода
            type_info = c.execute("SELECT type_name FROM subscription_types WHERE type_key = ?", (target_type,)).fetchone()
            type_name = type_info['type_name'] if type_info else target_type
            print(f"📊 Отправка подписчикам типа: {type_name}")
        
        conn.close()
        
        print(f"\n{'='*60}")
        print(f"📨 Сообщение: {message_title} - {message_body}")
        print(f"📊 Найдено подписок: {len(subscriptions)}")
        
        success_count = 0
        error_count = 0
        deleted_count = 0
        
        for sub in subscriptions:
            # Определяем тип браузера/сервиса по endpoint
            try:
                service = sub['endpoint'].split('/')[2]
            except:
                service = "unknown"
            
            print(f"\n📌 Подписка #{sub['id']} (тип: {sub['subscription_type']}) - сервис: {service}")
            
            subscription_info = {
                "endpoint": sub['endpoint'],
                "keys": {
                    "auth": sub['auth_key'],
                    "p256dh": sub['p256dh_key']
                }
            }
            
            try:
                parsed_url = urlparse(sub['endpoint'])
                origin = f"{parsed_url.scheme}://{parsed_url.netloc}"
                
                dynamic_claims = VAPID_CLAIMS.copy()
                dynamic_claims["aud"] = origin
                
                webpush(
                    subscription_info=subscription_info,
                    data=payload,
                    vapid_private_key=VAPID_PRIVATE_KEY,
                    vapid_claims=dynamic_claims
                )
                success_count += 1
                print(f"   ✅ Успешно отправлено")
                
            except WebPushException as ex:
                error_count += 1
                print(f"   ❌ Ошибка: {ex}")
                
                if ex.response:
                    print(f"      Статус: {ex.response.status_code}")
                    
                    if ex.response.status_code in [410, 404]:
                        conn = get_db()
                        c = conn.cursor()
                        c.execute("DELETE FROM subscriptions WHERE id = ?", (sub['id'],))
                        conn.commit()
                        conn.close()
                        deleted_count += 1
                        print(f"      🗑️ Подписка удалена из БД")
                    elif ex.response.status_code == 403:
                        print(f"      ⚠️ Ошибка 403 Forbidden - подписка сохранена")
                
            except Exception as e:
                error_count += 1
                print(f"   ❌ Неизвестная ошибка: {e}")
        
        print(f"\n{'='*60}")
        print(f"📊 ИТОГИ ОТПРАВКИ:")
        print(f"   ✅ Успешно: {success_count}")
        print(f"   ❌ Ошибок: {error_count}")
        print(f"   🗑️ Удалено: {deleted_count}")
        
        return JSONResponse({
            "status": "ok",
            "sent": success_count,
            "failed": error_count,
            "deleted": deleted_count,
            "total_original": len(subscriptions)
        })
        
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        raise HTTPException(status_code=400, detail=str(e))

# ========== Отладочные эндпоинты ==========

@app.get("/api/debug/subscriptions")
async def debug_subscriptions():
    """Просмотр всех подписок"""
    try:
        conn = get_db()
        c = conn.cursor()
        
        subscriptions = c.execute("""
            SELECT s.*, t.type_name, t.type_color 
            FROM subscriptions s
            LEFT JOIN subscription_types t ON s.subscription_type = t.type_key
        """).fetchall()
        
        conn.close()
        
        return JSONResponse({
            "total": len(subscriptions),
            "subscriptions": [dict(s) for s in subscriptions]
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/debug/clear-all")
async def clear_all():
    """Очистка всех подписок"""
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM subscriptions")
    conn.commit()
    conn.close()
    return JSONResponse({"status": "all subscriptions deleted"})

@app.get("/")
@app.get("/{full_path:path}")
async def serve_frontend(full_path: str = ""):
    frontend_path = Path("../frontend") / full_path
    if frontend_path.exists() and frontend_path.is_file():
        return FileResponse(frontend_path)
    return FileResponse("../frontend/index.html")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)