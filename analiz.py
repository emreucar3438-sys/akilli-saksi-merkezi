import paho.mqtt.client as mqtt
import telebot
import time
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- GÜNCEL VE KESİN AYARLAR ---
TOKEN = "8595769743:AAF0lit9xFYZDoc5AQO4jbKyG2lQ-ZTfOe0"
ID = "8504915615"
MQTT_BROKER = "broker.hivemq.com"
MQTT_TOPIC = "ev/saksi/nem"

# Bot nesnesini başlatıyoruz
bot = telebot.TeleBot(TOKEN)

# Hafıza Değişkenleri
son_mesaj_zamani = time.time()
bekci_uyarisi_verildi = False
sulama_kayitlari = [] # Son 10 sulama buraya kaydedilecek

# --- 1. FONKSİYON: TELGRAM'A MESAJ ATMA ---
def telegram_haber_ver(mesaj):
    try:
        bot.send_message(ID, mesaj)
        print(f"TELEGRAM GÖNDERİLDİ: {mesaj}", flush=True)
    except Exception as e:
        print(f"TELEGRAM HATASI: {e}", flush=True)

# --- 2. FONKSİYON: TELEGRAMDAN GELEN RAPOR KOMUTU ---
# Bilgisayar kapalı olsa bile Render üzerinden cevap verir
@bot.message_handler(commands=['rapor'])
def rapor_gonder(message):
    try:
        if not sulama_kayitlari:
            bot.reply_to(message, "📊 Henüz bir sulama kaydı bulunamadı aga.")
        else:
            rapor_metni = "📊 *Son 10 Sulama Kaydı:*\n\n" + "\n".join(sulama_kayitlari)
            bot.send_message(message.chat.id, rapor_metni, parse_mode="Markdown")
    except Exception as e:
        print(f"Rapor Gönderme Hatası: {e}", flush=True)

# --- 3. FONKSİYON: WEB SUNUCUSU (Render Kapanmasın Diye) ---
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Saksi Sistemi Aktif ve Raporlama Hazir!")

# --- 4. FONKSİYON: BEKÇİ KÖPEĞİ ---
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

# --- 5. FONKSİYON: MQTT MESAJ İŞLEME VE KAYIT ---
def on_message(client, userdata, msg):
    global son_mesaj_zamani
    try:
        son_mesaj_zamani = time.time()
        nem_str = msg.payload.decode()
        nem = int(nem_str)
        
        # Eğer nem %40 altındaysa (Sulama yapılıyorsa) kaydet
        if nem < 40:
            zaman = time.strftime('%d/%m %H:%M:%S')
            kayit = f"🕒 {zaman} -> Nem: %{nem}"
            
            # Eğer bu kayıt zaten listenin başında yoksa ekle (Aynı değerin tekrarını önlemek için)
            if not sulama_kayitlari or sulama_kayitlari[0].split("->")[1] != f" Nem: %{nem}":
                sulama_kayitlari.insert(0, kayit)
                if len(sulama_kayitlari) > 10:
                    sulama_kayitlari.pop()
        
        # Her durumda bildirim gönder (İstersen bunu sadece sulama anına çekebilirsin)
        telegram_haber_ver(f"🪴 Güncel Nem Oranı: %{nem}")
        
    except Exception as e:
        print(f"Mesaj isleme hatası: {e}", flush=True)

# --- ANA ÇALIŞTIRMA BLOĞU ---
if __name__ == "__main__":
    # 1. Web Sunucusunu Başlat
    threading.Thread(target=lambda: HTTPServer(('0.0.0.0', 10000), SimpleHandler).serve_forever(), daemon=True).start()
    
    # 2. Bekçi Köpeğini Başlat
    threading.Thread(target=bekci_kopegi, daemon=True).start()
    
    # 3. Telegram Bot Dinleyicisini Başlat (Ayrı Thread'de)
    threading.Thread(target=bot.infinity_polling, daemon=True).start()
    
    telegram_haber_ver("🚀 SİSTEM VE RAPORLAMA MODÜLÜ AKTİF!")
    
    # 4. MQTT Döngüsünü Başlat
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
