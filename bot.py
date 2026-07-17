import os
import telebot
from telebot import types
from google import genai
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

# ۱. تنظیمات اولیه و توکن‌ها
BOT_TOKEN = ("8358283348:AAFJO37rjWxTfrHq2lzgoUIFBINTHz3Mjuc", "")
GEMINI_API_KEY = os.environ.get("AQ.Ab8RN6IYakiQMn-1sAKeCSR3-aT-Wc4CBc6zQoAFkyWodq7kdg", "")
SPONSOR_CHANNEL = os.environ.get("@GMINIFARSI", "@MRAHMAD_1") # آیدی کانال خودت را اینجا یا در رندر ست کن

bot = telebot.TeleBot(BOT_TOKEN)
client = genai.Client(api_key=GEMINI_API_KEY)

# دیتابیس فرضی در حافظه برای ثبت پیش‌بینی‌ها
user_predictions = {}

# نمونه چالش امروز
CHALLENGE_TEXT = "⚽️ مسابقه امشب: رئال مادرید - بارسلونا\n⏰ ساعت: ۲۳:۳۰"
OPTIONS = ["برد رئال مادرید", "مساوی", "برد بارسلونا"]

# بررسی عضویت در کانال اسپانسر
def is_user_subscribed(user_id):
    try:
        member = bot.get_chat_member(SPONSOR_CHANNEL, user_id)
        if member.status in ['member', 'administrator', 'creator']:
            return True
        return False
    except Exception:
        # اگر کانال ست نشده باشد یا ربات ادمین نباشد، برای تست True برمی‌گرداند
        return True

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.chat.id
    
    # قفل عضویت اجباری
    if not is_user_subscribed(user_id):
        markup = types.InlineKeyboardMarkup()
        btn_join = types.InlineKeyboardButton("📢 عضویت در کانال", url=f"https://t.me/{SPONSOR_CHANNEL.replace('@','')}")
        btn_check = types.InlineKeyboardButton("🔄 عضو شدم! ورود به مسابقه", callback_data="check_subs")
        markup.add(btn_join)
        markup.add(btn_check)
        bot.send_message(user_id, f"👋 سلام! برای شرکت در مسابقات بزرگ پیش‌بینی و بردن کارت هدیه و شارژ، ابتدا باید در کانال زیر عضو شوی:", reply_markup=markup)
        return

    show_main_menu(user_id)

def show_main_menu(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🎯 شرکت در چالش امروز")
    markup.row("🧠 مشورت با هوش مصنوعی (جمینای)", "📊 وضعیت پیش‌بینی من")
    
    bot.send_message(user_id, "🎉 به ربات پیش‌بینی هوشمند خوش آمدی!\nیک گزینه را انتخاب کن:", reply_markup=markup)

# بررسی کلیک روی دکمه عضو شدم
@bot.callback_query_handler(func=lambda call: call.data == "check_subs")
def check_callback(call):
    if is_user_subscribed(call.message.chat.id):
        bot.delete_message(call.message.chat.id, call.message.message_id)
        show_main_menu(call.message.chat.id)
    else:
        bot.answer_callback_query(call.id, "❌ هنوز در کانال عضو نشده‌ای!", show_alert=True)

# مدیریت دکمه‌های منو
@bot.message_handler(func=lambda message: True)
def handle_menu(message):
    user_id = message.chat.id
    
    if not is_user_subscribed(user_id):
        bot.reply_to(message, "⚠️ لطفاً ابتدا با دستور /start عضویت خود را تایید کنید.")
        return

    if message.text == "🎯 شرکت در چالش امروز":
        markup = types.InlineKeyboardMarkup()
        for idx, opt in enumerate(OPTIONS):
            markup.add(types.InlineKeyboardButton(opt, callback_data=f"predict_{idx}"))
        
        bot.send_message(user_id, f"📝 **{CHALLENGE_TEXT}**\n\nگزینه مورد نظر خودت را برای پیش‌بینی انتخاب کن:", reply_markup=markup)

    elif message.text == "🧠 مشورت با هوش مصنوعی (جمینای)":
        bot.send_message(user_id, "🔄 در حال آنالیز اخبار و داده‌های ورزشی توسط جمینای... لطفاً صبر کنید.")
        try:
            prompt = f"با توجه به وضعیت فعلی تیم‌های رئال مادرید و بارسلونا در سال ۲۰۲۶، یک تحلیل بسیار کوتاه و جذاب ۲ خطی به زبان فارسی بگو و درصد احتمال برد هر کدام (رئال، مساوی، بارسا) را مشخص کن تا کاربر برای پیش‌بینی راهنمایی شود."
            response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
            bot.send_message(user_id, f"🔮 **پیش‌بینی و تحلیل هوش مصنوعی:**\n\n{response.text}")
        except Exception as e:
            bot.send_message(user_id, "❌ خطایی در ارتباط با هوش مصنوعی رخ داد.")

    elif message.text == "📊 وضعیت پیش‌بینی من":
        pred = user_predictions.get(user_id, "هنوز هیچ پیش‌بینی ثبت نکرده‌ای!")
        bot.send_message(user_id, f"🔍 آخرین وضعیت شما:\n\n{pred}")

# ثبت پیش‌بینی کاربر
@bot.callback_query_handler(func=lambda call: call.data.startswith("predict_"))
def save_prediction(call):
    user_id = call.message.chat.id
    opt_idx = int(call.data.split("_")[1])
    selected_option = OPTIONS[opt_idx]
    
    user_predictions[user_id] = f"ثبت شده: {selected_option}"
    
    bot.answer_callback_query(call.id, "✅ پیش‌بینی شما با موفقیت ثبت شد!", show_alert=True)
    bot.edit_message_text(f"🚀 پیش‌بینی شما برای چالش امروز ثبت شد:\n✨ **{selected_option}**\n\nنتایج نهایی پس از پایان مسابقه اعلام می‌شود.", user_id, call.message.message_id)

# وب‌سرور برای زنده نگه داشتن پورت رندر
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Predict Bot is Active!")

def run_health_server():
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(('0.0.0.0', port), HealthCheckHandler).serve_forever()

if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()
    bot.infinity_polling()
