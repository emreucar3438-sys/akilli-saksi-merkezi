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
        self.wfile.write(b"Saksi Sistemi Online... Her sey yolunda!")

def run_server():
    try:
        server = HTTPServer(('0.0.0.0', 10000), SimpleHandler)
        server.serve_forever()
    except Exception as e:
        print(f"Sunucu hatasi: {e}")

# --- BEKÇİ KÖPEĞİ FONKSİYONU ---
def bekci_kopegi():
    global son_mesaj_zamani, bekci_uyarisi_verildi
    while True:
        gecen_sure = time.time() - son_mesaj_zamani
        if gecen_sure > 600 and not bekci_uyarisi_verildi:
            uyari = "🚨 DIKKAT: Sakisdan 10 dakikadir veri alinamiyor!"
            try:
                requests.get(f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={ID}&text={uyari}", timeout=10)
                bekci_uyarisi_verildi = True
            except:
                print("Bekci uyari gonderemedi, internet hatasi olabilir.")
        
        if gecen_sure < 600:
            bekci_uyarisi_verildi = False
            
        time.sleep(60)

# --- MQTT VE ANALİZ ---
def on_message(client, userdata, msg):
    global son_mesaj_zamani
    son_mesaj_zamani = time.time()
    try:
        nem = msg.payload.decode()
        mesaj = f"🪴 Nem Orani: %{nem}"
        print(mesaj)
        # Telegram'a gönderirken hata olursa kodu durdurma, sadece pas geç
        requests.get(f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={ID}&text={mesaj}", timeout=10)
    except Exception as e:
        print(f"Mesaj isleme hatasi: {e}")

# --- ANA ÇALIŞTIRICI ---
if __name__ == "__main__":
    threading.Thread(target=run_server, daemon=True).start()
    threading.Thread(target=bekci_kopegi, daemon=True).start()
    
    client = mqtt.Client()
    client.on_message = on_message
    
    # Baglanti kopsa bile otomatik geri baglanmasi icin
    client.on_disconnect = lambda client, userdata, rc: client.reconnect()

    try:
        client.connect(MQTT_BROKER, 1883, 60)
        client.subscribe(MQTT_TOPIC)
        print("Sistem (Zirhli Mod) baslatildi...")
        client.loop_forever()
    except Exception as e:
        print(f"Ana dongu hatasi: {e}")
        time.sleep(10)
