import sqlite3
import requests
import telebot
from telebot import types
from datetime import datetime, timedelta
import threading
import time
from flask import Flask
import os

# ==================== تنظیمات اصلی ربات ====================
BOT_TOKEN = "8691005129:AAEUnoQYkGs1_tLRLlrSrOhXjjxL10AWpKI"
GROQ_API_KEY = "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"
ADMIN_ID = 6822309164
CHANNELS = ["@MRAHMAD_1", "@GMINIFARSI"]

# مشخصات کارت بانکی شما برای واریز کاربرها
CARD_NUMBER = "6037697438262914"  # شماره کارت خودت را بگذار
CARD_NAME = "احمد ...."            #حسین پویان      
PRICE_1_MONTH = "69,000"
PRICE_3_MONTHS = "159,000"
PRICE_6_MONTHS = "279,000"

# تعداد دعوتی که کاربر نیاز دارد تا سهمیه رایگان جدید بگیرد
REQUIRED_INVITES = 5
# تعداد پیام هدیه بعد از دعوت موفق تعداد بالا
GIFT_MESSAGES = 10
# ==========================================================

# ساخت یک وب‌سرور کوچک برای فریب دادن رندر و حل مشکل پورت
app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

bot = telebot.TeleBot(BOT_TOKEN)

SYSTEM_PROMPT = """
شما یک دستیار هوشمند، محترم، مودب و بسیار حرفه‌ای هستید.
لحن شما باید کاملاً متین و باوقار باشد. از ابراز صمیمیت بیش از حد،
استفاده از لغات عامیانه یا لحن خیلی چت‌گونه خودداری کنید و پاسخ‌ها را
به صورت شمرده، علمی، کاربردی و با احترام کامل
"""

def init_db():
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    # اضافه کردن ستون تاریخ پایان اشتراک (expire_date)
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
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT msg_count, has_joined, is_premium, expire_date FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()

    if not user:
        cursor.execute("INSERT INTO users (user_id, username, msg_count, has_joined, is_premium, expire_date) VALUES (?, ?, 0, 0, 0, NULL)", (user_id, username))
        conn.commit()
        conn.close()
        return 0, 0, 0, None

    msg_count, has_joined, is_premium, expire_date = user[0], user[1], user[2], user[3]
    
    # بررسی انقضای اشتراک ویژه
    if is_premium == 1 and expire_date:
        try:
            exp_dt = datetime.strptime(expire_date, "%Y-%m-%d %H:%M:%S")
            if datetime.now() > exp_dt:
                # اشتراک تمام شده است؛ تبدیل کاربر به حالت عادی
                cursor.execute("UPDATE users SET is_premium = 0, expire_date = NULL WHERE user_id = ?", (user_id,))
                conn.commit()
                is_premium = 0
                expire_date = None
        except Exception:
            pass

    conn.close()
    return msg_count, has_joined, is_premium, expire_date

def increment_msg(user_id):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET msg_count = msg_count + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def set_joined(user_id):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET has_joined = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def make_premium(user_id, months):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    expire_dt = datetime.now() + timedelta(days=30 * months)
    expire_str = expire_dt.strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("UPDATE users SET is_premium = 1, expire_date = ? WHERE user_id = ?", (expire_str, user_id))
    conn.commit()
    conn.close()
    return expire_str

def check_channel_join(user_id):
    for channel in CHANNELS:
        try:
            member = bot.get_chat_member(channel, user_id)
            if member.status in ['left', 'kicked']:
                return False
        except Exception:
            return False
    return True

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
    markup.add(btn1)
    markup.add(btn2)
    markup.add(btn3)
    return markup

def call_gemini_ai_direct(user_message):
    if not GROQ_API_KEY or GROQ_API_KEY.startswith("اینجا_"):
        return "❌ هیچ کلید API فعالی برای ربات ست نشده است."
        
    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "llama-3.3-70b-versatile", 
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message}
            ]
        }
        
        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code == 200:
            result = response.json()
            return result['choices'][0]['message']['content']
        elif response.status_code == 429:
            return "⚠️ ظرفیت موقت ربات پر شده است. لطفاً یک دقیقه دیگر مجدداً تلاش کنید."
        else:
            return f"❌ خطای سرور (کد {response.status_code}):\n{response.text}"
            
    except Exception as e:
        return f"❌ خطایی در ارتباط با سرور رخ داد:\n{str(e)}"

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    check_user(user_id, username)

    welcome_text = (
        "سلام و درود.\n"
        "به دستیار هوش مصنوعی خوش آمدید.\n"
        "شما می‌توانید ۳ پیام به صورت کاملاً رایگان ارسال کنید. "
        "پس از آن، جهت ادامه نیاز به عضویت در کانال‌های حامی ربات خواهید داشت. لطفاً سوال خود را بپرسید:"
    )
    bot.reply_to(message, welcome_text)

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID:
        return

    conn = sqlite3.connect('bot_database.db')
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

    report = (
        f"📊 داشبورد مدیریت سلطان\n\n"
        f"👥 کل کاربران: {total_users} نفر\n"
        f"⭐ کاربران ویژه فعال: {premium_users} نفر\n\n"
        f"📈 آمار رشد ثبت‌نام (۵ روز اخیر):\n"
        f"{growth_report if growth_report else 'هنوز آماری ثبت نشده است.'}"
    )
    bot.reply_to(message, report, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: True)
def callback_queries(call):
    user_id = call.from_user.id
    
    if call.data == "check_join":
        if check_channel_join(user_id):
            set_joined(user_id)
            bot.answer_callback_query(call.id, "✅ عضویت شما تایید شد!", show_alert=True)
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                  text="✅ عضویت شما با موفقیت تایید شد. اکنون ۱۰ سهمیه پیام رایگان جدید به شما تعلق گرفت. سوال خود را بفرستید:")
        else:
            bot.answer_callback_query(call.id, "❌ شما هنوز در همه کانال‌ها عضو نشده‌اید!", show_alert=True)
            
    elif call.data.startswith("buy_"):
        months = int(call.data.split("_")[1])
        price = PRICE_1_MONTH if months == 1 else (PRICE_3_MONTHS if months == 3 else PRICE_6_MONTHS)
        
        payment_text = (
            f"💳 دستورالعمل پرداخت اشتراک {months} ماهه:\n\n"
            f"💵 مبلغ قابل پرداخت: {price} تومان\n"
            f"📌 شماره کارت واریز:\n`{CARD_NUMBER}`\n"
            f"👤 به نام: {CARD_NAME}\n\n"
            f"⚠️ مهم: لطفا پس از واریز مبلغ، عکس فیش یا رسید تراکنش خود را دقیقاً به همین ربات ارسال کنید تا تایید شود."
        )
        # ذخیره موقت پلانی که کاربر انتخاب کرده با تغییر موقت استیت در پیام بعدی
        msg = bot.send_message(call.message.chat.id, payment_text, parse_mode="Markdown")
        bot.register_next_step_handler(msg, receive_receipt, months)

def receive_receipt(message, months):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    if message.content_type != 'photo':
        msg = bot.reply_to(message, "❌ لطفا رسید پرداخت را فقط به صورت عکس (تصویر) ارسال کنید. جهت انتخاب دوباره دکمه زیر را لمس کنید:", reply_markup=get_plans_keyboard())
        return

    # ارسال فیش برای ادمین ربات جهت بررسی
    photo_id = message.photo[-1].file_id
    admin_markup = types.InlineKeyboardMarkup()
    btn_approve = types.InlineKeyboardButton(text="✅ تایید و فعال‌سازی", callback_data=f"approve_{user_id}_{months}")
    btn_reject = types.InlineKeyboardButton(text="❌ رد تراکنش", callback_data=f"reject_{user_id}")
    admin_markup.add(btn_approve, btn_reject)
    
    bot.send_photo(
        ADMIN_ID, 
        photo_id, 
        caption=f"🔔 فیش واریزی جدید!\n\n👤 کاربر: @{username} (آیدی: {user_id})\n⭐️ متقاضی اشتراک: {months} ماهه",
        reply_markup=admin_markup
    )
    
    bot.reply_to(message, "✅ فیش واریزی شما برای ادمین ارسال شد. پس از بررسی و تایید نهایی، اشتراک شما فعال شده و از طریق همین ربات به شما اطلاع‌رسانی می‌شود.")

# پردازش دکمه‌های تایید یا رد ادمین
@bot.callback_query_handler(func=lambda call: call.data.startswith("approve_") or call.data.startswith("reject_"))
def admin_actions(call):
    if call.from_user.id != ADMIN_ID:
        return
        
    data_parts = call.data.split("_")
    action = data_parts[0]
    target_user_id = int(data_parts[1])
    
    if action == "approve":
        months = int(data_parts[2])
        expire_str = make_premium(target_user_id, months)
        
        # اطلاع‌رسانی به کاربر
        congrats_text = (
            f"🎉 تبریک! اشتراک {months} ماهه شما با موفقیت فعال شد.\n"
            f"📅 تاریخ انقضا: {expire_str}\n\n"
            f"اکنون می‌توانید بدون هیچ محدودیتی با قوی‌ترین هوش مصنوعی به گفتگو بپردازید!"
        )
        try:
            bot.send_message(target_user_id, congrats_text)
        except Exception:
            pass
            
        bot.answer_callback_query(call.id, "✅ اشتراک کاربر با موفقیت فعال شد.", show_alert=True)
        bot.edit_message_caption(chat_id=ADMIN_ID, message_id=call.message.message_id, caption=call.message.caption + "\n\n🟢 وضعیت: تایید شد و اشتراک فعال گردید.")
        
    elif action == "reject":
        reject_text = "❌ فیش واریزی شما توسط ادمین تایید نشد. در صورت بروز خطا یا اشتباه در تراکنش، لطفاً با پشتیبانی در ارتباط باشید."
        try:
            bot.send_message(target_user_id, reject_text)
        except Exception:
            pass
            
        bot.answer_callback_query(call.id, "🔴 درخواست رد شد.", show_alert=True)
        bot.edit_message_caption(chat_id=ADMIN_ID, message_id=call.message.message_id, caption=call.message.caption + "\n\n🔴 وضعیت: رد شد.")

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"

    msg_count, has_joined, is_premium, expire_date = check_user(user_id, username)

    if is_premium:
        bot.send_chat_action(message.chat.id, 'typing')
        ai_response = call_gemini_ai_direct(message.text)
        bot.reply_to(message, ai_response)
        return

    if msg_count < 3:
        increment_msg(user_id)
        bot.send_chat_action(message.chat.id, 'typing')
        ai_response = call_gemini_ai_direct(message.text)
        bot.reply_to(message, ai_response)
        return

    if not has_joined:
        if check_channel_join(user_id):
            set_joined(user_id)
            increment_msg(user_id)
            bot.send_chat_action(message.chat.id, 'typing')
            ai_response = call_gemini_ai_direct(message.text)
            bot.reply_to(message, f"✅ عضویت شما تایید شد (۱۰ سهمیه جدید).\n\n{ai_response}")
        else:
            markup = get_join_keyboard()
            bot.reply_to(message, "⚠️ سهمیه ۳ پیام اول شما تمام شد. برای باز شدن ۱۰ سهمیه رایگان بعدی، لطفاً در کانال‌های زیر عضو شوید:", reply_markup=markup)
        return

    if msg_count < 13:
        increment_msg(user_id)
        bot.send_chat_action(message.chat.id, 'typing')
        ai_response = call_gemini_ai_direct(message.text)
        bot.reply_to(message, ai_response)
    else:
        markup = get_plans_keyboard()
        bot.reply_to(message, "❌ سهمیه پیام‌های رایگان شما به پایان رسیده است.\n\nبرای خرید اشتراک و دسترسی نامحدود به هوش مصنوعی با سرعت بالا، لطفا یکی از پلان‌های زیر را انتخاب کنید:", reply_markup=markup)

if __name__ == '__main__':
    init_db()
    
    # اول وب‌سرور را روی ترید مجزا استارت می‌زنیم تا رندر معطل نشود
    server_thread = threading.Thread(target=run_web_server)
    server_thread.daemon = True
    server_thread.start()
    
    import time
    time.sleep(2) # دو ثانیه صبر می‌کنیم تا پورت کاملاً باز و آماده شود
    
    print("🚀 ربات هوشمند با سیستم دعوت و کارت‌به‌کارت سلطان فعال شد!")
    bot.infinity_polling()
