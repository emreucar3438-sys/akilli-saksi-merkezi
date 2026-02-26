import os
import time
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import paho.mqtt.client as mqtt
import telebot
from pymongo import MongoClient
import datetime
from dotenv import load_dotenv

# --- GÜVENLİK ZIRHI ---
# Render üzerindeki 'Environment' panelinden şifreleri okur.
load_dotenv() 

# --- AYARLAR (ŞİFRELER GİZLENDİ - RENDER'DAN ÇEKİLECEK) ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
ID = os.getenv("TELEGRAM_CHAT_ID")
MONGO_URI = os.getenv("MONGO_URI")

MQTT_BROKER = "broker.hivemq.com"
MQTT_TOPIC = "ev/saksi/nem"

# --- SAAT DÜZELTME ---
os.environ['TZ'] = 'Europe/Istanbul'
if hasattr(time, 'tzset'):
    time.tzset()

# --- MONGODB BAĞLANTISI ---
try:
    mongo_client = MongoClient(MONGO_URI)
    db = mongo_client["AkilliSaksiDB"]
    logs_col = db["NemGecmisi"]
    print("MongoDB Bağlantısı Başarılı! ✅", flush=True)
except Exception as e:
    print(f"MongoDB Bağlantı Hatası: {e}", flush=True)

bot = telebot.TeleBot(TOKEN)

son_mesaj_zamani = time.time()
bekci_uyarisi_verildi = False
sulama_kayitlari = [] 
son_nem = 0 

def telegram_haber_ver(mesaj):
    try:
        bot.send_message(ID, mesaj)
        print(f"TELEGRAM: {mesaj}", flush=True)
    except Exception as e:
        print(f"TELEGRAM HATASI: {e}", flush=True)

@bot.message_handler(commands=['rapor'])
def rapor_gonder(message):
    try:
        if not sulama_kayitlari:
            bot.reply_to(message, "📊 Henüz bir sulama kaydı bulunamadı aga.")
        else:
            rapor_metni = "📊 *Son 10 Ölçüm Kaydı:*\n\n" + "\n".join(sulama_kayitlari)
            bot.send_message(message.chat.id, rapor_metni, parse_mode="Markdown")
    except Exception as e:
        print(f"Rapor Hatası: {e}", flush=True)

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Saksi Sistemi Aktif ve Bulut Uyumlu!")

def bekci_kopegi():
    global son_mesaj_zamani, bekci_uyarisi_verildi
    while True:
        try:
            gecen_sure = time.time() - son_mesaj_zamani
            if gecen_sure > 600 and not bekci_uyarisi_verildi:
                telegram_haber_ver("🚨 BEKÇİ UYARISI: Saksıdan 10 dakikadır veri alınamıyor!")
                bekci_uyarisi_verildi = True
            if gecen_sure < 600:
                bekci_uyarisi_verildi = False
        except:
            pass
        time.sleep(60)

# ← YENİ EKLENEN FONKSİYON
def on_connect(client, userdata, flags, rc):
    print(f"MQTT Bağlantı Durumu: {rc}", flush=True)
    client.subscribe(MQTT_TOPIC)  # Bağlanınca hemen konuya abone ol

def on_message(client, userdata, msg):
    global son_nem, son_mesaj_zamani
    try:
        son_mesaj_zamani = time.time()
        gelen_veri = msg.payload.decode()
        
        if not gelen_veri.isdigit():
            telegram_haber_ver(gelen_veri)
            logs_col.insert_one({
                "cihaz": "Saksi_1",
                "mesaj": gelen_veri,
                "tur": "SİSTEM_NOTU",
                "zaman": datetime.datetime.now()
            })
            return 
        
        nem = int(gelen_veri)
        zaman = time.strftime('%d/%m %H:%M:%S')

        kayit_turu = "NORMAL_OKUMA"
        ek_not = ""

        if nem < 40:
            kayit_turu = "KRITIK_DURUM"
            ek_not = "Sulama Tetiklendi"
        elif son_nem != 0 and (nem - son_nem) > 10:
            kayit_turu = "SULAMA_YAPILDI"
            ek_not = "Sulama Sonrası Artış"

        veri_paketi = {
            "cihaz": "Saksi_1",
            "nem": nem,
            "tur": kayit_turu, 
            "not": ek_not,
            "zaman": datetime.datetime.now()
        }
        logs_col.insert_one(veri_paketi)
        
        if nem < 40:
            mesaj = f"🚨 Nem %{nem}! Durum KRİTİK, sulama başlıyor..."
            kayit = f"🚨 {zaman} -> KRİTİK: %{nem}"
        elif nem > son_nem and son_nem != 0 and (nem - son_nem) > 10:
            mesaj = f"🌿 Yeni Nem %{nem}"
            kayit = f"✅ {zaman} -> Yeni Nem: %{nem}"
        else:
            mesaj = f"🌿 Güncel Nem %{nem}"
            kayit = f"✅ {zaman} -> Normal: %{nem}"
        
        telegram_haber_ver(mesaj)
        sulama_kayitlari.insert(0, kayit)
        son_nem = nem
        
        if len(sulama_kayitlari) > 10:
            sulama_kayitlari.pop()

    except Exception as e:
        print(f"Mesaj İşleme Hatası: {e}", flush=True)

if __name__ == "__main__":
    threading.Thread(target=lambda: HTTPServer(('0.0.0.0', 10000), SimpleHandler).serve_forever(), daemon=True).start()
    threading.Thread(target=bekci_kopegi, daemon=True).start()
    threading.Thread(target=bot.infinity_polling, daemon=True).start()
    
    telegram_haber_ver("🚀 SİSTEM ZIRHLI VE GÜVENLİ OLARAK BAŞLATILDI!")
    
    while True:
        try:
            # ← DEĞİŞEN KISIM: Client oluşturma ve bağlantı ayarları
            client = mqtt.Client(client_id="Render_Saksi_Merkezi_Aga", clean_session=False)
            client.on_connect = on_connect  # ← Bağlantı kontrolü eklendi
            client.on_message = on_message
            client.connect(MQTT_BROKER, 1883, 60)
            client.loop_forever()
        except Exception as e:
            print(f"MQTT Hatası: {e}. Tekrar deneniyor...", flush=True)
            time.sleep(10)
