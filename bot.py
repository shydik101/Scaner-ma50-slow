import yfinance as yf, requests, os, json, time, numpy as np, threading
from datetime import datetime

TOKEN = os.getenv("TELEGRAM_TOKEN")
MY_CHAT_ID = str(os.getenv("TELEGRAM_CHAT_ID"))
PORT_FILE = "portfolio.json"

def load_porto():
    if not os.path.exists(PORT_FILE): return {}
    try: return json.loads(open(PORT_FILE).read())
    except: return {}
def save_porto(d): open(PORT_FILE,"w").write(json.dumps(d,indent=2))

def scan_one(ticker):
    t = ticker.upper().strip().replace(".JK","") + ".JK"
    try:
        df = yf.download(t, period="1y", interval="1d", progress=False, auto_adjust=True)
        if len(df) < 60: return None
        c = float(df['Close'].iloc[-1]); ma20 = float(df['Close'].rolling(20).mean().iloc[-1])
        vol = float(df['Volume'].iloc[-1]); vol_avg = float(df['Volume'].rolling(20).mean().iloc[-1])
        vol_r = vol/vol_avg if vol_avg>0 else 0
        trend = (c-ma20)/ma20*100
        tr = np.maximum(df['High']-df['Low'], np.maximum(abs(df['High']-df['Close'].shift(1)), abs(df['Low']-df['Close'].shift(1))))
        atr = float(tr.rolling(14).mean().iloc[-1])
        score = 60
        if c > ma20: score+=10
        if vol_r > 1.3: score+=10
        if vol_r > 1.9: score+=10
        if trend > 0: score+=10
        status = "STRONG BREAKOUT - BUY" if score>=80 else "BREAKOUT - BUY TIPIS" if score>=70 else "WAIT"
        bintang = "⭐⭐⭐⭐" if score>=80 else "⭐⭐" if score>=70 else "⭐"
        sl = int(c-atr*1.5); tp1 = int(c+atr*2); tp2 = int(c+atr*3.5)
        rr = (tp1-c)/(c-sl) if c!=sl else 0
        return {"ticker":t.replace(".JK",""),"close":int(c),"ma20":int(ma20),"vol":round(vol_r,1),"trend":round(trend,1),"score":score,"status":status,"bintang":bintang,"sl":sl,"tp1":tp1,"tp2":tp2,"rr":round(rr,1)}
    except: return None

def format_scan(h):
    return (f"#{h['score']//10} {h['ticker']}.JK {h['score']} - {h['status']} {h['bintang']}\n"
            f"Harga:{h['close']} | MA20:{h['ma20']} | Vol:{h['vol']}x {'VALID' if h['vol']>1.3 else 'TIPIS'} | Trend MA20:{h['trend']:+.1f}%/5hr\n"
            f"Entry:{int(h['close']*0.995)}-{int(h['close']*1.005)} | SL:{h['sl']} | TP1:{h['tp1']} TP2:{h['tp2']}\n"
            f"R:R 1:{h['rr']} | Money: max Rp 1.5jt")

def send(chat,text):
    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", data={"chat_id":chat,"text":text})

# === MESIN 1: AUTO SCAN JAM 15:10 WIB ===
def auto_scan_loop():
    while True:
        now = datetime.now() # Railway pakai WIB kalau di set TZ
        # 15:10 WIB Senin-Jumat
        if now.hour == 15 and now.minute == 10 and now.weekday() < 5:
            try:
                send(MY_CHAT_ID, "⏳ AUTO SCAN SORE 15:10 Jalan...")
                url_list = "https://raw.githubusercontent.com/budikuatno2-ship-it/auto-cuan/main/data/daytrade-observe-tickers.txt"
                tickers = [x.strip() for x in requests.get(url_list, timeout=15).text.splitlines() if x.strip()][:81]
                hasil=[]
                for t in tickers:
                    h = scan_one(t)
                    if h and h['score']>=65: hasil.append(h)
                hasil = sorted(hasil, key=lambda x: x['score'], reverse=True)[:5]
                if not hasil:
                    send(MY_CHAT_ID, f"🔥 SCAN SULTAN LITE - {now.strftime('%d Sep %H:%M')} WIB\nHari ini tidak ada yang lolos 65+. Pasar lagi sepi, HOLD CASH.")
                else:
                    pesan = f"🔥 SCAN SULTAN LITE - {now.strftime('%d Sep %H:%M')} WIB | {len(tickers)} saham\nTop 5 layak pantau:\n\n"
                    for i,h in enumerate(hasil,1): pesan += f"#{i} {format_scan(h)}\n\n"
                    pesan += "📌 Cek malam santai, entry besok pagi."
                    send(MY_CHAT_ID, pesan)
                time.sleep(61) # biar gak double kirim
            except Exception as e:
                send(MY_CHAT_ID, f"Auto scan error: {e}")
        time.sleep(30)

# === MESIN 2: COMMAND MANUAL ===
def command_loop():
    offset=0
    while True:
        try:
            r = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset={offset}&timeout=30", timeout=35).json()
            for upd in r.get("result",[]):
                offset = upd["update_id"]+1
                msg = upd.get("message",{}); chat_id=str(msg.get("chat",{}).get("id")); text=msg.get("text","").strip()
                if chat_id!=MY_CHAT_ID: continue

                if text.startswith("/start"):
                    send(chat_id,"🔥 SULTAN PRO AUTO+MANUAL AKTIF\n\nAUTO: Tiap 15:10 WIB kirim Top 5\nMANUAL:\n/scan CUAN TLKM - scan bebas\n/buy CUAN 885 10\n/sell CUAN\n/portfolio")

                elif text.startswith("/scan"):
                    tickers=text.replace("/scan","").strip().split()
                    if not tickers: send(chat_id,"Contoh: /scan CUAN TLKM"); continue
                    for tk in tickers[:10]:
                        h=scan_one(tk)
                        send(chat_id, format_scan(h) if h else f"❌ {tk} gagal")

                elif text.startswith("/buy"):
                    try:
                        _,ticker,harga,lot=text.split()
                        porto=load_porto(); porto[ticker.upper()]={"harga":int(harga),"lot":int(lot),"tgl":datetime.now().strftime("%d-%m")}
                        save_porto(porto); send(chat_id,f"✅ BUY {ticker.upper()} {lot} lot @ {harga}")
                    except: send(chat_id,"Format: /buy CUAN 885 10")

                elif text.startswith("/sell"):
                    try:
                        _,ticker=text.split()
                        porto=load_porto()
                        if ticker.upper() in porto: del porto[ticker.upper()]; save_porto(porto); send(chat_id,f"✅ {ticker.upper()} terjual")
                        else: send(chat_id,"Tidak ada di porto")
                    except: send(chat_id,"Format: /sell CUAN")

                elif text.startswith("/portfolio"):
                    porto=load_porto()
                    if not porto: send(chat_id,"📭 Porto kosong"); continue
                    reply=f"💼 PORTO - {datetime.now().strftime('%d Sep %H:%M')}\n\n"
                    for t,d in porto.items():
                        h=scan_one(t)
                        if not h: continue
                        pl=(h['close']-d['harga'])/d['harga']*100
                        reply+=f"{'🟢' if pl>0 else '🔴'} {t} {d['lot']} lot | {d['harga']}->{h['close']} ({pl:+.1f}%)\nSL:{h['sl']} TP1:{h['tp1']}\n\n"
                    send(chat_id,reply)
        except Exception as e:
            print(e); time.sleep(5)

# JALANKAN DUA MESIN BARENGAN
if __name__ == "__main__":
    threading.Thread(target=auto_scan_loop, daemon=True).start()
    command_loop()
