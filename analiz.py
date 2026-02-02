import paho.mqtt.client as mqtt
import time, requests, ssl, threading
from datetime import datetime, timedelta

# --- AYARLAR ---
BROKER_URL = "c7a265635c0947dd9338de41699abf4b.s1.eu.hivemq.cloud"
MQTT_USER = "emre_saksi"
MQTT_PASS = "Kayseri.3438"
TELEGRAM_TOKEN = "8361884405:AAHZMyTnNLHWuNKkBhJkPLRW7xRtfzQN-SM"
CHAT_ID = "8504915615"

son_gorulme = datetime.now()
bekci_kilit = threading.Lock()

def telegram_gonder(mesaj):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": mesaj}
        r = requests.post(url, data=payload, timeout=10)
        print(f"📡 Telegram Durumu: {r.status_code}")
    except Exception as e:
        print(f"❌ Telegram Hatası: {e}")

def on_message(client, userdata, message):
    global son_gorulme
    payload = message.payload.decode("utf-8")
    print(f"📩 Gelen Mesaj: {payload}")
    
    with bekci_kilit:
        son_gorulme = datetime.now()
    
    if message.topic == "saksi/bildirim":
        telegram_gonder(payload)

def bekci_kopegi():
    global son_gorulme
    while True:
        time.sleep(30)
        with bekci_kilit:
            # 5 dakika (300sn) veri gelmezse uyar
            if datetime.now() > son_gorulme + timedelta(seconds=300):
                telegram_gonder("⚠️ KRİTİK: Cihazdan 5 dakikadır haber alınamıyor!")
                son_gorulme = datetime.now()

# MQTT Kurulumu
client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
client.username_pw_set(MQTT_USER, MQTT_PASS)
client.tls_set(cert_reqs=ssl.CERT_NONE)
client.on_message = on_message

threading.Thread(target=bekci_kopegi, daemon=True).start()

try:
    print("🚀 Sistem başlatıldı...")
    client.connect(BROKER_URL, 8883)
    client.subscribe("saksi/bildirim")
    telegram_gonder("🚀 Akıllı Saksı Sistemi Çevrimiçi!")
    client.loop_forever()
except Exception as e:
    print(f"❌ Ana Hata: {e}")
