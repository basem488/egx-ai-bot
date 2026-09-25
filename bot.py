import os
import time
import requests

from indicators import add
from data_source import (
    discover_symbols,
    fetch_history,
    fetch_single_history,
)
import config


# =========================
# ANALYZE STOCK
# =========================

def analyze(sym, raw):

    d = add(raw, config).dropna(
        subset=[
            "EMA20",
            "RSI",
            "ATR",
            "VOL_RATIO",
            "SUP",
            "LOW10",
            "HIGH5",
            "EMA20_SLOPE5",
            "REBOUND10",
            "DRAWDOWN20",
            "RSI_PREV",
            "MACD_HIST",
            "MACD_HIST_PREV",
        ]
    )

    if len(d) < 10:
        return None

    x = d.iloc[-1]

    close = float(x.Close)
    atr = float(x.ATR)
    sup = float(x.SUP)
    low = float(x.LOW10)
    dd = float(x.DRAWDOWN20)
    reb = float(x.REBOUND10)

    correction = dd <= -config.MIN_CORRECTION_PCT
    recent = reb >= config.MIN_REBOUND_PCT
    above = close > float(x.EMA20)
    slope = float(x.EMA20_SLOPE5) >= config.MIN_EMA20_SLOPE

    rsi = (
        float(x.RSI) >= config.MIN_RSI
        and float(x.RSI) > float(x.RSI_PREV)
    )

    macd = (
        float(x.MACD_HIST)
        > float(x.MACD_HIST_PREV)
    )

    vol = (
        float(x.VOL_RATIO)
        >= config.MIN_VOLUME_RATIO
    )

    breakout = close > float(x.HIGH5)

    near = (
        close
        <= sup * config.SUPPORT_ZONE_MULTIPLIER
    )

    score = 0
    reasons = []

    checks = [
        (
            correction,
            20,
            f"تصحيح {abs(dd) * 100:.1f}% من قمة 20 يوم",
        ),
        (
            recent,
            15,
            f"ارتداد {reb * 100:.1f}% من قاع 10 أيام",
        ),
        (
            above,
            15,
            "السعر استعاد EMA20",
        ),
        (
            slope,
            10,
            "ميل EMA20 بدأ يتحسن",
        ),
        (
            rsi,
            10,
            f"RSI يتحسن ({float(x.RSI):.1f})",
        ),
        (
            macd,
            10,
            "MACD Histogram يتحسن",
        ),
        (
            vol,
            10,
            "حجم تداول مؤكد",
        ),
        (
            breakout,
            10,
            "اختراق قمة آخر 5 أيام",
        ),
    ]

    for ok, pts, msg in checks:
        if ok:
            score += pts
            reasons.append(msg)

    if not breakout and near:
        score += 5
        reasons.append("قريب من منطقة دعم")

    reversal = (
        correction
        and recent
        and above
        and rsi
        and macd
        and score >= config.REVERSAL_SCORE
    )

    if breakout:
        lo = close * 0.995
        hi = close * 1.01
    else:
        lo = max(
            float(x.EMA20),
            close - 0.5 * atr,
        )
        hi = close * 1.005

    stop = min(
        low - 0.25 * atr,
        sup * 0.98,
        lo - config.STOP_ATR_MULTIPLIER * atr,
    )

    risk = max(
        lo - stop,
        0.01,
    )

    return {
        "symbol": sym,
        "date": str(x.Date.date()),
        "close": round(close, 2),
        "score": score,
        "signal": (
            "REVERSAL"
            if reversal
            else (
                "WATCH"
                if score >= 70
                else "NEUTRAL"
            )
        ),
        "entry_low": round(lo, 2),
        "entry_high": round(hi, 2),
        "stop": round(stop, 2),
        "target1": round(
            lo + 1.5 * risk,
            2,
        ),
        "target2": round(
            lo + 2.5 * risk,
            2,
        ),
        "rsi": round(
            float(x.RSI),
            2,
        ),
        "vol_ratio": round(
            float(x.VOL_RATIO),
            2,
        ),
        "correction_pct": round(
            abs(dd) * 100,
            2,
        ),
        "rebound_pct": round(
            reb * 100,
            2,
        ),
        "reasons": reasons,
    }


# =========================
# TELEGRAM
# =========================

def telegram(method, **data):

    token = os.environ["TELEGRAM_BOT_TOKEN"]

    url = (
        f"https://api.telegram.org/"
        f"bot{token}/{method}"
    )

    return requests.post(
        url,
        data=data,
        timeout=30,
    ).json()


def send_message(chat_id, text):

    telegram(
        "sendMessage",
        chat_id=chat_id,
        text=text,
        parse_mode="HTML",
    )


# =========================
# FORMAT ANALYSIS
# =========================

def format_analysis(x):

    signal_text = {
        "REVERSAL": "🔄 REVERSAL",
        "WATCH": "👀 WATCH",
        "NEUTRAL": "⚪ NEUTRAL",
    }.get(
        x["signal"],
        x["signal"],
    )

    reasons = x["reasons"]

    if reasons:
        reasons_text = "\n".join(
            f"• {r}"
            for r in reasons
        )
    else:
        reasons_text = "• لا توجد إشارات مؤكدة حاليًا"

    return (
        f"<b>📊 تحليل {x['symbol']}</b>\n"
        f"التاريخ: {x['date']}\n\n"

        f"<b>السعر:</b> {x['close']}\n"
        f"<b>الإشارة:</b> {signal_text}\n"
        f"<b>Score:</b> {x['score']}/100\n\n"

        f"<b>🎯 منطقة الدخول:</b>\n"
        f"{x['entry_low']} - {x['entry_high']}\n\n"

        f"<b>🛑 وقف الخسارة:</b> {x['stop']}\n\n"

        f"<b>🎯 الأهداف:</b>\n"
        f"T1: {x['target1']}\n"
        f"T2: {x['target2']}\n\n"

        f"<b>المؤشرات:</b>\n"
        f"RSI: {x['rsi']}\n"
        f"Volume: {x['vol_ratio']}x\n"
        f"التصحيح: {x['correction_pct']}%\n"
        f"الارتداد: {x['rebound_pct']}%\n\n"

        f"<b>أسباب الإشارة:</b>\n"
        f"{reasons_text}\n\n"

        f"⚠️ التحليل آلي وليس توصية استثمارية."
    )


# =========================
# DIRECT STOCK ANALYSIS
# =========================

def analyze_single_stock(symbol):

    symbol =
