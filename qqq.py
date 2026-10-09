# QQQ RADAR SIMPLE - SCAN DETAIL TIAP PAGI
import os, requests, pandas as pd
from datetime import datetime, timedelta, timezone

PROXY_URL = "https://yahoo-proxy.rizalmawardi766.workers.dev"
WIB = timezone(timedelta(hours=7))
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send(msg):
    if TOKEN and CHAT_ID:
        try:
            requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=20)
        except Exception as e: print(e)
    print(msg)

def get_df():
    for _ in range(3):
        try:
            r = requests.get(f"{PROXY_URL}/?ticker=QQQ", timeout=15).json()
            q = r["chart"]["result"][0]["indicators"]["quote"][0]
            df = pd.DataFrame({
                "close": q["close"], "vol": q["volume"],
                "high": q.get("high", q["close"]), "low": q.get("low", q["close"]),
                "open": q.get("open", q["close"])
            }).dropna()
            if len(df) >= 100: return df
        except: pass
    return None

def main():
    df = get_df()
    if df is None:
        send("❌ QQQ gagal ambil data")
        return

    # Indikator
    df["MA20"]=df["close"].rolling(20).mean()
    df["MA50"]=df["close"].rolling(50).mean()
    df["MA200"]=df["close"].rolling(200).mean()
    df["vol_avg"]=df["vol"].rolling(20).mean()
    df["vol_ratio"]=df["vol"]/df["vol_avg"]
    df["ATR"]= (df["high"]-df["low"]).rolling(14).mean()
    delta=df["close"].diff()
    gain=delta.where(delta>0,0).rolling(14).mean()
    loss=-delta.where(delta<0,0).rolling(14).mean()
    df["RSI"]=100-(100/(1+gain/loss))
    df["MACD"]=df["close"].ewm(span=12).mean() - df["close"].ewm(span=26).mean()
    df["MACD_SIG"]=df["MACD"].ewm(span=9).mean()
    df["BB_MID"]=df["close"].rolling(20).mean()
    df["BB_STD"]=df["close"].rolling(20).std()
    df["BB_UP"]=df["BB_MID"]+2*df["BB_STD"]
    df["BB_LOW"]=df["BB_MID"]-2*df["BB_STD"]

    last=df.iloc[-1]
    c, ma20, ma50, ma200 = last["close"], last["MA20"], last["MA50"], last["MA200"]
    rsi, vol, atr = last["RSI"], last["vol_ratio"], last["ATR"]
    bb_up, bb_low = last["BB_UP"], last["BB_LOW"]
    macd, macd_sig = last["MACD"], last["MACD_SIG"]

    dist20=(c-ma20)/ma20*100
    dist50=(c-ma50)/ma50*100
    dist200=(c-ma200)/ma200*100
    pivot=(last["high"]+last["low"]+c)/3
    s1=2*pivot-last["high"]
    r1=2*pivot-last["low"]

    # Proyeksi 3 tahun
    bear=c*(1.02**3)
    base=c*(1.13**3)
    bull=c*(1.18**3)

    # Keputusan
    if c < ma200:
        keputusan = "🚨 BAHAYA - JUAL 50%"
        alasan = f"Harga ${c:.0f} di BAWAH MA200 ${ma200:.0f}. Uptrend 3 tahun patah. Institusi keluar. Ini sinyal paling bahaya di QQQ."
        aksi = f"Jual 50% sekarang, tunggu $600. SL di bawah ${ma200:.0f}"
    elif c < 700 and rsi < 40:
        keputusan = "💎 DISKON BESAR - TAMBAH"
        alasan = f"Harga diskon {dist200:.1f}% dari MA200. RSI {rsi:.0f} = murah/oversold. Boll bawah ${bb_low:.0f}. Ini level terbaik tambah."
        aksi = "Tambah di $658 (MA200) - target 2029 $1,078"
    elif c <= 732:
        keputusan = "➕ TAMBAH KECIL"
        alasan = f"Nempel MA20 ${ma20:.0f} ({dist20:+.1f}%). Vol {vol:.1f}x rame. MACD {'hijau' if macd>macd_sig else 'merah'}. Level tambah favorit."
        aksi = "Tambah 30% posisi di $727"
    elif c > ma20 and ma20 > ma50 and macd > macd_sig and 40 < rsi < 70:
        keputusan = "✅ HOLD KUAT"
        alasan = f"Tren naik sempurna: Harga > MA20 > MA50 > MA200. RSI {rsi:.0f} normal, MACD hijau. Base target 2029 ${base:.0f} (+{(base/c-1)*100:.0f}%)"
        aksi = "Diam, jangan tambah di atas $760"
    elif c > bb_up and rsi > 73:
        keputusan = "💰 TAKE PROFIT 25%"
        alasan = f"Nabrak Bollinger atas ${bb_up:.0f} + RSI {rsi:.0f} = overbought/kecapean. Biasanya turun 3-5%."
        aksi = "Jual 25% di $760+, beli lagi di $727"
    else:
        keputusan = "👀 WATCH"
        alasan = f"Harga di tengah. MA20 ${ma20:.0f}, MA200 ${ma200:.0f}. Belum murah belum mahal. Tunggu $727."
        aksi = "Tunggu pullback ke $727"

    now = datetime.now(WIB)
    msg = (
        f"*🔍 QQQ SCAN DETAIL - {now:%d %b %Y %H:%M WIB}*\n\n"
        f"*💰 HARGA*\n"
        f"QQQ: ${c:.2f} | ATR: ${atr:.1f}\n"
        f"Pivot: ${pivot:.0f} | S1: ${s1:.0f} | R1: ${r1:.0f}\n\n"
        f"*📊 INDIKATOR & ARTINYA*\n"
        f"MA20 ${ma20:.0f} ({dist20:+.1f}%) - Tren 1 bulan\n"
        f"MA50 ${ma50:.0f} ({dist50:+.1f}%) - Tren 2 bulan\n"
        f"MA200 ${ma200:.0f} ({dist200:+.1f}%) - Tren 10 bulan (paling penting)\n"
        f" -> Jika harga di atas MA200 = Bull market, aman hold\n"
        f" -> Jika di bawah = Bear, harus jual\n\n"
        f"RSI {rsi:.0f} - Ukur capek (0-100)\n"
        f" -> <40 = Murah, >70 = Mahal, ideal 40-65\n"
        f"MACD {macd:.2f} vs {macd_sig:.2f} = {'🟢 Hijau - Naik' if macd>macd_sig else '🔴 Merah - Turun'}\n"
        f"Bollinger Atas ${bb_up:.0f} Bawah ${bb_low:.0f} - Pagar harga\n"
        f"Volume {vol:.1f}x = {'Sepi' if vol<1 else 'Rame institusi >1.5x' if vol>1.5 else 'Normal'}\n\n"
        f"*🔮 PROYEKSI 3 TAHUN*\n"
        f"Bear 2%/th: ${bear:.0f} (jelek, AI gagal)\n"
        f"Base 13%/th: *${base:.0f}* (normal, paling mungkin)\n"
        f"Bull 18%/th: ${bull:.0f} (bagus, AI meledak)\n\n"
        f"*🎯 KEPUTUSAN*\n{keputusan}\n"
        f"_Alasan: {alasan}_\n\n"
        f"*✅ AKSI*\n{aksi}\n\n"
        f"*🚨 RULE KELUAR WAJIB*\n"
        f"1. Close 2 hari < MA200 ${ma200:.0f} = Jual 50%\n"
        f"2. RSI >78 + > Boll atas = Jual 25%\n"
        f"3. Yield 10Y >5% + NVDA miss = Jual semua\n"
    )
    send(msg)

if __name__ == "__main__": main()
