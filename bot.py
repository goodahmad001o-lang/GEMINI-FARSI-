import os
import sqlite3
from flask import Flask, request, jsonify, render_template_string
import telebot
from telebot import types
import groq

# --- تنظیمات اصلی ربات ---
BOT_TOKEN = "8691005129:AAG7R-6YqkTKPVwADyDBFPE-wwyRHYRz6VA"
GROQ_API_KEY = "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"
CHANNEL_ID = "@GMINIFARSI"
CHANNEL_LINK = "https://t.me/gemini_farsi_channel"
ADMIN_ID = 6822309164 # آیدی عددی تلگرام خودت

# آدرس سرور رندر شما (بدون اسلش در انتها)
RENDER_APP_URL = "https://gemini-farsi-bot.onrender.com"

# راه اندازی ربات و کلاینت گروک
bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
groq_client = groq.Groq(api_key=GROQ_API_KEY)

app = Flask(__name__)

# --- دیتابیس موقت در حافظه برای متن و لینک تبلیغات بالای صفحه ---
# ادمین می‌تواند این مقادیر را تغییر دهد
AD_TEXT = "🔥 اسپانسر امروز: بهترین کانال آموزش برنامه نویسی ایران! عضو شوید"
AD_LINK = "https://t.me/your_sponsor_channel"

# --- راه اندازی دیتابیس کاربران ---
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

# --- قالب گرافیکی صفحه وب مینی‌اپ (HTML + CSS + JS) ---
WEB_APP_HTML = """
<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>هوش مصنوعی جیمنای فارسی</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: Tahoma, Arial, sans-serif; }
        body { background-color: #121212; color: #fff; display: flex; flex-direction: column; height: 100vh; overflow: hidden; }
        
        /* بنر تبلیغاتی متحرک و شیک بالای صفحه */
        .ad-banner {
            background: linear-gradient(45deg, #ff416c, #ff4b2b);
            color: white;
            text-align: center;
            padding: 10px;
            font-size: 13px;
            font-weight: bold;
            text-decoration: none;
            display: block;
            box-shadow: 0 4px 10px rgba(0,0,0,0.3);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            z-index: 1000;
        }
        
        .chat-container { flex: 1; display: flex; flex-direction: column; overflow-y: auto; padding: 15px; }
        .message { margin-bottom: 15px; max-width: 80%; padding: 12px; border-radius: 15px; line-height: 1.5; font-size: 14px; }
        .user-msg { background-color: #0088cc; align-self: flex-start; border-bottom-left-radius: 2px; }
        .bot-msg { background-color: #1f1f1f; align-self: flex-end; border-bottom-right-radius: 2px; border: 1px solid #333; }
        
        .input-area { display: flex; padding: 10px; background-color: #1a1a1a; border-top: 1px solid #2d2d2d; }
        .input-area input { flex: 1; padding: 12px; border: none; border-radius: 25px; background-color: #2b2b2b; color: white; outline: none; font-size: 14px; padding-right: 15px; }
        .input-area button { background-color: #0088cc; border: none; color: white; padding: 10px 20px; margin-right: 10px; border-radius: 25px; cursor: pointer; font-weight: bold; }
    </style>
</head>
<body>

    <!-- بنر تبلیغاتی بالای صفحه وب اپ -->
    <a href="{{ ad_link }}" target="_blank" class="ad-banner">
        📢 {{ ad_text }}
    </a>

    <div class="chat-container" id="chatBox">
        <div class="message bot-msg">سلام! من هوش مصنوعی هستم. چطور می‌تونم کمکت کنم؟</div>
    </div>

    <div class="input-area">
        <input type="text" id="userInput" placeholder="سوالی داری بپرس...">
        <button onclick="sendMessage()">ارسال</button>
    </div>

    <script>
        function sendMessage() {
            const input = document.getElementById('userInput');
            const chatBox = document.getElementById('chatBox');
            const text = input.value.trim();
            if(!text) return;

            // اضافه کردن پیام کاربر به صفحه
            chatBox.innerHTML += `<div class="message user-msg">${text}</div>`;
            input.value = '';
            chatBox.scrollTop = chatBox.scrollHeight;

            // ارسال پیام به سرور و گرفتن جواب هوش مصنوعی
            fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: text })
            })
            .then(res => res.json())
            .then(data => {
                chatBox.innerHTML += `<div class="message bot-msg">${data.response}</div>`;
                chatBox.scrollTop = chatBox.scrollHeight;
            })
            .catch(() => {
                chatBox.innerHTML += `<div class="message bot-msg">❌ خطایی رخ داد. مجددا تلاش کنید.</div>`;
            });
        }
    </script>
</body>
</html>
"""

# --- مسیر نمایش صفحه وب مینی‌اپ ---
@app.route('/webapp')
def webapp_page():
    return render_template_string(WEB_APP_HTML, ad_text=AD_TEXT, ad_link=AD_LINK)

# --- وب‌سرویس دریافت پیام‌های مینی‌اپ و پاسخ با Groq ---
@app.route('/api/chat', methods=['POST'])
def api_chat_respond():
    data = request.json
    user_message = data.get("message", "")
    try:
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": "تو یک دستیار هوش مصنوعی فوق‌العاده صمیمی، خاکی و به زبان فارسی کاملا عامیانه و روان هستی."},
                {"role": "user", "content": user_message}
            ],
            model="llama3-8b-8192"
        )
        reply = chat_completion.choices[0].message.content
        return jsonify({"response": reply})
    except Exception as e:
        return jsonify({"response": "مشکلی پیش آمد، لطفاً دوباره امتحان کنید."})

# --- مسیر زنده بودن وب‌سرور ---
@app.route('/')
def home():
    return "Mini App Server is Live!", 200

# --- دریافت پیام‌های تلگرام ---
@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def get_message():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "OK", 200
    return "Forbidden", 403

# --- دکمه‌های کیبورد ربات با دکمه وب‌اپ ---
def main_keyboard(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    
    # دکمه مینی اپ که آدرس صفحه وب را باز می‌کند
    web_app_info = types.WebAppInfo(f"{RENDER_APP_URL}/webapp")
    btn_webapp = types.KeyboardButton("🧠 شروع چت با هوش مصنوعی (Mini App)", web_app=web_app_info)
    
    markup.add(btn_webapp)
    markup.row("👥 زیرمجموعه‌گیری (دعوت)", "📊 وضعیت حساب من")
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
                bot.send_message(referred_by, f"🎉 یک کاربر جدید با لینک شما عضو ربات شد!")
            except Exception:
                pass

    user_first_name = message.from_user.first_name or "دوست"
    welcome_text = (
        f"سلام {user_first_name} عزیز به ربات هوش مصنوعی پیشرفته خوش آمدید! ⚡\n\n"
        f"برای استفاده از ربات جدید ما که به شکل وب‌سایت شیک طراحی شده، کافیست **۱۰ نفر** را دعوت کنی!\n"
        f"دکمه شیشه‌ای شروع چت در پایین فعال است؛ اگر ۱۰ دعوتت پر باشد به راحتی باز می‌شود!"
    )
    bot.send_message(user_id, welcome_text, reply_markup=main_keyboard(user_id), parse_mode='Markdown')

# --- بخش رفرال و وضعیت ---
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
        f"📈 تعداد دعوت‌های شما تا الان: **{ref_count} از ۱۰**"
    )
    bot.send_message(user_id, text, parse_mode='Markdown')

@bot.message_handler(func=lambda msg: msg.text == "📊 وضعیت حساب من")
def account_status(message):
    user_id = message.from_user.id
    user = get_user(user_id)
    ref_count = user[3] if user else 0
    status = "✅ فعال (دسترسی به مینی‌اپ آزاد است)" if ref_count >= 10 else "❌ قفل (نیاز به دعوت بیشتر)"
    
    text = (
        f"📊 **وضعیت حساب کاربری شما**\n\n"
        f"👥 تعداد دعوت‌های ثبت‌شده: **{ref_count}**\n"
        f"⚙️ وضعیت دسترسی: {status}"
    )
    bot.send_message(user_id, text, parse_mode='Markdown')

# --- پنل مدیریت (مخصوص ادمین) ---
@bot.message_handler(func=lambda msg: msg.text == "⚙️ پنل مدیریت" and msg.from_user.id == ADMIN_ID)
def admin_panel(message):
    total, unlocked = get_stats()
    text = (
        f"📊 **پنل مدیریت هوشمند**\n\n"
        f"👥 کل کاربران: **{total}**\n"
        f"🔓 کاربران فعال: **{unlocked}**\n\n"
        f"تبلیغ فعلی بالای صفحه وب‌اپ:\n"
        f"`{AD_TEXT}`\n\n"
        f"برای تغییر تبلیغ از دستور زیر استفاده کنید:\n"
        f"`/setad متن_تبلیغ | لینک_تبلیغ`"
    )
    bot.send_message(ADMIN_ID, text, parse_mode='Markdown')

# --- تغییر تبلیغ بالای صفحه توسط ادمین ---
@bot.message_handler(commands=['setad'])
def set_ad_cmd(message):
    global AD_TEXT, AD_LINK
    if message.from_user.id != ADMIN_ID:
        return
    try:
        parts = message.text.replace("/setad ", "").split("|")
        if len(parts) == 2:
            AD_TEXT = parts[0].strip()
            AD_LINK = parts[1].strip()
            bot.send_message(ADMIN_ID, "✅ تبلیغ بالای مینی‌اپ با موفقیت بروزرسانی شد!")
        else:
            bot.send_message(ADMIN_ID, "❌ فرمت اشتباه است. نمونه: `/setad اسپانسر جدید | https://t.me/link`")
    except Exception as e:
        bot.send_message(ADMIN_ID, f"❌ خطا: {e}")

# اجرای فلاسک و تنظیم وب‌هوک
if __name__ == '__main__':
    bot.remove_webhook()
    bot.set_webhook(url=f"{RENDER_APP_URL}/{BOT_TOKEN}")
    print("Webhook and Mini App configured successfully!")
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
