import sqlite3
import requests
import telebot
from telebot import types

# ==================== تنظیمات اصلی ربات ====================
# توکن ربات تلگرامت را که از @BotFather گرفتی اینجا بذار
BOT_TOKEN = "8566783342:AAGgME6Rn2011ZT4Q-B6RiJR8AFDytUdFjo"

# کلید API که از سایت Groq گرفتی را اینجا بگذار (باید با gsk_ شروع شود)
GROQ_API_KEY = "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"
# آیدی عددی تلگرام خودت را اینجا بذار تا ادمین اصلی بشوی
ADMIN_ID = 6822309164

# آیدی کانال‌هایی که کاربرها باید قبل استفاده عضو شوند
CHANNELS = ["@MRAHMAD_1", "@GEMINIFARSI"]
# ==========================================================

bot = telebot.TeleBot(BOT_TOKEN)

SYSTEM_PROMPT = """
شما یک دستیار هوشمند، محترم، مودب و بسیار حرفه‌ای هستید.
لحن شما باید کاملاً متین و باوقار باشد. از ابراز صمیمیت بیش از حد،
استفاده از لغات عامیانه یا لحن خیلی چت‌گونه خودداری کنید و پاسخ‌ها را
به صورت شمرده، علمی، کاربردی و با احترام کامل به کاربر ارائه دهید.
"""

def init_db():
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            msg_count INTEGER DEFAULT 0,
            has_joined INTEGER DEFAULT 0,
            is_premium INTEGER DEFAULT 0,
            join_date DATE DEFAULT CURRENT_DATE
        )
    ''')
    conn.commit()
    conn.close()

def check_user(user_id, username):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT msg_count, has_joined, is_premium FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()

    if not user:
        cursor.execute("INSERT INTO users (user_id, username, msg_count, has_joined, is_premium) VALUES (?, ?, 0, 0, 0)", (user_id, username))
        conn.commit()
        conn.close()
        return 0, 0, 0

    conn.close()
    return user[0], user[1], user[2]

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

def call_gemini_ai_direct(user_message):
    if not GROQ_API_KEY or GROQ_API_KEY.startswith("اینجا_"):
        return "❌ هیچ کلید API فعالی برای ربات ست نشده است."
        
    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # استفاده از قوی‌ترین مدل متن‌باز Groq یعنی llama-3.3-70b-versatile
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
        f"⭐ کاربران ویژه: {premium_users} نفر\n\n"
        f"📈 آمار رشد ثبت‌نام (۵ روز اخیر):\n"
        f"{growth_report if growth_report else 'هنوز آماری ثبت نشده است.'}"
    )
    bot.reply_to(message, report, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "check_join")
def callback_check_join(call):
    user_id = call.from_user.id
    if check_channel_join(user_id):
        set_joined(user_id)
        bot.answer_callback_query(call.id, "✅ عضویت شما تایید شد!", show_alert=True)
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                              text="✅ عضویت شما با موفقیت تایید شد. اکنون ۱۰ سهمیه پیام رایگان جدید به شما تعلق گرفت. سوال خود را بفرستید:")
    else:
        bot.answer_callback_query(call.id, "❌ شما هنوز در همه کانال‌ها عضو نشده‌اید!", show_alert=True)

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"

    msg_count, has_joined, is_premium = check_user(user_id, username)

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
        bot.reply_to(message, "❌ سهمیه پیام‌های رایگان شما به پایان رسیده است.\n\nبرای ادامه استفاده و دسترسی نامحدود به هوش مصنوعی، لطفاً نسبت به خرید اشتراک اقدام فرمایید.")

if __name__ == '__main__':
    init_db()
    print("🚀 ربات ضد قفل و فوق‌العاده سریع سلطان (مجهز به موتور Groq Llama 3.3) با موفقیت روشن شد!")
    bot.infinity_polling()
