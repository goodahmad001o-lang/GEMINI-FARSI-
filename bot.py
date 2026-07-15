import os
import sqlite3
from flask import Flask, request
import telebot
from telebot import types
import groq

# --- تنظیمات اصلی ربات ---
BOT_TOKEN = "8691005129:AAG7R-6YqkTKPVwADyDBFPE-wwyRHYRz6VA"
GROQ_API_KEY = "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"
CHANNEL_ID = "@gminifarsi"  # آیدی کانال خودت
CHANNEL_LINK = "https://t.me/gemini_farsi_channel" # لینک کانال تو
ADMIN_ID = 6822309164  # آیدی عددی تلگرام خودت

# آدرس اختصاصی ربات شما روی رندر (حتماً ته آن اسلش نگذارید)
# مثال: https://gemini-farsi-bot.onrender.com
RENDER_APP_URL = "https://gemini-farsi-bot.onrender.com" 

# راه اندازی ربات و کلاینت گروک
bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
groq_client = groq.Groq(api_key=GROQ_API_KEY)

# وب‌سرور فلاسک
app = Flask(__name__)

# --- مسیر اصلی برای تست زنده بودن سرور ---
@app.route('/')
def home():
    return "Bot is alive and running with Webhook!", 200

# --- مسیر دریافت پیام‌ها از تلگرام (Webhook endpoint) ---
@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def get_message():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "OK", 200
    return "Forbidden", 403

# --- راه اندازی دیتابیس برای ذخیره اطلاعات ---
def init_db():
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            referred_by INTEGER,
            referrals_count INTEGER DEFAULT 0,
            joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

init_db()

# --- توابع کمکی دیتابیس ---
def get_user(user_id):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def add_user(user_id, username, referred_by=None):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (user_id, username, referred_by) VALUES (?, ?, ?)",
            (user_id, username, referred_by)
        )
        if referred_by:
            cursor.execute(
                "UPDATE users SET referrals_count = referrals_count + 1 WHERE user_id = ?",
                (referred_by,)
            )
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    conn.close()

def get_stats():
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users WHERE referrals_count >= 10")
    unlocked_users = cursor.fetchone()[0]
    conn.close()
    return total_users, unlocked_users

# --- بررسی عضویت در کانال ---
def check_sub(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_ID, user_id)
        if member.status in ['creator', 'administrator', 'member']:
            return True
        return False
    except Exception:
        return True

# --- دکمه‌های اصلی کیبورد ---
def main_keyboard(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🧠 چت با هوش مصنوعی", "👥 زیرمجموعه‌گیری (دعوت)")
    markup.row("📊 وضعیت حساب من")
    if user_id == ADMIN_ID:
        markup.row("⚙️ پنل مدیریت")
    return markup

# --- شروع کار ربات (/start) ---
@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.from_user.id
    username = message.from_user.username or "NoUsername"
    
    referred_by = None
    start_args = message.text.split()
    if len(start_args) > 1:
        try:
            referred_by = int(start_args[1])
            if referred_by == user_id:
                referred_by = None
        except ValueError:
            pass

    user_exists = get_user(user_id)
    if not user_exists:
        add_user(user_id, username, referred_by)
        if referred_by:
            try:
                bot.send_message(referred_by, f"🎉 یک کاربر جدید با لینک شما عضو ربات شد! امتیاز شما افزایش یافت.")
            except Exception:
                pass

    user_first_name = message.from_user.first_name or "دوست"
    welcome_text = (
        f"سلام {user_first_name} عزیز به ربات هوش مصنوعی پیشرفته خوش آمدید! ⚡\n\n"
        f"این ربات به قوی‌ترین مدل‌های هوش مصنوعی دنیا متصل است.\n"
        f"برای استفاده رایگان و نامحدود، کافیست **۱۰ نفر** از دوستانت را به ربات دعوت کنی!"
    )
    bot.send_message(user_id, welcome_text, reply_markup=main_keyboard(user_id), parse_mode='Markdown')

# --- بخش دعوت و رفرال ---
@bot.message_handler(func=lambda msg: msg.text == "👥 زیرمجموعه‌گیری (دعوت)")
def referral_info(message):
    user_id = message.from_user.id
    user = get_user(user_id)
    ref_count = user[3] if user else 0
    bot_info = bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
    
    text = (
        f"👥 **سیستم دعوت و کسب امتیاز رایگان**\n\n"
        f"🔗 لینک دعوت اختصاصی شما:\n`{ref_link}`\n\n"
        f"📈 تعداد دعوت‌های شما تا الان: **{ref_count} از ۱۰**\n\n"
        f"به محض اینکه ۱۰ نفر با لینک شما وارد ربات شوند، قفل چت با هوش مصنوعی برای همیشه برای شما باز می‌شود! 🎉"
    )
    bot.send_message(user_id, text, parse_mode='Markdown')

# --- بخش وضعیت حساب ---
@bot.message_handler(func=lambda msg: msg.text == "📊 وضعیت حساب من")
def account_status(message):
    user_id = message.from_user.id
    user = get_user(user_id)
    ref_count = user[3] if user else 0
    status = "✅ فعال (دسترسی نامحدود)" if ref_count >= 10 else "❌ قفل (نیاز به دعوت از دوستان)"
    
    text = (
        f"📊 **وضعیت حساب کاربری شما**\n\n"
        f"👤 شناسه کاربری: `{user_id}`\n"
        f"👥 تعداد دعوت‌های ثبت‌شده: **{ref_count}**\n"
        f"⚙️ وضعیت دسترسی به هوش مصنوعی: {status}\n"
    )
    bot.send_message(user_id, text, parse_mode='Markdown')

# --- پنل مدیریت (مخصوص ادمین) ---
@bot.message_handler(func=lambda msg: msg.text == "⚙️ پنل مدیریت" and msg.from_user.id == ADMIN_ID)
def admin_panel(message):
    total, unlocked = get_stats()
    
    bar_total = "🟩" * min(10, max(1, total // 10 if total > 0 else 0))
    bar_unlocked = "🟦" * min(10, max(1, unlocked // 10 if unlocked > 0 else 0))
    
    text = (
        f"📊 **پنل مدیریت هوشمند ربات**\n\n"
        f"👥 کل کاربران ثبت شده: **{total}**\n"
        f"📈 رشد کل: {bar_total}\n\n"
        f"🔓 کاربران فعال (دعوت بالای ۱۰ نفر): **{unlocked}**\n"
        f"📈 رشد فعالین: {bar_unlocked}\n\n"
        f"برای ارسال پیام همگانی به اعضا، پیام خود را با فرمت زیر بفرستید:\n"
        f"`/sendall متن پیام شما`"
    )
    bot.send_message(ADMIN_ID, text, parse_mode='Markdown')

# --- ارسال پیام همگانی توسط ادمین ---
@bot.message_handler(commands=['sendall'])
def send_all_cmd(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    parts = message.text.split(" ", 1)
    if len(parts) < 2:
        bot.send_message(ADMIN_ID, "❌ لطفا متن پیام را وارد کنید. مثال: `/sendall سلام دوستان`", parse_mode='Markdown')
        return
    
    broadcast_msg = parts[1]
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    conn.close()
    
    success = 0
    for u in users:
        try:
            bot.send_message(u[0], broadcast_msg)
            success += 1
        except Exception:
            pass
            
    bot.send_message(ADMIN_ID, f"📢 پیام همگانی با موفقیت به {success} کاربر ارسال شد.")

# --- بخش اصلی: چت با هوش مصنوعی ---
@bot.message_handler(func=lambda msg: msg.text == "🧠 چت با هوش مصنوعی" or not msg.text.startswith("/"))
def ai_chat(message):
    user_id = message.from_user.id
    
    if not check_sub(user_id):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("عضویت در کانال ما 📢", url=CHANNEL_LINK))
        bot.send_message(
            user_id, 
            "❌ برای استفاده از ربات، ابتدا باید در کانال رسمی ما عضو شوید. پس از عضویت دوباره به ربات پیام دهید.", 
            reply_markup=markup
        )
        return

    user = get_user(user_id)
    ref_count = user[3] if user else 0
    
    if ref_count < 10:
        bot_info = bot.get_me()
        ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
        warning_text = (
            f"🔒 **دسترسی محدود است!**\n\n"
            f"برای باز شدن چت رایگان با هوش مصنوعی، باید **۱۰ نفر** را دعوت کنی.\n"
            f"تا الان **{ref_count}** نفر را دعوت کرده‌ای.\n\n"
            f"🔗 لینک دعوت اختصاصی تو:\n`{ref_link}`\n\n"
            f"این لینک را برای دوستانت بفرست؛ به محض تکمیل ۱۰ نفر، سیستم به طور خودکار چت را برایت باز می‌کند!"
        )
        bot.send_message(user_id, warning_text, parse_mode='Markdown')
        return

    if message.text == "🧠 چت با هوش مصنوعی":
        bot.send_message(user_id, "🤖 قفل حساب شما باز است! هر سوالی داری بنویس تا با هوش مصنوعی پاسخ دهم:")
        return

    bot.send_chat_action(user_id, 'typing')

    try:
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "تو یک دستیار هوش مصنوعی فوق‌العاده باهوش، صمیمی، خوش‌برخورد و کاملاً مسلط به زبان فارسی هستی. "
                        "لحن تو باید کاملاً طبیعی، روان، گرم و بدون ترجمه‌های خشک و ماشینی باشد. "
                        "پاسخ‌هایت را کاربرپسند و دقیق بنویس. اصلاً از جملات عجیب و غریب انگلیسی به فارسی استفاده نکن."
                    )
                },
                {
                    "role": "user",
                    "content": message.text,
                }
            ],
            model="llama3-8b-8192",
        )
        
        response_text = chat_completion.choices[0].message.content
        bot.send_message(user_id, response_text, parse_mode='Markdown')
        
    except Exception as e:
        try:
            bot.send_message(user_id, response_text)
        except Exception:
            bot.send_message(user_id, "❌ متاسفانه در ارتباط با هوش مصنوعی خطایی رخ داد. لطفا دوباره تلاش کنید.")

# اجرای فلاسک و تنظیم وب‌هوک
if __name__ == '__main__':
    # حذف پاولینگ‌های قدیمی و فعال‌سازی وب‌هوک جدید روی تلگرام
    bot.remove_webhook()
    bot.set_webhook(url=f"{RENDER_APP_URL}/{BOT_TOKEN}")
    print("Webhook successfully set!")
    
    # اجرای وب‌سرور فلاسک به صورت مستقیم
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
