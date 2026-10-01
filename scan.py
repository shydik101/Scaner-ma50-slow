import os, requests, pandas as pd, time, json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from collections import defaultdict

TICKER_FILE = os.getenv("TICKER_FILE", "tickers-batch1.txt")
BATCH_LABEL = os.getenv("BATCH_LABEL", "HYBRID")
PROXY_URL = "https://yahoo-proxy.rizalmawardi766.workers.dev"
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
HISTORY_FILE = "history.json"

KINGS = {"BBCA.JK","BBRI.JK","BMRI.JK","BBNI.JK","TLKM.JK","ASII.JK","UNTR.JK","BBTN.JK"}

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

def load_history():
    if not os.path.exists(HISTORY_FILE): return {}
    try:
        with open(HISTORY_FILE, 'r') as f: return json.load(f)
    except: return {}

def save_history(history, today_tickers):
    today = datetime.now().strftime("%Y-%m-%d")
    history[today] = today_tickers
    # hapus data lebih dari 7 hari
    cutoff = datetime.now() - timedelta(days=7)
    history = {k:v for k,v in history.items() if datetime.strptime(k, "%Y-%m-%d") >= cutoff}
    with open(HISTORY_FILE, 'w') as f: json.dump(history, f, indent=2)

def count_streak(history, ticker):
    # hitung berapa kali muncul berturut-turut ke belakang dalam 7 hari
    dates = sorted(history.keys(), reverse=True) # terbaru dulu
    streak = 0
    for d in dates:
        if ticker in history[d]:
            streak += 1
        else:
            break # putus kalau ada hari bolong
    return streak

def analyze(ticker):
    df, retry = get_df(ticker)
    if df is None: return None
    df["MA20"]=df["close"].rolling(20).mean(); df["MA50"]=df["close"].rolling(50).mean()
    df["vol_avg"]=df["vol"].rolling(20).mean(); df["vol_ratio"]=df["vol"]/df["vol_avg"]
    delta=df["close"].diff(); gain=delta.where(delta>0,0).rolling(14).mean(); loss=-delta.where(delta<0,0).rolling(14).mean()
    df["RSI"]=100-(100/(1+gain/loss)); df["ADX"]=(df["close"].diff().abs().rolling(14).mean()/df["close"]*1000).clip(10,50)
    last=df.iloc[-1]; prev=df.iloc[-2]
    if pd.isna(last["MA20"]) or pd.isna(last["MA50"]): return None
    c, ma20, ma50 = last["close"], last["MA20"], last["MA50"]
    rsi=last["RSI"] if not pd.isna(last["RSI"]) else 50; vol=last["vol_ratio"] if not pd.isna(last["vol_ratio"]) else 1.0; adx=int(last["ADX"]) if not pd.isna(last["ADX"]) else 20
    dist50=(c-ma50)/ma50*100
    score=0
    if c>ma20 and c>ma50: score+=20
    if ma20>ma50: score+=15
    if 0<dist50<=7: score+=10
    if 50<=rsi<=70: score+=15
    if vol>=1.5: score+=15
    if adx>25: score+=10
    is_break50=c>ma50 and prev["close"]<=df.iloc[-2]["MA50"]; is_break20=c>ma20 and prev["close"]<=df.iloc[-2]["MA20"]; both_break=is_break50 and is_break20
    if both_break and vol>=2.0 and adx>30 and 55<=rsi<=65: label, stars, score = "SUPER BREAKOUT", 5, 90+int(vol*3)
    elif (is_break50 or is_break20) and vol>=1.5 and adx>25 and 50<=rsi<=70 and c>ma20: label, stars = "STRONG BREAKOUT", 4; score=max(score,75)
    elif (is_break50 or is_break20): label, stars = "BREAKOUT", 3; score=max(score,60)
    elif c>ma20 and ma20>ma50: label, stars = "UPTREND", 2
    elif -3<=dist50<=3: label, stars = "NEAR BREAKOUT", 1
    else: label, stars = "WEAK/DOWNTREND", 0
    if stars<3 or score<55: return None
    lot=int(1000000/c) if c>0 else 0
    return {"ticker": ticker, "score": score, "label": label, "stars": stars, "c": c, "ma20": ma20, "ma50": ma50, "dist": dist50, "vol": vol, "rsi": rsi, "adx": adx, "lot": lot, "retry": retry}

def main():
    start=time.time()
    with open(TICKER_FILE) as f: tickers=[x.strip() for x in f if x.strip() and not x.startswith("#")]
    history=load_history()
    results=[]; total_retry=0
    with ThreadPoolExecutor(max_workers=15) as ex:
        futs={ex.submit(analyze,t):t for t in tickers}
        for fu in as_completed(futs):
            r=fu.result()
            if r: results.append(r); total_retry+=r["retry"]
    results=sorted(results, key=lambda x:x["score"], reverse=True)[:10]

    # hitung streak & simpan history hari ini
    today_list=[r["ticker"] for r in results]
    save_history(history, today_list)
    # reload history yang udah update biar streak hari ini kehitung
    history=load_history()

    if not results:
        send(f"🔍 {BATCH_LABEL} {datetime.now():%d %b %H:%M}\nTidak ada sinyal Bintang 3+ hari ini.\n\n━━━━━━━━\n📊 Total:{len(tickers)} | 🔁 Retry:{total_retry} (3x aktif) | ⏱️ {time.time()-start:.1f}s")
        return

    header=f"🔥 SCAN HYBRID V10.1 {datetime.now():%d %b %H:%M}\n{BATCH_LABEL} | {TICKER_FILE}\nFilter: Bintang 3+ | Top 10\n\n"
    body_lines=[]
    for i, r in enumerate(results, 1):
        streak=count_streak(history, r["ticker"])
        msg=f"{i}. #{r['ticker']} {r['score']} {r['label']}\n{'⭐'*r['stars']} ({r['stars']}/5)\n"
        msg+=f"Price:{int(r['c'])} MA20:{int(r['ma20'])} MA50:{int(r['ma50'])} ({r['dist']:+.1f}%)\n"
        msg+=f"Vol:{r['vol']:.1f}x RSI:{int(r['rsi'])} ADX:{r['adx']} Lot:{r['lot']}\n"
        msg+=f"Entry:{int(r['c']*0.995)}-{int(r['c']*1.005)} SL:{int(r['c']*0.95)}\n"
        # BARIS BARU YANG KAMU MAU
        if streak >= 2:
            msg+=f"🔁 Muncul {streak}x berturut dalam 7 hari terakhir 🔥"
        elif streak == 1:
            msg+=f"🔁 Muncul pertama dalam 7 hari terakhir (New)"
        else:
            msg+=f"🔁 Tidak muncul dalam 7 hari terakhir"
        body_lines.append(msg)

    body="\n\n".join(body_lines)
    footer=f"\n\n━━━━━━━━━━━━━━━━\n📊 Total:{len(tickers)} Lolos:{len(results)}\n🔁 Retry 3x: {total_retry} | ⏱️ {time.time()-start:.1f}s | Maks: 5 Bintang"
    send(header+body+footer)

if __name__=="__main__": main()
