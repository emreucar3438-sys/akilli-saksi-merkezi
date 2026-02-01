import paho.mqtt.client as mqtt
from datetime import datetime, timedelta
import time, requests, ssl, threading

# --- AYARLAR ---
BROKER_URL = "c7a265635c0947dd9338de41699abf4b.s1.eu.hivemq.cloud"
MQTT_USER = "emre_saksi"
MQTT_PASS = "Kayseri.3438"
TELEGRAM_TOKEN = "8361884405:AAHZMyTnNLHWuNKkBhJkPLRW7xRtfzQN-SM"
CHAT_ID = "8504915615"

# --- DEĞİŞKENLER ---
son_gorulme = datetime.now()
son_telegram_vakti = 0
bekci_kilit = threading.Lock()

def telegram_gonder(mesaj):
    global son_telegram_vakti
    simdi = time.time()
    
    # 🛡️ ANTI-SPAM: Nem mesajları peş peşe gelirse 15 saniye barajı uygula
    if "Nem:" in mesaj and (simdi - son_telegram_vakti) < 15:
        print(f"🚫 Spam engellendi: {mesaj}")
        return

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": mesaj}, timeout=10)
        son_telegram_vakti = simdi
    except Exception as e: 
        print(f"❌ Telegram Hatası: {e}")

def log_yaz(topic, mesaj):
    zaman = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open("sulama_gunlugu.txt", "a", encoding="utf-8") as f:
        f.write(f"[{zaman}] {topic}: {mesaj}\n")

def bekci_kopegi():
    global son_gorulme
    while True:
        time.sleep(15)
        with bekci_kilit:
            # 🔔 120 saniye sınırı (Gereksiz uyarıları önlemek için ideal süre)
            if datetime.now() > son_gorulme + timedelta(seconds=120):
                uyari = ("⚠️ KRİTİK UYARI: Cihaz ile bağlantı kesildi!\n\n"
                         "Olası Nedenler:\n"
                         "1- Pil bitmiş olabilir.\n"
                         "2- WiFi kopmuş olabilir.\n"
                         "3- Cihaz uyanamıyor.")
                telegram_gonder(uyari)
                son_gorulme = datetime.now() # Mesajı atınca süreyi sıfırla

def on_message(client, userdata, message):
    global son_gorulme
    with bekci_kilit: 
        son_gorulme = datetime.now() # Her mesajda "cihaz yaşıyor" diyoruz
    
    payload = message.payload.decode("utf-8")
    log_yaz(message.topic, payload)
    print(f"📩 Gelen [{message.topic}]: {payload}")
    
    if message.topic == "saksi/bildirim":
        telegram_gonder(payload)

# MQTT Yapılandırması
client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
client.username_pw_set(MQTT_USER, MQTT_PASS)
client.tls_set(cert_reqs=ssl.CERT_NONE)
client.on_message = on_message

# Bekçiyi yan thread olarak başlat
threading.Thread(target=bekci_kopegi, daemon=True).start()

try:
    print("🚀 Akıllı Saksı Merkezi Çevrimiçi. Dinleme başlıyor...")
    client.connect(BROKER_URL, 8883)
    client.subscribe("saksi/#")
    telegram_gonder("🚀 Akıllı Saksı Sistemi Çevrimiçi!")
    client.loop_forever()
except Exception as e: 
    print(f"❌ Bağlantı Hatası: {e}")
