import yfinance as yf, pandas as pd, requests, os
from datetime import datetime
TOKEN = os.getenv("8824185237:AAH2VLFwOkW-iSpxEQ3u0fIQ-4AS8DnYug0")
CHAT_ID = os.getenv("109436181")
tickers = ["BBCA.JK","BBRI.JK","BMRI.JK","BBNI.JK","TLKM.JK","ASII.JK","UNTR.JK","ADRO.JK","AMRT.JK","ICBP.JK","INDF.JK","KLBF.JK","INCO.JK","ANTM.JK","MDKA.JK","PTBA.JK","ITMG.JK","ISAT.JK","SMGR.JK","JSMR.JK","MEDC.JK","BRPT.JK","AKRA.JK","MAPI.JK","MYOR.JK","BBTN.JK","HRUM.JK","BUMI.JK","GOTO.JK","EMTK.JK","CTRA.JK","PWON.JK","BSDE.JK","PGAS.JK","INDY.JK","ELSA.JK","ACES.JK"]
hasil = []
for t in tickers:
    try:
        df = yf.download(t, period="1y", interval="1d", progress=False)
        if len(df) < 60: continue
        df['MA50'] = df['Close'].rolling(50).mean()
        df_w = df['Close'].resample('W').last().rolling(50).mean()
        close = float(df['Close'].iloc[-1]); ma50_d = float(df['MA50'].iloc[-1]); ma50_w = float(df_w.iloc[-1])
        jarak = ((close-ma50_d)/ma50_d)*100
        if -3 <= jarak <= 3 and close > ma50_w:
            hasil.append(f"{t.replace('.JK','')} | {int(close)} | {round(jarak,2)}%")
    except: continue
now = datetime.now().strftime('%d %b %Y %H:%M')
pesan = f"📊 SCAN MA50 {now} WIB\n\n" + "\n".join([f"{i+1}. {h}" for i,h in enumerate(hasil)]) if hasil else f"⚠️ SCAN {now} - HOLD CASH, tidak ada kandidat"
requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", data={"chat_id": CHAT_ID, "text": pesan})
