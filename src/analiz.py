import paho.mqtt.client as mqtt
import requests
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

# --- AYARLAR ---
TOKEN = "7759247600:AAEB6F6v2tYv9qY9_OqfD6v0_9_0_9_0"
ID = "744958117"
MQTT_BROKER = "broker.hivemq.com"
MQTT_TOPIC = "ev/saksi/nem"

# Bekçi değişkenleri (Haberleşme kesilirse uyarır)
son_mesaj_zamani = time.time()
bekci_uyarisi_verildi = False

# --- 1. RENDER'I UYANIK TUTAN SUNUCU (Port 10000) ---
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"Saksi Sistemi Online... Cron-job basarili!")

def run_server():
    # Render'ın beklediği 10000 portunu burada açıyoruz
    server = HTTPServer(('0.0.0.0', 10000), SimpleHandler)
    server.serve_forever()

# --- 2. BEKÇİ KÖPEĞİ (Veri Akışını İzler) ---
def bekci_kopegi():
    global son_mesaj_zamani, bekci_uyarisi_verildi
    while True:
        gecen_sure = time.time() - son_mesaj_zamani
        # 10 dakika (600 saniye) veri gelmezse havla (mesaj at)
        if gecen_sure > 600 and not bekci_uyarisi_verildi:
            uyari = "🚨 DİKKAT: Saksıdan 10 dakikadır veri alınamıyor! Bağlantıyı kontrol et."
            requests.get(f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={ID}&text={uyari}")
            bekci_uyarisi_verildi = True
        
        if gecen_sure < 600:
            bekci_uyarisi_verildi = False
            
        time.sleep(60)

# --- 3. MQTT VE MESAJ ANALİZİ ---
def on_message(client, userdata, msg):
    global son_mesaj_zamani
    son_mesaj_zamani = time.time() # Veri geldi, bekçiyi sakinleştir
    nem = msg.payload.decode()
    mesaj = f"🪴 Nem Oranı: %{nem}"
    print(mesaj)
    # Telegram'a gönder
    requests.get(f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={ID}&text={mesaj}")

# --- ANA ÇALIŞTIRICI ---
if __name__ == "__main__":
    # Sunucuyu arka planda başlat
    threading.Thread(target=run_server, daemon=True).start()
    
    # Bekçiyi arka planda başlat
    threading.Thread(target=bekci_kopegi, daemon=True).start()
    
    # MQTT Bağlantısını kur
    client = mqtt.Client()
    client.on_message = on_message
    client.connect(MQTT_BROKER, 1883, 60)
    client.subscribe(MQTT_TOPIC)
    
    print("Sistem (Sunucu + Bekçi + MQTT) baslatildi, veriler bekleniyor...")
    client.loop_forever()
