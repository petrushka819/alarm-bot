import os
import json
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatMemberStatus
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ChatMemberHandler, ContextTypes
)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") or "ВАШ_ТОКЕН_ОТ_BOTFATHER"
DB_FILE = "db.json"
ALARM_COMMANDS = ["alarm"]

def load_db() -> dict:
    try:
        with open(DB_FILE, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"users": {}, "chats": {}, "links": {}}

def save_db():
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

db = load_db()


# ---------- запоминаем чаты, куда нас добавили / из которых удалили ----------

async def track_chats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mc = update.my_chat_member
    chat = mc.chat
    if chat.type not in ("group", "supergroup"):
        return
    cid = str(chat.id)
    if mc.new_chat_member.status in ("member", "administrator"):
        db["chats"][cid] = chat.title or "чат"
    else:
        db["chats"].pop(cid, None)
        db["links"].pop(cid, None)
    save_db()


# ---------- регистрация и подписка из лички ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db["users"][str(user.id)] = user.first_name
    save_db()
    await update.message.reply_text(
        f"Вы зарегистрированы, {user.first_name}!\n\n"
        "Чтобы получать уведомления из чата:\n"
        "1. Добавьте меня в этот чат.\n"
        "2. Напишите мне сюда /subscribe и выберите чат.\n"
        "3. Когда кто-то в чате напишет /alarm — вам придёт уведомление."
    )

async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    db["users"][uid] = update.effective_user.first_name
    save_db()

    buttons = []
    for cid, title in db["chats"].items():
        try:
            m = await context.bot.get_chat_member(int(cid), int(uid))
            if m.status in (ChatMemberStatus.MEMBER,
                            ChatMemberStatus.ADMINISTRATOR,
                            ChatMemberStatus.OWNER):
                subscribed = uid in db["links"].get(cid, [])
                mark = "✅ " if subscribed else ""
                buttons.append([InlineKeyboardButton(f"{mark}{title}",
                                                     callback_data=f"sub:{cid}")])
        except Exception:
            continue

    if not buttons:
        await update.message.reply_text(
            "Пока нет чатов, где я состою и где вы участник. "
            "Добавьте меня в нужный чат и напишите /subscribe снова."
        )
        return
    await update.message.reply_text(
        "Выберите чат (✅ — уже подписаны):",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def on_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    cid = q.data.split(":", 1)[1]
    uid = str(q.from_user.id)
    db["links"].setdefault(cid, [])
    if uid in db["links"][cid]:
        db["links"][cid].remove(uid)
        text = f"Подписка на «{db['chats'].get(cid, 'чат')}» отключена."
    else:
        db["links"][cid].append(uid)
        text = (f"Готово! Теперь /alarm в «{db['chats'].get(cid, 'чат')}» "
                f"будет присылать вам уведомление.")
    save_db()
    await q.edit_message_text(text)


# ---------- команда /alarm в чате ----------

async def send_alarm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    subscribers = db["links"].get(str(chat.id), [])
    if not subscribers:
        return

    sender = update.effective_user
    time = datetime.now().strftime("%H:%M %d.%m")
    who = sender.full_name + (f" (@{sender.username})" if sender.username else "")
    text = (f"🚨 Команда /alarm в чате «{chat.title}»\n"
            f"Кто вызвал: {who}\nКогда: {time}")

    for uid in subscribers:
        try:
            await context.bot.send_message(chat_id=int(uid), text=text)
        except Exception:
            pass


def main():
    if not TOKEN or "ВАШ" in TOKEN:
        raise SystemExit("Не задан токен: создайте переменную окружения TELEGRAM_BOT_TOKEN")

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("subscribe", subscribe))
    app.add_handler(CallbackQueryHandler(on_pick, pattern=r"^sub:"))
    app.add_handler(ChatMemberHandler(track_chats, ChatMemberHandler.MY_CHAT_MEMBER))
    for cmd in ALARM_COMMANDS:
        app.add_handler(CommandHandler(cmd, send_alarm))
    print("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
