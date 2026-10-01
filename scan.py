import os, requests, pandas as pd, time, json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

TICKER_FILE = os.getenv("TICKER_FILE", "tickers-batch1.txt")
BATCH_LABEL = os.getenv("BATCH_LABEL", "HYBRID")
PROXY_URL = "https://yahoo-proxy.rizalmawardi766.workers.dev"
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
HISTORY_FILE = "history.json"

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
            if len(df) >= 210: return df, attempt+1
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
    cutoff = datetime.now() - timedelta(days=7)
    history = {k:v for k,v in history.items() if datetime.strptime(k, "%Y-%m-%d") >= cutoff}
    with open(HISTORY_FILE, 'w') as f: json.dump(history, f, indent=2)

def count_streak(history, ticker):
    dates = sorted(history.keys(), reverse=True)
    streak = 0
    for d in dates:
        if ticker in history[d]: streak += 1
        else: break
    return streak

def analyze(ticker, history):
    df, retry = get_df(ticker)
    if df is None: return None

    df["MA20"]=df["close"].rolling(20).mean()
    df["MA50"]=df["close"].rolling(50).mean()
    df["MA200"]=df["close"].rolling(200).mean()
    df["vol_avg"]=df["vol"].rolling(20).mean()
    df["vol_ratio"]=df["vol"]/df["vol_avg"]

    delta=df["close"].diff()
    gain=delta.where(delta>0,0).rolling(14).mean()
    loss=-delta.where(delta<0,0).rolling(14).mean()
    df["RSI"]=100-(100/(1+gain/loss))
    df["ADX"]=(df["close"].diff().abs().rolling(14).mean()/df["close"]*1000).clip(10,50)

    last=df.iloc[-1]; prev=df.iloc[-2]
    if pd.isna(last["MA20"]) or pd.isna(last["MA50"]) or pd.isna(last["MA200"]): return None

    c, ma20, ma50, ma200 = last["close"], last["MA20"], last["MA50"], last["MA200"]
    rsi = last["RSI"] if not pd.isna(last["RSI"]) else 50
    rsi_prev = prev["RSI"] if not pd.isna(prev["RSI"]) else 50
    vol = last["vol_ratio"] if not pd.isna(last["vol_ratio"]) else 1.0
    vol_raw = last["vol"]
    vol_prev = prev["vol"]
    adx=int(last["ADX"]) if not pd.isna(last["ADX"]) else 20

    dist20 = (c - ma20) / ma20 * 100
    dist50 = (c - ma50) / ma50 * 100
    dist200 = (c - ma200) / ma200 * 100
    discount_gorengan = (c - ma20) / c * 100
    streak=count_streak(history, ticker)

    # ============ MODE 1: BIG CAPS DISKON BALIK ARAH ============
    if not IS_GORENGAN:
        # 1. Diskon MA20 -4% s/d +1%
        if dist20 < -4 or dist20 > 1: return None
        # 2. MA50 & MA200 Menyesuaikan
        if not (ma50 > ma200): return None
        if not (ma50 > df.iloc[-2]["MA50"]): return None
        # 3. Balik Arah
        is_price_up = last["close"] > prev["close"]
        is_rsi_up = rsi > rsi_prev and 48 <= rsi <= 62
        is_ma20_turn = ma20 > prev["MA20"]
        is_not_jebol = c > ma50 * 0.93

        if not (is_price_up and is_rsi_up and is_ma20_turn and is_not_jebol):
            return None
        # Jarak MA50 wajar
        if not (0 <= dist50 <= 15 and dist200 >=5): return None

        score = 80
        if -2 <= dist20 <= 0: score += 15
        if c > ma20 and prev["close"] < prev["MA20"]:
            label, stars = "DISKON BREAK MA20 - BALIK ARAH UP", 5
            score += 10
        else:
            label, stars = "DISKON GOLDEN BOTTOM - SIAP BALIK ARAH", 5

        lot=int(1000000/c) if c>0 else 0
        return {"ticker": ticker, "score": score, "label": label, "stars": stars, "c": c, "ma20": ma20, "ma50": ma50, "ma200": ma200, "dist20": dist20, "dist50": dist50, "dist200": dist200, "vol": vol, "rsi": rsi, "rsi_prev": rsi_prev, "adx": adx, "lot": lot, "retry": retry, "streak": streak, "is_gorengan": False}

    # ============ MODE 2: GORENGAN HOLD 1-2 MINGGU 3-10% ============
    else:
        # Filter ketat 3-10%
        if discount_gorengan < 3 or discount_gorengan > 10: return None
        if streak >= 4: return None
        if rsi > 68: return None
        if vol > 3.0 or vol < 1.2: return None
        if not (ma20 > ma50 and last["close"] > ma20): return None

        score = 80
        if 3 <= discount_gorengan <= 6: score += 15
        if streak <= 2: score += 10

        # Anti-FOMO final check
        is_overheat = False
        if streak >=3 and discount_gorengan > 8:
            score -= 20
            is_overheat = True

        label, stars = "PULLBACK MA20 - HOLD 1-2 MINGGU", 5
        if is_overheat:
            label = "FOMO PULLBACK - HATI-HATI"
            stars = 3

        lot=int(1000000/c) if c>0 else 0
        return {"ticker": ticker, "score": score, "label": label, "stars": stars, "c": c, "ma20": ma20, "ma50": ma50, "ma200": ma200, "dist20": dist20, "discount": discount_gorengan, "vol": vol, "rsi": rsi, "adx": adx, "lot": lot, "retry": retry, "streak": streak, "is_gorengan": True, "overheat": is_overheat}

def main():
    start=time.time()
    with open(TICKER_FILE) as f: tickers=[x.strip() for x in f if x.strip() and not x.startswith("#")]
    history=load_history()
    results=[]; total_retry=0
    with ThreadPoolExecutor(max_workers=15) as ex:
        futs={ex.submit(analyze,t,history):t for t in tickers}
        for fu in as_completed(futs):
            r=fu.result()
            if r: results.append(r); total_retry+=r["retry"]
    results=sorted(results, key=lambda x:x["score"], reverse=True)[:10]
    today_list=[r["ticker"] for r in results]
    save_history(history, today_list)
    history=load_history()

    mode_name = "GORENGAN HOLD 1-2 MINGGU (MA20 3-10%)" if IS_GORENGAN else "BIG CAPS DISKON BALIK ARAH (MA20 -4% s/d +1%)"

    if not results:
        send(f"🔍 {BATCH_LABEL} {datetime.now():%d %b %H:%M}\n{mode_name}\nTidak ada sinyal hari ini. Filter ketat.\n\n📊 Total:{len(tickers)} | 🔁 Retry:{total_retry} | ⏱️ {time.time()-start:.1f}s")
        return

    header=f"🔥 SCAN V10.7 {datetime.now():%d %b %H:%M}\n{mode_name}\n{BATCH_LABEL} | {TICKER_FILE}\n\n"
    body_lines=[]
    for i, r in enumerate(results, 1):
        if not r["is_gorengan"]:
            msg=f"{i}. #{r['ticker']} {r['score']} {r['label']}\n{'⭐'*r['stars']} ({r['stars']}/5)\n"
            msg+=f"Price:{int(r['c'])} MA20:{int(r['ma20'])} ({r['dist20']:+.1f}%)\n"
            msg+=f"MA50:{int(r['ma50'])} ({r['dist50']:+.1f}%) MA200:{int(r['ma200'])} ({r['dist200']:+.1f}%)\n"
            msg+=f"RSI:{int(r['rsi'])} (prev {int(r['rsi_prev'])}) ↗️ Vol:{r['vol']:.1f}x ADX:{r['adx']}\n"
            msg+=f"🎯 Best Buy: {int(r['ma20']*0.99)}-{int(r['ma20']*1.01)} (Nempel MA20)\n"
            msg+=f"SL: MA50 {int(r['ma50'])} | Target +15% (1-3 bln)"
        else:
            streak_txt = f"{r['streak']}x" if r['streak']>0 else "New"
            msg=f"{i}. #{r['ticker']} {r['score']} {r['label']}\n{'⭐'*r['stars']} ({r['stars']}/5)\n"
            msg+=f"Price:{int(r['c'])} MA20:{int(r['ma20'])} ({r['discount']:.1f}%) ✅ 3-10%\n"
            msg+=f"MA50:{int(r['ma50'])} MA200:{int(r['ma200'])}\n"
            msg+=f"Vol:{r['vol']:.1f}x RSI:{int(r['rsi'])} ADX:{r['adx']} Lot:{r['lot']}\n"
            msg+=f"🎯 Best Buy Mingguan: {int(r['ma20']*1.01)}-{int(r['ma20']*1.03)}\n"
            msg+=f"SL:{int(r['ma20']*0.96)} (-4%) | Entry Harian: {int(r['c']*0.99)}\n"
            msg+=f"🔁 Streak: {streak_txt} {'⚠️ Overheat' if r.get('overheat') else '✅ Aman Hold'}"
        body_lines.append(msg)

    body="\n\n".join(body_lines)
    footer=f"\n\n━━━━━━━━━━━━━━━━\n📊 Total:{len(tickers)} Lolos:{len(results)}\n🔁 Retry 3x: {total_retry} | ⏱️ {time.time()-start:.1f}s | Mode: {mode_name}"
    send(header+body+footer)

if __name__=="__main__": main()
