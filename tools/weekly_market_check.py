import requests, os, sys, pandas as pd

# Biar bisa run manual di laptop: python tools/weekly_market_check.py
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or input("Masukkan BOT TOKEN (kosongkan untuk test lokal): ")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID") or "123"
WORKER = os.getenv("WORKER_URL", "https://yahoo-proxy.rizalmawardi766.workers.dev")
MODE = os.getenv("MODE", "full") # full atau test_telegram

def get_data(ticker):
    try:
        url = f"{WORKER}/v8/finance/chart/{ticker}?range=2y&interval=1d"
        r = requests.get(url, timeout=20)
        closes = r.json()['chart']['result'][0]['indicators']['quote'][0]['close']
        df = pd.Series([c for c in closes if c is not None])
        price = float(df.iloc[-1])
        ma50 = float(df.rolling(50).mean().iloc[-1])
        ma200 = float(df.rolling(200).mean().iloc[-1])
        delta = df.diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = -delta.where(delta < 0, 0).rolling(14).mean()
        rsi = 100 - (100 / (1 + gain/loss))
        rsi_last = float(rsi.iloc[-1])
        st, emoji = ("BAHAYA","🔴") if price < ma200 else ("DISKON","🟡") if price < ma50 else ("AMAN","🟢")
        return price, ma50, ma200, rsi_last, st, emoji
    except Exception as e:
        print(f"Error {ticker}: {e}")
        return 0,0,0,0,f"Error","⚪"

def fmt(t, p):
    return f"Rp{p:,.0f}" if "JK" in t or t in ["^JKSE","IDR=X"] else f"{p:.2f}%" if t=="^TNX" else f"${p:.2f}"

def send_telegram(text):
    if not BOT_TOKEN or not CHAT_ID.isdigit():
        print("\n[MODE LOKAL] Pesan tidak dikirim ke Telegram, cuma print di sini:\n")
        print(text)
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"})

if MODE == "test_telegram":
    send_telegram("✅ Test Manual Berhasil! Bot Weekly Check nyambung ke Telegram.")
    sys.exit(0)

# Data
qqq, ihsg, bmri, tlkm, asii, us10y, usdidr = [get_data(t) for t in ["QQQ","^JKSE","BMRI.JK","TLKM.JK","ASII.JK","^TNX","IDR=X"]]

msg = f"""
📈 *WEEKLY MARKET CHECK* - Manual Run
━━━━━━━━━━━━━━━━━━
*🇺🇸 QQQ* {qqq[5]} *{qqq[4]}*
`Price {fmt('QQQ',qqq[0])} | MA200 {fmt('QQQ',qqq[2])} | RSI {qqq[3]:.0f}`
US10Y: *{fmt('^TNX',us10y[0])}* {us10y[5]}

━━━━━━━━━━━━━━━━━━
*🇮🇩 IDX* {ihsg[5]} *{ihsg[4]}* - {fmt('^JKSE',ihsg[0])}
*BMRI* {bmri[5]} {bmri[4]} - {fmt('BMRI.JK',bmri[0])} | RSI {bmri[3]:.0f}
*TLKM* {tlkm[5]} {tlkm[4]} - {fmt('TLKM.JK',tlkm[0])} | RSI {tlkm[3]:.0f}
*ASII* {asii[5]} {asii[4]} - {fmt('ASII.JK',asii[0])} | RSI {asii[3]:.0f}

USD/IDR: *{fmt('IDR=X',usdidr[0])}*
━━━━━━━━━━━━━━━━━━
"""

bahaya = sum(1 for x in [qqq,ihsg,bmri,tlkm,asii] if x[4]=="BAHAYA")
msg += "⚠️ WASPADA - Tahan cash\n" if bahaya else "🟢 AMAN - HOLD\n"

send_telegram(msg)
print(msg)
