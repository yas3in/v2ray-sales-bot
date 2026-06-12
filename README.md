# 🤖 X-UI / Shadowsocks 2022 Automated V2Ray Sales Telegram Bot

یک ربات هوشمند و اتوماتیک تلگرام برای فروش و مدیریت سرویس‌های کاهش پینگ و دور زدن فیلترینگ، متصل به پنل‌های مبتنی بر **X-UI (سنایی / علیرضا)** با پشتیبانی کامل از پروتکل‌های نسل جدید از جمله **Shadowsocks 2022**.

این پروژه با معماری ترکیبی (Hybrid) توسعه یافته است؛ تراکنش‌های مالی، بسته‌ها و کاربران در دیتابیس لوکال مدیریت می‌شوند، در حالی که ساخت کلاینت و مانیتورینگ ترافیک به صورت زنده (Live) از طریق API با پنل X-UI هماهنگ می‌گردد.

---

## ✨ ویژگی‌های کلیدی (Features)

*   **مدیریت هوشمند Shadowsocks 2022:** تولید کلیدهای استاندارد و امن ۳۲ بایتی Base64 به صورت اتوماتیک جهت جلوگیری از کرش کردن هسته Xray.
*   **معماری ناهمگام (Asynchronous):** توسعه یافته با `Aiogram 3` و `SQLAlchemy AsyncSession` برای بازدهی بالا و سرعت فوق‌العاده.
*   **سیستم کیف پول داخلی:** امکان شارژ حساب، کسر موجودی خودکار هنگام خرید و ثبت دقیق تاریخچه تراکنش‌ها.
*   **مانیتورینگ زنده ترافیک:** دریافت لحظه‌ای حجم مصرفی (Upload/Download)، حجم باقی‌مانده و تاریخ انقضا مستقیم از پنل.
*   **جلوگیری از تداخل (Race Condition):** بررسی یکتا بودن ایمیل‌ها در دیتابیس لوکال پیش از ارسال درخواست به پنل برای جلوگیری از خطاهای دیتابیس X-UI.
*   **تایپ‌هینتینگ استاندارد:** کد کاملاً بهینه‌سازی شده برای `Pylance` و ابزارهای استاتیک آنالیزور (Zero Errors وضعیت لایو).

---

## 🛠 ابزارها و تکنولوژی‌ها (Tech Stack)

*   **Language:** Python 3.10+
*   **Bot Framework:** Aiogram 3.x (FSM Router-based)
*   **Database ORM:** SQLAlchemy 2.x (Async Mode)
*   **Database:** PostgreSQL / SQLite
*   **Panel API:** X-UI (Sanaei / Alireza)

---

## 🚀 راه اندازی پروژه (Installation)

### ۱. کلون کردن مخزن
```bash
git clone [https://github.com/your-username/your-repo-name.git](https://github.com/your-username/your-repo-name.git)
cd your-repo-name
```

## ۲. ساخت محیط مجازی و نصب وابستگی‌ها

```bash
python -m venv venv

# Linux / macOS
source venv/bin/activate

# Windows
venv\Scripts\activate

pip install -r requirements.txt
```

---

## ۳. تنظیمات فایل محیطی (Environment Variables)

یک فایل با نام `.env` در ریشه پروژه ایجاد کنید و مقادیر زیر را در آن قرار دهید:

```env
BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwXyZ
DATABASE_URL=sqlite+aiosqlite:///./bot_database.db
XUI_URL=http://your-panel-ip:2053
XUI_USER=admin
XUI_PASS=password
```

---

## ۴. اجرای ربات

```bash
python main.py
```

---

# 📁 ساختار پوشه‌بندی پروژه (Architecture)

```text
.
├── database/
│   ├── db_config.py     # اتصالات دیتابیس
│   ├── models.py        # مدل‌های دیتابیس (User, Tariff, UserConfig, ...)
│   └── crud.py          # عملیات اصلی دیتابیس (CRUD)
│
├── handlers/
│   ├── user.py          # هندلرهای بخش کاربر (خرید، اطلاعات کلاینت، منو)
│   └── admin.py         # هندلرهای مدیریت ربات
│
├── keyboards/
│   └── inline.py        # کیبوردهای شیشه‌ای ربات
│
├── services/
│   └── xui_api.py       # ارتباط با API پنل X-UI
│
├── utils/
│   └── states.py        # FSM States
│
├── .env                 # تنظیمات محرمانه
├── main.py              # نقطه شروع اجرای ربات
└── README.md
```

---

# 📝 نقشه راه توسعه (Roadmap)

* [ ] اتصال به درگاه‌های پرداخت ریالی و کریپتو (NowPayments / زیبال)
* [ ] سیستم نوتیفیکیشن خودکار پیش از پایان حجم یا زمان سرویس
* [ ] امکان تمدید خودکار کانفیگ از داخل ربات
* [ ] افزودن قابلیت ساخت تانل و مدیریت چند پنل به‌صورت هم‌زمان

---

# 🤝 مشارکت (Contributing)

مشارکت‌ها باعث رشد و بهبود پروژه می‌شوند. از همکاری شما استقبال می‌کنیم.

1. پروژه را Fork کنید.
2. یک Branch جدید برای قابلیت خود ایجاد کنید:

```bash
git checkout -b feature/AmazingFeature
```

3. تغییرات خود را Commit کنید:

```bash
git commit -m "Add some AmazingFeature"
```

4. Branch خود را Push کنید:

```bash
git push origin feature/AmazingFeature
```

5. یک Pull Request ایجاد کنید.
