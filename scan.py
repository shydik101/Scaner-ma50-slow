import yfinance as yf, requests
from datetime import datetime

# TANAM LANGSUNG - biar tidak pusing Secret
TOKEN = "8824185237:AAH2VLFwOkW-iSpxEQ3u0fIQ-4AS8DnYug0"
CHAT_ID = "7855961885"

print(f"Test kirim ke {CHAT_ID} dengan token {TOKEN[:10]}...")

tickers = ["BBCA.JK","BBRI.JK","BMRI.JK","BBNI.JK","TLKM.JK","ASII.JK","UNTR.JK","ADRO.JK","AMRT.JK","ICBP.JK"]
hasil = []
for t in tickers:
    try:
        df = yf.download(t, period="3mo", interval="1d", progress=False, auto_adjust=True)
        if len(df) < 60: continue
        close = df['Close'].iloc[-1].item()
        ma50 = df['Close'].rolling(50).mean().iloc[-1].item()
        jarak = ((close-ma50)/ma50)*100
        if -3 <= jarak <= 3:
            hasil.append(f"{t.replace('.JK','')} {int(close)} {round(jarak,2)}%")
    except:
        continue

pesan = f"✅ BOT JALAN {datetime.now().strftime('%d %b %H:%M WIB')}\n" + ("\n".join(hasil) if hasil else "HOLD CASH - belum ada dekat MA50")
print(pesan)

r = requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", data={"chat_id": CHAT_ID, "text": pesan})
print(f"TELEGRAM RESPONSE: {r.text}")
