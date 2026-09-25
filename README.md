# EGX Reversal Telegram Bot
يفحص أسهم EGX غير البنكية بحثًا عن انتهاء التصحيح وبداية الارتداد.

## GitHub Actions
أضف Secret باسم `TELEGRAM_BOT_TOKEN`. افتح البوت في Telegram وأرسل `/start` مرة واحدة، ثم شغّل الـ workflow يدويًا أول مرة. الجدولة اليومية مضمّنة.

مصدر الأسعار: Yahoo Finance عبر yfinance، وقد تتأخر البيانات أو تفشل لبعض الرموز؛ البوت لا يخترع بيانات.
