import yfinance as yf, os, requests
from datetime import datetime
import pandas as pd

if os.path.exists("daytrade-observe-tickers.txt"):
    TICKER_FILE = "daytrade-observe-tickers.txt"
else:
    TICKER_FILE = "data/daytrade-observe-tickers.txt"

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
MIN_RR = 1.4

def safe_last(s):
    v = s.iloc[-1]
    if isinstance(v, pd.Series):
        v = v.iloc[0]
    return float(v)

def get_tickers():
    with open(TICKER_FILE) as f:
        t = [x.strip() for x in f if x.strip()]
    return [x if x.endswith(".JK") else x+".JK" for x in t]

def analyze(df, ticker):
    if len(df) < 30: return None
    # yfinance baru kadang return MultiIndex
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    close = df['Close']; high = df['High']; low = df['Low']; vol = df['Volume']
    ma20 = close.rolling(20).mean()
    vol_ma20 = vol.rolling(20).mean()
    atr = (high - low).rolling(14).mean()

    last_close = safe_last(close)
    last_ma20 = safe_last(ma20)
    last_vol = safe_last(vol)
    last_vol_ma = safe_last(vol_ma20)
    last_atr = safe_last(atr)
    last_high20 = safe_last(high.rolling(20).max())
    ma20_5 = safe_last(ma20.iloc[-5]) if len(ma20)>=5 else last_ma20
    ma20_slope = (last_ma20 - ma20_5)/ma20_5*100 if ma20_5!=0 else 0

    score=50
    if last_close>last_ma20: score+=15
    if ma20_slope>0: score+=10
    if last_vol>last_vol_ma*1.5: score+=15
    elif last_vol>last_vol_ma: score+=5
    if last_close>=last_high20*0.98: score+=10

    sl = last_ma20 if last_ma20 < last_close else last_close - last_atr*1.5
    tp1 = last_high20
    entry = last_close
    rr = (tp1-entry)/(entry-sl) if (entry-sl)>0 else 0

    if score>=75 and rr>=MIN_RR and last_vol>last_vol_ma*1.2: action="STRONG BREAKOUT - BUY CICIL"
    elif score>=70 and rr>=MIN_RR: action="BREAKOUT - BUY"
    elif score>=55: action="WAIT PULLBACK"
    else: action="SKIP"

    risk_rp = 100_000_000*0.015
    max_lot = int(risk_rp/((entry-sl)*100)) if (entry-sl)>0 else 0

    return {"ticker":ticker,"score":int(score),"close":last_close,"ma20":last_ma20,"entry":entry,"sl":sl,"tp1":tp1,"tp2":last_close+(last_close-sl)*2,"rr":rr,"vol":f"{last_vol/last_vol_ma:.1f}x","trend":f"{ma20_slope:.1f}%","action":action,"max_lot":max(1,max_lot)}

def main():
    tickers=get_tickers()
    print(f"START SCAN {len(tickers)} saham")
    results=[]
    for t in tickers:
        try:
            df=yf.download(t, period="3mo", progress=False, auto_adjust=True)
            if df.empty: continue
            r=analyze(df,t)
            if r and r['score']>=55: results.append(r)
        except Exception as e:
            print(f"ERR {t}: {e}"); continue
    results=sorted(results,key=lambda x:x['score'],reverse=True)
    top=[r for r in results if r['rr']>=MIN_RR][:8]
    now=datetime.now().strftime("%d %b %H:%M")
    msg=f"🔥 SCAN SULTAN LITE {now} | {len(tickers)} saham | R:R>={MIN_RR}\nTop {len(top)}:\n\n"
    for i,r in enumerate(top,1):
        star="⭐"*3 if r['score']>=75 else "⭐"*2
        pct=(r['sl']/r['entry']-1)*100
        msg+=f"#{i} {r['ticker']} {r['score']} - {r['action']} {star}\n H:{r['close']:.0f} MA:{r['ma20']:.0f} Vol:{r['vol']} | E:{r['entry']:.0f} SL:{r['sl']:.0f}({pct:.1f}%) TP:{r['tp1']:.0f} R:R 1:{r['rr']:.1f} {r['max_lot']}lot\n\n"
    if not top:
        msg+=f"Tidak ada R:R >= {MIN_RR} hari ini. Market kurang oke, wait & see."
    print(msg)
    if BOT_TOKEN and CHAT_ID:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={"chat_id":CHAT_ID,"text":msg})
        print("Telegram terkirim!")
    else:
        print(f"Token ada? {bool(BOT_TOKEN)} Chat ada? {bool(CHAT_ID)}")

if __name__=="__main__":
    main()
