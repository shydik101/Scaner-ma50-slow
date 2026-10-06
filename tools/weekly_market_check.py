import requests, os, pandas as pd

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
WORKER = os.getenv("WORKER_URL", "https://yahoo-proxy.rizalmawardi766.workers.dev")

def get_data(ticker):
    try:
        url = f"{WORKER}/?ticker={ticker}"
        r = requests.get(url, timeout=20)
        j = r.json()
        closes = j['chart']['result'][0]['indicators']['quote'][0]['close']
        df = pd.Series([c for c in closes if c is not None])

        price = float(df.iloc[-1])
        ma50 = float(df.rolling(50).mean().iloc[-1])
        ma200 = float(df.rolling(200).mean().iloc[-1])

        delta = df.diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = -delta.where(delta < 0, 0).rolling(14).mean()
        rsi = 100 - (100 / (1 + gain/loss))
        rsi_last = float(rsi.iloc[-1])

        if price < ma200:
            st, emoji, arti = "BAHAYA", "🔴", "Trend panjang rusak, jebol MA200"
        elif price < ma50:
            st, emoji, arti = "DISKON", "🟡", "Lagi koreksi di bawah MA50"
        else:
            st, emoji, arti = "AMAN", "🟢", "Trend naik masih kuat"

        # Arti RSI
        if rsi_last > 70:
            rsi_arti = "Mahal (Overbought)"
        elif rsi_last < 30:
            rsi_arti = "Murah (Oversold)"
        else:
            rsi_arti = "Normal"

        return price, ma50, ma200, rsi_last, st, emoji, arti, rsi_arti
    except Exception as e:
        print(f"FAIL {ticker}: {e}")
        return 0,0,0,0,"Error","⚪","Error","-"

def fmt(t,p):
    return f"Rp{p:,.0f}" if "JK" in t or t in ["^JKSE","IDR=X"] else f"{p:.2f}%" if t=="^TNX" else f"${p:.2f}"

def send_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"})

d = {k: get_data(v) for k,v in {
    "QQQ":"QQQ","IHSG":"^JKSE","BMRI":"BMRI.JK",
    "TLKM":"TLKM.JK","ASII":"ASII.JK","US10Y":"^TNX","USDIDR":"IDR=X"
}.items()}

msg = f"""
📈 *LAPORAN PASAR MINGGUAN*
_Hari Minggu jam 07:00 WIB - Update Trend Panjang_

Halo, ini ringkasan kondisi pasar minggu ini:

━━━━━━━━━━━━━━━━━━━━━━
*🇺🇸 AMERIKA - QQQ (Nasdaq 100)*
━━━━━━━━━━━━━━━━━━━━━━
Harga sekarang: *{fmt('QQQ',d['QQQ'][0])}*
Status: {d['QQQ'][5]} *{d['QQQ'][4]}* - {d['QQQ'][6]}

Detail:
• MA50 (trend 50 hari): {fmt('QQQ',d['QQQ'][1])}
• MA200 (trend 200 hari): {fmt('QQQ',d['QQQ'][2])}
• RSI {d['QQQ'][3]:.0f} → {d['QQQ'][7]}

Artinya: QQQ di atas MA200 = trend panjang masih naik.

Bunga US 10 Tahun: *{fmt('^TNX',d['US10Y'][0])}*
→ Kalau di atas 4.5% biasanya pasar agak waspada.

━━━━━━━━━━━━━━━━━━━━━━
*🇮🇩 INDONESIA - IHSG*
━━━━━━━━━━━━━━━━━━━━━━
Harga sekarang: *{fmt('^JKSE',d['IHSG'][0])}*
Status: {d['IHSG'][5]} *{d['IHSG'][4]}* - {d['IHSG'][6]}

Detail:
• MA50: {fmt('^JKSE',d['IHSG'][1])}
• MA200: {fmt('^JKSE',d['IHSG'][2])}
• RSI {d['IHSG'][3]:.0f} → {d['IHSG'][7]}

━━━━━━━━━━━━━━━━━━━━━━
*📊 SAHAM PANTAUAN*
━━━━━━━━━━━━━━━━━━━━━━

*1. BMRI (Bank Mandiri)* {d['BMRI'][5]}
Harga: {fmt('BMRI.JK',d['BMRI'][0])} | Status: *{d['BMRI'][4]}*
MA50: {fmt('BMRI.JK',d['BMRI'][1])} | MA200: {fmt('BMRI.JK',d['BMRI'][2])}
RSI: {d['BMRI'][3]:.0f} ({d['BMRI'][7]})
→ {d['BMRI'][6]}

*2. TLKM (Telkom)* {d['TLKM'][5]}
Harga: {fmt('TLKM.JK',d['TLKM'][0])} | Status: *{d['TLKM'][4]}*
MA50: {fmt('TLKM.JK',d['TLKM'][1])} | MA200: {fmt('TLKM.JK',d['TLKM'][2])}
RSI: {d['TLKM'][3]:.0f} ({d['TLKM'][7]})
→ {d['TLKM'][6]}

*3. ASII (Astra)* {d['ASII'][5]}
Harga: {fmt('ASII.JK',d['ASII'][0])} | Status: *{d['ASII'][4]}*
MA50: {fmt('ASII.JK',d['ASII'][1])} | MA200: {fmt('ASII.JK',d['ASII'][2])}
RSI: {d['ASII'][3]:.0f} ({d['ASII'][7]})
→ {d['ASII'][6]}

━━━━━━━━━━━━━━━━━━━━━━
*💵 KURS*
USD/IDR: *{fmt('IDR=X',d['USDIDR'][0])}*
→ Kalau naik terus, saham IDX biasanya agak berat.

━━━━━━━━━━━━━━━━━━━━━━
*🧠 KESIMPULAN GAMPANG*
"""

bahaya = [k for k,v in d.items() if "BAHAYA" in v[4]]
diskon = [k for k,v in d.items() if "DISKON" in v[4]]

if bahaya:
    msg += f"🔴 *WASPADA* - {', '.join(bahaya)} jebol MA200. Artinya trend panjangnya lagi rusak. Lebih baik tahan cash dulu, jangan buru-buru beli banyak.\n\n"
elif diskon:
    msg += f"🟡 *ADA DISKON* - {', '.join(diskon)} lagi di bawah MA50. Ini saatnya cicil beli pelan-pelan (DCA), bukan all-in.\n\n"
else:
    msg += "🟢 *AMAN - HOLD* - Semua saham masih di atas MA200. Trend panjang masih bagus, tinggal hold aja.\n\n"

msg += """
*Catatan:*
MA50 = Rata-rata harga 50 hari (trend menengah)
MA200 = Rata-rata harga 200 hari (trend panjang)
RSI >70 = Sudah mahal, RSI <30 = Sudah murah

_Bukan ajakan jual/beli, hanya untuk monitoring mingguan._
"""

send_telegram(msg)
print(msg)
