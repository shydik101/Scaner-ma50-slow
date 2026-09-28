import yfinance as yf
import os, requests
from datetime import datetime

# AUTO-CARI FILE TICKER
if os.path.exists("daytrade-observe-tickers.txt"):
    TICKER_FILE = "daytrade-observe-tickers.txt"
elif os.path.exists("data/daytrade-observe-tickers.txt"):
    TICKER_FILE = "data/daytrade-observe-tickers.txt"
else:
    TICKER_FILE = "daytrade-observe-tickers.txt"

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
MIN_RR = 1.4
PORTO = 100_000_000

def get_tickers():
    print(f"DEBUG: Baca {TICKER_FILE} exists={os.path.exists(TICKER_FILE)}")
    with open(TICKER_FILE) as f:
        tickers = [x.strip() for x in f if x.strip()]
    # auto tambah .JK kalau belum ada
    fixed = [t if t.endswith(".JK") else t+".JK" for t in tickers]
    print(f"DEBUG: {len(fixed)} tickers loaded: {fixed[:5]}")
    return fixed

# ... copy sisa function analyze & main dari file kemarin ...

def analyze(df, ticker):
    close = df['Close']
    high = df['High']
    low = df['Low']
    vol = df['Volume']
    if len(df) < 30: return None
    ma20 = close.rolling(20).mean()
    vol_ma20 = vol.rolling(20).mean()
    atr = (high - low).rolling(14).mean()
    last_close = float(close.iloc[-1])
    last_ma20 = float(ma20.iloc[-1])
    last_vol = float(vol.iloc[-1])
    last_vol_ma = float(vol_ma20.iloc[-1])
    last_atr = float(atr.iloc[-1])
    last_high20 = float(high.rolling(20).max().iloc[-1])
    ma20_slope = (ma20.iloc[-1] - ma20.iloc[-5]) / ma20.iloc[-5] * 100 if ma20.iloc[-5]!=0 else 0
    score = 50
    if last_close > last_ma20: score+=15
    if ma20_slope > 0: score+=10
    if last_vol > last_vol_ma*1.5: score+=15
    elif last_vol > last_vol_ma: score+=5
    if last_close >= last_high20*0.98: score+=10
    sl = last_ma20 if last_ma20 < last_close else last_close - last_atr*1.5
    tp1 = last_high20
    tp2 = last_close + (last_close - sl)*2
    entry = last_close
    rr = (tp1 - entry)/(entry - sl) if (entry - sl)>0 else 0
    vol_label = f"{last_vol/last_vol_ma:.1f}x"
    if score>=75 and rr>=MIN_RR and last_vol>last_vol_ma*1.2: action="STRONG BREAKOUT - BUY CICIL"
    elif score>=70 and rr>=MIN_RR: action="BREAKOUT - BUY"
    elif score>=55: action="WAIT PULLBACK"
    else: action="SKIP"
    risk_rp = PORTO*0.015
    risk_per = entry-sl
    max_lot = int(risk_rp/(risk_per*100)) if risk_per>0 else 0
    return {"ticker":ticker,"score":int(score),"close":last_close,"ma20":last_ma20,"entry":entry,"sl":sl,"tp1":tp1,"tp2":tp2,"rr":rr,"vol":vol_label,"trend":f"{ma20_slope:.1f}%","action":action,"max_lot":max(1,max_lot),"risk_rp":risk_rp}

def main():
    print("DEBUG: Start scan...")
    tickers = get_tickers()
    results=[]
    for t in tickers:
        try:
            print(f"SCAN {t}...")
            df = yf.download(t, period="3mo", progress=False, auto_adjust=True)
            if df.empty: continue
            res = analyze(df,t)
            if res and res['score']>=55: results.append(res)
        except Exception as e:
            print(f"ERR {t}: {e}")
            continue
    results = sorted(results, key=lambda x: x['score'], reverse=True)
    top = [r for r in results if r['rr']>=MIN_RR][:8]
    now = datetime.now().strftime("%d %b %H:%M")
    msg = f"🔥 SCAN SULTAN LITE {now} | {len(tickers)} saham | R:R>={MIN_RR}\nTop {len(top)}:\n\n"
    for i,r in enumerate(top,1):
        star="⭐"*3 if r['score']>=75 else "⭐"*2
        pct_sl=(r['sl']/r['entry']-1)*100
        msg+=f"#{i} {r['ticker']} {r['score']} - {r['action']} {star}\n   H:{r['close']:.0f} MA20:{r['ma20']:.0f} Vol:{r['vol']} Trend:{r['trend']}\n   E:{r['entry']:.0f} SL:{r['sl']:.0f} ({pct_sl:.1f}%) TP1:{r['tp1']:.0f} TP2:{r['tp2']:.0f} R:R 1:{r['rr']:.1f} | {r['max_lot']} lot\n\n"
    if not top:
        msg+=f"Tidak ada R:R >= {MIN_RR}. Pasar wait & see."
    print(msg)
    if BOT_TOKEN and CHAT_ID:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={"chat_id":CHAT_ID,"text":msg})
        print("DEBUG: Telegram terkirim")
    else:
        print("DEBUG: Token/Chat ID kosong")

if __name__ == "__main__":
    main()
