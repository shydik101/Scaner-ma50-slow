import warnings
warnings.filterwarnings("ignore")
import yfinance as yf
import requests, json
from datetime import datetime
import numpy as np
yf.set_tz_cache_location("/tmp")

import os
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

ihsg = yf.download("^JKSE", period="6mo", interval="1d", progress=False, auto_adjust=True, threads=False)
ihsg_close = ihsg['Close'].iloc[-1].item()
ihsg_ma50 = ihsg['Close'].rolling(50).mean().iloc[-1].item()
ihsg_ma200 = ihsg['Close'].rolling(200).mean().iloc[-1].item()
is_bull = ihsg_close > ihsg_ma50 and ihsg_ma50 > ihsg_ma200

url_list = "https://raw.githubusercontent.com/budikuatno2-ship-it/auto-cuan/main/data/daytrade-observe-tickers.txt"
r = requests.get(url_list, timeout=15)
raw = [x.strip().upper() for x in r.text.splitlines() if x.strip() and not x.startswith("#")]
TICKERS = [t if t.endswith(".JK") else t + ".JK" for t in raw]

hasil_A = []
hasil_B = []
hasil_C = []

def calc_rsi(s,p=14):
    d=s.diff()
    g=(d.where(d>0,0)).rolling(p).mean()
    l=(-d.where(d<0,0)).rolling(p).mean()
    return 100-(100/(1+g/l))

def calc_mfi(h,l,c,v,p=14):
    tp=(h+l+c)/3
    rmf=tp*v
    pos=rmf.where(tp>tp.shift(1),0).rolling(p).sum()
    neg=rmf.where(tp<tp.shift(1),0).rolling(p).sum()
    return 100-(100/(1+pos/neg))

for t in TICKERS:
    try:
        df = yf.download(t, period="1y", interval="1d", progress=False, auto_adjust=True, threads=False)
        if len(df) < 200:
            continue
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
        ema12=c.ewm(span=12, adjust=False).mean()
        ema26=c.ewm(span=26, adjust=False).mean()
        macd_hist=(ema12-ema26 - (ema12-ema26).ewm(span=9, adjust=False).mean()).iloc[-1].item()
        tr=np.maximum(h-l, np.maximum(abs(h-c.shift(1)), abs(l-c.shift(1))))
        atr=tr.rolling(14).mean().iloc[-1].item()
        jarak=((close-ma50)/ma50)*100
        score=0; tags=[]
        if not (close > ma50 and ma50 > ma200 and ma20 > ma50):
            continue
        if not (-6 <= jarak <= 4):
            continue
        score+=20; tags.append("Uptrend")
        if ma50 > ma50_p10 and ma50_p10 > ma50_p20:
            score+=15; tags.append("MA50 Naik")
        else:
            score+=5
        score+=10; tags.append(f"MA50 {jarak:.1f}%")
        if 38 <= rsi <= 58:
            score+=15; tags.append(f"RSI{int(rsi)}")
        elif 33 <= rsi <= 63:
            score+=7; tags.append(f"RSI{int(rsi)}")
        else:
            continue
        if macd_hist > -2:
            score+=5
        if obv.iloc[-1] > obv_ma20:
            score+=10; tags.append("OBV Akum")
        if 40 <= mfi <= 66:
            score+=10; tags.append(f"MFI{int(mfi)}")
        df10=df.tail(10)
        up=df10[df10['Close']>df10['Open']]['Volume'].sum()
        down=df10[df10['Close']<df10['Open']]['Volume'].sum()
        if up > down*1.2:
            score+=10; tags.append("Bandar Buy")
        elif up > down:
            score+=5
        body=h.iloc[-1].item()-l.iloc[-1].item()
        if body>0 and (close-l.iloc[-1].item())/body > 0.6:
            score+=5; tags.append("Reject")
        if not is_bull:
            score-=5
        sl=int(close - atr*1.8)
        tp1=int(close + atr*2.5)
        tp2=int(close + atr*4.5)
        risiko=close-sl
        if risiko <=0:
            continue
        lot=int((100_000_000*0.01)/(risiko*100))
        lot=max(1,min(lot,50))
        item={"ticker":t.replace('.JK',''),"close":int(close),"score":score,"sl":sl,"tp1":tp1,"tp2":tp2,"lot":lot,"jarak":round(jarak,1),"rsi":int(rsi),"tags":tags}
        if score >= 75:
            item["grade"]="A"; hasil_A.append(item)
        elif score >= 60:
            item["grade"]="B"; hasil_B.append(item)
        elif score >= 55:
            item["grade"]="C+"; hasil_C.append(item)
    except:
        continue

hasil_A=sorted(hasil_A, key=lambda x: x['score'], reverse=True)
hasil_B=sorted(hasil_B, key=lambda x: x['score'], reverse=True)
hasil_C=sorted(hasil_C, key=lambda x: x['score'], reverse=True)

now=datetime.now().strftime('%d %b %H:%M')
if not is_bull:
    pesan=f"MARKET FILTER - {now}\nIHSG {int(ihsg_close)} BEAR di bawah MA50 {int(ihsg_ma50)}\nSkor 55+ ditampilkan\n\n"
else:
    pesan=f"SCAN 55+ TAMPIL SKOR - {now}\nIHSG {int(ihsg_close)} Bull\nFull {len(TICKERS)} saham\n\n"

total=len(hasil_A)+len(hasil_B)+len(hasil_C)
pesan+=f"Total lolos skor 55+ : {total} saham\n"

if hasil_A:
    pesan+=f"\nGRADE A 75+ (Lot Normal) - {len(hasil_A)} saham:\n"
    for h in hasil_A[:8]:
        pesan+=f"\n{h['ticker']} {h['close']} | Skor {h['score']} {h['grade']}\n"
        pesan+=f"MA50 {h['jarak']}% RSI{h['rsi']} SL {h['sl']} TP {h['tp1']}\n"
        pesan+=f"Lot {h['lot']} | {','.join(h['tags'])}\n"

if hasil_B:
    pesan+=f"\nGRADE B 60-74 (Lot 50%) - {len(hasil_B)} saham:\n"
    for h in hasil_B[:8]:
        pesan+=f"\n{h['ticker']} {h['close']} | Skor {h['score']} {h['grade']}\n"
        pesan+=f"MA50 {h['jarak']}% RSI{h['rsi']} SL {h['sl']} TP {h['tp1']}\n"
        pesan+=f"Lot {max(1,h['lot']//2)} kecil | {','.join(h['tags'])}\n"

if hasil_C:
    pesan+=f"\nGRADE C+ 55-59 (Watchlist) - {len(hasil_C)} saham:\n"
    for h in hasil_C[:10]:
        pesan+=f"\n{h['ticker']} {h['close']} | Skor {h['score']} {h['grade']}\n"
        pesan+=f"MA50 {h['jarak']}% RSI{h['rsi']} | {','.join(h['tags'])}\n"

if total==0:
    pesan+=f"\nTidak ada skor 55+ hari ini. HOLD CASH.\n"

with open("portfolio.json","w") as f:
    json.dump(hasil_A+hasil_B+hasil_C, f, indent=2)

print(pesan)
requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", data={"chat_id": CHAT_ID, "text": pesan})
