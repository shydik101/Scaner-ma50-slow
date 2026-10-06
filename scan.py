import os, requests, pandas as pd, time, json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--market', default=os.getenv("MARKET", "IDX"))
parser.add_argument('--ticker_file', default=os.getenv("TICKER_FILE", "tickers-batch1.txt"))
args, _ = parser.parse_known_args()

MARKET = args.market.upper()
TICKER_FILE = args.ticker_file
BATCH_LABEL = os.getenv("BATCH_LABEL", f"{MARKET}-HYBRID")

HISTORY_FILE = "history_etf.json" if MARKET == "US" else "history.json"
PROXY_URL = "https://yahoo-proxy.rizalmawardi766.workers.dev"
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send(msg):
    if TOKEN and CHAT_ID:
        try:
            requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=20)
        except: pass
    print(msg)

def get_df(ticker):
    for _ in range(3):
        try:
            r = requests.get(f"{PROXY_URL}/?ticker={ticker}", timeout=15).json()
            q = r["chart"]["result"][0]["indicators"]["quote"][0]
            df = pd.DataFrame({"close": q["close"], "vol": q["volume"]}).dropna()
            if len(df) >= 60: return df, 1
        except: time.sleep(1); continue
    return None, 3

def load_history():
    if not os.path.exists(HISTORY_FILE): return {}
    try:
        with open(HISTORY_FILE, 'r') as f: return json.load(f)
    except: return {}

def save_history_merged(history, today_tickers):
    today = datetime.now().strftime("%d-%m-%Y")
    existing = history.get(today, [])
    merged = sorted(list(set(existing + today_tickers)))
    history[today] = merged
    cutoff = datetime.now() - timedelta(days=7)
    def parse(k):
        try: return datetime.strptime(k, "%d-%m-%Y")
        except:
            try: return datetime.strptime(k, "%Y-%m-%d")
            except: return cutoff
    history = {k:v for k,v in history.items() if parse(k) >= cutoff}
    with open(HISTORY_FILE, 'w') as f: json.dump(history, f, indent=2)

def count_streak(history, ticker):
    def parse(k):
        try: return datetime.strptime(k, "%d-%m-%Y")
        except:
            try: return datetime.strptime(k, "%Y-%m-%d")
            except: return datetime.min
    dates = sorted(history.keys(), key=parse, reverse=True)
    streak = 0
    for d in dates:
        if ticker in history[d]: streak += 1
        else: break
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
    lot=int(1000000/c) if MARKET!="US" and c>0 else int(1000/c) if c>0 else 0
    return {"ticker": ticker, "score": score, "label": label, "stars": stars, "c": c, "ma20": ma20, "ma50": ma50, "dist": dist50, "vol": vol, "rsi": rsi, "adx": adx, "lot": lot, "retry": retry}

def main():
    start=time.time()
    with open(TICKER_FILE) as f: tickers=[x.strip() for x in f if x.strip() and not x.startswith("#")]
    history=load_history()
    results=[]
    with ThreadPoolExecutor(max_workers=15) as ex:
        futs={ex.submit(analyze,t):t for t in tickers}
        for fu in as_completed(futs):
            r=fu.result()
            if r: results.append(r)
    results=sorted(results, key=lambda x:x["score"], reverse=True)[:10]
    today_list=[r["ticker"] for r in results]
    save_history_merged(history, today_list)
    history=load_history()

    if not results:
        send(f"🔍 *{BATCH_LABEL}* {datetime.now():%d %b %H:%M} [{MARKET}]\nTidak ada sinyal Bintang 3+ hari ini.")
        return

    header = f"🔥 *SCAN HYBRID V11 PRO*\n{datetime.now():%d %b %H:%M} WIB | Market: {MARKET}\nFilter: Bintang 3+ | Top {len(results)} | {BATCH_LABEL}\n"
    body_lines=[]
    for i, r in enumerate(results, 1):
        streak=count_streak(history, r["ticker"])
        entry=r["c"]; sl=entry*0.95; risk=entry-sl; tp=entry+(risk*2); rr=(tp-entry)/risk
        entry_low=entry*0.995; entry_high=entry*1.005; sl_pct=(entry-sl)/entry*100; tp_pct=(tp-entry)/entry*100
        stars="⭐"*r["stars"]
        msg = f"━━━━━━━━━━━━━━━━━━\n*{i}. #{r['ticker']}* — {r['label']} {stars} ({r['stars']}/5)\n"
        if MARKET=="US":
            msg+=f"💰 Price: ${r['c']:.2f} | MA20:{r['ma20']:.2f} MA50:{r['ma50']:.2f} ({r['dist']:+.1f}%)\n"
        else:
            msg+=f"💰 Price: {int(r['c'])} | MA20:{int(r['ma20'])} MA50:{int(r['ma50'])} ({r['dist']:+.1f}%)\n"
        msg+=f"📊 Vol:{r['vol']:.1f}x | RSI:{int(r['rsi'])} ADX:{r['adx']} | Lot:{r['lot']}\n"
        msg+=f"🎯 Entry: {entry_low:.2f}-{entry_high:.2f} | SL: {sl:.2f} (-{sl_pct:.0f}%)\n"
        msg+=f"💎 TP: {tp:.2f} (+{tp_pct:.0f}%) | *RR: 1 : {rr:.1f}*\n"
        if streak>=3: msg+=f"🔥 Muncul {streak}x berturut - Lagi HOT!"
        elif streak==2: msg+=f"🔁 Muncul {streak}x berturut - Lanjutan kemarin"
        elif streak==1 and len(history)>1: msg+=f"✨ New - Muncul pertama dalam 7 hari"
        elif streak==1: msg+=f"✨ New - Pertama kali muncul"
        else: msg+=f"💤 Absen lama, baru muncul lagi"
        body_lines.append(msg)

    footer=f"\n\n━━━━━━━━━━━━━━━━\n📊 Total: {len(tickers)} | Lolos: {len(results)} | ⏱️ {time.time()-start:.1f}s"
    send(header + "\n\n".join(body_lines) + footer)

if __name__=="__main__": main()
