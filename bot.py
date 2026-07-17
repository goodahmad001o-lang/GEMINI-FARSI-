import os
import requests
import telebot
from telebot import types
import google.generativeai as genai
from PIL import Image
import io
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

# ۱. دریافت توکن‌ها از متغیرهای محیطی رندر
BOT_TOKEN = os.environ.get("8691005129:AAG7R-6YqkTKPVwADyDBFPE-wwyRHYRz6VA", "")
GEMINI_API_KEY = os.environ.get("AQ.Ab8RN6IL6_p1DZY_bA2ElNEjNY-NbSohnxuMgqvUizMm42sOfg", "")

# راه‌اندازی ربات تلگرام و هوش مصنوعی جمینای
bot = telebot.TeleBot(BOT_TOKEN)
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

# ۲. اطلاعات فروشگاه (مغازه‌دار این متن را تغییر می‌دهد)
SHOP_INFO = """
نام فروشگاه: شیک پوش (فروشگاه آنلاین لباس مردانه)
قوانین ارسال: ارسال با پست پیشتاز به سراسر کشور (هزینه ۵۰ هزار تومان). تحویل ۳ الی ۵ روز کاری.
روش پرداخت: کارت به کارت به شماره کارت [۶۰۳۷-۹۹۱۹-۱۲۳۴-۵۶۷۸] به نام احمد احمدی. بعد از واریز حتما عکس فیش را اینجا بفرستید.

لیست محصولات موجود:
۱. هودی اورسایز مشکی - قیمت: ۵۸۰,۰۰۰ تومان - سایزها: L, XL, XXL - جنس: دورس ۳ نخ پنبه
۲. شلوار کارگو کتان سبز - قیمت: ۶۵۰,۰۰۰ تومان - سایزها: ۳۰ تا ۳۶ - رنگ‌ها: سبز زیتونی، مشکی
۳. تیشرت یقه گرد ساده - قیمت: ۲۹۰,۰۰۰ تومان - سایزها: M, L, XL - رنگ: سفید، طوسی
"""

# پرامپت هدایت لحن هوش مصنوعی
SYSTEM_PROMPT = f"""
تو ادمین مهربان، مودب، صبور و حرفه‌ای فروشگاه تلگرامی هستی. وظیفه تو این است که بر اساس اطلاعات فروشگاه زیر به مشتریان پاسخ دهی:
{SHOP_INFO}

دستورالعمل‌ها:
- لحن تو صمیمی، محترمانه و ترغیب‌کننده به خرید باشد. از ایموجی‌های مناسب استفاده کن.
- پاسخ‌های کوتاه و تلگرامی بفرست تا خواندنش راحت باشد.
"""

@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = (
        "سلام! به بوتیک آنلاین **شیک‌پوش** خوش آمدید 🛒✨\n\n"
        "من دستیار هوش مصنوعی فروشگاه هستم و ۲۴ ساعته در خدمتم.\n"
        "هر سوالی درباره قیمت، سایز، موجودی و نحوه ارسال داری بپرس تا راهنماییت کنم!\n\n"
        "🛍️ برای خرید، کافیه محصولت رو انتخاب کنی و بعد از واریز وجه، **عکس فیش واریزی** رو برام بفرستی."
    )
    bot.reply_to(message, welcome_text)

# بررسی عکس فیش واریزی با جمینای
@bot.message_handler(content_types=['photo'])
def handle_receipt(message):
    processing_msg = bot.reply_to(message, "🔄 در حال آنالیز و تایید فیش واریزی با هوش مصنوعی... لطفاً چند لحظه صبر کنید.")
    
    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        image = Image.open(io.BytesIO(downloaded_file))
        
        receipt_prompt = """
        این عکس یک فیش واریزی کارت به کارت بانکی در ایران است. آن را با دقت بسیار بالا تحلیل کن و پاسخ را دقیقا به زبان فارسی در قالب زیر ارائه بده:
        
        وضعیت فیش: [تایید شده / مشکوک به جعل / نامعتبر]
        مبلغ تراکنش: [مبلغ به ریال یا تومان]
        شماره پیگیری/مرجع: [کد پیگیری]
        تاریخ و ساعت تراکنش: [مثال: ۱۴۰۳/۱۲/۰۵ ساعت ۱۵:۳۰]
        توضیحات امنیت فیش: [اگر فونت ناهمخوان است یا رسید فاقد کدهای رهگیری رسمی است قید کن. در غیر این صورت بنویس: فونت و ساختار فیش طبیعی به نظر می‌رسد.]
        """
        
        response = model.generate_content([receipt_prompt, image])
        bot.delete_message(message.chat.id, processing_msg.message_id)
        bot.reply_to(message, f"🔍 **نتیجه بررسی رسید شما:**\n\n{response.text}")
        
    except Exception as e:
        bot.edit_message_text(f"❌ خطا در پردازش تصویر فیش: {str(e)}", message.chat.id, processing_msg.message_id)

# پاسخ به پیام‌های متنی مشتری
@bot.message_handler(func=lambda message: True)
def handle_chat(message):
    try:
        chat = model.start_chat(history=[])
        full_query = f"{SYSTEM_PROMPT}\n\nپیام مشتری: {message.text}"
        response = chat.send_message(full_query)
        bot.reply_to(message, response.text)
    except Exception as e:
        bot.reply_to(message, "عذرخواهی می‌کنم، سرور در حال حاضر پاسخگو نیست.")

# کدهای حل مشکل پورت رندر (Port Binding)
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"Bot is running smoothly!")

def run_health_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

if __name__ == "__main__":
    # اجرای وب‌سرور سلامتی در یک رشته جداگانه برای دور زدن ارور پورت رندر
    threading.Thread(target=run_health_server, daemon=True).start()
    # اجرای ربات تلگرام
    bot.infinity_polling()
