import os
import re
import yt_dlp
import telebot
from telebot import types

BOT_TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(BOT_TOKEN)

# 📢 Твои каналы для проверки подписки
CHANNELS = [
    {"id": "@efim_fits", "link": "https://t.me/efim_fits", "name": "Efim Fits"},
    {"id": "@rkomeat", "link": "https://t.me/rkomeat", "name": "Rkomeat"}
]

# --- ПРОВЕРКА ПОДПИСКИ ---

def check_subscriptions(user_id):
    """Проверяет, подписан ли пользователь на все каналы."""
    unsubscribed = []
    for channel in CHANNELS:
        try:
            member = bot.get_chat_member(chat_id=channel["id"], user_id=user_id)
            # Статусы, при которых подписка считается активной
            if member.status not in ['creator', 'administrator', 'member']:
                unsubscribed.append(channel)
        except Exception as e:
            print(f"Ошибка проверки канала {channel['id']}: {e}")
            # Если бот не админ в канале или произошла ошибка, считаем, что нужно подписаться
            unsubscribed.append(channel)
    return unsubscribed

def get_sub_keyboard(unsubscribed_channels):
    """Создает клавиатуру со ссылками на каналы, на которые юзер не подписан."""
    markup = types.InlineKeyboardMarkup(row_width=1)
    for ch in unsubscribed_channels:
        btn = types.InlineKeyboardButton(text=f"📌 Подписаться на {ch['name']}", url=ch['link'])
        markup.add(btn)
    
    # Кнопка проверки
    btn_check = types.InlineKeyboardButton(text="✅ Я подписался", callback_data="check_sub")
    markup.add(btn_check)
    return markup


# --- СКАЧИВАНИЕ ВИДЕО ---

def download_video(url, user_id):
    """Скачивает видео по ссылке с помощью yt-dlp."""
    filename = f"video_{user_id}.mp4"
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': filename,
        'quiet': True,
        'no_warnings': True,
        'max_filesize': 50 * 1024 * 1024,  # Ограничение 50 МБ для Telegram API
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return filename
    except Exception as e:
        print(f"Ошибка скачивания: {e}")
        if os.path.exists(filename):
            os.remove(filename)
        return None


# --- ОБРАБОТЧИКИ КОМАНД И СООБЩЕНИЙ ---

@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.chat.id
    unsubscribed = check_subscriptions(user_id)

    if unsubscribed:
        text = "👋 **Привет!**\n\nЧтобы пользоваться ботом и скачивать видео без водяных знаков, **подпишись на наши каналы**:"
        bot.send_message(user_id, text, parse_mode="Markdown", reply_markup=get_sub_keyboard(unsubscribed))
    else:
        text = "🎉 **Добро пожаловать!**\n\nПришли мне ссылку на видео из **TikTok**, **Instagram Reels** или **YouTube Shorts**, и я скачаю его для тебя!"
        bot.send_message(user_id, text, parse_mode="Markdown")

# Обработка нажатия на кнопку "Я подписался"
@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def callback_check_sub(call):
    user_id = call.from_user.id
    unsubscribed = check_subscriptions(user_id)

    if unsubscribed:
        bot.answer_callback_query(call.id, "❌ Вы всё ещё не подписались на все каналы!", show_alert=True)
    else:
        bot.answer_callback_query(call.id, "✅ Подписка подтверждена!")
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        bot.send_message(
            user_id,
            "🚀 **Отлично! Доступ открыт.**\nОтправь мне ссылку на видео для скачивания.",
            parse_mode="Markdown"
        )

# Обработка входящих ссылок
@bot.message_handler(func=lambda m: True)
def handle_message(message):
    user_id = message.chat.id
    text = message.text.strip()

    # 1. Проверяем подписку перед каждым действием
    unsubscribed = check_subscriptions(user_id)
    if unsubscribed:
        msg_text = "⚠️ **Доступ ограничен!**\nВы отписались от наших каналов. Подпишитесь снова, чтобы продолжить скачивать видео:"
        bot.send_message(user_id, msg_text, parse_mode="Markdown", reply_markup=get_sub_keyboard(unsubscribed))
        return

    # 2. Проверяем, является ли текст ссылкой
    url_pattern = re.compile(r'https?://[^\s]+')
    if not url_pattern.match(text):
        bot.send_message(user_id, "📌 Отправь корректную ссылку на видео (TikTok, Reels или Shorts).")
        return

    status_msg = bot.send_message(user_id, "⏳ **Скачиваю видео...** Пожалуйста, подождите.", parse_mode="Markdown")

    # 3. Скачиваем файл
    file_path = download_video(text, user_id)

    if file_path and os.path.exists(file_path):
        try:
            with open(file_path, 'rb') as video:
                bot.send_video(user_id, video, caption="📥 Держи твоё видео без водяных знаков!")
            bot.delete_message(user_id, status_msg.message_id)
        except Exception as e:
            bot.send_message(user_id, "❌ Не удалось отправить видео. Возможно, файл превышает допустимый размер Telegram (50 МБ).")
            print(f"Ошибка отправки файла: {e}")
        finally:
            # Обязательно удаляем файл с сервера после отправки
            if os.path.exists(file_path):
                os.remove(file_path)
    else:
        bot.edit_message_text("❌ **Ошибка!** Не удалось скачать видео. Проверь ссылку и попробуй ещё раз.", chat_id=user_id, message_id=status_msg.message_id, parse_mode="Markdown")


if __name__ == '__main__':
    print("Бот-загрузчик с проверкой подписки запущен!")
    bot.infinity_polling()
