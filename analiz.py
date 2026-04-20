import os
import json
import time
import threading
import datetime

import paho.mqtt.client as mqtt
import telebot
from flask import Flask, request
from pymongo import MongoClient
from dotenv import load_dotenv

# ================== CONFIG ==================
load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
MONGO_URI = os.getenv("MONGO_URI")
APP_URL = os.getenv("APP_URL")
PORT = int(os.getenv("PORT", 10000))

MQTT_BROKER = "broker.hivemq.com"
MQTT_TOPIC = "ev/saksi/nem"

# ================== APP ==================
app = Flask(__name__)
bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# ================== DB ==================
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["AkilliSaksiDB"]
col = db["logs"]

# ================== STATE ==================
last_update = time.time()
is_alert_active = False
last_telegram_send_time = 0

# 🔥 RAM BUFFER (SON 5 VERİ)
last_5_data = []

# ================== TELEGRAM ==================
def send(msg):
    global last_telegram_send_time
    current_time = time.time()

    if current_time - last_telegram_send_time < 2:
        print("ÇİFT MESAJ ENGELLENDİ:", msg)
        return

    try:
        bot.send_message(CHAT_ID, msg)
        last_telegram_send_time = current_time
        print("TELEGRAM:", msg)
    except Exception as e:
        print("Telegram error:", e)

# ================== TELEGRAM HANDLER ==================
# ================== TELEGRAM HANDLER ==================
# ================== TELEGRAM HANDLER ==================
@bot.message_handler(commands=['rapor'])
def handle_rapor(message):
    print("Telegram'dan /rapor komutu geldi!", flush=True)
    send_report()

# ================== RAPOR (SON 5 VERİ) ==================
def send_report():
    try:
        if not last_5_data:
            send("📊 Veri bulunamadı.")
            return

        msg = "📊 <b>Son 5 Nem Verisi</b>\n\n"

        for r in reversed(last_5_data):
            msg += f"💧 %{r['nem']}  🕒 {r['time'].strftime('%H:%M:%S')}\n"

        send(msg)

    except Exception as e:
        print("Rapor error:", e)
        send("❌ Rapor alınamadı")

# ================== WEBHOOK ==================
@app.route("/")
def home():
    return "IoT Server OK 🌱", 200


@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = telebot.types.Update.de_json(request.get_data().decode("utf-8"))
    bot.process_new_updates([update])
    return "OK", 200


@app.route("/set_webhook")
def set_webhook():
    bot.remove_webhook()
    bot.set_webhook(url=f"{APP_URL}/{TOKEN}")
    return "Webhook set OK", 200

# ================== MQTT ==================
def on_connect(client, userdata, flags, rc):
    print("MQTT connected:", rc)
    client.subscribe(MQTT_TOPIC)


def on_message(client, userdata, msg):
    global last_update, last_5_data
    last_update = time.time()

    try:
        payload = msg.payload.decode()
        data = json.loads(payload)

        nem = data.get("nem")
        temp = data.get("temp")
        kritik = data.get("kritik")
        water = data.get("water")
        status = data.get("status")

        # 1. KRİTİK DURUMLAR (Öncelikli Uyarılar)
        if status == "SENSOR_ERROR":
            send("⚠️ <b>SENSÖR HATASI!</b>\nStandart sapma yüksek, tahminleme moduna geçildi. Lütfen sensörü kontrol edin!")
            # Buraya 'return' koymuyoruz çünkü tahmin edilen nemi de aşağıda raporlamak istiyoruz.

        if status == "LOW_BATTERY":
            send("🔋 <b>BATARYA DÜŞÜK!</b>\n⚠️ Sistem şarja ihtiyaç duyuyor")
            col.insert_one({"type": "battery_low", "time": datetime.datetime.now()})
            return

        if status == "LOCKED":
            send("🔒 Sistem kilitlendi (3 hata sonrası)")
            col.insert_one({"type": "locked", "time": datetime.datetime.now()})
            return

        # 2. VERİ KAYIT (RAM Buffer)
        if nem is not None:
            last_5_data.append({"nem": nem, "time": datetime.datetime.now()})
            if len(last_5_data) > 5:
                last_5_data.pop(0)

            # 3. NORMAL MESAJ OLUŞTURMA
            msg_text = (
                f"🌱 <b>Akıllı Saksı</b>\n"
                f"💧 Nem: %{nem}\n"
                f"🌡 Sıcaklık: {temp}°C\n"
                f"⚠️ Kritik: %{kritik}\n"
                f"🚰 Su: {water:.1f} ml"
            )

            # Eğer tahminleme modundaysak mesajın sonuna küçük bir not ekleyelim (Opsiyonel)
            if status == "SENSOR_ERROR":
                msg_text += "\n\n<i>(Veriler tahminidir)</i>"

            if nem < kritik:
                msg_text = "🚨 <b>KRİTİK NEM!</b>\n" + msg_text

            send(msg_text)

            # 4. DB KAYDI
            col.insert_one({
                "nem": nem,
                "temp": temp,
                "kritik": kritik,
                "water": water,
                "status": status,
                "time": datetime.datetime.now()
            })

    except Exception as e:
        print("MQTT error:", e)

# ================== WATCHDOG ==================
def watchdog():
    global last_update, is_alert_active

    while True:
        current_diff = time.time() - last_update

        if current_diff > 32400 and not is_alert_active:
            send("⚠️ ESP32 veri göndermiyor (9 saat)")
            is_alert_active = True

        elif current_diff < 32400:
            is_alert_active = False

        time.sleep(60)

# ================== MQTT THREAD ==================
def mqtt_loop():
    client = mqtt.Client(client_id="akilli_saksi_v2", clean_session=True)
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(MQTT_BROKER, 1883, 60)
    client.loop_forever()

# ================== MAIN ==================
if __name__ == "__main__":
    threading.Thread(target=mqtt_loop, daemon=True).start()
    threading.Thread(target=watchdog, daemon=True).start()

    print("Server started...")
    app.run(host="0.0.0.0", port=PORT)
