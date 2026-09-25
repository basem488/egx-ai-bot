# EGX AI Web App

نسخة Web App للموبايل من بوت تحليل EGX.
تعمل محليًا أو على استضافة Python، وتعرض آخر الإشارات، وتدعم Web Push عند إعداد VAPID.

## تشغيل محلي
```bash
pip install -r requirements.txt
python app.py
```
افتح `http://127.0.0.1:8000` من المتصفح.

## البيانات
ضع ملفات CSV داخل `data/`:
`ETEL.csv`, `SWDY.csv`, `EGAL.csv`, `MFPC.csv`, `ALCN.csv`

الأعمدة:
`Date,Open,High,Low,Close,Volume`

## Push Notifications
للإشعارات الحقيقية تحتاج HTTPS (باستثناء localhost) ومتصفح يدعم Web Push.
ثبت:
```bash
pip install pywebpush
```
ثم عرّف:
`VAPID_PRIVATE_KEY`
`VAPID_PUBLIC_KEY`
`VAPID_CLAIMS_EMAIL`

بعدها افتح التطبيق واضغط Enable Push، ثم شغّل:
```bash
python scanner.py
```

ملاحظة: هذه نسخة بحثية. لا تنفذ صفقات تلقائيًا.
