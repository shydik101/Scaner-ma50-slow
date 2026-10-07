import os, requests, pandas as pd, time, json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

TICKER_FILE = os.getenv("TICKER_FILE", "tickers-watchlist.txt")
BATCH_LABEL = os.getenv("BATCH_LABEL", "WATCHLIST")
PROXY_URL = "https://yahoo-proxy.rizalmawardi766.workers.dev"
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
WIB = timezone(timedelta(hours=7))

def send(msg):
    if TOKEN and CHAT_ID:
        try: requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=20)
        except: pass
    print(msg)

def get_df(ticker):
    for _ in range(3):
        try:
            r = requests.get(f"{PROXY_URL}/?ticker={ticker}", timeout=15).json()
            q = r["chart"]["result"][0]["indicators"]["quote"][0]
            df = pd.DataFrame({
                "close": q["close"], "vol": q["volume"],
                "high": q.get("high", q["close"]), "low": q.get("low", q["close"]),
                "open": q.get("open", q["close"])
            }).dropna()
            if len(df) >= 60: return df, 1
        except: time.sleep(1); continue
    return None, 3

def calc_LPM(df):
    try:
        last = df.iloc[-1]
        range_hl = last["high"]-last["low"] if last["high"]!=last["low"] else 1
        close_pos = (last["close"]-last["low"])/range_hl*100
        akum_candle = (df.tail(20)["close"] > df.tail(20)["open"]).sum() / 20 * 100
        ma_score = 50 if last["close"] > last["MA20"] else -50
        lpm = (close_pos * 0.4 + akum_candle * 0.3 + (ma_score+50) * 0.3) - 50
        return lpm
    except: return 0

def calc_INTENSITY(df):
    try:
        vol_avg_60 = df["vol"].rolling(60).mean().iloc[-1]
        vol_std_60 = df["vol"].rolling(60).std().iloc[-1]
        vol_now = df["vol"].iloc[-1]
        z = (vol_now - vol_avg_60) / vol_std_60 if vol_std_60 and vol_std_60>0 else 0
        ratio = vol_now / vol_avg_60 if vol_avg_60>0 else 1
        return z, ratio
    except: return 0, 1

def calc_ROTATION(df):
    try:
        vol_20_sum = df["vol"].tail(20).sum()
        vol_60_avg = df["vol"].rolling(60).mean().iloc[-1] * 20
        return vol_20_sum / vol_60_avg if vol_60_avg and vol_60_avg>0 else 1
    except: return 1

def analyze_watchlist(ticker):
    df, retry = get_df(ticker)
    if df is None: return None
    df["MA20"]=df["close"].rolling(20).mean(); df["MA50"]=df["close"].rolling(50).mean(); df["MA200"]=df["close"].rolling(200).mean()
    df["vol_avg"]=df["vol"].rolling(20).mean(); df["vol_ratio"]=df["vol"]/df["vol_avg"]
    df["ATR"]=df["close"].diff().abs().rolling(14).mean()
    delta=df["close"].diff(); gain=delta.where(delta>0,0).rolling(14).mean(); loss=-delta.where(delta<0,0).rolling(14).mean()
    df["RSI"]=100-(100/(1+gain/loss)); df["ADX"]=(df["close"].diff().abs().rolling(14).mean()/df["close"]*1000).clip(10,50)
    last=df.iloc[-1]
    c,h,l,o = last["close"], last["high"], last["low"], last["open"]
    ma20, ma50, ma200 = last["MA20"], last["MA50"], last["MA200"]
    atr, vol, rsi, adx = last["ATR"], last["vol_ratio"], last["RSI"], int(last["ADX"])
    if pd.isna(ma20) or pd.isna(ma50): return None

    dist20 = (c-ma20)/ma20*100; dist50 = (c-ma50)/ma50*100; dist200 = (c-ma200)/ma200*100 if not pd.isna(ma200) else 0
    pivot = (h+l+c)/3; s1 = 2*pivot - h; s2 = pivot - (h - l); r1 = 2*pivot - l; r2 = pivot + (h - l)
    range_hl = h-l if h!=l else 1; close_pos = (c-l)/range_hl*100; upper_wick = (h-max(c,o))/range_hl*100

    score = 0
    if c > ma20: score+=20
    if ma20 > ma50: score+=15
    if 35 <= rsi <= 65: score+=15
    if vol >= 1.2: score+=10
    if adx > 20: score+=10

    if c > ma20 and c > ma50 and c > ma200: label, stars = "UPTREND KUAT", 4
    elif c > ma20 and ma20 > ma50: label, stars = "UPTREND", 3
    elif c > ma20: label, stars = "NEAR BREAKOUT", 2
    elif abs(dist50) <= 4: label, stars = "NEMPEL MA50", 1
    else: label, stars = "DOWNTREND / AKUMULASI", 0

    if close_pos >=80 and vol>=1.8 and upper_wick<20: bandar="AKUMULASI"
    elif upper_wick>40 and vol>=1.8: bandar="DISTRIBUSI"
    else: bandar="NETRAL"

    sl = c - max(c*0.04, atr*1.5); tp1 = c + atr*1.5; tp2 = c + atr*2.5; rr = (tp1-c)/(c-sl) if c>sl else 0

    if stars >=3 and vol>=1.5 and rsi>=50: keputusan = "GAS CICIL / BUY"
    elif stars ==2 and vol>=1.5: keputusan = "CICIL 30% BAWAH"
    elif stars <=1 and rsi <40: keputusan = "TUNGGU PANTULAN"
    else: keputusan = "WATCH"

    # Bandar Matrix
    lpm = calc_LPM(df); z_int, ratio_int = calc_INTENSITY(df); rot = calc_ROTATION(df)

    if lpm > 20: lpm_txt = f"Akumulasi +{lpm:.0f}"
    elif lpm < -20: lpm_txt = f"Distribusi {lpm:.0f}"
    else: lpm_txt = f"Netral {lpm:.0f}"

    if z_int > 3: int_txt = f"Sangat Aktif {ratio_int:.1f}x"
    elif z_int > 2: int_txt = f"Mulai Aktif {ratio_int:.1f}x"
    elif z_int > 1: int_txt = f"Agak Aktif {ratio_int:.1f}x"
    else: int_txt = f"Sepi {ratio_int:.1f}x"

    if rot > 2.5: rot_txt = f"Ekstra Rame {rot:.1f}x"
    elif rot > 1.5: rot_txt = f"Rame {rot:.1f}x"
    elif rot > 1.2: rot_txt = f"Agak Rame {rot:.1f}x"
    else: rot_txt = f"Sepi {rot:.1f}x"

    if lpm > 20 and z_int > 2 and 1.2 <= rot <= 2.5: konf = "TERKONFIRMASI - 3 Sinyal Kompak"
    elif lpm < -20 and z_int > 2 and rot > 2.0: konf = "DISTRIBUSI TERKONFIRMASI"
    else: konf = "Belum Kompak"

    return {
        "ticker": ticker.replace(".JK",""), "c": c, "ma20": ma20, "ma50": ma50, "ma200": ma200,
        "dist20": dist20, "dist50": dist50, "dist200": dist200,
        "vol": vol, "rsi": rsi, "adx": adx, "atr": atr, "close_pos": close_pos,
        "s1": s1, "s2": s2, "r1": r1, "r2": r2, "pivot": pivot,
        "label": label, "stars": stars, "score": score, "bandar": bandar,
        "sl": sl, "tp1": tp1, "tp2": tp2, "rr": rr, "keputusan": keputusan,
        "lpm": lpm, "lpm_txt": lpm_txt, "z_int": z_int, "ratio_int": ratio_int,
        "int_txt": int_txt, "rot": rot, "rot_txt": rot_txt, "konf": konf
    }

def main():
    now_wib = datetime.now(WIB)
    if not os.path.exists(TICKER_FILE):
        with open(TICKER_FILE, 'w') as f: f.write("BMRI.JK\n")
    with open(TICKER_FILE) as f: tickers=[x.strip() for x in f if x.strip() and not x.startswith("#")]
    results=[]
    with ThreadPoolExecutor(max_workers=10) as ex:
        futs={ex.submit(analyze_watchlist,t):t for t in tickers}
        for fu in as_completed(futs):
            r=fu.result()
            if r: results.append(r)

    if not results:
        send(f"*WATCHLIST RADAR V11.9.1* {now_wib:%d %b %H:%M WIB}\nTidak ada data")
        return

    header=f"*WATCHLIST RADAR V11.9.1 - BANDAR MATRIX*\n{now_wib:%d %b %H:%M WIB} | {BATCH_LABEL}\n\n"
    lines=[]
    for r in results:
        star_txt="⭐"*r["stars"] if r["stars"]>0 else "—"
        # Pesan gabung profesional
        msg = (
            f"*{r['ticker']}* | {r['label']} {star_txt} | Skor {r['score']}\n"
            f"Harga {int(r['c'])} | MA20 {int(r['ma20'])} ({r['dist20']:+.1f}%) | MA50 {int(r['ma50'])} ({r['dist50']:+.1f}%) | MA200 {int(r['ma200'])} ({r['dist200']:+.1f}%)\n"
            f"Vol {r['vol']:.1f}x | Pos {r['close_pos']:.0f}% | RSI {int(r['rsi'])} | ADX {r['adx']} | ATR {r['atr']:.0f}\n"
            f"Bandar {r['bandar']} | Pivot {r['pivot']:.0f} | S1 {r['s1']:.0f} S2 {r['s2']:.0f} | R1 {r['r1']:.0f} R2 {r['r2']:.0f}\n"
            f"SL {r['sl']:.0f} | TP1 {r['tp1']:.0f} | TP2 {r['tp2']:.0f} | RR 1:{r['rr']:.2f}\n"
            f"\n"
            f"Bandar Matrix: LPM {r['lpm_txt']} | Intensity {r['int_txt']} | Rotation {r['rot_txt']}\n"
            f"Konfirmasi: *{r['konf']}* | Keputusan: *{r['keputusan']}*\n"
        )
        if r['ticker']=="BMRI":
            msg+=f"_Forecast Jumat: Base 4050-4100 | Bear <4020 -> 3950 | Bull >4130 = Near Breakout_\n"
        msg+="──────────────────"
        lines.append(msg)

    send(header + "\n".join(lines))

if __name__=="__main__": main()
