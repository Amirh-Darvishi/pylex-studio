# PyLex Studio

ویرایشگر دسکتاپ پایتون با تحلیل لغوی و نحوی مستقل.

## امکانات
- ویرایش فایل‌های Python، شماره خطوط و رنگ‌بندی پایه
- تحلیل لغوی با `tokenize` و تحلیل نحوی با `ast`
- اجرای کد و نمایش stdout / stderr
- بزرگ‌نمایی، تم روشن/تاریک، باز کردن و ذخیره فایل
- آزمون‌های واحد و GitHub Actions

## نیازمندی
Python 3.10+ و Tkinter. وابستگی خارجی پایتون وجود ندارد.

## نصب و اجرا
```bash
git clone https://github.com/Amirh-Darvishi/pylex-studio.git
cd pylex-studio
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1
# Linux/macOS: source .venv/bin/activate
python main.py
```

## تست
```bash
python -m unittest discover -s tests -v
```

## امنیت
کد اجراشده با سطح دسترسی کاربر فعلی اجرا می‌شود. این ابزار sandbox نیست؛ کدهای ناشناس را اجرا نکنید.

راهنمای کامل فارسی در `docs/PROJECT_GUIDE.html` قرار دارد.
