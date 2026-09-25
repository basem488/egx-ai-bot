# EGX AI Web App — Render Ready

## Deploy
1. Upload this project to GitHub.
2. On Render choose **New -> Web Service** and connect the GitHub repo.
3. Render can also detect `render.yaml`.
4. Use the **Free** plan.
5. Build command: `pip install -r requirements.txt`
6. Start command: `gunicorn app:app --bind 0.0.0.0:$PORT`

## Universe: all EGX stocks except banks
The scanner now discovers **every stock CSV** placed under `data/` and analyzes it automatically.
It excludes the bank-sector tickers: COMI, QNBE, HDBK, ADIB, CANA, CIEB, FAIT, FAITA, EXPA, SAUD, UBEE, EGBE, SAIB.

**Important:** this version still needs daily CSV price files under `data/`. Adding a CSV for a listed EGX stock makes it part of the scan automatically; adding a bank CSV will still exclude it.
The free Render filesystem is ephemeral, so do not rely on local files for permanent storage.
For reliable Push subscriptions, use a persistent datastore later.

This app is for research/analysis only. It does not place trades.
