import os, requests, pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

TICKER_FILE = os.getenv("TICKER_FILE", "tickers-batch1.txt")
BATCH_LABEL = os.getenv("BATCH_LABEL", "HYBRID")
PROXY_URL = "https://yahoo-proxy.rizalmawardi766.workers.dev"
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

KINGS = {"BBCA.JK","BBRI.JK","BMRI.JK","BBNI.JK","TLKM.JK","ASII.JK","UNTR.JK","BBTN.JK"}

def send(msg):
    if TOKEN and CHAT_ID:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json={"chat_id": CHAT_ID, "text": msg}, timeout=20)
    print(msg)

def get_df(ticker):
    try:
        r = requests.get(f"{PROXY_URL}/?ticker={ticker}", timeout=15).json()
        q = r["chart"]["result"][0]["indicators"]["quote"][0]
        df = pd.DataFrame({"close": q["close"], "vol": q["volume"]}).dropna()
        return df if len(df) >= 60 else None
    except: return None

def analyze(ticker):
    df = get_df(ticker)
    if df is None: return None
    df["MA20"] = df["close"].rolling(20).mean()
    df["MA50"] = df["close"].rolling(50).mean()
    df["vol_avg"] = df["vol"].rolling(20).mean()
    df["vol_ratio"] = df["vol"] / df["vol_avg"]
    delta = df["close"].diff()
    gain = delta.where(delta>0,0).rolling(14).mean()
    loss = -delta.where(delta<0,0).rolling(14).mean()
    df["RSI"] = 100 - (100 / (1 + gain/loss))
    df["ADX"] = (df["close"].diff().abs().rolling(14).mean() / df["close"] * 1000).clip(10,50)

    last = df.iloc[-1]; prev = df.iloc[-2]
    if pd.isna(last["MA20"]) or pd.isna(last["MA50"]): return None

    c, ma20, ma50 = last["close"], last["MA20"], last["MA50"]
    rsi = last["RSI"] if not pd.isna(last["RSI"]) else 50
    vol = last["vol_ratio"] if not pd.isna(last["vol_ratio"]) else 1.0
    adx = int(last["ADX"]) if not pd.isna(last["ADX"]) else 20
    dist50 = (c - ma50)/ma50*100
    dist20 = (c - ma20)/ma20*100

    # SCORING HYBRID
    score = 0
    if c > ma20 and c > ma50: score += 20
    if ma20 > ma50: score += 15 # Golden cross V9
    if 0 < dist50 <= 7: score += 10
    if 50 <= rsi <= 70: score += 15
    elif rsi > 70: score += 5
    if vol >= 1.5: score += 15
    elif vol >= 1.2: score += 8
    if adx > 25: score += 10
    if ticker in KINGS: score += 5

    # 6 TIPE TREND
    is_new_break50 = c > ma50 and prev["close"] <= df.iloc[-2]["MA50"]
    is_new_break20 = c > ma20 and prev["close"] <= df.iloc[-2]["MA20"]

    if (is_new_break50 or is_new_break20) and vol >= 1.5 and adx > 25 and 50 <= rsi <= 70 and c > ma20 > ma50:
        label, stars = "STRONG BREAKOUT", 4 # 70-100
    elif (is_new_break50 or is_new_break20):
        label, stars = "BREAKOUT", 3 # 55-69
        score = max(score, 60)
    elif c > ma20 and ma20 > ma50 and 5 < dist50 <= 25:
        label, stars = "UPTREND", 2 # 40-54
    elif -3 <= dist50 <= 3:
        label, stars = "NEAR BREAKOUT", 1 # 25-39
    elif adx < 20 and abs(dist50) < 8:
        label, stars = "WEAK/SIDEWAYS", 0
    else:
        label, stars = "DOWNTREND", 0

    # FILTER UTAMA: LONG TERM CUMA 2 INI YANG DIKIRIM
    if label not in ["STRONG BREAKOUT", "UPTREND"]:
        return None

    if score < 40: return None

    lot = int(1000000/c) if c>0 else 0
    msg = f"#{ticker} {score} {label} - BUY\n{'⭐'*stars}\n"
    msg += f"Price: {int(c)} MA20:{int(ma20)} MA50:{int(ma50)} ({dist50:+.1f}%)\n"
    msg += f"Vol:{vol:.1f}x RSI:{int(rsi)} ADX:{adx} Lot:{lot}\n"
    msg += f"MA20>MA50: {'YES ✅' if ma20>ma50 else 'NO'} | Entry:{int(c*0.995)}-{int(c*1.005)}\n"
    msg += f"SL:{int(c*0.95)} TP1:{int(c*1.12)} TP2:{int(c*1.25)} | {BATCH_LABEL}"
    return {"score": score, "msg": msg}

def main():
    with open(TICKER_FILE) as f:
        tickers = [x.strip() for x in f if x.strip() and not x.startswith("#")]
    results=[]
    with ThreadPoolExecutor(max_workers=15) as ex:
        for fu in as_completed({ex.submit(analyze,t):t for t in tickers}):
            r=fu.result()
            if r: results.append(r)
    results=sorted(results, key=lambda x:x["score"], reverse=True)[:10]
    if not results:
        send(f"🔍 {BATCH_LABEL} {TICKER_FILE} {datetime.now():%d %b %H:%M} - Tidak ada STRONG BREAKOUT/UPTREND")
        return
    header=f"🔥 SCAN HYBRID MA20+MA50 {datetime.now():%d %b %H:%M}\n{BATCH_LABEL} - {TICKER_FILE}\n\n"
    full=header+"\n\n".join([r["msg"] for r in results])
    send(full)

if __name__=="__main__": main()
