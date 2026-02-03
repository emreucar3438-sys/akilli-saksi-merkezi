import paho.mqtt.client as mqtt
import requests
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

# --- AYARLAR ---
TOKEN = "8361884405:AAHZMyTnLHWuNKkBhJkPLRW7xRt fZQN-SM"
ID = "8504915615"
MQTT_BROKER = "broker.hivemq.com"
MQTT_TOPIC = "ev/saksi/nem"

# Bekçi değişkenleri
son_mesaj_zamani = time.time()
bekci_uyarisi_verildi = False

# --- RENDER UYANIK TUTUCU ---
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"Saksi Sistemi Online!")

def run_server():
    try:
        server = HTTPServer(('0.0.0.0', 10000), SimpleHandler)
        server.serve_forever()
    except: pass

# --- BEKÇİ KÖPEĞİ (WATCHDOG) ---
def bekci_kopegi():
    global son_mesaj_zamani, bekci_uyarisi_verildi
    while True:
        gecen_sure = time.time() - son_mesaj_zamani
        # 10 dakika (600 saniye) veri gelmezse uyar
        if gecen_sure > 600 and not bekci_uyarisi_verildi:
            uyari = "🚨 DIKKAT: Sakisdan 10 dakikadir veri alinamiyor!"
            try:
                requests.get(f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={ID}&text={uyari}", timeout=10)
                bekci_uyarisi_verildi = True
            except:
                print("Bekci uyari gonderemedi.")
        
        # Veri gelirse uyarıyı sıfırla
        if gecen_sure < 600:
            bekci_uyarisi_verildi = False
            
        time.sleep(60) # Her dakika kontrol et

# --- MQTT MESAJ GELDİĞİNDE ---
def on_message(client, userdata, msg):
    global son_mesaj_zamani
    son_mesaj_zamani = time.time() # Zamanı güncelle (Bekçiye 'iyiyim' de)
    try:
        nem = msg.payload.decode()
        mesaj = f"🪴 Nem Orani: %{nem}"
        print(f"Gelen Veri: {mesaj}")
        requests.get(f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={ID}&text={mesaj}", timeout=10)
    except Exception as e:
        print(f"Hata: {e}")

# --- ANA ÇALIŞTIRICI ---
if __name__ == "__main__":
    # Servisleri başlat
    threading.Thread(target=run_server, daemon=True).start()
    threading.Thread(target=bekci_kopegi, daemon=True).start()
    
    # MQTT V2 Client
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2) 
    client.on_message = on_message
    
    try:
        client.connect(MQTT_BROKER, 1883, 60)
        client.subscribe(MQTT_TOPIC)
        print("🚀 Sistem V2 + Bekci Kopegi Baslatildi...")
        client.loop_forever()
    except Exception as e:
        print(f"Baglanti Hatasi: {e}")

