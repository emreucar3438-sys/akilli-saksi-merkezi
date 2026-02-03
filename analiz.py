import paho.mqtt.client as mqtt
import requests
import time
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- GÜNCEL VE KESİN AYARLAR ---
TOKEN = "8595769743:AAF0l1t9xfYZDoc5AQ04jbKyG21Q-ZTf0e0"
ID = "8504915615"
MQTT_BROKER = "broker.hivemq.com"
MQTT_TOPIC = "ev/saksi/nem"

son_mesaj_zamani = time.time()
bekci_uyarisi_verildi = False

def telegram_haber_ver(mesaj):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        r = requests.get(url, params={"chat_id": ID, "text": mesaj}, timeout=10)
        print(f"TELEGRAM CEVABI: {r.text}", flush=True) 
    except Exception as e:
        print(f"BAGLANTI HATASI: {e}", flush=True)

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
            if gecen_sure > 600 and not bekci_uyarisi_verildi:
                telegram_haber_ver("🚨 BEKÇİ UYARISI: Saksıdan 10 dakikadır veri alınamıyor!")
                bekci_uyarisi_verildi = True
            if gecen_sure < 600:
                bekci_uyarisi_verildi = False
        except:
            pass
        time.sleep(60)

def on_message(client, userdata, msg):
    global son_mesaj_zamani
    try:
        son_mesaj_zamani = time.time()
        nem = msg.payload.decode()
        telegram_haber_ver(f"🪴 Nem Oranı: %{nem}")
    except Exception as e:
        print(f"Mesaj isleme hatası: {e}", flush=True)

if __name__ == "__main__":
    threading.Thread(target=lambda: HTTPServer(('0.0.0.0', 10000), SimpleHandler).serve_forever(), daemon=True).start()
    threading.Thread(target=bekci_kopegi, daemon=True).start()
    
    # Sistemin çalıştığını teyit etmek için:
    telegram_haber_ver("🚀 SİSTEM ŞİMDİ KUSURSUZ ÇALIŞIYOR!")
    
    while True:
        try:
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
            client.on_message = on_message
            client.connect(MQTT_BROKER, 1883, 60)
            client.subscribe(MQTT_TOPIC)
            print("MQTT Baglantisi kuruldu...", flush=True)
            client.loop_forever()
        except Exception as e:
            print(f"MQTT Hatasi: {e}. 10sn sonra tekrar denenecek...", flush=True)
            time.sleep(10)
