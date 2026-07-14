import sqlite3
import requests
import telebot
from telebot import types
from datetime import datetime, timedelta
import threading
import time
from flask import Flask, render_template_string
import os

# ==================== تنظیمات اصلی ربات ====================
BOT_TOKEN = "8691005129:AAEUnoQYkGs1_tLRLlrSrOhXjjxL10AWpKI"
GROQ_API_KEY = "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"
ADMIN_ID = 6822309164
CHANNELS = ["@MRAHMAD_1", "@GMINIFARSI"]

# مشخصات کارت بانکی شما برای واریز کاربرها
CARD_NUMBER = "6037697438262914"  
CARD_NAME = "حسین پویان"            
PRICE_1_MONTH = "69,000"
PRICE_3_MONTHS = "159,000"
PRICE_6_MONTHS = "279,000"

# تعداد دعوتی که کاربر نیاز دارد تا سهمیه رایگان جدید بگیرد
REQUIRED_INVITES = 5
# تعداد پیام هدیه بعد از دعوت موفق تعداد بالا
GIFT_MESSAGES = 10
# ==========================================================

# ساخت وب‌سرور با داشبورد مدیریتی شیک (تم تریدینگ‌ویو)
app = Flask('')

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>داشبورد مدیریتی سلطان</title>
    <link href="https://cdn.jsdelivr.net/gh/rastikerdar/vazirmatn@v33.003/Vazirmatn-font-face.css" rel="stylesheet" type="text/css" />
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { font-family: Vazirmatn, sans-serif; background-color: #0d1117; color: #c9d1d9; margin: 0; padding: 20px; }
        .container { max-width: 1000px; margin: 0 auto; }
        header { text-align: center; padding: 20px 0; border-bottom: 1px solid #21262d; margin-bottom: 30px; }
        h1 { color: #58a6ff; margin: 0; font-size: 28px; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .card { background-color: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        .card h3 { margin: 0 0 10px 0; color: #8b949e; font-size: 16px; }
        .card .value { font-size: 28px; font-weight: bold; color: #f0883e; }
        .chart-container { background-color: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        .chart-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; border-bottom: 1px solid #21262d; padding-bottom: 10px; }
        .chart-title { font-size: 18px; color: #58a6ff; margin: 0; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>📊 داشبورد آماری و هوشمند ربات سلطان</h1>
            <p style="color: #8b949e; margin-top: 5px;">نمایش وضعیت ثبت‌نام‌ها و کاربران فعال به صورت زنده</p>
        </header>

        <div class="stats-grid">
            <div class="card">
                <h3>👥 کل کاربران</h3>
                <div class="value">{{ total_users }}</div>
            </div>
            <div class="card">
                <h3>⭐ کاربران ویژه</h3>
                <div class="value" style="color: #58a6ff;">{{ premium_users }}</div>
            </div>
            <div class="card">
                <h3>🟢 وضعیت ربات</h3>
                <div class="value" style="color: #3fb950; font-size: 22px;">فعال و آنلاین</div>
            </div>
        </div>

        <div class="chart-container">
            <div class="chart-header">
                <h2 class="chart-title">📈 نمودار رشد کاربران (۵ روز اخیر)</h2>
            </div>
            <canvas id="growthChart" style="max-height: 400px;"></canvas>
        </div>
    </div>

    <script>
        const dates = {{ dates | tojson }};
        const counts = {{ counts | tojson }};
        const ctx = document.getElementById('growthChart').getContext('2d');
        const growthChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: dates,
                datasets: [{
                    label: 'تعداد اعضای جدید',
                    data: counts,
                    borderColor: '#f0883e',
                    backgroundColor: 'rgba(240, 136, 62, 0.1)',
                    borderWidth: 3,
                    tension: 0.4,
                    fill: true,
                    pointBackgroundColor: '#58a6ff',
                    pointBorderColor: '#fff',
                    pointRadius: 5
                }]
            },
            options: {
                responsive: true,
                scales: {
                    y: { beginAtZero: true, grid: { color: '#21262d' }, ticks: { color: '#8b949e' } },
                    x: { grid: { color: '#21262d' }, ticks: { color: '#8b949e' } }
                },
                plugins: {
                    legend: { labels: { color: '#c9d1d9', font: { family: 'Vazirmatn' } } }
                }
            }
        });
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    try:
        conn = sqlite3.connect('bot_database.db', timeout=30)
        conn.execute('PRAGMA journal_mode=WAL;')
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM users WHERE is_premium = 1")
        premium_users = cursor.fetchone()[0]
        cursor.execute("SELECT join_date, COUNT(*) FROM users GROUP BY join_date ORDER BY join_date DESC LIMIT 5")
        rows = cursor.fetchall()
        conn.close()
        
        rows.reverse()
        dates = [row[0] for row in rows]
        counts = [row[1] for row in rows]
        
        if not dates:
            dates = ["امروز"]
            counts = [total_users]
    except Exception:
        total_users, premium_users, dates, counts = 0, 0, ["خطا"], [0]
        
    return render_template_string(HTML_TEMPLATE, total_users=total_users, premium_users=premium_users, dates=dates, counts=counts)

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

bot = telebot.TeleBot(BOT_TOKEN)

# پرامپت هماهنگ شده با فرمت HTML جهت زیبایی متون
SYSTEM_PROMPT = """
شما یک هوش مصنوعی فوق‌پیشرفته، بسیار باهوش، کاریزماتیک و حلال مشکلات هستید.
مخاطب شما کاربران ایرانی هستند، پس باید با لحنی فوق‌العاده جذاب، صمیمی، محترمانه و کاملاً مسلط صحبت کنید.

قوانین حیاتی برای میخکوب کردن مخاطب:
۱. از تعارفات طولانی، سلام و علیک‌های تکراری و روده‌درازی در ابتدای پیام‌ها کاملاً خودداری کنید. مستقیم و بدون فوت وقت به سراغ اصل مطلب و حل مسئله کاربر بروید.
۲. پاسخ‌ها را با ساختاری بسیار تمیز، استفاده از بولت‌پوینت‌ها و ایموجی‌های کاملاً مرتبط تزیین کنید تا خواندن آن برای کاربر لذت‌بخش باشد.
۳. فقط و فقط به زبان فارسی روان، بدون غلط املایی و نگارشی بنویسید. هرگز از کلمات خارجی استفاده نکنید.
۴. لحن شما باید شبیه به یک مشاور ارشد و رفیق باهوش باشد؛ نه آن‌قدر خشک و اداری که کاربر خسته شود، و نه آن‌قدر عامیانه که ابهت علمی شما زیر سوال برود.
۵. خلاق، تیزبین و عمیق پاسخ دهید. به کاربر راه‌حل‌هایی بدهید که خودش به آن‌ها فکر نکرده است.
۶. در پاسخ‌های خود حتماً از تگ‌های HTML تلگرام استفاده کنید؛ مثلاً کلمات کلیدی، تیترها و بخش‌های مهم را داخل تگ <b> قرار دهید (مانند <b>متن مهم</b>) تا پیام‌ها فوق‌العاده شیک و خوانا شوند. هرگز از ستاره (*) یا آندرلاین (_) استفاده نکنید.
"""

# ==================== بخش دیتابیس ایمن با قابلیت WAL ====================
def init_db():
    conn = sqlite3.connect('bot_database.db', timeout=30)
    conn.execute('PRAGMA journal_mode=WAL;')
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
    conn = sqlite3.connect('bot_database.db', timeout=30)
    conn.execute('PRAGMA journal_mode=WAL;')
    cursor = conn.cursor()
    cursor.execute("SELECT msg_count, has_joined, is_premium, expire_date FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()

    if not user:
        cursor.execute("INSERT INTO users (user_id, username, msg_count, has_joined, is_premium, expire_date) VALUES (?, ?, 0, 0, 0, NULL)", (user_id, username))
        conn.commit()
        conn.close()
        return 0, 0, 0, None

    msg_count, has_joined, is_premium, expire_date = user[0], user[1], user[2], user[3]
    
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
    conn = sqlite3.connect('bot_database.db', timeout=30)
    conn.execute('PRAGMA journal_mode=WAL;')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET msg_count = msg_count + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def set_joined(user_id):
    conn = sqlite3.connect('bot_database.db', timeout=30)
    conn.execute('PRAGMA journal_mode=WAL;')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET has_joined = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def make_premium(user_id, months):
    conn = sqlite3.connect('bot_database.db', timeout=30)
    conn.execute('PRAGMA journal_mode=WAL;')
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

# ==================== کیبوردها ====================
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

# ==================== ارتباط با هوش مصنوعی ====================
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
            "model": "llama-3.1-8b-instant",
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
            return "❌ خطای موقت در دریافت پاسخ هوش مصنوعی. لطفاً دوباره پیام دهید."
            
    except Exception as e:
        return "❌ خطای غیرمنتظره در سرور رخ داد."

# ==================== هندلرهای اصلی دستورات تلگرام با سپر ضد کرش ====================
def safe_send_message(chat_id, text, parse_mode="HTML", reply_markup=None, reply_to_message_id=None):
    try:
        return bot.send_message(chat_id, text, parse_mode=parse_mode, reply_markup=reply_markup, reply_to_message_id=reply_to_message_id)
    except Exception as e:
        print(f"⚠️ خطای ارسال پیام تلگرام (شاید کاربر ربات را بلاک کرده): {e}")
        return None

def safe_send_photo(chat_id, photo_id, caption=None, reply_markup=None):
    try:
        return bot.send_photo(chat_id, photo_id, caption=caption, reply_markup=reply_markup)
    except Exception as e:
        print(f"⚠️ خطای ارسال عکس تلگرام: {e}")
        return None

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
        conn = sqlite3.connect('bot_database.db', timeout=30)
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
    except Exception:
        total_users, premium_users, growth_report = 0, 0, "خطای دیتابیس"

    report = (
        f"<b>📊 داشبورد مدیریت سلطان</b>\n\n"
        f"👥 کل کاربران: {total_users} نفر\n"
        f"⭐ کاربران ویژه فعال: {premium_users} نفر\n\n"
        f"📈 آمار رشد ثبت‌نام (۵ روز اخیر):\n"
        f"{growth_report if growth_report else 'هنوز آماری ثبت نشده است.'}"
    )
    safe_send_message(message.chat.id, report, reply_to_message_id=message.message_id)

# ==================== مدیریت رویدادهای کلیک (Callback Query) ====================
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

# ==================== دریافت و ارسال فیش واریزی ====================
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

# ==================== مدیریت پیام‌های کاربران ====================
@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"

    msg_count, has_joined, is_premium, expire_date = check_user(user_id, username)

    if is_premium:
        try:
            bot.send_chat_action(message.chat.id, 'typing')
        except Exception:
            pass
        ai_response = call_gemini_ai_direct(message.text)
        safe_send_message(message.chat.id, ai_response, reply_to_
