# EGX universe
# The scanner discovers every CSV file placed under data/ and excludes bank stocks.
# Bank tickers below reflect the EGX bank-sector list available in Sep 2026.
BANK_SYMBOLS={"COMI","QNBE","HDBK","ADIB","CANA","CIEB","FAIT","FAITA","EXPA","SAUD","UBEE","EGBE","SAIB"}

EMA_FAST,EMA_MID,EMA_SLOW=20,50,200
RSI_PERIOD,ATR_PERIOD,VOLUME_PERIOD=14,14,20
BREAKOUT_LOOKBACK=20
STOP_ATR_MULTIPLIER=1.8
TARGET1_RR,TARGET2_RR=1.5,2.5
WATCH_SCORE=70

# Reversal-after-correction settings
MIN_CORRECTION_PCT = 0.06       # at least 6% below the recent 20-day peak
MIN_REBOUND_PCT = 0.02          # at least 2% rebound from 10-day low
MIN_EMA20_SLOPE = 0.002         # EMA20 up at least 0.2% over 5 sessions
MIN_RSI = 45                    # RSI reclaiming the 45 area
MIN_VOLUME_RATIO = 1.10         # 10% above 20-day average volume
SUPPORT_ZONE_MULTIPLIER = 1.06
REVERSAL_SCORE = 70
