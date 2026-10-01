import os, json, requests, pandas as pd
from datetime import datetime

PROXY_URL = "https://yahoo-proxy.rizalmawardi766.workers.dev"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
HOLDINGS_FILE = "my_holdings.json"

def send_telegram(msg):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print(msg); return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try: requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=15)
    except Exception as e: print(e)

def get_data(ticker):
    try:
        r = requests.get(f"{PROXY_URL}/?ticker={ticker}", timeout=15)
        data = r.json()
        closes = data["chart"]["result"][0]["indicators"]["quote"][0]["close"]
        vols = data["chart"]["result"][0]["indicators"]["quote"][0]["volume"]
        df = pd.DataFrame({"close": closes, "vol": vols}).dropna()
        if len(df)<60: return None
        df["MA50"] = df["close"].rolling(50).mean()
        df["MA20"] = df["close"].rolling(20).mean()
        delta = df["close"].diff()
        gain = (delta.where(delta>0,0)).rolling(14).mean()
        loss = (-delta.where(delta<0,0)).rolling(14).mean()
        rs = gain/loss
        df["RSI"] = 100 - (100/(1+rs))
        df["vol_avg"] = df["vol"].rolling(20).mean()
        df["vol_ratio"] = df["vol"]/df["vol_avg"]
        return df
    except: return None

def check_exit(ticker, info, df):
    last = df.iloc[-1]; prev = df.iloc[-2]
    close = last["close"]; ma50 = last["MA50"]; ma20 = last["MA20"]
    rsi = last["RSI"]; vol = last["vol_ratio"]
    entry = info.get("entry",0)
    date_buy = info.get("date","")
    pnl = ((close-entry)/entry*100) if entry>0 else 0
    dist_ma50 = ((close-ma50)/ma50*100) if ma50>0 else 0
    try:
        d1 = datetime.strptime(date_buy, "%Y-%m-%d")
        hold_days = (datetime.now() - d1).days
    except: hold_days = 0

    if close < ma50 and prev["close"] < ma50:
        return f"🔴 SELL - JEBOL MA50 {ticker}\nBeli {date_buy} @ {entry} | Sekarang {int(close)} ({pnl:+.1f}%)\nHold {hold_days} hari | Harga di bawah MA50 {int(ma50)} ({dist_ma50:+.1f}%)\nRSI {int(rsi)} Vol {vol:.1f}x\nAksi: JUAL / SL ketat!"
    elif close < ma20 and rsi < 45:
        return f"🟡 WARNING - LEMAH {ticker}\nBeli {date_buy} @ {entry} | Sekarang {int(close)} ({pnl:+.1f}%)\nHold {hold_days} hari | Close < MA20 + RSI {int(rsi)} <45\nAksi: Siap Take Profit"
    elif hold_days >= 45 and abs(dist_ma50) < 3 and vol < 0.8:
        return f"🟠 SIDEWAYS {ticker}\nBeli {date_buy} @ {entry} | Sekarang {int(close)} ({pnl:+.1f}%)\nHold {hold_days} hari | Sideways di MA50, Vol sepi {vol:.1f}x\nAksi: Rotasi ke saham uptrend lain"
    return None

def main():
    print("V9.1 EXIT SCAN START")
    if not os.path.exists(HOLDINGS_FILE):
        send_telegram("📭 Holdings kosong. Belum ada saham yang tercatat dari scan BUY."); return
    with open(HOLDINGS_FILE, "r") as f:
        holdings = json.load(f)
    if not holdings:
        send_telegram("📭 Holdings kosong."); return
    alerts=[]
    for ticker, info in holdings.items():
        df = get_data(ticker)
        if df is None: continue
        a = check_exit(ticker, info, df)
        if a: alerts.append(a)
    if not alerts:
        msg = f"✅ HOLDINGS CHECK {datetime.now():%d %b %H:%M}\n{len(holdings)} saham masih UPTREND aman:\n"
        for t, inf in holdings.items():
            msg += f"- {t} beli {inf['date']} @ {inf['entry']}\n"
        msg += "\nTidak ada sinyal SELL hari ini."
        send_telegram(msg)
    else:
        full = f"⚠️ EXIT ALERT {datetime.now():%d %b %H:%M} - {len(alerts)} Saham perlu perhatian\n\n"
        full += "\n\n".join(alerts)
        send_telegram(full)

if __name__=="__main__": main()
