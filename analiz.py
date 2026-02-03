import paho.mqtt.client as mqtt
import requests
import time
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- NİHAİ AYARLAR ---
TOKEN = "8595769743:AAF0l1t9xfYZDoc5AQ04jbKyG21Q-ZTf0e0"
ID = "8504915615"
MQTT_BROKER = "broker.hivemq.com"
MQTT_TOPIC = "ev/saksi/nem"

# Bekçi değişkenleri
son_mesaj_zamani = time.time()
bekci_uyarisi_verildi = False

def telegram_haber_ver(mesaj):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        requests.get(url, params={"chat_id": ID, "text": mesaj}, timeout=10)
    except:
        pass

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Saksi Sistemi Aktif!")

def bekci_kopegi():
    global son_mesaj_zamani, bekci_uyarisi_verildi
    while True:
        try:
            gecen_sure = time.time() - son_mesaj_zamani
            # 10 dakika boyunca veri gelmezse (600 saniye)
            if gecen_sure > 600 and not bekci_uyarisi_verildi:
                telegram_haber_ver("🚨 BEKÇİ UYARISI: Saksıdan 10 dakikadır veri alınamıyor! ESP32'yi kontrol et.")
                bekci_uyarisi_verildi = True
            
            # Veri gelirse uyarı durumunu sıfırla
            if gecen_sure < 600:
                bekci_uyarisi_verildi = False
        except:
            pass
        time.sleep(60) # Dakikada bir kontrol et

def on_message(client, userdata, msg):
    global son_mesaj_zamani
    try:
        son_mesaj_zamani = time.time() # Zamanı güncelle
        nem = msg.payload.decode()
        telegram_haber_ver(f"🪴 Nem Oranı: %{nem}")
    except:
        pass

if __name__ == "__main__":
    # 1. Render Uyanık Tutucu (HTTP Server)
    threading.Thread(target=lambda: HTTPServer(('0.0.0.0', 10000), SimpleHandler).serve_forever(), daemon=True).start()
    
    # 2. Bekçi Köpeği (Watchdog)
    threading.Thread(target=bekci_kopegi, daemon=True).start()
    
    # 3. Sistemin başladığını haber ver
    telegram_haber_ver("🚀 SİSTEM VE BEKÇİ KÖPEĞİ DEVREYE GİRDİ!")
    
    # 4. MQTT Ana Döngü
    while True:
        try:
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
            client.on_message = on_message
            client.connect(MQTT_BROKER, 1883, 60)
            client.subscribe(MQTT_TOPIC)
            client.loop_forever()
        except:
            print("MQTT Bağlantısı başarısız, 10sn sonra tekrar denenecek...")
            time.sleep(10)
