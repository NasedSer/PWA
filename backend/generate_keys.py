import base64
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

def generate_vapid_keys():
    # Генерируем приватный ключ на кривой prime256v1 (требуется для VAPID)
    private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
    
    # Получаем публичный ключ
    public_key = private_key.public_key()
    
    # Публичный ключ в несжатом формате (65 байт: 0x04 + x + y)
    public_key_raw = public_key.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint
    )
    
    # Приватный ключ (32 байта)
    private_key_raw = private_key.private_numbers().private_value.to_bytes(32, 'big')
    
    # Кодируем в base64url (без padding)
    public_key_b64 = base64.urlsafe_b64encode(public_key_raw).decode('utf-8').rstrip('=')
    private_key_b64 = base64.urlsafe_b64encode(private_key_raw).decode('utf-8').rstrip('=')
    
    return public_key_b64, private_key_b64

# Генерируем ключи
public_key, private_key = generate_vapid_keys()

print("=" * 60)
print("✅ VAPID КЛЮЧИ УСПЕШНО СГЕНЕРИРОВАНЫ!")
print("=" * 60)
print("\n📋 Скопируйте эти строки в файл .env:\n")
print(f"VAPID_PUBLIC_KEY={public_key}")
print(f"VAPID_PRIVATE_KEY={private_key}")
print("\n" + "=" * 60)
print("\n📁 Пример содержимого файла .env (создайте его в папке backend):")
print("VAPID_PUBLIC_KEY=" + public_key)
print("VAPID_PRIVATE_KEY=" + private_key)
print("\n" + "=" * 60)

# Проверка длины ключей (должно быть 87 и 43 символа соответственно)
print(f"\n📊 Длина публичного ключа: {len(public_key)} символов (должно быть ~87)")
print(f"📊 Длина приватного ключа: {len(private_key)} символов (должно быть ~43)")