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

# Bekçi değişkenleri
son_mesaj_zamani = time.time()
bekci_uyarisi_verildi = False

# --- RENDER'I UYANIK TUTAN SUNUCU ---
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"Saksi Sistemi Online... Cron-job basarili!")

def run_server():
    server = HTTPServer(('0.0.0.0', 10000), SimpleHandler)
    server.serve_forever()

# --- BEKÇİ KÖPEĞİ FONKSİYONU ---
def bekci_kopegi():
    global son_mesaj_zamani, bekci_uyarisi_verildi
    while True:
        gecen_sure = time.time() - son_mesaj_zamani
        # 10 dakika (600 saniye) boyunca veri gelmezse
        if gecen_sure > 600 and not bekci_uyarisi_verildi:
            uyari = "🚨 DİKKAT: Saksıdan 10 dakikadır veri alınamıyor! Bağlantıyı kontrol et."
            requests.get(f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={ID}&text={uyari}")
            bekci_uyarisi_verildi = True
        
        # Veri tekrar gelmeye başlarsa uyarı durumunu sıfırla
        if gecen_sure < 600:
            bekci_uyarisi_verildi = False
            
        time.sleep(60) # Her dakika kontrol et

# --- MQTT VE ANALİZ ---
def on_message(client, userdata, msg):
    global son_mesaj_zamani
    son_mesaj_zamani = time.time() # Bekçiye "buradayım" de
    nem = msg.payload.decode()
    mesaj = f"🪴 Nem Oranı: %{nem}"
    print(mesaj)
    requests.get(f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={ID}&text={mesaj}")

# --- ANA ÇALIŞTIRICI ---
if __name__ == "__main__":
    # 1. Sunucuyu başlat (Cron-job için)
    threading.Thread(target=run_server, daemon=True).start()
    
    # 2. Bekçi Köpeğini başlat (Takip için)
    threading.Thread(target=bekci_kopegi, daemon=True).start()
    
    # 3. MQTT'yi başlat
    client = mqtt.Client()
    client.on_message = on_message
    client.connect(MQTT_BROKER, 1883, 60)
    client.subscribe(MQTT_TOPIC)
    
    print("Sistem (Bekçi Dahil) baslatildi...")
    client.loop_forever()
