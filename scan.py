import yfinance as yf, os, requests, pandas as pd
from datetime import datetime

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
MIN_RR = 1.4
PORTO = 100_000_000
RISK_PER_TRADE = 0.015

SEKTOR = {
    "NIKEL": ["MDKA","ANTM","INCO","NCKL","MBMA","HRUM","ADMR"],
    "ENERGY": ["ADRO","PTBA","ITMG","PTRO","RAJA","MEDC","ELSA","AKRA","PGAS","PGEO","BREN","DEWA","CUAN"],
    "BANK": ["BBCA","BBRI","BMRI","BBNI","BBTN","BRIS","BNGA","ARTO"],
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
    possible = ["daytrade-observe-tickers.txt", "data/daytrade-observe-tickers.txt"]
    TICKER_FILE = None
    for p in possible:
        if os.path.exists(p):
            TICKER_FILE = p
            break
    if not TICKER_FILE:
        print(f"ERROR file ticker tidak ada! cek: {possible}")
        print(f"Isi folder: {os.listdir('.')}")
        if os.path.exists("data"):
            print(f"Isi data/: {os.listdir('data')}")
        return []
    print(f"Pakai file: {TICKER_FILE}")
    with open(TICKER_FILE) as f:
        raw = [x.strip().upper().replace(".JK","") for x in f if x.strip() and not x.startswith('#')]
    # FIX: tambahin biang kerok error
    BUANG = ["WSKT","WIKA","PTPP","ADHI","INDX","FREN","BWLA","MASA","SMAA","ULPL","BEBS","BIPI","KPAL"]
    clean = [t for t in raw if t not in BUANG and len(t)>=4]
    print(f"Total ticker bersih: {len(clean)} (buang {len(raw)-len(clean)} delisting)")
    return [t+".JK" for t in clean]

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

    # FIX SL anti -0.5%
    sl_ma = m
    sl_atr = c - a*1.8
    sl = min(sl_ma, sl_atr)
    min_sl = c * 0.97
    if sl > min_sl: sl = min_sl
    if c - sl < 1: return None

    tp1 = h20
    tp2 = tp1 * 1.06
    rr = (tp1 - c)/(c - sl) if c-sl>0 else 0

    score=50
    if c>m: score+=15
    if slope>0: score+=10
    if v_ratio>1.5: score+=15
    elif v_ratio>1.0: score+=5
    if c>=h20*0.98: score+=10
    if rr>=MIN_RR: score+=5

    if score>=78: act="STRONG BREAKOUT - BUY CICIL"; star="⭐⭐⭐"
    elif score>=71: act="BREAKOUT - BUY"; star="⭐⭐"
    elif score>=60: act="WAIT PULLBACK"; star="⭐⭐"
    else: act="SKIP"; star="⭐"

    # FIX LOT BIAR GAK -1666 lot
    risk_rp = PORTO * RISK_PER_TRADE
    risk_per_share = abs(c - sl)
    lot = int(risk_rp / (risk_per_share * 100))
    lot = max(1, min(lot, 500))
    money = risk_per_share * 100 * lot
    entry_low = int(c*0.995)
    entry_high = int(c*1.005)

    return {
        "ticker":ticker, "score":int(score), "c":c, "m":m, "sl":sl, "tp1":tp1, "tp2":tp2, "rr":rr,
        "v_ratio":v_ratio, "vol_str":f"{v_ratio:.1f}x {'VALID' if v_ratio>=1.0 else 'TIPIS'}",
        "slope":slope, "trend_str":f"{slope:+.1f}%/5hr", "action":act, "star":star,
        "lot":lot, "money_str":f"max Rp {money/1_000_000:.1f}jt (~{lot} lot)", "entry":f"{entry_low}-{entry_high}",
    }

def main():
    print("--- SCAN SULTAN LITE START ---")
    tickers=get_tickers()
    if not tickers:
        print("STOP tidak ada ticker")
        return
    results=[]
    for t in tickers:
        try:
            df=yf.download(t, period="3mo", progress=False, auto_adjust=True)
            if df.empty:
                print(f"skip {t} empty")
                continue
            r=analyze(df,t)
            if r and r['score']>=60: results.append(r)
        except Exception as e:
            print(f"Skip {t} err {e}")
            continue
    print(f"Berhasil analisa: {len(results)} saham")
    results=sorted(results, key=lambda x: (x['rr']>=MIN_RR, x['score']), reverse=True)
    top5=[r for r in results if r['rr']>=MIN_RR][:5]
    if len(top5)<5:
        sisa=[r for r in results if r not in top5][:5-len(top5)]
        top5=top5+sisa
    now=datetime.now().strftime("%d %b %H:%M")
    msg=f"🔥 SCAN SULTAN LITE {now} | {len(tickers)} saham\nTop {len(top5)} layak pantau:\n\n"
    sektor_count={}; buy_count=0
    for i,r in enumerate(top5,1):
        pct_sl=(r['sl']/r['c']-1)*100
        pure=r['ticker'].replace(".JK","")
        for sec,lst in SEKTOR.items():
            if pure in lst: sektor_count[sec]=sektor_count.get(sec,0)+1
        if "BUY" in r['action']: buy_count+=1
        if r['v_ratio']>=1.2 and r['slope']>1.5:
            note="Volume valid, MA20 nanjak tajam, close dekat high 20hr"
        elif r['v_ratio']<1.0:
            note="Skor oke tapi volume tipis - rawan false breakout. Hati-hati."
        elif r['c']>r['tp1']:
            note=f"Boleh ambil, tapi jangan kejar di atas {r['tp1']:.0f}"
        else:
            note="Pantau volume besok"
        msg+=f"#{i} {r['ticker']} {r['score']} - {r['action']} {r['star']}\n"
        msg+=f" Harga:{r['c']:.0f} | MA20:{r['m']:.0f} | Vol:{r['vol_str']} | Trend MA20:{r['trend_str']}\n"
        msg+=f" Entry:{r['entry']} | SL:{r['sl']:.0f} ({pct_sl:.1f}%) | TP1:{r['tp1']:.0f} TP2:{r['tp2']:.0f}\n"
        msg+=f" R:R 1:{r['rr']:.1f} | Money: {r['money_str']}\n"
        msg+=f" Note: {note}\n\n"
    if top5:
        buy_list=[r['ticker'].replace('.JK','') for r in top5 if 'BUY' in r['action']]
        wait_list=[r['ticker'].replace('.JK','') for r in top5 if 'WAIT' in r['action']]
        sektor_kuat=max(sektor_count, key=sektor_count.get) if sektor_count else "-"
        total_risk=buy_count*1.5
        msg+=f"--- SUMMARY ---\n"
        if buy_list: msg+=f"{len(buy_list)} BUY: {', '.join(buy_list)} (prioritas)\n"
        if wait_list: msg+=f"{len(wait_list)} WAIT: {', '.join(wait_list)}\n"
        msg+=f"Sektor terkuat: {sektor_kuat}\n"
        msg+=f"Total risk jika ambil {buy_count} BUY: {total_risk:.1f}% porto\n"
    print(msg)
    if BOT_TOKEN and CHAT_ID:
        r=requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={"chat_id":CHAT_ID,"text":msg})
        print(f"TELEGRAM status: {r.status_code}")
    else:
        print("TELEGRAM token kosong - cek Secrets")

if __name__=="__main__":
    main()
