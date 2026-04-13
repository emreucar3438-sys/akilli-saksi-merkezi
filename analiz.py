import os
import json
import time
import threading
import datetime
import paho.mqtt.client as mqtt
import telebot
from pymongo import MongoClient
from dotenv import load_dotenv

# ================== CONFIG ==================
load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
MONGO_URI = os.getenv("MONGO_URI")

MQTT_BROKER = "broker.hivemq.com"
MQTT_TOPIC = "ev/saksi/nem"

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# ================== DB ==================
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["AkilliSaksiDB"]
col = db["logs"]

last_update = time.time()

# ================== TELEGRAM ==================
def send(msg):
    try:
        bot.send_message(CHAT_ID, msg)
        print("TELEGRAM GÖNDERİLDİ:", msg)
    except Exception as e:
        print("Telegram hatası:", e)

# ================== MQTT ==================
def on_connect(client, userdata, flags, rc, properties=None):
    print(f"MQTT Bağlandı! Kod: {rc}")
    client.subscribe(MQTT_TOPIC)

def on_message(client, userdata, msg):
    global last_update
    last_update = time.time()
    
    payload = msg.payload.decode()
    print(f"MQTT'den gelen ham veri: {payload}")

    try:
        data = json.loads(payload)
        
        nem = data.get("nem")
        temp = data.get("temp")
        kritik = data.get("kritik")
        water = data.get("water", 0)
        status = data.get("status")

        if status == "LOW_BATTERY":
            send("🔋 <b>BATARYA DÜŞÜK!</b>\n⚠️ Sistem şarja ihtiyaç duyuyor")
            return
        
        if status == "LOCKED":
            send("🔒 Sistem kilitlendi (3 hata sonrası)")
            return

        # SÜSLEMELİ MESAJ FORMATI
        msg_text = (
            f"🌱 <b>Akıllı Saksı</b>\n"
            f"💧 Nem: %{nem}\n"
            f"🌡 Sıcaklık: {temp}°C\n"
            f"⚠️ Kritik: %{kritik}\n"
            f"🚰 Su: {water:.1f} ml"
        )

        if nem < kritik:
            msg_text = "🚨 <b>KRİTİK NEM!</b>\n" + msg_text

        send(msg_text)

        # Veritabanına kaydet
        col.insert_one({
            "nem": nem, "temp": temp, "kritik": kritik, 
            "water": water, "time": datetime.datetime.now()
        })

    except Exception as e:
        print("İşleme hatası:", e)

# ================== MQTT THREAD ==================
def mqtt_loop():
    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message
    
    while True:
        try:
            client.connect(MQTT_BROKER, 1883, 60)
            client.loop_forever()
        except Exception as e:
            print(f"Bağlantı koptu, tekrar deneniyor... {e}")
            time.sleep(5)

# ================== MAIN ==================
if __name__ == "__main__":
    # MQTT'yi arka planda başlat
    threading.Thread(target=mqtt_loop, daemon=True).start()
    
    print("Bot Polling modunda başlatıldı... 🌱")
    # Botu sonsuz döngüde çalıştır
    bot.infinity_polling()
