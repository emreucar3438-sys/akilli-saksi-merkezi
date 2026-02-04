import paho.mqtt.client as mqtt
import telebot
import time
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- AYARLAR ---
TOKEN = "8595769743:AAF0lit9xFYZDoc5AQO4jbKyG2lQ-ZTfOe0"
ID = "8504915615"
MQTT_BROKER = "broker.hivemq.com"
MQTT_TOPIC = "ev/saksi/nem"

bot = telebot.TeleBot(TOKEN)

son_mesaj_zamani = time.time()
bekci_uyarisi_verildi = False
sulama_kayitlari = [] 
son_nem = 0  # Nem takibi için eklenen değişken

def telegram_haber_ver(mesaj):
    try:
        bot.send_message(ID, mesaj)
        print(f"TELEGRAM: {mesaj}", flush=True)
    except Exception as e:
        print(f"TELEGRAM HATASI: {e}", flush=True)

@bot.message_handler(commands=['rapor'])
def rapor_gonder(message):
    try:
        if not sulama_kayitlari:
            bot.reply_to(message, "📊 Henüz bir sulama kaydı bulunamadı aga.")
        else:
            # Markdown hatası almamak için metni temiz tutuyoruz
            rapor_metni = "📊 *Son 10 Ölçüm Kaydı:*\n\n" + "\n".join(sulama_kayitlari)
            bot.send_message(message.chat.id, rapor_metni, parse_mode="Markdown")
    except Exception as e:
        print(f"Rapor Hatası: {e}", flush=True)

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Saksi Sistemi Aktif ve Raporlama Hazir!")

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

# --- YENİ VE AKILLI MESAJ İŞLEME ---
def on_message(client, userdata, msg):
    global son_nem, son_mesaj_zamani
    try:
        son_mesaj_zamani = time.time()
        gelen_veri = msg.payload.decode()
        
        # Sadece sayı gelirse işlem yap (Metinleri eliyoruz)
        if gelen_veri.isdigit():
            nem = int(gelen_veri)
            zaman = time.strftime('%d/%m %H:%M:%S')
            
            # 1. SENARYO: KRİTİK DURUM
            if nem < 40:
                mesaj = f"🚨 Nem %{nem}! Durum KRİTİK, sulama başlıyor..."
                kayit = f"🚨 {zaman} -> KRİTİK: %{nem}"
            
            # 2. SENARYO: SULAMA SONRASI (Nem fırladıysa)
            elif nem > son_nem and son_nem != 0 and (nem - son_nem) > 5:
                mesaj = f"🌿 Yeni Nem %{nem}"
                kayit = f"✅ {zaman} -> Yeni Nem: %{nem}"
            
            # 3. SENARYO: NORMAL DURUM
            else:
                mesaj = f"🌿 Güncel Nem %{nem}"
                kayit = f"✅ {zaman} -> Normal: %{nem}"
            
            # Telefonuna süslü mesajı at
            telegram_haber_ver(mesaj)
            
            # Rapor listesine ekle
            sulama_kayitlari.insert(0, kayit)
            son_nem = nem # Hafızayı tazele
            
            if len(sulama_kayitlari) > 10:
                sulama_kayitlari.pop()

    except Exception as e:
        print(f"Mesaj İşleme Hatası: {e}", flush=True)

if __name__ == "__main__":
    # Web Sunucusu (Port 10000)
    threading.Thread(target=lambda: HTTPServer(('0.0.0.0', 10000), SimpleHandler).serve_forever(), daemon=True).start()
    
    # Bekçi ve Bot Threadleri
    threading.Thread(target=bekci_kopegi, daemon=True).start()
    threading.Thread(target=bot.infinity_polling, daemon=True).start()
    
    telegram_haber_ver("🚀 SİSTEM AKTİF! Saksı bekleniyor...")
    
    while True:
        try:
            client = mqtt.Client() 
            client.on_message = on_message
            client.connect(MQTT_BROKER, 1883, 60)
            client.subscribe(MQTT_TOPIC)
            client.loop_forever()
        except Exception as e:
            print(f"MQTT Hatası: {e}. Tekrar deneniyor...", flush=True)
            time.sleep(10)
