import yfinance as yf
import requests
import os

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

TICKERS = {
    "QQQ": "QQQ",
    "IHSG": "^JKSE",
    "BMRI": "BMRI.JK",
    "TLKM": "TLKM.JK",
    "ASII": "ASII.JK",
    "US10Y": "^TNX",
    "USDIDR": "IDR=X"
}

def get_check(ticker):
    df = yf.download(ticker, period="2y", interval="1d", progress=False)
    if len(df) < 200:
        return None
    price = float(df['Close'].iloc[-1])
    ma50 = float(df['Close'].rolling(50).mean().iloc[-1])
    ma200 = float(df['Close'].rolling(200).mean().iloc[-1])

    # RSI weekly approx dari daily
    delta = df['Close'].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = -delta.where(delta < 0, 0).rolling(14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    rsi_last = float(rsi.iloc[-1])

    status = "AMAN ✅"
    if price < ma200:
        status = "BAHAYA 🔴 Jebol MA200"
    elif price < ma50:
        status = "DISKON ⚠️ Di bawah MA50"

    return price, ma50, ma200, rsi_last, status

def send_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"})

msg = "📊 *WEEKLY MARKET CHECK - Minggu 07:00 WIB*\n\n"

# QQQ
p, ma50, ma200, rsi, st = get_check(TICKERS["QQQ"])
msg += f"*US - QQQ*\nPrice ${p:.2f} | MA50 ${ma50:.0f} | MA200 ${ma200:.0f}\nRSI {rsi:.0f} | Status: {st}\n\n"

# IHSG
p, ma50, ma200, rsi, st = get_check(TICKERS["IHSG"])
msg += f"*ID - IHSG*\n{p:.0f} | MA50 {ma50:.0f} | MA200 {ma200:.0f} | {st}\n\n"

for name in ["BMRI", "TLKM", "ASII"]:
    p, ma50, ma200, rsi, st = get_check(TICKERS[name])
    msg += f"{name}: Rp{p:.0f} (MA200 Rp{ma200:.0f}) - {st}\n"

# Yield & Kurs
us10y = yf.download("^TNX", period="5d", progress=False)['Close'].iloc[-1]
usd_idr = yf.download("IDR=X", period="5d", progress=False)['Close'].iloc[-1]
msg += f"\nUS10Y: {float(us10y):.2f}% {'AMAN ✅' if float(us10y) < 4.5 else 'WASPADA ⚠️ >4.5%'}\n"
msg += f"USD/IDR: Rp{float(usd_idr):.0f}\n\n"

msg += "Kesimpulan: HOLD kalau semua AMAN, siap Buy Dip kalau DISKON ⚠️"

send_telegram(msg)
print(msg)
