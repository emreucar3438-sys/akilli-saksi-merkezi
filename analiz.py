import os
import time
import json
import threading
import datetime

import paho.mqtt.client as mqtt
import telebot
from pymongo import MongoClient
from dotenv import load_dotenv

# ---------------- CONFIG ----------------
load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
MONGO_URI = os.getenv("MONGO_URI")

MQTT_BROKER = "broker.hivemq.com"
MQTT_TOPIC = "ev/saksi/nem"

# ---------------- STATE ----------------
son_mesaj_zamani = time.time()
son_nem = 0
lock = threading.Lock()

sulama_kayitlari = []
telegram_cooldown = 0

# ---------------- TELEGRAM ----------------
bot = telebot.TeleBot(TOKEN, parse_mode=None)

def telegram(msg):
    global telegram_cooldown

    now = time.time()
    if now - telegram_cooldown < 10:
        return

    try:
        bot.send_message(CHAT_ID, msg)
        telegram_cooldown = now
        print("TELEGRAM:", msg)
    except Exception as e:
        print("Telegram error:", e)

# ---------------- MONGO ----------------
try:
    mongo = MongoClient(MONGO_URI)
    db = mongo["AkilliSaksiDB"]
    col = db["logs"]
    print("MongoDB connected")
except Exception as e:
    print("Mongo error:", e)
    col = None

# ---------------- WATCHDOG ----------------
def watchdog():
    global son_mesaj_zamani

    while True:
        time.sleep(30)

        if time.time() - son_mesaj_zamani > 3600 * 9:
            telegram("🚨 ESP32 OFFLINE (9 saat veri yok)")
            print("WATCHDOG: ESP offline")

# ---------------- MQTT ----------------
def on_connect(client, userdata, flags, rc, properties=None):
    print("MQTT connected:", rc)
    client.subscribe(MQTT_TOPIC)

def on_disconnect(client, userdata, rc, properties=None):
    print("MQTT disconnected! reconnecting...")
    time.sleep(3)
    try:
        client.reconnect()
    except Exception as e:
        print("Reconnect error:", e)

def on_message(client, userdata, msg):
    global son_mesaj_zamani, son_nem

    try:
        payload = msg.payload.decode()
        data = json.loads(payload)

        son_mesaj_zamani = time.time()
        zaman = datetime.datetime.now().strftime("%d/%m %H:%M:%S")

        mesaj = None
        log = None

        # ---------------- ERROR ----------------
        if isinstance(data, dict) and ("error" in data or "status" in data):

            code = data.get("error") or data.get("status")

            if code == "LOW_BATTERY":
                mesaj = "⚡ Düşük batarya!"
            elif code in ["LOCKED", "SYSTEM_LOCKED"]:
                mesaj = "🔒 Sistem kilitlendi!"
            else:
                mesaj = f"⚠️ Durum: {code}"

            log = {
                "status": code,
                "time": datetime.datetime.now(),
                "type": "error_log"
            }

        # ---------------- SENSOR ----------------
        if isinstance(data, dict) and "nem" in data:

            nem = float(data.get("nem", 0))
            temp = float(data.get("temp", 0))
            kritik = float(data.get("kritik", 0))
            water = float(data.get("water", 0))

            if son_nem and nem > son_nem + 3:
                mesaj = f"🌱 Sulama başarılı! Nem: {nem}%"
            elif nem < kritik:
                mesaj = f"🚨 KRİTİK NEM! {nem}%"
            else:
                mesaj = f"🌿 Nem: {nem}% | Temp: {temp}°C"

            son_nem = nem

            log = {
                "nem": nem,
                "temp": temp,
                "kritik": kritik,
                "water": water,
                "time": datetime.datetime.now(),
                "type": "sensor_log"
            }

        # ---------------- SEND ----------------
        if mesaj:
            telegram(mesaj)

            with lock:
                sulama_kayitlari.insert(0, f"{zaman} -> {mesaj}")
                if len(sulama_kayitlari) > 10:
                    sulama_kayitlari.pop()

        # ---------------- DB ----------------
        if col is not None and log:
            try:
                col.insert_one(log)
            except Exception as e:
                print("Mongo insert error:", e)

    except Exception as e:
        print("MQTT processing error:", e)

# ---------------- TELEGRAM COMMAND ----------------
@bot.message_handler(commands=["rapor"])
def rapor(message):
    text = "🌱 SON 10 KAYIT:\n\n"

    with lock:
        if sulama_kayitlari:
            text += "\n".join(sulama_kayitlari)
        else:
            text += "Kayıt yok"

    bot.send_message(message.chat.id, text)

# ---------------- MQTT LOOP ----------------
def mqtt_loop():
    while True:
        try:
            client = mqtt.Client(
                client_id="Smart_Pot_Server"
            )

            client.on_connect = on_connect
            client.on_message = on_message
            client.on_disconnect = on_disconnect

            client.connect(MQTT_BROKER, 1883, 60)
            client.loop_forever()

        except Exception as e:
            print("MQTT crash:", e)
            time.sleep(5)

# ---------------- START ----------------
if __name__ == "__main__":

    # 🚨 CRITICAL FIX: Telegram webhook temizle (409 çözümü)
    try:
        bot.remove_webhook()
        time.sleep(1)
    except:
        pass

    threading.Thread(target=watchdog, daemon=True).start()

    # ❗ bot polling TEK THREAD
    threading.Thread(
        target=lambda: bot.infinity_polling(
            skip_pending=True,
            timeout=20,
            long_polling_timeout=20,
            none_stop=True
        ),
        daemon=True
    ).start()

    telegram("🚀 Cloud System Started")

    mqtt_loop()
