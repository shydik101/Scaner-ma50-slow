import yfinance as yf, requests, time
from datetime import datetime

TOKEN = "8824185237:AAH2VLFwOkW-iSpxEQ3u0fIQ-4AS8DnYug0"
CHAT_ID = "7855961885"

# LIST LENGKAP SAHAM INDONESIA (LQ45 + IDX80 + LQ45 tambahan)
# Kalau mau full 900 saham, nanti kita pakai file txt
TICKERS = [
"BBCA.JK","BBRI.JK","BMRI.JK","BBNI.JK","BRIS.JK","BNGA.JK","BMAS.JK","BBTN.JK","BBTN.JK","BJBR.JK",
"TLKM.JK","ISAT.JK","EXCL.JK","TOWR.JK","MTEL.JK",
"ASII.JK","UNTR.JK","AUTO.JK","DRMA.JK","INKP.JK","TKIM.JK",
"ADRO.JK","ADMR.JK","PTBA.JK","ITMG.JK","UNVR.JK","ICBP.JK","INDF.JK","KLBF.JK","SIDO.JK",
"AMRT.JK","MAPI.JK","MAPA.JK","ACES.JK","ERAA.JK",
"GOTO.JK","BUKA.JK","EMTK.JK","SCMA.JK",
"ANTM.JK","MDKA.JK","INCO.JK","NCKL.JK","HRUM.JK","BRMS.JK","MBMA.JK",
"PGAS.JK","MEDC.JK","AKRA.JK","ESSA.JK",
"CTRA.JK","PWON.JK","BSDE.JK","SMRA.JK","PANI.JK",
"SMGR.JK","INTP.JK","INDU.JK",
"TLKM.JK","JSMR.JK","WIKA.JK","PTPP.JK","ADHI.JK",
"ARTO.JK","BBYB.JK","BRPT.JK","TPIA.JK","CUAN.JK","BREN.JK","AMMN.JK","PGEO.JK"
]
# Tips: nanti tambah lagi sampai 200-300 ticker favoritmu

hasil = []
print(f"Mulai scan {len(TICKERS)} saham...")

for t in TICKERS:
    try:
        df = yf.download(t, period="6mo", interval="1d", progress=False, auto_adjust=True)
        if len(df) < 60: continue
        
        close = df['Close'].iloc[-1].item()
        ma20 = df['Close'].rolling(20).mean().iloc[-1].item()
        ma50 = df['Close'].rolling(50).mean().iloc[-1].item()
        ma50_prev = df['Close'].rolling(50).mean().iloc[-11].item() # 10 hari lalu
        vol = df['Volume'].iloc[-1].item()
        vol_avg = df['Volume'].rolling(20).mean().iloc[-1].item()
        
        jarak = ((close - ma50) / ma50) * 100
        slope_ma50 = ma50 > ma50_prev # MA50 naik?

        # FILTER KETAT: TREND NAIK + DEKAT MA50
        is_uptrend = close > ma50 and ma20 > ma50 and slope_ma50
        is_dekat = -3 <= jarak <= 3
        is_volume = vol > (vol_avg * 0.8)

        if is_uptrend and is_dekat and is_volume:
            hasil.append(f"{t.replace('.JK','')} | {int(close)} | MA50 {round(jarak,1)}% | Vol {int(vol/vol_avg*100)}%")

        time.sleep(0.2) # biar tidak di-ban yahoo
    except Exception as e:
        continue

now = datetime.now().strftime('%d %b %H:%M')
if hasil:
    pesan = f"🔥 SCANNER IDX TREND NAIK x MA50 - {now} WIB\nDitemukan {len(hasil)} saham:\n\n" + "\n".join(hasil[:30])
    pesan += f"\n\nScreener: Close>MA50, MA20>MA50, MA50 Naik, Jarak -3% s/d +3%"
else:
    pesan = f"⚠️ SCAN {now} WIB\nTidak ada saham uptrend yang dekat MA50 hari ini.\nMarket lagi jauh di atas / di bawah MA50. HOLD CASH."

print(pesan)
r = requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", data={"chat_id": CHAT_ID, "text": pesan})
print(f"TELEGRAM: {r.text}")
