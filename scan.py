import yfinance as yf
import requests, os, time, json, numpy as np, random, urllib.parse
from datetime import datetime, date, timedelta
import pandas as pd

TOKEN = os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
MODAL = 5000000
HISTORY_FILE = "history_top.json"
TICKER_FILE = os.getenv("TICKER_FILE", "daytrade-observe-tickers.txt")
BATCH_LABEL = os.getenv("BATCH_LABEL", "SCAN")

try:
    from curl_cffi import requests as c_requests
    HAS_CURL = True
except:
    HAS_CURL = False
    c_requests = None

def rsi(s, p=14):
    d=s.diff(); g=d.where(d>0,0).rolling(p).mean(); l=-d.where(d<0,0).rolling(p).mean()
    rs=g/l; return 100-(100/(1+rs))

def load_tickers():
    for fname in [TICKER_FILE, "daytrade-observe-tickers.txt", "tickers-batch1.txt", "tickers-batch2.txt"]:
        try:
            with open(fname) as f:
                t=[x.strip() for x in f if x.strip() and not x.startswith("#")]
                if t:
                    t=[x.upper() if x.upper().endswith(".JK") else f"{x.upper()}.JK" for x in t]
                    t=list(dict.fromkeys(t))
                    print(f"{BATCH_LABEL} Load {len(t)} from {fname}")
                    return t
        except: pass
    return ["BBCA.JK","BBRI.JK","BMRI.JK"]

def load_history():
    try:
        with open(HISTORY_FILE) as f: return json.load(f)
    except: return {}
def save_history(h):
    with open(HISTORY_FILE,'w') as f: json.dump(h,f)

def fetch_yahoo_allorigins(ticker):
    # V6.5 senjata utama - lewat allorigins biar IP GitHub tidak terlihat Yahoo
    try:
        y_url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=3mo&interval=1d"
        proxy_url = f"https://api.allorigins.win/raw?url={urllib.parse.quote(y_url, safe='')}"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(proxy_url, headers=headers, timeout=15)
        if r.status_code!= 200: return None
        j = r.json()
        result = j['chart']['result'][0]
        timestamps = result['timestamp']
        ohlc = result['indicators']['quote'][0]
        adj = result['indicators'].get('adjclose',[{}])[0].get('adjclose') or ohlc['close']
        df = pd.DataFrame({'Open': ohlc['open'],'High': ohlc['high'],'Low': ohlc['low'],'Close': adj,'Volume': ohlc['volume']}, index=pd.to_datetime(timestamps, unit='s'))
        df = df.dropna()
        if len(df) >= 30:
            print(f"OK allorigins {ticker}")
            return df
    except Exception as e:
        print(f"allorigins fail {ticker}: {e}")
    return None

def fetch_via_yfinance(ticker):
    try:
        if HAS_CURL and c_requests:
            sess = c_requests.Session(impersonate="chrome120")
            df = yf.download(ticker, period="3mo", interval="1d", progress=False, auto_adjust=True, threads=False, session=sess)
        else:
            df = yf.download(ticker, period="3mo", interval="1d", progress=False, auto_adjust=True, threads=False)
        if len(df) >= 30: return df
    except: pass
    return None

def fetch_via_tradingview(ticker):
    # Source anti blokir total - TradingView scanner
    try:
        code = ticker.replace(".JK","")
        url = "https://scanner.tradingview.com/indonesia/scan"
        payload = {"symbols":{"tickers":[f"IDX:{code}"],"query":{"types":[]}},"columns":["close","open","high","low","volume","EMA20","RSI","ADX"]}
        headers = {"User-Agent":"Mozilla/5.0"}
        r = requests.post(url, json=payload, headers=headers, timeout=10)
        if r.status_code==200:
            # tradingview cuma kasih last price, kita butuh history jadi skip, tapi coba ambil history lain
            pass
        # History via tradingview chart
        hist_url = f"https://api.tradingview.com/history?symbol=IDX:{code}&resolution=D&from={int((datetime.now()-timedelta(days=100)).timestamp())}&to={int(datetime.now().timestamp())}"
        r2 = requests.get(hist_url, headers=headers, timeout=10)
        if r2.status_code==200:
            j=r2.json()
            if 'o' in j and len(j['o'])>=30:
                df=pd.DataFrame({'Open':j['o'],'High':j['h'],'Low':j['l'],'Close':j['c'],'Volume':j['v']}, index=pd.to_datetime(j['t'], unit='s'))
                if len(df)>=30: return df
    except: pass
    return None

def fetch_via_stooq_proxy(ticker):
    try:
        y_url = f"https://stooq.com/q/d/l/?s={ticker.lower()}&i=d"
        proxy_url = f"https://api.allorigins.win/raw?url={urllib.parse.quote(y_url, safe='')}"
        r = requests.get(proxy_url, timeout=10)
        if r.status_code!=200 or 'Date' not in r.text: return None
        from io import StringIO
        df = pd.read_csv(StringIO(r.text))
        if len(df)<30: return None
        df.columns=[c.capitalize() for c in df.columns]
        df['Date']=pd.to_datetime(df['Date']); df.set_index('Date', inplace=True); df.sort_index(inplace=True)
        if len(df)>=30: return df
    except: return None

def get_data(ticker):
    # Urutan baru V6.5: allorigins paling ampuh dulu
    df = fetch_yahoo_allorigins(ticker)
    if df is not None and len(df)>=30: return df, "yahoo_proxy"
    time.sleep(0.3)
    df = fetch_via_yfinance(ticker)
    if df is not None and len(df)>=30: return df, "yfinance"
    time.sleep(0.3)
    df = fetch_via_stooq_proxy(ticker)
    if df is not None and len(df)>=30: return df, "stooq_proxy"
    df = fetch_via_tradingview(ticker)
    if df is not None and len(df)>=30: return df, "tv"
    return None, "failed"

def scan_one(ticker):
    try:
        t=ticker.upper().strip()
        if not t.endswith(".JK"): t+=".JK"
        df, source = get_data(t)
        if df is None or len(df)<30: return None, source
        c=float(df['Close'].iloc[-1]); o=float(df['Open'].iloc[-1])
        if c < 50 or c > 10000: return None, source
        vol=float(df['Volume'].iloc[-1]); vol_avg=float(df['Volume'].rolling(20).mean().iloc[-1]) if len(df)>=20 else vol
        vol_r=vol/vol_avg if vol_avg>0 else 0
        ma20=float(df['Close'].rolling(20).mean().iloc[-1]) if len(df)>=20 else c
        ma50=float(df['Close'].rolling(50).mean().iloc[-1]) if len(df)>=50 else c
        ma20_5ago=float(df['Close'].rolling(20).mean().shift(5).iloc[-1]) if len(df)>=25 else ma20
        trend_ma20=(ma20/ma20_5ago-1)*100 if ma20_5ago else 0
        ema9=float(df['Close'].ewm(span=9).mean().iloc[-1]); ema21=float(df['Close'].ewm(span=21).mean().iloc[-1])
        try: rsi14=float(rsi(df['Close']).iloc[-1])
        except: rsi14=50
        ema12=df['Close'].ewm(span=12).mean(); ema26=df['Close'].ewm(span=26).mean()
        macd=ema12-ema26; signal=macd.ewm(span=9).mean()
        try: macd_bull = float(macd.iloc[-1]) > float(signal.iloc[-1])
        except: macd_bull=False
        tr=np.maximum(df['High']-df['Low'], np.maximum(abs(df['High']-df['Close'].shift(1)), abs(df['Low']-df['Close'].shift(1))))
        atr=float(tr.rolling(14).mean().iloc[-1]) if len(tr)>=14 else float(tr.mean())
        try:
            plus_dm=df['High'].diff(); minus_dm=-df['Low'].diff(); plus_dm[plus_dm<0]=0; minus_dm[minus_dm<0]=0; atr2=tr.rolling(14).mean()
            plus_di=100*(plus_dm.ewm(alpha=1/14).mean()/atr2); minus_di=100*(minus_dm.ewm(alpha=1/14).mean()/atr2)
            dx=100*abs(plus_di-minus_di)/(plus_di+minus_di); adx_val=float(dx.rolling(14).mean().iloc[-1])
        except: adx_val=15
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
        if score<25: return None, source
        if score>=85: bintang="⭐⭐⭐⭐⭐"; bintang_num=5; status="GOD MODE - ALL IN"
        elif score>=70: bintang="⭐⭐⭐⭐"; bintang_num=4; status="STRONG BREAKOUT - BUY"
        elif score>=55: bintang="⭐⭐⭐"; bintang_num=3; status="BREAKOUT - BUY TIPIS"
        elif score>=40: bintang="⭐⭐"; bintang_num=2; status="PULLBACK - CICIL"
        else: bintang="⭐"; bintang_num=1; status="PANTAU"
        sl=int(c-atr*1.8); sl_pct=(sl-c)/c*100; tp1=int(c+atr*1.8); tp2=int(c+atr*3.2)
        rr=(tp1-c)/(c-sl) if c!=sl else 0; entry_low=int(c*0.995); entry_high=int(c*1.005); lot=int(MODAL/c/100) if c>0 else 0
        notes=[f"src:{source}"]
        if vol_r>=1.2: notes.append(f"Vol {vol_r:.1f}x")
        if trend_ma20>1: notes.append(f"MA20 +{trend_ma20:.1f}%")
        if macd_bull: notes.append("MACD bull")
        return {"ticker":t.replace(".JK",""), "close":int(c), "ma20":int(ma20), "vol":vol_r, "trend":trend_ma20,"rsi":int(rsi14), "adx":int(adx_val), "macd_bull":macd_bull, "score":score,"bintang":bintang, "bintang_num":bintang_num, "status":status,"entry_low":entry_low, "entry_high":entry_high, "sl":sl, "sl_pct":round(sl_pct,1),"tp1":tp1, "tp2":tp2, "rr":round(rr,1), "lot":lot, "notes":", ".join(notes[:3]), "source":source}, source
    except: return None, "failed"

tickers=load_tickers(); history=load_history(); hasil=[]; stats={"yahoo_proxy":0,"yfinance":0,"stooq_proxy":0,"tv":0,"failed":0}
for i, tk in enumerate(tickers):
    h, src = scan_one(tk)
    if h: hasil.append(h); stats[src]=stats.get(src,0)+1
    else: stats[src]=stats.get(src,0)+1
    time.sleep(0.8 + random.uniform(0,0.7))
    if i % 15 == 0 and i>0: time.sleep(3)

hasil=sorted(hasil, key=lambda x: x['score'], reverse=True)
today_str = str(date.today()); history[today_str] = [h['ticker'] for h in hasil[:15]]
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
import pytz; now=datetime.now(pytz.timezone("Asia/Jakarta")).strftime('%d %b %H:%M WIB')
source_info = f"y_proxy:{stats.get('yahoo_proxy',0)} yf:{stats.get('yfinance',0)} st_proxy:{stats.get('stooq_proxy',0)} tv:{stats.get('tv',0)} fail:{stats.get('failed',0)} | curl:{'ON' if HAS_CURL else 'OFF'}"

if not layak_tampil:
    if hasil:
        fallback = sorted(hasil, key=lambda x: x['score'], reverse=True)[:5]
        pesan=f"🔥 {BATCH_LABEL} V6.5 5JT {now} | {len(tickers)} saham\n[{source_info}]\nTop Bintang 3-5: Pasar merah, tidak ada bintang 3-5. Lolos minimal: {len(hasil)}\nFallback Top 5:\n\n"
        for i,h in enumerate(fallback,1):
            pesan+=f"#{i} {h['ticker']}.JK {h['score']} - {h['status']} {h['bintang']} [{h['source']}]\n Harga:{h['close']} | Vol:{h['vol']:.1f}x | RSI:{h['rsi']} ADX:{h['adx']} | Lot {h['lot']}\n\n"
    else:
        pesan=f"🔥 {BATCH_LABEL} V6.5 5JT {now} | {len(tickers)} saham\n[{source_info}]\n\nQUAD SOURCE GAGAL SEMUA! Coba run ulang 10 menit lagi.\nTotal ter-scan: {len(tickers)} saham."
else:
    pesan=f"🔥 {BATCH_LABEL} V6.5 5JT {now} | {len(tickers)} saham\n[{source_info}]\nTop {len(top_tampil)} Bintang 3-5 layak pantau (lolos: {len(hasil)}):\n\n"
    for i,h in enumerate(top_tampil,1):
        streak = get_streak(h['ticker'])
        if streak>=3: action = f"🔥🔥🔥 {streak} HARI BERTURUT! SUPER TREND"
        elif streak==2: action = f"🔁 MUNCUL 2 HARI! Trend kuat"
        else: action="✅ Baru muncul, momentum awal - BUY" if h['bintang_num']==5 else "👀 Baru muncul, cicil"
        pesan+=f"#{i} {h['ticker']}.JK {h['score']} - {h['status']} {h['bintang']}\n Harga:{h['close']} | MA20:{h['ma20']} | Vol:{h['vol']:.1f}x | Trend:{h['trend']:+.1f}% | [{h['source']}] Lot {h['lot']}\n RSI:{h['rsi']} ADX:{h['adx']} MACD:{'BULL' if h['macd_bull'] else 'WAIT'}\n Entry:{h['entry_low']}-{h['entry_high']} | SL:{h['sl']} ({h['sl_pct']}%) | TP1:{h['tp1']} TP2:{h['tp2']}\n R:R 1:{h['rr']} | {h['notes']}\n {action}\n\n"

print(pesan)
if TOKEN and CHAT_ID:
    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", data={"chat_id":CHAT_ID,"text":pesan})
