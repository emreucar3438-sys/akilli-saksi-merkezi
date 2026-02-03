import paho.mqtt.client as mqtt
import requests
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

# --- AYARLAR ---
TOKEN = "8361884405:AAHZMyTnLHWuNKkBhJkPLRW7xRtfZQN-SM"
ID = "8504915615"
MQTT_BROKER = "broker.hivemq.com"
MQTT_TOPIC = "ev/saksi/nem"

# Bekçi değişkenleri
son_mesaj_zamani = time.time()
bekci_uyarisi_verildi = False

# --- RENDER UYANIK TUTUCU (HTTP SERVER) ---
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"Saksi Sistemi Online!")

def run_server():
    try:
        server = HTTPServer(('0.0.0.0', 10000), SimpleHandler)
        print("🌍 HTTP Sunucu 10000 portunda baslatildi...")
        server.serve_forever()
    except Exception as e:
        print(f"❌ Sunucu Hatasi: {e}")

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
                print("⚠️ Bekci uyarisi gonderildi!")
            except:
                print("❌ Bekci mesaj gonderemedi.")
        
        # Veri gelirse uyarıyı sıfırla
        if gecen_sure < 600:
            bekci_uyarisi_verildi = False
            
        time.sleep(60)

# --- MQTT MESAJ GELDİĞİNDE ---
def on_message(client, userdata, msg):
    global son_mesaj_zamani
    son_mesaj_zamani = time.time()
    try:
        nem = msg.payload.decode()
        mesaj = f"🪴 Nem Orani: %{nem}"
        print(f"📩 Gelen Veri: {mesaj}")
        
        # Telegram'a gonder
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={ID}&text={mesaj}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            print("✅ Telegram mesaji basariyla ucuruldu!")
        else:
            print(f"❌ Telegram Hatasi: {resp.text}")
    except Exception as e:
        print(f"❌ Isleme Hatasi: {e}")

# --- ANA ÇALIŞTIRICI ---
if __name__ == "__main__":
    # 1. HTTP Sunucusunu Arka Planda Baslat (Render icin)
    threading.Thread(target=run_server, daemon=True).start()
    
    # 2. Bekci Kopegini Arka Planda Baslat
    threading.Thread(target=bekci_kopegi, daemon=True).start()
    
    # 3. MQTT Client Ayarla ve Baglan
    # En uyumlu baglanti icin CallbackAPIVersion belirtilmedi (Standard V1 modu)
    client = mqtt.Client() 
    client.on_message = on_message
    
    try:
        print("🔗 MQTT Broker'a baglaniyor...")
        client.connect(MQTT_BROKER, 1883, 60)
        client.subscribe(MQTT_TOPIC)
        print(f"🚀 SISTEM HAZIR! Dinlenen Topic: {MQTT_TOPIC}")
        client.loop_forever()
    except Exception as e:
        print(f"💥 KRITIK HATA: {e}")



