import yfinance as yf
import os
import requests
import pandas as pd
from datetime import datetime

# AUTO CARI FILE TICKER
if os.path.exists("daytrade-observe-tickers.txt"):
    TICKER_FILE = "daytrade-observe-tickers.txt"
else:
    TICKER_FILE = "data/daytrade-observe-tickers.txt"

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

MIN_RR = 1.2 # aku turunin dari 1.4 biar tiap hari ada hasil
PORTO = 100_000_000
SAHAM_DELISTED = ["BWLA.JK", "FREN.JK", "MASA.JK", "SMAA.JK", "ULPL.JK", "BEBS.JK"]

def last_float(s):
    """Ambil nilai terakhir dengan aman dari Series yfinance versi baru"""
    try:
        v = s.iloc[-1]
        # kalau masih Series (MultiIndex)
        if isinstance(v, pd.Series):
            v = v.iloc[0]
        # kalau numpy
        if hasattr(v, 'item'):
            return float(v.item())
        return float(v)
    except:
        return 0.0

def get_tickers():
    if not os.path.exists(TICKER_FILE):
        print(f"FILE TIDAK KETEMU: {TICKER_FILE}")
        return []
    with open(TICKER_FILE) as f:
        raw = [x.strip().upper() for x in f if x.strip() and not x.startswith('#')]
    tickers = []
    for t in raw:
        if not t.endswith(".JK"):
            t = t + ".JK"
        if t not in SAHAM_DELISTED:
            tickers.append(t)
    print(f"LOAD {len(tickers)} saham dari {TICKER_FILE}")
    return tickers

def analyze(df, ticker):
    if len(df) < 30:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    close = df['Close']
    high = df['High']
    low = df['Low']
    vol = df['Volume']

    ma20 = close.rolling(20).mean()
    vol_ma20 = vol.rolling(20).mean()
    atr = (high - low).rolling(14).mean()

    c = last_float(close)
    m = last_float(ma20)
    v = last_float(vol)
    vm = last_float(vol_ma20)
    atr_val = last_float(atr)
    h20 = last_float(high.rolling(20).max())

    if c == 0 or m == 0 or vm == 0:
        return None

    # ambil MA 5 hari lalu untuk slope
    try:
        m5_val = ma20.iloc[-6]
        if isinstance(m5_val, pd.Series):
            m5_val = m5_val.iloc[0]
        m5 = float(m5_val)
    except:
        m5 = m

    if m5 == 0:
        slope = 0
    else:
        slope = (m - m5) / m5 * 100

    # ANTI DIVISION BY ZERO
    sl = m if m < c else c - atr_val * 1.5
    if c - sl <= 0.5: # SL terlalu mepet
        return None

    tp1 = h20
    rr = (tp1 - c) / (c - sl) if (c - sl) > 0 else 0

    score = 50
    if c > m: score += 15
    if slope > 0: score += 10
    if v > vm * 1.5: score += 15
    elif v > vm: score += 5
    if c >= h20 * 0.98: score += 10

    if score >= 75 and rr >= MIN_RR and v > vm * 1.2:
        action = "STRONG BREAKOUT - BUY CICIL"
    elif score >= 70 and rr >= MIN_RR:
        action = "BREAKOUT - BUY"
    elif score >= 55:
        action = "WAIT PULLBACK"
    else:
        action = "SKIP"

    max_lot = int((PORTO * 0.015) / ((c - sl) * 100)) if (c - sl) > 0 else 1

    return {
        "ticker": ticker, "score": int(score), "close": c, "ma20": m,
        "sl": sl, "tp1": tp1, "rr": rr, "vol": f"{v/vm:.1f}x",
        "trend": f"{slope:.1f}%", "action": action, "lot": max(1, max_lot)
    }

def main():
    tickers = get_tickers()
    if not tickers:
        print("TICKER KOSONG!")
        return

    print(f"START SCAN {len(tickers)} SAHAM")
    results = []
    for t in tickers:
        try:
            df = yf.download(t, period="3mo", progress=False, auto_adjust=True)
            if df.empty or len(df) < 25:
                continue
            r = analyze(df, t)
            if r and r['score'] >= 55:
                results.append(r)
                print(f"OK {t} Score {r['score']} RR {r['rr']:.1f}")
        except Exception as e:
            print(f"SKIP {t}: {e}")
            continue

    results = sorted(results, key=lambda x: x['score'], reverse=True)
    top_rr = [r for r in results if r['rr'] >= MIN_RR][:8]
    # kalau yang RR bagus gak ada, tampilkan top score aja
    top = top_rr if top_rr else results[:8]

    now = datetime.now().strftime("%d %b %H:%M")
    msg = f"🔥 SCAN SULTAN {now} | {len(tickers)} saham | R:R>={MIN_RR}\n"

    if top_rr:
        msg += f"Top {len(top_rr)} LAYAK:\n\n"
    else:
        msg += f"Tidak ada RR>={MIN_RR}, Top Score hari ini:\n\n"

    for i, r in enumerate(top, 1):
        star = "⭐"*3 if r['score']>=75 else "⭐"*2 if r['score']>=65 else "⭐"
        pct_sl = (r['sl']/r['close']-1)*100
        msg += f"#{i} {r['ticker']} {r['score']} {star} - {r['action']}\n"
        msg += f" {r['close']:.0f} MA{r['ma20']:.0f} Vol{r['vol']} Trend{r['trend']}\n"
        msg += f" SL{r['sl']:.0f}({pct_sl:.1f}%) TP{r['tp1']:.0f} RR 1:{r['rr']:.1f} {r['lot']}lot\n\n"

    print(msg)

    if BOT_TOKEN and CHAT_ID:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        res = requests.post(url, data={"chat_id": CHAT_ID, "text": msg})
        print(f"TELEGRAM: {res.status_code} - {res.text[:200]}")
    else:
        print(f"SECRET KOSONG Token={bool(BOT_TOKEN)} Chat={bool(CHAT_ID)}")

if __name__ == "__main__":
    main()
