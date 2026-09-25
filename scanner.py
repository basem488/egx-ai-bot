import json
import os
from pathlib import Path
from datetime import datetime
import pandas as pd

import config
from indicators import add
from data_source import discover_symbols, fetch_history, BANK_SYMBOLS

SUBS = Path("subscriptions.json")
CACHE = {"at": None, "signals": [], "loaded": 0, "universe": 0}
CACHE_TTL = int(os.getenv("SCAN_CACHE_SECONDS", "900"))


def analyze(sym, raw):
    d = add(raw, config)
    cols = ["EMA20", "EMA50", "EMA200", "RSI", "ATR", "VOL_RATIO", "RES", "SUP",
            "PEAK20", "LOW10", "HIGH5", "EMA20_SLOPE5", "REBOUND10", "DRAWDOWN20",
            "RSI_PREV", "MACD_HIST", "MACD_HIST_PREV"]
    d = d.dropna(subset=cols)
    if len(d) < 10:
        raise ValueError("insufficient indicator rows")

    x = d.iloc[-1]
    p = d.iloc[-2]
    close = float(x.Close)
    atr = float(x.ATR)
    sup = float(x.SUP)
    recent_low = float(x.LOW10)
    drawdown = float(x.DRAWDOWN20)  # negative = below recent 20d peak
    rebound = float(x.REBOUND10)

    # The goal is NOT to catch a falling knife. We look for a meaningful
    # correction followed by an early, confirmed recovery.
    correction = drawdown <= -config.MIN_CORRECTION_PCT
    recent_rebound = rebound >= config.MIN_REBOUND_PCT
    above_ema20 = close > float(x.EMA20)
    ema_turning_up = float(x.EMA20_SLOPE5) >= config.MIN_EMA20_SLOPE
    rsi_reclaim = float(x.RSI) >= config.MIN_RSI and float(x.RSI) > float(x.RSI_PREV)
    macd_improving = float(x.MACD_HIST) > float(x.MACD_HIST_PREV)
    volume_confirm = float(x.VOL_RATIO) >= config.MIN_VOLUME_RATIO
    breakout_5d = close > float(x.HIGH5)
    near_support = close <= sup * config.SUPPORT_ZONE_MULTIPLIER

    score = 0
    reasons = []
    if correction:
        score += 20
        reasons.append(f"تصحيح {abs(drawdown)*100:.1f}% من قمة 20 يوم")
    if recent_rebound:
        score += 15
        reasons.append(f"ارتداد {rebound*100:.1f}% من قاع 10 أيام")
    if above_ema20:
        score += 15
        reasons.append("السعر استعاد EMA20")
    if ema_turning_up:
        score += 10
        reasons.append("ميل EMA20 بدأ يتحسن")
    if rsi_reclaim:
        score += 10
        reasons.append(f"RSI يتحسن ({float(x.RSI):.1f})")
    if macd_improving:
        score += 10
        reasons.append("MACD Histogram يتحسن")
    if volume_confirm:
        score += 10
        reasons.append("حجم تداول مؤكد")
    if breakout_5d:
        score += 10
        reasons.append("اختراق قمة آخر 5 أيام")
    elif near_support:
        score += 5
        reasons.append("قريب من منطقة دعم")

    # Only call it a completed-correction reversal when the core conditions
    # are present. This keeps alerts focused on early reversals rather than
    # ordinary uptrends.
    core = correction and recent_rebound and above_ema20 and rsi_reclaim and macd_improving
    reversal = core and score >= config.REVERSAL_SCORE

    if breakout_5d:
        lo, hi = close * 0.995, close * 1.01
    elif above_ema20:
        lo, hi = max(float(x.EMA20), close - 0.5 * atr), close * 1.005
    else:
        lo, hi = close * 0.985, close * 0.995

    # Stop below the recent reversal low/support, with ATR protection.
    stop = min(recent_low - 0.25 * atr, sup * 0.98, lo - config.STOP_ATR_MULTIPLIER * atr)
    risk = max(lo - stop, 0.01)

    signal = "REVERSAL" if reversal else ("WATCH" if score >= config.WATCH_SCORE else "NEUTRAL")
    return {
        "symbol": sym,
        "date": str(pd.Timestamp(x.Date).date()),
        "close": round(close, 2),
        "score": int(max(0, min(100, score))),
        "signal": signal,
        "entry_low": round(lo, 2),
        "entry_high": round(hi, 2),
        "stop": round(stop, 2),
        "target1": round(lo + config.TARGET1_RR * risk, 2),
        "target2": round(lo + config.TARGET2_RR * risk, 2),
        "rsi": round(float(x.RSI), 2),
        "vol_ratio": round(float(x.VOL_RATIO), 2),
        "correction_pct": round(abs(drawdown) * 100, 2),
        "rebound_pct": round(rebound * 100, 2),
        "reasons": reasons,
    }


def _refresh():
    symbols = discover_symbols()
    data = fetch_history(symbols, period=os.getenv("HISTORY_PERIOD", "3y"))
    out = []
    for s, d in data.items():
        if s in BANK_SYMBOLS:
            continue
        try:
            out.append(analyze(s, d))
        except Exception as e:
            print(s, e)
    # Reversals first, then score.
    out.sort(key=lambda x: (x["signal"] == "REVERSAL", x["score"]), reverse=True)
    CACHE.update({"at": datetime.utcnow(), "signals": out, "loaded": len(data), "universe": len(symbols)})
    Path("reports").mkdir(exist_ok=True)
    Path("reports/signals.json").write_text(json.dumps(out, ensure_ascii=False, indent=2))

    # Push only the high-confidence reversal alerts.
    for x in out:
        if x["signal"] == "REVERSAL":
            send_push({
                "title": f'EGX {x["symbol"]} — REVERSAL',
                "body": f'تصحيح انتهى مبدئيًا | دخول {x["entry_low"]}-{x["entry_high"]} | وقف {x["stop"]} | T1 {x["target1"]} | T2 {x["target2"]}'
            })
    return out


def load_signals(force=False):
    now = datetime.utcnow()
    if not force and CACHE["at"] and (now - CACHE["at"]).total_seconds() < CACHE_TTL:
        return CACHE["signals"]
    return _refresh()


def status():
    return {
        "cached_at": CACHE["at"].isoformat() if CACHE["at"] else None,
        "loaded": CACHE["loaded"],
        "universe": CACHE["universe"],
        "cache_seconds": CACHE_TTL,
    }


def send_push(payload):
    if not SUBS.exists():
        return
    try:
        from pywebpush import webpush
        subs = json.loads(SUBS.read_text())
        private = os.getenv("VAPID_PRIVATE_KEY")
        email = os.getenv("VAPID_CLAIMS_EMAIL", "mailto:admin@example.com")
        if not private:
            return
        alive = []
        for sub in subs:
            try:
                webpush(subscription_info=sub, data=json.dumps(payload),
                        vapid_private_key=private, vapid_claims={"sub": email})
                alive.append(sub)
            except Exception as exc:
                print("push error:", exc)
        SUBS.write_text(json.dumps(alive, ensure_ascii=False, indent=2))
    except Exception as e:
        print("push setup error:", e)


if __name__ == "__main__":
    print(json.dumps(_refresh(), ensure_ascii=False, indent=2))
