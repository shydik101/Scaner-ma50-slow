import os
import requests
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

TICKER_FILE = os.getenv("TICKER_FILE", "tickers-batch1.txt")
PROXY_URL = "https://yahoo-proxy.rizalmawardi766.workers.dev"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

DIVIDEN_KINGS = {
    "BBCA.JK", "BBRI.JK", "BMRI.JK", "BBNI.JK", "BBTN.JK",
    "TLKM.JK", "ASII.JK", "UNTR.JK", "PTBA.JK", "ADRO.JK",
    "ITMG.JK", "ANTM.JK", "ICBP.JK", "INDF.JK", "KLBF.JK",
    "SMGR.JK", "INTP.JK", "GGRM.JK", "HMSP.JK"
}

def send_telegram(msg):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print(msg); return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=10)

def get_data(ticker):
    try:
        url = f"{PROXY_URL}/?ticker={ticker}"
        r = requests.get(url, timeout=15)
        data = r.json()
        closes = data["chart"]["result"][0]["indicators"]["quote"][0]["close"]
        volumes = data["chart"]["result"][0]["indicators"]["quote"][0]["volume"]
        df = pd.DataFrame({"close": closes, "vol": volumes}).dropna()
        return df if len(df) >= 60 else None
    except:
        return None

def analyze_ticker(ticker):
    df = get_data(ticker)
    if df is None: return None
    df["MA50"] = df["close"].rolling(50).mean()
    delta = df["close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df["RSI"] = 100 - (100 / (1 + rs))
    df["vol_avg"] = df["vol"].rolling(20).mean()
    df["vol_ratio"] = df["vol"] / df["vol_avg"]
    last = df.iloc[-1]; prev = df.iloc[-2]
    close = last["close"]; ma50 = last["MA50"]
    if pd.isna(ma50): return None
    rsi = round(last["RSI"],0) if not pd.isna(last["RSI"]) else 50
    vol = round(last["vol_ratio"],1) if not pd.isna(last["vol_ratio"]) else 1.0
    adx = 35
    score = 0
    dist_ma50 = ((close - ma50) / ma50) * 100
    if close > ma50 and prev["close"] <= df.iloc[-2]["MA50"]: score += 40
    elif close > ma50: score += 20
    if vol >= 1.5: score += 15
    if 50 <= rsi <= 70: score += 15
    if 0 < dist_ma50 <= 7: score += 10
    if score < 40: return None

    if score >= 70: trend_label, stars = "STRONG BREAKOUT", 4
    elif score >= 55: trend_label, stars = "BREAKOUT", 3
    else: trend_label, stars = "UPTREND", 2

    ma50_val = int(ma50); sl_long = int(close * 0.95)
    tp1_long = int(close * 1.12); tp2_long = int(close * 1.25)
    entry_low = int(close * 0.995); entry_high = int(close * 1.005)
    lot = int(1000000 / close) if close > 0 else 0
    is_dividen = ticker in DIVIDEN_KINGS

    msg = f"#{ticker} {score} {trend_label} - BUY\n"
    msg += f"{'⭐'*stars}\n"
    msg += f"Harga: {int(close)} | MA50: {ma50_val} ({dist_ma50:+.1f}% di atas MA50)\n"
    msg += f"Vol: {vol}x | RSI: {int(rsi)} | ADX: {adx} | Lot {lot}\n"
    msg += f"Entry: {entry_low}-{entry_high} SL: {sl_long} (-5%) TP: {tp1_long} (+12%) / {tp2_long}\n"
    msg += f"Trend: UPTREND - Hold 1-3 Bulan"
    if is_dividen: msg += f"\nDividen King ⭐"
    return {"score": score, "msg": msg, "ticker": ticker}

def main():
    print(f"V9 LONG-TERM START - {TICKER_FILE}")
    with open(TICKER_FILE) as f:
        tickers = [l.strip() for l in f if l.strip() and not l.startswith("#")]
    results = []
    with ThreadPoolExecutor(max_workers=15) as ex:
        futs = {ex.submit(analyze_ticker, t): t for t in tickers}
        for fu in as_completed(futs):
            r = fu.result()
            if r: results.append(r)
    results = sorted(results, key=lambda x: x["score"], reverse=True)[:10]
    if not results:
        send_telegram(f"🔍 Scan {TICKER_FILE} {datetime.now():%d %b %H:%M} - Tidak ada STRONG BREAKOUT hari ini.")
        return
    full = f"🔥 SCAN V9 LONG-TERM {datetime.now():%d %b %H:%M} - {TICKER_FILE}\nTop {len(results)} Saham di atas MA50 (Hold 1-3 Bulan)\n\n"
    for i, r in enumerate(results, 1):
        full += r["msg"].replace(f"#{r['ticker']}", f"#{i} {r['ticker']}") + "\n\n"
    print(full); send_telegram(full)

if __name__ == "__main__": main()
