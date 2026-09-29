import yfinance as yf
import requests
import os
import time
import numpy as np
from datetime import datetime

TOKEN = os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def load_tickers():
    try:
        with open("daytrade-observe-tickers.txt") as f:
            tickers = [x.strip() for x in f if x.strip() and not x.startswith("#")]
            if tickers:
                return tickers
    except:
        pass
    return ["BBCA.JK","BBRI.JK","BMRI.JK","BBNI.JK","TLKM.JK","ASII.JK","UNTR.JK","CUAN.JK","GOTO.JK","BREN.JK"]

def scan_one(t):
    try:
        t = t.upper().strip()
        if not t.endswith(".JK"): t += ".JK"
        df = yf.download(t, period="1y", interval="1d", progress=False, auto_adjust=True)
        if len(df) < 60: return None

        c = float(df['Close'].iloc[-1])
        o = float(df['Open'].iloc[-1])
        h = float(df['High'].iloc[-1])
        l = float(df['Low'].iloc[-1])
        ma20 = float(df['Close'].rolling(20).mean().iloc[-1])
        ma50 = float(df['Close'].rolling(50).mean().iloc[-1])
        vol = float(df['Volume'].iloc[-1])
        vol_avg = float(df['Volume'].rolling(20).mean().iloc[-1])
        vol_r = vol / vol_avg if vol_avg>0 else 0
        trend = (c - ma20) / ma20 * 100
        
        tr = np.maximum(df['High']-df['Low'], np.maximum(abs(df['High']-df['Close'].shift(1)), abs(df['Low']-df['Close'].shift(1))))
        atr = float(tr.rolling(14).mean().iloc[-1])
        
        # === SISTEM SKOR 5 BINTANG BARU ===
        score = 0
        
        # 1. Posisi Harga vs MA20 (max 30 poin)
        if c > ma20 * 1.05: score += 30
        elif c > ma20 * 1.02: score += 25
        elif c > ma20: score += 15
        elif c > ma20 * 0.98: score += 5
        
        # 2. Volume (max 30 poin)
        if vol_r >= 3.0: score += 30
        elif vol_r >= 2.0: score += 25
       
