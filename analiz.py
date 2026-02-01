import paho.mqtt.client as mqtt
from datetime import datetime
import time
import requests

# --- AYARLAR ---
BROKER_IP = "172.20.10.3"
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