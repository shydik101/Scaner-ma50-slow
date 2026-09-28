import yfinance as yf, os, requests, pandas as pd
from datetime import datetime

TICKER_FILE = "daytrade-observe-tickers.txt" if os.path.exists("daytrade-observe-tickers.txt") else "data/daytrade-observe-tickers.txt"
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
MIN_RR = 1.4

def last(s):
    # aman untuk semua versi yfinance
    try:
        v = s.iloc[-1]
        if isinstance(v, pd.Series):
            v = v.iloc[0]
        if hasattr(v, 'item'):
            return float(v.item())
        return float(v)
    except:
        return float(s)

def get_tickers():
    with open(TICKER_FILE) as f:
        t = [x.strip().upper() for x in f if x.strip() and not x.startswith('#')]
    return [x if x.endswith(".JK") else x+".JK" for x in t]

def analyze(df, ticker):
    if len(df) < 30: return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    close = df['Close']; high = df['High']; low = df['Low']; vol = df['Volume']
    ma20 = close.rolling(20).mean()
    vol_ma20 = vol.rolling(20).mean()
    atr = (high - low).rolling(14).mean()

    c = last(close); m = last(ma20); v = last(vol); vm = last(vol_ma20); a = last(atr); h20 = last(high.rolling(20).max())
    m5 = float(ma20.iloc[-6]) if len(ma20)>5 else m # ambil 5 candle lalu, tanpa safe_last dobel
    slope = (m - m5)/m5*100 if m5!=0 else 0

    score=50
    if c>m: score+=15
    if slope>0: score+=10
    if v>vm*1.5: score+=15
    elif v>vm: score+=5
    if c>=h20*0.98: score+=10

    sl = m if m < c else c - a*1.5
    tp1 = h20
    rr = (tp1-c)/(c-sl) if (c-sl)>0 else 0

    if score>=75 and rr>=MIN_RR and v>vm*1.2: act="STRONG BREAKOUT - BUY CICIL"
    elif score>=70 and rr>=MIN_RR: act="BREAKOUT - BUY"
    elif score>=55: act="WAIT PULLBACK"
    else: act="SKIP"

    max_lot = int((100_000_000*0.015)/((c-sl)*100)) if c>sl else 1
    return {"ticker":ticker,"score":int(score),"c":c,"m":m,"sl":sl,"tp1":tp1,"rr":rr,"vol":f"{v/vm:.1f}x","trend":f"{slope:.1f}%","action":act,"lot":max(1,max_lot)}

def main():
    tickers = get_tickers()
    print(f"START {len(tickers)} saham")
    res=[]
    for t in tickers:
        try:
            df=yf.download(t, period="3mo", progress=False, auto_adjust=True)
            if df.empty or len(df)<25: continue
            r=analyze(df,t)
            if r and r['score']>=55: res.append(r)
        except Exception as e:
            print(f"ERR {t}: {e}"); continue

    res=sorted(res,key=lambda x:x['score'],reverse=True)
    top=[r for r in res if r['rr']>=MIN_RR][:8]
    now=datetime.now().strftime("%d %b %H:%M")
    msg=f"🔥 SCAN SULTAN {now} | {len(tickers)} saham | R:R>={MIN_RR}\nTop {len(top)}:\n\n"
    for i,r in enumerate(top,1):
        pct=(r['sl']/r['c']-1)*100
        msg+=f"#{i} {r['ticker']} {r['score']} - {r['action']}\n {r['c']:.0f} MA{r['m']:.0f} Vol{r['vol']} | SL{r['sl']:.0f}({pct:.1f}%) TP{r['tp1']:.0f} RR 1:{r['rr']:.1f} {r['lot']}lot\n\n"
    if not top:
        msg+=f"Tidak ada RR>={MIN_RR}. Market choppy. Top score {res[0]['score'] if res else 0}"
    print(msg)
    if BOT_TOKEN and CHAT_ID:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={"chat_id":CHAT_ID,"text":msg})
        print("TELEGRAM OK")
    else:
        print(f"SECRET ERROR Token={bool(BOT_TOKEN)} Chat={bool(CHAT_ID)}")

if __name__=="__main__":
    main()
