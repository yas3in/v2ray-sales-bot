FROM python:3.12-slim

WORKDIR /app

# نصب وابستگی‌های سیستم
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# نصب کتابخانه‌های پایتون
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# کپی کد پروژه
COPY . .

# ایجاد پوشه دیتابیس
RUN mkdir -p /app/data

EXPOSE 8080

# اجرا در حالت Webhook
CMD ["python", "webhook.py"]
