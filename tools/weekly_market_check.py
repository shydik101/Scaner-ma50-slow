import requests, os, pandas as pd

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
WORKER = os.getenv("WORKER_URL", "https://yahoo-proxy.rizalmawardi766.workers.dev")

def get_check(ticker):
    try:
        # endpoint chart via worker kamu
        url = f"{WORKER}/v8/finance/chart/{ticker}?range=2y&interval=1d"
        r = requests.get(url, timeout=20)
        j = r.json()
        result = j['chart']['result'][0]
        closes = result['indicators']['quote'][0]['close']
        df = pd.Series(closes).dropna()

        price = float(df.iloc[-1])
        ma50 = float(df.rolling(50).mean().iloc[-1])
        ma200 = float(df.rolling(200).mean().iloc[-1])

        # RSI 14
        delta = df.diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = -delta.where(delta < 0, 0).rolling(14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        rsi_last = float(rsi.iloc[-1])

        if price < ma200:
            status = "BAHAYA 🔴 Jebol MA200"
        elif price < ma50:
            status = "DISKON ⚠️ Di bawah MA50"
        else:
            status = "AMAN ✅"

        return f"{ticker}: {price:.0f} | MA50 {ma50:.0f} | MA200 {ma200:.0f} | RSI {rsi_last:.0f} | {status}"
    except Exception as e:
        return f"{ticker}: Error {e}"

def send_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": text})

tickers = ["QQQ", "^JKSE", "BMRI.JK", "TLKM.JK", "ASII.JK"]

lines = ["📊 WEEKLY MARKET CHECK - Minggu 07:00 WIB", ""]
for t in tickers:
    lines.append(get_check(t))

# Tambahan US10Y & USDIDR
try:
    lines.append("")
    lines.append(get_check("^TNX") + " (US10Y)")
    lines.append(get_check("IDR=X") + " (USD/IDR)")
except:
    pass

msg = "\n".join(lines)
print(msg)
send_telegram(msg)
