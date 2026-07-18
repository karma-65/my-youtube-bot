import os
import threading
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import yt_dlp
from flask import Flask

# توکن ربات تلگرام شما
BOT_TOKEN = '8850665631:AAEpcVdECkXjLdZILIMPl6sLH4XoYbhQe-Y'
bot = telebot.TeleBot(BOT_TOKEN)

# تنظیمات Flask (فقط برای زنده نگه داشتن سرور رندر)
app = Flask(__name__)
DOWNLOAD_DIR = "downloads"
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

user_links = {}

@app.route('/')
def home():
    return "Bot server is running!"

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "سلام! لینک یوتیوب رو برام بفرست، کیفیت رو انتخاب کن تا ویدیو رو مستقیم همین‌جا برات بفرستم. 🎬")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    url = message.text
    if "youtube.com" in url or "youtu.be" in url:
        msg = bot.reply_to(message, "⏳ در حال بررسی ویدیو و استخراج کیفیت‌ها...")
        try:
            ydl_opts = {
                'nocheckcertificate': True,
                'quiet': True,
                'extractor_args': {
                    'youtube': {
                        'player_client': ['tvhtml5', 'android'],
                        'skip': ['dash', 'hls']
                    }
                }
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info:
                    raise Exception("اطلاعات ویدیو دریافت نشد.")
                formats = info.get('formats', [])
                
            markup = InlineKeyboardMarkup()
            available_qualities = set()
            for f in formats:
                # فیلتر کیفیت‌های mp4 حاوی صدا و تصویر
                if f.get('height') and f.get('ext') == 'mp4' and f.get('vcodec') != 'none' and f.get('acodec') != 'none':
                    height = f.get('height')
                    if height not in available_qualities:
                        available_qualities.add(height)
                        format_id = f.get('format_id')
                        # ساخت دکمه‌های شیشه‌ای قشنگ
                        markup.add(InlineKeyboardButton(text=f"🎬 {height}p", callback_data=f"{format_id}:{height}"))
            
            if available_qualities:
                user_links[message.chat.id] = url
                bot.delete_message(message.chat.id, msg.message_id)
                bot.send_message(message.chat.id, "✨ کیفیت مورد نظر رو برای پخش مستقیم انتخاب کن:", reply_markup=markup)
            else:
                bot.edit_message_text("❌ کیفیت مناسبی (mp4 مستقیم) برای این ویدیو پیدا نشد.", message.chat.id, msg.message_id)
        except Exception as e:
            bot.edit_message_text(f"❌ خطا در بررسی ویدیو:\n{str(e)}", message.chat.id, msg.message_id)
    else:
        bot.reply_to(message, "❌ لطفاً یک لینک معتبر از یوتیوب بفرستید.")

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    chat_id = call.message.chat.id
    url = user_links.get(chat_id)
    if not url: return
    
    format_id, height = call.data.split(':')
    bot.edit_message_text("📥 در حال دانلود ویدیو از یوتیوب...", chat_id, call.message.message_id)
    
    filename = f"video_{chat_id}.mp4"
    filepath = os.path.join(DOWNLOAD_DIR, filename)
    
    try:
        ydl_opts = {
            'format': format_id, 
            'outtmpl': filepath,
            'nocheckcertificate': True,
            'extractor_args': {
                'youtube': {
                    'player_client': ['tvhtml5', 'android']
                }
            }
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            
        # بررسی حجم فایل قبل از ارسال (محدودیت ۵۰ مگابایت تلگرام)
        file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
        if file_size_mb > 50:
            bot.edit_message_text(f"❌ حجم این کیفیت {file_size_mb:.1f} مگابایت است و از حد مجاز تلگرام (۵۰ مگابایت) بیشتره! لطفاً کیفیت پایین‌تری انتخاب کنید.", chat_id, call.message.message_id)
            if os.path.exists(filepath):
                os.remove(filepath)
            return

        bot.edit_message_text("📤 دانلود کامل شد! در حال ارسال ویدیو به تلگرام...", chat_id, call.message.message_id)
        
        # ارسال مستقیم ویدیو در چت ربات
        with open(filepath, 'rb') as video_file:
            bot.send_video(chat_id, video_file, timeout=120)
            
        # پاک کردن فایل از روی سرور رندر برای باز شدن فضا
        if os.path.exists(filepath):
            os.remove(filepath)
            
        bot.delete_message(chat_id, call.message.message_id)
        
    except Exception as e:
        bot.edit_message_text(f"❌ خطایی در دانلود یا ارسال رخ داد:\n{str(e)}", chat_id, call.message.message_id)
        if os.path.exists(filepath):
            os.remove(filepath)

def run_flask():
    import os
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    bot.infinity_polling()
