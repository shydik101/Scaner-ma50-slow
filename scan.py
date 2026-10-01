import os
import json
import requests
import time
from datetime import datetime

TICKER_FILE = os.getenv("TICKER_FILE", "tickers-batch1.txt")
PROXY_URL = "https://yahoo-proxy.rizalmawardi766.workers.dev"
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
HOLDINGS_FILE = "my_holdings.json"

def send_telegram(msg):
    if not BOT_TOKEN or not CHAT_ID:
        print("Telegram env tidak ada")
        return
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}
        r = requests.post(url, json=payload, timeout=15)
        print(f"Telegram status: {r.status_code}")
    except Exception as e:
        print(f"Telegram error: {e}")

def get_chart(ticker):
    try:
        url = f"{PROXY_URL}/?ticker={ticker}"
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        data = r.json()
        result = data.get("chart", {}).get("result")
        if not result:
            return None
        return result[0]
    except Exception as e:
        print(f"Gagal {ticker}: {e}")
        return None

def analyze():
    if not os.path.exists(TICKER_FILE):
        print(f"{TICKER_FILE} tidak ada")
        return

    with open(TICKER_FILE) as f:
        tickers = [x.strip().upper() for x in f if x.strip()]

    print(f"Scanning {len(tickers)} saham dari {TICKER_FILE}")

    holdings = {}
    if os.path.exists(HOLDINGS_FILE):
        try:
            with open(HOLDINGS_FILE) as jf:
                holdings = json.load(jf)
        except:
            holdings = {}

    buy_list = []

    for ticker in tickers:
        chart = get_chart(ticker)
        if not chart:
            time.sleep(0.5)
            continue
        try:
            closes = chart["indicators"]["quote"][0]["close"]
            closes = [c for c in closes if c is not None]
            if len(closes) < 50:
                continue

            ma20 = sum(closes[-20:]) / 20
            ma50 = sum(closes[-50:]) / 50
            last = closes[-1]
            prev = closes[-2]

            if last > ma20 and ma20 > ma50 and last > prev:
                buy_list.append(f"{ticker} - {last} (MA20:{ma20:.0f})")
                holdings[ticker] = {"buy_price": last, "date": datetime.now().strftime("%Y-%m-%d"), "batch": TICKER_FILE}
        except Exception as e:
            print(f"Error analisa {ticker}: {e}")

        time.sleep(0.3)

    with open(HOLDINGS_FILE, "w") as out:
        json.dump(holdings, out, indent=2)

    print(f"BUY ketemu: {buy_list}")

    if buy_list:
        batch_name = "BIG CAP" if "batch1" in TICKER_FILE else "GORENGAN"
        msg = f"🚀 *BUY SIGNAL {batch_name}* {datetime.now().strftime('%d-%m %H:%M')}\n\n"
        msg += "\n".join(buy_list[:20])
        if len(buy_list) > 20:
            msg += f"\n...dan {len(buy_list)-20} lainnya"
        send_telegram(msg)

if __name__ == "__main__":
    analyze()
