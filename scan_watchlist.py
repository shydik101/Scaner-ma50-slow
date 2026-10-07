import os, requests, pandas as pd, time, json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

TICKER_FILE = os.getenv("TICKER_FILE", "tickers-watchlist.txt")
BATCH_LABEL = os.getenv("BATCH_LABEL", "WATCHLIST")
HISTORY_FILE = "history.json"
PROXY_URL = "https://yahoo-proxy.rizalmawardi766.workers.dev"
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
WIB = timezone(timedelta(hours=7))

def send(msg):
    if TOKEN and CHAT_ID:
        try: requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=20)
        except: pass
    print(msg)

def get_df(ticker):
    for _ in range(3):
        try:
            r = requests.get(f"{PROXY_URL}/?ticker={ticker}", timeout=15).json()
            q = r["chart"]["result"][0]["indicators"]["quote"][0]
            df = pd.DataFrame({
                "close": q["close"], "vol": q["volume"],
                "high": q.get("high", q["close"]), "low": q.get("low", q["close"]),
                "open": q.get("open", q["close"])
            }).dropna()
            if len(df) >= 60: return df, 1
        except: time.sleep(1); continue
    return None, 3

def analyze_watchlist(ticker):
    df, retry = get_df(ticker)
    if df is None: return None
    df["MA20"]=df["close"].rolling(20).mean(); df["MA50"]=df["close"].rolling(50).mean()
    df["MA200"]=df["close"].rolling(200).mean()
    df["vol_avg"]=df["vol"].rolling(20).mean(); df["vol_ratio"]=df["vol"]/df["vol_avg"]
    df["ATR"]=df["close"].diff().abs().rolling(14).mean()
    delta=df["close"].diff(); gain=delta.where(delta>0,0).rolling(14).mean(); loss=-delta.where(delta<0,0).rolling(14).mean()
    df["RSI"]=100-(100/(1+gain/loss)); df["ADX"]=(df["close"].diff().abs().rolling(14).mean()/df["close"]*1000).clip(10,50)
    last=df.iloc[-1]
    c,h,l,o = last["close"], last["high"], last["low"], last["open"]
    ma20, ma50, ma200 = last["MA20"], last["MA50"], last["MA200"]
    atr, vol, rsi, adx = last["ATR"], last["vol_ratio"], last["RSI"], int(last["ADX"])
    if pd.isna(ma20) or pd.isna(ma50): return None

    # Support Resistance ala V11.8 Pro
    dist_ma20 = (c-ma20)/ma20*100; dist_ma50 = (c-ma50)/ma50*100; dist_ma200 = (c-ma200)/ma200*100 if not pd.isna(ma200) else 0
    pivot = (h+l+last["close"])/3
    s1 = 2*pivot - h; s2 = pivot - (h - l); r1 = 2*pivot - l; r2 = pivot + (h - l)

    # Scoring khusus watchlist (lebih longgar dari scan buy)
    score = 0
    if c > ma20: score+=20
    if ma20 > ma50: score+=15
    if rsi >= 35 and rsi <= 65: score+=15
    if vol >= 1.2: score+=10
    if adx > 20: score+=10

    # Label trend
    if c > ma20 and c > ma50 and c > ma200: label, stars = "UPTREND KUAT", 4
    elif c > ma20 and ma20 > ma50: label, stars = "UPTREND", 3
    elif c > ma20: label, stars = "NEAR BREAKOUT MA20", 2
    elif abs(dist_ma50) <= 4: label, stars = "NEMPEL MA50", 1
    else: label, stars = "DOWNTREND / AKUMULASI", 0

    # Bandar quick check
    range_hl = h-l if h!=l else 1
    close_pos = (c-l)/range_hl*100
    upper_wick = (h-max(c,o))/range_hl*100
    if close_pos >=80 and vol>=1.8 and upper_wick<20: bandar="🟢 AKUM BANDAR"
    elif upper_wick>40 and vol>=1.8: bandar="🔴 DISTRIBUSI"
    else: bandar="⚪ NETRAL"

    # SL TP RR
    sl = c - max(c*0.04, atr*1.5)
    tp1 = c + atr*1.5; tp2 = c + atr*2.5
    rr1 = (tp1-c)/(c-sl) if c>sl else 0

    # Keputusan V11.8 style
    if stars >=3 and vol>=1.5 and rsi>=50: keputusan = "✅ GAS CICIL / BUY"
    elif stars ==2 and vol>=1.5: keputusan = "🟡 CICIL 30% BAWAH"
    elif stars <=1 and rsi <40: keputusan = "⏳ TUNGGU PANTULAN - JANGAN AVERAGE DOWN"
    else: keputusan = "👀 WATCH - BELUM VALID"

    return {
        "ticker": ticker.replace(".JK",""), "c": c, "ma20": ma20, "ma50": ma50, "ma200": ma200,
        "dist20": dist_ma20, "dist50": dist_ma50, "dist200": dist_ma200,
        "vol": vol, "rsi": rsi, "adx": adx, "atr": atr,
        "s1": s1, "s2": s2, "r1": r1, "r2": r2, "pivot": pivot,
        "label": label, "stars": stars, "score": score, "bandar": bandar,
        "close_pos": close_pos, "sl": sl, "tp1": tp1, "tp2": tp2, "rr": rr1,
        "keputusan": keputusan
    }

def main():
    now_wib = datetime.now(WIB)
    if not os.path.exists(TICKER_FILE):
        # Auto create kalau belum ada
        with open(TICKER_FILE, 'w') as f: f.write("BMRI.JK\n")
    with open(TICKER_FILE) as f: tickers=[x.strip() for x in f if x.strip() and not x.startswith("#")]
    results=[]
    with ThreadPoolExecutor(max_workers=10) as ex:
        futs={ex.submit(analyze_watchlist,t):t for t in tickers}
        for fu in as_completed(futs):
            r=fu.result()
            if r: results.append(r)
    if not results:
        send(f"👁️ *WATCHLIST RADAR V11.8.1* {now_wib:%d %b %H:%M WIB}\nGak ada data")
        return
    header=f"👁️ *WATCHLIST RADAR V11.8.1 PRO*\n{now_wib:%d %b %H:%M WIB} | {BATCH_LABEL}\nDetail BMRI & Watchlist\n"
    lines=[]
    for r in results:
        stars="⭐"*r["stars"] if r["stars"]>0 else "💤"
        msg=f"━━━━━━━━━━━━━━━━━━\n*#{r['ticker']}* — {r['label']} {stars} Skor:{r['score']}\n"
        msg+=f"💰 {int(r['c'])} | MA20:{int(r['ma20'])} ({r['dist20']:+.1f}%) MA50:{int(r['ma50'])} ({r['dist50']:+.1f}%) MA200:{int(r['ma200'])} ({r['dist200']:+.1f}%)\n"
        msg+=f"📊 Vol:{r['vol']:.1f}x Pos:{r['close_pos']:.0f}% RSI:{int(r['rsi'])} ADX:{r['adx']} ATR:{r['atr']:.0f}\n"
        msg+=f"{r['bandar']} | Pivot:{r['pivot']:.0f}\n"
        msg+=f"🛡️ S2:{r['s2']:.0f} S1:{r['s1']:.0f} | 🎯 R1:{r['r1']:.0f} R2:{r['r2']:.0f}\n"
        msg+=f"SL:{r['sl']:.0f} TP1:{r['tp1']:.0f} TP2:{r['tp2']:.0f} RR 1:{r['rr']:.2f}\n"
        msg+=f"📋 *{r['keputusan']}*"
        # Analisa khusus BMRI sampai Jumat
        if r['ticker']=="BMRI":
            msg+=f"\n\n*Ramalan BMRI s/d Jumat:*\nBase: 4050-4100, Bear case 3990-4020 jebol = 3950, Bull case close >4130 = NEAR BREAKOUT"
        lines.append(msg)
    send(header + "\n".join(lines))

if __name__=="__main__": main()
