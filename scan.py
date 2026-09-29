import yfinance as yf
import requests
import os
import time
import numpy as np
from datetime import datetime

TOKEN = os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def load_tickers():
    try:
        with open("daytrade-observe-tickers.txt") as f:
            t = [x.strip() for x in f if x.strip() and not x.startswith("#")]
            if t:
                return t
    except:
        pass
    return ["BBCA.JK","BBRI.JK","BMRI.JK","BBNI.JK","TLKM.JK","ASII.JK","UNTR.JK","CUAN.JK","GOTO.JK","BREN.JK"]

def scan_one(ticker):
    try:
        t = ticker.upper().strip()
        if not t.endswith(".JK"):
            t += ".JK"
        df = yf.download(t, period="1y", interval="1d", progress=False, auto_adjust=True)
        if len(df) < 60:
            return None
        c = float(df['Close'].iloc[-1])
        o = float(df['Open'].iloc[-1])
        h = float(df['High'].iloc[-1])
        ma20 = float(df['Close'].rolling(20).mean().iloc[-1])
        ma50 = float(df['Close'].rolling(50).mean().iloc[-1])
        vol = float(df['Volume'].iloc[-1])
        vol_avg = float(df['Volume'].rolling(20).mean().iloc[-1])
        vol_r = vol / vol_avg if vol_avg > 0 else 0
        trend = (c - ma20) / ma20 * 100
        tr = np.maximum(df['High']-df['Low'], np.maximum(abs(df['High']-df['Close'].shift(1)), abs(df['Low']-df['Close'].shift(1))))
        atr = float(tr.rolling(14).mean().iloc[-1])

        score = 0
        if c > ma20 * 1.05: score += 30
        elif c > ma20 * 1.02: score += 25
        elif c > ma20: score += 15
        else: score += 5

        if vol_r >= 3.0: score += 30
        elif vol_r >= 2.0: score += 25
        elif vol_r >= 1.5: score += 20
        elif vol_r >= 1.2: score += 10
        else: score += 2

        if trend >= 3: score += 20
        elif trend >= 1: score += 15
        elif trend >= 0: score += 10
        else: score += 3

        if c > o: score += 5
        if c > ma50: score += 10
        if ma20 > ma50: score += 5

        if score >= 90:
            bintang = "⭐⭐⭐⭐⭐"
            status = "GOD MODE - ALL IN"
        elif score >= 80:
            bintang = "⭐⭐⭐⭐"
            status = "STRONG BREAKOUT - BUY"
        elif score >= 65:
            bintang = "⭐⭐⭐"
            status = "BREAKOUT - BUY TIPIS"
        elif score >= 50:
            bintang = "⭐⭐"
            status = "WAIT PULLBACK"
        elif score >= 35:
            bintang = "⭐"
            status = "Pantau Volume"
        else:
            return None

        sl = int(c - atr*1.5)
        tp1 = int(c + atr*2)
        tp2 = int(c + atr*3.5)
        rr = (tp1-c)/(c-sl) if c != sl else 0

        return {
            "ticker": t.replace(".JK",""), "close": int(c), "ma20": int(ma20),
            "vol": round(vol_r,1), "trend": round(trend,1), "score": score,
            "status": status, "bintang": bintang, "sl": sl, "tp1": tp1, "tp2": tp2, "rr": round(rr,1)
        }
    except Exception as e:
        print(f"Error {ticker}: {e}")
        return None

tickers = load_tickers()
hasil = []
print("--- SCAN SULTAN 5 BINTANG START ---")
for i, tk in enumerate(tickers[:81]):
    h = scan_one(tk)
    if h:
        hasil.append(h)
    time.sleep(0.2)

hasil = sorted(hasil, key=lambda x: x['score'], reverse=True)
now = datetime.now().strftime('%d %b %H:%M')

if not hasil:
    pesan = f"🔥 SCAN 5 BINTANG - {now} WIB\n{len(tickers)} saham, tidak ada yang lolos."
else:
    pesan = f"🔥 SCAN SULTAN 5 BINTANG - {now} WIB | {len(tickers)} saham\nTop {len(hasil)} layak pantau:\n\n"
    for idx, h in enumerate(hasil[:10], 1):
        pesan += f"#{idx} {h['ticker']}.JK {h['score']} - {h['status']} {h['bintang']}\n"
        pesan += f"Harga:{h['close']} | MA20:{h['ma20']} | Vol:{h['vol']}x | Trend:{h['trend']:+.1f}%\n"
        pesan += f"SL:{h['sl']} | TP1:{h['tp1']} TP2:{h['tp2']} R:R 1:{h['rr']}\n\n"

print(pesan)

if TOKEN and CHAT_ID:
    r = requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", data={"chat_id": CHAT_ID, "text": pesan})
    print(f"TELEGRAM status: {r.status_code}")
else:
    print("TELEGRAM token kosong")
