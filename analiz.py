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

    if current_time - last_telegram_send_time < 1:
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
        
        # 0. Mesaj Tipini Al (Hata almamak için en başta tanımlıyoruz)
        msg_type = data.get("type")

        # --- ÖZEL MESAJ TİPLERİ (SULAMA VE KRİTİK DURUMLAR)
        if msg_type == "INFO":
            send(f"☀️ <b>Güneş Ertelemesi</b>\nNem: %{data.get('nem')}\nIşık: {data.get('isik')}\nSulama akşam saatlerine ertelendi.")
            return
        if msg_type == "DECISION":
            send(f"💧 <b>SULAMA BAŞLADI</b>\nSebep: {data.get('reason')}")
            return # Alt satırlara devam etme

        if msg_type == "CRITICAL":
            send(f"🚨 <b>ACİL DURUM:</b> {data.get('msg')}")
            return

        if msg_type == "RESULT":
            post_nem = data.get("post_nem")
            water = data.get("water")
            send(f"✅ <b>SULAMA TAMAMLANDI</b>\n💧 Son Nem: %{post_nem}\n🧪 Harcanan: {water} ml")
            return
        # -------------------------------------------------------

        # 1. STANDART DURUM VERİLERİNİ AL
        nem = data.get("nem")
        temp = data.get("temp", 0)
        kritik = data.get("kritik", 40)
        water = data.get("water", 0)
        status = data.get("status", "OK")

        # 2. ÖNCELİKLİ DURUM KONTROLLERİ (Hata ve Pil)
        alert_prefix = ""
        if status == "SENSOR_ERROR":
            alert_prefix = "⚠️ <b>TAHMİN MODU:</b> Sensör gürültülü!\n"
        
        if status == "LOW_BATTERY":
            send("🔋 <b>BATARYA DÜŞÜK!</b>\n⚠️ Sistem kapanmak üzere.")
            return

        # GÜNCELLENEN KISIM: Kilitli ise sadece kilit ve sıcaklık mesajı gönder
        if is_locked:
            msg_text = (
                f"🔒 <b>SİSTEM KİLİTLİ</b>\n"
                f"⚠️ Pompa koruması devrede!\n"
                f"🌡 Hava Sıcaklığı: {temp}°C\n\n"
                f"📌 Su bitmiş olabilir, lütfen kontrol et."
            )
            send(msg_text)
            return # Fonksiyonu burada keser, alttaki nem mesajlarını atmaz.

        # 3. VERİ KAYIT VE MESAJ OLUŞTURMA
        if nem is not None:
            # RAM Buffer Güncelleme
            last_5_data.append({"nem": nem, "time": datetime.datetime.now()})
            if len(last_5_data) > 5: 
                last_5_data.pop(0)

            # Mesaj Metni
            msg_text = (
                f"{alert_prefix}"
                f"🌱 <b>Akıllı Saksı</b>\n"
                f"💧 Nem: %{nem}\n"
                f"🌡 Sıcaklık: {temp}°C\n"
                f"🚰 Su: {water:.1f} ml"
            )

            # Kritik Nem Uyarısı (Gerçekten nem düşükse ve sensör sağlamsa)
            if nem < kritik and status != "SENSOR_ERROR":
                msg_text = "🚨 <b>KRİTİK NEM!</b>\n" + msg_text

            send(msg_text)

            # MongoDB Kaydı
            data["time"] = datetime.datetime.now()
            col.insert_one(data)

    except Exception as e:
        print(f"MQTT error: {e}")

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

    while True:
        try:
            client.connect(MQTT_BROKER, 1883, 60)
            client.loop_forever()
        except Exception as e:
            print("MQTT reconnecting...", e)
            time.sleep(5)

# ================== MAIN ==================
if __name__ == "__main__":
    threading.Thread(target=mqtt_loop, daemon=True).start()
    threading.Thread(target=watchdog, daemon=True).start()

    print("Server started...")
app.run(host="0.0.0.0", port=PORT, threaded=True, use_reloader=False)
