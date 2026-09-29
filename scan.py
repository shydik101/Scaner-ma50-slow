import yfinance as yf
import requests, os, time, json, numpy as np, random
from datetime import datetime, date

TOKEN = os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
MODAL = 1500000
HISTORY_FILE = "history_top.json"

def rsi(s, p=14):
    d=s.diff(); g=d.where(d>0,0).rolling(p).mean(); l=-d.where(d<0,0).rolling(p).mean()
    rs=g/l; return 100-(100/(1+rs))

def load_tickers():
    try:
        with open("daytrade-observe-tickers.txt") as f:
            t=[x.strip() for x in f if x.strip() and not x.startswith("#")]
            if t: return t
    except: pass
    return ["BBCA.JK","BBRI.JK","BMRI.JK","BBNI.JK","TLKM.JK","ASII.JK","UNTR.JK","CUAN.JK","GOTO.JK","BREN.JK","BRPT.JK"]

def load_history():
    try:
        with open(HISTORY_FILE) as f: return json.load(f)
    except: return {}
def save_history(h):
    with open(HISTORY_FILE,'w') as f: json.dump(h,f)

def get_data(ticker):
    """V6.2 ANTI-BLOCK: retry 3x dengan 2 method"""
    for attempt in range(3):
        try:
            df = yf.download(ticker, period="3mo", interval="1d", progress=False, auto_adjust=True, threads=False)
            if len(df) >= 30:
                return df
        except: pass
        try:
            time.sleep(1 + attempt)
            tk = yf.Ticker(ticker)
            df2 = tk.history(period="3mo", interval="1d", auto_adjust=True)
            if len(df2) >= 30:
                return df2
        except: pass
        time.sleep(2 + attempt*2 + random.uniform(0,1))
    return None

def scan_one(ticker):
    try:
        t=ticker.upper().strip()
        if not t.endswith(".JK"): t+=".JK"
        df = get_data(t)
        if df is None or len(df)<30:
            return None
        c=float(df['Close'].iloc[-1]); o=float(df['Open'].iloc[-1])
        vol=float(df['Volume'].iloc[-1])
        vol_avg=float(df['Volume'].rolling(20).mean().iloc[-1]) if len(df)>=20 else vol
        vol_r=vol/vol_avg if vol_avg>0 else 0
        ma20=float(df['Close'].rolling(20).mean().iloc[-1]) if len(df)>=20 else c
        ma50=float(df['Close'].rolling(50).mean().iloc[-1]) if len(df)>=50 else c
        ma20_5ago=float(df['Close'].rolling(20).mean().shift(5).iloc[-1]) if len(df)>=25 else ma20
        trend_ma20=(ma20/ma20_5ago-1)*100 if ma20_5ago else 0
        ema9=float(df['Close'].ewm(span=9).mean().iloc[-1]); ema21=float(df['Close'].ewm(span=21).mean().iloc[-1])
        rsi14=float(rsi(df['Close']).iloc[-1]) if len(df)>=15 else 50
        ema12=df['Close'].ewm(span=12).mean(); ema26=df['Close'].ewm(span=26).mean()
        macd=ema12-ema26; signal=macd.ewm(span=9).mean()
        macd_bull = float(macd.iloc[-1]) > float(signal.iloc[-1])
        tr=np.maximum(df['High']-df['Low'], np.maximum(abs(df['High']-df['Close'].shift(1)), abs(df['Low']-df['Close'].shift(1))))
        atr=float(tr.rolling(14).mean().iloc[-1]) if len(tr)>=14 else float(tr.mean())
        plus_dm=df['High'].diff(); minus_dm=-df['Low'].diff()
        plus_dm[plus_dm<0]=0; minus_dm[minus_dm<0]=0
        atr2=tr.rolling(14).mean()
        try:
            plus_di=100*(plus_dm.ewm(alpha=1/14).mean()/atr2); minus_di=100*(minus_dm.ewm(alpha=1/14).mean()/atr2)
            dx=100*abs(plus_di-minus_di)/(plus_di+minus_di)
            adx_val=float(dx.rolling(14).mean().iloc[-1])
        except:
            adx_val=15

        score=0
        if ema9>ema21: score+=15
        if c>ma20: score+=10
        if ma20>ma50: score+=10
        if vol_r>=1.2: score+=20
        if vol_r>=1.5: score+=5
        if 35<=rsi14<=80: score+=15
        if macd_bull: score+=10
        if adx_val>=12: score+=10
        if c>o: score+=10
        if rsi14>88: score-=15
        if adx_val<10: score-=10
        if score<25: return None

        if score>=85:
            bintang="⭐⭐⭐⭐⭐"; bintang_num=5; status="GOD MODE - ALL IN"
        elif score>=70:
            bintang="⭐⭐⭐⭐"; bintang_num=4; status="STRONG BREAKOUT - BUY"
        elif score>=55:
            bintang="⭐⭐⭐"; bintang_num=3; status="BREAKOUT - BUY TIPIS"
        elif score>=40:
            bintang="⭐⭐"; bintang_num=2; status="PULLBACK - CICIL"
        else:
            bintang="⭐"; bintang_num=1; status="PANTAU"

        sl=int(c-atr*1.8); sl_pct=(sl-c)/c*100
        tp1=int(c+atr*1.8); tp2=int(c+atr*3.2)
        rr=(tp1-c)/(c-sl) if c!=sl else 0
        entry_low=int(c*0.995); entry_high=int(c*1.005)
        lot=int(MODAL/c/100) if c>0 else 0
        notes=[]
        if vol_r>=1.2: notes.append(f"Vol valid {vol_r:.1f}x")
        if trend_ma20>1: notes.append(f"MA20 +{trend_ma20:.1f}%")
        if macd_bull: notes.append("MACD bull")

        return {"ticker":t.replace(".JK",""), "close":int(c), "ma20":int(ma20), "vol":vol_r, "trend":trend_ma20,
                "rsi":int(rsi14), "adx":int(adx_val), "macd_bull":macd_bull, "score":score,
                "bintang":bintang, "bintang_num":bintang_num, "status":status,
                "entry_low":entry_low, "entry_high":entry_high, "sl":sl, "sl_pct":round(sl_pct,1),
                "tp1":tp1, "tp2":tp2, "rr":round(rr,1), "lot":lot, "notes":", ".join(notes[:3]) if notes else "pantau"}
    except:
        return None

tickers=load_tickers()
history=load_history()
hasil=[]
failed=0
for i, tk in enumerate(tickers):
    h=scan_one(tk)
    if h: hasil.append(h)
    else: failed+=1
    time.sleep(0.8 + random.uniform(0,0.5))
    if i % 10 == 0 and i>0:
        time.sleep(3)

hasil=sorted(hasil, key=lambda x: x['score'], reverse=True)
today_str = str(date.today())
history[today_str] = [h['ticker'] for h in hasil[:15]]
if len(history)>7:
    for k in sorted(history.keys())[:-7]: del history[k]
save_history(history)

def get_streak(ticker):
    streak=0
    for d in sorted(history.keys(), reverse=True):
        if ticker in history.get(d, []): streak+=1
        else: break
    return streak

layak_tampil = [h for h in hasil if h['bintang_num'] >= 3]
top_tampil = layak_tampil[:10] if len(layak_tampil) > 10 else layak_tampil
now=datetime.now().strftime('%d %b %H:%M')

if not layak_tampil:
    if hasil:
        fallback = sorted(hasil, key=lambda x: x['score'], reverse=True)[:5]
        pesan=f"🔥 SCAN SULTAN LITE {now} | {len(tickers)} saham\nTop Bintang 3-5: Pasar merah, tidak ada bintang 3-5 hari ini.\nDari {len(tickers)} saham, lolos minimal: {len(hasil)} saham. Gagal download: {failed}\nFallback Top 5 bintang 1-2:\n\n"
        for i,h in enumerate(fallback,1):
            pesan+=f"#{i} {h['ticker']}.JK {h['score']} - {h['status']} {h['bintang']}\n Harga:{h['close']} | MA20:{h['ma20']} | Vol:{h['vol']:.1f}x | RSI:{h['rsi']} ADX:{h['adx']}\n\n"
    else:
        pesan=f"🔥 SCAN SULTAN LITE {now} | {len(tickers)} saham\nTop Bintang 3-5:\n\nYahoo Finance lagi limit / market libur. Dari {len(tickers)} ticker tidak ada data yang ke-download (gagal: {failed}). Coba run ulang 10 menit lagi.\nTotal ter-scan: {len(tickers)} saham. V6.2 sudah pakai retry 3x."
else:
    pesan=f"🔥 SCAN SULTAN LITE {now} | {len(tickers)} saham\nTop {len(top_tampil)} Bintang 3-5 layak pantau (lolos: {len(hasil)}, gagal: {failed}):\n\n"
    for i,h in enumerate(top_tampil,1):
        streak = get_streak(h['ticker'])
        if streak>=3: action = f"🔥🔥🔥 {streak} HARI BERTURUT! SUPER TREND - WAJIB HOLD"
        elif streak==2: action = f"🔁 MUNCUL 2 HARI! Trend kuat, HOLD / tambah"
        else:
            if h['bintang_num']==5: action="✅ Baru muncul, momentum awal - BUY"
            else: action="👀 Baru muncul, cicil / pantau breakout"
        pesan+=f"#{i} {h['ticker']}.JK {h['score']} - {h['status']} {h['bintang']}\n"
        pesan+=f" Harga:{h['close']} | MA20:{h['ma20']} | Vol:{h['vol']:.1f}x VALID | Trend MA20:{h['trend']:+.1f}%/5hr\n"
        pesan+=f" RSI:{h['rsi']} | ADX:{h['adx']} | MACD:{'BULL' if h['macd_bull'] else 'WAIT'}\n"
        pesan+=f" Entry:{h['entry_low']}-{h['entry_high']} | SL:{h['sl']} ({h['sl_pct']}%) | TP1:{h['tp1']} TP2:{h['tp2']}\n"
        pesan+=f" R:R 1:{h['rr']} | Money: max Rp 1.5jt (~{h['lot']} lot)\n"
        pesan+=f" Note: {h['notes']}\n {action}\n\n"

print(pesan)
if TOKEN and CHAT_ID:
    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", data={"chat_id":CHAT_ID,"text":pesan})
