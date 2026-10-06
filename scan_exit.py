import os, requests, pandas as pd, time, json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--market', default=os.getenv("MARKET", "IDX"), help='IDX or US')
parser.add_argument('--ticker_file', default=os.getenv("TICKER_FILE", "tickers-batch1.txt"))
args, _ = parser.parse_known_args()

MARKET = args.market.upper()
TICKER_FILE = args.ticker_file
BATCH_LABEL = os.getenv("BATCH_LABEL", f"{MARKET}-{args.ticker_file.replace('.txt','')}")

PROXY_URL = "https://yahoo-proxy.rizalmawardi766.workers.dev"
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

HISTORY_FILE = "history_etf.json" if MARKET == "US" else "history.json"

IS_GORENGAN = "batch2" in TICKER_FILE.lower() or "gorengan" in BATCH_LABEL.lower() or "ETF" in TICKER_FILE.upper()
if MARKET == "US":
    IS_GORENGAN = True

def send(msg):
    if TOKEN and CHAT_ID:
        try: requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=20)
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
    df["MA20"]=df["close"].rolling(20).mean()
    df["MA50"]=df["close"].rolling(50).mean()
    df["vol_avg"]=df["vol"].rolling(20).mean()
    df["vol_ratio"]=df["vol"]/df["vol_avg"]
    df["ATR"]=df["close"].diff().abs().rolling(14).mean()
    delta=df["close"].diff()
    gain=delta.where(delta>0,0).rolling(14).mean()
    loss=-delta.where(delta<0,0).rolling(14).mean()
    df["RSI"]=100-(100/(1+gain/loss))

    last=df.iloc[-1]
    if pd.isna(last["MA20"]) or pd.isna(last["MA50"]): return None
    c, ma20, ma50 = last["close"], last["MA20"], last["MA50"]
    rsi=last["RSI"] if not pd.isna(last["RSI"]) else 50
    vol=last["vol_ratio"] if not pd.isna(last["vol_ratio"]) else 1.0
    atr=last["ATR"] if not pd.isna(last["ATR"]) else c*0.02
    atr_pct = (atr/c*100) if c>0 else 0

    # SL Dinamis untuk referensi kenapa jebol
    sl_hit = c - (atr*1.5)
    sl_hit = max(c*0.93, min(c*0.97, sl_hit)) # batas 3-7%
    loss_pct = (c - sl_hit)/c*100

    if IS_GORENGAN:
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
        if c < ma20 and c < ma50 and vol >= 2.0:
            label, stars = "SUPER SELL - Jebol MA50 Long Term", 5
        elif c < ma50:
            label, stars = "STRONG SELL - Jebol MA50", 4
        elif c < ma50 * 1.02 and rsi < 45:
            label, stars = "SELL - Rawan Jebol MA50", 3
        else:
            return None

    if MARKET == "US":
        price_str = f"${c:.2f} MA20:${ma20:.2f} MA50:${ma50:.2f}"
        sl_str = f"SL Ref: ${sl_hit:.2f} (-{loss_pct:.1f}%)"
    else:
        price_str = f"Price:{int(c)} MA20:{int(ma20)} MA50:{int(ma50)}"
        sl_str = f"SL Ref: {int(sl_hit)} (-{loss_pct:.1f}%)"

    msg=f"#{ticker} {label}\n{'⭐'*stars} ({stars}/5) - {BATCH_LABEL} [{MARKET}]\n"
    msg+=f"{price_str}\n"
    msg+=f"Vol Jual: {vol:.1f}x RSI: {int(rsi)} ATR:{atr_pct:.1f}%\n"
    msg+=f"{sl_str}\n"
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
        print(f"{BATCH_LABEL} [{MARKET}] - Tidak ada SELL signal")
        return

    header=f"⚠️ *EXIT ALERT V11.4 PRO*\n{datetime.now():%d %b %H:%M} | {BATCH_LABEL} | {TICKER_FILE} | Market:{MARKET}\nFilter: Bintang 3+ | RR ATR Ref | Top 10\n\n"
    body="\n\n".join([r["msg"] for r in results])
    footer=f"\n\n━━━━━━━━━━━━━━━━\n📊 Total Cek: {len(tickers)} | SELL: {len(results)}\n🔁 Retry 3x: {total_retry} | ⏱️ {elapsed:.1f}s | Market:{MARKET}"
    send(header+body+footer)

if __name__=="__main__": main()
