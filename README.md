# 🌱 Smart Plant Watering System - Cloud Backend

ESP32 tabanlı akıllı saksı sisteminin bulut servisi. MQTT üzerinden nem verisi alır, MongoDB'ye kaydeder ve Telegram ile bildirim gönderir.

## 🏗️ Mimari
```
ESP32 (Sensor) → MQTT Broker → Cloud Service → MongoDB
                                      ↓
                               Telegram Bot
```

## ⚙️ Teknolojiler

- **MQTT**: paho-mqtt (ESP32 ile iletişim)
- **Bot**: python-telegram-bot
- **Database**: MongoDB Atlas
- **Deploy**: Render.com

## 📡 MQTT İletişimi
```python
# ESP32 publish eder:
Topic: "ev/saksi/nem"
Payload: "45" (nem değeri)

# Bu servis dinler ve işler:
client.subscribe("ev/saksi/nem")
```

## 🚀 Kurulum

1. Render.com'da yeni Web Service oluştur
2. Environment Variables:
   - `TELEGRAM_TOKEN`: Bot token
   - `TELEGRAM_CHAT_ID`: Chat ID
   - `MONGO_URI`: MongoDB connection string
3. Bu repoyu bağla ve deploy et

## 📊 Özellikler

- ✅ Real-time MQTT iletişimi
- ✅ MongoDB time-series data storage
- ✅ Telegram bildirimleri
- ✅ Watchdog monitoring (10 dk timeout)
- ✅ /rapor komutu (son 10 kayıt)

## 📱 Telegram Komutları

- `/rapor` - Son 10 ölçüm kaydını göster

## 🔧 Deployment
```bash
# Render otomatik deploy yapar, manuel test için:
python main.py
```

## 📝 License

MIT
