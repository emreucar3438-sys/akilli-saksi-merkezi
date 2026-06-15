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

# RAM BUFFER (SON 5 VERİ)
last_5_data = []

# ================== TELEGRAM ==================
def send(msg):
    global last_telegram_send_time
    current_time = time.time()

    # Eğer iki mesaj arası 0.5 saniyeden kısaysa, kısa bir mola ver
    # Böylece ESP'den peş peşe gelen mesajlar engellenmez, sadece sıraya girer.
    if current_time - last_telegram_send_time < 0.5:
        time.sleep(0.5) 

    try:
        bot.send_message(CHAT_ID, msg)
        last_telegram_send_time = time.time() # Zamanı mesaj gönderildikten sonra güncelle
        print("TELEGRAM:", msg)
    except Exception as e:
        print("Telegram error:", e)

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
        msg_type = data.get("type")
        msg_content = data.get("msg", "")

        # --- 1. INFO MESAJLARI (Güneş Erteleme vs.) ---
        if msg_type == "INFO":
            if msg_content == "GUNES_ERTELEME_30SN":
                mesaj = (
                    f"☀️ <b>GÜNEŞTEN DOLAYI ERTELENDİ</b>\n"
                    f"────────────────────\n"
                    f"💧 <b>Mevcut Nem:</b> %{data.get('nem')}\n"
                    f"💡 <b>Işık Şiddeti:</b> {data.get('isik')}\n\n"
                    f"🕒 Bitki köklerinin haşlanmaması için sulama kısa bir süre ertelendi."
                )
                send(mesaj)
            else:
                send(f"ℹ️ <b>BİLGİ:</b> {msg_content}\nNem: %{data.get('nem')}")
            return # Bu tip işlendi, diğerlerini kontrol etme

        # --- 2. LOG MESAJLARI (Yağmur Durumu ve Genel Loglar) ---
        elif msg_type == "LOG":
            # Yağmur kelimelerini yakala
            if any(k in msg_content for k in ["Yagmur", "yagabilir", "Yağmur"]):
                send(f"🌧️ <b>HAVA DURUMU UYARISI</b>\n{msg_content}")
            else:
                send(f"ℹ️ <b>BİLGİ:</b> {msg_content}")
            return

        # --- 3. DİĞER ÖZEL TİPLER (DECISION, CRITICAL, RESULT) ---
        elif msg_type == "DECISION":
            send(f"💧 <b>SULAMA BAŞLADI</b>\nSebep: {data.get('reason')}")
            return

        elif msg_type == "CRITICAL":
            send(f"🚨 <b>ACİL DURUM:</b> {msg_content}")
            return

        elif msg_type == "RESULT":
            post_nem = data.get("post_nem")
            water = data.get("water")
            send(f"✅ <b>SULAMA TAMAMLANDI</b>\n💧 Son Nem: %{post_nem}\n🧪 Harcanan: {water} ml")
            return

        # --- 4. STANDART DURUM VERİLERİ (Diğer tüm veri akışları) ---
        nem = data.get("nem")
        temp = data.get("temp", 0)
        kritik = data.get("kritik", 40)
        isik = data.get("isik", 0)
        water = data.get("water", 0)
        status = data.get("status", "OK")

        if status == "LOW_BATTERY":
            send("🔋 <b>BATARYA DÜŞÜK!</b>\n⚠️ Sistem kapanmak üzere.")
            return

        is_locked = data.get("locked") == "true" or data.get("locked") is True
        if is_locked:
            send("🔒 <b>SİSTEM KİLİTLİ</b>\n⚠️ Pompa koruması devrede! Su bitmiş olabilir.")
            return

        if nem is not None:
            # RAM Buffer Güncelleme
            last_5_data.append({"nem": nem, "time": datetime.datetime.now()})
            if len(last_5_data) > 5: last_5_data.pop(0)

            msg_text = f"🌱 <b>Akıllı Saksı</b>\n💧 Nem: %{nem}\n🌡 Sıcaklık: {temp}°C\n💡 Işık: %{isik}\n🚰 Su: {water:.1f} ml"
            if nem < kritik and status != "SENSOR_ERROR":
                msg_text = "🚨 <b>KRİTİK NEM!</b>\n" + msg_text
            
            send(msg_text)
            data["time"] = datetime.datetime.now()
            col.insert_one(data)

    except Exception as e:
        print(f"MQTT işleme hatası: {e}")
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
