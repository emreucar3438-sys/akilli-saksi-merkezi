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

# ================== TELEGRAM ==================
def send(msg):
    try:
        bot.send_message(CHAT_ID, msg)
        print("TELEGRAM:", msg)
    except Exception as e:
        print("Telegram error:", e)

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
    global last_update

    last_update = time.time()

    try:
        payload = msg.payload.decode()
        data = json.loads(payload)

        nem = data.get("nem")
        temp = data.get("temp")
        kritik = data.get("kritik")
        water = data.get("water")
        status = data.get("status")

        # ================= LOW BATTERY =================
        if status == "LOW_BATTERY":
            send("🔋 <b>BATARYA DÜŞÜK!</b>\n⚠️ Sistem şarja ihtiyaç duyuyor")
            col.insert_one({"type": "battery_low", "time": datetime.datetime.now()})
            return

        # ================= LOCK =================
        if status == "LOCKED":
            send("🔒 Sistem kilitlendi (3 hata sonrası)")
            col.insert_one({"type": "locked", "time": datetime.datetime.now()})
            return

        # ================= NORMAL DATA =================
        msg_text = (
            f"🌱 <b>Akıllı Saksı</b>\n"
            f"💧 Nem: %{nem}\n"
            f"🌡 Sıcaklık: {temp}°C\n"
            f"⚠️ Kritik: %{kritik}\n"
            f"🚰 Su: {water:.1f} ml"
        )

        # kritik durum
        if nem < kritik:
            msg_text = "🚨 <b>KRİTİK NEM!</b>\n" + msg_text

        send(msg_text)

        col.insert_one({
            "nem": nem,
            "temp": temp,
            "kritik": kritik,
            "water": water,
            "time": datetime.datetime.now()
        })

    except Exception as e:
        print("MQTT error:", e)

# ================== WATCHDOG ==================
def watchdog():
    global last_update
    while True:
        if time.time() - last_update > 32400:
            send("⚠️ ESP32 veri göndermiyor (9saat)")
        time.sleep(60)

# ================== MQTT THREAD ==================
def mqtt_loop():
    client = mqtt.Client(client_id=f"pot_{int(time.time())}")
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
