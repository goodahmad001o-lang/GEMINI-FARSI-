import os

print("--- 📂 لیست تمام فایل‌های موجود در پروژه شما ---")
try:
    for root, dirs, files in os.walk("."):
        for file in files:
            print(os.path.join(root, file))
except Exception as e:
    print(f"Error: {e}")
print("---------------------------------------------")

# یک ارور ساختگی برای اینکه رندر متوقف شود و لاگ بالا را ببینیم
raise SystemExit("حاج احمد، لیست فایل‌ها رو بالا چاپ کردم! ببین اسم فایل اصلی چیه؟")
