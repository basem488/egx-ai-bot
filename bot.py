import os
import time
import requests

from indicators import add
from data_source import discover_symbols, fetch_history, BANK_SYMBOLS
import config


def analyze(sym, raw):
    d = add(raw, config).dropna(
        subset=[
            'EMA20', 'RSI', 'ATR', 'VOL_RATIO', 'SUP',
            'LOW10', 'HIGH5', 'EMA20_SLOPE5', 'REBOUND10',
            'DRAWDOWN20', 'RSI_PREV', 'MACD_HIST', 'MACD_HIST_PREV'
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
    rsi = float(x.RSI) >= config.MIN_RSI and float(x.RSI) > float(x.RSI_PREV)
    macd = float(x.MACD_HIST) > float(x.MACD_HIST_PREV)
    vol = float(x.VOL_RATIO) >= config.MIN_VOLUME_RATIO
    breakout = close > float(x.HIGH5)
    near = close <= sup * config.SUPPORT_ZONE_MULTIPLIER

    score = 0
    reasons = []

    checks = [
        (correction, 20, f'تصحيح {abs(dd) * 100:.1f}% من قمة 20 يوم'),
        (recent, 15, f'ارتداد {reb * 100:.1f}% من قاع 10 أيام'),
        (above, 15, 'السعر استعاد EMA20'),
        (slope, 10, 'ميل EMA20 بدأ يتحسن'),
        (rsi, 10, f'RSI يتحسن ({float(x.RSI):.1f})'),
        (macd, 10, 'MACD Histogram يتحسن'),
        (vol, 10, 'حجم تداول مؤكد'),
        (breakout, 10, 'اختراق قمة آخر 5 أيام'),
    ]

    for ok, pts, msg in checks:
        if ok:
            score += pts
            reasons.append(msg)

    if not breakout and near:
        score += 5
        reasons.append('قريب من منطقة دعم')

    reversal = (
        correction and recent and above and rsi and macd
        and score >= config.REVERSAL_SCORE
    )

    if breakout:
        lo, hi = close * 0.995, close * 1.01
    else:
        lo, hi = max(float(x.EMA20), close - 0.5 * atr), close * 1.005

    stop = min(
        low - 0.25 * atr,
        sup * 0.98,
        lo - config.STOP_ATR_MULTIPLIER * atr
    )

    risk = max(lo - stop, 0.01)

    return {
        'symbol': sym,
        'date': str(x.Date.date()),
        'close': round(close, 2),
        'score': score,
        'signal': 'REVERSAL' if reversal else ('WATCH' if score >= 70 else 'NEUTRAL'),
        'entry_low': round(lo, 2),
        'entry_high': round(hi, 2),
        'stop': round(stop, 2),
        'target1': round(lo + 1.5 * risk, 2),
        'target2': round(lo + 2.5 * risk, 2),
        'rsi': round(float(x.RSI), 2),
        'vol_ratio': round(float(x.VOL_RATIO), 2),
        'correction_pct': round(abs(dd) * 100, 2),
        'rebound_pct': round(reb * 100, 2),
        'reasons': reasons
    }


def telegram(method, **data):
    token = os.environ['TELEGRAM_BOT_TOKEN']
    url = f'https://api.telegram.org/bot{token}/{method}'
    return requests.post(url, data=data, timeout=30).json()


def send_message(chat_id, text):
    telegram(
        'sendMessage',
        chat_id=chat_id,
        text=text,
        parse_mode='HTML'
    )


def scan_egx():
    symbols = discover_symbols()
    data = fetch_history(symbols)
    results = []

    for s, d in data.items():
        try:
            x = analyze(s, d)
            if x:
                results.append(x)
        except Exception as e:
            print(s, e)

    rev = [x for x in results if x['signal'] == 'REVERSAL']
    rev.sort(key=lambda x: x['score'], reverse=True)

    if not rev:
        return '🔎 فحص EGX اكتمل\nلا توجد حاليًا إشارات REVERSAL مطابقة للشروط.'

    lines = [
        '<b>🔄 EGX REVERSAL</b>',
        'أسهم بدأت تنهي التصحيح وتظهر علامات ارتداد:',
        ''
    ]

    for x in rev[:10]:
        lines += [
            f"<b>{x['symbol']}</b> | Score {x['score']}/100",
            f"السعر: {x['close']} | التصحيح: {x['correction_pct']}% | الارتداد: {x['rebound_pct']}%",
            f"🎯 دخول: {x['entry_low']} - {x['entry_high']}",
            f"🛑 وقف: {x['stop']}",
            f"🎯 T1: {x['target1']} | T2: {x['target2']}",
            f"RSI: {x['rsi']} | Volume: {x['vol_ratio']}x",
            '• ' + '\n• '.join(x['reasons'][:5]),
            ''
        ]

    return '\n'.join(lines)


def main():
    print('Telegram bot started...')

    offset = None

    while True:
        try:
            result = telegram(
                'getUpdates',
                timeout=25,
                offset=offset
            )

            updates = result.get('result', [])

            for update in updates:
                offset = update['update_id'] + 1

                message = update.get('message')
                if not message:
                    continue

                chat_id = message['chat']['id']
                text = message.get('text', '').strip().lower()

                if text in ['/start', 'start', 'مرحبا', 'اهلا', 'أهلا']:
                    send_message(
                        chat_id,
                        '🤖 <b>EGX AI Bot</b>\n\n'
                        'البوت شغال ومستعد.\n\n'
                        'اكتب <b>فحص</b> أو <b>egx</b> لعمل تحليل للسوق.'
                    )

                elif text in ['فحص', 'egx', '/scan', 'scan']:
                    send_message(chat_id, '⏳ جاري فحص EGX...')

                    try:
                        result_text = scan_egx()
                        send_message(chat_id, result_text)
                    except Exception as e:
                        print('Scan error:', e)
                        send_message(
                            chat_id,
                            '❌ حصل خطأ أثناء فحص السوق.'
                        )

                else:
                    send_message(
                        chat_id,
                        'اكتب <b>فحص</b> لعمل تحليل EGX.'
                    )

        except Exception as e:
            print('Bot error:', e)
            time.sleep(5)


if __name__ == '__main__':
    main()
