# EGX AI Web App — Automatic EGX Scanner (no banks)

This version automatically discovers the current EGX stock universe from public market pages, removes the 13 EGX bank-sector listings, downloads daily OHLCV history from Yahoo Finance using the `.CA` EGX ticker convention, calculates technical indicators, and shows entry/stop/targets.

## Important data limitation
Yahoo Finance/yfinance is an unofficial third-party source and does not cover every EGX security. The app therefore skips symbols for which Yahoo returns insufficient history. The universe discovery is refreshed when the scan cache expires.

EGX itself publishes a live Market Watch with symbol, sector, last price, volume and value traded. The app does not claim that Yahoo is an official EGX feed.

## Render Free
Free Render Web Services are suitable for testing/hobby use but have ephemeral local storage and can spin down. Therefore subscriptions/cache are in-memory/local and can be lost on restart. Push notifications should be treated as best-effort on the free setup.

Build: `pip install -r requirements.txt`
Start: `gunicorn app:app --bind 0.0.0.0:$PORT`

Optional env vars:
- `VAPID_PUBLIC_KEY`
- `VAPID_PRIVATE_KEY`
- `VAPID_CLAIMS_EMAIL`
- `SCAN_CACHE_SECONDS` (default 900)
- `HISTORY_PERIOD` (default 3y)

This app is research/analysis software. It does not place trades and its signals are not guarantees of future performance.
