import paho.mqtt.client as mqtt
import requests
import time
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- AYARLAR ---
TOKEN = "8361884405:AAHZMyTnLHWuNKkBhJkPLRW7xRtfZQN-SM"
ID = "8504915615"
MQTT_BROKER = "broker.hivemq.com"
MQTT_TOPIC = "ev/saksi/nem"

# Bekçi değişkenleri
son_mesaj_zamani = time.time()
bekci_uyarisi_verildi = False

# --- TELEGRAM MESAJ GÖNDERİCİ ---
def telegram_haber_ver(mesaj):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        requests.get(url, params={"chat_id": ID, "text": mesaj}, timeout=10)
    except Exception as e:
        print(f"Telegram Hatası: {e}")

# --- RENDER UYANIK TUTUCU (HTTP) ---
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Saksi Sistemi Online!")

# --- BEKÇİ KÖPEĞİ (WATCHDOG) ---
def bekci_kopegi():
    global son_mesaj_zamani, bekci_uyarisi_verildi
    while True:
        try:
            gecen_sure = time.time() - son_mesaj_zamani
            # 10 dakika (600 saniye) veri gelmezse uyar
            if gecen_sure > 600 and not bekci_uyarisi_verildi:
                telegram_haber_ver("🚨 DIKKAT: Saksıdan 10 dakikadır veri alınamıyor! ESP32'yi kontrol et.")
                bekci_uyarisi_verildi = True
            
            # Veri gelirse uyarıyı sıfırla
            if gecen_sure < 600:
                bekci_uyarisi_verildi = False
        except:
            pass
        time.sleep(60)

# --- MQTT MESAJ GELDİĞİNDE ---
def on_message(client, userdata, msg):
    global son_mesaj_zamani
    try:
        son_mesaj_zamani = time.time() # Zamanı güncelle
        nem = msg.payload.decode()
        telegram_haber_ver(f"🪴 Nem Oranı: %{nem}")
    except Exception as e:
        print(f"Mesaj İşleme Hatası: {e}")

# --- ANA MOTOR ---
if __name__ == "__main__":
    # 1. HTTP Server'ı Arka Planda Başlat
    threading.Thread(target=lambda: HTTPServer(('0.0.0.0', 10000), SimpleHandler).serve_forever(), daemon=True).start()
    
    # 2. Bekçi Köpeğini Arka Planda Başlat
    threading.Thread(target=bekci_kopegi, daemon=True).start()
    
    # 3. Sistem Başladı Müjdesi
    telegram_haber_ver("🚀 RENDER SİSTEMİ (BEKÇİ DAHİL) BAŞLATILDI!")
    
    # 4. MQTT V2 Bağlantı ve Hata Kontrolü
    while True: # Bağlantı koparsa otomatik yeniden denemesi için
        try:
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
            client.on_message = on_message
            
            client.connect(MQTT_BROKER, 1883, 60)
            client.subscribe(MQTT_TOPIC)
            print("🚀 MQTT Bağlantısı Başarılı!")
            client.loop_forever()
        except Exception as e:
            print(f"Bağlantı koptu, 10sn sonra tekrar denenecek: {e}")
            time.sleep(10)
