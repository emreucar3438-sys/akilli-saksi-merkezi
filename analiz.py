import paho.mqtt.client as mqtt
from datetime import datetime, timedelta
import time, requests, ssl, threading, os
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- AYARLAR (ESP32 İLE TAM UYUMLU) ---
BROKER_URL = "c7a265635c0947dd9338de41699abf4b.s1.eu.hivemq.cloud"
MQTT_USER = "emre_saksi"
MQTT_PASS = "Kayseri.3438"
TELEGRAM_TOKEN = "8361884405:AAHZMyTnNLHWuNKkBhJkPLRW7xRtfzQN-SM"
CHAT_ID = "8504915615"

# --- DEĞİŞKENLER ---
son_gorulme = datetime.now()
son_telegram_vakti = 0
bekci_kilit = threading.Lock()

# --- RENDER İÇİN YAŞAM SİNYALİ SUNUCUSU ---
# Render, dışarıdan bir portun dinlenmesini ister. Bu sınıf onu sağlar.
class RenderKandirici(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"Saksi Sistemi Online ve MQTT Dinliyor!")

def run_render_server():
    # Render'ın verdiği portu al, yoksa 10000 kullan
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), RenderKandirici)
    print(f"--- 🛡️ Render Yaşam Sinyali {port} Portunda Başlatıldı ---")
    server.serve_forever()

def telegram_gonder(mesaj):
    global son_telegram_vakti
    simdi = time.time()
    
    if "Nem:" in mesaj and (simdi - son_telegram_vakti) < 15:
        print(f"🚫 Spam engellendi: {mesaj}")
        return

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": mesaj}
        r = requests.post(url, data=payload, timeout=10)
        son_telegram_vakti = simdi
        print(f"📡 Telegram Gönderildi: {mesaj} (Durum: {r.status_code})")
    except Exception as e: 
        print(f"❌ Telegram Hatası: {e}")

def bekci_kopegi():
    global son_gorulme
    while True:
        time.sleep(30)
        with bekci_kilit:
            if datetime.now() > son_gorulme + timedelta(seconds=600):
                uyari = "⚠️ KRİTİK: Cihazdan 10 dakikadır haber alınamıyor! Pil veya WiFi kontrolü yapın."
                telegram_gonder(uyari)
                son_gorulme = datetime.now()

def on_message(client, userdata, message):
    global son_gorulme
    with bekci_kilit: 
        son_gorulme = datetime.now()
    
    try:
        payload = message.payload.decode("utf-8")
        print(f"📩 Gelen [{message.topic}]: {payload}")
        
        if message.topic == "saksi/bildirim":
            telegram_gonder(payload)
    except Exception as e:
        print(f"❌ Mesaj Hatası: {e}")

def on_disconnect(client, userdata, rc):
    print("📡 Bağlantı koptu, yeniden bağlanılıyor...")
    if rc != 0:
        try:
            client.reconnect()
        except:
            pass

# --- MQTT KURULUMU ---
client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
client.username_pw_set(MQTT_USER, MQTT_PASS)
client.tls_set(cert_reqs=ssl.CERT_NONE)
client.on_message = on_message
client.on_disconnect = on_disconnect

# 1. Bekçiyi yan kolda başlat
threading.Thread(target=bekci_kopegi, daemon=True).start()

# 2. RENDER YAŞAM SİNYALİNİ (HTTP Sunucu) yan kolda başlat
# Bu sayede Render "Bu servis çalışıyor" diyecek ve bizi kapatmayacak.
threading.Thread(target=run_render_server, daemon=True).start()

try:
    print("🚀 Akıllı Saksı Sistemi Başlatıldı...")
    client.connect(BROKER_URL, 8883)
    client.subscribe("saksi/bildirim")
    telegram_gonder("🚀 Akıllı Saksı Sistemi Çevrimiçi! (Bulut Sunucu Aktif)")
    client.loop_forever()
except Exception as e: 
    print(f"❌ Ana Hata: {e}")

