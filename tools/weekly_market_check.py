import requests, os, pandas as pd

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
WORKER = os.getenv("WORKER_URL", "https://yahoo-proxy.rizalmawardi766.workers.dev")

def get_data(ticker):
    try:
        url = f"{WORKER}/?ticker={ticker}"
        r = requests.get(url, timeout=20)
        print(f"GET {url} -> {r.status_code} {r.text[:200]}")
        j = r.json()

        # Worker kamu kemungkinan balikin format Yahoo langsung atau custom
        # Kita handle 2 kemungkinan
        if 'chart' in j:
            closes = j['chart']['result'][0]['indicators']['quote'][0]['close']
            df = pd.Series([c for c in closes if c is not None])
        elif 'close' in j or 'prices' in j or 'data' in j:
            raw = j.get('close') or j.get('prices') or j.get('data') or j.get('chart')
            # kalau array of dict
            if isinstance(raw, list) and isinstance(raw[0], dict):
                df = pd.Series([x.get('close') or x.get('c') for x in raw])
            else:
                df = pd.Series(raw)
            df = df.dropna()
        else:
            # fallback: j langsung list harga
            df = pd.Series(list(j.values())[0] if isinstance(j, dict) else j)

        price = float(df.iloc[-1])
        ma50 = float(df.rolling(50).mean().iloc[-1])
        ma200 = float(df.rolling(200).mean().iloc[-1])

        delta = df.diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = -delta.where(delta < 0, 0).rolling(14).mean()
        rsi = 100 - (100 / (1 + gain/loss))
        rsi_last = float(rsi.iloc[-1])

        if price < ma200:
            st, emoji = "BAHAYA 🔴 Jebol MA200", "🔴"
        elif price < ma50:
            st, emoji = "DISKON 🟡 Di bawah MA50", "🟡"
        else:
            st, emoji = "AMAN ✅ Di atas MA", "🟢"
        return price, ma50, ma200, rsi_last, st, emoji
    except Exception as e:
        print(f"FAIL {ticker}: {e}")
        return 0,0,0,0,f"Error {e}"[:100],"⚪"

def fmt(t,p):
    if p==0: return "Error"
    return f"Rp{p:,.0f}" if "JK" in t or t in ["^JKSE","IDR=X"] else f"{p:.2f}%" if t=="^TNX" else f"${p:.2f}"

def send_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"})

datas = {}
for t in ["QQQ","^JKSE","BMRI.JK","TLKM.JK","ASII.JK","^TNX","IDR=X"]:
    datas[t] = get_data(t)

msg = f"""
📈 *WEEKLY MARKET CHECK*
Minggu 07:00 WIB | Pakai Worker

━━━━━━━━━━━━━━━━━━
*🇺🇸 US*
*QQQ* {datas['QQQ'][5]} {datas['QQQ'][4]}
`{fmt('QQQ',datas['QQQ'][0])} | MA200 {fmt('QQQ',datas['QQQ'][2])} | RSI {datas['QQQ'][3]:.0f}`
US10Y: *{fmt('^TNX',datas['^TNX'][0])}*

━━━━━━━━━━━━━━━━━━
*🇮🇩 IDX*
*IHSG* {datas['^JKSE'][5]} `{fmt('^JKSE',datas['^JKSE'][0])}`
*BMRI* {datas['BMRI.JK'][5]} `{fmt('BMRI.JK',datas['BMRI.JK'][0])} | RSI {datas['BMRI.JK'][3]:.0f}`
*TLKM* {datas['TLKM.JK'][5]} `{fmt('TLKM.JK',datas['TLKM.JK'][0])} | RSI {datas['TLKM.JK'][3]:.0f}`
*ASII* {datas['ASII.JK'][5]} `{fmt('ASII.JK',datas['ASII.JK'][0])} | RSI {datas['ASII.JK'][3]:.0f}`

USD/IDR: *{fmt('IDR=X',datas['IDR=X'][0])}*
━━━━━━━━━━━━━━━━━━
"""
msg += "🟢 *HOLD* - Trend aman\n" if all("AMAN" in d[4] for d in [datas['QQQ'],datas['^JKSE']]) else "🟡 *WASPADA* - Ada diskon\n"

send_telegram(msg)
print(msg)
