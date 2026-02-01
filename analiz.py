import paho.mqtt.client as mqtt
from datetime import datetime, timedelta
import time
import requests
import ssl
import threading

# --- AYARLAR (HIVE MQ & TELEGRAM) ---
BROKER_URL = "c7a265635c0947dd9338de41699abf4b.s1.eu.hivemq.cloud"
MQTT_USER = "emre_saksi"
MQTT_PASS = "Kayseri.3438"
TELEGRAM_TOKEN = "8361884405:AAHZMyTnNLHWuNKkBhJkPLRW7xRtfzQN-SM"
CHAT_ID = "8504915615"
PUSH_KEY = "MWbLO2lB7DuSJBKee5Zk"

# --- TOPIC AYARLARI ---
TOPIC_SENSOR = "esp32/sensor"   
TOPIC_KOMUT = "esp32/komut"
TOPIC_BILDIRIM = "saksi/bildirim"

# --- DEĞİŞKENLER ---
son_gorulme = datetime.now()
son_telegram_vakti = 0
bekci_kilit = threading.Lock()

def telegram_gonder(mesaj):
    global son_telegram_vakti
    simdi = time.time()
    
    # Anti-Spam: 15 saniyede bir mesaj sınırı
    if (simdi - son_telegram_vakti) < 15:
        return

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": mesaj}, timeout=10)
        son_telegram_vakti = simdi
    except Exception as e: 
        print(f"❌ Telegram Hatası: {e}")

def bekci_kopegi():
    global son_gorulme
    while True:
        time.sleep(30)
        with bekci_kilit:
            if datetime.now() > son_gorulme + timedelta(seconds=120):
                telegram_gonder("⚠️ KRİTİK: Cihaz ile bağlantı kesildi! (Çevrimdışı)")
                son_gorulme = datetime.now()

def on_message(client, userdata, message):
    global son_gorulme, son_telegram_vakti
    payload = message.payload.decode("utf-8")
    zaman = datetime.now().strftime("%H:%M:%S")
    
    with bekci_kilit:
        son_gorulme = datetime.now()

    # 1. Senaryo: Cihazdan Nem Verisi Gelirse
    if message.topic == TOPIC_SENSOR:
        try:
            nem = int(payload)
            print(f"[{zaman}] Nem: %{nem}")
            if nem < 40:
                print(f"🚨 KRİTİK NEM: %{nem}! Sulama tetikleniyor...")
                client.publish(TOPIC_KOMUT, "SULA")
                telegram_gonder(f"💧 Nem %{nem}'ye düştü. Sulama başlatıldı!")
        except:
            pass

    # 2. Senaryo: Cihazdan Özel Bildirim Gelirse
    elif message.topic == TOPIC_BILDIRIM:
        telegram_gonder(f"📢 Cihaz Mesajı: {payload}")

# --- MQTT KURULUMU ---
client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
client.username_pw_set(MQTT_USER, MQTT_PASS)
client.tls_set(cert_reqs=ssl.CERT_NONE)
client.on_message = on_message

# Bekçiyi başlat
threading.Thread(target=bekci_kopegi, daemon=True).start()

try:
    print("🚀 Akıllı Saksı Merkezi Çevrimiçi. Dinleme başlıyor...")
    client.connect(BROKER_URL, 8883)
    client.subscribe([(TOPIC_SENSOR, 0), (TOPIC_BILDIRIM, 0)])
    telegram_gonder("🚀 Akıllı Saksı Sistemi Bulut Üzerinden Aktif!")
    client.loop_forever()
except Exception as e:
    print(f"❌ Bağlantı Hatası: {e}")
