"""
Smart Plant Watering System - Cloud Backend
ESP32 → MQTT → Bu Servis → MongoDB + Telegram

Render.com üzerinde çalışan backend servisi.
MQTT ile ESP32'den nem verisi alır, MongoDB'ye kaydeder, Telegram ile bildirim gönderir.
"""

import os
import time
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import paho.mqtt.client as mqtt
import telebot
from pymongo import MongoClient
import datetime
from dotenv import load_dotenv

# Şifreleri .env dosyasından veya Render environment'tan yükle
load_dotenv() 

# Hassas bilgiler - Render'ın Environment Variables paneline yazılacak
TOKEN = os.getenv("TELEGRAM_TOKEN")
ID = os.getenv("TELEGRAM_CHAT_ID")
MONGO_URI = os.getenv("MONGO_URI")

# MQTT broker ayarları (HiveMQ public broker kullanıyoruz)
MQTT_BROKER = "broker.hivemq.com"
MQTT_TOPIC = "ev/saksi/nem"  # ESP32'nin publish ettiği topic

# Saat dilimi ayarı (Türkiye saati)
os.environ['TZ'] = 'Europe/Istanbul'
if hasattr(time, 'tzset'):
    time.tzset()

# MongoDB bağlantısı
try:
    mongo_client = MongoClient(MONGO_URI)
    db = mongo_client["AkilliSaksiDB"]
    logs_col = db["NemGecmisi"]  # Nem ölçümlerini buraya yazıyoruz
    print("MongoDB Bağlantısı Başarılı! ✅", flush=True)
except Exception as e:
    print(f"MongoDB Bağlantı Hatası: {e}", flush=True)

# Telegram bot başlat
bot = telebot.TeleBot(TOKEN)

# Global değişkenler
son_mesaj_zamani = time.time()  # ESP32'den son mesaj ne zaman geldi
bekci_uyarisi_verildi = False   # Watchdog alarmı verildi mi
sulama_kayitlari = []           # Son 10 kayıt (telegram raporu için)
son_nem = 0                     # Önceki nem değeri (artış kontrolü için)

def telegram_haber_ver(mesaj):
    """Telegram'a bildirim gönder"""
    try:
        bot.send_message(ID, mesaj)
        print(f"TELEGRAM: {mesaj}", flush=True)
    except Exception as e:
        print(f"TELEGRAM HATASI: {e}", flush=True)

@bot.message_handler(commands=['rapor'])
def rapor_gonder(message):
    """
    /rapor komutu - Son 10 ölçüm kaydını gönder
    Kullanım: Telegram'dan /rapor yaz
    """
    try:
        if not sulama_kayitlari:
            bot.reply_to(message, "📊 Henüz bir sulama kaydı bulunamadı.")
        else:
            rapor_metni = "📊 *Son 10 Ölçüm Kaydı:*\n\n" + "\n".join(sulama_kayitlari)
            bot.send_message(message.chat.id, rapor_metni, parse_mode="Markdown")
    except Exception as e:
        print(f"Rapor Hatası: {e}", flush=True)

# Render.com health check için basit HTTP server
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Saksi Sistemi Aktif ve Bulut Uyumlu!")
    
    def log_message(self, format, *args):
        pass  # Log bastırma

def bekci_kopegi():
    """
    Watchdog thread - ESP32 bağlantı kontrolü
    10 dakika mesaj gelmezse alarm ver
    """
    global son_mesaj_zamani, bekci_uyarisi_verildi
    while True:
        try:
            gecen_sure = time.time() - son_mesaj_zamani
            
            # 10 dakika mesaj yoksa uyar
            if gecen_sure > 600 and not bekci_uyarisi_verildi:
                telegram_haber_ver("🚨 BEKÇİ UYARISI: Saksıdan 10 dakikadır veri alınamıyor!")
                bekci_uyarisi_verildi = True
            
            # Mesaj geldi, alarm flagini resetle
            if gecen_sure < 600:
                bekci_uyarisi_verildi = False
        except:
            pass
        time.sleep(60)  # Her dakika kontrol et

# MQTT callback: Broker'a bağlanınca çalışır
def on_connect(client, userdata, flags, rc):
    """
    MQTT bağlantı başarılı olunca topic'e subscribe ol
    rc: 0=başarılı, diğer değerler hata
    """
    print(f"MQTT Bağlantı Durumu: {rc}", flush=True)
    client.subscribe(MQTT_TOPIC)

# MQTT callback: Mesaj geldiğinde çalışır (ASIL İŞ BURADA)
def on_message(client, userdata, msg):
    """
    ESP32'den MQTT mesajı geldiğinde çalışır
    
    Mesaj tipleri:
    1. Sayısal (nem): "45" -> Sensör verisi
    2. Text (hata): "HATA: Su Gelmiyor!" -> Sistem mesajı
    
    İşlem akışı:
    ESP32 publish eder -> HiveMQ broker -> Bu fonksiyon -> MongoDB + Telegram
    """
    global son_nem, son_mesaj_zamani
    
    try:
        son_mesaj_zamani = time.time()  # Watchdog için timestamp güncelle
        gelen_veri = msg.payload.decode()  # Byte'tan string'e çevir
        
        # Text mesaj mı (hata mesajı gibi)
        if not gelen_veri.isdigit():
            telegram_haber_ver(gelen_veri)
            logs_col.insert_one({
                "cihaz": "Saksi_1",
                "mesaj": gelen_veri,
                "tur": "SİSTEM_NOTU",
                "zaman": datetime.datetime.now()
            })
            return
        
        # Sayısal veri (nem ölçümü)
        nem = int(gelen_veri)
        zaman = time.strftime('%d/%m %H:%M:%S')

        # Kayıt tipini belirle
        kayit_turu = "NORMAL_OKUMA"
        ek_not = ""

        if nem < 40:
            # Kritik nem seviyesi
            kayit_turu = "KRITIK_DURUM"
            ek_not = "Sulama Tetiklendi"
        elif son_nem != 0 and (nem - son_nem) > 10:
            # Ani artış = sulama yapıldı
            kayit_turu = "SULAMA_YAPILDI"
            ek_not = "Sulama Sonrası Artış"

        # MongoDB'ye kaydet
        veri_paketi = {
            "cihaz": "Saksi_1",
            "nem": nem,
            "tur": kayit_turu, 
            "not": ek_not,
            "zaman": datetime.datetime.now()
        }
        logs_col.insert_one(veri_paketi)
        
        # Telegram mesajını hazırla
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
        
        # Local history güncelle (son 10 kayıt)
        sulama_kayitlari.insert(0, kayit)
        son_nem = nem
        
        if len(sulama_kayitlari) > 10:
            sulama_kayitlari.pop()

    except Exception as e:
        print(f"Mesaj İşleme Hatası: {e}", flush=True)

# Ana program başlangıcı
if __name__ == "__main__":
    # Thread 1: HTTP health check (Render.com için gerekli)
    threading.Thread(
        target=lambda: HTTPServer(('0.0.0.0', 10000), SimpleHandler).serve_forever(),
        daemon=True
    ).start()
    
    # Thread 2: Watchdog (bağlantı kontrolü)
    threading.Thread(
        target=bekci_kopegi,
        daemon=True
    ).start()
    
    # Thread 3: Telegram bot (komut dinleyici)
    threading.Thread(
        target=bot.infinity_polling,
        daemon=True
    ).start()
    
    # Başlangıç bildirimi
    telegram_haber_ver("🚀 SİSTEM ZIRHLI VE GÜVENLİ OLARAK BAŞLATILDI!")
    
    # Ana loop: MQTT dinleme (blocking)
    # Bağlantı kopunca otomatik yeniden bağlanır
    while True:
        try:
            # MQTT client oluştur
            client = mqtt.Client(
                client_id="Render_Saksi_Merkezi",
                clean_session=False  # Subscription'ları koru
            )
            
            client.on_connect = on_connect  # Bağlanınca ne yapsın
            client.on_message = on_message  # Mesaj gelince ne yapsın
            
            # Broker'a bağlan (HiveMQ public)
            client.connect(MQTT_BROKER, 1883, 60)
            
            # Sonsuz döngü - mesajları dinle
            client.loop_forever()
            
        except Exception as e:
            print(f"MQTT Hatası: {e}. Tekrar deneniyor...", flush=True)
            time.sleep(10)  # 10 saniye bekle, tekrar dene


