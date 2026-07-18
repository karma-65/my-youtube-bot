import os
import threading
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import yt_dlp
from flask import Flask, send_from_directory, request

# ۱. توکن ربات تلگرام خود را اینجا بگذارید
BOT_TOKEN = '8850665631:AAEpcVdECkXjLdZILIMPl6sLH4XoYbhQe-Y'
bot = telebot.TeleBot(BOT_TOKEN)

# ۲. تنظیمات Flask
app = Flask(__name__)
DOWNLOAD_DIR = "downloads"
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

user_links = {}

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(DOWNLOAD_DIR, filename, as_attachment=True)

@app.route('/')
def home():
    return "Bot server is running!"

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "سلام! لینک یوتیوب رو بفرست، کیفیت رو انتخاب کن و لینک مستقیم بگیر. 🎬")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    url = message.text
    if "youtube.com" in url or "youtu.be" in url:
        msg = bot.reply_to(message, "⏳ در حال بررسی ویدیو...")
        try:
            with yt_dlp.YoutubeDL({}) as ydl:
                info = ydl.extract_info(url, download=False)
                formats = info.get('formats', [])
                
            markup = InlineKeyboardMarkup()
            available_qualities = set()
            for f in formats:
                if f.get('height') and f.get('ext') == 'mp4' and f.get('vcodec') != 'none' and f.get('acodec') != 'none':
                    height = f.get('height')
                    if height not in available_qualities:
                        available_qualities.add(height)
                        format_id = f.get('format_id')
                        markup.add(InlineKeyboardButton(text=f"🎬 {height}p", callback_data=f"{format_id}:{height}"))
            
            if available_qualities:
                user_links[message.chat.id] = url
                bot.delete_message(message.chat.id, msg.message_id)
                bot.send_message(message.chat.id, "کیفیت مورد نظر را انتخاب کنید:", reply_markup=markup)
            else:
                bot.edit_message_text("❌ کیفیت مناسبی پیدا نشد.", message.chat.id, msg.message_id)
        except Exception as e:
            bot.edit_message_text(f"❌ خطا:\n{str(e)}", message.chat.id, msg.message_id)

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    chat_id = call.message.chat.id
    url = user_links.get(chat_id)
    if not url: return
    
    format_id, height = call.data.split(':')
    bot.edit_message_text("📥 در حال آماده‌سازی لینک دانلود...", chat_id, call.message.message_id)
    
    filename = f"video_{chat_id}.mp4"
    filepath = os.path.join(DOWNLOAD_DIR, filename)
    
    try:
        with yt_dlp.YoutubeDL({'format': format_id, 'outtmpl': filepath}) as ydl:
            ydl.download([url])
            
        # پیدا کردن اتوماتیک آدرس سرور
        server_url = request.url_root.rstrip('/')
        download_link = f"{server_url}/download/{filename}"
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(text="📥 دانلود ویدیو", url=download_link))
        bot.edit_message_text(f"✅ ویدیوی {height}p آماده دانلود است:", chat_id, call.message.message_id, reply_markup=markup)
    except Exception as e:
        bot.edit_message_text(f"❌ خطایی رخ داد:\n{str(e)}", chat_id, call.message.message_id)

def run_flask():
    # رندر پورت را خودش از طریق متغیر محیطی تعیین می‌کند، اگر نبود روی 10000 ست می‌شود
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    bot.infinity_polling()
