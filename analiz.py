import os
import time
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import paho.mqtt.client as mqtt
import telebot
from pymongo import MongoClient
import datetime
from dotenv import load_dotenv

# --- ENV ---
load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
ID = os.getenv("TELEGRAM_CHAT_ID")
MONGO_URI = os.getenv("MONGO_URI")

MQTT_BROKER = "broker.hivemq.com"
MQTT_TOPIC = "ev/saksi/nem"

# --- TIMEZONE ---
os.environ['TZ'] = 'Europe/Istanbul'
if hasattr(time, 'tzset'):
    time.tzset()

# --- DB ---
try:
    mongo_client = MongoClient(MONGO_URI)
    db = mongo_client["AkilliSaksiDB"]
    logs_col = db["NemGecmisi"]
    print("MongoDB Bağlantısı Başarılı! ✅", flush=True)
except Exception as e:
    print(f"MongoDB Bağlantı Hatası: {e}", flush=True)

bot = telebot.TeleBot(TOKEN)

# --- STATE ---
son_mesaj_zamani = time.time()
bekci_uyarisi_verildi = False
sulama_kayitlari = []
son_nem = 0

# 🔋 YENİ BATARYA STATE
son_batarya_uyarisi = False

# --- TELEGRAM ---
def telegram_haber_ver(mesaj):
    try:
        bot.send_message(ID, mesaj)
        print(f"TELEGRAM: {mesaj}", flush=True)
    except Exception as e:
        print(f"TELEGRAM HATASI: {e}", flush=True)

# --- RAPOR ---
@bot.message_handler(commands=['rapor'])
def rapor_gonder(message):
    try:
        if not sulama_kayitlari:
            bot.reply_to(message, "📊 Henüz kayıt yok aga.")
        else:
            text = "📊 Son 10 Kayıt:\n\n" + "\n".join(sulama_kayitlari)
            bot.send_message(message.chat.id, text)
    except Exception as e:
        print(f"Rapor Hatası: {e}", flush=True)

# --- HTTP ---
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Saksi Sistemi Aktif")

# --- WATCHDOG ---
def bekci_kopegi():
    global son_mesaj_zamani, bekci_uyarisi_verildi
    while True:
        try:
            if time.time() - son_mesaj_zamani > 600 and not bekci_uyarisi_verildi:
                telegram_haber_ver("🚨 10 dakikadır veri yok!")
                bekci_uyarisi_verildi = True

            if time.time() - son_mesaj_zamani < 600:
                bekci_uyarisi_verildi = False

        except:
            pass

        time.sleep(60)

# --- MQTT ---
def on_connect(client, userdata, flags, rc):
    print(f"MQTT Bağlantı: {rc}", flush=True)
    client.subscribe(MQTT_TOPIC)

def on_message(client, userdata, msg):
    global son_nem, son_mesaj_zamani, son_batarya_uyarisi

    try:
        son_mesaj_zamani = time.time()
        gelen = msg.payload.decode()

        zaman = time.strftime('%d/%m %H:%M:%S')

        # ---------------- JSON değilse direkt mesaj ----------------
        if not gelen.isdigit():
            telegram_haber_ver(gelen)
            logs_col.insert_one({
                "mesaj": gelen,
                "zaman": datetime.datetime.now(),
                "type": "system"
            })
            return

        nem = int(gelen)

        kayit = ""
        mesaj = ""

        # ---------------- NEM LOJİK ----------------
        if nem < 40:
            mesaj = f"🚨 KRİTİK NEM %{nem}"
            kayit = f"🚨 {zaman} -> KRİTİK %{nem}"

        elif son_nem != 0 and (nem - son_nem) > 10:
            mesaj = f"🌿 Sulama sonrası %{nem}"
            kayit = f"✅ {zaman} -> SULAMA %{nem}"

        else:
            mesaj = f"🌿 Nem %{nem}"
            kayit = f"✅ {zaman} -> NORMAL %{nem}"

        son_nem = nem

        telegram_haber_ver(mesaj)

        sulama_kayitlari.insert(0, kayit)
        if len(sulama_kayitlari) > 10:
            sulama_kayitlari.pop()

        logs_col.insert_one({
            "nem": nem,
            "zaman": datetime.datetime.now(),
            "type": "sensor"
        })

        # ---------------- 🔋 BATARYA KONTROL (YENİ EKLENDİ) ----------------
        # Eğer MQTT mesajı JSON ise batarya kontrolü
        try:
            import json
            data = json.loads(gelen)

            if "batarya" in data:
                batarya = int(data["batarya"])

                if batarya < 20 and not son_batarya_uyarisi:
                    telegram_haber_ver(f"⚡ DÜŞÜK BATARYA %{batarya} - Şarj et!")
                    son_batarya_uyarisi = True

                elif batarya >= 20:
                    son_batarya_uyarisi = False

        except:
            pass

    except Exception as e:
        print(f"MQTT Hatası: {e}", flush=True)

# --- MAIN ---
if __name__ == "__main__":

    threading.Thread(
        target=lambda: HTTPServer(('0.0.0.0', 10000), SimpleHandler).serve_forever(),
        daemon=True
    ).start()

    threading.Thread(target=bekci_kopegi, daemon=True).start()
    threading.Thread(target=bot.infinity_polling, daemon=True).start()

    telegram_haber_ver("🚀 Sistem Başlatıldı")

    while True:
        try:
            client = mqtt.Client(client_id="Render_Saksi")
            client.on_connect = on_connect
            client.on_message = on_message

            client.connect(MQTT_BROKER, 1883, 60)
            client.loop_forever()

        except Exception as e:
            print(f"MQTT Hatası: {e}", flush=True)
            time.sleep(10)
