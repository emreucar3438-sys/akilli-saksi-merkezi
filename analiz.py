import paho.mqtt.client as mqtt
from datetime import datetime
import time
import requests

# --- AYARLAR ---
BROKER_IP = "import paho.mqtt.client as mqtt
from datetime import datetime, timedelta
import time, requests, ssl, threading

# --- AYARLAR ---
BROKER_URL = "c7a265635c0947dd9338de41699abf4b.s1.eu.hivemq.cloud"
MQTT_USER = "emre_saksi"
MQTT_PASS = "Kayseri.3438"
TELEGRAM_TOKEN = "8361884405:AAHZMyTnNLHWuNKkBhJkPLRW7xRtfzQN-SM"
CHAT_ID = "8504915615"

# --- DEĞİŞKENLER ---
son_gorulme = datetime.now()
son_telegram_vakti = 0
bekci_kilit = threading.Lock()

def telegram_gonder(mesaj):
    global son_telegram_vakti
    simdi = time.time()
    
    # 🛡️ ANTI-SPAM: Nem mesajları peş peşe gelirse 15 saniye barajı uygula
    if "Nem:" in mesaj and (simdi - son_telegram_vakti) < 15:
        print(f"🚫 Spam engellendi: {mesaj}")
        return

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": mesaj}, timeout=10)
        son_telegram_vakti = simdi
    except Exception as e: 
        print(f"❌ Telegram Hatası: {e}")

def log_yaz(topic, mesaj):
    zaman = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open("sulama_gunlugu.txt", "a", encoding="utf-8") as f:
        f.write(f"[{zaman}] {topic}: {mesaj}\n")

def bekci_kopegi():
    global son_gorulme
    while True:
        time.sleep(15)
        with bekci_kilit:
            # 🔔 120 saniye sınırı (Gereksiz uyarıları önlemek için ideal süre)
            if datetime.now() > son_gorulme + timedelta(seconds=120):
                uyari = ("⚠️ KRİTİK UYARI: Cihaz ile bağlantı kesildi!\n\n"
                         "Olası Nedenler:\n"
                         "1- Pil bitmiş olabilir.\n"
                         "2- WiFi kopmuş olabilir.\n"
                         "3- Cihaz uyanamıyor.")
                telegram_gonder(uyari)
                son_gorulme = datetime.now() # Mesajı atınca süreyi sıfırla

def on_message(client, userdata, message):
    global son_gorulme
    with bekci_kilit: 
        son_gorulme = datetime.now() # Her mesajda "cihaz yaşıyor" diyoruz
    
    payload = message.payload.decode("utf-8")
    log_yaz(message.topic, payload)
    print(f"📩 Gelen [{message.topic}]: {payload}")
    
    if message.topic == "saksi/bildirim":
        telegram_gonder(payload)

# MQTT Yapılandırması
client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
client.username_pw_set(MQTT_USER, MQTT_PASS)
client.tls_set(cert_reqs=ssl.CERT_NONE)
client.on_message = on_message

# Bekçiyi yan thread olarak başlat
threading.Thread(target=bekci_kopegi, daemon=True).start()

try:
    print("🚀 Akıllı Saksı Merkezi Çevrimiçi. Dinleme başlıyor...")
    client.connect(BROKER_URL, 8883)
    client.subscribe("saksi/#")
    telegram_gonder("🚀 Akıllı Saksı Sistemi Çevrimiçi!")
    client.loop_forever()
except Exception as e: 
    print(f"❌ Bağlantı Hatası: {e}")"
TOPIC_SENSOR = "esp32/sensor"   
TOPIC_KOMUT = "esp32/komut"     

# %100 çalışan anahtarın
PUSH_KEY = "MWbLO2lB7DuSJBKee5Zk" 

son_bildirim_vakti = 0

def bildirim_ve_sulama_tetikle(nem_degeri):
    url = "https://www.pushsafer.com/api"
    
    # Başarılı senaryo mesajı
    mesaj = f"💧 Nem %{nem_degeri}'ye düştü. Sulama başlatıldı!"
    baslik = "Saksı Otomasyonu: İŞLEM"
    ikon = "5" 

    try:
        # ESP32'ye emir gönder
        sonuc = client.publish(TOPIC_KOMUT, "SULA")
        
        if sonuc.rc != mqtt.MQTT_ERR_SUCCESS:
            raise Exception("MQTT Broker bağlantısı hatası!")

        print(f"[{datetime.now().strftime('%H:%M:%S')}] 💧 ESP32'ye 'SULA' emri iletildi.")

    except Exception as e:
        # Hata senaryosu mesajı
        mesaj = f"⚠️ HATA: Nem %{nem_degeri} ama motor çalışmadı! Hata: {e}"
        baslik = "Saksı Otomasyonu: KRİTİK HATA"
        ikon = "11" 
        print(f"❌ Sistem Hatası: {e}")

    # Pushsafer bildirimini gönder
    params = {
        "k": PUSH_KEY.strip(),
        "m": mesaj,
        "t": baslik,
        "d": "a", 
        "i": ikon, "s": "11", "v": "3"
    }
    
    try:
        res = requests.post(url, data=params, timeout=10)
        if '"status":1' in res.text:
            print(f"✅ Bildirim Cepte: {baslik}")
    except Exception as api_e:
        print(f"⚠️ Bildirim gönderilemedi: {api_e}")

def on_message(client, userdata, message):
    global son_bildirim_vakti
    try:
        payload = message.payload.decode("utf-8")
        su_an = time.time()
        zaman = datetime.now().strftime("%H:%M:%S")

        if message.topic == TOPIC_SENSOR:
            nem = int(payload)
            
            # --- KRİTİK DÜZELTME BURADA ---
            # Nem %40'ın altına düşerse ve 15 saniye geçtiyse çalış
            if nem < 40 and (su_an - son_bildirim_vakti > 15):
                print(f"[{zaman}] 🚨 KRİTİK NEM: %{nem}! Sulama başlatılıyor...")
                bildirim_ve_sulama_tetikle(nem)
                son_bildirim_vakti = su_an
            else:
                # Nem %40 ve üzerindeyse sadece log bas, işlem yapma
                print(f"[{zaman}] Nem: %{nem} | Durum: Stabil.")
                
    except Exception as e:
        print(f"⚠️ Veri İşleme Hatası: {e}")

# --- MQTT KURULUMU ---
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
client.on_message = on_message

try:
    client.connect(BROKER_IP, 1883)
    client.subscribe([(TOPIC_SENSOR, 0)])
    print("="*50)
    print("🌟 AKILLI SAKSI ANALİZ SERVİSİ AKTİF")
    print("="*50)
    client.loop_forever()
except Exception as e:

    print(f"❌ MQTT Bağlantı Hatası: {e}")
