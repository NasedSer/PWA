from pywebpush import generate_vapid_keys

print("Генерация VAPID ключей...")
vapid_keys = generate_vapid_keys()

print("\n✅ Ключи успешно сгенерированы!")
print("\nСкопируйте эти строки в файл .env:\n")
print(f"VAPID_PUBLIC_KEY={vapid_keys.public_key}")
print(f"VAPID_PRIVATE_KEY={vapid_keys.private_key}")