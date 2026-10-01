import requests, os, time, json, numpy as np, urllib.parse, random
from datetime import datetime, date
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import StringIO

TOKEN = os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
MODAL = 5000000
HISTORY_FILE = "history_top.json"
TICKER_FILE = os.getenv("TICKER_FILE", "daytrade-observe-tickers.txt")
BATCH_LABEL = os.getenv("BATCH_LABEL", "SCAN")

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
                    return list(dict.fromkeys(t))
        except: pass
    return ["BBCA.JK"]

def load_history():
    try:
        with open(HISTORY_FILE) as f: return json.load(f)
    except: return {}
def save_history(h):
    with open(HISTORY_FILE,'w') as f: json.dump(h,f)

# === V8.4 MULTI-PROXY ROTATOR ===
PROXIES = [
    "https://api.allorigins.win/raw?url={}",
    "https://corsproxy.io/?{}",
    "https://api.codetabs.com/v1/proxy?quest={}",
]

def fetch_yahoo_rotator(ticker):
    y_url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=3mo&interval=1d"
    enc_url = urllib.parse.quote(y_url, safe='')

    for proxy_template in random.sample(PROXIES, len(PROXIES)): # acak urutan proxy
        try:
            proxy_url = proxy_template.format(enc_url)
            r = requests.get(proxy_url, timeout=15)
            if r.status_code!=200:
                time.sleep(0.5)
                continue
            # allorigins return raw json, corsproxy return json, codetabs return json
            txt = r.text
            if '"chart"' not in txt:
                continue
            j=r.json()
            if 'chart' not in j or j['chart']['result'] is None:
                continue
            result=j['chart']['result'][0]
            timestamps=result['timestamp']
            ohlc=result['indicators']['quote'][0]
            adj=result['indicators'].get('adjclose',[{}])[0].get('adjclose') or ohlc['close']
            df=pd.DataFrame({'Open': ohlc['open'],'High': ohlc['high'],'Low': ohlc['low'],'Close': adj,'Volume': ohlc['volume']}, index=pd.to_datetime(timestamps, unit='s'))
            df=df.dropna()
            if len(df)>=30:
                return df, proxy_template.split('/')[2] # return domain proxy yg berhasil
        except:
            time.sleep(0.5)
            continue
    return None, "failed"

def fetch_stooq(ticker):
    try:
        url = f"https://stooq.com/q/d/l/?s={ticker.lower()}&i=d"
        r = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=10)
        if r.status_code!=200 or 'Date' not in r.text: return None
        df = pd.read_csv(StringIO(r.text))
        if len(df)<30: return None
        df.columns=[c.capitalize() for c in df.columns]
        df['Date']=pd.to_datetime(df['Date']); df.set_index('Date', inplace=True); df.sort_index(inplace=True)
        return df
    except: return None

def get_data(ticker):
    df, src = fetch_yahoo_rotator(ticker)
    if df is not None: return df, src
    df = fetch_stooq(ticker)
    if df is not None: return df, "stooq"
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
        if score<20: return None, source
        if score>=85: bintang="⭐⭐⭐⭐⭐"; bintang_num=5; status="GOD MODE - ALL IN"
        elif score>=70: bintang="⭐⭐⭐⭐"; bintang_num=4; status="STRONG BREAKOUT - BUY"
        elif score>=55: bintang="⭐⭐⭐"; bintang_num=3; status="BREAKOUT - BUY TIPIS"
        elif score>=40: bintang="⭐⭐"; bintang_num=2; status="PULLBACK - CICIL"
        else: bintang="⭐"; bintang_num=1; status="PANTAU"
        sl=int(c-atr*1.8); sl_pct=(sl-c)/c*100; tp1=int(c+atr*1.8); tp2=int(c+atr*3.2)
        rr=(tp1-c)/(c-sl) if c!=sl else 0; entry_low=int(c*0.995); entry_high=int(c*1.005); lot=int(MODAL/c/100) if c>0 else 0
        return {"ticker":t.replace(".JK",""), "close":int(c), "ma20":int(ma20), "vol":vol_r, "trend":trend_ma20,"rsi":int(rsi14), "adx":int(adx_val), "macd_bull":macd_bull, "score":score,"bintang":bintang, "bintang_num":bintang_num, "status":status,"entry_low":entry_low, "entry_high":entry_high, "sl":sl, "sl_pct":round(sl_pct,1),"tp1":tp1, "tp2":tp2, "rr":round(rr,1), "lot":lot, "notes":f"src:{source}", "source":source}, source
    except: return None, "failed"

tickers=load_tickers(); history=load_history(); hasil=[]; stats={}
print(f"V8.4 ROTATOR START {len(tickers)}")

with ThreadPoolExecutor(max_workers=2) as executor: # 2 aja biar gak kena limit
    futures = {executor.submit(scan_one, tk): tk for tk in tickers}
    for future in as_completed(futures):
        h, src = future.result()
        if h: hasil.append(h)
        stats[src]=stats.get(src,0)+1
        time.sleep(0.4)

hasil=sorted(hasil, key=lambda x: x['score'], reverse=True)
today_str = str(date.today()); history[today_str] = [h['ticker'] for h in hasil[:15]]
if len(history)>7:
    for k in sorted(history.keys())[:-7]: del history[k]
save_history(history)
def get_streak(t):
    s=0
    for d in sorted(history.keys(), reverse=True):
        if t in history.get(d, []): s+=1
        else: break
    return s

layak_tampil = [h for h in hasil if h['bintang_num'] >= 3]
top_tampil = layak_tampil[:10]
import pytz; now=datetime.now(pytz.timezone("Asia/Jakarta")).strftime('%d %b %H:%M WIB')
source_info = " ".join([f"{k}:{v}" for k,v in stats.items()])

if not layak_tampil:
    fb = sorted(hasil, key=lambda x: x['score'], reverse=True)[:5]
    pesan=f"🔥 {BATCH_LABEL} V8.4 5JT {now} | {len(tickers)} saham\n[{source_info}]\nFallback Top 5:\n\n"
    for i,h in enumerate(fb,1):
        pesan+=f"#{i} {h['ticker']}.JK {h['score']} {h['status']} {h['bintang']} [{h['source']}]\n Harga:{h['close']} Vol:{h['vol']:.1f}x RSI:{h['rsi']} Lot {h['lot']}\n\n"
else:
    pesan=f"🔥 {BATCH_LABEL} V8.4 5JT {now} | {len(tickers)} saham\n[{source_info}]\nTop {len(top_tampil)} Bintang 3-5 (lolos {
