import yfinance as yf, requests, os, json, time, numpy as np, threading
from datetime import datetime

TOKEN = os.getenv("TELEGRAM_TOKEN")
MY_CHAT_ID = str(os.getenv("TELEGRAM_CHAT_ID"))
PORT_FILE = "portfolio.json"
TICKER_FILE = "daytrade-observe-tickers.txt"

def load_porto():
    if not os.path.exists(PORT_FILE): return {}
    try: return json.loads(open(PORT_FILE).read())
    except: return {}
def save_porto(d): open(PORT_FILE,"w").write(json.dumps(d,indent=2))

def load_tickers():
    # 1. Coba baca file lokal kamu yang di repo
    try:
        if os.path.exists(TICKER_FILE):
            with open(TICKER_FILE) as f:
                data = [x.strip() for x in f if x.strip() and not x.startswith("#")]
                if data: 
                    print(f"Load {len(data)} ticker dari {TICKER_FILE}")
                    return data[:81]
    except Exception as e:
        print(f"Gagal baca {TICKER_FILE}: {e}")

    # 2. Fallback kalau file lokal tidak ada -> pakai list LQ45
    print("Fallback pakai LQ45 default")
    return ["BBCA.JK","BBRI.JK","BMRI.JK","BBNI.JK","TLKM.JK","ASII.JK","UNTR.JK","ADRO.JK","AMRT.JK","ICBP.JK","INDF.JK","KLBF.JK","BBCA.JK"]

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
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", data={"chat_id":chat,"text":text}, timeout=15)
    except Exception as e:
        print(f"Gagal kirim: {e}")

# === AUTO SCAN 15:10 WIB ===
def auto_scan_loop():
    while True:
        now = datetime.now()
        if now.hour == 15 and now.minute == 10 and now.weekday() < 5:
            try:
                tickers = load_tickers()
                send(MY_CHAT_ID, f"⏳ AUTO SCAN 15:10 Jalan... scan {len(tickers)} saham dari {TICKER_FILE}")
                hasil=[]
                for t in tickers:
                    h = scan_one(t)
                    if h and h['score']>=65: hasil.append(h)
                    time.sleep(0.2)
                hasil = sorted(hasil, key=lambda x: x['score'], reverse=True)[:5]
                if not hasil:
                    send(MY_CHAT_ID, f"🔥 SCAN SULTAN LITE - {now.strftime('%d %b %H:%M')} WIB\nFull {len(tickers)} saham\nTidak ada yang lolos 65+ hari ini. HOLD CASH.")
                else:
                    pesan = f"🔥 SCAN SULTAN LITE - {now.strftime('%d %b %H:%M')} WIB | {len(tickers)} saham\nTop 5 layak pantau:\n\n"
                    for i,h in enumerate(hasil,1): pesan += f"#{i} {format_scan(h)}\n\n"
                    pesan += "📌 Cek malam santai, entry besok pagi."
                    send(MY_CHAT_ID, pesan)
                time.sleep(70)
            except Exception as e:
                send(MY_CHAT_ID, f"Auto scan error: {e}")
        time.sleep(30)

# === COMMAND MANUAL ===
def command_loop():
    offset=0
    print("🤖 SULTAN PRO AKTIF - baca file lokal")
    while True:
        try:
            r = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset={offset}&timeout=30", timeout=35).json()
            for upd in r.get("result",[]):
                offset = upd["update_id"]+1
                msg = upd.get("message",{}); chat_id=str(msg.get("chat",{}).get("id")); text=msg.get("text","").strip()
                if chat_id!=MY_CHAT_ID: continue

                if text.startswith("/start"):
                    send(chat_id,"🔥 SULTAN PRO AUTO+MANUAL\nFile
