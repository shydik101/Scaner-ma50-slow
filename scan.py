def analyze(df, ticker):
    if len(df) < 35: return None
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    df = df.dropna()
    if len(df) < 30: return None

    close=df['Close']; high=df['High']; low=df['Low']; vol=df['Volume']
    ma20=close.rolling(20).mean(); vol_ma20=vol.rolling(20).mean(); atr=(high-low).rolling(14).mean(); high20=high.rolling(20).max()

    c=last_float(close); m=last_float(ma20); v=last_float(vol); vm=last_float(vol_ma20); a=last_float(atr); h20=last_float(high20)
    if c==0 or m==0 or vm==0 or a==0: return None

    try: m5=float(ma20.dropna().iloc[-6])
    except: m5=m
    slope=(m-m5)/m5*100 if m5!=0 else 0
    v_ratio = v/vm if vm>0 else 0

    # FIX SL: jangan pakai MA20 kalau terlalu mepet, pakai ATR minimal 2%
    sl_ma = m
    sl_atr = c - a*1.8
    sl = min(sl_ma, sl_atr) # ambil yang paling bawah
    # paksa minimal 2% di bawah harga biar gak -0.5%
    min_sl = c * 0.97
    if sl > min_sl:
        sl = min_sl

    if c - sl < 1: return None

    tp1 = h20
    tp2 = tp1 * 1.06
    rr = (tp1 - c)/(c - sl) if c-sl>0 else 0

    score=50
    if c>m: score+=15
    if slope>0: score+=10
    if v_ratio>1.5: score+=15
    elif v_ratio>1.0: score+=5
    if c>=h20*0.98: score+=10
    if rr>=1.4: score+=5

    if score>=78: act="STRONG BREAKOUT - BUY CICIL"; star="⭐⭐⭐"
    elif score>=71: act="BREAKOUT - BUY"; star="⭐⭐"
    elif score>=60: act="WAIT PULLBACK"; star="⭐⭐"
    else: act="SKIP"; star="⭐"

    # FIX LOT BIAR GAK MINUS
    risk_rp = PORTO * RISK_PER_TRADE
    risk_per_share = abs(c - sl)
    lot = int(risk_rp / (risk_per_share * 100))
    lot = max(1, min(lot, 500)) # batasi max 500 lot biar gak 1666 lot
    money = risk_per_share * 100 * lot

    entry_low = int(c*0.995)
    entry_high = int(c*1.005)

    return {
        "ticker":ticker, "score":int(score), "c":c, "m":m, "sl":sl, "tp1":tp1, "tp2":tp2, "rr":rr,
        "v_ratio":v_ratio, "vol_str":f"{v_ratio:.1f}x {'VALID' if v_ratio>=1.2 else 'TIPIS'}",
        "slope":slope, "trend_str":f"{slope:+.1f}%/5hr", "action":act, "star":star,
        "lot":lot, "money_str":f"max Rp {money/1_000_000:.1f}jt (~{lot} lot)", "entry":f"{entry_low}-{entry_high}",
        "days_up":0, "close_near_high":c/h20 if h20>0 else 0
    }
