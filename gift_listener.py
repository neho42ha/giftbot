import os
import sys
from typing import Set, List, Union
from loguru import logger
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import Message, Chat

load_dotenv()

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
WHITELIST_RAW = os.getenv("WHITELIST_CHATS", "").strip()
KEYWORDS_RAW = os.getenv("KEYWORDS", "gift,подар,дроп,drop,🎁,подарок,Gift").strip()

if not API_ID or not API_HASH:
    print("❌ API_ID/API_HASH не заданы. Проверьте .env", file=sys.stderr)
    sys.exit(1)

# Разбираем белый список
WHITELIST: List[str] = []
if WHITELIST_RAW:
    WHITELIST = [x.strip() for x in WHITELIST_RAW.split(",") if x.strip()]

KEYWORDS: List[str] = [x.strip() for x in KEYWORDS_RAW.split(",") if x.strip()]

# Логирование
logger.remove()
logger.add(sys.stdout, level="INFO", enqueue=True, backtrace=False, diagnose=False)

app = Client("gift_session", api_id=API_ID, api_hash=API_HASH, workdir=".")

# Простая защита от дублей
seen_ids: Set[tuple] = set()  # (chat_id, message_id)

def _in_whitelist(chat: Union[Chat, None]) -> bool:
    if not WHITELIST:
        return True  # если список пуст — слушаем всё (можно поменять)
    if not chat:
        return False
    name = f"@{chat.username}" if chat.username else None
    cid = str(chat.id)
    return (name in WHITELIST) or (cid in WHITELIST)

def looks_like_gift(msg: Message) -> bool:
    # 1) Сервисные сообщения (часто дропы идут как service)
    if getattr(msg, "service", False):
        # Pyrogram 2.x: у некоторых подарков бывает отдельная структура.
        # Чтобы не зависеть от версии, проверяем текст/подпись и типы.
        text = (msg.text or msg.caption or "").lower()
        if any(k.lower() in text for k in KEYWORDS):
            return True

    # 2) Обычные анонсы с текстом/капшеном
    text = (msg.text or msg.caption or "").lower()
    if any(k.lower() in text for k in KEYWORDS):
        return True

    # 3) Перестраховка: медиа/стикеры с эмодзи 🎁 и похожими словами в подписи
    if msg.sticker or msg.photo or msg.video or msg.document:
        if any(k.lower() in text for k in KEYWORDS):
            return True

    return False

@app.on_message(filters.channel | filters.group | filters.service | filters.private)
def handle_msg(_, msg: Message):
    try:
        if not _in_whitelist(msg.chat):
            return

        key = (msg.chat.id if msg.chat else 0, msg.id)
        if key in seen_ids:
            return
        seen_ids.add(key)

        if looks_like_gift(msg):
            chat_title = msg.chat.title if msg.chat and msg.chat.title else (f"@{msg.chat.username}" if msg.chat and msg.chat.username else "чат")
            preview = (msg.text or msg.caption or "").strip()
            if not preview:
                preview = repr(msg)[:200]
            notify = f"🎁 Возможный дроп в {chat_title}\n\n{preview[:500]}"
            app.send_message("me", notify)
            logger.info(f"Alert sent from chat={chat_title} mid={msg.id}")
    except Exception as e:
        logger.exception(f"Handler error: {e}")
        try:
            app.send_message("me", f"⚠️ Ошибка обработчика: {e}")
        except Exception:
            pass

if __name__ == "__main__":
    logger.info("Gift listener starting…")
    app.run()