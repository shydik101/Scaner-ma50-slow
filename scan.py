import warnings
warnings.filterwarnings("ignore")
import yfinance as yf, requests, time, json, os
from datetime import datetime
import numpy as np

yf.set_tz_cache_location("/tmp")

TOKEN = "8824185237:AAH2VLFwOkW-iSpxEQ3u0fIQ-4AS8DnYug0"
CHAT_ID = "7855961885"

print("Cek regime IHSG...")
ihsg = yf.download("^JKSE", period="6mo", interval="1d", progress=False, auto_adjust=True, threads=False)
ihsg_close = ihsg['Close'].iloc[-1].item()
ihsg_ma50 = ihsg['Close'].rolling(50).mean().iloc[-1].item()
ihsg_ma200 = ihsg['Close'].rolling(200).mean().iloc[-1].item()
is_bull_market = ihsg_close > ihsg_ma50 and ihsg_ma50 > ihsg_ma200
print(f"IHSG {int(ihsg_close)} MA50 {int(ihsg_ma50)} Bull={is_bull_market}")

url_list = "https://raw.githubusercontent.com/budikuatno2-ship-it/auto-cuan/main/data/daytrade-observe-tickers.txt"
r = requests.get(url_list, timeout=15)
tickers_raw = [x.strip().upper() for x in r.text.splitlines() if x.strip() and not x.startswith("#")]
TICKERS = [t if t.endswith(".JK") else t + ".JK" for t in tickers_raw]

hasil_A = [] # Grade A/A+
hasil_B = [] # Grade B (tengah)

def calc_rsi(s, p=14):
    d = s.diff(); g = (d.where(d > 0, 0)).rolling(p).mean(); l = (-d.where(d < 0, 0)).rolling(p).mean()
    return 100 - (100/(1+g/l))

def calc_mfi(h,l,c,v,p=14):
    tp = (h+l+c)/3; rmf = tp*v
    pos = rmf.where(tp>tp.shift(1),0).rolling(p).sum()
    neg = rmf.where(tp<tp.shift(1),0).rolling(p).sum()
    return 100 - (100/(1+pos/neg))

for i,t in enumerate(TICKERS):
    try:
        df = yf.download(t, period="1y", interval="1d", progress=False, auto_adjust=True, threads=False)
        if len(df) < 200: continue
        c=df['Close']; h=df['High']; l=df['Low']; v=df['Volume']
        close=c.iloc[-1].item()
        ma20=c.rolling(20).mean().iloc[-1].item()
        ma50=c.rolling(50).mean().iloc[-1].item()
        ma200=c.rolling(200).mean().iloc[-1].item()
        ma50_p10=c.rolling(50).mean().iloc[-11].item()
        ma50_p20=c.rolling(50).mean().iloc[-21].item()
        rsi=calc_rsi(c,14).iloc[-1].item()
        mfi=calc_mfi(h,l,c,v,14).iloc[-1].item()
        obv=(np.sign(c.diff())*v).fillna(0).cumsum()
        obv_ma20=obv.rolling(20).mean().iloc[-1]
        ema12=c.ewm(span=12, adjust=False).mean(); ema26=c.ewm(span=26, adjust=False).mean()
        macd_hist=(ema12-ema26 - (ema12-ema26).ewm(span=9, adjust=False).mean()).iloc[-1].item()
        tr=np.maximum(h-l, np.maximum(abs(h-c.shift(1)), abs(l-c.shift(1))))
        atr=tr.rolling(14).mean().iloc[-1].item()
        jarak=((close-ma50)/ma50)*100

        score=0; tags=[]

        # FILTER DASAR - SAMA KAYA VERSI SIMPLE KAMU
        if not (close > ma50 and ma50 > ma200 and ma20 > ma50): continue
        if not (-6 <= jarak <= 4): continue # lebih longgar dikit biar MDKA HRUM masuk

        # SKORING
        score+=20; tags.append("Uptrend")
        if ma50 > ma50_p10 and ma50_p10 > ma50_p20: score+=15; tags.append("MA50↑")
        else: score+=5
        score+=10; tags.append(f"MA50 {jarak:.1f}%")
        
        if 38 <= rsi <= 58: score+=15; tags.append(f"RSI{int(rsi)}")
        elif 33 <= rsi <= 63: score+=7
        else: continue

        if macd_hist > -2: score+=5
        if obv.iloc[-1] > obv_ma20: score+=10; tags.append("OBV Akum")
        if 40 <= mfi <= 66: score+=10; tags.append(f"MFI{int(mfi)}")
        
        df10=df.tail(10); up=df10[df10['Close']>df10['Open']]['Volume'].sum(); down=df10[df10['Close']<df10['Open']]['Volume'].sum()
        if up > down*1.2: score+=10; tags.append("Bandar Buy")
        elif up > down: score+=5
        
        body=h.iloc[-1].item()-l.iloc[-1].item()
        if body>0 and (close-l.iloc[-1].item())/body > 0.6: score+=5; tags.append("Reject")

        if not is_bull_market: score-=10 # potong cuma 10 di versi tengah, bukan 20

        # POSITION SIZING
        MODAL=100_000_000; RISIKO_PERSEN=1
        sl=int(close - atr*1.8)
        tp1=int(close + atr*2.5); tp2=int(close + atr*4.5)
        risiko=close-sl
        if risiko <=0: continue
        lot=int((MODAL*RISIKO_PERSEN/100)/(risiko*100)); lot=max(1,min(lot,50))

        # GRADE
        if score >= 85: grade="A+ (85%+)"; hasil_A.append({"ticker":t.replace('.JK',''),"close":int(close),"score":score,"grade":grade,"sl":sl,"tp1":tp1,"tp2":tp2,"lot":lot,"jarak":round(jarak,1),"rsi":int(rsi),"tags":tags})
        elif score >= 75: grade="A (80%)"; hasil_A.append({"ticker":t.replace('.JK',''),"close":int(close),"score":score,"grade":grade,"sl":sl,"tp1":tp1,"tp2":tp2,"lot":lot,"jarak":round(jarak,1),"rsi":int(rsi),"tags":tags})
        elif score >= 60: grade="B (70%)"; hasil_B.append({"ticker":t.replace('.JK',''),"close":int(close),"score":score,"grade":grade,"sl":sl,"tp1":tp1,"tp2":tp2,"lot":lot,"jarak":round(jarak,1),"rsi":int(rsi),"tags":tags})

        if i%100==0: print(f"{i}/{len(TICKERS)} A:{len(hasil_A)} B:{len(hasil_B)}")
        time.sleep(0.05)
    except: continue

hasil_A=sorted(hasil_A, key=lambda x: x['score'], reverse=True)
hasil_B=sorted(hasil_B, key=lambda x: x['score'], reverse=True)
now=datetime.now().strftime('%d %b %H:%M')

if not is_bull_market:
    pesan=f"⚠️ MARKET FILTER - {now} WIB\nIHSG {int(ihsg_close)} di BAWAH MA50 {int(ihsg_ma50)}\nMarket BEAR - Lot dikurangi 50%\n\n"
else:
    pesan=f"✅ SCAN TENGAH A+B - {now} WIB\nIHSG {int(ihsg_close)} Bull ✅\nFull {len(TICKERS)} saham\n\n"

if hasil_A:
    pesan+=f"💎 GRADE A/A+ (Lot Normal) - {len(hasil_A)} saham:\n"
    for h in hasil_A[:8]:
        pesan+=f"\n🔹 {h['ticker']} {h['close']} | {h['grade']} Score {h['score']}\n"
        pesan+=f"MA50 {h['jarak']}% RSI{h['rsi']} SL {h['sl']} TP1 {h['tp1']} TP2 {h['tp2']}\n"
        pesan+=f"Lot: {h['lot']} lot | {','.join(h['tags'])}\n"

if hasil_B:
    pesan+=f"\n🔸 GRADE B (Lot 50% -
