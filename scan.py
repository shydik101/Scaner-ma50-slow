import yfinance as yf
import requests, os, time, numpy as np
from datetime import datetime

TOKEN = os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
MODAL = 1500000  # Rp 1.5jt

def rsi(s, p=14):
    d=s.diff(); g=d.where(d>0,0).rolling(p).mean(); l=-d.where(d<0,0).rolling(p).mean()
    rs=g/l; return 100-(100/(1+rs))

def load_tickers():
    try:
        with open("daytrade-observe-tickers.txt") as f:
            t=[x.strip() for x in f if x.strip() and not x.startswith("#")]
            if t: return t
    except: pass
    return ["BBCA.JK","BBRI.JK","BMRI.JK","BBNI.JK","TLKM.JK","ASII.JK","UNTR.JK","CUAN.JK","GOTO.JK","BREN.JK"]

def scan_one(ticker):
    try:
        t=ticker.upper().strip()
        if not t.endswith(".JK"): t+=".JK"
        df = yf.download(t, period="1y", interval="1d", progress=False, auto_adjust=True)
        if len(df)<100: return None
        
        c=float(df['Close'].iloc[-1]); o=float(df['Open'].iloc[-1]); h=float(df['High'].iloc[-1]); l=float(df['Low'].iloc[-1])
        vol=float(df['Volume'].iloc[-1]); vol_avg=float(df['Volume'].rolling(20).mean().iloc[-1])
        vol_r=vol/vol_avg if vol_avg>0 else 0

        ma20=float(df['Close'].rolling(20).mean().iloc[-1]); ma50=float(df['Close'].rolling(50).mean().iloc[-1])
        ema9=float(df['Close'].ewm(span=9).mean().iloc[-1]); ema21=float(df['Close'].ewm(span=21).mean().iloc[-1])
        rsi14=float(rsi(df['Close']).iloc[-1])

        ema12=df['Close'].ewm(span=12).mean(); ema26=df['Close'].ewm(span=26).mean()
        macd=ema12-ema26; signal=macd.ewm(span=9).mean()
        macd_val=float(macd.iloc[-1]); signal_val=float(signal.iloc[-1])

        std20=float(df['Close'].rolling(20).std().iloc[-1])
        bb_up=ma20+2*std20; bb_low=ma20-2*std20
        bb_pos=(c-bb_low)/(bb_up-bb_low)*100 if bb_up!=bb_low else 50

        tr=np.maximum(df['High']-df['Low'], np.maximum(abs(df['High']-df['Close'].shift(1)), abs(df['Low']-df['Close'].shift(1))))
        atr=float(tr.rolling(14).mean().iloc[-1])

        # ADX + MFI
        plus_dm=df['High'].diff(); minus_dm=-df['Low'].diff()
        plus_dm[plus_dm<0]=0; minus_dm[minus_dm<0]=0
        atr2=tr.rolling(14).mean()
        plus_di=100*(plus_dm.ewm(alpha=1/14).mean()/atr2); minus_di=100*(minus_dm.ewm(alpha=1/14).mean()/atr2)
        dx=100*abs(plus_di-minus_di)/(plus_di+minus_di)
        adx_val=float(dx.rolling(14).mean().iloc[-1])

        tp_=(df['High']+df['Low']+df['Close'])/3; rmf=tp_*df['Volume']
        pos_flow=rmf.where(tp_>tp_.shift(1),0).rolling(14).sum(); neg_flow=rmf.where(tp_<tp_.shift(1),0).rolling(14).sum()
        mfr=pos_flow/neg_flow; mfi=100-(100/(1+mfr)); mfi_val=float(mfi.iloc[-1])

        # Trend MA20 5hr
        ma20_5ago=float(df['Close'].rolling(20).mean().shift(5).iloc[-1])
        trend_ma20 = (ma20/ma20_5ago-1)*100 if ma20_5ago else 0

        score=0; notes=[]
        if ema9>ema21 and ma20>ma50 and c>ma20: score+=25; notes.append("Trend 4 lapis OK")
        elif c>ma20 and ema9>ema21: score+=15
        else: score+=5

        if vol_r>=2.5: score+=25; v_status=f"{vol_r:.1f}x BANDAR"; notes.append(f"Vol {v_status}")
        elif vol_r>=1.5: score+=20; v_status=f"{vol_r:.1f}x VALID"
        elif vol_r>=1.2: score+=10; v_status=f"{vol_r:.1f}x VALID"
        else: v_status=f"{vol_r:.1f}x"; score+=5

        if 50<=rsi14<=70: score+=15
        elif rsi14>80: score-=10

        if macd_val>signal_val and macd_val>0: score+=15
        elif macd_val>signal_val: score+=8

        if adx_val>=25: score+=10; notes.append(f"ADX {adx_val:.0f} kuat")
        if 55<=bb_pos<=90 and c>o: score+=10

        if adx_val<15: return None
        if rsi14>82: return None

        if score>=88: bintang="⭐⭐⭐⭐⭐"; status="GOD MODE - ALL IN"
        elif score>=80: bintang="⭐⭐⭐⭐"; status="STRONG BREAKOUT - BUY CICIL"
        elif score>=70: bintang="⭐⭐⭐"; status="BREAKOUT - BUY TIPIS"
        elif score>=50: bintang="⭐⭐"; status="WAIT PULLBACK"
        else: bintang="⭐"; status="PANTAU"

        entry_low=int(c*0.995); entry_high=int(c*1.005)
        sl=int(c-atr*1.5); sl_pct=(sl-c)/c*100
        tp1=int(c+atr*2.2); tp2=int(c+atr*3.8)
        rr=(tp1-c)/(c-sl) if c!=sl else 0
        
        # Money Management
        lot = int(MODAL / c / 100) if c>0 else 0

        return {
            "ticker":t.replace(".JK",""), "close":int(c), "ma20":int(ma20), "vol":vol_r, "v_status":v_status,
            "trend":round(trend_ma20,1), "rsi":int(rsi14), "adx":int(adx_val), "mfi":int(mfi_val),
            "score":score, "bintang":bintang, "status":status,
            "entry_low":entry_low, "entry_high":entry_high, "sl":sl, "sl_pct":round(sl_pct,1),
            "tp1":tp1, "tp2":tp2, "rr":round(rr,1), "lot":lot, "notes":", ".join(notes[:3])
        }
    except Exception as e:
        print(f"Err {ticker}: {e}"); return None

tickers=load_tickers(); hasil=[]
for tk in tickers[:81]:
    h=scan_one(tk)
    if h: hasil.append(h)
    time.sleep(0.2)

hasil=sorted(hasil, key=lambda x: x['score'], reverse=True)
now=datetime.now().strftime('%d %b %H:%M')

if not hasil:
    pesan=f"🔥 SCAN MA50 SELOW - {now} WIB\n{len(tickers)} saham, tidak ada yang lolos filter."
else:
    pesan=f"🔥 SCAN MA50 SELOW - {now} WIB | {len(tickers)} saham\nTop {len(hasil)} akurat:\n\n"
    for i,h in enumerate(hasil[:10],1):
        pesan+=f"#{i} {h['ticker']}.JK {h['score']} - {h['status']} {h['bintang']}\n"
        pesan+=f"Harga:{h['close']} | MA20:{h['ma20']} | Vol:{h['vol']:.1f}x {h['v_status'].split('x')[-1].strip()} | Trend MA20:{h['trend']:+.1f}%/5hr\n"
        pesan+=f"RSI:{h['rsi']} | ADX:{h['adx']} | MFI:{h['mfi']} | MACD:{'BULL' if h['score']>70 else 'WAIT'}\n"
        pesan+=f"Entry:{h['entry_low']}-{h['entry_high']} | SL:{h['sl']} ({h['sl_pct']}%) | TP1:{h['tp1']} TP2:{h['tp2']}\n"
        pesan+=f"R:R 1:{h['rr']} | Money: max Rp 1.5jt (~{h['lot']} lot)\n"
        pesan+=f"Note: {h['notes']}, close dekat high 20hr\n\n"

print(pesan)
if TOKEN and CHAT_ID:
    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", data={"chat_id":CHAT_ID,"text":pesan})
