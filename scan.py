import warnings
warnings.filterwarnings("ignore")
import yfinance as yf, requests, time, json, os
yf.set_tz_cache_location("/tmp")
from datetime import datetime
import numpy as np

TOKEN = "8824185237:AAH2VLFwOkW-iSpxEQ3u0fIQ-4AS8DnYug0"
CHAT_ID = "7855961885"

# 1. CEK REGIME IHSG DULU - JANGAN LAWAN MARKET
print("Cek regime IHSG...")
ihsg = yf.download("^JKSE", period="6mo", interval="1d", progress=False, auto_adjust=True)
ihsg_close = ihsg['Close'].iloc[-1].item()
ihsg_ma50 = ihsg['Close'].rolling(50).mean().iloc[-1].item()
ihsg_ma200 = ihsg['Close'].rolling(200).mean().iloc[-1].item()
is_bull_market = ihsg_close > ihsg_ma50 and ihsg_ma50 > ihsg_ma200
print(f"IHSG {int(ihsg_close)} MA50 {int(ihsg_ma50)} Bull={is_bull_market}")

# List sektor yang lagi uptrend (proxy: cek ETF sektor / komposit)
# Kita sederhanakan: cek momentum 20 hari
SECTOR_MAP = {
    "FINANCE": ["BBCA.JK","BBRI.JK","BMRI.JK","BBNI.JK","BRIS.JK"],
    "ENERGY": ["ADRO.JK","PTBA.JK","ITMG.JK","MEDC.JK","PGAS.JK"],
    "MINING": ["ANTM.JK","MDKA.JK","INCO.JK","NCKL.JK","HRUM.JK"],
    "TECH": ["GOTO.JK","BUKA.JK","EMTK.JK","SCMA.JK"],
}

url_list = "https://raw.githubusercontent.com/budikuatno2-ship-it/auto-cuan/main/data/daytrade-observe-tickers.txt"
r = requests.get(url_list, timeout=15)
tickers_raw = [x.strip().upper() for x in r.text.splitlines() if x.strip() and not x.startswith("#")]
TICKERS = [t if t.endswith(".JK") else t + ".JK" for t in tickers_raw]

hasil = []

def calc_rsi(s, p=14):
    d = s.diff()
    g = (d.where(d > 0, 0)).rolling(p).mean()
    l = (-d.where(d < 0, 0)).rolling(p).mean()
    rs = g/l
    return 100 - (100/(1+rs))

def calc_mfi(h,l,c,v,p=14):
    tp = (h+l+c)/3
    rmf = tp*v
    pos = rmf.where(tp>tp.shift(1),0).rolling(p).sum()
    neg = rmf.where(tp<tp.shift(1),0).rolling(p).sum()
    return 100 - (100/(1+pos/neg))

for i,t in enumerate(TICKERS):
    try:
        df = yf.download(t, period="1y", interval="1d", progress=False, auto_adjust=True, threads=False)
        if len(df) < 200: continue
        c = df['Close']
        h = df['High']; l = df['Low']; o = df['Open']; v = df['Volume']
        close = c.iloc[-1].item()
        ma20 = c.rolling(20).mean().iloc[-1].item()
        ma50 = c.rolling(50).mean().iloc[-1].item()
        ma200 = c.rolling(200).mean().iloc[-1].item()
        ma50_p10 = c.rolling(50).mean().iloc[-11].item()
        ma50_p20 = c.rolling(50).mean().iloc[-21].item()
        
        rsi = calc_rsi(c,14).iloc[-1].item()
        mfi = calc_mfi(h,l,c,v,14).iloc[-1].item()
        vol_avg20 = v.rolling(20).mean().iloc[-1].item()
        obv = (np.sign(c.diff())*v).fillna(0).cumsum()
        obv_ma20 = obv.rolling(20).mean().iloc[-1]
        
        ema12 = c.ewm(span=12).mean(); ema26 = c.ewm(span=26).mean()
        macd_hist = (ema12-ema26 - (ema12-ema26).ewm(span=9).mean()).iloc[-1].item()
        tr = np.maximum(h-l, np.maximum(abs(h-c.shift(1)), abs(l-c.shift(1))))
        atr = tr.rolling(14).mean().iloc[-1].item()
        jarak = ((close-ma50)/ma50)*100

        score = 0; tags = []; grade = "C"

        # FILTER WAJIB
        if not (close > ma50 and ma50 > ma200 and ma20 > ma50): continue
        if not (-5 <= jarak <= 2.5): continue
        if not is_bull_market: # kalau IHSG bear, skor dikurangi 20
            score -= 20

        # SKORING 100
        score += 20; tags.append("Uptrend")
        if ma50 > ma50_p10 and ma50_p10 > ma50_p20: score+=15; tags.append("MA50↑")
        score+=15; tags.append(f"MA50 {jarak:.1f}%")
        if 38 <= rsi <= 58: score+=10; tags.append(f"RSI{int(rsi)}")
        if macd_hist > -2: score+=5
        if obv.iloc[-1] > obv_ma20: score+=10; tags.append("OBV Akum")
        if 40 <= mfi <= 65: score+=10; tags.append(f"MFI{int(mfi)}")
        df10 = df.tail(10); up = df10[df10['Close']>df10['Open']]['Volume'].sum(); down = df10[df10['Close']<df10['Open']]['Volume'].sum()
        if up > down*1.2: score+=10; tags.append("Bandar Buy")
        body = h.iloc[-1].item()-l.iloc[-1].item()
        if body>0 and (close-l.iloc[-1].item())/body > 0.6: score+=5; tags.append("Reject")

        # GRADE SYSTEM
        if score >= 85: grade="A+ (85%+)"
        elif score >= 75: grade="A (80%)"
        elif score >= 65: grade="B (70%)"
        else: continue

        # POSITION SIZING: Modal 100jt, risiko 1% per trade
        MODAL = 100_000_000
        RISIKO_PERSEN = 1
        sl = int(close - atr*1.8)
        tp1 = int(close + atr*2.5); tp2 = int(close + atr*4.5)
        risiko_per_saham = close - sl
        if risiko_per_saham <=0: continue
        lot = int((MODAL * RISIKO_PERSEN/100) / (risiko_per_saham * 100)) # 1 lot = 100 lembar
        lot = max(1, min(lot, 50)) # batasi 1-50 lot

        hasil.append({"ticker":t.replace('.JK',''),"close":int(close),"score":score,"grade":grade,"jarak":round(jarak,1),"rsi":int(rsi),"sl":sl,"tp1":tp1,"tp2":tp2,"lot":lot,"tags":tags})

        if i%100==0: print(f"{i}/{len(TICKERS)} lolos {len(hasil)}")
        time.sleep(0.1)
    except: continue

hasil = sorted(hasil, key=lambda x: x['score'], reverse=True)
now = datetime.now().strftime('%d %b %H:%M')

if not is_bull_market:
    pesan = f"⚠️ MARKET FILTER - {now} WIB\nIHSG {int(ihsg_close)} di BAWAH MA50 {int(ihsg_ma50)}\nMarket lagi BEAR, scan tetap jalan tapi HATI-HATI, kurangi lot 50%!\n\n"
else:
    pesan = f"✅ ULTIMATE SCAN GRADE A+ - {now} WIB\nIHSG {int(ihsg_close)} Bull Market ✅\nFull {len(TICKERS)} saham, lolos {len(hasil)}:\n"

if hasil:
    for h in hasil[:10]: # top 10 aja biar tidak spam
        pesan += f"\n🔹 {h['ticker']} {h['close']} | {h['grade']} Score {h['score']}\n"
        pesan += f"Jarak {h['jarak']}% RSI{h['rsi']} SL {h['sl']} TP1 {h['tp1']} TP2 {h['tp2']}\n"
        pesan += f"Lot: {h['lot']} lot (Modal 100jt Risiko 1%)\n"
        pesan += f"{','.join(h['tags'])}\n"

    pesan += f"\nMoney Management: Jangan lebih dari 3 saham Grade A+ bersamaan. TP1 jual 50%, geser SL ke modal."
    
    # SIMPAN KE FILE portfolio.json buat tracking TP/SL besok
    with open("portfolio.json","w") as f:
        json.dump(hasil[:10], f, indent=2)
    
else:
    pesan += f"\nTidak ada Grade A/B hari ini. HOLD CASH adalah posisi terbaik."

print(pesan)
requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", data={"chat_id": CHAT_ID, "text": pesan})
