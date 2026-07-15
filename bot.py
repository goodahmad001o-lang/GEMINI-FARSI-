import sqlite3
import requests
import telebot
from telebot import types
from datetime import datetime, timedelta
import threading
from flask import Flask
import os

# ==================== تنظیمات اصلی ربات ====================
BOT_TOKEN = "8691005129:AAGF-rvF9K5fOZONM-8JPXguhDKl4mKQni4"
GROQ_API_KEY = "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"
ADMIN_ID = 6822309164
CHANNELS = ["@MRAHMAD_1", "@GMINIFARSI"]

# مشخصات کارت بانکی شما برای واریز کاربرها
CARD_NUMBER = "6037697438262914"  
CARD_NAME = "حسین پویان"            
PRICE_1_MONTH = "69,000"
PRICE_3_MONTHS = "159,000"
PRICE_6_MONTHS = "279,000"

# نام دیتابیس نو و تازه جهت جلوگیری از قفل‌های قبلی
DATABASE_NAME = "sultan_final_database.db"
# ==========================================================

# ۱. وب‌سرور مینیمال برای باز نگه داشتن پورت رندر و جلوگیری از تایم‌اوت
app = Flask('')

@app.route('/')
def home():
    return "🟢 Sultan Bot is fully active and running in background!"

def run_web_server():
    try:
        port = int(os.environ.get("PORT", 10000))
        app.run(host='0.0.0.0', port=port)
    except Exception as e:
        print(f"❌ Error starting web server: {e}")

bot = telebot.TeleBot(BOT_TOKEN)

# پرامپت هماهنگ شده با فرمت HTML تلگرام جهت پایداری پیام‌ها
SYSTEM_PROMPT = """
شما یک هوش مصنوعی فوق‌پیشرفته، بسیار باهوش، کاریزماتیک و حلال مشکلات هستید.
مخاطب شما کاربران ایرانی هستند، پس باید با لحنی فوق‌العاده جذاب، صمیمی، محترمانه و کاملاً مسلط صحبت کنید.

قوانین حیاتی:
۱. از تعارفات طولانی، سلام و علیک‌های تکراری و روده‌درازی در ابتدای پیام‌ها کاملاً خودداری کنید. مستقیم و بدون فوت وقت به سراغ اصل مطلب و حل مسئله کاربر بروید.
۲. پاسخ‌ها را با ساختاری بسیار تمیز، استفاده از بولت‌پوینت‌ها و ایموجی‌های کاملاً مرتبط تزیین کنید.
۳. فقط و فقط به زبان فارسی روان، بدون غلط املایی بنویسید.
۴. در پاسخ‌های خود حتماً از تگ‌های HTML تلگرام استفاده کنید؛ مثلاً کلمات کلیدی، تیترها و بخش‌های مهم را داخل تگ <b> قرار دهید (مانند <b>متن مهم</b>) تا پیام‌ها فوق‌العاده شیک و خوانا شوند. هرگز از ستاره (*) یا آندرلاین (_) استفاده نکنید چون تلگرام پیام را ارسال نمی‌کند و ارور می‌دهد.
"""

# ==================== بخش دیتابیس ایمن و ضد قفل ====================
def get_db_connection():
    # فعال کردن تایم‌اوت ۳۰ ثانیه‌ای برای منتظر ماندن در صورت مشغول بودن دیتابیس
    conn = sqlite3.connect(DATABASE_NAME, timeout=30.0)
    # فعال کردن حالت WAL برای پشتیبانی از خواندن و نوشتن همزمان بدون قفل شدن
    conn.execute('PRAGMA journal_mode=WAL;')
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            msg_count INTEGER DEFAULT 0,
            has_joined INTEGER DEFAULT 0,
            is_premium INTEGER DEFAULT 0,
            join_date DATE DEFAULT CURRENT_DATE,
            expire_date TEXT
        )
    ''')
    conn.commit()
    conn.close()

def check_user(user_id, username):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # پیدا کردن کاربر
    cursor.execute("SELECT msg_count, has_joined, is_premium, expire_date FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()

    # اگر کاربر در دیتابیس نبود، با INSERT OR IGNORE ذخیره می‌کنیم تا ارور تکراری (UNIQUE constraint) نگیریم
    if not user:
        cursor.execute("INSERT OR IGNORE INTO users (user_id, username, msg_count, has_joined, is_premium, expire_date) VALUES (?, ?, 0, 0, 0, NULL)", (user_id, username))
        conn.commit()
        conn.close()
        return 0, 0, 0, None

    msg_count, has_joined, is_premium, expire_date = user[0], user[1], user[2], user[3]
    
    # بررسی انقضای حساب ویژه کاربران
    if is_premium == 1 and expire_date:
        try:
            exp_dt = datetime.strptime(expire_date, "%Y-%m-%d %H:%M:%S")
            if datetime.now() > exp_dt:
                cursor.execute("UPDATE users SET is_premium = 0, expire_date = NULL WHERE user_id = ?", (user_id,))
                conn.commit()
                is_premium = 0
                expire_date = None
        except Exception:
            pass

    conn.close()
    return msg_count, has_joined, is_premium, expire_date

def increment_msg(user_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET msg_count = msg_count + 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"⚠️ Error incrementing message: {e}")

def set_joined(user_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET has_joined = 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"⚠️ Error setting joined status: {e}")

def make_premium(user_id, months):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        expire_dt = datetime.now() + timedelta(days=30 * months)
        expire_str = expire_dt.strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("UPDATE users SET is_premium = 1, expire_date = ? WHERE user_id = ?", (expire_str, user_id))
        conn.commit()
        conn.close()
        return expire_str
    except Exception as e:
        print(f"⚠️ Error making user premium: {e}")
        return str(datetime.now() + timedelta(days=30 * months))

def check_channel_join(user_id):
    for channel in CHANNELS:
        try:
            member = bot.get_chat_member(channel, user_id)
            if member.status in ['left', 'kicked']:
                return False
        except Exception:
            # اگر کانالی موقتاً در دسترس نبود یا آیدی خطا داد، تایید می‌کنیم تا کاربر معطل نشود
            return False
    return True

# ==================== دکمه‌ها و کیبوردها ====================
def get_join_keyboard():
    markup = types.InlineKeyboardMarkup()
    for i, ch in enumerate(CHANNELS, 1):
        btn = types.InlineKeyboardButton(text=f"📢 عضویت در کانال {i}", url=f"https://t.me/{ch.replace('@', '')}")
        markup.add(btn)
    check_btn = types.InlineKeyboardButton(text=f"🔄 بررسی عضویت", callback_data="check_join")
    markup.add(check_btn)
    return markup

def get_plans_keyboard():
    markup = types.InlineKeyboardMarkup()
    btn1 = types.InlineKeyboardButton(text=f"⭐️ ۱ ماهه ({PRICE_1_MONTH} تومان)", callback_data="buy_1")
    btn2 = types.InlineKeyboardButton(text=f"⭐️ ۳ ماهه ({PRICE_3_MONTHS} تومان)", callback_data="buy_3")
    btn3 = types.InlineKeyboardButton(text=f"⭐️ ۶ ماهه ({PRICE_6_MONTHS} تومان)", callback_data="buy_6")
    markup.add(btn1, btn2)
    markup.add(btn3)
    return markup

# ==================== ارتباط ایمن با هوش مصنوعی ====================
def call_gemini_ai_direct(user_message):
    if not GROQ_API_KEY:
        return "❌ هیچ کلید API فعالی برای ربات ست نشده است."
        
    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "llama-3.1-8b-instant",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message}
            ]
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        
        if response.status_code == 200:
            result = response.json()
            return result['choices'][0]['message']['content']
        elif response.status_code == 429:
            return "⚠️ ظرفیت موقت ربات پر شده است. لطفاً یک دقیقه دیگر مجدداً تلاش کنید."
        else:
            return "❌ خطای موقت در دریافت پاسخ هوش مصنوعی. لطفاً دوباره پیام دهید."
            
    except Exception as e:
        print(f"⚠️ Error calling AI: {e}")
        return "❌ خطای غیرمنتظره در سرور رخ داد. لطفاً چند لحظه بعد مجدداً پیام خود را ارسال کنید."

# ==================== توابع ارسال پیام ایمن (جلوگیری از کرش) ====================
def safe_send_message(chat_id, text, parse_mode="HTML", reply_markup=None, reply_to_message_id=None):
    try:
        return bot.send_message(chat_id, text, parse_mode=parse_mode, reply_markup=reply_markup, reply_to_message_id=reply_to_message_id)
    except Exception as e:
        print(f"⚠️ Telegram blocked or failed to send message to {chat_id}: {e}")
        return None

def safe_send_photo(chat_id, photo_id, caption=None, reply_markup=None):
    try:
        return bot.send_photo(chat_id, photo_id, caption=caption, reply_markup=reply_markup)
    except Exception as e:
        print(f"⚠️ Telegram failed to send photo to {chat_id}: {e}")
        return None

# ==================== هندلرهای ربات ====================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    check_user(user_id, username)

    welcome_text = (
        "<b>سلام و درود.</b>\n"
        "به دستیار هوش مصنوعی خوش آمدید.\n\n"
        "شما می‌توانید ۳ پیام به صورت کاملاً رایگان ارسال کنید. "
        "پس از آن، جهت ادامه نیاز به عضویت در کانال‌های حامی ربات خواهید داشت. لطفاً سوال خود را بپرسید:"
    )
    safe_send_message(message.chat.id, welcome_text, reply_to_message_id=message.message_id)

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID:
        return

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM users WHERE is_premium = 1")
        premium_users = cursor.fetchone()[0]
        cursor.execute("SELECT join_date, COUNT(*) FROM users GROUP BY join_date ORDER BY join_date DESC LIMIT 5")
        rows = cursor.fetchall()
        conn.close()

        growth_report = ""
        for row in rows:
            growth_report += f"📅 تاریخ: {row[0]} -> 👤 {row[1]} عضو جدید\n"
    except Exception as e:
        print(f"⚠️ Admin panel db error: {e}")
        total_users, premium_users, growth_report = 0, 0, "خطای دریافت اطلاعات"

    report = (
        f"<b>📊 داشبورد مدیریت سلطان</b>\n\n"
        f"👥 کل کاربران: {total_users} نفر\n"
        f"⭐ کاربران ویژه فعال: {premium_users} نفر\n\n"
        f"📈 آمار رشد ثبت‌نام (۵ روز اخیر):\n"
        f"{growth_report if growth_report else 'هنوز آماری ثبت نشده است.'}"
    )
    safe_send_message(message.chat.id, report, reply_to_message_id=message.message_id)

# ==================== مدیریت رویدادهای دکمه شیشه‌ای (Callback) ====================
@bot.callback_query_handler(func=lambda call: True)
def callback_queries(call):
    user_id = call.from_user.id
    
    if call.data == "check_join":
        if check_channel_join(user_id):
            set_joined(user_id)
            try:
                bot.answer_callback_query(call.id, "✅ عضویت شما تایید شد!", show_alert=True)
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                      text="✅ عضویت شما با موفقیت تایید شد. اکنون ۱۰ سهمیه پیام رایگان جدید به شما تعلق گرفت. سوال خود را بفرستید:", parse_mode="HTML")
            except Exception:
                pass
        else:
            try:
                bot.answer_callback_query(call.id, "❌ شما هنوز در همه کانال‌ها عضو نشده‌اید!", show_alert=True)
            except Exception:
                pass
            
    elif call.data.startswith("buy_"):
        months = int(call.data.split("_")[1])
        price = PRICE_1_MONTH if months == 1 else (PRICE_3_MONTHS if months == 3 else PRICE_6_MONTHS)
        
        payment_text = (
            f"<b>💳 دستورالعمل پرداخت اشتراک {months} ماهه:</b>\n\n"
            f"💵 مبلغ قابل پرداخت: {price} تومان\n"
            f"📌 شماره کارت واریز:\n<code>{CARD_NUMBER}</code>\n"
            f"👤 به نام: {CARD_NAME}\n\n"
            f"⚠️ مهم: لطفا پس از واریز مبلغ، عکس فیش یا رسید تراکنش خود را دقیقاً به همین ربات ارسال کنید تا تایید شود."
        )
        msg = safe_send_message(call.message.chat.id, payment_text)
        if msg:
            bot.register_next_step_handler(msg, receive_receipt, months)

    elif call.data.startswith("approve_"):
        if call.from_user.id != ADMIN_ID:
            return
        data_parts = call.data.split("_")
        target_user_id = int(data_parts[1])
        months = int(data_parts[2])
        expire_str = make_premium(target_user_id, months)
        
        congrats_text = (
            f"🎉 <b>تبریک! اشتراک {months} ماهه شما با موفقیت فعال شد.</b>\n"
            f"📅 تاریخ انقضا: {expire_str}\n\n"
            f"اکنون می‌توانید بدون هیچ محدودیتی با قوی‌ترین هوش مصنوعی به گفتگو بپردازید!"
        )
        safe_send_message(target_user_id, congrats_text)
            
        try:
            bot.answer_callback_query(call.id, "✅ اشتراک کاربر با موفقیت فعال شد.", show_alert=True)
            bot.edit_message_caption(chat_id=ADMIN_ID, message_id=call.message.message_id, caption=call.message.caption + "\n\n🟢 وضعیت: تایید شد.")
        except Exception:
            pass

    elif call.data.startswith("reject_"):
        if call.from_user.id != ADMIN_ID:
            return
        data_parts = call.data.split("_")
        target_user_id = int(data_parts[1])
        
        reject_text = "❌ فیش واریزی شما توسط ادمین تایید نشد. در صورت بروز خطا یا اشتباه در تراکنش، لطفاً با پشتیبانی در ارتباط باشید."
        safe_send_message(target_user_id, reject_text)
            
        try:
            bot.answer_callback_query(call.id, "🔴 درخواست رد شد.", show_alert=True)
            bot.edit_message_caption(chat_id=ADMIN_ID, message_id=call.message.message_id, caption=call.message.caption + "\n\n🔴 وضعیت: رد شد.")
        except Exception:
            pass

# ==================== فرآیند فیش واریزی ====================
def receive_receipt(message, months):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    if message.content_type != 'photo':
        bot.reply_to(message, "❌ لطفا رسید پرداخت را فقط به صورت عکس (تصویر) ارسال کنید. جهت انتخاب دوباره دکمه زیر را لمس کنید:", reply_markup=get_plans_keyboard())
        return

    photo_id = message.photo[-1].file_id
    admin_markup = types.InlineKeyboardMarkup()
    btn_approve = types.InlineKeyboardButton(text="✅ تایید و فعال‌سازی", callback_data=f"approve_{user_id}_{months}")
    btn_reject = types.InlineKeyboardButton(text="❌ رد تراکنش", callback_data=f"reject_{user_id}")
    admin_markup.add(btn_approve, btn_reject)
    
    safe_send_photo(
        ADMIN_ID, 
        photo_id, 
        caption=f"🔔 فیش واریزی جدید!\n\n👤 کاربر: @{username} (آیدی: {user_id})\n⭐️ متقاضی اشتراک: {months} ماهه",
        reply_markup=admin_markup
    )
    
    bot.reply_to(message, "✅ فیش واریزی شما برای ادمین ارسال شد. پس از بررسی و تایید نهایی، اشتراک شما فعال شده و از طریق همین ربات به شما اطلاع‌رسانی می‌شود.")

# ==================== دریافت و مدیریت پیام‌ها ====================
@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"

    msg_count, has_joined, is_premium, expire_date = check_user(user_id, username)

    # کاربران پرمیوم محدودیت پیام ندارند
    if is_premium:
        try:
            bot.send_chat_action(message.chat.id, 'typing')
        except Exception:
            pass
        ai_response = call_gemini_ai_direct(message.text)
        safe_send_message(message.chat.id, ai_response, reply_to_message_id=message.message_id)
        return

    # ۳ پیام رایگان اول
    if msg_count < 3:
        increment_msg(user_id)
        try:
            bot.send_chat_action(message.chat.id, 'typing')
        except Exception:
            pass
        ai_response = call_gemini_ai_direct(message.text)
        safe_send_message(message.chat.id, ai_response, reply_to_message_id=message.message_id)
        return

    # بررسی جوین شدن برای باز شدن ۱۰ سهمیه بعدی
    if not has_joined:
        if check_channel_join(user_id):
            set_joined(user_id)
            increment_msg(user_id)
            try:
                bot.send_chat_action(message.chat.id, 'typing')
            except Exception:
                pass
            ai_response = call_gemini_ai_direct(message.text)
            safe_send_message(message.chat.id, f"✅ عضویت شما تایید شد (۱۰ سهمیه جدید).\n\n{ai_response}", reply_to_message_id=message.message_id)
        else:
            markup = get_join_keyboard()
            safe_send_message(message.chat.id, "⚠️ سهمیه ۳ پیام اول شما تمام شد. برای باز شدن ۱۰ سهمیه رایگان بعدی، لطفاً در کانال‌های زیر عضو شوید:", reply_markup=markup, reply_to_message_id=message.message_id)
        return

    # استفاده از ۱۰ سهمیه رایگان دوم (تا سقف ۱۳ پیام کل)
    if msg_count < 13:
        increment_msg(user_id)
        try:
            bot.send_chat_action(message.chat.id, 'typing')
        except Exception:
            pass
        ai_response = call_gemini_ai_direct(message.text)
        safe_send_message(message.chat.id, ai_response, reply_to_message_id=message.message_id)
    else:
        # اتمام کل سهمیه‌ها و هدایت به خرید پلان
        markup = get_plans_keyboard()
        safe_send_message(message.chat.id, "❌ سهمیه پیام‌های رایگان شما به پایان رسیده است.\n\nبرای خرید اشتراک و دسترسی نامحدود به هوش مصنوعی با سرعت بالا، لطفا یکی از پلان‌های زیر را انتخاب کنید:", reply_markup=markup, reply_to_message_id=message.message_id)

# ==================== نقطه ورود و استارت پروژه ====================
if __name__ == '__main__':
    # ۱. ایجاد و آماده‌سازی دیتابیس
    init_db()
    
    # ۲. راه‌اندازی ربات تلگرام در یک ترید پس‌زمینه جداگانه
    # مقدار skip_pending=True باعث می‌شود پیام‌های ارسال شده در زمان خاموشی ربات یکجا لود نشوند و ربات هنگ نکند
    bot_thread = threading.Thread(target=bot.infinity_polling, kwargs={"skip_pending": True})
    bot_thread.daemon = True
    bot_thread.start()
    
    print("🚀 Bot is running in background thread...")
    
    # ۳. اجرای وب‌سرور روی ترید اصلی جهت پورت بایندینگ رندر
    print("🌐 Launching Flask Web Server...")
    run_web_server()
