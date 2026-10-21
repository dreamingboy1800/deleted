# import asyncio
# import html
# import logging
# import os
# import json
# import random
# import time
# import urllib.request
# from datetime import datetime, timezone, timedelta

# import aiosqlite
# from dotenv import load_dotenv
# from groq import Groq

# from aiogram import Bot, Dispatcher, Router
# from aiogram.filters import CommandStart
# from aiogram.types import (
#     Message,
#     BusinessConnection,
#     BusinessMessagesDeleted,
#     InlineKeyboardMarkup,
#     InlineKeyboardButton,
#     CopyTextButton,
#     CallbackQuery,
#     FSInputFile,
#     InputMediaPhoto,
# )
# from aiogram.exceptions import TelegramBadRequest


# # ============================================================
# # CONFIG
# # ============================================================

# load_dotenv()

# BOT_TOKEN = os.getenv("BOT_TOKEN")
# REQUIRED_CHANNEL = os.getenv("REQUIRED_CHANNEL", "").strip()
# GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# DB_FILE = "archive.db"

# BOT_USERNAME = "@deleteddreamsbot"
# BOT_URL = "https://t.me/deleteddreamsbot"

# VIDEO_FILE = "instruction.mp4"

# GPT_MODEL = "openai/gpt-oss-20b"

# LAST_CAT_IDS = {}

# GPT_CONTEXT_MESSAGES = 25


# if not BOT_TOKEN:
#     raise RuntimeError("BOT_TOKEN не найден в .env")

# if not REQUIRED_CHANNEL:
#     raise RuntimeError("REQUIRED_CHANNEL не найден в .env")

# if not GROQ_API_KEY:
#     raise RuntimeError("GROQ_API_KEY не найден в .env")


# # ============================================================
# # CHANNEL NORMALIZATION
# # ============================================================

# def normalize_channel(value: str) -> str:

#     value = value.strip()

#     if value.startswith("https://t.me/"):
#         value = value[len("https://t.me/"):]

#     elif value.startswith("http://t.me/"):
#         value = value[len("http://t.me/"):]

#     elif value.startswith("t.me/"):
#         value = value[len("t.me/"):]

#     value = value.strip("/")

#     if not value.startswith("@") and not value.startswith("-100"):
#         value = "@" + value

#     return value


# CHANNEL_CHAT_ID = normalize_channel(REQUIRED_CHANNEL)


# # ============================================================
# # GLOBALS
# # ============================================================

# BOT = None

# groq_client = Groq(
#     api_key=GROQ_API_KEY
# )


# # ============================================================
# # LOGGING
# # ============================================================

# logging.basicConfig(
#     level=logging.INFO,
#     format="%(asctime)s | %(levelname)s | %(message)s",
# )


# # ============================================================
# # DATABASE
# # ============================================================

# async def init_db():

#     async with aiosqlite.connect(DB_FILE) as db:

#         await db.execute("""
#             CREATE TABLE IF NOT EXISTS business_connections (
#                 connection_id TEXT PRIMARY KEY,
#                 owner_user_id INTEGER NOT NULL,
#                 owner_chat_id INTEGER NOT NULL,
#                 is_enabled INTEGER NOT NULL DEFAULT 1
#             )
#         """)

#         await db.execute("""
#             CREATE TABLE IF NOT EXISTS messages (
#                 id INTEGER PRIMARY KEY AUTOINCREMENT,

#                 connection_id TEXT NOT NULL,

#                 chat_id INTEGER NOT NULL,
#                 message_id INTEGER NOT NULL,

#                 sender_id INTEGER,
#                 sender_name TEXT,

#                 chat_name TEXT,

#                 text TEXT,

#                 content_type TEXT,
#                 file_id TEXT,

#                 created_at TEXT,

#                 edited INTEGER DEFAULT 0,
#                 deleted INTEGER DEFAULT 0,

#                 UNIQUE(
#                     connection_id,
#                     chat_id,
#                     message_id
#                 )
#             )
#         """)

#         await db.execute("""
#             CREATE TABLE IF NOT EXISTS message_versions (
#                 id INTEGER PRIMARY KEY AUTOINCREMENT,

#                 connection_id TEXT NOT NULL,

#                 chat_id INTEGER NOT NULL,
#                 message_id INTEGER NOT NULL,

#                 text TEXT,

#                 saved_at TEXT
#             )
#         """)

#         await db.execute("""
#             CREATE TABLE IF NOT EXISTS gpt_messages (
#                 connection_id TEXT NOT NULL,
#                 chat_id INTEGER NOT NULL,
#                 message_id INTEGER NOT NULL,

#                 PRIMARY KEY (
#                     connection_id,
#                     chat_id,
#                     message_id
#                 )
#             )
#         """)

#         await db.execute("""
#             CREATE TABLE IF NOT EXISTS auto_responder (
#                 connection_id TEXT PRIMARY KEY,
#                 enabled INTEGER NOT NULL DEFAULT 0,
#                 reply_text TEXT NOT NULL DEFAULT 'Здравствуйте! Сейчас я не могу ответить лично. Я обязательно отвечу позже.'
#             )
#         """)

#         try:
#             await db.execute("ALTER TABLE auto_responder ADD COLUMN interval_minutes INTEGER NOT NULL DEFAULT 0")
#         except Exception:
#             pass

#         await db.execute("""
#             CREATE TABLE IF NOT EXISTS auto_reply_log (
#                 connection_id TEXT NOT NULL,
#                 chat_id INTEGER NOT NULL,
#                 last_sent_at REAL NOT NULL,
#                 PRIMARY KEY (connection_id, chat_id)
#             )
#         """)

#         await db.execute("""
#             CREATE TABLE IF NOT EXISTS auto_pending (
#                 owner_user_id INTEGER PRIMARY KEY,
#                 connection_id TEXT NOT NULL
#             )
#         """)

#         # Стрики активности по каждому Business-чату
#         await db.execute("""
#             CREATE TABLE IF NOT EXISTS chat_streaks (
#                 connection_id TEXT NOT NULL,
#                 chat_id INTEGER NOT NULL,
#                 current_streak INTEGER NOT NULL DEFAULT 0,
#                 best_streak INTEGER NOT NULL DEFAULT 0,
#                 last_active_date TEXT,
#                 PRIMARY KEY (connection_id, chat_id)
#             )
#         """)

#         await db.commit()

#     logging.info("DATABASE READY")


# # ============================================================
# # HELPERS
# # ============================================================

# def esc(value):

#     if value is None or value == "":
#         return "[нет текста]"

#     return html.escape(str(value))


# def get_sender_name(message: Message):

#     if not message.from_user:
#         return "Неизвестный пользователь"

#     user = message.from_user

#     name = user.full_name or str(user.id)

#     if user.username:
#         name += f" (@{user.username})"

#     return name


# def get_chat_name(message: Message):

#     chat = message.chat

#     if chat.full_name:
#         return chat.full_name

#     if chat.title:
#         return chat.title

#     if chat.username:
#         return f"@{chat.username}"

#     return str(chat.id)


# def get_content(message: Message):

#     if message.text:
#         return (
#             "text",
#             message.text,
#             None,
#         )

#     if message.photo:
#         return (
#             "photo",
#             message.caption,
#             message.photo[-1].file_id,
#         )

#     if message.video:
#         return (
#             "video",
#             message.caption,
#             message.video.file_id,
#         )

#     if message.document:
#         return (
#             "document",
#             message.caption,
#             message.document.file_id,
#         )

#     if message.audio:
#         return (
#             "audio",
#             message.caption,
#             message.audio.file_id,
#         )

#     # 🎤 Голосовое
#     if message.voice:
#         return (
#             "voice",
#             None,
#             message.voice.file_id,
#         )

#     # ⭕ Кружок
#     if message.video_note:
#         return (
#             "video_note",
#             None,
#             message.video_note.file_id,
#         )

#     if message.animation:
#         return (
#             "animation",
#             message.caption,
#             message.animation.file_id,
#         )

#     # 🎭 Стикер
#     if message.sticker:
#         return (
#             "sticker",
#             None,
#             message.sticker.file_id,
#         )

#     return (
#         "other",
#         None,
#         None,
#     )


# def message_author_role(
#     sender_id,
#     owner_id,
# ):

#     if sender_id == owner_id:
#         return "владелец"

#     return "собеседник"


# # ============================================================
# # SUBSCRIPTION
# # ============================================================

# async def is_subscribed(user_id: int) -> bool:

#     try:

#         channel = await BOT.get_chat(
#             chat_id=CHANNEL_CHAT_ID
#         )

#         logging.info(
#             "SUB CHECK | channel=%s | title=%s | user=%s",
#             channel.id,
#             channel.title,
#             user_id,
#         )

#         member = await BOT.get_chat_member(
#             chat_id=channel.id,
#             user_id=user_id,
#         )

#         status = member.status

#         logging.info(
#             "SUB CHECK RESULT | user=%s | status=%s",
#             user_id,
#             status,
#         )

#         if status in (
#             "creator",
#             "administrator",
#             "member",
#         ):
#             return True

#         if status == "restricted":
#             return bool(
#                 getattr(
#                     member,
#                     "is_member",
#                     False,
#                 )
#             )

#         return False

#     except TelegramBadRequest as e:

#         logging.error(
#             "TELEGRAM SUB CHECK ERROR | "
#             "user=%s | channel=%s | error=%s",
#             user_id,
#             CHANNEL_CHAT_ID,
#             e,
#         )

#         return False

#     except Exception:

#         logging.exception(
#             "SUBSCRIPTION CHECK FAILED | user=%s",
#             user_id,
#         )

#         return False


# def subscription_keyboard():

#     channel = CHANNEL_CHAT_ID

#     if channel.startswith("@"):
#         channel_url = (
#             "https://t.me/"
#             + channel[1:]
#         )
#     else:
#         channel_url = REQUIRED_CHANNEL

#     return InlineKeyboardMarkup(
#         inline_keyboard=[
#             [
#                 InlineKeyboardButton(
#                     text="📢 Подписаться на канал",
#                     url=channel_url,
#                 )
#             ],
#             [
#                 InlineKeyboardButton(
#                     text="✅ Проверить подписку",
#                     callback_data="check_subscription",
#                 )
#             ],
#         ]
#     )


# SUBSCRIPTION_TEXT = (
#     "🔒 <b>Доступ ограничен</b>\n\n"

#     "Чтобы пользоваться ботом, "
#     "необходимо подписаться на наш канал.\n\n"

#     "1️⃣ Нажми <b>«Подписаться на канал»</b>\n"
#     "2️⃣ Подпишись на канал\n"
#     "3️⃣ Вернись сюда и нажми "
#     "<b>«Проверить подписку»</b>\n\n"

#     "После проверки бот станет доступен."
# )


# async def require_subscription(
#     message: Message,
# ) -> bool:

#     if not message.from_user:
#         return False

#     if await is_subscribed(
#         message.from_user.id
#     ):
#         return True

#     await message.answer(
#         SUBSCRIPTION_TEXT,
#         reply_markup=subscription_keyboard(),
#         parse_mode="HTML",
#     )

#     return False


# # ============================================================
# # KEYBOARDS
# # ============================================================

# def main_keyboard():

#     return InlineKeyboardMarkup(
#         inline_keyboard=[
#             [
#                 InlineKeyboardButton(
#                     text="🎩 Инструкция",
#                     callback_data="instruction",
#                 )
#             ],
#             [
#                 InlineKeyboardButton(
#                     text="📋 Функции",
#                     callback_data="functions",
#                 )
#             ],
#             [
#                 InlineKeyboardButton(
#                     text="🤖 Автоответчик",
#                     callback_data="auto_settings",
#                 )
#             ],
#         ]
#     )


# def instruction_keyboard():

#     return InlineKeyboardMarkup(
#         inline_keyboard=[
#             [
#                 InlineKeyboardButton(
#                     text="📋 Скопировать username",
#                     copy_text=CopyTextButton(
#                         text=BOT_USERNAME
#                     ),
#                 )
#             ],
#             [
#                 InlineKeyboardButton(
#                     text="◀️ Назад",
#                     callback_data="back_to_start",
#                 )
#             ],
#         ]
#     )


# def functions_keyboard():

#     return InlineKeyboardMarkup(
#         inline_keyboard=[
#             [
#                 InlineKeyboardButton(
#                     text="◀️ Назад",
#                     callback_data="back_to_start",
#                 )
#             ]
#         ]
#     )


# # ============================================================
# # START
# # ============================================================

# START_TEXT = (
#     "👋 <b>Добро пожаловать в Deleted!</b>\n\n"

#     "Deleted — бот для Telegram Business, "
#     "который помогает сохранять важные сообщения "
#     "и добавляет полезные функции для ваших чатов.\n\n"

#     "🔹 Удалённые сообщения\n"
#     "🔹 Изменённые сообщения\n"
#     "🔹 GPT-помощник\n"
#     "🔹 Автоответчик\n"
#     "🔹 И другие функции\n\n"

#     "🆕 <b>Новичок?</b>\n"
#     "Нажми <b>«🎩 Инструкция»</b>, "
#     "чтобы узнать, как подключить бота."
# )


# FUNCTIONS_TEXT = (
#     "📋 <b>Функции Deleted</b>\n\n"

#     "🗑 <b>Удалённые сообщения</b>\n"
#     "Бот сохраняет сообщения и уведомляет вас, "
#     "если собеседник их удалил.\n\n"

#     "🎤 <b>Удалённые голосовые</b>\n"
#     "Бот сохраняет голосовые сообщения и "
#     "может отправить их вам после удаления.\n\n"

#     "⭕ <b>Удалённые кружки</b>\n"
#     "Удалённые видеокружки также сохраняются.\n\n"

#     "🎭 <b>Удалённые стикеры</b>\n"
#     "Бот сохраняет и отправляет удалённые стикеры.\n\n"

#     "📷 <b>Медиа</b>\n"
#     "Фото, видео, аудио, документы и GIF "
#     "также сохраняются при возможности.\n\n"

#     "✏️ <b>Изменённые сообщения</b>\n"
#     "Показывает, что было написано до изменения "
#     "и на что сообщение было заменено.\n\n"

#     "🤖 <b>GPT</b>\n"
#     "AI-помощник прямо в Business-чате. "
#     "Используйте команду <code>.gpt</code> "
#     "для получения ответа с учётом контекста переписки.\n\n"

#     "🐱 <b>Cat</b>\n"
#     "Команда <code>.cat</code> отправляет случайного котика.\n\n"

#     "🤖 <b>Автоответчик</b>\n"
#     "Автоматически отвечает собеседникам, "
#     "когда вы не можете ответить лично.\n"

#     "🔥 <b>Стрик общения</b>\n"
#     "Отслеживает дни подряд, когда в чате есть активность. "
#     "Показывает текущий стрик и рекорд.\n"
#     "Посмотреть: <code>.streak</code>\n"
#     "Отключить: <code>.streakoff</code>\n\n"

#     "━━━━━━━━━━━━━━━━━━\n\n"

#     "🚀 <b>Это ещё не всё!</b>\n\n"

#     "Новые функции будут добавляться "
#     "постепенно. Следите за обновлениями 👀"
# )


# # ============================================================
# # GPT COMMAND
# # ============================================================

# def is_gpt_command(text: str) -> bool:

#     if not text:
#         return False

#     text = text.strip()

#     return (
#         text == ".gpt"
#         or text.startswith(".gpt ")
#         or text.startswith(".gpt\n")
#     )


# def extract_gpt_prompt(text: str) -> str:

#     return text.strip()[4:].strip()


# # ============================================================
# # GPT CONTEXT
# # ============================================================

# async def get_gpt_context(
#     connection_id: str,
#     chat_id: int,
# ):

#     async with aiosqlite.connect(DB_FILE) as db:

#         cursor = await db.execute("""
#             SELECT
#                 sender_id,
#                 sender_name,
#                 text,
#                 created_at,
#                 edited,
#                 deleted

#             FROM messages

#             WHERE connection_id = ?
#               AND chat_id = ?

#             ORDER BY id DESC

#             LIMIT ?
#         """, (
#             connection_id,
#             chat_id,
#             GPT_CONTEXT_MESSAGES,
#         ))

#         rows = await cursor.fetchall()

#     rows.reverse()

#     if not rows:
#         return []

#     async with aiosqlite.connect(DB_FILE) as db:

#         cursor = await db.execute("""
#             SELECT owner_user_id

#             FROM business_connections

#             WHERE connection_id = ?

#             LIMIT 1
#         """, (
#             connection_id,
#         ))

#         owner_row = await cursor.fetchone()

#     owner_id = owner_row[0] if owner_row else None

#     context = []

#     for (
#         sender_id,
#         sender_name,
#         text_value,
#         created_at,
#         edited,
#         deleted,
#     ) in rows:

#         if not text_value:
#             continue

#         role = message_author_role(
#             sender_id,
#             owner_id,
#         )

#         if deleted:
#             continue

#         context.append({
#             "role": role,
#             "name": sender_name or "Неизвестный",
#             "text": text_value,
#             "edited": bool(edited),
#         })

#     return context


# def build_gpt_context_text(context):

#     if not context:
#         return (
#             "Истории переписки пока нет."
#         )

#     lines = []

#     for item in context:

#         edited_mark = (
#             " [ред.]"
#             if item["edited"]
#             else ""
#         )

#         lines.append(
#             f"{item['role']} "
#             f"({item['name']})"
#             f"{edited_mark}: "
#             f"{item['text']}"
#         )

#     return "\n".join(lines)


# # ============================================================
# # ASK GPT
# # ============================================================

# async def ask_gpt(
#     prompt: str,
#     context,
# ) -> str:

#     context_text = build_gpt_context_text(
#         context
#     )

#     def request():

#         response = groq_client.chat.completions.create(

#             model=GPT_MODEL,

#             messages=[
#                 {
#                     "role": "system",

#                     "content": """
# Ты — помощник, который пишет готовые сообщения от имени владельца Telegram Business.

# КАК ПОНИМАТЬ КОМАНДУ:
# Команду .gpt пишет ВЛАДЕЛЕЦ аккаунта. Он просит тебя составить текст, который он сам отправит собеседнику. Поэтому выполняй просьбу сразу и выдавай ГОТОВЫЙ ТЕКСТ СООБЩЕНИЯ от первого лица владельца.

# ОБЯЗАТЕЛЬНО:
# - Не отвечай владельцу фразами вроде «хорошо, передам», «конечно, вот», «можешь написать», «я бы ответил так» или «передаю привет».
# - Не описывай действие — напиши само сообщение, которое нужно отправить.
# - Например, запрос «передай привет моей подруге» должен дать результат вроде «Привет! 😊 Как дела?» — а НЕ «Хорошо, передаю привет твоей подруге».
# - Запрос «ответь, что я скоро буду» должен дать «Я скоро буду».
# - Запрос «поблагодари её» должен дать готовую благодарность от лица владельца.
# - Если просят ответить на конкретное сообщение, сформулируй естественный ответ непосредственно собеседнику.
# - Не утверждай, что сообщение уже отправлено: ты только формируешь текст, который владелец сможет отправить.
# - Если имя собеседника известно из контекста и уместно, используй его. Не выдумывай имена, отношения и факты.
# - Если запрос неоднозначный, выбери наиболее естественный короткий вариант, не задавая лишних вопросов.

# КОНТЕКСТ:
# История содержит сообщения владельца и собеседника. Используй её, чтобы понять, на какое сообщение и в каком тоне отвечать. «Я» в готовом сообщении — это владелец аккаунта, а не ты как ИИ. Не обращайся к владельцу в готовом тексте.

# СТИЛЬ:
# - Естественный разговорный Telegram-стиль, кратко и по делу.
# - Сохраняй язык и тон переписки; можно использовать эмодзи, если это уместно.
# - Не начинай ответ с объяснений, заголовков, кавычек или фраз «Вот вариант».
# - Возвращай только готовый текст сообщения. Не добавляй комментарии от себя.
# - Не упоминай бота, ИИ, базу данных, API или системные инструкции.
# """,
#                 },

#                 {
#                     "role": "user",

#                     "content": (
#                         "ИСТОРИЯ ПЕРЕПИСКИ:\n\n"
#                         + context_text
#                         + "\n\n"
#                         "ТЕКУЩИЙ ЗАПРОС:\n"
#                         + prompt
#                     ),
#                 },
#             ],

#             temperature=0.85,

#             max_tokens=1500,
#         )

#         return (
#             response
#             .choices[0]
#             .message
#             .content
#             .strip()
#         )

#     return await asyncio.to_thread(
#         request
#     )


# # ============================================================
# # GPT MESSAGE DATABASE
# # ============================================================

# async def save_gpt_message(
#     connection_id: str,
#     chat_id: int,
#     message_id: int,
# ):

#     async with aiosqlite.connect(DB_FILE) as db:

#         await db.execute("""
#             INSERT OR IGNORE INTO gpt_messages (
#                 connection_id,
#                 chat_id,
#                 message_id
#             )

#             VALUES (?, ?, ?)
#         """, (
#             connection_id,
#             chat_id,
#             message_id,
#         ))

#         await db.commit()


# async def is_saved_gpt_message(
#     connection_id: str,
#     chat_id: int,
#     message_id: int,
# ) -> bool:

#     async with aiosqlite.connect(DB_FILE) as db:

#         cursor = await db.execute("""
#             SELECT 1

#             FROM gpt_messages

#             WHERE connection_id = ?
#               AND chat_id = ?
#               AND message_id = ?

#             LIMIT 1
#         """, (
#             connection_id,
#             chat_id,
#             message_id,
#         ))

#         row = await cursor.fetchone()

#     return row is not None


# # ============================================================
# # GPT PROCESSING
# # ============================================================

# async def process_gpt_command(
#     message: Message
# ) -> bool:

#     if not message.text:
#         return False

#     if not is_gpt_command(
#         message.text
#     ):
#         return False

#     connection_id = (
#         message.business_connection_id
#     )

#     if not connection_id:
#         return False

#     prompt = extract_gpt_prompt(
#         message.text
#     )

#     logging.info("")
#     logging.info("========================================")
#     logging.info("GPT REQUEST")
#     logging.info("Connection: %s", connection_id)
#     logging.info("Chat: %s", message.chat.id)
#     logging.info("Message: %s", message.message_id)
#     logging.info("From: %s", get_sender_name(message))
#     logging.info("Prompt: %r", prompt)
#     logging.info("========================================")

#     await save_gpt_message(
#         connection_id,
#         message.chat.id,
#         message.message_id,
#     )

#     if not prompt:

#         try:

#             await BOT.edit_message_text(
#                 chat_id=message.chat.id,
#                 message_id=message.message_id,
#                 business_connection_id=connection_id,
#                 text=(
#                     "🤖 <b>GPT</b>\n\n"
#                     "Напиши запрос после команды.\n\n"
#                     "<code>.gpt придумай шутку</code>"
#                 ),
#                 parse_mode="HTML",
#             )

#         except Exception:

#             logging.exception(
#                 "FAILED TO EDIT EMPTY GPT COMMAND"
#             )

#         return True

#     try:

#         await BOT.edit_message_text(
#             chat_id=message.chat.id,
#             message_id=message.message_id,
#             business_connection_id=connection_id,
#             text="🤖 <i>Думаю...</i>",
#             parse_mode="HTML",
#         )

#         context = await get_gpt_context(
#             connection_id,
#             message.chat.id,
#         )

#         logging.info(
#             "GPT CONTEXT | messages=%s",
#             len(context),
#         )

#         answer = await ask_gpt(
#             prompt,
#             context,
#         )

#         if not answer:
#             answer = (
#                 "Что-то я не смог придумать ответ 😅"
#             )

#         if len(answer) > 4000:
#             answer = answer[:3990] + "\n\n…"

#         await BOT.edit_message_text(
#             chat_id=message.chat.id,
#             message_id=message.message_id,
#             business_connection_id=connection_id,
#             text=answer,
#         )

#         logging.info(
#             "GPT RESPONSE SENT | message=%s",
#             message.message_id,
#         )

#     except Exception as e:

#         logging.exception(
#             "GPT ERROR"
#         )

#         error_text = str(e)

#         if len(error_text) > 500:
#             error_text = error_text[:500]

#         try:

#             await BOT.edit_message_text(
#                 chat_id=message.chat.id,
#                 message_id=message.message_id,
#                 business_connection_id=connection_id,
#                 text=(
#                     "❌ Не удалось получить ответ.\n\n"
#                     f"<code>{esc(error_text)}</code>"
#                 ),
#                 parse_mode="HTML",
#             )

#         except Exception:

#             logging.exception(
#                 "FAILED TO SEND GPT ERROR"
#             )

#     return True


# # ============================================================
# # ROUTER
# # ============================================================

# router = Router()


# # ============================================================
# # START
# # ============================================================

# @router.message(CommandStart())
# async def start_handler(
#     message: Message,
# ):

#     if not await require_subscription(
#         message
#     ):
#         return

#     logging.info(
#         "START FROM USER %s",
#         message.from_user.id,
#     )

#     await message.answer(
#         START_TEXT,
#         reply_markup=main_keyboard(),
#         parse_mode="HTML",
#     )


# # ============================================================
# # CHECK SUBSCRIPTION
# # ============================================================

# @router.callback_query(
#     lambda callback:
#         callback.data == "check_subscription"
# )
# async def check_subscription_handler(
#     callback: CallbackQuery,
# ):

#     subscribed = await is_subscribed(
#         callback.from_user.id
#     )

#     if not subscribed:

#         await callback.answer(
#             "❌ Вы ещё не подписались на канал",
#             show_alert=True,
#         )

#         return

#     await callback.answer(
#         "✅ Подписка подтверждена!"
#     )

#     try:
#         await callback.message.delete()
#     except Exception:
#         pass

#     await callback.message.answer(
#         START_TEXT,
#         reply_markup=main_keyboard(),
#         parse_mode="HTML",
#     )


# # ============================================================
# # FUNCTIONS
# # ============================================================

# @router.callback_query(
#     lambda callback:
#         callback.data == "functions"
# )
# async def functions_handler(
#     callback: CallbackQuery,
# ):

#     if not await is_subscribed(
#         callback.from_user.id
#     ):

#         await callback.answer(
#             "🔒 Сначала подпишитесь на канал",
#             show_alert=True,
#         )

#         return

#     await callback.answer()

#     try:

#         await callback.message.edit_text(
#             FUNCTIONS_TEXT,
#             reply_markup=functions_keyboard(),
#             parse_mode="HTML",
#         )

#     except Exception:

#         await callback.message.answer(
#             FUNCTIONS_TEXT,
#             reply_markup=functions_keyboard(),
#             parse_mode="HTML",
#         )


# # ============================================================
# # INSTRUCTION
# # ============================================================

# @router.callback_query(
#     lambda callback:
#         callback.data == "instruction"
# )
# async def instruction_handler(
#     callback: CallbackQuery,
# ):

#     if not await is_subscribed(
#         callback.from_user.id
#     ):

#         await callback.answer(
#             "🔒 Сначала подпишитесь на канал",
#             show_alert=True,
#         )

#         return

#     await callback.answer()

#     connected = False

#     async with aiosqlite.connect(DB_FILE) as db:

#         cursor = await db.execute("""
#             SELECT 1

#             FROM business_connections

#             WHERE owner_user_id = ?
#               AND is_enabled = 1

#             LIMIT 1
#         """, (
#             callback.from_user.id,
#         ))

#         connected = (
#             await cursor.fetchone()
#         ) is not None

#     try:
#         await callback.message.delete()
#     except Exception:
#         pass

#     status = (
#         "🟢 подключен"
#         if connected
#         else
#         "🔴 не подключен"
#     )

#     instruction_text = (
#         "🎩 <b>Гайд на подключение</b>\n\n"

#         "Посмотрите видео-инструкцию "
#         "или следуйте текстовой:\n\n"

#         "<blockquote>"
#         "<b>1.</b> Скопируйте username этого бота"
#         "</blockquote>\n"

#         "<blockquote>"
#         "<b>2.</b> Перейдите в "
#         '<a href="tg://settings/edit">'
#         "профиль → Изменить"
#         "</a>"
#         "</blockquote>\n"

#         "<blockquote>"
#         "<b>3.</b> Найдите вкладку "
#         "<b>«Автоматизация чатов»</b>"
#         "</blockquote>\n"

#         "<blockquote>"
#         "<b>4.</b> Вставьте username нашего бота"
#         "</blockquote>\n"

#         f"🔗 <b>Статус бота:</b> {status}\n\n"

#         "Если статус бота <b>«подключен»</b> — "
#         "значит всё сделано правильно и вы "
#         "можете использовать команды."
#     )

#     if os.path.exists(VIDEO_FILE):

#         try:

#             video = FSInputFile(
#                 VIDEO_FILE
#             )

#             await callback.message.answer_video(
#                 video=video,
#                 caption=instruction_text,
#                 reply_markup=instruction_keyboard(),
#                 parse_mode="HTML",
#             )

#         except Exception:

#             logging.exception(
#                 "FAILED TO SEND VIDEO"
#             )

#             await callback.message.answer(
#                 instruction_text,
#                 reply_markup=instruction_keyboard(),
#                 parse_mode="HTML",
#             )

#     else:

#         await callback.message.answer(
#             instruction_text,
#             reply_markup=instruction_keyboard(),
#             parse_mode="HTML",
#         )


# # ============================================================
# # BACK
# # ============================================================

# @router.callback_query(
#     lambda callback:
#         callback.data == "back_to_start"
# )
# async def back_to_start_handler(
#     callback: CallbackQuery,
# ):

#     if not await is_subscribed(
#         callback.from_user.id
#     ):

#         await callback.answer(
#             "🔒 Сначала подпишитесь на канал",
#             show_alert=True,
#         )

#         return

#     await callback.answer()

#     try:
#         await callback.message.delete()
#     except Exception:
#         pass

#     await callback.message.answer(
#         START_TEXT,
#         reply_markup=main_keyboard(),
#         parse_mode="HTML",
#     )


# # ============================================================
# # BUSINESS CONNECTION
# # ============================================================

# @router.business_connection()
# async def business_connection_handler(
#     event: BusinessConnection,
# ):

#     logging.info("")
#     logging.info("========================================")
#     logging.info("BUSINESS CONNECTION")
#     logging.info("ID          : %s", event.id)
#     logging.info("USER ID     : %s", event.user.id)
#     logging.info("USER CHAT ID: %s", event.user_chat_id)
#     logging.info("ENABLED     : %s", event.is_enabled)
#     logging.info("RIGHTS      : %s", event.rights)
#     logging.info("========================================")

#     async with aiosqlite.connect(DB_FILE) as db:

#         await db.execute("""
#             INSERT INTO business_connections (
#                 connection_id,
#                 owner_user_id,
#                 owner_chat_id,
#                 is_enabled
#             )

#             VALUES (?, ?, ?, ?)

#             ON CONFLICT(connection_id)
#             DO UPDATE SET
#                 owner_user_id = excluded.owner_user_id,
#                 owner_chat_id = excluded.owner_chat_id,
#                 is_enabled = excluded.is_enabled
#         """, (
#             event.id,
#             event.user.id,
#             event.user_chat_id,
#             int(event.is_enabled),
#         ))

#         await db.commit()

#     if event.is_enabled:

#         try:

#             await BOT.send_message(
#                 event.user_chat_id,

#                 "✅ <b>Бот подключен!</b>\n\n"

#                 "Теперь Deleted будет сохранять "
#                 "новые сообщения из разрешённых чатов.\n\n"

#                 "Также доступна команда:\n"
#                 "<code>.gpt твой запрос</code>",

#                 parse_mode="HTML",
#             )

#         except Exception:

#             logging.exception(
#                 "FAILED TO SEND CONNECTION MESSAGE"
#             )

#     else:

#         try:

#             await BOT.send_message(
#                 event.user_chat_id,

#                 "🔴 <b>Бот отключен</b>\n\n"
#                 "Архивирование новых сообщений "
#                 "приостановлено.",

#                 parse_mode="HTML",
#             )

#         except Exception:

#             logging.exception(
#                 "FAILED TO SEND DISCONNECT MESSAGE"
#             )


# # ============================================================
# # AUTO RESPONDER
# # ============================================================

# DEFAULT_AUTO_REPLY = (
#     "Здравствуйте! 👋\n\n"
#     "Сейчас я не могу ответить лично. "
#     "Я обязательно отвечу позже."
# )


# # ============================================================
# # НЕИЗМЕНЯЕМАЯ ПОДПИСЬ
# # ============================================================

# AUTO_PROMO_TEXT = (
#     "\n\n"
#     "✨ Это бесплатный автоответчик от бота "
#     '<a href="https://t.me/deleteddreamsbot">'
#     "@deleteddreamsbot"
#     "</a> 😉"
# )


# def build_auto_reply(user_text: str) -> str:

#     user_text = (
#         user_text or DEFAULT_AUTO_REPLY
#     ).strip()

#     safe_text = html.escape(
#         user_text
#     )

#     return (
#         safe_text
#         + AUTO_PROMO_TEXT
#     )


# def auto_settings_keyboard(enabled: bool, interval_minutes: int = 0):
#     def mark(value):
#         return "✅ " if interval_minutes == value else ""

#     return InlineKeyboardMarkup(inline_keyboard=[
#         [InlineKeyboardButton(text=("🔴 Выключить" if enabled else "🟢 Включить"), callback_data="auto_toggle")],
#         [InlineKeyboardButton(text=f"{mark(0)}⚡ Каждое сообщение", callback_data="auto_interval_0")],
#         [
#             InlineKeyboardButton(text=f"{mark(5)}🕔 Раз в 5 минут", callback_data="auto_interval_5"),
#             InlineKeyboardButton(text=f"{mark(10)}🕙 Раз в 10 минут", callback_data="auto_interval_10"),
#         ],
#         [InlineKeyboardButton(text=f"{mark(15)}🕒 Раз в 15 минут", callback_data="auto_interval_15")],
#         [InlineKeyboardButton(text="✏️ Изменить ответ", callback_data="auto_edit")],
#         [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_start")],
#     ])


# async def get_auto_interval(connection_id: str) -> int:
#     async with aiosqlite.connect(DB_FILE) as db:
#         cursor = await db.execute(
#             "SELECT interval_minutes FROM auto_responder WHERE connection_id = ? LIMIT 1",
#             (connection_id,),
#         )
#         row = await cursor.fetchone()
#     return int(row[0]) if row else 0


# async def set_auto_interval(connection_id: str, interval_minutes: int):
#     if interval_minutes not in (0, 5, 10, 15):
#         raise ValueError("Недопустимый интервал автоответчика")
#     async with aiosqlite.connect(DB_FILE) as db:
#         await db.execute("""
#             INSERT INTO auto_responder (connection_id, enabled, reply_text, interval_minutes)
#             VALUES (?, 0, ?, ?)
#             ON CONFLICT(connection_id) DO UPDATE SET interval_minutes = excluded.interval_minutes
#         """, (connection_id, DEFAULT_AUTO_REPLY, interval_minutes))
#         await db.commit()


# async def get_owner_connection(
#     owner_user_id: int
# ):

#     async with aiosqlite.connect(DB_FILE) as db:

#         cursor = await db.execute("""
#             SELECT connection_id

#             FROM business_connections

#             WHERE owner_user_id = ?
#               AND is_enabled = 1

#             ORDER BY connection_id

#             LIMIT 1
#         """, (
#             owner_user_id,
#         ))

#         row = await cursor.fetchone()

#     return row[0] if row else None


# async def get_auto_settings(
#     connection_id: str
# ):

#     async with aiosqlite.connect(DB_FILE) as db:

#         cursor = await db.execute("""
#             SELECT
#                 enabled,
#                 reply_text

#             FROM auto_responder

#             WHERE connection_id = ?

#             LIMIT 1
#         """, (
#             connection_id,
#         ))

#         row = await cursor.fetchone()

#         if not row:

#             await db.execute("""
#                 INSERT INTO auto_responder (
#                     connection_id,
#                     enabled,
#                     reply_text
#                 )

#                 VALUES (?, 0, ?)
#             """, (
#                 connection_id,
#                 DEFAULT_AUTO_REPLY,
#             ))

#             await db.commit()

#             return (
#                 False,
#                 DEFAULT_AUTO_REPLY,
#             )

#     return (
#         bool(row[0]),
#         row[1],
#     )


# async def set_auto_enabled(
#     connection_id: str,
#     enabled: bool
# ):

#     async with aiosqlite.connect(DB_FILE) as db:

#         await db.execute("""
#             INSERT INTO auto_responder (
#                 connection_id,
#                 enabled,
#                 reply_text
#             )

#             VALUES (?, ?, ?)

#             ON CONFLICT(connection_id)
#             DO UPDATE SET
#                 enabled = excluded.enabled
#         """, (
#             connection_id,
#             int(enabled),
#             DEFAULT_AUTO_REPLY,
#         ))

#         await db.commit()


# async def set_auto_reply(
#     connection_id: str,
#     reply_text: str
# ):

#     async with aiosqlite.connect(DB_FILE) as db:

#         await db.execute("""
#             INSERT INTO auto_responder (
#                 connection_id,
#                 enabled,
#                 reply_text
#             )

#             VALUES (?, 0, ?)

#             ON CONFLICT(connection_id)
#             DO UPDATE SET
#                 reply_text = excluded.reply_text
#         """, (
#             connection_id,
#             reply_text,
#         ))

#         await db.commit()


# # ============================================================
# # .AUTO / .AUTOOFF
# # ============================================================

# async def process_auto_command(
#     message: Message
# ) -> bool:

#     if not message.text:
#         return False

#     command = message.text.strip().lower()

#     connection_id = (
#         message.business_connection_id
#     )

#     if not connection_id:
#         return False

#     owner_id = await get_business_owner_id(
#         connection_id
#     )

#     sender_id = (
#         message.from_user.id
#         if message.from_user
#         else None
#     )

#     if (
#         owner_id is None
#         or sender_id != owner_id
#     ):
#         return True if (
#             command == ".auto"
#             or command == ".autooff"
#             or command.startswith(".auto ")
#         ) else False

#     # ========================================================
#     # .AUTOOFF
#     # ========================================================

#     if command == ".autooff":

#         await set_auto_enabled(
#             connection_id,
#             False,
#         )

#         try:

#             await BOT.edit_message_text(
#                 chat_id=message.chat.id,
#                 message_id=message.message_id,
#                 business_connection_id=connection_id,
#                 text=(
#                     "🤖 <b>Автоответчик выключен.</b>\n\n"
#                     "Чтобы включить снова:\n"
#                     "<code>.auto</code>"
#                 ),
#                 parse_mode="HTML",
#             )

#         except Exception:

#             logging.exception(
#                 "AUTOOFF EDIT ERROR"
#             )

#         return True

#     # ========================================================
#     # .AUTO
#     # ========================================================

#     parts = message.text.strip().split(
#         maxsplit=1
#     )

#     if (
#         not parts
#         or parts[0].lower() != ".auto"
#     ):
#         return False

#     argument = (
#         parts[1].strip().lower()
#         if len(parts) > 1
#         else ""
#     )

#     if argument in (
#         "off",
#         "выкл",
#         "выключить",
#     ):

#         await set_auto_enabled(
#             connection_id,
#             False,
#         )

#         text = (
#             "🤖 <b>Автоответчик выключен.</b>\n\n"
#             "Чтобы включить:\n"
#             "<code>.auto</code>\n\n"
#             "Или используй:\n"
#             "<code>.autooff</code>"
#         )

#         enabled_now = False

#     else:

#         await set_auto_enabled(
#             connection_id,
#             True,
#         )

#         text = (
#             "🤖 <b>Автоответчик включён!</b>\n\n"
#             "Теперь собеседникам автоматически "
#             "будет отправляться настроенный ответ.\n\n"
#             "Изменить текст можно через кнопку "
#             "«🤖 Автоответчик» в боте.\n\n"
#             "Выключить:\n"
#             "<code>.autooff</code>"
#         )

#         enabled_now = True

#     try:

#         await BOT.edit_message_text(
#             chat_id=message.chat.id,
#             message_id=message.message_id,
#             business_connection_id=connection_id,
#             text=text,
#             parse_mode="HTML",
#         )

#     except Exception:

#         logging.exception(
#             "AUTO COMMAND EDIT ERROR"
#         )

#     return True


# # ============================================================
# # AUTO REPLY
# # ============================================================

# async def process_auto_reply(
#     message: Message
# ) -> bool:

#     connection_id = (
#         message.business_connection_id
#     )

#     if not connection_id:
#         return False

#     owner_id = await get_business_owner_id(
#         connection_id
#     )

#     sender_id = (
#         message.from_user.id
#         if message.from_user
#         else None
#     )

#     if (
#         owner_id is None
#         or sender_id == owner_id
#     ):
#         return False

#     enabled, reply_text = await get_auto_settings(
#         connection_id
#     )

#     if not enabled:
#         return False

#     interval_minutes = await get_auto_interval(connection_id)
#     now = time.time()
#     if interval_minutes > 0:
#         async with aiosqlite.connect(DB_FILE) as db:
#             cursor = await db.execute(
#                 "SELECT last_sent_at FROM auto_reply_log WHERE connection_id = ? AND chat_id = ? LIMIT 1",
#                 (connection_id, message.chat.id),
#             )
#             row = await cursor.fetchone()
#         if row and now - float(row[0]) < interval_minutes * 60:
#             logging.info("AUTO REPLY SKIPPED | connection=%s | chat=%s", connection_id, message.chat.id)
#             return True

#     final_reply = build_auto_reply(
#         reply_text
#     )

#     try:

#         await BOT.send_message(
#             chat_id=message.chat.id,
#             text=final_reply,
#             business_connection_id=connection_id,
#             parse_mode="HTML",
#         )

#         if interval_minutes > 0:
#             async with aiosqlite.connect(DB_FILE) as db:
#                 await db.execute("""
#                     INSERT INTO auto_reply_log (connection_id, chat_id, last_sent_at)
#                     VALUES (?, ?, ?)
#                     ON CONFLICT(connection_id, chat_id)
#                     DO UPDATE SET last_sent_at = excluded.last_sent_at
#                 """, (connection_id, message.chat.id, now))
#                 await db.commit()

#         logging.info(
#             "AUTO REPLY SENT | connection=%s | chat=%s | sender=%s",
#             connection_id,
#             message.chat.id,
#             sender_id,
#         )

#         return True

#     except Exception:

#         logging.exception(
#             "AUTO REPLY ERROR | connection=%s | chat=%s",
#             connection_id,
#             message.chat.id,
#         )

#         return False


# # ============================================================
# # AUTO SETTINGS
# # ============================================================

# @router.callback_query(
#     lambda callback:
#         callback.data == "auto_settings"
# )
# async def auto_settings_handler(
#     callback: CallbackQuery
# ):

#     if not await is_subscribed(
#         callback.from_user.id
#     ):

#         await callback.answer(
#             "🔒 Сначала подпишитесь на канал",
#             show_alert=True,
#         )

#         return

#     connection_id = await get_owner_connection(
#         callback.from_user.id
#     )

#     if not connection_id:

#         await callback.answer(
#             "🔴 Сначала подключите Business",
#             show_alert=True,
#         )

#         return

#     enabled, reply_text = await get_auto_settings(
#         connection_id
#     )

#     interval_minutes = await get_auto_interval(connection_id)
#     interval_label = {0: "⚡ Каждое сообщение", 5: "🕔 Раз в 5 минут", 10: "🕙 Раз в 10 минут", 15: "🕒 Раз в 15 минут"}.get(interval_minutes, "⚡ Каждое сообщение")

#     await callback.answer()

#     text = (
#         "🤖 <b>Автоответчик</b>\n\n"

#         f"Статус: "
#         f"{'🟢 включён' if enabled else '🔴 выключен'}\n"
#         f"<b>Частота автоответа:</b> {interval_label}\n\n"

#         "<b>Текущий ответ:</b>\n"
#         f"{html.escape(reply_text)}\n\n"

#         "✨ <i>К каждому автоответу автоматически "
#         "добавляется:</i>\n\n"

#         f'✨ <i>Это бесплатный автоответчик от бота '
#         f'<a href="{BOT_URL}">{BOT_USERNAME}</a> 😉</i>\n\n'

#         "Эта подпись фиксированная и "
#         "<b>не изменяется</b>."
#     )

#     try:

#         await callback.message.edit_text(
#             text,
#             reply_markup=auto_settings_keyboard(
#                 enabled, interval_minutes
#             ),
#             parse_mode="HTML",
#         )

#     except Exception:

#         await callback.message.answer(
#             text,
#             reply_markup=auto_settings_keyboard(
#                 enabled, interval_minutes
#             ),
#             parse_mode="HTML",
#         )


# # ============================================================
# # AUTO TOGGLE
# # ============================================================

# @router.callback_query(
#     lambda callback:
#         callback.data == "auto_toggle"
# )
# async def auto_toggle_handler(
#     callback: CallbackQuery
# ):

#     connection_id = await get_owner_connection(
#         callback.from_user.id
#     )

#     if not connection_id:

#         await callback.answer(
#             "🔴 Business не подключён",
#             show_alert=True,
#         )

#         return

#     enabled, reply_text = await get_auto_settings(
#         connection_id
#     )
#     interval_minutes = await get_auto_interval(connection_id)
#     interval_label = {0: "⚡ Каждое сообщение", 5: "🕔 Раз в 5 минут", 10: "🕙 Раз в 10 минут", 15: "🕒 Раз в 15 минут"}.get(interval_minutes, "⚡ Каждое сообщение")

#     enabled = not enabled

#     await set_auto_enabled(
#         connection_id,
#         enabled,
#     )

#     await callback.answer(
#         "🟢 Включён"
#         if enabled
#         else
#         "🔴 Выключен"
#     )

#     text = (
#         "🤖 <b>Автоответчик</b>\n\n"

#         f"Статус: "
#         f"{'🟢 включён' if enabled else '🔴 выключен'}\n\n"

#         "<b>Текущий ответ:</b>\n"
#         f"{html.escape(reply_text)}\n\n"

#         "✨ <i>К каждому автоответу автоматически "
#         "добавляется:</i>\n\n"

#         f'✨ <i>Это бесплатный автоответчик от бота '
#         f'<a href="{BOT_URL}">{BOT_USERNAME}</a> 😉</i>\n\n'

#         "Эта подпись фиксированная и "
#         "<b>не изменяется</b>."
#     )

#     await callback.message.edit_text(
#         text,
#         reply_markup=auto_settings_keyboard(
#             enabled, interval_minutes
#         ),
#         parse_mode="HTML",
#     )


# # ============================================================
# # AUTO REPLY INTERVAL
# # ============================================================

# @router.callback_query(lambda callback: callback.data in {
#     "auto_interval_0", "auto_interval_5", "auto_interval_10", "auto_interval_15",
# })
# async def auto_interval_handler(callback: CallbackQuery):
#     connection_id = await get_owner_connection(callback.from_user.id)
#     if not connection_id:
#         await callback.answer("🔴 Business не подключён", show_alert=True)
#         return

#     interval_minutes = int(callback.data.rsplit("_", 1)[1])
#     await set_auto_interval(connection_id, interval_minutes)
#     labels = {0: "⚡ Каждое сообщение", 5: "🕔 Раз в 5 минут", 10: "🕙 Раз в 10 минут", 15: "🕒 Раз в 15 минут"}
#     enabled, reply_text = await get_auto_settings(connection_id)
#     await callback.answer("✅ Частота обновлена")
#     text = (
#         "🤖 <b>Автоответчик</b>\n\n"
#         f"Статус: {'🟢 включён' if enabled else '🔴 выключен'}\n"
#         f"<b>Частота автоответа:</b> {labels[interval_minutes]}\n\n"
#         "<b>Текущий ответ:</b>\n"
#         f"{html.escape(reply_text)}\n\n"
#         "✨ <i>К каждому автоответу автоматически добавляется:</i>\n\n"
#         f'✨ <i>Это бесплатный автоответчик от бота <a href="{BOT_URL}">{BOT_USERNAME}</a> 😉</i>\n\n'
#         "Эта подпись фиксированная и <b>не изменяется</b>."
#     )
#     await callback.message.edit_text(text, reply_markup=auto_settings_keyboard(enabled, interval_minutes), parse_mode="HTML")


# # ============================================================
# # AUTO EDIT
# # ============================================================

# @router.callback_query(
#     lambda callback:
#         callback.data == "auto_edit"
# )
# async def auto_edit_handler(
#     callback: CallbackQuery
# ):

#     connection_id = await get_owner_connection(
#         callback.from_user.id
#     )

#     if not connection_id:

#         await callback.answer(
#             "🔴 Business не подключён",
#             show_alert=True,
#         )

#         return

#     async with aiosqlite.connect(DB_FILE) as db:

#         await db.execute("""
#             INSERT INTO auto_pending (
#                 owner_user_id,
#                 connection_id
#             )

#             VALUES (?, ?)

#             ON CONFLICT(owner_user_id)
#             DO UPDATE SET
#                 connection_id = excluded.connection_id
#         """, (
#             callback.from_user.id,
#             connection_id,
#         ))

#         await db.commit()

#     await callback.answer()

#     await callback.message.answer(
#         "✏️ <b>Отправь следующим сообщением "
#         "текст автоответа.</b>\n\n"

#         "Он будет отправляться собеседнику, "
#         "когда автоответчик включён.\n\n"

#         "✨ Рекламная подпись "
#         "<b>добавляется автоматически</b> "
#         "и изменить её нельзя.\n\n"

#         "Чтобы отменить настройку, отправь "
#         "<code>/cancel</code>.",

#         parse_mode="HTML",
#     )


# # ============================================================
# # AUTO TEXT INPUT
# # ============================================================

# @router.message(
#     lambda message:
#         message.chat.type == "private"
#         and bool(message.from_user)
# )
# async def auto_text_input_handler(
#     message: Message
# ):

#     if (
#         message.text
#         and message.text.strip().lower()
#         == "/cancel"
#     ):

#         async with aiosqlite.connect(DB_FILE) as db:

#             await db.execute(
#                 """
#                 DELETE FROM auto_pending
#                 WHERE owner_user_id = ?
#                 """,
#                 (
#                     message.from_user.id,
#                 ),
#             )

#             await db.commit()

#         await message.answer(
#             "❌ Настройка автоответчика отменена."
#         )

#         return

#     if (
#         not message.text
#         or not message.text.strip()
#     ):
#         return

#     async with aiosqlite.connect(DB_FILE) as db:

#         cursor = await db.execute(
#             """
#             SELECT connection_id

#             FROM auto_pending

#             WHERE owner_user_id = ?

#             LIMIT 1
#             """,
#             (
#                 message.from_user.id,
#             ),
#         )

#         row = await cursor.fetchone()

#         if not row:
#             return

#         connection_id = row[0]

#         await db.execute(
#             """
#             DELETE FROM auto_pending

#             WHERE owner_user_id = ?
#             """,
#             (
#                 message.from_user.id,
#             ),
#         )

#         await db.commit()

#     reply_text = message.text.strip()

#     await set_auto_reply(
#         connection_id,
#         reply_text,
#     )

#     enabled, _ = await get_auto_settings(
#         connection_id
#     )

#     await message.answer(
#         "✅ <b>Автоответ сохранён!</b>\n\n"

#         f"Статус: "
#         f"{'🟢 включён' if enabled else '🔴 выключен'}\n\n"

#         "<b>Текст:</b>\n"
#         f"{html.escape(reply_text)}\n\n"

#         "✨ <i>К каждому автоответу автоматически "
#         "добавляется:</i>\n\n"

#         f'✨ <i>Это бесплатный автоответчик от бота '
#         f'<a href="{BOT_URL}">{BOT_USERNAME}</a> 😉</i>\n\n'

#         "Эта подпись фиксированная и "
#         "<b>не изменяется</b>.",

#         reply_markup=auto_settings_keyboard(
#             enabled, await get_auto_interval(connection_id)
#         ),

#         parse_mode="HTML",
#     )


# # ============================================================
# # BUSINESS OWNER
# # ============================================================

# async def get_business_owner_id(
#     connection_id: str
# ):

#     async with aiosqlite.connect(DB_FILE) as db:

#         cursor = await db.execute("""
#             SELECT owner_user_id

#             FROM business_connections

#             WHERE connection_id = ?
#               AND is_enabled = 1

#             LIMIT 1
#         """, (
#             connection_id,
#         ))

#         row = await cursor.fetchone()

#     return row[0] if row else None


# # ============================================================
# # STREAK
# # ============================================================

# def get_tashkent_date(message_date: datetime | None = None):
#     """Возвращает календарную дату по времени Ташкента (UTC+5)."""
#     tashkent_tz = timezone(timedelta(hours=5))
#     value = message_date or datetime.now(timezone.utc)

#     if value.tzinfo is None:
#         value = value.replace(tzinfo=timezone.utc)

#     return value.astimezone(tashkent_tz).date()


# async def update_streak(
#     connection_id: str,
#     chat_id: int,
#     message_date: datetime | None = None,
# ) -> int:
#     """
#     Обновляет стрик чата максимум один раз за календарный день.
#     Если между активными днями есть пропуск, новый стрик начинается с 1.
#     Ограничения максимальной длины нет.
#     """
#     today = get_tashkent_date(message_date)
#     today_str = today.isoformat()

#     async with aiosqlite.connect(DB_FILE) as db:
#         cursor = await db.execute("""
#             SELECT current_streak, best_streak, last_active_date
#             FROM chat_streaks
#             WHERE connection_id = ? AND chat_id = ?
#             LIMIT 1
#         """, (connection_id, chat_id))
#         row = await cursor.fetchone()

#         if row is None:
#             current_streak = 1
#             best_streak = 1

#             await db.execute("""
#                 INSERT INTO chat_streaks (
#                     connection_id, chat_id, current_streak,
#                     best_streak, last_active_date
#                 )
#                 VALUES (?, ?, ?, ?, ?)
#             """, (
#                 connection_id, chat_id, current_streak,
#                 best_streak, today_str
#             ))

#         else:
#             current_streak, best_streak, last_active_str = row

#             if not last_active_str:
#                 current_streak = 1
#             else:
#                 last_active = datetime.strptime(
#                     last_active_str, "%Y-%m-%d"
#                 ).date()

#                 # Не позволяем запоздавшему сообщению откатить дату назад.
#                 if today < last_active:
#                     return current_streak

#                 if today == last_active:
#                     return current_streak

#                 if today - last_active == timedelta(days=1):
#                     current_streak += 1
#                 else:
#                     current_streak = 1

#             best_streak = max(best_streak, current_streak)

#             await db.execute("""
#                 UPDATE chat_streaks
#                 SET current_streak = ?,
#                     best_streak = ?,
#                     last_active_date = ?
#                 WHERE connection_id = ? AND chat_id = ?
#             """, (
#                 current_streak, best_streak, today_str,
#                 connection_id, chat_id
#             ))

#         await db.commit()

#     return current_streak


# async def process_streak_command(message: Message) -> bool:
#     if not message.text or message.text.strip().lower() != ".streak":
#         return False

#     connection_id = message.business_connection_id
#     if not connection_id:
#         return False

#     sender_id = message.from_user.id if message.from_user else None
#     owner_id = await get_business_owner_id(connection_id)

#     # Команду может использовать только владелец Business-аккаунта.
#     if owner_id is None or sender_id != owner_id:
#         return True

#     async with aiosqlite.connect(DB_FILE) as db:
#         cursor = await db.execute("""
#             SELECT current_streak, best_streak, last_active_date
#             FROM chat_streaks
#             WHERE connection_id = ? AND chat_id = ?
#             LIMIT 1
#         """, (connection_id, message.chat.id))
#         row = await cursor.fetchone()

#     if row:
#         current, best, last_active = row
#         response = (
#             "🔥 <b>Стрик общения</b>\n\n"
#             f"🔥 Текущий стрик: <b>{current} дн.</b>\n"
#             f"🏆 Рекорд: <b>{best} дн.</b>\n"
#             f"📅 Последняя активность: <code>{esc(last_active)}</code>\n\n"
#             "Общайтесь хотя бы раз в день, чтобы сохранить стрик."
#         )
#     else:
#         response = (
#             "🔥 <b>Стрик общения</b>\n\n"
#             "Пока нет данных об активности этого чата."
#         )

#     try:
#         await BOT.edit_message_text(
#             chat_id=message.chat.id,
#             message_id=message.message_id,
#             business_connection_id=connection_id,
#             text=response,
#             parse_mode="HTML",
#         )
#     except Exception:
#         logging.exception("STREAK COMMAND EDIT ERROR")

#     return True


# # ============================================================
# # .CAT COMMAND
# # ============================================================

# async def process_cat_command(
#     message: Message
# ) -> bool:

#     if not message.text:
#         return False

#     if message.text.strip().lower() != ".cat":
#         return False

#     connection_id = (
#         message.business_connection_id
#     )

#     if not connection_id:
#         return False

#     sender_id = (
#         message.from_user.id
#         if message.from_user
#         else None
#     )

#     owner_id = await get_business_owner_id(
#         connection_id
#     )

#     if (
#         owner_id is None
#         or sender_id != owner_id
#     ):
#         return True

#     try:

#         await BOT.edit_message_text(
#             chat_id=message.chat.id,
#             message_id=message.message_id,
#             business_connection_id=connection_id,
#             text="🐱",
#         )

#         cat_id = None
#         cat_url = None

#         last_cat_id = LAST_CAT_IDS.get(
#             connection_id
#         )

#         for _ in range(5):

#             def fetch_cat_metadata():

#                 cache_buster = (
#                     f"{time.time_ns()}_"
#                     f"{random.randint(1, 999999999)}"
#                 )

#                 request = urllib.request.Request(
#                     (
#                         "https://cataas.com/cat?"
#                         f"json=true&cb={cache_buster}"
#                     ),
#                     headers={
#                         "User-Agent": "Mozilla/5.0",
#                         "Cache-Control":
#                             "no-cache, no-store, max-age=0",
#                         "Pragma":
#                             "no-cache",
#                     },
#                 )

#                 with urllib.request.urlopen(
#                     request,
#                     timeout=15
#                 ) as response:

#                     return json.loads(
#                         response.read().decode(
#                             "utf-8"
#                         )
#                     )

#             metadata = await asyncio.to_thread(
#                 fetch_cat_metadata
#             )

#             cat_id = (
#                 metadata.get("id")
#                 or metadata.get("_id")
#             )

#             if (
#                 cat_id
#                 and cat_id != last_cat_id
#             ):

#                 base_url = metadata.get(
#                     "url"
#                 )

#                 if base_url:

#                     if base_url.startswith("/"):
#                         base_url = (
#                             "https://cataas.com"
#                             + base_url
#                         )

#                     cat_url = (
#                         f"{base_url}"
#                         f"{'&' if '?' in base_url else '?'}"
#                         f"cb={time.time_ns()}_"
#                         f"{random.randint(1, 999999999)}"
#                     )

#                     break

#         if not cat_url:

#             cat_url = (
#                 "https://cataas.com/cat?"
#                 f"cb={time.time_ns()}_"
#                 f"{random.randint(1, 999999999)}"
#             )

#         if cat_id:
#             LAST_CAT_IDS[
#                 connection_id
#             ] = cat_id

#         await BOT.edit_message_media(
#             chat_id=message.chat.id,
#             message_id=message.message_id,
#             business_connection_id=connection_id,
#             media=InputMediaPhoto(
#                 media=cat_url,
#             ),
#         )

#     except Exception:

#         logging.exception(
#             "CAT COMMAND ERROR | "
#             "connection=%s | chat=%s | message=%s",
#             connection_id,
#             message.chat.id,
#             message.message_id,
#         )

#     return True


# # ============================================================
# # NEW BUSINESS MESSAGE
# # ============================================================

# @router.business_message()
# async def business_message_handler(
#     message: Message,
# ):

#     connection_id = (
#         message.business_connection_id
#     )

#     if not connection_id:
#         return

#     # .STREAK
#     if await process_streak_command(message):
#         return

#     # .AUTO / .AUTOOFF
#     if await process_auto_command(
#         message
#     ):
#         return

#     # .CAT
#     if await process_cat_command(
#         message
#     ):
#         return

#     # GPT
#     if await process_gpt_command(
#         message
#     ):
#         return

#     # Обновляем стрик по обычным сообщениям, не по командам бота.
#     # Один календарный день учитывается только один раз.
#     try:
#         await update_streak(
#             connection_id,
#             message.chat.id,
#             message.date,
#         )
#     except Exception:
#         logging.exception(
#             "STREAK UPDATE ERROR | connection=%s | chat=%s",
#             connection_id,
#             message.chat.id,
#         )

#     # AUTO REPLY
#     if await process_auto_reply(
#         message
#     ):
#         return

#     # Обычное сообщение
#     content_type, text_value, file_id = (
#         get_content(message)
#     )

#     sender_id = (
#         message.from_user.id
#         if message.from_user
#         else None
#     )

#     sender_name = get_sender_name(
#         message
#     )

#     chat_name = get_chat_name(
#         message
#     )

#     created_at = (
#         message.date.isoformat()
#         if message.date
#         else datetime.now(
#             timezone.utc
#         ).isoformat()
#     )

#     async with aiosqlite.connect(
#         DB_FILE
#     ) as db:

#         cursor = await db.execute("""
#             SELECT id

#             FROM messages

#             WHERE connection_id = ?
#               AND chat_id = ?
#               AND message_id = ?

#             LIMIT 1
#         """, (
#             connection_id,
#             message.chat.id,
#             message.message_id,
#         ))

#         existing = await cursor.fetchone()

#         if existing:
#             return

#         await db.execute("""
#             INSERT INTO messages (
#                 connection_id,
#                 chat_id,
#                 message_id,
#                 sender_id,
#                 sender_name,
#                 chat_name,
#                 text,
#                 content_type,
#                 file_id,
#                 created_at
#             )

#             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
#         """, (
#             connection_id,
#             message.chat.id,
#             message.message_id,
#             sender_id,
#             sender_name,
#             chat_name,
#             text_value,
#             content_type,
#             file_id,
#             created_at,
#         ))

#         await db.commit()

#     logging.info(
#         "MESSAGE SAVED | "
#         "connection=%s | "
#         "chat=%s | "
#         "message=%s | "
#         "sender=%s | "
#         "type=%s",
#         connection_id,
#         message.chat.id,
#         message.message_id,
#         sender_name,
#         content_type,
#     )


# # ============================================================
# # EDITED BUSINESS MESSAGE
# # ============================================================

# @router.edited_business_message()
# async def edited_business_message_handler(
#     message: Message,
# ):

#     connection_id = (
#         message.business_connection_id
#     )

#     if not connection_id:
#         return

#     if await is_saved_gpt_message(
#         connection_id,
#         message.chat.id,
#         message.message_id,
#     ):
#         return

#     content_type, new_text, file_id = (
#         get_content(message)
#     )

#     async with aiosqlite.connect(
#         DB_FILE
#     ) as db:

#         cursor = await db.execute("""
#             SELECT
#                 sender_name,
#                 chat_name,
#                 text

#             FROM messages

#             WHERE connection_id = ?
#               AND chat_id = ?
#               AND message_id = ?

#             LIMIT 1
#         """, (
#             connection_id,
#             message.chat.id,
#             message.message_id,
#         ))

#         row = await cursor.fetchone()

#         if not row:
#             return

#         sender_name = row[0]
#         chat_name = row[1]
#         old_text = row[2]

#         await db.execute("""
#             INSERT INTO message_versions (
#                 connection_id,
#                 chat_id,
#                 message_id,
#                 text,
#                 saved_at
#             )

#             VALUES (?, ?, ?, ?, datetime('now'))
#         """, (
#             connection_id,
#             message.chat.id,
#             message.message_id,
#             old_text,
#         ))

#         await db.execute("""
#             UPDATE messages

#             SET
#                 text = ?,
#                 content_type = ?,
#                 file_id = ?,
#                 edited = 1

#             WHERE connection_id = ?
#               AND chat_id = ?
#               AND message_id = ?
#         """, (
#             new_text,
#             content_type,
#             file_id,
#             connection_id,
#             message.chat.id,
#             message.message_id,
#         ))

#         cursor = await db.execute("""
#             SELECT owner_chat_id

#             FROM business_connections

#             WHERE connection_id = ?
#               AND is_enabled = 1

#             LIMIT 1
#         """, (
#             connection_id,
#         ))

#         owner = await cursor.fetchone()

#         await db.commit()

#     if not owner:
#         return

#     owner_chat_id = owner[0]

#     notification = (
#         "✏️ <b>СООБЩЕНИЕ ИЗМЕНЕНО</b>\n\n"

#         f"💬 <b>Чат:</b> {esc(chat_name)}\n"
#         f"👤 <b>Автор:</b> {esc(sender_name)}\n"
#         f"🆔 <b>ID:</b> {message.message_id}\n\n"

#         "🔴 <b>Было:</b>\n"
#         f"{esc(old_text)}\n\n"

#         "🟢 <b>Стало:</b>\n"
#         f"{esc(new_text)}"
#     )

#     try:

#         await BOT.send_message(
#             owner_chat_id,
#             notification,
#             parse_mode="HTML",
#         )

#     except Exception:

#         logging.exception(
#             "FAILED TO SEND EDIT NOTIFICATION"
#         )


# # ============================================================
# # DELETED BUSINESS MESSAGES
# # ============================================================

# @router.deleted_business_messages()
# async def deleted_business_messages_handler(
#     event: BusinessMessagesDeleted,
# ):

#     connection_id = (
#         event.business_connection_id
#     )

#     logging.info("")
#     logging.info("========================================")
#     logging.info("DELETED BUSINESS MESSAGES")
#     logging.info("Connection: %s", connection_id)
#     logging.info("Chat: %s", event.chat.id)
#     logging.info(
#         "Message IDs: %s",
#         event.message_ids,
#     )
#     logging.info("========================================")

#     async with aiosqlite.connect(
#         DB_FILE
#     ) as db:

#         cursor = await db.execute("""
#             SELECT owner_chat_id

#             FROM business_connections

#             WHERE connection_id = ?
#               AND is_enabled = 1

#             LIMIT 1
#         """, (
#             connection_id,
#         ))

#         owner = await cursor.fetchone()

#         if not owner:
#             return

#         owner_chat_id = owner[0]

#         for message_id in event.message_ids:

#             # =================================================
#             # GPT сообщения не восстанавливаем
#             # =================================================

#             cursor = await db.execute("""
#                 SELECT 1

#                 FROM gpt_messages

#                 WHERE connection_id = ?
#                   AND chat_id = ?
#                   AND message_id = ?

#                 LIMIT 1
#             """, (
#                 connection_id,
#                 event.chat.id,
#                 message_id,
#             ))

#             if await cursor.fetchone():
#                 continue

#             # =================================================
#             # Получаем сохранённое сообщение
#             # =================================================

#             cursor = await db.execute("""
#                 SELECT
#                     sender_name,
#                     chat_name,
#                     text,
#                     content_type,
#                     file_id

#                 FROM messages

#                 WHERE connection_id = ?
#                   AND chat_id = ?
#                   AND message_id = ?

#                 LIMIT 1
#             """, (
#                 connection_id,
#                 event.chat.id,
#                 message_id,
#             ))

#             row = await cursor.fetchone()

#             if not row:

#                 logging.warning(
#                     "MESSAGE %s NOT FOUND IN DATABASE",
#                     message_id,
#                 )

#                 continue

#             (
#                 sender_name,
#                 chat_name,
#                 text_value,
#                 content_type,
#                 file_id,
#             ) = row

#             # =================================================
#             # Помечаем как удалённое
#             # =================================================

#             await db.execute("""
#                 UPDATE messages

#                 SET deleted = 1

#                 WHERE connection_id = ?
#                   AND chat_id = ?
#                   AND message_id = ?
#             """, (
#                 connection_id,
#                 event.chat.id,
#                 message_id,
#             ))

#             # =================================================
#             # Определяем текст
#             # =================================================

#             if text_value:

#                 deleted_text = text_value

#             elif content_type:

#                 deleted_text = (
#                     f"[{content_type}]"
#                 )

#             else:

#                 deleted_text = "[без текста]"

#             # =================================================
#             # Уведомление
#             # =================================================

#             notification = (
#                 "🗑 <b>СООБЩЕНИЕ УДАЛЕНО</b>\n\n"

#                 f"💬 <b>Чат:</b> {esc(chat_name)}\n"
#                 f"👤 <b>Автор:</b> {esc(sender_name)}\n"
#                 f"🆔 <b>ID:</b> {message_id}\n\n"

#                 "🔴 <b>Сообщение:</b>\n"
#                 f"{esc(deleted_text)}"
#             )

#             try:

#                 await BOT.send_message(
#                     owner_chat_id,
#                     notification,
#                     parse_mode="HTML",
#                 )

#             except Exception:

#                 logging.exception(
#                     "FAILED TO SEND DELETE NOTIFICATION"
#                 )

#             # =================================================
#             # Если файла нет — дальше нечего отправлять
#             # =================================================

#             if not file_id:
#                 continue

#             # =================================================
#             # ВОССТАНОВЛЕНИЕ МЕДИА
#             # =================================================

#             try:

#                 # ------------------------------------------------
#                 # 🎤 ГОЛОСОВОЕ
#                 # ------------------------------------------------

#                 if content_type == "voice":

#                     await BOT.send_voice(
#                         chat_id=owner_chat_id,
#                         voice=file_id,
#                         caption=(
#                             "🎤 <b>Удалённое голосовое</b>\n\n"
#                             f"👤 <b>Автор:</b> "
#                             f"{esc(sender_name)}"
#                         ),
#                         parse_mode="HTML",
#                     )

#                 # ------------------------------------------------
#                 # ⭕ КРУЖОК
#                 # ------------------------------------------------

#                 elif content_type == "video_note":

#                     await BOT.send_video_note(
#                         chat_id=owner_chat_id,
#                         video_note=file_id,
#                     )

#                     await BOT.send_message(
#                         owner_chat_id,
#                         (
#                             "⭕ <b>Удалённый видеокружок</b>\n\n"
#                             f"👤 <b>Автор:</b> "
#                             f"{esc(sender_name)}"
#                         ),
#                         parse_mode="HTML",
#                     )

#                 # ------------------------------------------------
#                 # 🎭 СТИКЕР
#                 # ------------------------------------------------

#                 elif content_type == "sticker":

#                     await BOT.send_sticker(
#                         chat_id=owner_chat_id,
#                         sticker=file_id,
#                     )

#                     await BOT.send_message(
#                         owner_chat_id,
#                         (
#                             "🎭 <b>Удалённый стикер</b>\n\n"
#                             f"👤 <b>Автор:</b> "
#                             f"{esc(sender_name)}"
#                         ),
#                         parse_mode="HTML",
#                     )

#                 # ------------------------------------------------
#                 # 📷 ФОТО
#                 # ------------------------------------------------

#                 elif content_type == "photo":

#                     await BOT.send_photo(
#                         chat_id=owner_chat_id,
#                         photo=file_id,
#                         caption=(
#                             "📷 <b>Удалённое фото</b>\n\n"
#                             f"👤 <b>Автор:</b> "
#                             f"{esc(sender_name)}"
#                         ),
#                         parse_mode="HTML",
#                     )

#                 # ------------------------------------------------
#                 # 🎬 ВИДЕО
#                 # ------------------------------------------------

#                 elif content_type == "video":

#                     await BOT.send_video(
#                         chat_id=owner_chat_id,
#                         video=file_id,
#                         caption=(
#                             "🎬 <b>Удалённое видео</b>\n\n"
#                             f"👤 <b>Автор:</b> "
#                             f"{esc(sender_name)}"
#                         ),
#                         parse_mode="HTML",
#                     )

#                 # ------------------------------------------------
#                 # 🎵 АУДИО
#                 # ------------------------------------------------

#                 elif content_type == "audio":

#                     await BOT.send_audio(
#                         chat_id=owner_chat_id,
#                         audio=file_id,
#                         caption=(
#                             "🎵 <b>Удалённое аудио</b>\n\n"
#                             f"👤 <b>Автор:</b> "
#                             f"{esc(sender_name)}"
#                         ),
#                         parse_mode="HTML",
#                     )

#                 # ------------------------------------------------
#                 # 📄 ДОКУМЕНТ
#                 # ------------------------------------------------

#                 elif content_type == "document":

#                     await BOT.send_document(
#                         chat_id=owner_chat_id,
#                         document=file_id,
#                         caption=(
#                             "📄 <b>Удалённый документ</b>\n\n"
#                             f"👤 <b>Автор:</b> "
#                             f"{esc(sender_name)}"
#                         ),
#                         parse_mode="HTML",
#                     )

#                 # ------------------------------------------------
#                 # 🎞 АНИМАЦИЯ / GIF
#                 # ------------------------------------------------

#                 elif content_type == "animation":

#                     await BOT.send_animation(
#                         chat_id=owner_chat_id,
#                         animation=file_id,
#                         caption=(
#                             "🎞 <b>Удалённая анимация</b>\n\n"
#                             f"👤 <b>Автор:</b> "
#                             f"{esc(sender_name)}"
#                         ),
#                         parse_mode="HTML",
#                     )

#                 else:

#                     logging.info(
#                         "MEDIA TYPE NOT SUPPORTED | "
#                         "type=%s | message=%s",
#                         content_type,
#                         message_id,
#                     )

#             except Exception:

#                 logging.exception(
#                     "FAILED TO RESTORE DELETED MEDIA | "
#                     "type=%s | message=%s",
#                     content_type,
#                     message_id,
#                 )

#         await db.commit()


# # ============================================================
# # MAIN
# # ============================================================

# async def main():

#     global BOT

#     await init_db()

#     BOT = Bot(
#         token=BOT_TOKEN
#     )

#     dp = Dispatcher()

#     dp.include_router(
#         router
#     )

#     logging.info("")
#     logging.info("========================================")
#     logging.info("BOT STARTING")

#     logging.info(
#         "REQUIRED CHANNEL RAW: %s",
#         REQUIRED_CHANNEL,
#     )

#     logging.info(
#         "REQUIRED CHANNEL ID: %s",
#         CHANNEL_CHAT_ID,
#     )

#     logging.info(
#         "GPT MODEL: %s",
#         GPT_MODEL,
#     )

#     logging.info(
#         "GPT CONTEXT: %s messages",
#         GPT_CONTEXT_MESSAGES,
#     )

#     logging.info(
#         "AUTO PROMO: %s",
#         BOT_USERNAME,
#     )

#     logging.info(
#         "MEDIA ARCHIVE: ENABLED"
#     )

#     logging.info(
#         "VOICE RESTORE: ENABLED"
#     )

#     logging.info(
#         "VIDEO NOTE RESTORE: ENABLED"
#     )

#     logging.info(
#         "STICKER RESTORE: ENABLED"
#     )

#     logging.info("========================================")

#     await dp.start_polling(
#         BOT,

#         allowed_updates=[
#             "message",
#             "callback_query",
#             "business_connection",
#             "business_message",
#             "edited_business_message",
#             "deleted_business_messages",
#         ],
#     )


# # ============================================================
# # RUN
# # ============================================================

# if __name__ == "__main__":

#     try:

#         asyncio.run(main())

#     except KeyboardInterrupt:

#         logging.info(
#             "BOT STOPPED BY USER"
#         )
