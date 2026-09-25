# EGX universe
# The scanner discovers every CSV file placed under data/ and excludes bank stocks.
# Bank tickers below reflect the EGX bank-sector list available in Sep 2026.
BANK_SYMBOLS={
    "COMI","QNBE","HDBK","ADIB","CANA","CIEB","FAIT","FAITA",
    "EXPA","SAUD","UBEE","EGBE","SAIB"
}

EMA_FAST,EMA_MID,EMA_SLOW=20,50,200
RSI_PERIOD,ATR_PERIOD,VOLUME_PERIOD=14,14,20
BREAKOUT_LOOKBACK=20
STOP_ATR_MULTIPLIER=1.8
TARGET1_RR,TARGET2_RR=1.5,2.5
WATCH_SCORE=70
