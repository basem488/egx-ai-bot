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

    symbol = symbol.strip().upper()

    if symbol.endswith(".CA"):
        symbol = symbol[:-3]

    if not symbol:
        return None

    print(
        f"Analyzing requested stock: {symbol}"
    )

    raw = fetch_single_history(symbol)

    if raw is None or raw.empty:
        return None

    result = analyze(
        symbol,
        raw,
    )

    return result


# =========================
# FULL EGX SCAN
# =========================

def scan_egx():

    print("Starting EGX scan...")

    symbols = discover_symbols()

    data = fetch_history(symbols)

    results = []

    for symbol, raw in data.items():

        try:

            result = analyze(
                symbol,
                raw,
            )

            if result is not None:
                results.append(result)

        except Exception as e:

            print(
                f"Analysis failed for "
                f"{symbol}: {e}"
            )

    results.sort(
        key=lambda x: x["score"],
        reverse=True,
    )

    return results


# =========================
# FORMAT EGX SCAN
# =========================

def format_scan(results):

    if not results:

        return (
            "❌ لم يتم العثور على بيانات "
            "صالحة للتحليل."
        )

    strong = [
        x for x in results
        if x["score"] >= 70
    ]

    if not strong:

        return (
            "📊 <b>فحص EGX</b>\n\n"
            "لم تظهر حاليًا أسهم بدرجة "
            "70 أو أكثر.\n\n"
            f"تم فحص {len(results)} سهم.\n\n"
            "⚠️ التحليل آلي وليس توصية استثمارية."
        )

    lines = [
        "📊 <b>نتائج فحص EGX</b>",
        "",
        f"تم العثور على {len(strong)} سهم "
        f"بـ Score ≥ 70:",
        "",
    ]

    for x in strong[:20]:

        signal = {
            "REVERSAL": "🔄",
            "WATCH": "👀",
            "NEUTRAL": "⚪",
        }.get(
            x["signal"],
            "⚪",
        )

        lines.append(
            f"{signal} <b>{x['symbol']}</b> "
            f"— Score {x['score']}/100"
        )

        lines.append(
            f"السعر: {x['close']} | "
            f"RSI: {x['rsi']}"
        )

        lines.append("")

    lines.append(
        "استخدم <b>/egx SYMBOL</b> "
        "لتحليل سهم محدد بالتفصيل."
    )

    lines.append("")
    lines.append(
        "⚠️ التحليل آلي وليس توصية استثمارية."
    )

    return "\n".join(lines)


# =========================
# COMMAND HANDLER
# =========================

def handle_message(message):

    if not message:
        return

    chat = message.get("chat", {})
    chat_id = chat.get("id")

    if chat_id is None:
        return

    text = message.get("text", "")

    if not text:
        return

    text = text.strip()

    if not text:
        return

    # =========================
    # START
    # =========================

    if text.startswith("/start"):

        send_message(
            chat_id,
            (
                "🤖 <b>EGX AI Bot</b>\n\n"
                "استخدم:\n"
                "<b>/egx COMI</b>\n"
                "<b>/egx TMGH</b>\n\n"
                "لتحليل سهم محدد مباشرة.\n\n"
                "أو استخدم:\n"
                "<b>/egx</b>\n\n"
                "لفحص أسهم EGX."
            ),
        )

        return

    # =========================
    # EGX COMMAND
    # =========================

    if text.lower().startswith("/egx"):

        parts = text.split()

        # /egx فقط
        if len(parts) == 1:

            send_message(
                chat_id,
                "⏳ جاري فحص أسهم EGX، انتظر...",
            )

            try:

                results = scan_egx()

                response = format_scan(
                    results
                )

                send_message(
                    chat_id,
                    response,
                )

            except Exception as e:

                print(
                    f"EGX scan error: {e}"
                )

                send_message(
                    chat_id,
                    "❌ حصل خطأ أثناء فحص EGX.",
                )

            return

        # /egx SYMBOL
        symbol = parts[1].upper()

        send_message(
            chat_id,
            f"⏳ جاري تحليل {symbol}...",
        )

        try:

            result = analyze_single_stock(
                symbol
            )

            if result is None:

                send_message(
                    chat_id,
                    (
                        f"❌ لم أستطع الحصول على "
                        f"بيانات كافية للسهم "
                        f"<b>{symbol}</b>."
                    ),
                )

                return

            send_message(
                chat_id,
                format_analysis(result),
            )

        except Exception as e:

            print(
                f"Single stock error "
                f"{symbol}: {e}"
            )

            send_message(
                chat_id,
                (
                    f"❌ حصل خطأ أثناء تحليل "
                    f"<b>{symbol}</b>."
                ),
            )

        return

    # =========================
    # DIRECT SYMBOL
    # =========================

    # لو المستخدم كتب COMI مباشرة
    if (
        len(text.split()) == 1
        and text.replace(".", "").isalnum()
        and len(text) <= 10
        and not text.startswith("/")
    ):

        symbol = text.upper()

        send_message(
            chat_id,
            f"⏳ جاري تحليل {symbol}...",
        )

        try:

            result = analyze_single_stock(
                symbol
            )

            if result is None:

                send_message(
                    chat_id,
                    (
                        f"❌ لم أستطع الحصول على "
                        f"بيانات كافية للسهم "
                        f"<b>{symbol}</b>."
                    ),
                )

                return

            send_message(
                chat_id,
                format_analysis(result),
            )

        except Exception as e:

            print(
                f"Direct symbol error "
                f"{symbol}: {e}"
            )

            send_message(
                chat_id,
                (
                    f"❌ حصل خطأ أثناء تحليل "
                    f"<b>{symbol}</b>."
                ),
            )

        return


# =========================
# TELEGRAM POLLING
# =========================

def run_bot():

    print("Bot started.")

    offset = None

    while True:

        try:

            params = {
                "timeout": 25,
            }

            if offset is not None:
                params["offset"] = offset

            token = os.environ[
                "TELEGRAM_BOT_TOKEN"
            ]

            response = requests.get(
                f"https://api.telegram.org/"
                f"bot{token}/getUpdates",
                params=params,
                timeout=35,
            )

            data = response.json()

            if not data.get("ok"):

                print(
                    "Telegram API error:",
                    data,
                )

                time.sleep(5)
                continue

            updates = data.get(
                "result",
                [],
            )

            for update in updates:

                offset = (
                    update["update_id"] + 1
                )

                try:

                    message = update.get(
                        "message"
                    )

                    if message:
                        handle_message(
                            message
                        )

                except Exception as e:

                    print(
                        f"Message handling error: "
                        f"{e}"
                    )

        except requests.exceptions.Timeout:

            print(
                "Telegram timeout, retrying..."
            )

            continue

        except Exception as e:

            print(
                f"Polling error: {e}"
            )

            time.sleep(5)


# =========================
# MAIN
# =========================

if __name__ == "__main__":
    run_bot()
