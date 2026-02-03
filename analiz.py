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

# --- RENDER UYANIK TUTUCU ---
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Saksi Sistemi Online!")

def run_server():
    server = HTTPServer(('0.0.0.0', 10000), SimpleHandler)
    server.serve_forever()

# --- BEKÇİ KÖPEĞİ (WATCHDOG) ---
def bekci_kopegi():
    global son_mesaj_zamani, bekci_uyarisi_verildi
    while True:
        gecen_sure = time.time() - son_mesaj_zamani
        # 10 dakika (600 saniye) boyunca veri gelmezse
        if gecen_sure > 600 and not bekci_uyarisi_verildi:
            uyari = "🚨 DIKKAT: Saksıdan 10 dakikadır veri alınamıyor! Bağlantıyı kontrol et."
            try:
                requests.get(f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={ID}&text={uyari}")
                bekci_uyarisi_verildi = True
                print("⚠️ Bekçi uyarısı gönderildi!")
            except:
                print("❌ Bekçi mesaj gönderemedi.")
        
        # Veri akışı tekrar başlarsa uyarı durumunu sıfırla
        if gecen_sure < 600:
            bekci_uyarisi_verildi = False
            
        time.sleep(60) # Her dakika kontrol et

# --- MESAJ GELİNCE ---
def on_message(client, userdata, msg):
    global son_mesaj_zamani
    son_mesaj_zamani = time.time() # Zamanı güncelle (Bekçiye 'iyiyim' de)
    try:
        nem = msg.payload.decode()
        mesaj = f"🪴 Nem Oranı: %{nem}"
        print(f"📩 VERİ GELDİ: {mesaj}")
        
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        params = {"chat_id": ID, "text": mesaj}
        requests.get(url, params=params, timeout=10)
        print("✅ Telegram'a iletildi.")
    except Exception as e:
        print(f"❌ Hata: {e}")

# --- ANA MOTOR ---
if __name__ == "__main__":
    # Arka plan görevlerini başlat
    threading.Thread(target=run_server, daemon=True).start()
    threading.Thread(target=bekci_kopegi, daemon=True).start()
    
    # MQTT Bağlantısı
    client = mqtt.Client() 
    client.on_message = on_message
    
    print("🔗 Sunucuya bağlanılıyor...")
    try:
        client.connect(MQTT_BROKER, 1883, 60)
        client.subscribe(MQTT_TOPIC)
        print(f"🚀 SİSTEM VE BEKÇİ AKTİF! '{MQTT_TOPIC}' dinleniyor...")
        client.loop_forever()
    except Exception as e:
        print(f"💥 Bağlantı Hatası: {e}")




