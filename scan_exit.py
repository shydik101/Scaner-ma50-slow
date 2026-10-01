import os, json, requests, pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

TICKER_FILE = os.getenv("TICKER_FILE", "tickers-batch1.txt")
PROXY_URL = "https://yahoo-proxy.rizalmawardi766.workers.dev"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
HOLDINGS_FILE = "my_holdings.json"
DIVIDEN_KINGS = {"BBCA.JK","BBRI.JK","BMRI.JK","BBNI.JK","BBTN.JK","TLKM.JK","ASII.JK","UNTR.JK","PTBA.JK","ADRO.JK","ITMG.JK","ANTM.JK","ICBP.JK","INDF.JK","KLBF.JK","SMGR.JK","INTP.JK"}

def send_telegram(msg):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID: print(msg); return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try: requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=10)
    except: pass

def save_to_holdings(ticker, entry_price, score):
    holdings = {}
    if os.path.exists(HOLDINGS_FILE):
        try:
            with open(HOLDINGS_FILE, "r") as f: holdings = json.load(f)
        except: holdings = {}
    if ticker not in holdings:
        tipe = "GORENGAN" if "batch2" in TICKER_FILE.lower() else "BIGCAP"
        holdings[ticker] = {"entry": int(entry_price), "date": datetime.now().strftime("%Y-%m-%d"), "score": score, "tipe": tipe, "source_file": TICKER_FILE}
        with open(HOLDINGS_FILE, "w") as f: json.dump(holdings, f, indent=2)

def get_data(ticker):
    try:
        r = requests.get(f"{PROXY_URL}/?ticker={ticker}", timeout=15)
        data = r.json()
        closes = data["chart"]["result"][0]["indicators"]["quote"][0]["close"]
        vols = data["chart"]["result"][0]["indicators"]["quote"][0]["volume"]
        df = pd.DataFrame({"close": closes, "vol": vols}).dropna()
        return df if len(df)>=60 else None
    except: return None

def analyze_ticker(ticker):
    df = get_data(ticker)
    if df is None: return None
    df["MA50"] = df["close"].rolling(50).mean(); df["MA20"] = df["close"].rolling(20).mean()
    delta = df["close"].diff(); gain = (delta.where(delta>0,0)).rolling(14).mean(); loss = (-delta.where(delta<0,0)).rolling(14).mean()
    rs = gain/loss; df["RSI"] = 100 - (100/(1+rs)); df["vol_avg"] = df["vol"].rolling(20).mean(); df["vol_ratio"] = df["vol"]/df["vol_avg"]
    last = df.iloc[-1]; prev = df.iloc[-2]; close = last["close"]; ma50 = last["MA50"]
    if pd.isna(ma50): return None
    rsi = 0 if pd.isna(last["RSI"]) else last["RSI"]; vol = 0 if pd.isna(last["vol_ratio"]) else last["vol_ratio"]; dist = ((close-ma50)/ma50)*100
    score=0
    if close>ma50 and prev["close"]<=df.iloc[-2]["MA50"]: score+=40
    elif close>ma50: score+=20
    if vol>=1.5: score+=15
    if 50<=rsi<=70: score+=15
    if 0<dist<=7: score+=10
    if close>last["MA20"]: score+=5
    if score<55: return None
    if score>=70: trend, stars = "STRONG BREAKOUT", 4
    else: trend, stars = "BREAKOUT", 3
    ma50_v=int(ma50); sl=int(close*0.95); tp1=int(close*1.12); tp2=int(close*1.25); el=int(close*0.995); eh=int(close*1.005); lot=int(1000000/close) if close>0 else 0
    tipe_label = "GORENGAN" if "batch2" in TICKER_FILE.lower() else "BIGCAP LONG-TERM"
    msg = f"#{ticker} {score} {trend} - BUY ({tipe_label})\n{'⭐'*stars}\nHarga: {int(close)} | MA50: {ma50_v} ({dist:+.1f}% di atas MA50)\nVol: {vol:.1f}x | RSI: {int(rsi)} | Lot {lot}\nEntry: {el}-{eh} SL: {sl} (-5%) TP: {tp1} (+12%) / {tp2}\n"
    msg += "Trend: SCALP - Hold 1-3 Hari" if "batch2" in TICKER_FILE.lower() else "Trend: UPTREND - Hold 1-3 Bulan"
    if ticker in DIVIDEN_KINGS: msg += "\nDividen King ⭐"
    if score>=70: save_to_holdings(ticker, close, score)
    return {"score":score, "msg":msg, "ticker":ticker}

def main():
    with open(TICKER_FILE) as f: tickers=[l.strip() for l in f if l.strip() and not l.startswith("#")]
    results=[]
    with ThreadPoolExecutor(max_workers=15) as ex:
        futs={ex.submit(analyze_ticker,t):t for t in tickers}
        for fu in as_completed(futs):
            r=fu.result()
            if r: results.append(r)
    results=sorted(results, key=lambda x:x["score"], reverse=True)[:10]
    if not results: send_telegram(f"🔍 SCAN V9.2 {datetime.now():%d %b %H:%M} - {TICKER_FILE}\nTidak ada BREAKOUT."); return
    full=f"🔥 SCAN V9.2 {datetime.now():%d %b %H:%M} - {TICKER_FILE}\nTop {len(results)} | Auto tercatat\n\n"
    for i,r in enumerate(results,1): full+=r["msg"].replace(f"#{r['ticker']}",f"#{i} {r['ticker']}")+"\n\n"
    send_telegram(full)

if __name__=="__main__": main()
