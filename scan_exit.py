import os, json, requests, pandas as pd, argparse
from datetime import datetime

PROXY_URL = "https://yahoo-proxy.rizalmawardi766.workers.dev"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
HOLDINGS_FILE = "my_holdings.json"

parser = argparse.ArgumentParser()
parser.add_argument("--tipe", default="ALL")
args = parser.parse_args()
FILTER_TIPE = args.tipe.upper()

def send_telegram(msg):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID: print(msg); return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try: requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=15)
    except: pass

def get_data(ticker):
    try:
        r = requests.get(f"{PROXY_URL}/?ticker={ticker}", timeout=15)
        data = r.json()
        closes = data["chart"]["result"][0]["indicators"]["quote"][0]["close"]
        vols = data["chart"]["result"][0]["indicators"]["quote"][0]["volume"]
        df = pd.DataFrame({"close": closes, "vol": vols}).dropna()
        if len(df)<60: return None
        df["MA50"] = df["close"].rolling(50).mean(); df["MA20"] = df["close"].rolling(20).mean()
        delta = df["close"].diff(); gain = (delta.where(delta>0,0)).rolling(14).mean(); loss = (-delta.where(delta<0,0)).rolling(14).mean()
        rs = gain/loss; df["RSI"] = 100 - (100/(1+rs)); df["vol_avg"] = df["vol"].rolling(20).mean(); df["vol_ratio"] = df["vol"]/df["vol_avg"]
        return df
    except: return None

def check_exit(ticker, info, df):
    last = df.iloc[-1]; prev = df.iloc[-2]
    close = last["close"]; ma50 = last["MA50"]; ma20 = last["MA20"]; rsi = last["RSI"]; vol = last["vol_ratio"]
    entry = info.get("entry",0); date_buy = info.get("date",""); tipe = info.get("tipe","BIGCAP")
    pnl = ((close-entry)/entry*100) if entry>0 else 0
    try: hold_days = (datetime.now() - datetime.strptime(date_buy, "%Y-%m-%d")).days
    except: hold_days = 0

    if tipe == "GORENGAN":
        if close < ma20:
            return f"🔴 SELL GORENGAN {ticker} - JEBOL MA20\nBeli {date_buy} @ {entry} | Now {int(close)} ({pnl:+.1f}%) | {hold_days}h\nAksi: JUAL SEKARANG!"
        if rsi < 50 and vol < 1.0:
            return f"🟡 WARNING GORENGAN {ticker} - LOYO\nBeli {date_buy} @ {entry} | Now {int(close)} ({pnl:+.1f}%)\nRSI {int(rsi)} Vol {vol:.1f}x\nAksi: TP cepat!"
    else:
        if close < ma50 and prev["close"] < ma50:
            return f"🔴 SELL BIGCAP {ticker} - JEBOL MA50\nBeli {date_buy} @ {entry} | Now {int(close)} ({pnl:+.1f}%) | {hold_days} hari\nAksi: JUAL"
        if close < ma20 and rsi < 45 and hold_days > 10:
            return f"🟡 WARNING BIGCAP {ticker}\nBeli {date_buy} @ {entry} | Now {int(close)} ({pnl:+.1f}%)\nAksi: Watch TP"
    return None

def main():
    if not os.path.exists(HOLDINGS_FILE): send_telegram("📭 Holdings kosong."); return
    with open(HOLDINGS_FILE, "r") as f: holdings = json.load(f)
    if FILTER_TIPE!= "ALL": holdings = {k:v for k,v in holdings.items() if v.get("tipe","") == FILTER_TIPE}
    alerts=[]
    for ticker, info in holdings.items():
        df = get_data(ticker)
        if df is None: continue
        a = check_exit(ticker, info, df)
        if a: alerts.append(a)
    if not alerts:
        msg = f"✅ CHECK {FILTER_TIPE} {datetime.now():%d %b %H:%M}\n{len(holdings)} saham aman\n"
        for t, inf in holdings.items(): msg += f"- {t} [{inf.get('tipe','')}] {inf['date']} @ {inf['entry']}\n"
        send_telegram(msg)
    else:
        full = f"⚠️ EXIT {FILTER_TIPE} {datetime.now():%d %b %H:%M} - {len(alerts)} Saham\n\n" + "\n\n".join(alerts)
        send_telegram(full)

if __name__=="__main__": main()
