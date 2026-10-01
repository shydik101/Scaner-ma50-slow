import os, requests, pandas as pd, time, json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

TICKER_FILE = os.getenv("TICKER_FILE", "tickers-batch1.txt")
BATCH_LABEL = os.getenv("BATCH_LABEL", "BIGCAPS")
PROXY_URL = "https://yahoo-proxy.rizalmawardi766.workers.dev"
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
HISTORY_FILE = "history.json"

# Tentukan MA jebol tergantung batch
IS_GORENGAN = "batch2" in TICKER_FILE.lower() or "gorengan" in BATCH_LABEL.lower()

def send(msg):
    if TOKEN and CHAT_ID:
        try: requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json={"chat_id": CHAT_ID, "text": msg}, timeout=20)
        except: pass
    print(msg)

def get_df(ticker):
    for attempt in range(3):
        try:
            r = requests.get(f"{PROXY_URL}/?ticker={ticker}", timeout=15).json()
            q = r["chart"]["result"][0]["indicators"]["quote"][0]
            df = pd.DataFrame({"close": q["close"], "vol": q["volume"]}).dropna()
            if len(df) >= 60: return df, attempt+1
        except:
            time.sleep(1); continue
    return None, 3

def analyze_exit(ticker):
    df, retry = get_df(ticker)
    if df is None: return None
    df["MA20"]=df["close"].rolling(20).mean(); df["MA50"]=df["close"].rolling(50).mean()
    df["vol_avg"]=df["vol"].rolling(20).mean(); df["vol_ratio"]=df["vol"]/df["vol_avg"]
    delta=df["close"].diff(); gain=delta.where(delta>0,0).rolling(14).mean(); loss=-delta.where(delta<0,0).rolling(14).mean()
    df["RSI"]=100-(100/(1+gain/loss))

    last=df.iloc[-1]
    if pd.isna(last["MA20"]) or pd.isna(last["MA50"]): return None
    c, ma20, ma50 = last["close"], last["MA20"], last["MA50"]
    rsi=last["RSI"] if not pd.isna(last["RSI"]) else 50
    vol=last["vol_ratio"] if not pd.isna(last["vol_ratio"]) else 1.0

    # LOGIKA EXIT BINTANG 5
    if IS_GORENGAN:
        # Gorengan ketat: jebol MA20 aja SELL
        if c < ma20 and c < ma50 and vol >= 2.0:
            label, stars = "SUPER SELL - Jebol MA20+MA50 Vol Gede", 5
        elif c < ma20 and vol >= 1.5:
            label, stars = "STRONG SELL - Jebol MA20", 4
        elif c < ma20:
            label, stars = "SELL - Jebol MA20", 3
        elif c < ma20 * 1.02 and rsi < 45:
            label, stars = "WEAK SELL - Dekat MA20", 2
        else:
            return None
    else:
        # Bigcaps longgar: jebol MA50 baru SELL
        if c < ma20 and c < ma50 and vol >= 2.0:
            label, stars = "SUPER SELL - Jebol MA50 Long Term", 5
        elif c < ma50:
            label, stars = "STRONG SELL - Jebol MA50", 4
        elif c < ma50 * 1.02 and rsi < 45:
            label, stars = "SELL - Rawan Jebol MA50", 3
        else:
            return None

    msg=f"#{ticker} {label}\n{'⭐'*stars} ({stars}/5) - {BATCH_LABEL}\n"
    msg+=f"Price: {int(c)} MA20:{int(ma20)} MA50:{int(ma50)}\n"
    msg+=f"Vol Jual: {vol:.1f}x RSI: {int(rsi)}\n"
    msg+=f"Aksi: Jual Sesi 1 Besok"
    return {"msg": msg, "stars": stars, "retry": retry}

def main():
    start=time.time()
    with open(TICKER_FILE) as f: tickers=[x.strip() for x in f if x.strip() and not x.startswith("#")]
    results=[]; total_retry=0
    with ThreadPoolExecutor(max_workers=15) as ex:
        futs={ex.submit(analyze_exit,t):t for t in tickers}
        for fu in as_completed(futs):
            r=fu.result()
            if r: results.append(r); total_retry+=r["retry"]

    results=sorted(results, key=lambda x:x["stars"], reverse=True)[:10]
    elapsed=time.time()-start

    if not results:
        # Kalau gak ada yang SELL, diam aja biar gak berisik (atau kirim log kalau mau)
        print(f"{BATCH_LABEL} - Tidak ada SELL signal")
        return

    header=f"⚠️ EXIT ALERT V10.1 {datetime.now():%d %b %H:%M}\n{BATCH_LABEL} | {TICKER_FILE}\nFilter: Bintang 3+ | Top 10\n\n"
    body="\n\n".join([r["msg"] for r in results])
    footer=f"\n\n━━━━━━━━━━━━━━━━\n📊 Total Cek: {len(tickers)} | SELL: {len(results)}\n🔁 Retry 3x: {total_retry} | ⏱️ {elapsed:.1f}s | Maks: 5 Bintang"
    send(header+body+footer)

if __name__=="__main__": main()
