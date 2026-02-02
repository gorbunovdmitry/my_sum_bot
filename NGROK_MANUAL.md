# 📥 Установка ngrok вручную

## Вариант 1: Скачать напрямую

1. Откройте https://ngrok.com/download
2. Выберите macOS (ARM64 для M3)
3. Скачайте и распакуйте
4. Переместите в PATH:
   ```bash
   sudo mv ngrok /usr/local/bin/
   ```

## Вариант 2: Через Homebrew (повторная попытка)

```bash
brew install ngrok/ngrok/ngrok
```

Если не работает, попробуйте:
```bash
brew tap ngrok/ngrok
brew install ngrok
```

## После установки

1. Получите токен: https://dashboard.ngrok.com/get-started/your-authtoken
2. Настройте: `ngrok config add-authtoken YOUR_TOKEN`
3. Запустите: `ngrok http 5000`

---

## Альтернатива: Использовать другой туннель

Если ngrok не работает, можно использовать:
- **Cloudflare Tunnel** (бесплатно, постоянный домен)
- **localtunnel** (npm): `npx localtunnel --port 5000`
- **serveo** (SSH): `ssh -R 80:localhost:5000 serveo.net`

Но для Telegram Login Widget лучше всего подходит ngrok.
