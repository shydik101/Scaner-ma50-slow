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
    # cari file otomatis
    possible = ["daytrade-observe-tickers.txt", "data/daytrade-observe-tickers.txt"]
    TICKER_FILE = None
    for p in possible:
        if os.path.exists(p):
            TICKER_FILE = p
            break
    if not TICKER_FILE:
        print(f"ERROR file ticker tidak ada! cek: {possible}")
        print(f"Isi folder: {os.listdir('.')}")
        return []

    print(f"Pakai file: {TICKER_FILE}")
    with open(TICKER_FILE) as f:
        raw = [x.strip().upper().replace(".JK","") for x in f if x.strip() and not x.startswith('#')]

    # BUANG SAHAM DELISTING / BIKIN ERROR
    BUANG = ["WSKT","WIKA","PTPP","FREN","BWLA","MASA","SMAA","ULPL","BEBS"]
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

    # FIX SL BIAR GAK -0.5%
    sl_ma = m
    sl_atr = c - a*1.8
    sl = min(sl_ma, sl_atr)
    min_sl = c * 0.97 # minimal 3% di bawah
    if sl > min_sl:
        sl = min_sl

    if c - sl < 1: return None
    tp1 = h20
    tp2 = tp1 * 1.06
    rr = (tp1 - c)/(c - sl)
