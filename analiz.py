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

# --- RENDER İÇİN HTTP SUNUCUSU ---
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
        # 10 dakika (600 saniye) boyunca veri gelmezse uyar
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
        print(f"📩 VERI GELDI: %{nem}")
        # Telegram Gönderimi
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        requests.get(url, params={"chat_id": ID, "text": f"🪴 Nem Oranı: %{nem}"}, timeout=10)
        print("✅ Telegram mesajı gönderildi!")
    except Exception as e:
        print(f"❌ Hata: {e}")

# --- ANA MOTOR ---
if __name__ == "__main__":
    # 1. Render Sunucusunu ve Bekçi Köpeğini arka planda başlat
    threading.Thread(target=run_server, daemon=True).start()
    threading.Thread(target=bekci_kopegi, daemon=True).start()
    
    # 2. YENİ NESİL (V2) MQTT BAĞLANTISI
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2) 
    client.on_message = on_message
    
    print("🔗 MQTT Broker'a bağlanılıyor...")
    try:
        client.connect(MQTT_BROKER, 1883, 60)
        client.subscribe(MQTT_TOPIC)
        print(f"🚀 SİSTEM VE BEKÇİ HAZIR! '{MQTT_TOPIC}' dinleniyor...")
        client.loop_forever()
    except Exception as e:
        print(f"💥 Bağlantı Hatası: {e}")




