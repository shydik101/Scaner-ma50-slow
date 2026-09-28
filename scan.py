import yfinance as yf, os, requests, pandas as pd
from datetime import datetime

TICKER_FILE = "daytrade-observe-tickers.txt" if os.path.exists("daytrade-observe-tickers.txt") else "data/daytrade-observe-tickers.txt"
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
MIN_RR = 1.4
PORTO = 100_000_000
RISK_PER_TRADE = 0.015

SEKTOR = {
    "NIKEL": ["MDKA","ANTM","INCO","NCKL","MBMA","HRUM","ADMR"],
    "ENERGY": ["ADRO","PTBA","ITMG","PTRO","RAJA","MEDC","ELSA","AKRA","PGAS","PGEO","BREN","DEWA"],
    "BANK": ["BBCA","BBRI","BMRI","BBNI","BBTN","BRIS","ARTO","BBYB"],
    "TECH": ["GOTO","BUKA","EMTK","SCMA","DCII"],
}

def last_float(s):
    s = s.dropna()
    if s.empty: return 0.0
    v = s.iloc[-1]
    if isinstance(v, pd.Series): v = v.iloc[0]
    try:
        if hasattr(v, 'item'): v = v.item()
        return float(v)
    except: return 0.0

def get_tickers():
    with open(TICKER_FILE) as f:
        raw = [x.strip().upper() for x in f if x.strip() and not x.startswith('#')]
    return list(dict.fromkeys([t if t.endswith(".JK") else t+".JK" for t in raw]))

def get_note(r):
    c,m,v_ratio,trend_score,days_up = r['c'], r['m'], r['v_ratio'], r['slope'], r['days_up']
    notes=[]
    if v_ratio >= 1.5: notes.append("Volume valid")
    elif v_ratio < 1.0: notes.append("volume tipis - rawan false breakout")

    if trend_score > 2.5: notes.append("MA20 nanjak tajam")
    elif trend_score > 1.0: notes.append("MA20 nanjak")

    if r['close_near_high'] > 0.98: notes.append("close dekat high 20hr")

    if days_up >= 4: notes.append(f"sudah naik {days_up} hari")

    if v_ratio < 1.0 and days_up >=3:
        return f"Skor oke tapi sudah naik {days_up} hari, volume tipis - rawan false breakout. SKIP dulu."
    if r['c'] > r['tp1']*1.02:
        return f"Boleh ambil, tapi jangan kejar di atas {r['tp1']*1.02:.0f}"
    if r['rr'] < 1.4:
        return f"Tunggu koreksi ke {r['m']:.0f}, jangan FOMO di pucuk"
    if "Volume valid" in str(notes):
        return f"{', '.join(notes)}"
    return "Sektor kompak naik hari ini" if v_ratio>1.5 else "Pantau volume besok"

def analyze(df, ticker):
    if len(df) < 35: return None
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    df = df.dropna()
    if len(df) < 30: return None

    close=df['Close']; high=df['High']; low=df['Low']; vol=df['Volume']
    ma20=close.rolling(20).mean(); vol_ma20=vol.rolling(20).mean(); atr=(high-low).rolling(14).mean(); high20=high.rolling(20).max()

    c=last_float(close); m=last_float(ma20); v=last_float(vol); vm=last_float(vol_ma20); a=last_float(atr); h20=last_float(high20)
    if c==0 or m==0 or vm==0 or a==0: return None

    try: m5=float(ma20.dropna().iloc[-6])
    except: m5=m
    slope=(m-m5)/m5*100 if m5!=0 else 0
    v_ratio = v/vm if vm>0 else 0

    # hitung naik berapa hari
    try:
        closes = close.dropna().iloc[-6:-1].values
        days_up = 0
        for i in range(len(closes)-1, 0, -1):
            if closes[i] > closes[i-1]: days_up+=1
            else: break
    except: days_up=0

    sl = m if m < c else c - a*1.5
    if c - sl < 1: return None

    tp1 = h20
    tp2 = tp1 + (tp1 - c)*0.8 # TP2 = 80% ekstensi lagi
    rr = (tp1 - c)/(c - sl) if c-sl>0 else 0

    score=50
    if c>m: score+=15
    if slope>0: score+=10
    if v_ratio>1.5: score+=15
    elif v_ratio>1.0: score+=5
    if c>=h20*0.98: score+=10
    if rr>=1.4: score+=2

    if score>=78: act="STRONG BREAKOUT - BUY CICIL"; star="⭐⭐⭐"
    elif score>=71: act="BREAKOUT - BUY"; star="⭐⭐"
    elif score>=60: act="WAIT PULLBACK"; star="⭐⭐"
    else: act="SKIP"; star="⭐"

    lot = int((PORTO*RISK_PER_TRADE)/((c-sl)*100)) if c>sl else 1
    money = (c-sl)*100*lot
    money_str = f"max Rp {money/1_000_000:.1f}jt (~{lot} lot)"

    entry_low = int(c*0.99)
    entry_high = int(c*1.01)

    return {
        "ticker":ticker, "score":int(score), "c":c, "m":m, "sl":sl, "tp1":tp1, "tp2":tp2, "rr":rr,
        "v_ratio":v_ratio, "vol_str":f"{v_ratio:.1f}x {'VALID' if v_ratio>=1.2 else 'TIPIS'}",
        "slope":slope, "trend_str":f"{slope:+.1f}%/5hr", "action":act, "star":star,
        "lot":lot, "money_str":money_str, "entry":f"{entry_low}-{entry_high}",
        "days_up":days_up, "close_near_high":c/h20 if h20>0 else 0
    }

def main():
    tickers=get_tickers()
    results=[]
    for t in tickers:
        try:
            df=yf.download(t, period="3mo", progress=False, auto_adjust=True)
            if df.empty: continue
            r=analyze(df,t)
            if r and r['score']>=60: results.append(r)
        except: continue

    results=sorted(results, key=lambda x: (x['rr']>=MIN_RR, x['score']), reverse=True)
    top5=[r for r in results if r['rr']>=MIN_RR][:5]
    if len(top5)<5: # lengkapi dengan pullback biar tetap 5
        sisa = [r for r in results if r not in top5][:5-len(top5)]
        top5 = top5 + sisa

    now=datetime.now().strftime("%d %b %H:%M")
    msg=f"🔥 SCAN SULTAN LITE {now} | {len(tickers)} saham\nTop {len(top5)} layak pantau:\n\n"

    buy_count=0
    sektor_count={}
    for i,r in enumerate(top5,1):
        pct_sl=(r['sl']/r['c']-1)*100
        # cek sektor
        pure = r['ticker'].replace(".JK","")
        for sec, lst in SEKTOR.items():
            if pure in lst:
                sektor_count[sec]=sektor_count.get(sec,0)+1

        if "BUY" in r['action']: buy_count+=1

        note = get_note(r)
        msg+=f"#{i} {r['ticker']} {r['score']} - {r['action']} {r['star']}\n"
        msg+=f" Harga:{r['c']:.0f} | MA20:{r['m']:.0f} | Vol:{r['vol_str']} | Trend MA20:{r['trend_str']}\n"
        msg+=f" Entry:{r['entry']} | SL:{r['sl']:.0f} ({pct_sl:.1f}%) | TP1:{r['tp1']:.0f} TP2:{r['tp2']:.0f}\n"
        msg+=f" R:R 1:{r['rr']:.1f} | Money: {r['money_str']}\n"
        msg+=f" Note: {note}\n\n"

    # SUMMARY
    if top5:
        buy_list = [r['ticker'].replace('.JK','') for r in top5 if 'BUY' in r['action']]
        wait_list = [r['ticker'].replace('.JK','') for r in top5 if 'WAIT' in r['action']]
        sektor_kuat = max(sektor_count, key=sektor_count.get) if sektor_count else "-"
        total_risk = buy_count*1.5

        msg+=f"--- SUMMARY ---\n"
        if buy_list: msg+=f"{len(buy_list)} BUY: {', '.join(buy_list)} (prioritas)\n"
        if [r for r in top5 if 'HATI2' in r['action'] or r['score']<75 and 'BUY' in r['action']]:
            hati2 = [r['ticker'].replace('.JK','') for r in top5 if r['score']<78 and 'BUY' in r['action']]
            if hati2: msg+=f"{len(hati2)} BUY HATI2: {', '.join(hati2)}\n"
        if wait_list: msg+=f"{len(wait_list)} WAIT: {', '.join(wait_list)}\n"
        msg+=f"Sektor terkuat: {sektor_kuat}\n"
        msg+=f"Total risk jika ambil {buy_count} BUY: {total_risk:.1f}% porto\n"

    print(msg)
    if BOT_TOKEN and CHAT_ID:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={"chat_id":CHAT_ID,"text":msg})

if __name__=="__main__":
    main()
