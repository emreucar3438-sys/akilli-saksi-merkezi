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

# --- TELEGRAM HABER VERİCİ (LOG DESTEKLİ) ---
def telegram_haber_ver(mesaj):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        r = requests.get(url, params={"chat_id": ID, "text": mesaj}, timeout=10)
        # BU SATIR SAYESİNDE SORUNU GÖRECEĞİZ:
        print(f"TELEGRAM CEVABI: {r.text}", flush=True)
    except Exception as e:
        print(f"BAĞLANTI HATASI: {e}", flush=True)

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Saksi Sistemi Aktif!")

# --- BEKÇİ KÖPEĞİ ---
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

# --- MQTT MESAJ GELİNCE ---
def on_message(client, userdata, msg):
    global son_mesaj_zamani
    try:
        son_mesaj_zamani = time.time()
        nem = msg.payload.decode()
        telegram_haber_ver(f"🪴 Nem Oranı: %{nem}")
    except Exception as e:
        print(f"Mesaj işleme hatası: {e}", flush=True)

if __name__ == "__main__":
    # 1. HTTP Server
    threading.Thread(target=lambda: HTTPServer(('0.0.0.0', 10000), SimpleHandler).serve_forever(), daemon=True).start()
    
    # 2. Bekçi Köpeği
    threading.Thread(target=bekci_kopegi, daemon=True).start()
    
    # 3. Başlangıç Mesajı
    telegram_haber_ver("🚀 SİSTEM VE BEKÇİ KÖPEĞİ DEVREYE GİRDİ!")
    
    # 4. MQTT
    while True:
        try:
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
            client.on_message = on_message
            client.connect(MQTT_BROKER, 1883, 60)
            client.subscribe(MQTT_TOPIC)
            print("MQTT Bağlantısı kuruldu, dinleniyor...", flush=True)
            client.loop_forever()
        except Exception as e:
            print(f"MQTT Hatası: {e}. 10 saniye sonra tekrar denenecek...", flush=True)
            time.sleep(10)
