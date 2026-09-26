"""
EGX AI Bot - 1 Year Backtest
Uses the EXISTING indicators.py and config.py from the repository.

Backtest scope:
- REVERSAL signals only
- Last 1 year of daily data
- Signal is generated using the close of day D only.
- Entry is simulated from day D+1 onward (no look-ahead).
- Maximum holding period: 10 trading sessions.
- Outcomes: STOP, T1, T2, TIMEOUT, NO_ENTRY.
- If STOP and target are both touched in the same daily candle,
  STOP is counted first (conservative because daily OHLC has no intraday order).
"""

from datetime import datetime, timedelta, timezone
import math
import os
import time

import pandas as pd
import yfinance as yf

from indicators import add
import config
from data_source import discover_symbols


REQUIRED = [
    "EMA20", "RSI", "ATR", "VOL_RATIO", "SUP", "LOW10",
    "HIGH5", "EMA20_SLOPE5", "REBOUND10", "DRAWDOWN20",
    "RSI_PREV", "MACD_HIST", "MACD_HIST_PREV"
]

HOLDING_SESSIONS = 10
DATA_PERIOD = "2y"  # extra warm-up; we evaluate only the last 1 year


def download_stock(symbol):
    ticker = f"{symbol}.CA"
    try:
        df = yf.download(
            ticker,
            period=DATA_PERIOD,
            interval="1d",
            auto_adjust=False,
            progress=False,
            threads=False,
            group_by="ticker",
            timeout=30,
        )

        if df is None or df.empty:
            return pd.DataFrame()

        if isinstance(df.columns, pd.MultiIndex):
            # Usually (ticker, field) for a single ticker with group_by=ticker.
            if ticker in df.columns.get_level_values(0):
                df = df.xs(ticker, axis=1, level=0, drop_level=True)
            elif ticker in df.columns.get_level_values(-1):
                df = df.xs(ticker, axis=1, level=-1, drop_level=True)
            else:
                df.columns = [
                    c[-1] if isinstance(c, tuple) else c for c in df.columns
                ]

        df = df.reset_index()
        df.columns = [str(c) for c in df.columns]

        # Normalize possible Date/Datetime naming.
        if "Date" not in df.columns:
            for c in df.columns:
                if str(c).lower() in ("date", "datetime"):
                    df = df.rename(columns={c: "Date"})
                    break

        required = ["Date", "Open", "High", "Low", "Close", "Volume"]
        if not all(c in df.columns for c in required):
            return pd.DataFrame()

        df = df[required].copy()
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        try:
            df["Date"] = df["Date"].dt.tz_localize(None)
        except Exception:
            pass

        for c in required[1:]:
            df[c] = pd.to_numeric(df[c], errors="coerce")

        df = df.dropna().sort_values("Date").reset_index(drop=True)
        return df

    except Exception as e:
        print(f"[DOWNLOAD ERROR] {symbol}: {e}")
        return pd.DataFrame()


def signal_for_row(d, i, symbol):
    """Same signal rules as bot.py, evaluated only on row i."""
    x = d.iloc[i]

    if any(pd.isna(x[c]) for c in REQUIRED):
        return None

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

    macd = float(x.MACD_HIST) > float(x.MACD_HIST_PREV)
    vol = float(x.VOL_RATIO) >= config.MIN_VOLUME_RATIO
    breakout = close > float(x.HIGH5)
    near = close <= sup * config.SUPPORT_ZONE_MULTIPLIER

    score = 0
    checks = [
        (correction, 20),
        (recent, 15),
        (above, 15),
        (slope, 10),
        (rsi, 10),
        (macd, 10),
        (vol, 10),
        (breakout, 10),
    ]

    for ok, pts in checks:
        if ok:
            score += pts

    if not breakout and near:
        score += 5

    reversal = (
        correction
        and recent
        and above
        and rsi
        and macd
        and score >= config.REVERSAL_SCORE
    )

    if not reversal:
        return None

    if breakout:
        entry_low = close * 0.995
        entry_high = close * 1.01
    else:
        entry_low = max(float(x.EMA20), close - 0.5 * atr)
        entry_high = close * 1.005

    stop = min(
        low - 0.25 * atr,
        sup * 0.98,
        entry_low - config.STOP_ATR_MULTIPLIER * atr,
    )

    risk = max(entry_low - stop, 0.01)
    target1 = entry_low + config.TARGET1_RR * risk
    target2 = entry_low + config.TARGET2_RR * risk

    return {
        "symbol": symbol,
        "signal_date": x.Date.date().isoformat(),
        "signal_close": close,
        "score": score,
        "entry_low": entry_low,
        "entry_high": entry_high,
        "stop": stop,
        "target1": target1,
        "target2": target2,
    }


def simulate_trade(d, signal_index, sig):
    """
    Start from the next trading session.
    Entry is triggered when price reaches entry_low.
    If the next session opens below entry_low, we use the open as the fill,
    unless it is already below the stop (then STOP_GAP).
    """
    start = signal_index + 1
    end = min(start + HOLDING_SESSIONS, len(d))

    if start >= len(d):
        return {
            **sig,
            "entry_date": "",
            "entry_price": math.nan,
            "exit_date": "",
            "exit_price": math.nan,
            "outcome": "NO_FOLLOWUP",
            "return_pct": math.nan,
            "holding_sessions": 0,
        }

    entry_price = None
    entry_date = None
    entry_pos = None

    for j in range(start, end):
        r = d.iloc[j]
        o, h, l = float(r.Open), float(r.High), float(r.Low)

        # Conservative gap handling.
        if o < sig["stop"]:
            return {
                **sig,
                "entry_date": r.Date.date().isoformat(),
                "entry_price": o,
                "exit_date": r.Date.date().isoformat(),
                "exit_price": o,
                "outcome": "STOP_GAP",
                "return_pct": (o / sig["entry_low"] - 1) * 100,
                "holding_sessions": j - start + 1,
            }

        # If price opens inside entry zone, fill at open.
        if sig["entry_low"] <= o <= sig["entry_high"]:
            entry_price = o
            entry_date = r.Date.date().isoformat()
            entry_pos = j
            break

        # If price trades through the lower edge of the zone, fill at entry_low.
        if l <= sig["entry_low"] <= h:
            entry_price = sig["entry_low"]
            entry_date = r.Date.date().isoformat()
            entry_pos = j
            break

        # If it opens above the zone and never reaches it, this day is skipped.
        # A later day can still trigger the entry.

    if entry_price is None:
        return {
            **sig,
            "entry_date": "",
            "entry_price": math.nan,
            "exit_date": "",
            "exit_price": math.nan,
            "outcome": "NO_ENTRY",
            "return_pct": math.nan,
            "holding_sessions": end - start,
        }

    # Once entered, simulate up to 10 sessions including entry day.
    exit_end = min(entry_pos + HOLDING_SESSIONS, len(d))

    for j in range(entry_pos, exit_end):
        r = d.iloc[j]
        h, l = float(r.High), float(r.Low)

        # Targets/stop are based on the bot's planned entry_low.
        # Conservative daily-bar rule: STOP wins if both are touched.
        if l <= sig["stop"]:
            exit_price = sig["stop"]
            return {
                **sig,
                "entry_date": entry_date,
                "entry_price": entry_price,
                "exit_date": r.Date.date().isoformat(),
                "exit_price": exit_price,
                "outcome": "STOP",
                "return_pct": (exit_price / entry_price - 1) * 100,
                "holding_sessions": j - entry_pos + 1,
            }

        if h >= sig["target2"]:
            exit_price = sig["target2"]
            return {
                **sig,
                "entry_date": entry_date,
                "entry_price": entry_price,
                "exit_date": r.Date.date().isoformat(),
                "exit_price": exit_price,
                "outcome": "T2",
                "return_pct": (exit_price / entry_price - 1) * 100,
                "holding_sessions": j - entry_pos + 1,
            }

        if h >= sig["target1"]:
            exit_price = sig["target1"]
            return {
                **sig,
                "entry_date": entry_date,
                "entry_price": entry_price,
                "exit_date": r.Date.date().isoformat(),
                "exit_price": exit_price,
                "outcome": "T1",
                "return_pct": (exit_price / entry_price - 1) * 100,
                "holding_sessions": j - entry_pos + 1,
            }

    # No stop/target within the window: close at last observed session.
    j = exit_end - 1
    r = d.iloc[j]
    exit_price = float(r.Close)

    return {
        **sig,
        "entry_date": entry_date,
        "entry_price": entry_price,
        "exit_date": r.Date.date().isoformat(),
        "exit_price": exit_price,
        "outcome": "TIMEOUT",
        "return_pct": (exit_price / entry_price - 1) * 100,
        "holding_sessions": j - entry_pos + 1,
    }


def main():
    print("=" * 70)
    print("EGX AI BOT - 1 YEAR REVERSAL BACKTEST")
    print("=" * 70)
    print(f"Run time: {datetime.now(timezone.utc).isoformat()}")
    print(f"Holding window: {HOLDING_SESSIONS} trading sessions")
    print("Signal: REVERSAL only")
    print("Data source: Yahoo Finance / yfinance")
    print()

    symbols = discover_symbols()
    print(f"Universe: {len(symbols)} symbols")

    cutoff = pd.Timestamp.utcnow().tz_localize(None) - pd.Timedelta(days=365)
    all_results = []
    loaded = 0
    signals = 0

    for n, symbol in enumerate(symbols, 1):
        print(f"[{n}/{len(symbols)}] {symbol}")
        raw = download_stock(symbol)

        if raw.empty or len(raw) < 220:
            print("  SKIP: insufficient data")
            continue

        loaded += 1

        # Indicators are calculated exactly as in the bot.
        d = add(raw, config)

        # Evaluate signals only in the requested last year.
        for i in range(1, len(d)):
            if d.iloc[i].Date < cutoff:
                continue

            sig = signal_for_row(d, i, symbol)
            if sig is None:
                continue

            signals += 1
            result = simulate_trade(d, i, sig)
            all_results.append(result)

        time.sleep(0.2)

    results = pd.DataFrame(all_results)

    if results.empty:
        print("\nNO REVERSAL SIGNALS FOUND.")
        Path("backtest_summary.txt").write_text(
            "No REVERSAL signals were found in the last year.\n",
            encoding="utf-8",
        )
        return

    # Summary statistics
    total = len(results)
    outcome_counts = results["outcome"].value_counts()
    completed = results[results["outcome"].isin(["STOP", "STOP_GAP", "T1", "T2", "TIMEOUT"])].copy()
    wins_t1_or_better = results["outcome"].isin(["T1", "T2"]).sum()
    wins_t2 = (results["outcome"] == "T2").sum()
    stops = results["outcome"].isin(["STOP", "STOP_GAP"]).sum()
    no_entry = (results["outcome"] == "NO_ENTRY").sum()
    timeouts = (results["outcome"] == "TIMEOUT").sum()

    valid_returns = completed["return_pct"].dropna()
    avg_return = valid_returns.mean() if len(valid_returns) else float("nan")
    median_return = valid_returns.median() if len(valid_returns) else float("nan")
    best = valid_returns.max() if len(valid_returns) else float("nan")
    worst = valid_returns.min() if len(valid_returns) else float("nan")

    # Equal-weight sequence, not a portfolio simulation.
    equity = (1 + valid_returns / 100).cumprod() if len(valid_returns) else pd.Series(dtype=float)
    if len(equity):
        running_max = equity.cummax()
        drawdown = equity / running_max - 1
        max_dd = drawdown.min() * 100
        total_compounded = (equity.iloc[-1] - 1) * 100
    else:
        max_dd = float("nan")
        total_compounded = float("nan")

    win_rate = wins_t1_or_better / total * 100
    t2_rate = wins_t2 / total * 100
    stop_rate = stops / total * 100

    summary = f"""
EGX AI BOT - 1 YEAR BACKTEST
Generated: {datetime.now(timezone.utc).isoformat()}

UNIVERSE
--------
Symbols in bot universe: {len(symbols)}
Symbols with usable data: {loaded}

SIGNALS
-------
REVERSAL signals: {total}
T1 or T2: {wins_t1_or_better} ({win_rate:.2f}%)
T2: {wins_t2} ({t2_rate:.2f}%)
STOP / STOP_GAP: {stops} ({stop_rate:.2f}%)
TIMEOUT: {timeouts}
NO_ENTRY: {no_entry}

RETURNS (equal-weight per completed signal)
-------------------------------------------
Average return: {avg_return:.2f}%
Median return: {median_return:.2f}%
Best return: {best:.2f}%
Worst return: {worst:.2f}%
Compounded sequence return: {total_compounded:.2f}%
Max drawdown of signal sequence: {max_dd:.2f}%

IMPORTANT
---------
This is a historical simulation, not an investment recommendation.
Daily OHLC data cannot reveal the intraday order when STOP and TARGET
are both touched on the same candle, so STOP is counted first.
The test uses the signal-day close only to create the signal and starts
entry simulation from the following trading session.
"""
    print(summary)

    results = results.sort_values(["signal_date", "symbol"]).reset_index(drop=True)
    results.to_csv("backtest_results.csv", index=False, encoding="utf-8-sig")

    # Per-symbol breakdown
    by_symbol = (
        results.groupby("symbol")
        .agg(
            signals=("symbol", "size"),
            t1_t2=("outcome", lambda s: s.isin(["T1", "T2"]).sum()),
            t2=("outcome", lambda s: (s == "T2").sum()),
            stops=("outcome", lambda s: s.isin(["STOP", "STOP_GAP"]).sum()),
            avg_return=("return_pct", "mean"),
        )
        .reset_index()
    )
    by_symbol["win_rate_pct"] = by_symbol["t1_t2"] / by_symbol["signals"] * 100
    by_symbol = by_symbol.sort_values(["win_rate_pct", "signals"], ascending=[False, False])
    by_symbol.to_csv("backtest_by_symbol.csv", index=False, encoding="utf-8-sig")

    Path("backtest_summary.txt").write_text(summary.strip() + "\n", encoding="utf-8")

    print("\nFiles created:")
    print(" - backtest_summary.txt")
    print(" - backtest_results.csv")
    print(" - backtest_by_symbol.csv")


if __name__ == "__main__":
    main()
