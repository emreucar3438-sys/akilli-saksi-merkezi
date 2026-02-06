import os
import time
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import paho.mqtt.client as mqtt
import telebot
from pymongo import MongoClient
import datetime

# --- SAAT DÜZELTME ---
os.environ['TZ'] = 'Europe/Istanbul'
if hasattr(time, 'tzset'):
    time.tzset()

# --- AYARLAR ---
TOKEN = "8595769743:AAF0lit9xFYZDoc5AQO4jbKyG2lQ-ZTfOe0"
ID = "8504915615"
MQTT_BROKER = "broker.hivemq.com"
MQTT_TOPIC = "ev/saksi/nem"

# --- MONGODB BAĞLANTISI ---
MONGO_URI = "mongodb+srv://emreucar3438_db_user:Kayseri.3438@cluster0.r39oc0p.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
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
        self.wfile.write(b"Saksi Sistemi Aktif ve Raporlama Hazir!")

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

# --- GÜNCELLENEN AKILLI MESAJ İŞLEYİCİ (MONGODB DESTEKLİ) ---
def on_message(client, userdata, msg):
    global son_nem, son_mesaj_zamani
    try:
        son_mesaj_zamani = time.time()
        gelen_veri = msg.payload.decode()
        
        # 1. Eğer gelen veri sayı DEĞİLSE (Hata mesajı, emoji vs.)
        if not gelen_veri.isdigit():
            telegram_haber_ver(gelen_veri)
            # Hataları da "SİSTEM_NOTU" olarak veri tabanına yazalım ki AI bilsin
            logs_col.insert_one({
                "cihaz": "Saksi_1",
                "mesaj": gelen_veri,
                "tur": "SİSTEM_NOTU",
                "zaman": datetime.datetime.now()
            })
            return 
        
        # 2. Eğer gelen veri sayı ise (Nem rakamı)
        nem = int(gelen_veri)
        zaman = time.strftime('%d/%m %H:%M:%S')

        # --- AI İÇİN AKILLI KAYIT VE ETİKETLEME ---
        kayit_turu = "NORMAL_OKUMA"
        ek_not = ""

        if nem < 40:
            kayit_turu = "KRITIK_DURUM"
            ek_not = "Sulama Tetiklendi"
        elif son_nem != 0 and (nem - son_nem) > 10:
            kayit_turu = "SULAMA_YAPILDI"
            ek_not = "Sulama Sonrası Artış"
            telegram_haber_ver("💧 Sulama başarılı! Nem yükseldi.")

        # MongoDB'ye detaylı kayıt (Gelecekte AI eğitmek için altın değerinde)
        veri_paketi = {
            "cihaz": "Saksi_1",
            "nem": nem,
            "tur": kayit_turu, 
            "not": ek_not,
            "zaman": datetime.datetime.now()
        }
        logs_col.insert_one(veri_paketi)
        print(f"MongoDB: {kayit_turu} kaydedildi. 🏰", flush=True)
        
        # --- TELEGRAM RAPOR MANTIĞI ---
        if nem < 40:
            mesaj = f"🚨 Nem %{nem}! Durum KRİTİK, sulama başlıyor..."
            kayit = f"🚨 {zaman} -> KRİTİK: %{nem}"
        elif kayit_turu == "SULAMA_YAPILDI":
            mesaj = f"🌿 Sulama Sonrası Nem: %{nem}"
            kayit = f"💧 {zaman} -> SULAMA: %{nem}"
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
    
    telegram_haber_ver("🚀 SİSTEM AKTİF! Hem Telegram hem MongoDB hazır.")
    
    while True:
        try:
            client = mqtt.Client() 
            client.on_message = on_message
            client.connect(MQTT_BROKER, 1883, 60)
            client.subscribe(MQTT_TOPIC)
            client.loop_forever()
        except Exception as e:
            print(f"MQTT Hatası: {e}. Tekrar deneniyor...", flush=True)
            time.sleep(10)
