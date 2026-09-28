import yfinance as yf, requests, time
from datetime import datetime

TOKEN = "8824185237:AAH2VLFwOkW-iSpxEQ3u0fIQ-4AS8DnYug0"
CHAT_ID = "7855961885"

# AMBIL LIST 957 SAHAM LANGSUNG DARI GITHUB (auto update)
url_list = "https://raw.githubusercontent.com/budikuatno2-ship-it/auto-cuan/main/data/daytrade-observe-tickers.txt"
print(f"Download list ticker dari {url_list}")
try:
    r = requests.get(url_list, timeout=15)
    tickers_raw = [x.strip().upper() for x in r.text.splitlines() if x.strip() and not x.startswith("#")]
    TICKERS = [t if t.endswith(".JK") else t + ".JK" for t in tickers_raw]
    print(f"Berhasil dapat {len(TICKERS)} ticker")
except:
    # fallback kalau gagal download
    TICKERS = ["BBCA.JK","BBRI.JK","BMRI.JK","BBNI.JK","TLKM.JK","ASII.JK","MDKA.JK","HRUM.JK","ANTM.JK","ADRO.JK"]

hasil = []
print(f"Mulai scan {len(TICKERS)} saham...")

for i, t in enumerate(TICKERS):
    try:
        df = yf.download(t, period="6mo", interval="1d", progress=False, auto_adjust=True)
        if len(df) < 60: 
            continue
        
        close = df['Close'].iloc[-1].item()
        ma20 = df['Close'].rolling(20).mean().iloc[-1].item()
        ma50 = df['Close'].rolling(50).mean().iloc[-1].item()
        ma50_prev = df['Close'].rolling(50).mean().iloc[-11].item()
        vol = df['Volume'].iloc[-1].item()
        vol_avg = df['Volume'].rolling(20).mean().iloc[-1].item()
        if vol_avg == 0: continue
        
        jarak = ((close - ma50) / ma50) * 100
        slope_ma50 = ma50 > ma50_prev

        # FILTER: TREND NAIK + DEKAT MA50
        is_uptrend = close > ma50 and ma20 > ma50 and slope_ma50
        is_dekat = -4 <= jarak <= 4  # aku longgarkan dikit jadi 4% biar dapat lebih banyak
        is_volume = vol > (vol_avg * 0.7)

        if is_uptrend and is_dekat and is_volume:
            hasil.append(f"{t.replace('.JK','')} | {int(close)} | {round(jarak,1)}% | Vol{int(vol/vol_avg*100)}%")

        if i % 50 == 0:
            print(f"Progress {i}/{len(TICKERS)} -> ketemu {len(hasil)}")
        time.sleep(0.15)
    except:
        continue

now = datetime.now().strftime('%d %b %H:%M')
# Telegram batasi 4096 karakter, kita potong jadi 2 pesan kalau banyak
if hasil:
    header = f"🔥 FULL SCAN 957 IDX - {now} WIB\nTrend Naik x Dekat MA50\nDitemukan {len(hasil)} saham:\n\n"
    pesan1 = header + "\n".join(hasil[:35])
    print(pesan1)
    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", data={"chat_id": CHAT_ID, "text": pesan1})
    
    # kalau lebih dari 35, kirim pesan ke-2
    if len(hasil) > 35:
        time.sleep(1)
        pesan2 = f"Lanjutan ({len(hasil)-35} saham lagi):\n\n" + "\n".join(hasil[35:70])
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", data={"chat_id": CHAT_ID, "text": pesan2})
else:
    pesan = f"⚠️ FULL SCAN 957 - {now} WIB\nTidak ada saham uptrend dekat MA50 hari ini."
    print(pesan)
    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", data={"chat_id": CHAT_ID, "text": pesan})
