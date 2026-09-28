import yfinance as yf
import os
import requests
from datetime import datetime

TICKER_FILE = "daytrade-observe-tickers.txt"
# fallback kalau nanti kamu pindahin ke folder data
if not os.path.exists(TICKER_FILE):
    TICKER_FILE = "data/daytrade-observe-tickers.txt"
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
MIN_SCORE = 55
MIN_RR = 1.4
PORTO = 50_000_000

def get_tickers():
    with open(TICKER_FILE) as f:
        return [x.strip() for x in f if x.strip()]

def analyze(df, ticker):
    close = df['Close']
    high = df['High']
    low = df['Low']
    vol = df['Volume']
    ma20 = close.rolling(20).mean()
    vol_ma20 = vol.rolling(20).mean()
    atr = (high - low).rolling(14).mean()
    
    if len(df) < 30:
        return None

    last_close = float(close.iloc[-1])
    last_ma20 = float(ma20.iloc[-1])
    last_vol = float(vol.iloc[-1])
    last_vol_ma = float(vol_ma20.iloc[-1])
    last_atr = float(atr.iloc[-1])
    last_high20 = float(high.rolling(20).max().iloc[-1])
    ma20_slope = (ma20.iloc[-1] - ma20.iloc[-5]) / ma20.iloc[-5] * 100 if ma20.iloc[-5] != 0 else 0
    
    score = 50
    if last_close > last_ma20: score += 15
    if ma20_slope > 0: score += 10
    if last_vol > last_vol_ma * 1.5: score += 15
    elif last_vol > last_vol_ma: score += 5
    if last_close >= last_high20 * 0.98: score += 10
    
    sl = last_ma20 if last_ma20 < last_close else last_close - last_atr*1.5
    tp1 = last_high20
    tp2 = last_close + (last_close - sl) * 2
    entry = last_close
    
    rr = (tp1 - entry) / (entry - sl) if (entry - sl) > 0 else 0
    vol_label = f"{last_vol/last_vol_ma:.1f}x {'VALID' if last_vol > last_vol_ma*1.2 else 'TIPIS'}"
    
    if score >= 75 and rr >= MIN_RR and last_vol > last_vol_ma*1.2:
        action = "STRONG BREAKOUT - BUY CICIL"
    elif score >= 70 and rr >= MIN_RR:
        action = "BREAKOUT - BUY"
    elif score >= 55:
        action = "WAIT PULLBACK"
    else:
        action = "SKIP"
    
    risk_rp = PORTO * 0.015
    risk_per_lembar = entry
